"""Tests for diff analysis."""

import json

import pytest

from idotaku.report.diff import diff_reports, diff_to_dict
from idotaku.report.loader import load_report


@pytest.fixture
def modified_report_data(sample_report_data):
    """Modified report data for diff testing."""
    import copy

    data = copy.deepcopy(sample_report_data)
    # Add a new IDOR finding
    data["potential_idor"].append({
        "id_value": "new_finding_456",
        "id_type": "numeric",
        "reason": "New finding",
        "usages": [
            {"method": "PUT", "url": "https://api.example.com/items/456", "location": "path"},
        ],
    })
    # Add new tracked ID
    data["tracked_ids"]["new_id_789"] = {
        "type": "numeric",
        "first_seen": "2024-01-01T11:00:00",
        "origin": None,
        "usages": [],
    }
    # Update summary
    data["summary"]["total_unique_ids"] += 1
    data["summary"]["total_flows"] += 2
    return data


@pytest.fixture
def modified_report_file(modified_report_data, tmp_path):
    report_file = tmp_path / "modified_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(modified_report_data, f)
    return report_file


class TestDiffReports:
    def test_identical_reports(self, sample_report_file):
        data = load_report(sample_report_file)
        result = diff_reports(data, data)
        assert not result.has_changes

    def test_new_idor_detected(self, sample_report_file, modified_report_file):
        data_a = load_report(sample_report_file)
        data_b = load_report(modified_report_file)
        result = diff_reports(data_a, data_b)
        assert len(result.new_idor) == 1
        assert result.new_idor[0]["id_value"] == "new_finding_456"

    def test_removed_idor_detected(self, sample_report_file, modified_report_file):
        data_a = load_report(modified_report_file)
        data_b = load_report(sample_report_file)
        result = diff_reports(data_a, data_b)
        assert len(result.removed_idor) == 1

    def test_new_tracked_ids(self, sample_report_file, modified_report_file):
        data_a = load_report(sample_report_file)
        data_b = load_report(modified_report_file)
        result = diff_reports(data_a, data_b)
        assert "new_id_789" in result.new_ids

    def test_flow_count_changes(self, sample_report_file, modified_report_file):
        data_a = load_report(sample_report_file)
        data_b = load_report(modified_report_file)
        result = diff_reports(data_a, data_b)
        assert result.flow_count_b > result.flow_count_a

    def test_has_changes_property(self, sample_report_file, modified_report_file):
        data_a = load_report(sample_report_file)
        data_b = load_report(modified_report_file)
        result = diff_reports(data_a, data_b)
        assert result.has_changes


class TestDiffToDict:
    def test_serializable(self, sample_report_file, modified_report_file):
        data_a = load_report(sample_report_file)
        data_b = load_report(modified_report_file)
        result = diff_reports(data_a, data_b)
        d = diff_to_dict(result)
        # Should be JSON-serializable
        json.dumps(d)

    def test_contains_all_sections(self, sample_report_file, modified_report_file):
        data_a = load_report(sample_report_file)
        data_b = load_report(modified_report_file)
        result = diff_reports(data_a, data_b)
        d = diff_to_dict(result)
        assert "has_changes" in d
        assert "idor" in d
        assert "tracked_ids" in d
        assert "flows" in d
        assert "ids" in d

    def test_delta_values(self, sample_report_file, modified_report_file):
        data_a = load_report(sample_report_file)
        data_b = load_report(modified_report_file)
        result = diff_reports(data_a, data_b)
        d = diff_to_dict(result)
        assert d["flows"]["delta"] == result.flow_count_b - result.flow_count_a
