"""Tests for report loading and analysis functions."""

import pytest

from idotaku.report import (
    load_report,
    ReportLoadError,
    ReportData,
    ReportSummary,
    build_param_producer_consumer,
    build_param_flow_mappings,
    build_flow_graph,
    build_api_dependencies,
    build_id_transition_map,
)


class TestLoadReport:
    """Tests for load_report function."""

    def test_load_valid_report(self, sample_report_file):
        """Test loading a valid report file."""
        data = load_report(sample_report_file)

        assert isinstance(data, ReportData)
        assert isinstance(data.summary, ReportSummary)
        assert data.summary.total_unique_ids == 5
        assert data.summary.ids_with_origin == 4
        assert data.summary.total_flows == 10

    def test_load_empty_report(self, empty_report_file):
        """Test loading an empty report file."""
        data = load_report(empty_report_file)

        assert data.summary.total_unique_ids == 0
        assert len(data.tracked_ids) == 0
        assert len(data.flows) == 0

    def test_load_nonexistent_file(self, tmp_path):
        """Test loading a non-existent file exits with error."""
        with pytest.raises(SystemExit):
            load_report(tmp_path / "nonexistent.json")

    def test_load_invalid_json(self, tmp_path):
        """Test loading a file with invalid JSON exits with error."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json{{{")
        with pytest.raises(SystemExit):
            load_report(bad_file)

    def test_load_partial_report(self, tmp_path):
        """Test loading a JSON file missing some keys uses defaults."""
        partial = tmp_path / "partial.json"
        partial.write_text('{"summary": {"total_unique_ids": 3}}')
        data = load_report(partial)
        assert data.summary.total_unique_ids == 3
        assert data.summary.total_flows == 0  # default
        assert data.flows == []  # default
        assert data.tracked_ids == {}  # default

    def test_sorted_flows(self, sample_report_file):
        """Test that sorted_flows returns flows in timestamp order."""
        data = load_report(sample_report_file)
        sorted_flows = data.sorted_flows

        timestamps = [f.get("timestamp", "") for f in sorted_flows]
        assert timestamps == sorted(timestamps)

    def test_idor_values(self, sample_report_file):
        """Test that idor_values returns correct set."""
        data = load_report(sample_report_file)

        assert "external_999" in data.idor_values
        assert "12345" not in data.idor_values

    def test_is_idor(self, sample_report_file):
        """Test is_idor method."""
        data = load_report(sample_report_file)

        assert data.is_idor("external_999") is True
        assert data.is_idor("12345") is False


class TestBuildParamProducerConsumer:
    """Tests for build_param_producer_consumer function."""

    def test_basic_mapping(self, sample_report_file):
        """Test basic producer/consumer mapping."""
        data = load_report(sample_report_file)
        producer, consumers = build_param_producer_consumer(data.sorted_flows)

        # Check producer
        assert "12345" in producer
        assert producer["12345"]["method"] == "POST"

        # Check consumers
        assert "12345" in consumers
        assert len(consumers["12345"]) >= 1

    def test_empty_flows(self):
        """Test with empty flows."""
        producer, consumers = build_param_producer_consumer([])

        assert len(producer) == 0
        assert len(consumers) == 0


class TestBuildParamFlowMappings:
    """Tests for build_param_flow_mappings function."""

    def test_basic_mappings(self, sample_report_file):
        """Test basic flow mappings."""
        data = load_report(sample_report_file)
        param_origins, param_usages, flow_produces = build_param_flow_mappings(data.sorted_flows)

        # Check that response IDs are tracked as origins
        assert "12345" in param_origins
        assert "67890" in param_origins

        # Check that request IDs are tracked as usages
        assert "12345" in param_usages

        # Check flow_produces maps flow indices to params
        assert len(flow_produces) > 0


class TestBuildFlowGraph:
    """Tests for build_flow_graph function."""

    def test_basic_graph(self, sample_report_file):
        """Test basic flow graph construction."""
        data = load_report(sample_report_file)
        param_origins, param_usages, _ = build_param_flow_mappings(data.sorted_flows)
        graph = build_flow_graph(param_origins, param_usages)

        # Graph should have edges from producer flows to consumer flows
        assert isinstance(graph, dict)

    def test_empty_graph(self):
        """Test with empty mappings."""
        graph = build_flow_graph({}, {})
        assert len(graph) == 0


class TestBuildApiDependencies:
    """Tests for build_api_dependencies function."""

    def test_basic_dependencies(self, sample_report_file):
        """Test basic API dependency building."""
        data = load_report(sample_report_file)
        producer, consumers = build_param_producer_consumer(data.sorted_flows)
        deps = build_api_dependencies(producer, consumers)

        # Should have at least one API dependency
        assert isinstance(deps, dict)


class TestBuildIdTransitionMap:
    """Tests for build_id_transition_map function."""

    def test_basic_transition(self, sample_report_file):
        """Test basic ID transition mapping."""
        data = load_report(sample_report_file)
        id_to_origin, id_to_usage = build_id_transition_map(data.sorted_flows)

        # Check origins are tracked
        assert "12345" in id_to_origin
        assert id_to_origin["12345"]["flow_idx"] == 0

        # Check usages are tracked
        assert "12345" in id_to_usage
        assert len(id_to_usage["12345"]) >= 1

    def test_empty_flows(self):
        """Test with empty flows."""
        id_to_origin, id_to_usage = build_id_transition_map([])

        assert len(id_to_origin) == 0
        assert len(id_to_usage) == 0


class TestLoadReportWithExitOnError:
    """Tests for load_report with exit_on_error parameter."""

    def test_raises_on_nonexistent_file(self, tmp_path):
        """Test that ReportLoadError is raised for nonexistent file."""
        with pytest.raises(ReportLoadError, match="Cannot read"):
            load_report(tmp_path / "nonexistent.json", exit_on_error=False)

    def test_raises_on_invalid_json(self, tmp_path):
        """Test that ReportLoadError is raised for invalid JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json{{{")
        with pytest.raises(ReportLoadError, match="Invalid JSON"):
            load_report(bad_file, exit_on_error=False)

    def test_returns_data_on_success(self, sample_report_file):
        """Test successful load with exit_on_error=False."""
        data = load_report(sample_report_file, exit_on_error=False)
        assert isinstance(data, ReportData)
        assert data.summary.total_unique_ids == 5
