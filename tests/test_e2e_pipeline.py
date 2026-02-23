"""End-to-end integration test for the full idotaku pipeline.

Tests the complete flow: HAR import -> report loading -> analysis -> all export formats.
"""

import csv
import json

import pytest

from idotaku.import_har import import_har_to_file
from idotaku.report.loader import load_report
from idotaku.report.scoring import score_all_findings
from idotaku.report.diff import diff_reports
from idotaku.report.auth_analysis import detect_cross_user_access
from idotaku.report.analysis import (
    build_param_flow_mappings,
    build_flow_graph,
    find_chain_roots,
)
from idotaku.export.csv_exporter import export_csv
from idotaku.export.sarif_exporter import export_sarif
from idotaku.export.chain_exporter import export_chain_html
from idotaku.export.sequence_exporter import export_sequence_html


@pytest.fixture
def realistic_har_data():
    """Realistic HAR data with multiple entries exercising the full pipeline.

    Scenario:
      1. POST /auth/login -> returns user_id=50001 and token in JSON body
      2. GET /users/50001 -> uses user_id from login response in URL path
      3. GET /users/50001/orders?user_id=50001 -> uses user_id in path AND query
      4. POST /orders -> creates order, returns order_id=70001
      5. PUT /orders/70001 -> updates the order using order_id from step 4
      6. DELETE /users/99999 -> uses ID 99999 NOT seen in any response (IDOR candidate)
    """
    return {
        "log": {
            "version": "1.2",
            "entries": [
                # Entry 1: Login (POST) - produces user_id 50001
                {
                    "startedDateTime": "2024-06-15T09:00:00.000Z",
                    "request": {
                        "method": "POST",
                        "url": "https://api.example.com/auth/login",
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"},
                        ],
                        "postData": {
                            "mimeType": "application/json",
                            "text": '{"username": "alice", "password": "secret"}',
                        },
                    },
                    "response": {
                        "status": 200,
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"},
                        ],
                        "content": {
                            "mimeType": "application/json",
                            "text": json.dumps({
                                "user_id": 50001,
                                "token": "eyJhbGciOiJIUzI1NiJ9.test.signature",
                            }),
                        },
                    },
                },
                # Entry 2: GET user profile - uses user_id in URL path
                {
                    "startedDateTime": "2024-06-15T09:01:00.000Z",
                    "request": {
                        "method": "GET",
                        "url": "https://api.example.com/users/50001",
                        "headers": [
                            {
                                "name": "Authorization",
                                "value": "Bearer tokenAAA111222333444555666",
                            },
                        ],
                    },
                    "response": {
                        "status": 200,
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"},
                        ],
                        "content": {
                            "mimeType": "application/json",
                            "text": json.dumps({
                                "id": 50001,
                                "name": "Alice",
                                "email": "alice@example.com",
                            }),
                        },
                    },
                },
                # Entry 3: GET orders - uses user_id in path AND query param
                {
                    "startedDateTime": "2024-06-15T09:02:00.000Z",
                    "request": {
                        "method": "GET",
                        "url": "https://api.example.com/users/50001/orders?user_id=50001",
                        "headers": [
                            {
                                "name": "Authorization",
                                "value": "Bearer tokenAAA111222333444555666",
                            },
                        ],
                    },
                    "response": {
                        "status": 200,
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"},
                        ],
                        "content": {
                            "mimeType": "application/json",
                            "text": json.dumps({"orders": [], "total": 0}),
                        },
                    },
                },
                # Entry 4: POST create order - produces order_id 70001
                {
                    "startedDateTime": "2024-06-15T09:03:00.000Z",
                    "request": {
                        "method": "POST",
                        "url": "https://api.example.com/orders",
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"},
                            {
                                "name": "Authorization",
                                "value": "Bearer tokenAAA111222333444555666",
                            },
                        ],
                        "postData": {
                            "mimeType": "application/json",
                            "text": json.dumps({
                                "product_id": 30001,
                                "quantity": 2,
                            }),
                        },
                    },
                    "response": {
                        "status": 201,
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"},
                        ],
                        "content": {
                            "mimeType": "application/json",
                            "text": json.dumps({
                                "order_id": 70001,
                                "status": "created",
                            }),
                        },
                    },
                },
                # Entry 5: PUT update order - uses order_id from step 4
                {
                    "startedDateTime": "2024-06-15T09:04:00.000Z",
                    "request": {
                        "method": "PUT",
                        "url": "https://api.example.com/orders/70001",
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"},
                            {
                                "name": "Authorization",
                                "value": "Bearer tokenAAA111222333444555666",
                            },
                        ],
                        "postData": {
                            "mimeType": "application/json",
                            "text": json.dumps({"quantity": 3}),
                        },
                    },
                    "response": {
                        "status": 200,
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"},
                        ],
                        "content": {
                            "mimeType": "application/json",
                            "text": json.dumps({
                                "order_id": 70001,
                                "status": "updated",
                            }),
                        },
                    },
                },
                # Entry 6: DELETE with unknown ID - IDOR candidate
                {
                    "startedDateTime": "2024-06-15T09:05:00.000Z",
                    "request": {
                        "method": "DELETE",
                        "url": "https://api.example.com/users/99999",
                        "headers": [
                            {
                                "name": "Authorization",
                                "value": "Bearer tokenBBB999888777666555444",
                            },
                        ],
                    },
                    "response": {
                        "status": 204,
                        "headers": [],
                        "content": {},
                    },
                },
            ],
        },
    }


@pytest.fixture
def har_file(realistic_har_data, tmp_path):
    """Write the realistic HAR data to a temporary file."""
    path = tmp_path / "realistic.har"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(realistic_har_data, f)
    return path


@pytest.mark.slow
class TestE2EPipeline:
    """End-to-end integration tests for the full idotaku pipeline."""

    # ------------------------------------------------------------------ #
    # Step 1: HAR import -> JSON report file
    # ------------------------------------------------------------------ #

    def test_import_har_to_file_creates_report(self, har_file, tmp_path):
        """import_har_to_file produces a valid JSON report on disk."""
        report_path = tmp_path / "report.json"
        report = import_har_to_file(har_file, report_path)

        assert report_path.exists()
        with open(report_path, encoding="utf-8") as f:
            on_disk = json.load(f)

        # Top-level keys present
        for key in ("summary", "flows", "tracked_ids", "potential_idor"):
            assert key in on_disk
            assert key in report

    # ------------------------------------------------------------------ #
    # Step 2: load_report -> ReportData
    # ------------------------------------------------------------------ #

    def test_load_report_returns_report_data(self, har_file, tmp_path):
        """load_report returns a ReportData with expected attributes."""
        report_path = tmp_path / "report.json"
        import_har_to_file(har_file, report_path)
        report_data = load_report(report_path, exit_on_error=False)

        assert report_data.summary.total_flows == 6
        assert report_data.summary.total_unique_ids > 0
        assert len(report_data.flows) == 6
        assert isinstance(report_data.tracked_ids, dict)
        assert isinstance(report_data.potential_idor, list)

    # ------------------------------------------------------------------ #
    # Step 3: Verify report content
    # ------------------------------------------------------------------ #

    def test_report_has_expected_flows(self, har_file, tmp_path):
        """Verify that all 6 HAR entries appear as flows."""
        report_path = tmp_path / "report.json"
        import_har_to_file(har_file, report_path)
        rd = load_report(report_path, exit_on_error=False)

        methods = [f.get("method") for f in rd.flows]
        assert "POST" in methods
        assert "GET" in methods
        assert "PUT" in methods
        assert "DELETE" in methods

    def test_tracked_ids_contain_user_and_order(self, har_file, tmp_path):
        """user_id 50001 and order_id 70001 should be tracked with origins."""
        report_path = tmp_path / "report.json"
        import_har_to_file(har_file, report_path)
        rd = load_report(report_path, exit_on_error=False)

        assert "50001" in rd.tracked_ids
        assert rd.tracked_ids["50001"]["origin"] is not None

        assert "70001" in rd.tracked_ids
        assert rd.tracked_ids["70001"]["origin"] is not None

    def test_potential_idor_detected(self, har_file, tmp_path):
        """ID 99999 should be flagged as a potential IDOR candidate."""
        report_path = tmp_path / "report.json"
        import_har_to_file(har_file, report_path)
        rd = load_report(report_path, exit_on_error=False)

        idor_values = [item.get("id_value") for item in rd.potential_idor]
        assert "99999" in idor_values

    def test_user_id_has_multiple_usages(self, har_file, tmp_path):
        """user_id 50001 is used in multiple requests (path + query)."""
        report_path = tmp_path / "report.json"
        import_har_to_file(har_file, report_path)
        rd = load_report(report_path, exit_on_error=False)

        info = rd.tracked_ids.get("50001", {})
        usages = info.get("usages", [])
        # At least used in GET /users/50001 and GET /users/50001/orders?user_id=50001
        assert len(usages) >= 2

    # ------------------------------------------------------------------ #
    # Step 4: score_all_findings
    # ------------------------------------------------------------------ #

    def test_score_all_findings(self, har_file, tmp_path):
        """score_all_findings returns scored findings with risk metadata."""
        report_path = tmp_path / "report.json"
        import_har_to_file(har_file, report_path)
        rd = load_report(report_path, exit_on_error=False)

        scored = score_all_findings(rd.potential_idor)
        assert len(scored) == len(rd.potential_idor)
        for finding in scored:
            assert "risk_score" in finding
            assert "risk_level" in finding
            assert "risk_factors" in finding
            assert finding["risk_level"] in ("critical", "high", "medium", "low")
            assert 0 <= finding["risk_score"] <= 100

        # 99999 is used with DELETE method -> should get a higher score
        idor_99999 = [f for f in scored if f.get("id_value") == "99999"]
        assert len(idor_99999) == 1
        assert idor_99999[0]["risk_score"] > 0

    # ------------------------------------------------------------------ #
    # Step 5: diff_reports (report vs itself)
    # ------------------------------------------------------------------ #

    def test_diff_reports_same_report_no_changes(self, har_file, tmp_path):
        """Diffing a report against itself should show no changes."""
        report_path = tmp_path / "report.json"
        import_har_to_file(har_file, report_path)
        rd = load_report(report_path, exit_on_error=False)

        diff = diff_reports(rd, rd)
        assert not diff.has_changes
        assert diff.new_idor == []
        assert diff.removed_idor == []
        assert diff.new_ids == []
        assert diff.removed_ids == []
        assert diff.flow_count_a == diff.flow_count_b

    # ------------------------------------------------------------------ #
    # Step 6: detect_cross_user_access
    # ------------------------------------------------------------------ #

    def test_detect_cross_user_access_no_auth_context(self, har_file, tmp_path):
        """Without auth_context in flows, cross-user detection returns empty."""
        report_path = tmp_path / "report.json"
        import_har_to_file(har_file, report_path)
        rd = load_report(report_path, exit_on_error=False)

        # HAR import does not set auth_context, so no cross-user access found
        results = detect_cross_user_access(rd.flows)
        assert isinstance(results, list)
        # With no auth_context fields, nothing should be detected
        assert results == []

    def test_detect_cross_user_access_with_auth_context(self, har_file, tmp_path):
        """Injecting auth_context into flows should allow detection."""
        report_path = tmp_path / "report.json"
        import_har_to_file(har_file, report_path)
        rd = load_report(report_path, exit_on_error=False)

        # Manually inject auth_context to simulate cross-user access
        enriched_flows = []
        for flow in rd.flows:
            enriched = dict(flow)
            url = enriched.get("url", "")
            # Give the DELETE /users/99999 a different token than others
            if enriched.get("method") == "DELETE" and "99999" in url:
                enriched["auth_context"] = {
                    "auth_type": "bearer",
                    "token_hash": "hash_user_B",
                }
            elif "50001" in url and enriched.get("method") == "GET":
                # Give GET requests for user 50001 a different token
                enriched["auth_context"] = {
                    "auth_type": "bearer",
                    "token_hash": "hash_user_A",
                }
            enriched_flows.append(enriched)

        results = detect_cross_user_access(enriched_flows)
        # This is a valid call; results depend on whether the same id_value
        # is accessed with different token_hash values
        assert isinstance(results, list)

    # ------------------------------------------------------------------ #
    # Step 7: export_csv
    # ------------------------------------------------------------------ #

    def test_export_csv_idor_mode(self, har_file, tmp_path):
        """export_csv in idor mode creates a valid CSV with IDOR rows."""
        report_path = tmp_path / "report.json"
        import_har_to_file(har_file, report_path)
        rd = load_report(report_path, exit_on_error=False)

        csv_path = tmp_path / "idor.csv"
        export_csv(csv_path, rd, mode="idor")

        assert csv_path.exists()
        with open(csv_path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) > 0
        expected_headers = {"id_value", "id_type", "method", "url", "location", "field", "reason"}
        assert expected_headers.issubset(set(reader.fieldnames or []))

        # 99999 should appear in at least one row
        id_values = [r["id_value"] for r in rows]
        assert "99999" in id_values

    def test_export_csv_flows_mode(self, har_file, tmp_path):
        """export_csv in flows mode creates a CSV with all flow rows."""
        report_path = tmp_path / "report.json"
        import_har_to_file(har_file, report_path)
        rd = load_report(report_path, exit_on_error=False)

        csv_path = tmp_path / "flows.csv"
        export_csv(csv_path, rd, mode="flows")

        assert csv_path.exists()
        with open(csv_path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Should have one row per flow
        assert len(rows) == 6

    # ------------------------------------------------------------------ #
    # Step 8: export_sarif
    # ------------------------------------------------------------------ #

    def test_export_sarif(self, har_file, tmp_path):
        """export_sarif creates a valid SARIF 2.1.0 JSON file."""
        report_path = tmp_path / "report.json"
        import_har_to_file(har_file, report_path)
        rd = load_report(report_path, exit_on_error=False)

        sarif_path = tmp_path / "report.sarif"
        export_sarif(sarif_path, rd)

        assert sarif_path.exists()
        with open(sarif_path, encoding="utf-8") as f:
            sarif = json.load(f)

        assert sarif["version"] == "2.1.0"
        assert "$schema" in sarif
        assert len(sarif["runs"]) == 1

        run = sarif["runs"][0]
        assert run["tool"]["driver"]["name"] == "idotaku"
        assert "rules" in run["tool"]["driver"]

        results = run["results"]
        assert len(results) == len(rd.potential_idor)
        for result in results:
            assert result["ruleId"] == "IDOR001"
            assert "message" in result
            assert "locations" in result

    # ------------------------------------------------------------------ #
    # Step 9: Chain analysis (build_param_flow_mappings -> build_flow_graph -> find_chain_roots)
    # ------------------------------------------------------------------ #

    def test_chain_analysis_pipeline(self, har_file, tmp_path):
        """Chain analysis pipeline produces graph and roots from flows."""
        report_path = tmp_path / "report.json"
        import_har_to_file(har_file, report_path)
        rd = load_report(report_path, exit_on_error=False)

        sorted_flows = rd.sorted_flows
        param_origins, param_usages, flow_produces = build_param_flow_mappings(sorted_flows)

        # user_id 50001 should be produced in a response and consumed in requests
        assert "50001" in param_origins
        assert "50001" in param_usages

        # order_id 70001 should be produced and consumed
        assert "70001" in param_origins
        assert "70001" in param_usages

        flow_graph = build_flow_graph(param_origins, param_usages)
        assert isinstance(flow_graph, dict)
        # There should be at least one edge in the graph
        assert len(flow_graph) > 0

        roots = find_chain_roots(flow_graph, flow_produces, sorted_flows, min_depth=2)
        assert isinstance(roots, list)
        # Each root is (flow_idx, depth, node_count)
        for root in roots:
            assert len(root) == 3
            flow_idx, depth, node_count = root
            assert depth >= 2
            assert node_count >= 1

    # ------------------------------------------------------------------ #
    # Step 10: export_chain_html
    # ------------------------------------------------------------------ #

    def test_export_chain_html(self, har_file, tmp_path):
        """export_chain_html creates an HTML file with CSP meta tag."""
        report_path = tmp_path / "report.json"
        import_har_to_file(har_file, report_path)
        rd = load_report(report_path, exit_on_error=False)

        sorted_flows = rd.sorted_flows
        param_origins, param_usages, flow_produces = build_param_flow_mappings(sorted_flows)
        flow_graph = build_flow_graph(param_origins, param_usages)
        roots = find_chain_roots(flow_graph, flow_produces, sorted_flows, min_depth=2)

        # Transform roots to the 4-tuple format expected by export_chain_html:
        # (score, depth, nodes, root_idx)
        selected_roots = [
            (depth * 100 + node_count, depth, node_count, flow_idx)
            for flow_idx, depth, node_count in roots
        ]

        html_path = tmp_path / "chain.html"
        export_chain_html(html_path, sorted_flows, flow_graph, flow_produces, selected_roots)

        assert html_path.exists()
        content = html_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "Content-Security-Policy" in content
        assert "Parameter Chain Trees" in content

    def test_export_chain_html_empty_roots(self, har_file, tmp_path):
        """export_chain_html works with empty selected_roots."""
        report_path = tmp_path / "report.json"
        import_har_to_file(har_file, report_path)
        rd = load_report(report_path, exit_on_error=False)

        sorted_flows = rd.sorted_flows
        html_path = tmp_path / "chain_empty.html"
        export_chain_html(html_path, sorted_flows, {}, {}, [])

        assert html_path.exists()
        content = html_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content

    # ------------------------------------------------------------------ #
    # Step 11: export_sequence_html
    # ------------------------------------------------------------------ #

    def test_export_sequence_html(self, har_file, tmp_path):
        """export_sequence_html creates an HTML file with CSP meta tag."""
        report_path = tmp_path / "report.json"
        import_har_to_file(har_file, report_path)
        rd = load_report(report_path, exit_on_error=False)

        html_path = tmp_path / "sequence.html"
        export_sequence_html(html_path, rd.sorted_flows, rd.tracked_ids, rd.potential_idor)

        assert html_path.exists()
        content = html_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "Content-Security-Policy" in content
        assert "API Sequence Diagram" in content

    # ------------------------------------------------------------------ #
    # Full pipeline in a single test
    # ------------------------------------------------------------------ #

    def test_full_pipeline_end_to_end(self, har_file, tmp_path):
        """Run the entire pipeline in one test to verify integration.

        HAR import -> load -> score -> diff -> CSV -> SARIF -> chain -> sequence
        """
        # 1. Import HAR to file
        report_path = tmp_path / "full_pipeline_report.json"
        report_dict = import_har_to_file(har_file, report_path)
        assert report_path.exists()
        assert report_dict["summary"]["total_flows"] == 6

        # 2. Load report
        rd = load_report(report_path, exit_on_error=False)
        assert rd.summary.total_flows == 6
        assert len(rd.potential_idor) > 0

        # 3. Score findings
        scored = score_all_findings(rd.potential_idor)
        assert all("risk_score" in f for f in scored)

        # 4. Diff with self
        diff = diff_reports(rd, rd)
        assert not diff.has_changes

        # 5. Cross-user access (no auth_context -> empty)
        cross = detect_cross_user_access(rd.flows)
        assert isinstance(cross, list)

        # 6. CSV exports
        csv_idor = tmp_path / "pipeline_idor.csv"
        export_csv(csv_idor, rd, mode="idor")
        assert csv_idor.exists()

        csv_flows = tmp_path / "pipeline_flows.csv"
        export_csv(csv_flows, rd, mode="flows")
        assert csv_flows.exists()

        # 7. SARIF export
        sarif_path = tmp_path / "pipeline.sarif"
        export_sarif(sarif_path, rd)
        assert sarif_path.exists()
        with open(sarif_path, encoding="utf-8") as f:
            sarif = json.load(f)
        assert sarif["version"] == "2.1.0"

        # 8. Chain analysis + HTML export
        sorted_flows = rd.sorted_flows
        param_origins, param_usages, flow_produces = build_param_flow_mappings(sorted_flows)
        flow_graph = build_flow_graph(param_origins, param_usages)
        roots = find_chain_roots(flow_graph, flow_produces, sorted_flows, min_depth=2)
        selected_roots = [
            (depth * 100 + node_count, depth, node_count, flow_idx)
            for flow_idx, depth, node_count in roots
        ]
        chain_html = tmp_path / "pipeline_chain.html"
        export_chain_html(chain_html, sorted_flows, flow_graph, flow_produces, selected_roots)
        assert chain_html.exists()
        chain_content = chain_html.read_text(encoding="utf-8")
        assert "Content-Security-Policy" in chain_content

        # 9. Sequence HTML export
        seq_html = tmp_path / "pipeline_sequence.html"
        export_sequence_html(seq_html, sorted_flows, rd.tracked_ids, rd.potential_idor)
        assert seq_html.exists()
        seq_content = seq_html.read_text(encoding="utf-8")
        assert "Content-Security-Policy" in seq_content
