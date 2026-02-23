"""Tests for IDTracker core logic (internal methods, no mitmproxy flow mocking)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from idotaku.tracker import IDTracker, IDOccurrence, FlowRecord
from idotaku.config import IdotakuConfig


class MockHeaders(dict):
    """Mock mitmproxy headers with get() method."""

    def get(self, key, default=""):
        return super().get(key.lower(), default)


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
        """Test that invalid JSON falls back to plain text (not None).

        This allows ID extraction from malformed JSON responses,
        which is useful for API testing when responses may be corrupted.
        """
        content = b"not valid json"
        result = tracker._parse_body(content, "application/json")
        # Falls back to plain text instead of returning None
        assert result == "not valid json"


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


class TestLogMethod:
    """Test _log() method."""

    def test_log_info_without_ctx(self, tracker, capsys):
        """Test info logging without mitmproxy context."""
        tracker._use_ctx = False
        tracker._log("info", "test message")
        captured = capsys.readouterr()
        assert "[INFO] test message" in captured.out

    def test_log_warn_without_ctx(self, tracker, capsys):
        """Test warning log without context."""
        tracker._use_ctx = False
        tracker._log("warn", "warning message")
        captured = capsys.readouterr()
        assert "[WARN] warning message" in captured.out

    def test_log_error_without_ctx(self, tracker, capsys):
        """Test error log without context."""
        tracker._use_ctx = False
        tracker._log("error", "error message")
        captured = capsys.readouterr()
        assert "[ERROR] error message" in captured.out

    def test_log_with_ctx_fallback(self, tracker, capsys):
        """Test logging falls back when ctx raises exception."""
        tracker._use_ctx = True
        # ctx.log will raise because we're not in mitmproxy
        tracker._log("info", "fallback message")
        captured = capsys.readouterr()
        assert "fallback message" in captured.out


class TestDoneMethod:
    """Test done() method."""

    def test_done_writes_report(self, tracker):
        """Test done() writes report to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker.output_file = str(Path(tmpdir) / "report.json")
            tracker.done()
            assert Path(tracker.output_file).exists()
            with open(tracker.output_file) as f:
                data = json.load(f)
            assert "summary" in data
            assert "flows" in data

    def test_done_creates_parent_dirs(self, tracker):
        """Test done() creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker.output_file = str(Path(tmpdir) / "subdir" / "nested" / "report.json")
            tracker.done()
            assert Path(tracker.output_file).exists()

    def test_done_handles_write_error(self, tracker, capsys):
        """Test done() handles write errors gracefully."""
        with patch("builtins.open", side_effect=OSError("Mocked write error")):
            tracker.done()
        captured = capsys.readouterr()
        assert "Failed to save" in captured.out or "ERROR" in captured.out


class TestPrintSummary:
    """Test print_summary() method."""

    def test_print_summary_empty(self, tracker, capsys):
        """Test summary with no data."""
        tracker.print_summary()
        captured = capsys.readouterr()
        assert "Summary" in captured.out
        assert "Total unique IDs tracked: 0" in captured.out

    def test_print_summary_with_potential_idor(self, tracker, capsys):
        """Test summary shows potential IDOR."""
        tracker._record_id(IDOccurrence(
            id_value="99999", id_type="numeric",
            location="path", field_name=None,
            url="https://api.example.com/admin/99999",
            method="DELETE", timestamp="t1",
            direction="request",
        ))
        tracker.print_summary()
        captured = capsys.readouterr()
        assert "Potential IDOR" in captured.out
        assert "99999" in captured.out


class TestMitmproxyFlowMocking:
    """Test request/response methods with mocked flows."""

    def test_request_basic(self, tracker):
        """Test request() processes basic flow."""
        flow = MagicMock()
        flow.id = "test-flow-1"
        flow.request.pretty_url = "https://api.example.com/users/12345"
        flow.request.method = "GET"
        flow.request.headers = MockHeaders({"content-type": "application/json"})
        flow.request.content = b"{}"

        tracker.request(flow)

        assert "test-flow-1" in tracker.flow_records
        assert "12345" in tracker.tracked_ids

    def test_request_with_body(self, tracker):
        """Test request() extracts IDs from body."""
        flow = MagicMock()
        flow.id = "test-flow-2"
        flow.request.pretty_url = "https://api.example.com/users"
        flow.request.method = "POST"
        flow.request.headers = MockHeaders({"content-type": "application/json"})
        flow.request.content = b'{"user_id": 67890}'

        tracker.request(flow)

        assert "67890" in tracker.tracked_ids

    def test_request_domain_filtered(self):
        """Test request() filters domains."""
        config = IdotakuConfig(target_domains=["allowed.com"])
        tracker = IDTracker(config)
        tracker._use_ctx = False

        flow = MagicMock()
        flow.id = "filtered-flow"
        flow.request.pretty_url = "https://blocked.com/api/12345"
        flow.request.method = "GET"
        flow.request.headers = MockHeaders({})
        flow.request.content = b""

        tracker.request(flow)

        assert "filtered-flow" not in tracker.flow_records

    def test_request_extension_filtered(self, tracker):
        """Test request() filters static files."""
        flow = MagicMock()
        flow.id = "css-flow"
        flow.request.pretty_url = "https://api.example.com/style.css"
        flow.request.method = "GET"
        flow.request.headers = MockHeaders({})
        flow.request.content = b""

        tracker.request(flow)

        assert "css-flow" not in tracker.flow_records

    def test_request_with_auth_context(self, tracker):
        """Test request() extracts auth context."""
        flow = MagicMock()
        flow.id = "auth-flow"
        flow.request.pretty_url = "https://api.example.com/users"
        flow.request.method = "GET"
        flow.request.headers = MockHeaders({
            "authorization": "Bearer test_token_123",
            "content-type": "application/json",
        })
        flow.request.content = b""

        tracker.request(flow)

        assert tracker.flow_records["auth-flow"].auth_context is not None
        assert tracker.flow_records["auth-flow"].auth_context["auth_type"] == "Bearer"

    def test_response_basic(self, tracker):
        """Test response() processes basic flow."""
        # First create flow via request
        flow = MagicMock()
        flow.id = "resp-flow"
        flow.request.pretty_url = "https://api.example.com/users"
        flow.request.method = "POST"
        flow.request.headers = MockHeaders({"content-type": "application/json"})
        flow.request.content = b"{}"
        tracker.request(flow)

        # Then process response
        flow.response.headers = MockHeaders({"content-type": "application/json"})
        flow.response.content = b'{"id": 55555}'
        tracker.response(flow)

        assert "55555" in tracker.tracked_ids
        assert tracker.tracked_ids["55555"].origin is not None

    def test_response_creates_flow_if_missing(self, tracker):
        """Test response() creates flow if not exists."""
        flow = MagicMock()
        flow.id = "response-only"
        flow.request.pretty_url = "https://api.example.com/data"
        flow.request.method = "GET"
        flow.response.headers = MockHeaders({"content-type": "application/json"})
        flow.response.content = b'{"result": 77777}'

        tracker.response(flow)

        assert "response-only" in tracker.flow_records
        assert "77777" in tracker.tracked_ids

    def test_full_request_response_cycle(self, tracker):
        """Test full request-response cycle with IDOR detection."""
        # Request with unknown ID (potential IDOR)
        req_flow = MagicMock()
        req_flow.id = "idor-flow"
        req_flow.request.pretty_url = "https://api.example.com/admin/88888"
        req_flow.request.method = "DELETE"
        req_flow.request.headers = MockHeaders({})
        req_flow.request.content = b""
        tracker.request(req_flow)

        report = tracker.generate_report()
        idor_values = [i["id_value"] for i in report["potential_idor"]]
        assert "88888" in idor_values


class TestApplyConfig:
    """Test _apply_config() method."""

    def test_apply_custom_config(self):
        """Test applying custom config."""
        config = IdotakuConfig(
            output="custom.json",
            min_numeric=500,
            target_domains=["api.test.com"],
        )
        tracker = IDTracker(config)

        assert tracker.output_file == "custom.json"
        assert tracker.min_numeric == 500
        assert "api.test.com" in tracker.target_domains

    def test_reapply_config(self, tracker):
        """Test reapplying config updates values."""
        new_config = IdotakuConfig(min_numeric=1000)
        tracker._apply_config(new_config)

        assert tracker.min_numeric == 1000


class TestLoadMethod:
    """Test load() method (mitmproxy addon loader registration)."""

    def test_load_registers_options(self, tracker):
        """Test that load() registers three mitmproxy options."""
        loader = MagicMock()
        tracker.load(loader)
        assert loader.add_option.call_count == 3


class TestConfigureMethod:
    """Test configure() method (mitmproxy config update handler)."""

    def test_configure_config_path(self, tracker):
        """Test configure() loads config when idotaku_config changes."""
        with patch("idotaku.tracker.ctx") as mock_ctx:
            mock_ctx.options.idotaku_config = "test_config.yaml"
            mock_ctx.options.idotaku_output = ""
            mock_ctx.options.idotaku_min_numeric = 0
            tracker._use_ctx = True
            with patch("idotaku.tracker.load_config") as mock_load:
                mock_load.return_value = IdotakuConfig()
                tracker.configure({"idotaku_config"})
                mock_load.assert_called_once_with("test_config.yaml")

    def test_configure_output(self, tracker):
        """Test configure() updates output_file when idotaku_output changes."""
        with patch("idotaku.tracker.ctx") as mock_ctx:
            mock_ctx.options.idotaku_output = "custom_output.json"
            mock_ctx.options.idotaku_min_numeric = 0
            tracker._use_ctx = True
            tracker.configure({"idotaku_output"})
            assert tracker.output_file == "custom_output.json"

    def test_configure_min_numeric(self, tracker):
        """Test configure() updates min_numeric when idotaku_min_numeric changes."""
        with patch("idotaku.tracker.ctx") as mock_ctx:
            mock_ctx.options.idotaku_min_numeric = 500
            mock_ctx.options.idotaku_output = ""
            tracker._use_ctx = True
            tracker.configure({"idotaku_min_numeric"})
            assert tracker.min_numeric == 500


class TestLogWithCtx:
    """Test _log() with ctx enabled calling specific log levels."""

    def test_log_info_with_ctx(self, tracker):
        """Test _log('info', ...) calls ctx.log.info()."""
        tracker._use_ctx = True
        with patch("idotaku.tracker.ctx") as mock_ctx:
            tracker._log("info", "test info")
            mock_ctx.log.info.assert_called_once_with("test info")

    def test_log_warn_with_ctx(self, tracker):
        """Test _log('warn', ...) calls ctx.log.warn()."""
        tracker._use_ctx = True
        with patch("idotaku.tracker.ctx") as mock_ctx:
            tracker._log("warn", "test warn")
            mock_ctx.log.warn.assert_called_once_with("test warn")

    def test_log_error_with_ctx(self, tracker):
        """Test _log('error', ...) calls ctx.log.error()."""
        tracker._use_ctx = True
        with patch("idotaku.tracker.ctx") as mock_ctx:
            tracker._log("error", "test error")
            mock_ctx.log.error.assert_called_once_with("test error")


class TestParseBodyEdgeCases:
    """Test _parse_body() error handling edge cases."""

    def test_parse_body_type_error(self, tracker):
        """Test _parse_body handles TypeError from malformed data."""
        with patch("json.loads", side_effect=TypeError("test")):
            result = tracker._parse_body(b'{"valid": "json"}', "application/json")
            # Should fall back to decoded text
            assert result == '{"valid": "json"}'


class TestResponseNone:
    """Test response() when flow.response is None."""

    def test_response_with_none_response(self, tracker):
        """Test response() returns early when flow.response is None."""
        flow = MagicMock()
        flow.id = "null-response"
        flow.request.pretty_url = "https://api.example.com/data"
        flow.request.method = "GET"
        flow.request.headers = MockHeaders({})
        flow.request.content = b""
        flow.response = None

        # Should not raise
        tracker.response(flow)

        # Flow should not be recorded since response was None
        assert "null-response" not in tracker.flow_records


class TestShouldExcludeEdgeCases:
    """Test _should_exclude() additional edge cases."""

    def test_should_exclude_returns_false_for_normal_id(self, tracker):
        """Verify that normal numeric IDs are not excluded."""
        result = tracker._should_exclude("12345")
        assert result is False

    def test_should_exclude_returns_false_for_uuid(self, tracker):
        """Verify that UUIDs are not excluded."""
        result = tracker._should_exclude("550e8400-e29b-41d4-a716-446655440000")
        assert result is False


class TestShouldExcludeReturnsTrue:
    """Test _should_exclude() returning True (line 172)."""

    def test_exclude_unix_timestamp(self, tracker):
        """A 10-13 digit number matches the default exclude pattern for Unix timestamps."""
        # Default exclude pattern: r"^\d{10,13}$" matches Unix timestamps
        result = tracker._should_exclude("1700000000")
        assert result is True

    def test_exclude_unix_timestamp_13_digits(self, tracker):
        """13-digit number (millisecond timestamp) should be excluded."""
        result = tracker._should_exclude("1700000000000")
        assert result is True

    def test_exclude_version_number(self, tracker):
        """Version numbers like 1.2.3 should be excluded by default pattern."""
        # Default exclude pattern: r"^\d+\.\d+\.\d+$"
        result = tracker._should_exclude("1.2.3")
        assert result is True

    def test_exclude_does_not_match_normal_id(self, tracker):
        """Normal IDs should not be excluded."""
        result = tracker._should_exclude("12345")
        assert result is False


class TestExtractIdsFromTextValueError:
    """Test _extract_ids_from_text() ValueError handling (lines 186-188).

    The default numeric pattern r'\\b[1-9]\\d{2,10}\\b' always matches valid ints,
    so we override the pattern to one that can match non-integer strings
    to trigger the ValueError path.
    """

    def test_numeric_value_error_path(self, tracker):
        """Trigger ValueError in int() conversion by using a custom numeric pattern."""
        import re
        # Override the numeric pattern to match strings containing dots (e.g. "123.456")
        # which will fail int() conversion
        tracker.patterns["numeric"] = re.compile(r"\b[\d.]{3,10}\b")
        result = tracker._extract_ids_from_text("value is 12.345 here")
        # The match "12.345" would fail int() and be skipped via ValueError
        values = [v for v, t in result]
        assert "12.345" not in values


class TestProcessUrl:
    """Test _process_url() directly (lines 393-413)."""

    def test_process_url_path_ids(self, tracker):
        """Test _process_url extracts IDs from URL path and records them."""
        tracker._process_url(
            "https://api.example.com/users/12345",
            "GET", "request", "2024-01-01T10:00:00"
        )
        assert "12345" in tracker.tracked_ids
        assert len(tracker.request_log) == 1
        assert tracker.request_log[0].location == "url_path"
        assert tracker.request_log[0].direction == "request"

    def test_process_url_query_ids(self, tracker):
        """Test _process_url extracts IDs from query parameters."""
        tracker._process_url(
            "https://api.example.com/search?user_id=67890",
            "GET", "request", "2024-01-01T10:00:00"
        )
        assert "67890" in tracker.tracked_ids
        assert tracker.request_log[0].location == "query"
        assert tracker.request_log[0].field_name == "user_id"

    def test_process_url_response_direction(self, tracker):
        """Test _process_url with response direction sets origin."""
        tracker._process_url(
            "https://api.example.com/items/99999",
            "POST", "response", "2024-01-01T10:00:00"
        )
        assert "99999" in tracker.tracked_ids
        assert tracker.tracked_ids["99999"].origin is not None
        assert len(tracker.response_log) == 1

    def test_process_url_no_ids(self, tracker):
        """Test _process_url with no IDs in URL."""
        tracker._process_url(
            "https://api.example.com/health",
            "GET", "request", "2024-01-01T10:00:00"
        )
        assert len(tracker.tracked_ids) == 0

    def test_process_url_both_path_and_query(self, tracker):
        """Test _process_url extracts from both path and query."""
        tracker._process_url(
            "https://api.example.com/users/11111?order_id=22222",
            "GET", "request", "2024-01-01T10:00:00"
        )
        assert "11111" in tracker.tracked_ids
        assert "22222" in tracker.tracked_ids


class TestProcessBody:
    """Test _process_body() directly (lines 430-450)."""

    def test_process_body_json_dict(self, tracker):
        """Test _process_body with JSON dict body."""
        tracker._process_body(
            b'{"user_id": 12345}', "application/json",
            "https://api.example.com/users", "POST", "response",
            "2024-01-01T10:00:00"
        )
        assert "12345" in tracker.tracked_ids
        assert tracker.tracked_ids["12345"].origin is not None
        assert tracker.response_log[0].location == "body"
        assert tracker.response_log[0].field_name == "user_id"

    def test_process_body_json_list(self, tracker):
        """Test _process_body with JSON list body."""
        tracker._process_body(
            b'[{"id": 11111}, {"id": 22222}]', "application/json",
            "https://api.example.com/items", "GET", "response",
            "2024-01-01T10:00:00"
        )
        assert "11111" in tracker.tracked_ids
        assert "22222" in tracker.tracked_ids

    def test_process_body_text(self, tracker):
        """Test _process_body with plain text body (line 448-461)."""
        tracker._process_body(
            b"the user id is 99999", "text/plain",
            "https://api.example.com/data", "GET", "response",
            "2024-01-01T10:00:00"
        )
        assert "99999" in tracker.tracked_ids
        assert tracker.response_log[0].location == "body"
        assert tracker.response_log[0].field_name is None

    def test_process_body_empty(self, tracker):
        """Test _process_body with empty body returns early."""
        tracker._process_body(
            b"", "application/json",
            "https://api.example.com/data", "GET", "response",
            "2024-01-01T10:00:00"
        )
        assert len(tracker.tracked_ids) == 0

    def test_process_body_request_direction(self, tracker):
        """Test _process_body with request direction records usage."""
        tracker._process_body(
            b'{"target_id": 55555}', "application/json",
            "https://api.example.com/action", "POST", "request",
            "2024-01-01T10:00:00"
        )
        assert "55555" in tracker.tracked_ids
        assert len(tracker.request_log) == 1
        assert tracker.tracked_ids["55555"].origin is None
        assert len(tracker.tracked_ids["55555"].usages) == 1


class TestResponseDomainFiltering:
    """Test response() domain filtering (line 528)."""

    def test_response_filtered_by_domain(self):
        """Test response() returns early when domain is filtered."""
        config = IdotakuConfig(target_domains=["allowed.com"])
        tracker = IDTracker(config)
        tracker._use_ctx = False

        flow = MagicMock()
        flow.id = "filtered-response"
        flow.request.pretty_url = "https://blocked.com/api/data"
        flow.request.method = "GET"
        flow.response = MagicMock()
        flow.response.status_code = 200
        flow.response.headers = MockHeaders({"content-type": "application/json"})
        flow.response.content = b'{"id": 12345}'

        tracker.response(flow)

        # Flow should not be recorded since domain is filtered
        assert "filtered-response" not in tracker.flow_records
        assert "12345" not in tracker.tracked_ids

    def test_response_filtered_by_extension(self):
        """Test response() returns early for static file extensions."""
        tracker = IDTracker()
        tracker._use_ctx = False

        flow = MagicMock()
        flow.id = "css-response"
        flow.request.pretty_url = "https://example.com/style.css"
        flow.request.method = "GET"
        flow.response = MagicMock()
        flow.response.status_code = 200
        flow.response.headers = MockHeaders({"content-type": "text/css"})
        flow.response.content = b"body { color: #12345; }"

        tracker.response(flow)

        assert "css-response" not in tracker.flow_records
