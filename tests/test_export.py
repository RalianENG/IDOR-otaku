"""Tests for export module."""

import pytest
from pathlib import Path

from idotaku.export.chain_exporter import (
    _get_flow_details,
    _get_api_key,
    export_chain_html,
)
from idotaku.export.html_base import html_escape


class TestGetFlowDetails:
    """Tests for _get_flow_details function."""

    def test_complete_flow(self):
        """Test extracting details from complete flow."""
        flow = {
            "method": "POST",
            "url": "https://api.example.com/users",
            "timestamp": "2024-01-01T10:00:00Z",
            "request_ids": [{"value": "123", "type": "numeric"}],
            "response_ids": [{"value": "456", "type": "numeric"}],
        }
        details = _get_flow_details(flow)

        assert details["method"] == "POST"
        assert details["url"] == "https://api.example.com/users"
        assert details["domain"] == "api.example.com"
        assert details["path"] == "/users"
        assert details["timestamp"] == "2024-01-01T10:00:00Z"
        assert len(details["request_ids"]) == 1
        assert len(details["response_ids"]) == 1

    def test_minimal_flow(self):
        """Test extracting details from minimal flow."""
        flow = {}
        details = _get_flow_details(flow)

        assert details["method"] == "?"
        assert details["url"] == "?"
        assert details["domain"] == ""
        assert details["path"] == "/"
        assert details["request_ids"] == []
        assert details["response_ids"] == []


class TestGetApiKey:
    """Tests for _get_api_key function."""

    def test_basic_api_key(self):
        """Test basic API key generation."""
        flow = {
            "method": "GET",
            "url": "https://api.example.com/users",
        }
        key = _get_api_key(flow)

        assert key.startswith("GET ")
        assert "/users" in key

    def test_numeric_id_normalization(self):
        """Test that numeric IDs are normalized."""
        flow1 = {"method": "GET", "url": "https://api.example.com/users/123"}
        flow2 = {"method": "GET", "url": "https://api.example.com/users/456"}

        key1 = _get_api_key(flow1)
        key2 = _get_api_key(flow2)

        # Both should normalize to same pattern
        assert key1 == key2
        assert "{id}" in key1

    def test_uuid_normalization(self):
        """Test that UUIDs are normalized."""
        flow = {
            "method": "GET",
            "url": "https://api.example.com/items/550e8400-e29b-41d4-a716-446655440000",
        }
        key = _get_api_key(flow)

        assert "{uuid}" in key


class TestExportChainHtml:
    """Tests for export_chain_html function."""

    @pytest.fixture
    def sample_flows(self):
        """Create sample flows for testing."""
        return [
            {
                "method": "POST",
                "url": "https://api.example.com/users",
                "timestamp": "2024-01-01T10:00:00Z",
                "request_ids": [],
                "response_ids": [{"value": "12345", "type": "numeric", "location": "body", "field": "id"}],
            },
            {
                "method": "GET",
                "url": "https://api.example.com/users/12345",
                "timestamp": "2024-01-01T10:01:00Z",
                "request_ids": [{"value": "12345", "type": "numeric", "location": "path"}],
                "response_ids": [{"value": "67890", "type": "numeric", "location": "body", "field": "order_id"}],
            },
            {
                "method": "GET",
                "url": "https://api.example.com/orders/67890",
                "timestamp": "2024-01-01T10:02:00Z",
                "request_ids": [{"value": "67890", "type": "numeric", "location": "path"}],
                "response_ids": [],
            },
        ]

    @pytest.fixture
    def sample_flow_graph(self):
        """Create sample flow graph."""
        return {
            0: [(1, ["12345"])],
            1: [(2, ["67890"])],
        }

    @pytest.fixture
    def sample_flow_produces(self):
        """Create sample flow produces mapping."""
        return {
            0: ["12345"],
            1: ["67890"],
        }

    def test_creates_html_file(self, tmp_path, sample_flows, sample_flow_graph, sample_flow_produces):
        """Test that HTML file is created."""
        output_file = tmp_path / "chain.html"
        selected_roots = [(300, 3, 3, 0)]  # (score, depth, nodes, root_idx)

        export_chain_html(
            output_file,
            sample_flows,
            sample_flow_graph,
            sample_flow_produces,
            selected_roots,
        )

        assert output_file.exists()

    def test_html_contains_required_elements(self, tmp_path, sample_flows, sample_flow_graph, sample_flow_produces):
        """Test that HTML contains required elements."""
        output_file = tmp_path / "chain.html"
        selected_roots = [(300, 3, 3, 0)]

        export_chain_html(
            output_file,
            sample_flows,
            sample_flow_graph,
            sample_flow_produces,
            selected_roots,
        )

        content = output_file.read_text(encoding="utf-8")

        assert "<!DOCTYPE html>" in content
        assert "<title>" in content
        assert "idotaku" in content
        assert "<style>" in content
        assert "<script>" in content
        assert "treesData" in content

    def test_html_contains_flow_data(self, tmp_path, sample_flows, sample_flow_graph, sample_flow_produces):
        """Test that HTML contains flow data."""
        output_file = tmp_path / "chain.html"
        selected_roots = [(300, 3, 3, 0)]

        export_chain_html(
            output_file,
            sample_flows,
            sample_flow_graph,
            sample_flow_produces,
            selected_roots,
        )

        content = output_file.read_text(encoding="utf-8")

        # Should contain method and path from flows
        assert "POST" in content
        assert "/users" in content

    def test_multiple_roots(self, tmp_path, sample_flows, sample_flow_graph, sample_flow_produces):
        """Test export with multiple root trees."""
        output_file = tmp_path / "chain.html"
        # Two root trees
        selected_roots = [
            (300, 3, 3, 0),
            (100, 1, 1, 2),
        ]

        export_chain_html(
            output_file,
            sample_flows,
            sample_flow_graph,
            sample_flow_produces,
            selected_roots,
        )

        content = output_file.read_text(encoding="utf-8")

        # Should contain rank markers for both trees
        assert '"rank": 1' in content or '"rank":1' in content
        assert '"rank": 2' in content or '"rank":2' in content

    def test_empty_roots(self, tmp_path, sample_flows, sample_flow_graph, sample_flow_produces):
        """Test export with no root trees."""
        output_file = tmp_path / "chain.html"
        selected_roots = []

        export_chain_html(
            output_file,
            sample_flows,
            sample_flow_graph,
            sample_flow_produces,
            selected_roots,
        )

        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert "treesData = []" in content


class TestHtmlEscape:
    """Tests for HTML escape function."""

    def test_escape_html_entities(self):
        """Test HTML entity escaping."""
        assert html_escape("<script>") == "&lt;script&gt;"
        assert html_escape("a & b") == "a &amp; b"
        assert html_escape('"quoted"') == "&quot;quoted&quot;"

    def test_no_escape_needed(self):
        """Test string without special characters."""
        assert html_escape("normal text") == "normal text"

    def test_non_string_input(self):
        """Test non-string input."""
        assert html_escape(12345) == "12345"
