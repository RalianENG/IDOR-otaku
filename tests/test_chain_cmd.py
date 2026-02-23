"""Tests for chain command to improve coverage of src/idotaku/commands/chain.py."""

import json

import pytest
from click.testing import CliRunner

from idotaku.cli import main
from idotaku.commands.chain import (
    format_param,
    escape_rich,
)


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestEscapeRich:
    """Tests for escape_rich helper."""

    def test_escape_brackets(self):
        assert escape_rich("test[0]") == "test\\[0]"

    def test_no_brackets(self):
        assert escape_rich("hello") == "hello"

    def test_multiple_brackets(self):
        assert escape_rich("a[1][2]") == "a\\[1]\\[2]"

    def test_empty_string(self):
        assert escape_rich("") == ""


class TestFormatParam:
    """Tests for format_param helper covering all branches."""

    def test_empty_list_returns_none_markup(self):
        """Line 28-29: empty list returns dim 'none'."""
        result = format_param([])
        assert result == "[dim]none[/dim]"

    def test_single_item_list(self):
        """Single-item list is treated like a scalar."""
        result = format_param(["user_id"])
        assert "user_id" in result
        assert "[cyan]" in result

    def test_two_params_short_list(self):
        """Line 34-36: 2 params, short list display."""
        result = format_param(["a", "b"])
        assert "a" in result
        assert "b" in result
        assert "[cyan]" in result

    def test_three_params_short_list(self):
        """Line 34-36: 3 params, all shown, no +N suffix."""
        result = format_param(["x", "y", "z"])
        assert "x" in result
        assert "y" in result
        assert "z" in result
        assert "+" not in result

    def test_four_params_with_suffix(self):
        """Line 34-36: 4+ params shows first 3 and +1 suffix."""
        result = format_param(["a", "b", "c", "d"])
        assert "a" in result
        assert "b" in result
        assert "c" in result
        assert "+1" in result

    def test_six_params_with_suffix(self):
        """6 params shows first 3 and +3 suffix."""
        result = format_param(["a", "b", "c", "d", "e", "f"])
        assert "+3" in result

    def test_long_param_truncated_in_list(self):
        """Long params in a multi-item list are truncated to 12 chars."""
        result = format_param(["short", "this_is_a_very_long_param_name"])
        # The long param should be truncated to 12 chars + ".."
        assert ".." in result

    def test_scalar_string(self):
        """A plain string (not a list) is formatted directly."""
        result = format_param("some_id")
        assert "some_id" in result
        assert "[cyan]" in result

    def test_long_scalar_string_truncated(self):
        """Long scalar string is truncated at 20 chars."""
        long_param = "a" * 30
        result = format_param(long_param)
        assert ".." in result


# ---------------------------------------------------------------------------
# CLI tests via CliRunner
# ---------------------------------------------------------------------------


class TestChainCommandEmptyFlows:
    """Tests for chain command with empty or filtered-out flows."""

    def test_chain_empty_report(self, runner, empty_report_file):
        """Lines 91-93: empty flows prints 'No flows found'."""
        result = runner.invoke(main, ["chain", str(empty_report_file)])
        assert result.exit_code == 0
        assert "No flows found" in result.output

    def test_chain_domain_filter_no_match(self, runner, sample_report_file):
        """Lines 101-104: domain filter returning no flows."""
        result = runner.invoke(main, [
            "chain", str(sample_report_file),
            "--domains", "nonexistent-domain.xyz",
        ])
        assert result.exit_code == 0
        assert "No flows found matching domain filter" in result.output

    def test_chain_high_min_depth_no_chains(self, runner, sample_report_file):
        """Lines 289-292: high min_depth yields no chains."""
        result = runner.invoke(main, [
            "chain", str(sample_report_file),
            "--min-depth", "99",
        ])
        assert result.exit_code == 0
        assert "No parameter chains found" in result.output


class TestChainCommandWithCycles:
    """Tests for chain command with cycle-creating flows."""

    @pytest.fixture
    def cycle_report_file(self, tmp_path):
        """Create a report with cycle-creating flows: A->B->C->A."""
        cycle_report = {
            "summary": {
                "total_unique_ids": 3,
                "ids_with_origin": 3,
                "ids_with_usage": 3,
                "total_flows": 3,
            },
            "tracked_ids": {},
            "flows": [
                {
                    "method": "POST",
                    "url": "https://api.example.com/a",
                    "timestamp": "2024-01-01T10:00:00",
                    "request_ids": [
                        {"value": "id_c", "type": "numeric", "location": "body", "field": "c_id"},
                    ],
                    "response_ids": [
                        {"value": "id_a", "type": "numeric", "location": "body", "field": "a_id"},
                    ],
                },
                {
                    "method": "POST",
                    "url": "https://api.example.com/b",
                    "timestamp": "2024-01-01T10:01:00",
                    "request_ids": [
                        {"value": "id_a", "type": "numeric", "location": "body", "field": "a_id"},
                    ],
                    "response_ids": [
                        {"value": "id_b", "type": "numeric", "location": "body", "field": "b_id"},
                    ],
                },
                {
                    "method": "POST",
                    "url": "https://api.example.com/c",
                    "timestamp": "2024-01-01T10:02:00",
                    "request_ids": [
                        {"value": "id_b", "type": "numeric", "location": "body", "field": "b_id"},
                    ],
                    "response_ids": [
                        {"value": "id_c", "type": "numeric", "location": "body", "field": "c_id"},
                    ],
                },
            ],
            "potential_idor": [],
        }
        report_file = tmp_path / "cycle_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(cycle_report, f)
        return report_file

    def test_chain_with_cycle_flows(self, runner, cycle_report_file):
        """Lines 129-130, 143-144: calc_tree_depth/count_tree_nodes with cycles."""
        result = runner.invoke(main, [
            "chain", str(cycle_report_file),
            "--min-depth", "2",
        ])
        assert result.exit_code == 0
        # Should either find chains or report none -- must not crash
        assert "Parameter Chain Trees" in result.output or "No parameter chains found" in result.output

    def test_chain_with_cycle_min_depth_1(self, runner, cycle_report_file):
        """Lower min_depth to capture more chains with cycles."""
        result = runner.invoke(main, [
            "chain", str(cycle_report_file),
            "--min-depth", "1",
        ])
        assert result.exit_code == 0


class TestChainCommandHtmlExport:
    """Tests for chain command HTML export."""

    def test_chain_html_output(self, runner, sample_report_file, tmp_path):
        """Lines 340-342: HTML export path."""
        html_file = tmp_path / "chain_output.html"
        result = runner.invoke(main, [
            "chain", str(sample_report_file),
            "--min-depth", "1",
            "--html", str(html_file),
        ])
        assert result.exit_code == 0
        # If chains were found, HTML should be exported
        if "Parameter Chain Trees" in result.output:
            assert html_file.exists()
            assert "HTML exported to:" in result.output


class TestChainCommandTopLimit:
    """Tests for chain command --top limit."""

    @pytest.fixture
    def large_chain_report_file(self, tmp_path):
        """Create a report with many chain roots to test --top limit."""
        # Create many independent chains: each pair (produce -> consume)
        flows = []
        for i in range(20):
            # Producer
            flows.append({
                "method": "POST",
                "url": f"https://api.example.com/resource{i}",
                "timestamp": f"2024-01-01T{10+i:02d}:00:00",
                "request_ids": [],
                "response_ids": [
                    {"value": f"param_{i}", "type": "numeric", "location": "body", "field": "id"},
                ],
            })
            # Consumer
            flows.append({
                "method": "GET",
                "url": f"https://api.example.com/use{i}",
                "timestamp": f"2024-01-01T{10+i:02d}:01:00",
                "request_ids": [
                    {"value": f"param_{i}", "type": "numeric", "location": "path", "field": None},
                ],
                "response_ids": [],
            })

        report = {
            "summary": {
                "total_unique_ids": 20,
                "ids_with_origin": 20,
                "ids_with_usage": 20,
                "total_flows": len(flows),
            },
            "tracked_ids": {},
            "flows": flows,
            "potential_idor": [],
        }
        report_file = tmp_path / "large_chain_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f)
        return report_file

    def test_chain_top_limit(self, runner, large_chain_report_file):
        """Line 286-287: top limit stops adding roots."""
        result = runner.invoke(main, [
            "chain", str(large_chain_report_file),
            "--min-depth", "1",
            "--top", "3",
        ])
        assert result.exit_code == 0


class TestChainCommandCycleRef:
    """Tests for cycle ref node rendering (lines 190-202, 227-231)."""

    @pytest.fixture
    def cycle_ref_report_file(self, tmp_path):
        """Create a report where same API pattern appears in a chain, producing cycle refs.

        Flow 0: POST /items -> produces id_x
        Flow 1: GET /items/123 (uses id_x, produces id_y)
        Flow 2: GET /items/456 (uses id_y) - same normalized path as flow 1 => cycle ref
        """
        report = {
            "summary": {
                "total_unique_ids": 2,
                "ids_with_origin": 2,
                "ids_with_usage": 2,
                "total_flows": 3,
            },
            "tracked_ids": {},
            "flows": [
                {
                    "method": "POST",
                    "url": "https://api.example.com/items",
                    "timestamp": "2024-01-01T10:00:00",
                    "request_ids": [],
                    "response_ids": [
                        {"value": "id_x", "type": "numeric", "location": "body", "field": "item_id"},
                    ],
                },
                {
                    "method": "GET",
                    "url": "https://api.example.com/items/123",
                    "timestamp": "2024-01-01T10:01:00",
                    "request_ids": [
                        {"value": "id_x", "type": "numeric", "location": "path", "field": None},
                    ],
                    "response_ids": [
                        {"value": "id_y", "type": "numeric", "location": "body", "field": "next_id"},
                    ],
                },
                {
                    "method": "GET",
                    "url": "https://api.example.com/items/456",
                    "timestamp": "2024-01-01T10:02:00",
                    "request_ids": [
                        {"value": "id_y", "type": "numeric", "location": "path", "field": None},
                    ],
                    "response_ids": [],
                },
            ],
            "potential_idor": [],
        }
        report_file = tmp_path / "cycle_ref_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f)
        return report_file

    def test_chain_with_cycle_ref_rendering(self, runner, cycle_ref_report_file):
        """Lines 190-202, 227-231: build_tree_data with cycle ref and render_tree_node for ref type."""
        result = runner.invoke(main, [
            "chain", str(cycle_ref_report_file),
            "--min-depth", "1",
        ])
        assert result.exit_code == 0
        # Should not crash and should display tree output
        assert "Parameter Chain Trees" in result.output or "No parameter chains found" in result.output


class TestChainCommandRootNodeWithoutViaParams:
    """Tests for render_tree_node line 246 (root node, no via_params)."""

    def test_root_node_label_no_via(self, runner, sample_report_file):
        """Line 246: root node renders with just index + API, no via params."""
        result = runner.invoke(main, [
            "chain", str(sample_report_file),
            "--min-depth", "1",
        ])
        assert result.exit_code == 0


class TestChainCommandMarkCoveredRecursion:
    """Tests for mark_covered recursion (line 279, 282-283)."""

    @pytest.fixture
    def deep_chain_report_file(self, tmp_path):
        """Create a report with a deeper chain A->B->C->D."""
        report = {
            "summary": {
                "total_unique_ids": 3,
                "ids_with_origin": 3,
                "ids_with_usage": 3,
                "total_flows": 4,
            },
            "tracked_ids": {},
            "flows": [
                {
                    "method": "POST",
                    "url": "https://api.example.com/start",
                    "timestamp": "2024-01-01T10:00:00",
                    "request_ids": [],
                    "response_ids": [
                        {"value": "p1", "type": "numeric", "location": "body", "field": "id"},
                    ],
                },
                {
                    "method": "GET",
                    "url": "https://api.example.com/step1",
                    "timestamp": "2024-01-01T10:01:00",
                    "request_ids": [
                        {"value": "p1", "type": "numeric", "location": "path", "field": None},
                    ],
                    "response_ids": [
                        {"value": "p2", "type": "numeric", "location": "body", "field": "id2"},
                    ],
                },
                {
                    "method": "GET",
                    "url": "https://api.example.com/step2",
                    "timestamp": "2024-01-01T10:02:00",
                    "request_ids": [
                        {"value": "p2", "type": "numeric", "location": "path", "field": None},
                    ],
                    "response_ids": [
                        {"value": "p3", "type": "numeric", "location": "body", "field": "id3"},
                    ],
                },
                {
                    "method": "GET",
                    "url": "https://api.example.com/step3",
                    "timestamp": "2024-01-01T10:03:00",
                    "request_ids": [
                        {"value": "p3", "type": "numeric", "location": "path", "field": None},
                    ],
                    "response_ids": [],
                },
            ],
            "potential_idor": [],
        }
        report_file = tmp_path / "deep_chain_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f)
        return report_file

    def test_mark_covered_recursion(self, runner, deep_chain_report_file):
        """Lines 277-283: mark_covered recurses through children and cycle detection."""
        result = runner.invoke(main, [
            "chain", str(deep_chain_report_file),
            "--min-depth", "2",
            "--top", "5",
        ])
        assert result.exit_code == 0
        assert "Parameter Chain Trees" in result.output
