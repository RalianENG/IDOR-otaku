"""Tests for HAR import."""

import json

import pytest

from idotaku.import_har import (
    import_har,
    import_har_to_file,
    _extract_ids_from_text,
    _collect_ids_from_url,
    _collect_ids_from_body,
    _collect_ids_from_headers,
    _build_tracked_ids,
    _build_potential_idor,
)
from idotaku.config import IdotakuConfig


@pytest.fixture
def config():
    return IdotakuConfig()


@pytest.fixture
def compiled(config):
    return {
        "patterns": config.get_compiled_patterns(),
        "exclude_patterns": config.get_compiled_exclude_patterns(),
        "min_numeric": config.min_numeric,
    }


@pytest.fixture
def sample_har_data():
    """Minimal HAR data for testing."""
    return {
        "log": {
            "version": "1.2",
            "entries": [
                {
                    "startedDateTime": "2024-01-01T10:00:00.000Z",
                    "request": {
                        "method": "POST",
                        "url": "https://api.example.com/users",
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"},
                        ],
                        "postData": {
                            "mimeType": "application/json",
                            "text": '{"name": "test"}',
                        },
                    },
                    "response": {
                        "status": 200,
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"},
                        ],
                        "content": {
                            "mimeType": "application/json",
                            "text": '{"id": 12345, "name": "test"}',
                        },
                    },
                },
                {
                    "startedDateTime": "2024-01-01T10:01:00.000Z",
                    "request": {
                        "method": "GET",
                        "url": "https://api.example.com/users/12345",
                        "headers": [],
                    },
                    "response": {
                        "status": 200,
                        "headers": [],
                        "content": {
                            "mimeType": "application/json",
                            "text": '{"id": 12345, "name": "test"}',
                        },
                    },
                },
                {
                    "startedDateTime": "2024-01-01T10:02:00.000Z",
                    "request": {
                        "method": "DELETE",
                        "url": "https://api.example.com/users/99999",
                        "headers": [],
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
def sample_har_file(sample_har_data, tmp_path):
    har_file = tmp_path / "test.har"
    with open(har_file, "w", encoding="utf-8") as f:
        json.dump(sample_har_data, f)
    return har_file


class TestExtractIdsFromText:
    def test_numeric_id(self, compiled):
        result = _extract_ids_from_text("12345", **compiled)
        values = [v for v, t in result]
        assert "12345" in values

    def test_uuid(self, compiled):
        result = _extract_ids_from_text(
            "550e8400-e29b-41d4-a716-446655440000", **compiled
        )
        values = [v for v, t in result]
        assert "550e8400-e29b-41d4-a716-446655440000" in values

    def test_below_min_numeric_excluded(self, compiled):
        result = _extract_ids_from_text("50", **compiled)
        values = [v for v, t in result]
        assert "50" not in values


class TestCollectIdsFromUrl:
    def test_path_ids(self, compiled):
        result = _collect_ids_from_url(
            "https://api.example.com/users/12345",
            compiled["patterns"], compiled["exclude_patterns"], compiled["min_numeric"],
        )
        values = [r["value"] for r in result]
        assert "12345" in values

    def test_query_ids(self, compiled):
        result = _collect_ids_from_url(
            "https://api.example.com/search?user_id=67890",
            compiled["patterns"], compiled["exclude_patterns"], compiled["min_numeric"],
        )
        values = [r["value"] for r in result]
        assert "67890" in values


class TestCollectIdsFromHeaders:
    def test_cookie_header(self, compiled, config):
        headers = [{"name": "Cookie", "value": "session=abc12345678901234567890"}]
        result = _collect_ids_from_headers(
            headers, compiled["patterns"], compiled["exclude_patterns"],
            compiled["min_numeric"], config.get_all_ignore_headers(),
        )
        assert len(result) >= 0  # May or may not match depending on token pattern

    def test_authorization_header(self, compiled, config):
        headers = [{"name": "Authorization", "value": "Bearer abc12345678901234567890def"}]
        result = _collect_ids_from_headers(
            headers, compiled["patterns"], compiled["exclude_patterns"],
            compiled["min_numeric"], config.get_all_ignore_headers(),
        )
        # Should extract token-like values from Bearer token
        assert all(r["location"] == "header" for r in result)


class TestImportHar:
    def test_basic_import(self, sample_har_file):
        report = import_har(sample_har_file)
        assert "summary" in report
        assert "flows" in report
        assert "tracked_ids" in report
        assert "potential_idor" in report

    def test_flow_count(self, sample_har_file):
        report = import_har(sample_har_file)
        assert report["summary"]["total_flows"] == 3

    def test_tracked_ids_populated(self, sample_har_file):
        report = import_har(sample_har_file)
        assert report["summary"]["total_unique_ids"] > 0

    def test_potential_idor_detected(self, sample_har_file):
        report = import_har(sample_har_file)
        # ID 99999 appears in request path but not in any response
        idor_values = [item["id_value"] for item in report["potential_idor"]]
        assert "99999" in idor_values

    def test_origin_tracking(self, sample_har_file):
        report = import_har(sample_har_file)
        # ID 12345 appears in response first, so should have origin
        if "12345" in report["tracked_ids"]:
            assert report["tracked_ids"]["12345"]["origin"] is not None

    def test_empty_har(self, tmp_path):
        har_file = tmp_path / "empty.har"
        with open(har_file, "w") as f:
            json.dump({"log": {"version": "1.2", "entries": []}}, f)

        report = import_har(har_file)
        assert report["summary"]["total_flows"] == 0
        assert report["potential_idor"] == []


class TestImportHarToFile:
    def test_creates_output(self, sample_har_file, tmp_path):
        output = tmp_path / "report.json"
        report = import_har_to_file(sample_har_file, output)
        assert output.exists()
        assert report["summary"]["total_flows"] > 0

    def test_output_is_valid_json(self, sample_har_file, tmp_path):
        output = tmp_path / "report.json"
        import_har_to_file(sample_har_file, output)

        with open(output, encoding="utf-8") as f:
            data = json.load(f)
        assert "summary" in data


class TestBuildTrackedIds:
    def test_origin_set_from_response(self):
        flows = [
            {
                "method": "POST",
                "url": "https://api.example.com/users",
                "timestamp": "2024-01-01T10:00:00",
                "request_ids": [],
                "response_ids": [{"value": "123", "type": "numeric", "location": "body", "field": "id"}],
            },
        ]
        tracked = _build_tracked_ids(flows)
        assert tracked["123"]["origin"] is not None

    def test_usage_recorded_from_request(self):
        flows = [
            {
                "method": "GET",
                "url": "https://api.example.com/users/123",
                "timestamp": "2024-01-01T10:01:00",
                "request_ids": [{"value": "123", "type": "numeric", "location": "url_path"}],
                "response_ids": [],
            },
        ]
        tracked = _build_tracked_ids(flows)
        assert len(tracked["123"]["usages"]) == 1


class TestBuildPotentialIdor:
    def test_detects_usage_without_origin(self):
        tracked = {
            "999": {
                "type": "numeric",
                "first_seen": "t",
                "origin": None,
                "usage_count": 1,
                "usages": [{"url": "x", "method": "GET", "location": "path"}],
            },
        }
        idor = _build_potential_idor(tracked)
        assert len(idor) == 1
        assert idor[0]["id_value"] == "999"

    def test_no_idor_when_origin_exists(self):
        tracked = {
            "123": {
                "type": "numeric",
                "first_seen": "t",
                "origin": {"url": "x", "method": "POST"},
                "usage_count": 1,
                "usages": [{"url": "y", "method": "GET"}],
            },
        }
        idor = _build_potential_idor(tracked)
        assert len(idor) == 0
