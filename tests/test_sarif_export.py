"""Tests for SARIF export."""

import json

from idotaku.export.sarif_exporter import export_sarif, _build_sarif_result
from idotaku.report.loader import load_report


class TestBuildSarifResult:
    def test_basic_result(self):
        finding = {
            "id_value": "12345",
            "id_type": "numeric",
            "reason": "ID used in request but never seen in response",
            "usages": [
                {"method": "GET", "url": "https://api.example.com/users/12345", "location": "path"},
            ],
        }
        result = _build_sarif_result(finding)
        assert result["ruleId"] == "IDOR001"
        assert result["level"] == "warning"

    def test_result_has_message(self):
        finding = {
            "id_value": "abc-123",
            "id_type": "uuid",
            "reason": "No origin found",
            "usages": [],
        }
        result = _build_sarif_result(finding)
        assert "abc-123" in result["message"]["text"]
        assert "uuid" in result["message"]["text"]

    def test_result_has_locations(self):
        finding = {
            "id_value": "999",
            "id_type": "numeric",
            "reason": "test",
            "usages": [
                {"method": "DELETE", "url": "https://api.example.com/items/999", "location": "path"},
                {"method": "GET", "url": "https://api.example.com/items/999", "location": "path"},
            ],
        }
        result = _build_sarif_result(finding)
        assert len(result["locations"]) == 2

    def test_result_without_usages(self):
        finding = {
            "id_value": "empty",
            "id_type": "token",
            "reason": "test",
            "usages": [],
        }
        result = _build_sarif_result(finding)
        # Should still have a fallback location
        assert len(result["locations"]) == 1


class TestExportSarif:
    def test_creates_file(self, sample_report_file, tmp_path):
        output = tmp_path / "out.sarif.json"
        data = load_report(sample_report_file)
        export_sarif(output, data)
        assert output.exists()

    def test_valid_json(self, sample_report_file, tmp_path):
        output = tmp_path / "out.sarif.json"
        data = load_report(sample_report_file)
        export_sarif(output, data)

        with open(output, encoding="utf-8") as f:
            sarif = json.load(f)
        assert sarif["version"] == "2.1.0"
        assert "$schema" in sarif

    def test_correct_result_count(self, sample_report_file, tmp_path):
        output = tmp_path / "out.sarif.json"
        data = load_report(sample_report_file)
        export_sarif(output, data)

        with open(output, encoding="utf-8") as f:
            sarif = json.load(f)

        results = sarif["runs"][0]["results"]
        assert len(results) == len(data.potential_idor)

    def test_empty_report(self, empty_report_file, tmp_path):
        output = tmp_path / "out.sarif.json"
        data = load_report(empty_report_file)
        export_sarif(output, data)

        with open(output, encoding="utf-8") as f:
            sarif = json.load(f)

        results = sarif["runs"][0]["results"]
        assert len(results) == 0

    def test_tool_info(self, sample_report_file, tmp_path):
        output = tmp_path / "out.sarif.json"
        data = load_report(sample_report_file)
        export_sarif(output, data)

        with open(output, encoding="utf-8") as f:
            sarif = json.load(f)

        tool = sarif["runs"][0]["tool"]["driver"]
        assert tool["name"] == "idotaku"
        assert "rules" in tool
