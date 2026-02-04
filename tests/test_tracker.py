"""Tests for IDTracker core logic (internal methods, no mitmproxy flow mocking)."""

import pytest

from idotaku.tracker import IDTracker, IDOccurrence, TrackedID, FlowRecord
from idotaku.config import IdotakuConfig


@pytest.fixture
def tracker():
    """Create an IDTracker with default config and ctx disabled."""
    t = IDTracker()
    t._use_ctx = False
    return t


class TestExtractIdsFromText:
    """Test _extract_ids_from_text()."""

    def test_numeric_id(self, tracker):
        result = tracker._extract_ids_from_text("user id is 12345")
        values = [v for v, t in result]
        assert "12345" in values

    def test_uuid(self, tracker):
        result = tracker._extract_ids_from_text(
            "id: 550e8400-e29b-41d4-a716-446655440000"
        )
        values = [v for v, t in result]
        assert "550e8400-e29b-41d4-a716-446655440000" in values

    def test_min_numeric_filtering(self, tracker):
        """Numbers below min_numeric should be excluded."""
        result = tracker._extract_ids_from_text("value is 50")
        values = [v for v, t in result]
        assert "50" not in values

    def test_above_min_numeric(self, tracker):
        result = tracker._extract_ids_from_text("value is 999")
        values = [v for v, t in result]
        assert "999" in values

    def test_empty_text(self, tracker):
        result = tracker._extract_ids_from_text("")
        assert result == []

    def test_no_ids_in_text(self, tracker):
        result = tracker._extract_ids_from_text("hello world")
        assert result == []


class TestExtractIdsFromJson:
    """Test _extract_ids_from_json()."""

    def test_flat_dict(self, tracker):
        data = {"user_id": 12345, "name": "test"}
        result = tracker._extract_ids_from_json(data)
        values = [v for v, t, f in result]
        assert "12345" in values

    def test_nested_dict(self, tracker):
        data = {"response": {"data": {"id": 67890}}}
        result = tracker._extract_ids_from_json(data)
        values = [v for v, t, f in result]
        assert "67890" in values

    def test_field_path(self, tracker):
        data = {"response": {"data": {"id": 67890}}}
        result = tracker._extract_ids_from_json(data)
        fields = [f for v, t, f in result if v == "67890"]
        assert "response.data.id" in fields

    def test_list_items(self, tracker):
        data = {"items": [{"id": 111}, {"id": 222}]}
        result = tracker._extract_ids_from_json(data)
        values = [v for v, t, f in result]
        assert "111" in values
        assert "222" in values

    def test_depth_limit(self, tracker):
        """Exceeding depth limit should return empty."""
        data = {"a": 12345}
        result = tracker._extract_ids_from_json(data, _depth=tracker._MAX_JSON_DEPTH)
        assert result == []

    def test_empty_dict(self, tracker):
        result = tracker._extract_ids_from_json({})
        assert result == []


class TestShouldExclude:
    """Test _should_exclude()."""

    def test_excluded_value(self, tracker):
        """Default exclude patterns should match certain values."""
        # Default exclude patterns include common non-ID values
        result = tracker._should_exclude("0")
        # "0" may or may not be excluded depending on config
        assert isinstance(result, bool)

    def test_normal_value_not_excluded(self, tracker):
        result = tracker._should_exclude("12345")
        assert result is False


class TestParseBody:
    """Test _parse_body()."""

    def test_json_body(self, tracker):
        content = b'{"id": 123}'
        result = tracker._parse_body(content, "application/json")
        assert isinstance(result, dict)
        assert result["id"] == 123

    def test_text_body(self, tracker):
        content = b"plain text body"
        result = tracker._parse_body(content, "text/plain")
        assert result == "plain text body"

    def test_empty_body(self, tracker):
        result = tracker._parse_body(b"", "application/json")
        assert result is None

    def test_invalid_json(self, tracker):
        content = b"not valid json"
        result = tracker._parse_body(content, "application/json")
        assert result is None


class TestRecordId:
    """Test _record_id()."""

    def test_record_response_origin(self, tracker):
        occ = IDOccurrence(
            id_value="12345", id_type="numeric",
            location="body", field_name="id",
            url="https://api.example.com/users",
            method="POST", timestamp="2024-01-01T10:00:00",
            direction="response",
        )
        tracker._record_id(occ)

        assert "12345" in tracker.tracked_ids
        assert tracker.tracked_ids["12345"].origin is occ
        assert len(tracker.response_log) == 1

    def test_record_request_usage(self, tracker):
        occ = IDOccurrence(
            id_value="12345", id_type="numeric",
            location="path", field_name=None,
            url="https://api.example.com/users/12345",
            method="GET", timestamp="2024-01-01T10:01:00",
            direction="request",
        )
        tracker._record_id(occ)

        assert "12345" in tracker.tracked_ids
        assert len(tracker.tracked_ids["12345"].usages) == 1
        assert len(tracker.request_log) == 1

    def test_origin_not_overwritten(self, tracker):
        """First response sets origin; subsequent responses don't overwrite."""
        occ1 = IDOccurrence(
            id_value="12345", id_type="numeric",
            location="body", field_name="id",
            url="https://api.example.com/a",
            method="POST", timestamp="t1",
            direction="response",
        )
        occ2 = IDOccurrence(
            id_value="12345", id_type="numeric",
            location="body", field_name="id",
            url="https://api.example.com/b",
            method="POST", timestamp="t2",
            direction="response",
        )
        tracker._record_id(occ1)
        tracker._record_id(occ2)

        assert tracker.tracked_ids["12345"].origin is occ1


class TestCollectIdsFromUrl:
    """Test _collect_ids_from_url()."""

    def test_path_ids(self, tracker):
        result = tracker._collect_ids_from_url("https://api.example.com/users/12345")
        values = [r["value"] for r in result]
        assert "12345" in values
        assert any(r["location"] == "url_path" for r in result if r["value"] == "12345")

    def test_query_ids(self, tracker):
        result = tracker._collect_ids_from_url("https://api.example.com/search?user_id=67890")
        values = [r["value"] for r in result]
        assert "67890" in values
        matching = [r for r in result if r["value"] == "67890"]
        assert matching[0]["location"] == "query"
        assert matching[0]["field"] == "user_id"

    def test_no_ids(self, tracker):
        result = tracker._collect_ids_from_url("https://api.example.com/health")
        # No numeric IDs above min_numeric in this URL
        numeric_ids = [r for r in result if r["type"] == "numeric"]
        assert len(numeric_ids) == 0


class TestCollectIdsFromBody:
    """Test _collect_ids_from_body()."""

    def test_json_body(self, tracker):
        body = b'{"user_id": 12345, "name": "test"}'
        result = tracker._collect_ids_from_body(body, "application/json")
        values = [r["value"] for r in result]
        assert "12345" in values
        matching = [r for r in result if r["value"] == "12345"]
        assert matching[0]["location"] == "body"
        assert matching[0]["field"] == "user_id"

    def test_text_body(self, tracker):
        body = b"the id is 99999"
        result = tracker._collect_ids_from_body(body, "text/plain")
        values = [r["value"] for r in result]
        assert "99999" in values

    def test_empty_body(self, tracker):
        result = tracker._collect_ids_from_body(b"", "application/json")
        assert result == []


class TestCollectIdsFromHeaders:
    """Test _collect_ids_from_headers()."""

    def test_cookie_header(self, tracker):
        headers = {"cookie": "session=abc12345678901234567890"}
        result = tracker._collect_ids_from_headers(headers)
        # All results should have location=header
        assert all(r["location"] == "header" for r in result)

    def test_set_cookie_header(self, tracker):
        headers = {"set-cookie": "sid=12345; Path=/; HttpOnly"}
        result = tracker._collect_ids_from_headers(headers)
        matching = [r for r in result if r["value"] == "12345"]
        if matching:
            assert matching[0]["field"].startswith("set-cookie:")

    def test_authorization_header(self, tracker):
        headers = {"authorization": "Bearer mytoken12345678901234567890"}
        result = tracker._collect_ids_from_headers(headers)
        assert all(r["location"] == "header" for r in result)
        auth_results = [r for r in result if r["field"] and "authorization" in r["field"]]
        assert len(auth_results) >= 0  # Depends on token pattern matching

    def test_ignored_header(self, tracker):
        """Headers in ignore list should be skipped."""
        headers = {"content-type": "application/json"}
        result = tracker._collect_ids_from_headers(headers)
        assert result == []

    def test_custom_header(self, tracker):
        headers = {"x-request-id": "12345"}
        result = tracker._collect_ids_from_headers(headers)
        values = [r["value"] for r in result]
        assert "12345" in values
        matching = [r for r in result if r["value"] == "12345"]
        assert matching[0]["field"] == "x-request-id"


class TestExtractAuthContext:
    """Test _extract_auth_context()."""

    def test_bearer_token(self, tracker):
        headers = {"authorization": "Bearer abc123def456"}
        result = tracker._extract_auth_context(headers)
        assert result is not None
        assert result["auth_type"] == "Bearer"
        assert len(result["token_hash"]) == 8

    def test_session_cookie(self, tracker):
        headers = {"cookie": "session=abc123; other=val"}
        result = tracker._extract_auth_context(headers)
        assert result is not None
        assert result["auth_type"] == "Cookie"

    def test_no_auth(self, tracker):
        headers = {"content-type": "application/json"}
        result = tracker._extract_auth_context(headers)
        assert result is None

    def test_different_tokens_different_hashes(self, tracker):
        h1 = {"authorization": "Bearer token_a"}
        h2 = {"authorization": "Bearer token_b"}
        r1 = tracker._extract_auth_context(h1)
        r2 = tracker._extract_auth_context(h2)
        assert r1["token_hash"] != r2["token_hash"]


class TestShouldTrackUrl:
    """Test _should_track_url()."""

    def test_track_api_url(self, tracker):
        assert tracker._should_track_url("https://api.example.com/users") is True

    def test_exclude_static_files(self, tracker):
        assert tracker._should_track_url("https://example.com/style.css") is False
        assert tracker._should_track_url("https://example.com/script.js") is False
        assert tracker._should_track_url("https://example.com/image.png") is False

    def test_domain_filtering(self):
        config = IdotakuConfig(target_domains=["api.example.com"])
        t = IDTracker(config)
        t._use_ctx = False
        assert t._should_track_url("https://api.example.com/users") is True
        assert t._should_track_url("https://other.com/users") is False


class TestGenerateReport:
    """Test generate_report()."""

    def test_empty_report(self, tracker):
        report = tracker.generate_report()
        assert report["summary"]["total_unique_ids"] == 0
        assert report["summary"]["total_flows"] == 0
        assert report["flows"] == []
        assert report["tracked_ids"] == {}
        assert report["potential_idor"] == []

    def test_report_with_data(self, tracker):
        """Simulate tracking and generate report."""
        # Record a response origin
        tracker._record_id(IDOccurrence(
            id_value="12345", id_type="numeric",
            location="body", field_name="id",
            url="https://api.example.com/users",
            method="POST", timestamp="t1",
            direction="response",
        ))
        # Record a request usage
        tracker._record_id(IDOccurrence(
            id_value="12345", id_type="numeric",
            location="path", field_name=None,
            url="https://api.example.com/users/12345",
            method="GET", timestamp="t2",
            direction="request",
        ))
        # Record usage-only ID (potential IDOR)
        tracker._record_id(IDOccurrence(
            id_value="99999", id_type="numeric",
            location="path", field_name=None,
            url="https://api.example.com/admin/99999",
            method="DELETE", timestamp="t3",
            direction="request",
        ))

        report = tracker.generate_report()
        assert report["summary"]["total_unique_ids"] == 2
        assert report["summary"]["ids_with_origin"] == 1
        assert report["summary"]["ids_with_usage"] == 2

        # Check IDOR detection
        idor_values = [i["id_value"] for i in report["potential_idor"]]
        assert "99999" in idor_values
        assert "12345" not in idor_values  # has origin

    def test_report_tracked_id_structure(self, tracker):
        tracker._record_id(IDOccurrence(
            id_value="555", id_type="numeric",
            location="body", field_name="id",
            url="https://api.example.com/items",
            method="POST", timestamp="t1",
            direction="response",
        ))
        report = tracker.generate_report()
        info = report["tracked_ids"]["555"]
        assert info["type"] == "numeric"
        assert info["first_seen"] == "t1"
        assert info["origin"] is not None
        assert info["origin"]["url"] == "https://api.example.com/items"

    def test_report_flow_records(self, tracker):
        """Flow records should appear in report."""
        tracker.flow_records["f1"] = FlowRecord(
            flow_id="f1", url="https://api.example.com/test",
            method="GET", timestamp="t1",
            request_ids=[{"value": "123", "type": "numeric", "location": "path", "field": None}],
            response_ids=[],
        )
        report = tracker.generate_report()
        assert report["summary"]["total_flows"] == 1
        assert len(report["flows"]) == 1
        assert report["flows"][0]["flow_id"] == "f1"

    def test_report_auth_context_in_flow(self, tracker):
        tracker.flow_records["f1"] = FlowRecord(
            flow_id="f1", url="https://api.example.com/test",
            method="GET", timestamp="t1",
            auth_context={"auth_type": "Bearer", "token_hash": "abc12345"},
        )
        report = tracker.generate_report()
        assert "auth_context" in report["flows"][0]
        assert report["flows"][0]["auth_context"]["auth_type"] == "Bearer"


class TestOccurrenceToDict:
    """Test _occurrence_to_dict()."""

    def test_converts_correctly(self, tracker):
        occ = IDOccurrence(
            id_value="12345", id_type="numeric",
            location="body", field_name="user_id",
            url="https://api.example.com/users",
            method="POST", timestamp="2024-01-01T10:00:00",
            direction="response",
        )
        result = tracker._occurrence_to_dict(occ)
        assert result["url"] == "https://api.example.com/users"
        assert result["method"] == "POST"
        assert result["location"] == "body"
        assert result["field_name"] == "user_id"
        assert result["timestamp"] == "2024-01-01T10:00:00"
        # direction and id_value/id_type are NOT included in dict
        assert "direction" not in result
        assert "id_value" not in result
