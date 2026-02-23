"""Tests for coverage improvement - sequence, lifeline, csv, banner, verify helpers."""
import json
import os
import pytest
from click.testing import CliRunner
from idotaku.cli import main
from idotaku.banner import print_banner


@pytest.fixture
def runner():
    return CliRunner()


# ===== Banner tests =====

class TestBannerCoverage:
    """Test banner.py uncovered paths."""

    def test_print_banner_no_console(self):
        """Test print_banner when called without console."""
        # Should create its own Console and not raise
        print_banner()

    def test_print_banner_no_version(self):
        """Test print_banner with show_version=False."""
        from rich.console import Console
        from io import StringIO
        buf = StringIO()
        c = Console(file=buf)
        print_banner(c, show_version=False)
        output = buf.getvalue()
        # Banner ASCII art should be present
        assert "__" in output
        # Version string should NOT be present
        assert "IDOR detection tool" not in output


# ===== Sequence tests =====

class TestSequenceCoverage:
    """Test sequence.py uncovered paths."""

    def test_sequence_empty_flows(self, runner, tmp_path):
        """Test sequence with empty flows."""
        data = {
            "summary": {"total_unique_ids": 0, "ids_with_origin": 0, "ids_with_usage": 0, "total_flows": 0},
            "tracked_ids": {},
            "flows": [],
            "potential_idor": [],
        }
        report = tmp_path / "empty.json"
        report.write_text(json.dumps(data), encoding="utf-8")
        result = runner.invoke(main, ["sequence", str(report)])
        assert result.exit_code == 0
        assert "No flows" in result.output

    def test_sequence_with_empty_id_values(self, runner, tmp_path):
        """Test sequence with flows that have empty ID values."""
        data = {
            "summary": {"total_unique_ids": 1, "ids_with_origin": 0, "ids_with_usage": 0, "total_flows": 2},
            "tracked_ids": {},
            "flows": [
                {"method": "POST", "url": "https://api.example.com/users", "timestamp": "2024-01-01T10:00:00",
                 "request_ids": [{"value": "", "type": "numeric", "location": "body"}],
                 "response_ids": [{"value": "", "type": "numeric", "location": "body"}]},
                {"method": "GET", "url": "https://api.example.com/items", "timestamp": "2024-01-01T10:01:00",
                 "request_ids": [{"value": "123", "type": "numeric", "location": "path"}],
                 "response_ids": [{"value": "456", "type": "numeric", "location": "body", "field": "id"}]},
            ],
            "potential_idor": [],
        }
        report = tmp_path / "empty_ids.json"
        report.write_text(json.dumps(data), encoding="utf-8")
        result = runner.invoke(main, ["sequence", str(report)])
        assert result.exit_code == 0

    def test_sequence_html_export(self, runner, tmp_path):
        """Test sequence with HTML export."""
        data = {
            "summary": {"total_unique_ids": 1, "ids_with_origin": 1, "ids_with_usage": 1, "total_flows": 2},
            "tracked_ids": {"123": {"type": "numeric", "first_seen": "t1", "origin": None, "usages": []}},
            "flows": [
                {"method": "POST", "url": "https://api.example.com/users", "timestamp": "2024-01-01T10:00:00",
                 "request_ids": [],
                 "response_ids": [{"value": "123", "type": "numeric", "location": "body", "field": "id"}]},
                {"method": "GET", "url": "https://api.example.com/users/123", "timestamp": "2024-01-01T10:01:00",
                 "request_ids": [{"value": "123", "type": "numeric", "location": "path"}],
                 "response_ids": []},
            ],
            "potential_idor": [],
        }
        report = tmp_path / "seq.json"
        report.write_text(json.dumps(data), encoding="utf-8")
        html_out = tmp_path / "sequence.html"
        result = runner.invoke(main, ["sequence", str(report), "--html", str(html_out)])
        assert result.exit_code == 0
        assert html_out.exists()

    def test_sequence_many_ids_truncation(self, runner, tmp_path):
        """Test sequence with >5 IDs (shows +N more)."""
        many_ids = [{"value": str(i * 1000), "type": "numeric", "location": "body", "field": f"id{i}"} for i in range(1, 8)]
        data = {
            "summary": {"total_unique_ids": 7, "ids_with_origin": 7, "ids_with_usage": 0, "total_flows": 1},
            "tracked_ids": {},
            "flows": [
                {"method": "POST", "url": "https://api.example.com/batch", "timestamp": "2024-01-01T10:00:00",
                 "request_ids": many_ids,
                 "response_ids": many_ids},
            ],
            "potential_idor": [],
        }
        report = tmp_path / "many_ids.json"
        report.write_text(json.dumps(data), encoding="utf-8")
        result = runner.invoke(main, ["sequence", str(report)])
        assert result.exit_code == 0
        assert "more" in result.output


# ===== Lifeline tests =====

class TestLifelineCoverage:
    """Test lifeline.py uncovered paths."""

    def test_lifeline_empty_flows(self, runner, tmp_path):
        """Test lifeline with empty flows."""
        data = {
            "summary": {"total_unique_ids": 0, "ids_with_origin": 0, "ids_with_usage": 0, "total_flows": 0},
            "tracked_ids": {},
            "flows": [],
            "potential_idor": [],
        }
        report = tmp_path / "empty.json"
        report.write_text(json.dumps(data), encoding="utf-8")
        result = runner.invoke(main, ["lifeline", str(report)])
        assert result.exit_code == 0
        assert "No flows" in result.output

    def test_lifeline_with_empty_id_values(self, runner, tmp_path):
        """Test lifeline with empty ID values in flows."""
        data = {
            "summary": {"total_unique_ids": 1, "ids_with_origin": 0, "ids_with_usage": 0, "total_flows": 2},
            "tracked_ids": {},
            "flows": [
                {"method": "POST", "url": "https://api.example.com/test", "timestamp": "2024-01-01T10:00:00",
                 "request_ids": [{"value": "", "type": "numeric", "location": "body"}],
                 "response_ids": [{"value": "", "type": "numeric", "location": "body"}]},
                {"method": "GET", "url": "https://api.example.com/test2", "timestamp": "2024-01-01T10:01:00",
                 "request_ids": [{"value": "123", "type": "numeric", "location": "path"}],
                 "response_ids": [{"value": "123", "type": "numeric", "location": "body", "field": "id"}]},
            ],
            "potential_idor": [],
        }
        report = tmp_path / "empty_ids.json"
        report.write_text(json.dumps(data), encoding="utf-8")
        result = runner.invoke(main, ["lifeline", str(report)])
        assert result.exit_code == 0


# ===== CSV tests =====

class TestCsvCoverage:
    """Test csv_cmd.py uncovered paths."""

    def test_csv_default_output(self, runner, tmp_path):
        """Test csv command without -o flag (uses default output name)."""
        data = {
            "summary": {"total_unique_ids": 1, "ids_with_origin": 0, "ids_with_usage": 1, "total_flows": 1},
            "tracked_ids": {},
            "flows": [{"method": "GET", "url": "https://api.example.com/items/999", "timestamp": "t1",
                       "request_ids": [{"value": "999", "type": "numeric", "location": "path"}],
                       "response_ids": []}],
            "potential_idor": [{"id_value": "999", "id_type": "numeric", "reason": "test",
                               "usages": [{"method": "GET", "url": "https://api.example.com/items/999", "location": "path"}]}],
        }
        report = tmp_path / "report.json"
        report.write_text(json.dumps(data), encoding="utf-8")

        # Run from tmp_path so default file goes there
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(main, ["csv", str(report)])
            assert result.exit_code == 0
            assert "CSV exported" in result.output
            # Default output should be idotaku_idor.csv
            assert (tmp_path / "idotaku_idor.csv").exists()
        finally:
            os.chdir(original_cwd)


# ===== Verify helper tests =====

class TestVerifyHelpers:
    """Test verify_cmd.py internal helper functions."""

    def test_build_original_response_no_match(self):
        """Test _build_original_response when no flow matches."""
        from idotaku.commands.verify_cmd import _build_original_response
        finding = {"id_value": "123", "id_type": "numeric"}
        usage = {"url": "https://api.example.com/users/123", "method": "GET"}
        flows = [
            {"url": "https://api.example.com/other", "method": "POST", "status_code": 200},
        ]
        result = _build_original_response(finding, usage, flows)
        assert result is None

    def test_build_original_response_zero_status(self):
        """Test _build_original_response when status_code is 0."""
        from idotaku.commands.verify_cmd import _build_original_response
        finding = {"id_value": "123", "id_type": "numeric"}
        usage = {"url": "https://api.example.com/users/123", "method": "GET"}
        flows = [
            {"url": "https://api.example.com/users/123", "method": "GET", "status_code": 0},
        ]
        result = _build_original_response(finding, usage, flows)
        assert result is None

    def test_build_original_response_success(self):
        """Test _build_original_response with matching flow."""
        from idotaku.commands.verify_cmd import _build_original_response
        finding = {"id_value": "123", "id_type": "numeric"}
        usage = {"url": "https://api.example.com/users/123", "method": "GET"}
        flows = [
            {"url": "https://api.example.com/users/123", "method": "GET",
             "status_code": 200, "response_headers": {"content-type": "application/json"},
             "response_body": '{"id": 123}'},
        ]
        result = _build_original_response(finding, usage, flows)
        assert result is not None
        assert result.status_code == 200

    def test_build_request_from_report_with_flow(self):
        """Test _build_request_from_report finds matching flow."""
        from idotaku.commands.verify_cmd import _build_request_from_report
        finding = {"id_value": "123", "id_type": "numeric"}
        usage = {"url": "https://api.example.com/users/123", "method": "GET"}
        flows = [
            {"url": "https://api.example.com/users/123", "method": "GET",
             "request_headers": {"authorization": "Bearer token"},
             "request_body": None},
        ]
        result = _build_request_from_report(finding, usage, flows)
        assert result.url == "https://api.example.com/users/123"
        assert "authorization" in result.headers

    def test_build_request_from_report_no_matching_flow(self):
        """Test _build_request_from_report without matching flow."""
        from idotaku.commands.verify_cmd import _build_request_from_report
        finding = {"id_value": "123", "id_type": "numeric"}
        usage = {"url": "https://api.example.com/users/123", "method": "GET"}
        flows = []
        result = _build_request_from_report(finding, usage, flows)
        assert result.url == "https://api.example.com/users/123"
        assert result.headers == {}

    def test_set_nested_value_int_preservation(self):
        """Test _set_nested_value preserves int type."""
        from idotaku.commands.verify_cmd import _set_nested_value
        data = {"user": {"id": 123}}
        _set_nested_value(data, "user.id", "123", "456")
        assert data["user"]["id"] == 456
        assert isinstance(data["user"]["id"], int)

    def test_set_nested_value_int_conversion_failure(self):
        """Test _set_nested_value falls back to string when int conversion fails."""
        from idotaku.commands.verify_cmd import _set_nested_value
        data = {"user": {"id": 123}}
        _set_nested_value(data, "user.id", "123", "not_a_number")
        assert data["user"]["id"] == "not_a_number"

    def test_set_nested_value_string_type(self):
        """Test _set_nested_value with string values."""
        from idotaku.commands.verify_cmd import _set_nested_value
        data = {"user": {"name": "old_value"}}
        _set_nested_value(data, "user.name", "old_value", "new_value")
        assert data["user"]["name"] == "new_value"

    def test_set_nested_value_missing_path(self):
        """Test _set_nested_value with non-existent path."""
        from idotaku.commands.verify_cmd import _set_nested_value
        data = {"user": {"id": 123}}
        _set_nested_value(data, "nonexistent.path", "123", "456")
        # Should not modify data
        assert data["user"]["id"] == 123

    def test_set_nested_value_missing_final_key(self):
        """Test _set_nested_value with non-existent final key."""
        from idotaku.commands.verify_cmd import _set_nested_value
        data = {"user": {"id": 123}}
        _set_nested_value(data, "user.missing_key", "123", "456")
        # Should not modify data and should not add the key
        assert "missing_key" not in data["user"]

    def test_set_nested_value_flat_key(self):
        """Test _set_nested_value with a single-level key (no dots)."""
        from idotaku.commands.verify_cmd import _set_nested_value
        data = {"id": "123"}
        _set_nested_value(data, "id", "123", "456")
        assert data["id"] == "456"

    def test_find_header_key_case_insensitive(self):
        """Test _find_header_key with case insensitive matching."""
        from idotaku.commands.verify_cmd import _find_header_key
        headers = {"Authorization": "Bearer token", "Content-Type": "application/json"}
        assert _find_header_key(headers, "authorization") == "Authorization"
        assert _find_header_key(headers, "AUTHORIZATION") == "Authorization"

    def test_find_header_key_with_colon_format(self):
        """Test _find_header_key with cookie:session_id format."""
        from idotaku.commands.verify_cmd import _find_header_key
        headers = {"Cookie": "session=abc123"}
        assert _find_header_key(headers, "cookie:session") == "Cookie"

    def test_find_header_key_not_found(self):
        """Test _find_header_key returns None when not found."""
        from idotaku.commands.verify_cmd import _find_header_key
        headers = {"Authorization": "Bearer token"}
        assert _find_header_key(headers, "x-custom") is None

    def test_replace_in_json_valid(self):
        """Test _replace_in_json with valid JSON and field_name."""
        from idotaku.commands.verify_cmd import _replace_in_json
        body = '{"user_id": "123", "name": "test"}'
        result = _replace_in_json(body, "123", "456", "user_id")
        assert "456" in result

    def test_replace_in_json_invalid_json(self):
        """Test _replace_in_json with invalid JSON fallback."""
        from idotaku.commands.verify_cmd import _replace_in_json
        body = "not json content with 123"
        result = _replace_in_json(body, "123", "456", None)
        assert "456" in result

    def test_replace_in_json_no_field_name(self):
        """Test _replace_in_json without field_name does string replace."""
        from idotaku.commands.verify_cmd import _replace_in_json
        body = '{"id": "123"}'
        result = _replace_in_json(body, "123", "456", None)
        assert "456" in result

    def test_replace_in_json_invalid_json_with_field_name(self):
        """Test _replace_in_json with invalid JSON and field_name falls back to string replace."""
        from idotaku.commands.verify_cmd import _replace_in_json
        body = "user_id=123&other=test"
        result = _replace_in_json(body, "123", "456", "user_id")
        assert "456" in result

    def test_apply_modification_url_path(self):
        """Test _apply_modification for url_path location."""
        from idotaku.commands.verify_cmd import _apply_modification
        from idotaku.verify import RequestData, Modification
        request = RequestData(method="GET", url="https://api.example.com/users/123", headers={}, body=None)
        mod = Modification(original_value="123", modified_value="456", location="url_path", field_name=None, description="test")
        result = _apply_modification(request, mod)
        assert "456" in result.url
        assert "123" not in result.url

    def test_apply_modification_query(self):
        """Test _apply_modification for query location with field_name."""
        from idotaku.commands.verify_cmd import _apply_modification
        from idotaku.verify import RequestData, Modification
        request = RequestData(method="GET", url="https://api.example.com/search?user_id=123", headers={}, body=None)
        mod = Modification(original_value="123", modified_value="456", location="query", field_name="user_id", description="test")
        result = _apply_modification(request, mod)
        assert "456" in result.url

    def test_apply_modification_query_no_field(self):
        """Test _apply_modification for query without field name (fallback replace)."""
        from idotaku.commands.verify_cmd import _apply_modification
        from idotaku.verify import RequestData, Modification
        request = RequestData(method="GET", url="https://api.example.com/search?id=123", headers={}, body=None)
        mod = Modification(original_value="123", modified_value="456", location="query", field_name=None, description="test")
        result = _apply_modification(request, mod)
        assert "456" in result.url

    def test_apply_modification_body_json(self):
        """Test _apply_modification for JSON body."""
        from idotaku.commands.verify_cmd import _apply_modification
        from idotaku.verify import RequestData, Modification
        request = RequestData(method="POST", url="https://api.example.com/users",
                            headers={"Content-Type": "application/json"},
                            body='{"user_id": "123"}')
        mod = Modification(original_value="123", modified_value="456", location="body", field_name="user_id", description="test")
        result = _apply_modification(request, mod)
        assert "456" in result.body

    def test_apply_modification_body_text(self):
        """Test _apply_modification for non-JSON body."""
        from idotaku.commands.verify_cmd import _apply_modification
        from idotaku.verify import RequestData, Modification
        request = RequestData(method="POST", url="https://api.example.com/users",
                            headers={"Content-Type": "application/x-www-form-urlencoded"},
                            body="user_id=123&name=test")
        mod = Modification(original_value="123", modified_value="456", location="body", field_name=None, description="test")
        result = _apply_modification(request, mod)
        assert "456" in result.body

    def test_apply_modification_body_none(self):
        """Test _apply_modification for body location with no body."""
        from idotaku.commands.verify_cmd import _apply_modification
        from idotaku.verify import RequestData, Modification
        request = RequestData(method="POST", url="https://api.example.com/users",
                            headers={}, body=None)
        mod = Modification(original_value="123", modified_value="456", location="body", field_name=None, description="test")
        result = _apply_modification(request, mod)
        assert result.body is None

    def test_apply_modification_header(self):
        """Test _apply_modification for header location."""
        from idotaku.commands.verify_cmd import _apply_modification
        from idotaku.verify import RequestData, Modification
        request = RequestData(method="GET", url="https://api.example.com/users",
                            headers={"Cookie": "session=abc123"},
                            body=None)
        mod = Modification(original_value="abc123", modified_value="xyz789", location="header", field_name="cookie:session", description="test")
        result = _apply_modification(request, mod)
        assert "xyz789" in result.headers["Cookie"]

    def test_apply_modification_header_no_field(self):
        """Test _apply_modification for header location without field_name."""
        from idotaku.commands.verify_cmd import _apply_modification
        from idotaku.verify import RequestData, Modification
        request = RequestData(method="GET", url="https://api.example.com/users",
                            headers={"Cookie": "session=abc123"},
                            body=None)
        mod = Modification(original_value="abc123", modified_value="xyz789", location="header", field_name=None, description="test")
        result = _apply_modification(request, mod)
        # Without field_name, header modification should not apply
        assert "abc123" in result.headers["Cookie"]

    def test_apply_modification_body_content_type_lowercase(self):
        """Test _apply_modification for JSON body with lowercase content-type header."""
        from idotaku.commands.verify_cmd import _apply_modification
        from idotaku.verify import RequestData, Modification
        request = RequestData(method="POST", url="https://api.example.com/users",
                            headers={"content-type": "application/json"},
                            body='{"user_id": "123"}')
        mod = Modification(original_value="123", modified_value="456", location="body", field_name="user_id", description="test")
        result = _apply_modification(request, mod)
        assert "456" in result.body

    def test_display_legal_warning(self):
        """Test _display_legal_warning runs without error."""
        from idotaku.commands.verify_cmd import _display_legal_warning
        _display_legal_warning()

    def test_display_request(self):
        """Test _display_request runs without error."""
        from idotaku.commands.verify_cmd import _display_request
        from idotaku.verify import RequestData
        req = RequestData(method="GET", url="https://api.example.com/test",
                        headers={"Authorization": "Bearer token"}, body='{"key": "value"}')
        _display_request(req, "Test Request")

    def test_display_request_no_body_no_headers(self):
        """Test _display_request with no body and no headers."""
        from idotaku.commands.verify_cmd import _display_request
        from idotaku.verify import RequestData
        req = RequestData(method="GET", url="https://api.example.com/test",
                        headers={}, body=None)
        _display_request(req, "Minimal Request")

    def test_display_request_many_headers(self):
        """Test _display_request with more than 10 headers."""
        from idotaku.commands.verify_cmd import _display_request
        from idotaku.verify import RequestData
        headers = {f"X-Header-{i}": f"value-{i}" for i in range(15)}
        req = RequestData(method="GET", url="https://api.example.com/test",
                        headers=headers, body=None)
        _display_request(req, "Many Headers Request")

    def test_display_response(self):
        """Test _display_response runs without error."""
        from idotaku.commands.verify_cmd import _display_response
        from idotaku.verify import ResponseData
        resp = ResponseData(status_code=200, headers={}, body='{"result": "ok"}', content_length=16)
        _display_response(resp)

    def test_display_response_error_status(self):
        """Test _display_response with error status code."""
        from idotaku.commands.verify_cmd import _display_response
        from idotaku.verify import ResponseData
        resp = ResponseData(status_code=403, headers={}, body='{"error": "forbidden"}', content_length=22)
        _display_response(resp)

    def test_display_response_no_body(self):
        """Test _display_response with empty body."""
        from idotaku.commands.verify_cmd import _display_response
        from idotaku.verify import ResponseData
        resp = ResponseData(status_code=204, headers={}, body="", content_length=0)
        _display_response(resp)

    def test_display_comparison(self):
        """Test _display_comparison runs without error."""
        from idotaku.commands.verify_cmd import _display_comparison
        from idotaku.verify import ComparisonResult
        comp = ComparisonResult(
            status_match=True,
            status_original=200,
            status_modified=200,
            content_length_diff=0,
            verdict="VULNERABLE",
            details=["Status codes match", "Body differs"],
        )
        _display_comparison(comp)

    def test_display_comparison_not_vulnerable(self):
        """Test _display_comparison with NOT_VULNERABLE verdict."""
        from idotaku.commands.verify_cmd import _display_comparison
        from idotaku.verify import ComparisonResult
        comp = ComparisonResult(
            status_match=False,
            status_original=200,
            status_modified=403,
            content_length_diff=-500,
            verdict="NOT_VULNERABLE",
            details=["Status codes differ", "Access denied"],
        )
        _display_comparison(comp)

    def test_prompt_select_usage_no_usages(self):
        """Test _prompt_select_usage with no usages."""
        from idotaku.commands.verify_cmd import _prompt_select_usage
        finding = {"usages": []}
        result = _prompt_select_usage(finding)
        assert result is None

    def test_prompt_select_usage_single(self):
        """Test _prompt_select_usage with single usage returns it directly."""
        from idotaku.commands.verify_cmd import _prompt_select_usage
        usage = {"method": "GET", "url": "https://api.example.com/test", "location": "path"}
        finding = {"usages": [usage]}
        result = _prompt_select_usage(finding)
        assert result == usage
