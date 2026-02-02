"""Flow analysis utilities for idotaku reports."""

from collections import defaultdict
from urllib.parse import urlparse
from typing import Any


def build_param_producer_consumer(sorted_flows: list[dict]) -> tuple[dict, dict]:
    """Build param producer and consumer mappings.

    Args:
        sorted_flows: List of flow records sorted by timestamp

    Returns:
        Tuple of (param_producer, param_consumers):
        - param_producer: dict mapping param_value to producer info
          {param: {"idx": flow_idx, "method": str, "path": str, "field": str}}
        - param_consumers: defaultdict mapping param_value to list of consumer info
          {param: [{"idx": flow_idx, "method": str, "path": str, "field": str}, ...]}
    """
    param_producer = {}
    param_consumers = defaultdict(list)

    for i, flow in enumerate(sorted_flows):
        method = flow.get("method", "?")
        url = flow.get("url", "?")
        path = urlparse(url).path or "/"

        # Track producers (first response)
        for res_id in flow.get("response_ids", []):
            val = res_id["value"]
            if val not in param_producer:
                param_producer[val] = {
                    "idx": i,
                    "method": method,
                    "path": path,
                    "field": res_id.get("field") or res_id.get("location"),
                }

        # Track consumers
        for req_id in flow.get("request_ids", []):
            val = req_id["value"]
            param_consumers[val].append({
                "idx": i,
                "method": method,
                "path": path,
                "field": req_id.get("field") or req_id.get("location"),
            })

    return param_producer, param_consumers


def build_param_flow_mappings(sorted_flows: list[dict]) -> tuple[dict, dict, dict]:
    """Build param origin/usage mappings for flow graph construction.

    Args:
        sorted_flows: List of flow records sorted by timestamp

    Returns:
        Tuple of (param_origins, param_usages, flow_produces):
        - param_origins: defaultdict[param, list[flow_idx]] - all producers of each param
        - param_usages: defaultdict[param, list[flow_idx]] - all consumers of each param
        - flow_produces: defaultdict[flow_idx, list[param]] - params produced by each flow
    """
    param_origins = defaultdict(list)
    param_usages = defaultdict(list)
    flow_produces = defaultdict(list)

    for i, flow in enumerate(sorted_flows):
        for res_id in flow.get("response_ids", []):
            val = res_id["value"]
            param_origins[val].append(i)
            flow_produces[i].append(val)

        for req_id in flow.get("request_ids", []):
            val = req_id["value"]
            param_usages[val].append(i)

    return param_origins, param_usages, flow_produces


def build_flow_graph(
    param_origins: dict[str, list[int]],
    param_usages: dict[str, list[int]],
) -> dict[int, list[tuple[int, list[str]]]]:
    """Build flow graph from param mappings.

    Creates a graph where edges represent parameter flow from producing
    API to consuming API.

    Args:
        param_origins: Mapping of param to list of producing flow indices
        param_usages: Mapping of param to list of consuming flow indices

    Returns:
        Flow graph: dict[origin_idx, list[(usage_idx, [params])]]
    """
    # Build raw graph with param grouping
    flow_graph_raw = defaultdict(lambda: defaultdict(list))

    for param, origin_idxs in param_origins.items():
        for origin_idx in origin_idxs:
            for usage_idx in param_usages.get(param, []):
                if usage_idx != origin_idx:  # Prevent self-loops only
                    flow_graph_raw[origin_idx][usage_idx].append(param)

    # Convert to list format with sorted edges
    flow_graph = defaultdict(list)
    for origin_idx, usages in flow_graph_raw.items():
        for usage_idx, params in sorted(usages.items()):
            flow_graph[origin_idx].append((usage_idx, params))

    return flow_graph


def build_api_dependencies(
    param_producer: dict,
    param_consumers: dict,
) -> dict[str, dict[str, list[dict]]]:
    """Build API dependency graph.

    Creates a mapping showing which APIs produce parameters consumed by other APIs.

    Args:
        param_producer: Producer mapping from build_param_producer_consumer
        param_consumers: Consumer mapping from build_param_producer_consumer

    Returns:
        API dependencies: dict[producer_api_key, dict[param, list[consumer_info]]]
        where consumer_info = {"api": consumer_api_key, "field": str}
    """
    api_deps = defaultdict(lambda: defaultdict(list))

    for param_val, producer in param_producer.items():
        if param_val not in param_consumers:
            continue

        producer_key = f"{producer['method']} {producer['path']}"

        for consumer in param_consumers[param_val]:
            if consumer["idx"] <= producer["idx"]:
                continue  # Only forward dependencies

            consumer_key = f"{consumer['method']} {consumer['path']}"

            if consumer_key != producer_key:  # Don't self-reference
                api_deps[producer_key][param_val].append({
                    "api": consumer_key,
                    "field": consumer["field"],
                })

    return api_deps


def build_id_transition_map(sorted_flows: list[dict]) -> tuple[dict, dict]:
    """Build ID transition maps for trace visualization.

    Args:
        sorted_flows: List of flow records sorted by timestamp

    Returns:
        Tuple of (id_to_origin, id_to_subsequent_usage):
        - id_to_origin: dict[id_value, {"flow_idx": int, "location": str, "field": str}]
        - id_to_subsequent_usage: dict[id_value, list[{"flow_idx": int, "location": str, "field": str}]]
    """
    id_to_origin = {}
    id_to_subsequent_usage = defaultdict(list)

    for i, flow in enumerate(sorted_flows):
        # Track request IDs for subsequent usage
        for req_id in flow.get("request_ids", []):
            id_val = req_id["value"]
            id_to_subsequent_usage[id_val].append({
                "flow_idx": i,
                "location": req_id.get("location", "?"),
                "field": req_id.get("field"),
            })

        # Track response IDs for origin
        for res_id in flow.get("response_ids", []):
            id_val = res_id["value"]
            if id_val not in id_to_origin:
                id_to_origin[id_val] = {
                    "flow_idx": i,
                    "location": res_id.get("location", "?"),
                    "field": res_id.get("field"),
                }

    return id_to_origin, id_to_subsequent_usage


def find_chain_roots(
    flow_graph: dict[int, list],
    flow_produces: dict[int, list],
    sorted_flows: list[dict],
    min_depth: int = 2,
) -> list[tuple[int, int, int]]:
    """Find and rank root flows for chain trees.

    Args:
        flow_graph: Flow graph from build_flow_graph
        flow_produces: Flow produces mapping
        sorted_flows: List of flow records
        min_depth: Minimum tree depth to include

    Returns:
        List of (flow_idx, depth, node_count) tuples, sorted by depth*nodes descending
    """
    def calc_tree_depth(flow_idx: int, visited: set) -> int:
        """Calculate maximum tree depth from a flow."""
        if flow_idx in visited:
            return 0
        visited.add(flow_idx)

        max_child_depth = 0
        for next_idx, _ in flow_graph.get(flow_idx, []):
            child_depth = calc_tree_depth(next_idx, visited.copy())
            max_child_depth = max(max_child_depth, child_depth)

        return 1 + max_child_depth

    def count_tree_nodes(flow_idx: int, visited: set) -> int:
        """Count total nodes in tree."""
        if flow_idx in visited:
            return 0
        visited.add(flow_idx)

        count = 1
        for next_idx, _ in flow_graph.get(flow_idx, []):
            count += count_tree_nodes(next_idx, visited.copy())
        return count

    # Find root candidates (flows that produce params and have outgoing edges)
    root_candidates = []
    for flow_idx in flow_produces.keys():
        if flow_idx in flow_graph:
            depth = calc_tree_depth(flow_idx, set())
            if depth >= min_depth:
                node_count = count_tree_nodes(flow_idx, set())
                root_candidates.append((flow_idx, depth, node_count))

    # Sort by depth * node_count (importance score)
    root_candidates.sort(key=lambda x: x[1] * x[2], reverse=True)

    return root_candidates
