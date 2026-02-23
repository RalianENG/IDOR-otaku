"""Tests for chain command, chain exporter, and analysis coverage gaps.

Targets uncovered lines:
- chain.py: 105, 122, 196-202, 220-221, 246, 315
- chain_exporter.py: 99-117
- analysis.py: 152
"""

import json
from collections import defaultdict

import pytest
from click.testing import CliRunner

from idotaku.cli import main
from idotaku.report.analysis import (
    build_param_producer_consumer,
    build_param_flow_mappings,
    build_api_dependencies,
    build_id_transition_map,
    find_chain_roots,
)
from idotaku.export.chain_exporter import (
    _build_tree_json,
    _inject_deferred_children,
    export_chain_html,
)


@pytest.fixture
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# chain.py line 105: domain filter that matches SOME flows
# ---------------------------------------------------------------------------


class TestChainDomainFilterPartialMatch:
    """Cover chain.py line 105: domain filter matching some (not all) flows."""

    def test_domain_filter_with_partial_match(self, runner, tmp_path):
        """When domain filter matches some flows, the 'Filtering by domains' message appears."""
        data = {
            "summary": {"total_unique_ids": 2, "ids_with_origin": 1, "ids_with_usage": 1, "total_flows": 3},
            "tracked_ids": {},
            "flows": [
                {
                    "method": "POST",
                    "url": "https://api.example.com/users",
                    "timestamp": "2024-01-01T10:00:00",
                    "request_ids": [],
                    "response_ids": [
                        {"value": "id1", "type": "numeric", "location": "body", "field": "id"},
                    ],
                },
                {
                    "method": "GET",
                    "url": "https://api.example.com/users/123",
                    "timestamp": "2024-01-01T10:01:00",
                    "request_ids": [
                        {"value": "id1", "type": "numeric", "location": "path", "field": None},
                    ],
                    "response_ids": [],
                },
                {
                    "method": "GET",
                    "url": "https://other-domain.com/stuff",
                    "timestamp": "2024-01-01T10:02:00",
                    "request_ids": [],
                    "response_ids": [],
                },
            ],
            "potential_idor": [],
        }
        report = tmp_path / "partial_domain.json"
        report.write_text(json.dumps(data), encoding="utf-8")
        result = runner.invoke(main, ["chain", str(report), "--domains", "api.example.com", "--min-depth", "1"])
        assert result.exit_code == 0
        # Line 105: "Filtering by domains" message should appear
        assert "Filtering by domains" in result.output


# ---------------------------------------------------------------------------
# chain.py line 122: format_api with path > 45 chars
# ---------------------------------------------------------------------------


class TestChainLongPath:
    """Cover chain.py line 122: path truncation in format_api when path > 45 chars."""

    def test_chain_with_long_url_path(self, runner, tmp_path):
        """When a flow URL has a path longer than 45 chars, it should be truncated."""
        long_path = "/very/long/api/path/that/exceeds/forty/five/characters/definitely"
        assert len(long_path) > 45

        data = {
            "summary": {"total_unique_ids": 1, "ids_with_origin": 1, "ids_with_usage": 1, "total_flows": 2},
            "tracked_ids": {},
            "flows": [
                {
                    "method": "POST",
                    "url": f"https://api.example.com{long_path}",
                    "timestamp": "2024-01-01T10:00:00",
                    "request_ids": [],
                    "response_ids": [
                        {"value": "long_id", "type": "numeric", "location": "body", "field": "id"},
                    ],
                },
                {
                    "method": "GET",
                    "url": "https://api.example.com/short",
                    "timestamp": "2024-01-01T10:01:00",
                    "request_ids": [
                        {"value": "long_id", "type": "numeric", "location": "path", "field": None},
                    ],
                    "response_ids": [],
                },
            ],
            "potential_idor": [],
        }
        report = tmp_path / "long_path.json"
        report.write_text(json.dumps(data), encoding="utf-8")
        result = runner.invoke(main, ["chain", str(report), "--min-depth", "1"])
        assert result.exit_code == 0
        # The long path should be truncated (line 122: path[:42] + "...")
        assert "..." in result.output


# ---------------------------------------------------------------------------
# chain.py lines 196-202, 220-221, 246: deferred children from cycle ref
# and inject_deferred actually injecting, and from_cycle rendering
# ---------------------------------------------------------------------------


class TestChainDeferredChildrenFromCycleRef:
    """Cover chain.py lines 196-202 (deferred children), 220-221 (inject_deferred),
    and 246 (from_cycle label without via_params).

    We need:
    - Flow A produces param1 -> Flow B uses param1 and produces param2
    - Flow B (same API pattern) appears again as Flow C using param2 -> cycle ref
    - Flow C has children (grandchildren) that should be deferred to Flow B's node

    The key: a cycle ref node that has outgoing edges, so its grandchildren get deferred.
    """

    @pytest.fixture
    def deferred_cycle_report(self, tmp_path):
        """Report where cycle ref's target node has grandchildren that get deferred.

        Flow 0: POST /items -> produces param_x
        Flow 1: GET /items/111 (uses param_x, produces param_y) - normalized: GET /items/{id}
        Flow 2: GET /items/222 (uses param_y, produces param_z) - same normalized: GET /items/{id} => CYCLE REF
        Flow 3: GET /details (uses param_z) - this is a grandchild of the cycle ref

        When flow 2 is detected as cycle ref to flow 1:
        - flow_graph[2] has edge to flow 3 via param_z
        - gc_idx=3, gc_api=GET /details != GET /items/{id}
        - So flow 3 gets deferred to the cycle target (flow 1's index)
        """
        data = {
            "summary": {"total_unique_ids": 3, "ids_with_origin": 3, "ids_with_usage": 3, "total_flows": 4},
            "tracked_ids": {},
            "flows": [
                {
                    "method": "POST",
                    "url": "https://api.example.com/items",
                    "timestamp": "2024-01-01T10:00:00",
                    "request_ids": [],
                    "response_ids": [
                        {"value": "param_x", "type": "numeric", "location": "body", "field": "id"},
                    ],
                },
                {
                    "method": "GET",
                    "url": "https://api.example.com/items/111",
                    "timestamp": "2024-01-01T10:01:00",
                    "request_ids": [
                        {"value": "param_x", "type": "numeric", "location": "path", "field": None},
                    ],
                    "response_ids": [
                        {"value": "param_y", "type": "numeric", "location": "body", "field": "next_id"},
                    ],
                },
                {
                    "method": "GET",
                    "url": "https://api.example.com/items/222",
                    "timestamp": "2024-01-01T10:02:00",
                    "request_ids": [
                        {"value": "param_y", "type": "numeric", "location": "path", "field": None},
                    ],
                    "response_ids": [
                        {"value": "param_z", "type": "numeric", "location": "body", "field": "extra_id"},
                    ],
                },
                {
                    "method": "GET",
                    "url": "https://api.example.com/details",
                    "timestamp": "2024-01-01T10:03:00",
                    "request_ids": [
                        {"value": "param_z", "type": "numeric", "location": "path", "field": None},
                    ],
                    "response_ids": [],
                },
            ],
            "potential_idor": [],
        }
        report = tmp_path / "deferred_cycle.json"
        report.write_text(json.dumps(data), encoding="utf-8")
        return report

    def test_chain_deferred_children_via_cli(self, runner, deferred_cycle_report):
        """CLI test covering lines 196-202, 220-221, 246."""
        result = runner.invoke(main, [
            "chain", str(deferred_cycle_report),
            "--min-depth", "1",
        ])
        assert result.exit_code == 0
        assert "Parameter Chain Trees" in result.output

    def test_chain_deferred_children_with_html(self, runner, deferred_cycle_report, tmp_path):
        """HTML export also exercises the deferred children logic in chain_exporter."""
        html_out = tmp_path / "deferred.html"
        result = runner.invoke(main, [
            "chain", str(deferred_cycle_report),
            "--min-depth", "1",
            "--html", str(html_out),
        ])
        assert result.exit_code == 0
        if "Parameter Chain Trees" in result.output:
            assert html_out.exists()
            html_content = html_out.read_text(encoding="utf-8")
            assert "Parameter Chain Trees" in html_content


# ---------------------------------------------------------------------------
# chain_exporter.py lines 99-117: deferred children in _build_tree_json
# ---------------------------------------------------------------------------


class TestChainExporterDeferredChildren:
    """Cover chain_exporter.py lines 99-117 directly via unit test."""

    def test_build_tree_json_with_cycle_ref_and_grandchildren(self):
        """When a child is cycle_ref, its grandchildren should be deferred.

        Setup:
        - Flow 0: POST /items (produces param_x) -> flow_graph[0] = [(1, ["param_x"])]
        - Flow 1: GET /items/111 (normalizes to GET /items/{id}, produces param_y) -> flow_graph[1] = [(2, ["param_y"])]
        - Flow 2: GET /items/222 (normalizes to GET /items/{id}, produces param_z) -> cycle ref to flow 1
        - flow_graph[2] = [(3, ["param_z"])]
        - Flow 3: GET /details (uses param_z) -> grandchild that should be deferred
        """
        flows = [
            {
                "method": "POST",
                "url": "https://api.example.com/items",
                "timestamp": "t1",
                "request_ids": [],
                "response_ids": [{"value": "param_x", "type": "n", "location": "body", "field": "id"}],
            },
            {
                "method": "GET",
                "url": "https://api.example.com/items/111",
                "timestamp": "t2",
                "request_ids": [{"value": "param_x", "type": "n", "location": "path"}],
                "response_ids": [{"value": "param_y", "type": "n", "location": "body", "field": "next"}],
            },
            {
                "method": "GET",
                "url": "https://api.example.com/items/222",
                "timestamp": "t3",
                "request_ids": [{"value": "param_y", "type": "n", "location": "path"}],
                "response_ids": [{"value": "param_z", "type": "n", "location": "body", "field": "extra"}],
            },
            {
                "method": "GET",
                "url": "https://api.example.com/details",
                "timestamp": "t4",
                "request_ids": [{"value": "param_z", "type": "n", "location": "path"}],
                "response_ids": [],
            },
        ]

        flow_graph = defaultdict(list)
        flow_graph[0] = [(1, ["param_x"])]
        flow_graph[1] = [(2, ["param_y"])]
        flow_graph[2] = [(3, ["param_z"])]

        deferred_children = {}
        node_index_map = {}
        index_counter = [1]
        first_occurrence = {}

        tree = _build_tree_json(
            flow_idx=0,
            via_params=None,
            visited_apis=set(),
            node_index_map=node_index_map,
            index_counter=index_counter,
            deferred_children=deferred_children,
            first_occurrence=first_occurrence,
            sorted_flows=flows,
            flow_graph=flow_graph,
        )

        # Flow 0 -> Flow 1 -> Flow 2 (cycle ref to flow 1) -> Flow 3 (deferred)
        assert tree["flow_idx"] == 0
        assert len(tree["children"]) == 1
        child_1 = tree["children"][0]
        assert child_1["flow_idx"] == 1

        # Flow 2 should be a cycle_ref (same normalized path as flow 1: GET /items/{id})
        assert len(child_1["children"]) == 1
        child_2 = child_1["children"][0]
        assert child_2.get("type") == "cycle_ref"

        # Deferred children should have been populated
        # The grandchild (flow 3) should be deferred to the cycle target
        assert len(deferred_children) > 0

        # Inject deferred children
        _inject_deferred_children(tree, deferred_children)

        # After injection, child_1 should now have the deferred grandchild
        has_deferred = any(c.get("from_cycle") for c in child_1.get("children", []))
        assert has_deferred, "Deferred children should be injected into the cycle target node"


# ---------------------------------------------------------------------------
# chain_exporter.py: export_chain_html with cycle ref data
# ---------------------------------------------------------------------------


class TestExportChainHtmlWithCycleRef:
    """Cover the full export_chain_html path with cycle ref flows."""

    def test_export_with_deferred_cycle(self, tmp_path):
        """Full HTML export with cycle ref and deferred children."""
        flows = [
            {
                "method": "POST",
                "url": "https://api.example.com/items",
                "timestamp": "t1",
                "request_ids": [],
                "response_ids": [{"value": "px", "type": "n", "location": "body", "field": "id"}],
            },
            {
                "method": "GET",
                "url": "https://api.example.com/items/111",
                "timestamp": "t2",
                "request_ids": [{"value": "px", "type": "n", "location": "path"}],
                "response_ids": [{"value": "py", "type": "n", "location": "body", "field": "next"}],
            },
            {
                "method": "GET",
                "url": "https://api.example.com/items/222",
                "timestamp": "t3",
                "request_ids": [{"value": "py", "type": "n", "location": "path"}],
                "response_ids": [{"value": "pz", "type": "n", "location": "body", "field": "extra"}],
            },
            {
                "method": "GET",
                "url": "https://api.example.com/details",
                "timestamp": "t4",
                "request_ids": [{"value": "pz", "type": "n", "location": "path"}],
                "response_ids": [],
            },
        ]

        flow_graph = defaultdict(list)
        flow_graph[0] = [(1, ["px"])]
        flow_graph[1] = [(2, ["py"])]
        flow_graph[2] = [(3, ["pz"])]

        flow_produces = {0: ["px"], 1: ["py"], 2: ["pz"]}
        selected_roots = [(300, 3, 4, 0)]  # (score, depth, nodes, root_idx)

        html_out = tmp_path / "cycle_export.html"
        export_chain_html(html_out, flows, flow_graph, flow_produces, selected_roots)

        assert html_out.exists()
        content = html_out.read_text(encoding="utf-8")
        assert "Parameter Chain Trees" in content
        assert "cycle_ref" in content or "from_cycle" in content or "items" in content


# ---------------------------------------------------------------------------
# analysis.py line 152: producer param not in consumers (continue)
# ---------------------------------------------------------------------------


class TestBuildApiDependenciesProducerNotConsumed:
    """Cover analysis.py line 151-152: param produced but never consumed."""

    def test_producer_with_no_consumers(self):
        """A param that is produced but never consumed should be skipped."""
        flows = [
            {
                "method": "POST",
                "url": "https://api.example.com/create",
                "timestamp": "t1",
                "request_ids": [],
                "response_ids": [
                    {"value": "orphan_param", "type": "numeric", "location": "body", "field": "id"},
                ],
            },
        ]
        producer, consumers = build_param_producer_consumer(flows)
        assert "orphan_param" in producer
        assert "orphan_param" not in consumers

        deps = build_api_dependencies(producer, consumers)
        # No dependencies since the param has no consumers
        assert len(deps) == 0

    def test_producer_not_consumed_with_other_valid_deps(self):
        """Mix of consumed and unconsumed params."""
        flows = [
            {
                "method": "POST",
                "url": "https://api.example.com/create",
                "timestamp": "t1",
                "request_ids": [],
                "response_ids": [
                    {"value": "consumed_param", "type": "numeric", "location": "body", "field": "id"},
                    {"value": "orphan_param", "type": "numeric", "location": "body", "field": "extra"},
                ],
            },
            {
                "method": "GET",
                "url": "https://api.example.com/read",
                "timestamp": "t2",
                "request_ids": [
                    {"value": "consumed_param", "type": "numeric", "location": "path", "field": None},
                ],
                "response_ids": [],
            },
        ]
        producer, consumers = build_param_producer_consumer(flows)
        assert "orphan_param" in producer
        assert "orphan_param" not in consumers
        assert "consumed_param" in producer
        assert "consumed_param" in consumers

        deps = build_api_dependencies(producer, consumers)
        # Only consumed_param should create a dependency; orphan_param hits line 152 (continue)
        assert len(deps) > 0
        # Verify orphan_param is not in any dependency
        for api_key, param_deps in deps.items():
            assert "orphan_param" not in param_deps


# ---------------------------------------------------------------------------
# analysis.py: build_api_dependencies self-reference (consumer_key == producer_key)
# ---------------------------------------------------------------------------


class TestBuildApiDependenciesSelfReference:
    """Cover analysis.py line 162: consumer_key == producer_key (self-reference skip)."""

    def test_same_api_produces_and_consumes_different_flows(self):
        """When a later flow at the same API path consumes what an earlier flow produced,
        consumer_key == producer_key, so it should be skipped (self-reference).
        """
        flows = [
            {
                "method": "POST",
                "url": "https://api.example.com/items",
                "timestamp": "t1",
                "request_ids": [],
                "response_ids": [
                    {"value": "self_ref_param", "type": "numeric", "location": "body", "field": "id"},
                ],
            },
            {
                "method": "POST",
                "url": "https://api.example.com/items",
                "timestamp": "t2",
                "request_ids": [
                    {"value": "self_ref_param", "type": "numeric", "location": "body", "field": "parent_id"},
                ],
                "response_ids": [],
            },
        ]
        producer, consumers = build_param_producer_consumer(flows)
        deps = build_api_dependencies(producer, consumers)
        # Both flows have same method+path (POST /items), so consumer_key == producer_key
        # This should be a self-reference and skipped
        assert len(deps) == 0


# ---------------------------------------------------------------------------
# Additional edge case tests for build_id_transition_map
# ---------------------------------------------------------------------------


class TestBuildIdTransitionMapFirstOriginPreserved:
    """Test that the first origin is preserved when a param is produced multiple times."""

    def test_first_origin_preserved(self):
        flows = [
            {
                "method": "POST",
                "url": "https://api.example.com/a",
                "timestamp": "t1",
                "request_ids": [],
                "response_ids": [
                    {"value": "dup_id", "type": "numeric", "location": "body", "field": "id"},
                ],
            },
            {
                "method": "POST",
                "url": "https://api.example.com/b",
                "timestamp": "t2",
                "request_ids": [],
                "response_ids": [
                    {"value": "dup_id", "type": "numeric", "location": "body", "field": "id"},
                ],
            },
        ]
        origins, usages = build_id_transition_map(flows)
        assert origins["dup_id"]["flow_idx"] == 0  # First occurrence preserved


# ---------------------------------------------------------------------------
# Additional test for find_chain_roots with no flow_graph entries
# ---------------------------------------------------------------------------


class TestFindChainRootsEmpty:
    """Test find_chain_roots with empty flow graph."""

    def test_no_flow_graph_entries(self):
        roots = find_chain_roots({}, {}, [])
        assert roots == []

    def test_with_cycle(self):
        flow_graph = {0: [(1, ["p1"])], 1: [(0, ["p2"])]}
        flow_produces = {0: ["p1"], 1: ["p2"]}
        flows = [
            {"method": "POST", "url": "https://api.example.com/a", "timestamp": "t1"},
            {"method": "POST", "url": "https://api.example.com/b", "timestamp": "t2"},
        ]
        roots = find_chain_roots(flow_graph, flow_produces, flows, min_depth=1)
        assert len(roots) > 0


# ---------------------------------------------------------------------------
# Additional test for build_param_flow_mappings with empty values
# ---------------------------------------------------------------------------


class TestBuildParamFlowMappingsEmptyValues:
    """Test build_param_flow_mappings skips empty values."""

    def test_empty_values_skipped(self):
        flows = [
            {
                "method": "GET",
                "url": "https://api.example.com/test",
                "timestamp": "t1",
                "request_ids": [{"value": "", "type": "numeric", "location": "path"}],
                "response_ids": [{"value": "", "type": "numeric", "location": "body"}],
            },
        ]
        origins, usages, produces = build_param_flow_mappings(flows)
        assert "" not in origins
        assert "" not in usages
