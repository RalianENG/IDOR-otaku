"""Chain tree HTML exporter for idotaku."""

import json
from pathlib import Path
from typing import Union
from urllib.parse import urlparse

from ..utils.url import normalize_api_path, extract_domain
from .html_styles import CHAIN_STYLES
from .html_scripts import CHAIN_SCRIPTS


def _get_flow_details(flow: dict) -> dict:
    """Get detailed info for a flow."""
    url = flow.get("url", "")
    return {
        "method": flow.get("method", "?"),
        "url": url if url else "?",
        "domain": extract_domain(url) or "",
        "path": urlparse(url).path or "/",
        "timestamp": flow.get("timestamp", ""),
        "request_ids": flow.get("request_ids", []),
        "response_ids": flow.get("response_ids", []),
    }


def _get_api_key(flow: dict) -> str:
    """Get API key (method + normalized path) for cycle detection."""
    method = flow.get("method", "?")
    url = flow.get("url", "")
    return f"{method} {normalize_api_path(url)}"


def _build_tree_json(
    flow_idx: int,
    via_params: list,
    visited_apis: set,
    node_index_map: dict,
    index_counter: list,
    deferred_children: dict,
    first_occurrence: dict,
    sorted_flows: list,
    flow_graph: dict,
) -> dict:
    """Build JSON tree structure for HTML with cycle continuation.

    Cycle detection is based on API pattern (method + normalized path), not flow_idx.
    This allows the same parameter to flow through different APIs without being
    treated as a cycle.
    """
    flow = sorted_flows[flow_idx]
    api_key = _get_api_key(flow)
    is_cycle = api_key in visited_apis

    # Already visited this API pattern? Return ref
    if is_cycle:
        first_idx = first_occurrence.get(api_key, flow_idx)
        target_index = node_index_map.get(first_idx, "?")
        return {
            "type": "cycle_ref",
            "flow_idx": flow_idx,
            "target_index": target_index,
            "via_params": via_params,
            "api_key": api_key,
        }

    # Mark this API pattern as visited
    new_visited = visited_apis | {api_key}
    first_occurrence[api_key] = flow_idx

    # Assign index to this node
    current_index = index_counter[0]
    index_counter[0] += 1
    node_index_map[flow_idx] = current_index

    details = _get_flow_details(flow)
    children = []

    for next_idx, next_params in flow_graph.get(flow_idx, []):
        child = _build_tree_json(
            next_idx,
            next_params,
            new_visited,
            node_index_map,
            index_counter,
            deferred_children,
            first_occurrence,
            sorted_flows,
            flow_graph,
        )
        if child:
            # If child is a cycle_ref, defer its grandchildren to the cycle target
            if child.get("type") == "cycle_ref":
                target_index = child.get("target_index")
                target_idx = child["flow_idx"]
                for gc_idx, gc_params in flow_graph.get(target_idx, []):
                    gc_flow = sorted_flows[gc_idx]
                    gc_api = _get_api_key(gc_flow)
                    if gc_idx != target_idx and gc_api not in new_visited:
                        if target_index not in deferred_children:
                            deferred_children[target_index] = []
                        gc = _build_tree_json(
                            gc_idx,
                            gc_params,
                            new_visited,
                            node_index_map,
                            index_counter,
                            deferred_children,
                            first_occurrence,
                            sorted_flows,
                            flow_graph,
                        )
                        if gc:
                            gc["from_cycle"] = True
                            deferred_children[target_index].append(gc)
            children.append(child)

    return {
        "flow_idx": flow_idx,
        "index": current_index,
        "via_params": via_params,
        "is_cycle": False,
        "api_key": api_key,
        "method": details["method"],
        "url": details["url"],
        "domain": details["domain"],
        "path": details["path"],
        "timestamp": details["timestamp"],
        "request_ids": details["request_ids"],
        "response_ids": details["response_ids"],
        "children": children,
    }


def _inject_deferred_children(tree: dict, deferred_children: dict) -> None:
    """Inject deferred children into their target nodes."""
    if not tree or tree.get("type") == "cycle_ref":
        return

    # Inject deferred children for this node
    node_index = tree.get("index")
    if node_index in deferred_children:
        tree["children"].extend(deferred_children[node_index])
        for child in deferred_children[node_index]:
            child["from_cycle"] = True
        del deferred_children[node_index]

    # Recurse into children
    for child in tree.get("children", []):
        _inject_deferred_children(child, deferred_children)


def export_chain_html(
    output_path: Union[str, Path],
    sorted_flows: list[dict],
    flow_graph: dict[int, list],
    flow_produces: dict[int, list],
    selected_roots: list[tuple],
) -> None:
    """Export chain trees to interactive HTML.

    Args:
        output_path: Path to output HTML file
        sorted_flows: List of flow records sorted by timestamp
        flow_graph: Flow graph mapping flow_idx to [(next_idx, [params])]
        flow_produces: Mapping of flow_idx to produced params (unused but kept for API compat)
        selected_roots: List of (score, depth, nodes, root_idx) tuples
    """
    # Build tree data for all selected roots
    trees_data = []
    for rank, (score, depth, nodes, root_idx) in enumerate(selected_roots, 1):
        # Initialize tracking for this tree
        node_index_map = {}
        index_counter = [1]
        deferred_children = {}
        visited_apis = set()
        first_occurrence = {}

        tree = _build_tree_json(
            root_idx,
            None,
            visited_apis,
            node_index_map,
            index_counter,
            deferred_children,
            first_occurrence,
            sorted_flows,
            flow_graph,
        )

        # Inject deferred children into their targets
        _inject_deferred_children(tree, deferred_children)

        tree["rank"] = rank
        tree["depth"] = depth
        tree["nodes"] = nodes
        trees_data.append(tree)

    trees_json = json.dumps(trees_data)

    # Build HTML content
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>idotaku - Parameter Chain Trees</title>
    <style>
{CHAIN_STYLES}
    </style>
</head>
<body>
    <div class="tree-panel">
        <h1>Parameter Chain Trees</h1>
        <div class="security-warning">
            <strong>Warning:</strong> This report may contain sensitive data extracted from intercepted HTTP traffic
            (tokens, session IDs, API keys, cookies). Do not share this file publicly.
        </div>
        <div id="trees"></div>
    </div>

    <div class="hint">Hover path for full URL | Click <kbd>+</kbd> to expand nodes</div>

    <script>
{CHAIN_SCRIPTS.replace("{trees_json}", trees_json)}
    </script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
