"""Tests for chain command helpers and chain export tree building."""

from collections import defaultdict

from idotaku.commands.chain import _parse_domain_filter, _filter_flows_by_domain
from idotaku.report.analysis import find_chain_roots, build_flow_graph, build_param_flow_mappings
from idotaku.export.chain_exporter import _build_tree_json, _inject_deferred_children


class TestParseDomainFilter:
    def test_none_returns_empty(self):
        assert _parse_domain_filter(None) == []

    def test_empty_string_returns_empty(self):
        assert _parse_domain_filter("") == []

    def test_single_domain(self):
        assert _parse_domain_filter("api.example.com") == ["api.example.com"]

    def test_multiple_domains(self):
        result = _parse_domain_filter("a.com, b.com, c.com")
        assert result == ["a.com", "b.com", "c.com"]

    def test_strips_whitespace(self):
        result = _parse_domain_filter("  a.com ,  b.com  ")
        assert result == ["a.com", "b.com"]

    def test_ignores_empty_parts(self):
        result = _parse_domain_filter("a.com,,b.com,")
        assert result == ["a.com", "b.com"]


class TestFilterFlowsByDomain:
    def test_no_patterns_returns_all(self):
        flows = [{"url": "https://a.com/x"}, {"url": "https://b.com/y"}]
        result = _filter_flows_by_domain(flows, [])
        assert len(result) == 2

    def test_exact_domain_match(self):
        flows = [
            {"url": "https://api.example.com/users"},
            {"url": "https://other.com/stuff"},
        ]
        result = _filter_flows_by_domain(flows, ["api.example.com"])
        assert len(result) == 1
        assert result[0]["url"] == "https://api.example.com/users"

    def test_wildcard_domain_match(self):
        flows = [
            {"url": "https://api.example.com/a"},
            {"url": "https://web.example.com/b"},
            {"url": "https://other.com/c"},
        ]
        result = _filter_flows_by_domain(flows, ["*.example.com"])
        assert len(result) == 2

    def test_flow_without_url_skipped(self):
        flows = [{"method": "GET"}]
        result = _filter_flows_by_domain(flows, ["example.com"])
        assert len(result) == 0


class TestFindChainRoots:
    def _build_graph(self, flows):
        """Helper to build flow graph from test flows."""
        param_origins, param_usages, flow_produces = build_param_flow_mappings(flows)
        flow_graph = build_flow_graph(param_origins, param_usages)
        return flow_graph, flow_produces

    def test_simple_chain(self):
        """A->B->C chain should find A as root with depth 3."""
        flows = [
            {
                "method": "POST", "url": "https://api.example.com/a",
                "timestamp": "t1",
                "request_ids": [],
                "response_ids": [{"value": "id1", "type": "numeric", "location": "body"}],
            },
            {
                "method": "GET", "url": "https://api.example.com/b",
                "timestamp": "t2",
                "request_ids": [{"value": "id1", "type": "numeric", "location": "path"}],
                "response_ids": [{"value": "id2", "type": "numeric", "location": "body"}],
            },
            {
                "method": "GET", "url": "https://api.example.com/c",
                "timestamp": "t3",
                "request_ids": [{"value": "id2", "type": "numeric", "location": "path"}],
                "response_ids": [],
            },
        ]
        flow_graph, flow_produces = self._build_graph(flows)
        roots = find_chain_roots(flow_graph, flow_produces, flows, min_depth=2)
        assert len(roots) >= 1
        root_idx, depth, node_count = roots[0]
        assert root_idx == 0  # Flow A is root
        assert depth >= 2

    def test_no_chains_below_min_depth(self):
        """A->B chain (depth 2) should not appear with min_depth=3."""
        flows = [
            {
                "method": "POST", "url": "https://api.example.com/a",
                "timestamp": "t1",
                "request_ids": [],
                "response_ids": [{"value": "id1", "type": "numeric", "location": "body"}],
            },
            {
                "method": "GET", "url": "https://api.example.com/b",
                "timestamp": "t2",
                "request_ids": [{"value": "id1", "type": "numeric", "location": "path"}],
                "response_ids": [],
            },
        ]
        flow_graph, flow_produces = self._build_graph(flows)
        roots = find_chain_roots(flow_graph, flow_produces, flows, min_depth=3)
        assert len(roots) == 0

    def test_empty_flows(self):
        flow_graph = defaultdict(list)
        flow_produces = defaultdict(list)
        roots = find_chain_roots(flow_graph, flow_produces, [], min_depth=2)
        assert roots == []

    def test_sorted_by_importance(self):
        """Roots should be sorted by depth * node_count descending."""
        flows = [
            # Chain 1: A->B (depth 2, 2 nodes)
            {"method": "POST", "url": "https://a.com/1", "timestamp": "t1",
             "request_ids": [], "response_ids": [{"value": "p1", "type": "t", "location": "body"}]},
            {"method": "GET", "url": "https://a.com/2", "timestamp": "t2",
             "request_ids": [{"value": "p1", "type": "t", "location": "path"}],
             "response_ids": [{"value": "p2", "type": "t", "location": "body"}]},
            # Chain 1 extends: B->C (depth 3, 3 nodes)
            {"method": "GET", "url": "https://a.com/3", "timestamp": "t3",
             "request_ids": [{"value": "p2", "type": "t", "location": "path"}],
             "response_ids": []},
        ]
        flow_graph, flow_produces = self._build_graph(flows)
        roots = find_chain_roots(flow_graph, flow_produces, flows, min_depth=2)
        if len(roots) > 1:
            # First root should have higher importance score
            assert roots[0][1] * roots[0][2] >= roots[1][1] * roots[1][2]


class TestBuildTreeJson:
    def test_simple_tree(self):
        flows = [
            {"method": "POST", "url": "https://api.com/a", "timestamp": "t1",
             "request_ids": [], "response_ids": [{"value": "1", "type": "n", "location": "body"}]},
            {"method": "GET", "url": "https://api.com/b", "timestamp": "t2",
             "request_ids": [{"value": "1", "type": "n", "location": "path"}],
             "response_ids": []},
        ]
        flow_graph = defaultdict(list)
        flow_graph[0] = [(1, ["1"])]

        tree = _build_tree_json(
            flow_idx=0, via_params=None, visited_apis=set(),
            node_index_map={}, index_counter=[1],
            deferred_children={}, first_occurrence={},
            sorted_flows=flows, flow_graph=flow_graph,
        )

        assert tree["flow_idx"] == 0
        assert tree["index"] == 1
        assert tree["method"] == "POST"
        assert len(tree["children"]) == 1
        assert tree["children"][0]["flow_idx"] == 1

    def test_cycle_detection(self):
        """Same API pattern visited twice should produce cycle_ref."""
        flows = [
            {"method": "GET", "url": "https://api.com/items/123", "timestamp": "t1",
             "request_ids": [], "response_ids": [{"value": "1", "type": "n", "location": "body"}]},
            {"method": "GET", "url": "https://api.com/items/456", "timestamp": "t2",
             "request_ids": [{"value": "1", "type": "n", "location": "path"}],
             "response_ids": []},
        ]
        # Flow 0 -> Flow 1, both normalize to "GET /items/{id}"
        flow_graph = defaultdict(list)
        flow_graph[0] = [(1, ["1"])]

        tree = _build_tree_json(
            flow_idx=0, via_params=None, visited_apis=set(),
            node_index_map={}, index_counter=[1],
            deferred_children={}, first_occurrence={},
            sorted_flows=flows, flow_graph=flow_graph,
        )

        # Child should be a cycle_ref since both flows have same API pattern
        child = tree["children"][0]
        assert child.get("type") == "cycle_ref"

    def test_no_children(self):
        flows = [
            {"method": "GET", "url": "https://api.com/leaf", "timestamp": "t1",
             "request_ids": [], "response_ids": []},
        ]
        flow_graph = defaultdict(list)
        tree = _build_tree_json(
            flow_idx=0, via_params=None, visited_apis=set(),
            node_index_map={}, index_counter=[1],
            deferred_children={}, first_occurrence={},
            sorted_flows=flows, flow_graph=flow_graph,
        )
        assert tree["children"] == []


class TestInjectDeferredChildren:
    def test_inject_into_target(self):
        tree = {
            "index": 1, "children": [],
            "method": "GET", "url": "/a",
        }
        deferred = {
            1: [{"flow_idx": 99, "index": 5, "children": [], "method": "GET", "url": "/z"}],
        }
        _inject_deferred_children(tree, deferred)
        assert len(tree["children"]) == 1
        assert tree["children"][0]["flow_idx"] == 99
        assert tree["children"][0]["from_cycle"] is True

    def test_no_deferred(self):
        tree = {"index": 1, "children": [], "method": "GET", "url": "/a"}
        _inject_deferred_children(tree, {})
        assert tree["children"] == []

    def test_cycle_ref_skipped(self):
        tree = {"type": "cycle_ref", "target_index": 1}
        _inject_deferred_children(tree, {1: [{"flow_idx": 99}]})
        # Should not crash, cycle_ref is skipped

    def test_none_tree(self):
        _inject_deferred_children(None, {1: [{"x": 1}]})
        # Should not crash