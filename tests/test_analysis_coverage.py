"""Tests for analysis.py edge cases to improve coverage of src/idotaku/report/analysis.py."""


from idotaku.report.analysis import (
    build_param_producer_consumer,
    build_param_flow_mappings,
    build_api_dependencies,
    build_id_transition_map,
    find_chain_roots,
)


# ---------------------------------------------------------------------------
# build_param_producer_consumer edge cases
# ---------------------------------------------------------------------------


class TestBuildParamProducerConsumerEdgeCases:
    """Edge cases for build_param_producer_consumer."""

    def test_empty_value_in_response_ids(self):
        """Line 37: empty val in response_ids should be skipped."""
        flows = [
            {
                "method": "GET",
                "url": "https://api.example.com/test",
                "timestamp": "t1",
                "request_ids": [],
                "response_ids": [
                    {"value": "", "type": "numeric", "location": "body", "field": "id"},
                ],
            },
        ]
        producer, consumer = build_param_producer_consumer(flows)
        assert "" not in producer

    def test_empty_value_in_request_ids(self):
        """Line 50: empty val in request_ids should be skipped."""
        flows = [
            {
                "method": "GET",
                "url": "https://api.example.com/test",
                "timestamp": "t1",
                "request_ids": [
                    {"value": "", "type": "numeric", "location": "body", "field": "id"},
                ],
                "response_ids": [],
            },
        ]
        producer, consumer = build_param_producer_consumer(flows)
        assert "" not in consumer

    def test_missing_value_key_in_response_ids(self):
        """value key missing entirely defaults to empty string, should be skipped."""
        flows = [
            {
                "method": "GET",
                "url": "https://api.example.com/test",
                "timestamp": "t1",
                "request_ids": [],
                "response_ids": [
                    {"type": "numeric", "location": "body", "field": "id"},
                ],
            },
        ]
        producer, consumer = build_param_producer_consumer(flows)
        assert "" not in producer

    def test_missing_value_key_in_request_ids(self):
        """value key missing entirely defaults to empty string, should be skipped."""
        flows = [
            {
                "method": "GET",
                "url": "https://api.example.com/test",
                "timestamp": "t1",
                "request_ids": [
                    {"type": "numeric", "location": "path", "field": None},
                ],
                "response_ids": [],
            },
        ]
        producer, consumer = build_param_producer_consumer(flows)
        assert "" not in consumer

    def test_normal_values_are_tracked(self):
        """Verify non-empty values are properly recorded."""
        flows = [
            {
                "method": "POST",
                "url": "https://api.example.com/users",
                "timestamp": "t1",
                "request_ids": [],
                "response_ids": [
                    {"value": "12345", "type": "numeric", "location": "body", "field": "id"},
                ],
            },
            {
                "method": "GET",
                "url": "https://api.example.com/users/12345",
                "timestamp": "t2",
                "request_ids": [
                    {"value": "12345", "type": "numeric", "location": "path", "field": None},
                ],
                "response_ids": [],
            },
        ]
        producer, consumer = build_param_producer_consumer(flows)
        assert "12345" in producer
        assert "12345" in consumer
        assert producer["12345"]["idx"] == 0
        assert consumer["12345"][0]["idx"] == 1

    def test_mix_of_empty_and_valid_values(self):
        """Empty values are skipped while valid values are kept."""
        flows = [
            {
                "method": "POST",
                "url": "https://api.example.com/test",
                "timestamp": "t1",
                "request_ids": [
                    {"value": "", "type": "numeric", "location": "path", "field": None},
                    {"value": "valid_req", "type": "string", "location": "query", "field": "q"},
                ],
                "response_ids": [
                    {"value": "", "type": "numeric", "location": "body", "field": "bad"},
                    {"value": "valid_res", "type": "string", "location": "body", "field": "ok"},
                ],
            },
        ]
        producer, consumer = build_param_producer_consumer(flows)
        assert "" not in producer
        assert "" not in consumer
        assert "valid_res" in producer
        assert "valid_req" in consumer


# ---------------------------------------------------------------------------
# build_param_flow_mappings edge cases
# ---------------------------------------------------------------------------


class TestBuildParamFlowMappingsEdgeCases:
    """Edge cases for build_param_flow_mappings."""

    def test_empty_response_value(self):
        """Line 82-83: empty val in response_ids should be skipped."""
        flows = [
            {
                "method": "GET",
                "url": "https://api.example.com/test",
                "timestamp": "t1",
                "request_ids": [],
                "response_ids": [{"value": "", "type": "numeric"}],
            },
        ]
        origins, usages, produces = build_param_flow_mappings(flows)
        assert "" not in origins
        assert 0 not in produces  # No params produced

    def test_empty_request_value(self):
        """Line 89-90: empty val in request_ids should be skipped."""
        flows = [
            {
                "method": "GET",
                "url": "https://api.example.com/test",
                "timestamp": "t1",
                "request_ids": [{"value": "", "type": "numeric"}],
                "response_ids": [],
            },
        ]
        origins, usages, produces = build_param_flow_mappings(flows)
        assert "" not in usages

    def test_missing_value_in_response(self):
        """Missing value key in response_ids should be skipped."""
        flows = [
            {
                "method": "GET",
                "url": "https://api.example.com/test",
                "timestamp": "t1",
                "request_ids": [],
                "response_ids": [{"type": "numeric"}],
            },
        ]
        origins, usages, produces = build_param_flow_mappings(flows)
        assert "" not in origins

    def test_missing_value_in_request(self):
        """Missing value key in request_ids should be skipped."""
        flows = [
            {
                "method": "GET",
                "url": "https://api.example.com/test",
                "timestamp": "t1",
                "request_ids": [{"type": "numeric"}],
                "response_ids": [],
            },
        ]
        origins, usages, produces = build_param_flow_mappings(flows)
        assert "" not in usages

    def test_valid_values_tracked(self):
        """Non-empty values are properly mapped."""
        flows = [
            {
                "method": "POST",
                "url": "https://api.example.com/a",
                "timestamp": "t1",
                "request_ids": [],
                "response_ids": [{"value": "abc", "type": "string"}],
            },
            {
                "method": "GET",
                "url": "https://api.example.com/b",
                "timestamp": "t2",
                "request_ids": [{"value": "abc", "type": "string"}],
                "response_ids": [],
            },
        ]
        origins, usages, produces = build_param_flow_mappings(flows)
        assert "abc" in origins
        assert 0 in origins["abc"]
        assert "abc" in usages
        assert 1 in usages["abc"]
        assert "abc" in produces[0]


# ---------------------------------------------------------------------------
# build_api_dependencies edge cases
# ---------------------------------------------------------------------------


class TestBuildApiDependenciesEdgeCases:
    """Edge cases for build_api_dependencies."""

    def test_consumer_before_producer_skipped(self):
        """Line 157-158: consumer idx <= producer idx should be skipped (backward deps)."""
        # Flow 0: requests param "123" (consumer at idx=0)
        # Flow 1: produces param "123" in response (producer at idx=1)
        # Since consumer idx (0) <= producer idx (1), this is a backward dependency -> skipped
        flows = [
            {
                "method": "GET",
                "url": "https://api.example.com/a",
                "timestamp": "t1",
                "request_ids": [
                    {"value": "123", "type": "numeric", "location": "path", "field": None},
                ],
                "response_ids": [],
            },
            {
                "method": "POST",
                "url": "https://api.example.com/b",
                "timestamp": "t2",
                "request_ids": [],
                "response_ids": [
                    {"value": "123", "type": "numeric", "location": "body", "field": "id"},
                ],
            },
        ]
        producer, consumers = build_param_producer_consumer(flows)
        deps = build_api_dependencies(producer, consumers)
        # Producer is at idx=1 (flow 1), consumer is at idx=0 (flow 0)
        # consumer["idx"] (0) <= producer["idx"] (1) => skipped
        assert len(deps) == 0

    def test_consumer_same_idx_as_producer_skipped(self):
        """Consumer at same index as producer should be skipped."""
        # Flow 0: produces AND consumes "123"
        flows = [
            {
                "method": "POST",
                "url": "https://api.example.com/self",
                "timestamp": "t1",
                "request_ids": [
                    {"value": "123", "type": "numeric", "location": "body", "field": "in_id"},
                ],
                "response_ids": [
                    {"value": "123", "type": "numeric", "location": "body", "field": "out_id"},
                ],
            },
        ]
        producer, consumers = build_param_producer_consumer(flows)
        deps = build_api_dependencies(producer, consumers)
        # Same idx (0 == 0) => skipped
        assert len(deps) == 0

    def test_forward_dependency_included(self):
        """Forward dependencies (consumer idx > producer idx) should be included."""
        flows = [
            {
                "method": "POST",
                "url": "https://api.example.com/create",
                "timestamp": "t1",
                "request_ids": [],
                "response_ids": [
                    {"value": "abc", "type": "string", "location": "body", "field": "id"},
                ],
            },
            {
                "method": "GET",
                "url": "https://api.example.com/read",
                "timestamp": "t2",
                "request_ids": [
                    {"value": "abc", "type": "string", "location": "path", "field": None},
                ],
                "response_ids": [],
            },
        ]
        producer, consumers = build_param_producer_consumer(flows)
        deps = build_api_dependencies(producer, consumers)
        # Producer at idx=0, consumer at idx=1 => forward dep, included
        assert len(deps) > 0


# ---------------------------------------------------------------------------
# build_id_transition_map edge cases
# ---------------------------------------------------------------------------


class TestBuildIdTransitionMapEdgeCases:
    """Edge cases for build_id_transition_map."""

    def test_empty_request_id_value(self):
        """Line 191-192: empty val in request_ids should be skipped."""
        flows = [
            {
                "method": "GET",
                "url": "https://api.example.com/a",
                "timestamp": "t1",
                "request_ids": [
                    {"value": "", "type": "numeric", "location": "path"},
                ],
                "response_ids": [],
            },
        ]
        origin, subsequent = build_id_transition_map(flows)
        assert "" not in subsequent

    def test_empty_response_id_value(self):
        """Line 202-203: empty val in response_ids should be skipped."""
        flows = [
            {
                "method": "GET",
                "url": "https://api.example.com/a",
                "timestamp": "t1",
                "request_ids": [],
                "response_ids": [
                    {"value": "", "type": "numeric", "location": "body"},
                ],
            },
        ]
        origin, subsequent = build_id_transition_map(flows)
        assert "" not in origin

    def test_missing_value_in_request(self):
        """Missing value key in request_ids should be skipped."""
        flows = [
            {
                "method": "GET",
                "url": "https://api.example.com/a",
                "timestamp": "t1",
                "request_ids": [
                    {"type": "numeric", "location": "path"},
                ],
                "response_ids": [],
            },
        ]
        origin, subsequent = build_id_transition_map(flows)
        assert "" not in subsequent

    def test_missing_value_in_response(self):
        """Missing value key in response_ids should be skipped."""
        flows = [
            {
                "method": "GET",
                "url": "https://api.example.com/a",
                "timestamp": "t1",
                "request_ids": [],
                "response_ids": [
                    {"type": "numeric", "location": "body"},
                ],
            },
        ]
        origin, subsequent = build_id_transition_map(flows)
        assert "" not in origin

    def test_valid_transition(self):
        """Valid values produce correct origin and subsequent usage."""
        flows = [
            {
                "method": "POST",
                "url": "https://api.example.com/create",
                "timestamp": "t1",
                "request_ids": [],
                "response_ids": [
                    {"value": "id_1", "type": "numeric", "location": "body", "field": "id"},
                ],
            },
            {
                "method": "GET",
                "url": "https://api.example.com/read",
                "timestamp": "t2",
                "request_ids": [
                    {"value": "id_1", "type": "numeric", "location": "path", "field": None},
                ],
                "response_ids": [],
            },
        ]
        origin, subsequent = build_id_transition_map(flows)
        assert "id_1" in origin
        assert origin["id_1"]["flow_idx"] == 0
        assert "id_1" in subsequent
        assert subsequent["id_1"][0]["flow_idx"] == 1


# ---------------------------------------------------------------------------
# find_chain_roots edge cases
# ---------------------------------------------------------------------------


class TestFindChainRootsEdgeCases:
    """Edge cases for find_chain_roots."""

    def test_cycle_in_flow_graph(self):
        """Lines 233-234, 246-247: Cycles should be handled (depth returns 0 for visited)."""
        # Two flows forming a cycle: 0->1->0
        flow_graph = {0: [(1, ["param1"])], 1: [(0, ["param2"])]}
        flow_produces = {0: ["param1"], 1: ["param2"]}
        flows = [
            {"method": "POST", "url": "https://api.example.com/a", "timestamp": "t1"},
            {"method": "POST", "url": "https://api.example.com/b", "timestamp": "t2"},
        ]
        roots = find_chain_roots(flow_graph, flow_produces, flows, min_depth=2)
        assert isinstance(roots, list)
        # With cycle 0->1->0: from node 0, depth = 1 + depth(1) = 1 + (1 + depth(0 visited=0))
        # = 1 + (1 + 0) = 2. Same for node 1. Both should qualify at min_depth=2.
        assert len(roots) == 2

    def test_cycle_with_high_min_depth(self):
        """Cycle-limited depth should not exceed actual reachable depth."""
        flow_graph = {0: [(1, ["p1"])], 1: [(0, ["p2"])]}
        flow_produces = {0: ["p1"], 1: ["p2"]}
        flows = [
            {"method": "POST", "url": "https://api.example.com/a", "timestamp": "t1"},
            {"method": "POST", "url": "https://api.example.com/b", "timestamp": "t2"},
        ]
        # Depth from each node in cycle is 2, so min_depth=3 should yield nothing
        roots = find_chain_roots(flow_graph, flow_produces, flows, min_depth=3)
        assert len(roots) == 0

    def test_three_node_cycle(self):
        """Three-node cycle: 0->1->2->0."""
        flow_graph = {
            0: [(1, ["p1"])],
            1: [(2, ["p2"])],
            2: [(0, ["p3"])],
        }
        flow_produces = {0: ["p1"], 1: ["p2"], 2: ["p3"]}
        flows = [
            {"method": "POST", "url": "https://api.example.com/a", "timestamp": "t1"},
            {"method": "POST", "url": "https://api.example.com/b", "timestamp": "t2"},
            {"method": "POST", "url": "https://api.example.com/c", "timestamp": "t3"},
        ]
        # From node 0: depth = 1 + (1 + (1 + 0)) = 3
        roots = find_chain_roots(flow_graph, flow_produces, flows, min_depth=2)
        assert isinstance(roots, list)
        assert len(roots) == 3

    def test_no_outgoing_edges(self):
        """Flow that produces params but has no outgoing edges is not a root."""
        flow_graph = {}  # No edges at all
        flow_produces = {0: ["param1"]}
        flows = [
            {"method": "POST", "url": "https://api.example.com/a", "timestamp": "t1"},
        ]
        roots = find_chain_roots(flow_graph, flow_produces, flows, min_depth=1)
        assert len(roots) == 0

    def test_empty_graph(self):
        """Empty graph returns no roots."""
        roots = find_chain_roots({}, {}, [], min_depth=1)
        assert roots == []

    def test_sort_order_by_importance(self):
        """Roots sorted by depth * node_count descending."""
        # Chain A: 0->1 (depth=2, nodes=2, score=4)
        # Chain B: 2->3->4 (depth=3, nodes=3, score=9)
        flow_graph = {
            0: [(1, ["p1"])],
            2: [(3, ["p2"])],
            3: [(4, ["p3"])],
        }
        flow_produces = {0: ["p1"], 2: ["p2"], 3: ["p3"]}
        flows = [
            {"method": "POST", "url": "https://api.example.com/a", "timestamp": "t1"},
            {"method": "GET", "url": "https://api.example.com/b", "timestamp": "t2"},
            {"method": "POST", "url": "https://api.example.com/c", "timestamp": "t3"},
            {"method": "GET", "url": "https://api.example.com/d", "timestamp": "t4"},
            {"method": "GET", "url": "https://api.example.com/e", "timestamp": "t5"},
        ]
        roots = find_chain_roots(flow_graph, flow_produces, flows, min_depth=2)
        assert len(roots) >= 2
        # First root should have higher importance score
        score_first = roots[0][1] * roots[0][2]
        score_second = roots[1][1] * roots[1][2]
        assert score_first >= score_second
