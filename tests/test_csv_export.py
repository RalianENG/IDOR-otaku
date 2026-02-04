"""Tests for CSV export."""

import csv

import pytest

from idotaku.export.csv_exporter import export_csv, export_idor_csv, export_flows_csv
from idotaku.report.loader import load_report


class TestExportIdorCsv:
    def test_creates_file(self, sample_report_file, tmp_path):
        output = tmp_path / "idor.csv"
        data = load_report(sample_report_file)
        export_idor_csv(output, data)
        assert output.exists()

    def test_correct_headers(self, sample_report_file, tmp_path):
        output = tmp_path / "idor.csv"
        data = load_report(sample_report_file)
        export_idor_csv(output, data)

        with open(output, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert set(reader.fieldnames) == {
                "id_value", "id_type", "method", "url", "location", "field", "reason",
            }

    def test_correct_row_count(self, sample_report_file, tmp_path):
        output = tmp_path / "idor.csv"
        data = load_report(sample_report_file)
        export_idor_csv(output, data)

        with open(output, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # sample_report_data has 1 IDOR finding with 1 usage
        assert len(rows) == 1
        assert rows[0]["id_value"] == "external_999"

    def test_empty_report(self, empty_report_file, tmp_path):
        output = tmp_path / "idor.csv"
        data = load_report(empty_report_file)
        export_idor_csv(output, data)

        with open(output, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 0


class TestExportFlowsCsv:
    def test_creates_file(self, sample_report_file, tmp_path):
        output = tmp_path / "flows.csv"
        data = load_report(sample_report_file)
        export_flows_csv(output, data)
        assert output.exists()

    def test_correct_headers(self, sample_report_file, tmp_path):
        output = tmp_path / "flows.csv"
        data = load_report(sample_report_file)
        export_flows_csv(output, data)

        with open(output, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert "timestamp" in reader.fieldnames
            assert "method" in reader.fieldnames
            assert "url" in reader.fieldnames

    def test_correct_row_count(self, sample_report_file, tmp_path):
        output = tmp_path / "flows.csv"
        data = load_report(sample_report_file)
        export_flows_csv(output, data)

        with open(output, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # sample_report_data has 4 flows
        assert len(rows) == 4


class TestExportCsv:
    def test_idor_mode(self, sample_report_file, tmp_path):
        output = tmp_path / "out.csv"
        data = load_report(sample_report_file)
        export_csv(output, data, mode="idor")
        assert output.exists()

    def test_flows_mode(self, sample_report_file, tmp_path):
        output = tmp_path / "out.csv"
        data = load_report(sample_report_file)
        export_csv(output, data, mode="flows")
        assert output.exists()

    def test_invalid_mode_raises(self, sample_report_file, tmp_path):
        output = tmp_path / "out.csv"
        data = load_report(sample_report_file)
        with pytest.raises(ValueError, match="Unknown export mode"):
            export_csv(output, data, mode="invalid")
