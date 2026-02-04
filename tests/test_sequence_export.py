"""Tests for sequence diagram export module."""

import pytest

from idotaku.export.sequence_exporter import (
    _build_lifeline_key,
    _build_sequence_data,
    export_sequence_html,
)


class TestBuildLifelineKey:
    """Tests for _build_lifeline_key function."""

    def test_basic_flow(self):
        """Test lifeline key from basic flow."""
        flow = {
            "method": "GET",
            "url": "https://api.example.com/users",
        }
        key = _build_lifeline_key(flow)
        assert "GET" in key
        assert "/users" in key
        assert "api.example.com" in key

    def test_numeric_id_normalized(self):
        """Test that numeric IDs are normalized in lifeline key."""
        flow1 = {"method": "GET", "url": "https://api.example.com/users/123"}
        flow2 = {"method": "GET", "url": "https://api.example.com/users/456"}
        assert _build_lifeline_key(flow1) == _build_lifeline_key(flow2)

    def test_empty_flow(self):
        """Test lifeline key from empty flow."""
        flow = {}
        key = _build_lifeline_key(flow)
        assert "?" in key


class TestBuildSequenceData:
    """Tests for _build_sequence_data function."""

    @pytest.fixture
    def sample_flows(self):
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
    def sample_tracked_ids(self):
        return {
            "12345": {"type": "numeric", "first_seen": "2024-01-01T10:00:00Z"},
            "67890": {"type": "numeric", "first_seen": "2024-01-01T10:01:00Z"},
        }

    @pytest.fixture
    def sample_idor(self):
        return [
            {"id_value": "external_999", "id_type": "numeric", "reason": "No origin"},
        ]

    def test_builds_lifelines(self, sample_flows, sample_tracked_ids, sample_idor):
        """Test that lifelines are correctly built."""
        data = _build_sequence_data(sample_flows, sample_tracked_ids, sample_idor)
        assert data["lifelines"][0] == "Client"
        assert len(data["lifelines"]) > 1

    def test_flow_lifeline_mapping(self, sample_flows, sample_tracked_ids, sample_idor):
        """Test that each flow maps to a lifeline column."""
        data = _build_sequence_data(sample_flows, sample_tracked_ids, sample_idor)
        assert len(data["flow_lifeline_map"]) == len(sample_flows)
        # All indices should be valid
        for idx in data["flow_lifeline_map"]:
            assert 0 <= idx < len(data["lifelines"])

    def test_flows_data_preserved(self, sample_flows, sample_tracked_ids, sample_idor):
        """Test that flow data is preserved in output."""
        data = _build_sequence_data(sample_flows, sample_tracked_ids, sample_idor)
        assert len(data["flows"]) == 3
        assert data["flows"][0]["method"] == "POST"
        assert data["flows"][1]["method"] == "GET"

    def test_idor_values_included(self, sample_flows, sample_tracked_ids, sample_idor):
        """Test that IDOR values are included."""
        data = _build_sequence_data(sample_flows, sample_tracked_ids, sample_idor)
        assert "external_999" in data["idor_values"]

    def test_id_info_built(self, sample_flows, sample_tracked_ids, sample_idor):
        """Test that ID info is correctly built."""
        data = _build_sequence_data(sample_flows, sample_tracked_ids, sample_idor)
        assert "12345" in data["id_info"]
        assert "67890" in data["id_info"]
        assert data["id_info"]["12345"]["type"] == "numeric"
        # 12345 is used in request once
        assert data["id_info"]["12345"]["usage_count"] == 1

    def test_empty_flows(self):
        """Test with empty flows list."""
        data = _build_sequence_data([], {}, [])
        assert data["flows"] == []
        assert data["lifelines"] == ["Client"]
        assert data["flow_lifeline_map"] == []

    def test_max_lifelines_limit(self):
        """Test that lifeline count is limited."""
        # Create flows with many different endpoints
        flows = []
        for i in range(15):
            flows.append({
                "method": "GET",
                "url": f"https://api.example.com/endpoint{i}",
                "timestamp": f"2024-01-01T10:{i:02d}:00Z",
                "request_ids": [],
                "response_ids": [],
            })
        data = _build_sequence_data(flows, {}, [], max_lifelines=5)
        # Should have Client + 5 endpoints + Other = 7
        assert len(data["lifelines"]) == 7
        assert data["lifelines"][-1] == "Other"


class TestExportSequenceHtml:
    """Tests for export_sequence_html function."""

    @pytest.fixture
    def sample_flows(self):
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
                "response_ids": [],
            },
        ]

    def test_creates_html_file(self, tmp_path, sample_flows):
        """Test that HTML file is created."""
        output = tmp_path / "sequence.html"
        export_sequence_html(output, sample_flows, {}, [])
        assert output.exists()

    def test_html_contains_required_elements(self, tmp_path, sample_flows):
        """Test that HTML contains required elements."""
        output = tmp_path / "sequence.html"
        export_sequence_html(output, sample_flows, {}, [])
        content = output.read_text(encoding="utf-8")

        assert "<!DOCTYPE html>" in content
        assert "<title>" in content
        assert "idotaku" in content
        assert "<style>" in content
        assert "<script>" in content
        assert "seqData" in content

    def test_html_contains_flow_data(self, tmp_path, sample_flows):
        """Test that HTML contains flow data."""
        output = tmp_path / "sequence.html"
        export_sequence_html(output, sample_flows, {}, [])
        content = output.read_text(encoding="utf-8")

        assert "POST" in content
        assert "/users" in content

    def test_empty_flows(self, tmp_path):
        """Test export with no flows."""
        output = tmp_path / "sequence.html"
        export_sequence_html(output, [], {}, [])
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert '"flows": []' in content or '"flows":[]' in content

    def test_idor_values_in_html(self, tmp_path, sample_flows):
        """Test that IDOR values appear in HTML data."""
        output = tmp_path / "sequence.html"
        idor = [{"id_value": "12345", "id_type": "numeric", "reason": "test"}]
        export_sequence_html(output, sample_flows, {}, idor)
        content = output.read_text(encoding="utf-8")
        assert "12345" in content
