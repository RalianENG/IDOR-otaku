"""Tests for IDOR verification feature."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from idotaku.verify.models import (
    ComparisonResult,
    Modification,
    RequestData,
    ResponseData,
    SuggestedValue,
    VerifyResult,
)
from idotaku.verify.suggestions import CUSTOM_INPUT, suggest_modifications
from idotaku.verify.comparison import compare_responses
from idotaku.verify.http_client import VerifyHttpClient
from idotaku.commands.verify_cmd import (
    _apply_modification,
    _replace_in_json,
    _set_nested_value,
    _build_request_from_report,
    _build_original_response,
    _find_header_key,
    _display_legal_warning,
    _display_request,
    _display_response,
    _display_comparison,
    _display_summary,
    _save_results,
    _result_to_dict,
)


# --- TestSuggestions ---


class TestSuggestions:
    """Test parameter modification suggestions."""

    def test_numeric_suggestions(self) -> None:
        result = suggest_modifications("1000", "numeric")
        values = [s.value for s in result]
        assert "1001" in values  # +1
        assert "999" in values   # -1
        assert "1010" in values  # +10
        assert "0" in values     # zero
        assert "1" in values     # admin
        assert "-1" in values    # negative

    def test_numeric_invalid_value(self) -> None:
        result = suggest_modifications("not_a_number", "numeric")
        # Should still have universal suggestions
        assert any(s.value == "" for s in result)
        assert any(s.value == CUSTOM_INPUT for s in result)

    def test_uuid_suggestions(self) -> None:
        result = suggest_modifications(
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "uuid"
        )
        values = [s.value for s in result]
        assert "00000000-0000-0000-0000-000000000000" in values
        # Should have a random UUID
        assert any(
            len(v) == 36 and v.count("-") == 4
            for v in values
            if v != "00000000-0000-0000-0000-000000000000"
        )

    def test_token_suggestions(self) -> None:
        token = "abc123def456"
        result = suggest_modifications(token, "token")
        values = [s.value for s in result]
        assert "invalid_token" in values
        assert "a" * len(token) in values

    def test_custom_input_always_present(self) -> None:
        for id_type in ("numeric", "uuid", "token", "unknown"):
            result = suggest_modifications("test", id_type)
            assert any(s.value == CUSTOM_INPUT for s in result)

    def test_empty_string_always_present(self) -> None:
        for id_type in ("numeric", "uuid", "token"):
            result = suggest_modifications("test", id_type)
            assert any(s.value == "" for s in result)


# --- TestComparison ---


class TestComparison:
    """Test response comparison logic."""

    def test_same_status_same_length_vulnerable(self) -> None:
        original = ResponseData(status_code=200, content_length=1000)
        modified = ResponseData(status_code=200, content_length=1010)
        result = compare_responses(modified, original)
        assert result.verdict == "VULNERABLE"
        assert result.status_match is True

    def test_same_status_different_length_likely(self) -> None:
        original = ResponseData(status_code=200, content_length=1000)
        modified = ResponseData(status_code=200, content_length=2000)
        result = compare_responses(modified, original)
        assert result.verdict == "LIKELY_VULNERABLE"

    def test_403_not_vulnerable(self) -> None:
        original = ResponseData(status_code=200, content_length=1000)
        modified = ResponseData(status_code=403, content_length=50)
        result = compare_responses(modified, original)
        assert result.verdict == "NOT_VULNERABLE"

    def test_401_not_vulnerable(self) -> None:
        original = ResponseData(status_code=200, content_length=1000)
        modified = ResponseData(status_code=401, content_length=50)
        result = compare_responses(modified, original)
        assert result.verdict == "NOT_VULNERABLE"

    def test_404_inconclusive(self) -> None:
        original = ResponseData(status_code=200, content_length=1000)
        modified = ResponseData(status_code=404, content_length=50)
        result = compare_responses(modified, original)
        assert result.verdict == "INCONCLUSIVE"

    def test_standalone_200_likely(self) -> None:
        modified = ResponseData(status_code=200, content_length=1000)
        result = compare_responses(modified)
        assert result.verdict == "LIKELY_VULNERABLE"
        assert result.status_original is None

    def test_standalone_403_not_vulnerable(self) -> None:
        modified = ResponseData(status_code=403, content_length=50)
        result = compare_responses(modified)
        assert result.verdict == "NOT_VULNERABLE"

    def test_standalone_500_inconclusive(self) -> None:
        modified = ResponseData(status_code=500, content_length=50)
        result = compare_responses(modified)
        assert result.verdict == "INCONCLUSIVE"

    def test_content_length_diff_calculated(self) -> None:
        original = ResponseData(status_code=200, content_length=100)
        modified = ResponseData(status_code=200, content_length=150)
        result = compare_responses(modified, original)
        assert result.content_length_diff == 50

    def test_details_populated(self) -> None:
        modified = ResponseData(status_code=200, content_length=100)
        result = compare_responses(modified)
        assert len(result.details) > 0


# --- TestHttpClient ---


class TestHttpClient:
    """Test HTTP client (with mocked httpx)."""

    @patch("idotaku.verify.http_client.httpx.Client")
    def test_send_get_request(self, mock_client_cls: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"id": 1}'
        mock_response.content = b'{"id": 1}'

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client = VerifyHttpClient(timeout=10.0)
        request = RequestData(method="GET", url="https://api.example.com/users/1")
        response = client.send(request)

        assert response.status_code == 200
        assert response.content_length == 9
        mock_client.request.assert_called_once()

    @patch("idotaku.verify.http_client.httpx.Client")
    def test_send_post_with_body(self, mock_client_cls: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {}
        mock_response.text = "{}"
        mock_response.content = b"{}"

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client = VerifyHttpClient()
        request = RequestData(
            method="POST",
            url="https://api.example.com/users",
            headers={"Content-Type": "application/json"},
            body='{"name": "test"}',
        )
        response = client.send(request)

        assert response.status_code == 201
        call_kwargs = mock_client.request.call_args
        assert call_kwargs.kwargs.get("content") == '{"name": "test"}'

    @patch("idotaku.verify.http_client.httpx.Client")
    def test_ssl_disabled(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = ""
        mock_response.content = b""
        mock_client.request.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client = VerifyHttpClient(verify_ssl=False)
        client.send(RequestData(method="GET", url="https://example.com"))

        mock_client_cls.assert_called_once_with(
            timeout=30.0,
            verify=False,
            proxy=None,
            follow_redirects=False,
        )

    @patch("idotaku.verify.http_client.httpx.Client")
    def test_proxy_configuration(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = ""
        mock_response.content = b""
        mock_client.request.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client = VerifyHttpClient(proxy="http://127.0.0.1:8080")
        client.send(RequestData(method="GET", url="https://example.com"))

        mock_client_cls.assert_called_once_with(
            timeout=30.0,
            verify=True,
            proxy="http://127.0.0.1:8080",
            follow_redirects=False,
        )


# --- TestApplyModification ---


class TestApplyModification:
    """Test request modification application."""

    def test_url_path_replacement(self) -> None:
        request = RequestData(
            method="GET",
            url="https://api.example.com/users/12345/profile",
        )
        mod = Modification(
            original_value="12345",
            modified_value="12346",
            location="url_path",
            field_name=None,
            description="Original + 1",
        )
        result = _apply_modification(request, mod)
        assert "12346" in result.url
        assert "12345" not in result.url

    def test_query_param_replacement(self) -> None:
        request = RequestData(
            method="GET",
            url="https://api.example.com/search?user_id=12345&page=1",
        )
        mod = Modification(
            original_value="12345",
            modified_value="12346",
            location="query",
            field_name="user_id",
            description="Original + 1",
        )
        result = _apply_modification(request, mod)
        assert "user_id=12346" in result.url
        assert "page=1" in result.url

    def test_json_body_replacement(self) -> None:
        request = RequestData(
            method="POST",
            url="https://api.example.com/action",
            headers={"Content-Type": "application/json"},
            body='{"user_id": 12345, "action": "test"}',
        )
        mod = Modification(
            original_value="12345",
            modified_value="12346",
            location="body",
            field_name="user_id",
            description="Original + 1",
        )
        result = _apply_modification(request, mod)
        body = json.loads(result.body)
        assert body["user_id"] == 12346
        assert body["action"] == "test"

    def test_header_value_replacement(self) -> None:
        request = RequestData(
            method="GET",
            url="https://api.example.com/data",
            headers={"X-User-Id": "12345"},
        )
        mod = Modification(
            original_value="12345",
            modified_value="12346",
            location="header",
            field_name="x-user-id",
            description="Original + 1",
        )
        result = _apply_modification(request, mod)
        assert result.headers["X-User-Id"] == "12346"

    def test_does_not_mutate_original(self) -> None:
        request = RequestData(
            method="GET",
            url="https://api.example.com/users/12345",
            headers={"Authorization": "Bearer token"},
        )
        mod = Modification(
            original_value="12345",
            modified_value="12346",
            location="url_path",
            field_name=None,
            description="test",
        )
        result = _apply_modification(request, mod)
        assert "12345" in request.url
        assert "12346" in result.url


# --- TestReplaceInJson ---


class TestReplaceInJson:
    """Test JSON body replacement."""

    def test_simple_field(self) -> None:
        body = '{"id": "12345"}'
        result = _replace_in_json(body, "12345", "12346", "id")
        data = json.loads(result)
        assert data["id"] == "12346"

    def test_nested_field(self) -> None:
        body = '{"data": {"user": {"id": "12345"}}}'
        result = _replace_in_json(body, "12345", "12346", "data.user.id")
        data = json.loads(result)
        assert data["data"]["user"]["id"] == "12346"

    def test_numeric_type_preserved(self) -> None:
        body = '{"id": 12345}'
        result = _replace_in_json(body, "12345", "12346", "id")
        data = json.loads(result)
        assert data["id"] == 12346
        assert isinstance(data["id"], int)

    def test_invalid_json_fallback(self) -> None:
        body = "not json {id: 12345}"
        result = _replace_in_json(body, "12345", "12346", "id")
        assert "12346" in result

    def test_no_field_name_string_replace(self) -> None:
        body = '{"id": "12345"}'
        result = _replace_in_json(body, "12345", "12346", None)
        assert "12346" in result


# --- TestBuildFromReport ---


class TestBuildFromReport:
    """Test building request/response from report data."""

    def test_build_request_with_full_data(self) -> None:
        finding = {"id_value": "12345", "id_type": "numeric"}
        usage = {
            "url": "https://api.example.com/users/12345",
            "method": "GET",
        }
        flows = [
            {
                "url": "https://api.example.com/users/12345",
                "method": "GET",
                "request_headers": {"Authorization": "Bearer token123"},
                "request_body": None,
            }
        ]
        result = _build_request_from_report(finding, usage, flows)
        assert result.method == "GET"
        assert result.url == "https://api.example.com/users/12345"
        assert result.headers.get("Authorization") == "Bearer token123"

    def test_build_request_no_matching_flow(self) -> None:
        finding = {"id_value": "12345", "id_type": "numeric"}
        usage = {
            "url": "https://api.example.com/other",
            "method": "GET",
        }
        flows = [
            {
                "url": "https://api.example.com/users/12345",
                "method": "GET",
            }
        ]
        result = _build_request_from_report(finding, usage, flows)
        assert result.headers == {}

    def test_build_original_response(self) -> None:
        finding = {"id_value": "12345", "id_type": "numeric"}
        usage = {
            "url": "https://api.example.com/users/12345",
            "method": "GET",
        }
        flows = [
            {
                "url": "https://api.example.com/users/12345",
                "method": "GET",
                "status_code": 200,
                "response_headers": {"content-type": "application/json"},
                "response_body": '{"id": 12345}',
            }
        ]
        result = _build_original_response(finding, usage, flows)
        assert result is not None
        assert result.status_code == 200
        assert result.content_length == 13

    def test_build_original_response_no_status(self) -> None:
        """Old format report without status_code should return None."""
        finding = {"id_value": "12345", "id_type": "numeric"}
        usage = {
            "url": "https://api.example.com/users/12345",
            "method": "GET",
        }
        flows = [
            {
                "url": "https://api.example.com/users/12345",
                "method": "GET",
            }
        ]
        result = _build_original_response(finding, usage, flows)
        assert result is None


# --- TestVerifyCommand ---


class TestVerifyCommand:
    """Test the verify CLI command."""

    def test_verify_help(self) -> None:
        from idotaku.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["verify", "--help"])
        assert result.exit_code == 0
        assert "Verify IDOR candidates" in result.output

    def test_verify_no_findings(self, tmp_path: pytest.TempPathFactory) -> None:
        from idotaku.cli import main
        report = {
            "summary": {"total_unique_ids": 0, "ids_with_origin": 0,
                        "ids_with_usage": 0, "total_flows": 0},
            "tracked_ids": {},
            "flows": [],
            "potential_idor": [],
        }
        report_file = tmp_path / "empty.json"  # type: ignore[operator]
        report_file.write_text(json.dumps(report))

        runner = CliRunner()
        result = runner.invoke(main, ["verify", str(report_file)])
        assert result.exit_code == 0
        assert "No IDOR candidates" in result.output

    def test_verify_min_score_filter(self, tmp_path: pytest.TempPathFactory) -> None:
        from idotaku.cli import main
        report = {
            "summary": {"total_unique_ids": 1, "ids_with_origin": 0,
                        "ids_with_usage": 1, "total_flows": 1},
            "tracked_ids": {},
            "flows": [],
            "potential_idor": [
                {
                    "id_value": "12345",
                    "id_type": "numeric",
                    "usages": [{
                        "url": "https://example.com/users/12345",
                        "method": "GET",
                        "location": "url_path",
                        "field_name": None,
                        "timestamp": "2024-01-01T00:00:00",
                    }],
                    "reason": "test",
                },
            ],
        }
        report_file = tmp_path / "report.json"  # type: ignore[operator]
        report_file.write_text(json.dumps(report))

        runner = CliRunner()
        # Score for this finding would be low (GET=5 + url_path=20 + numeric=15 = 40)
        result = runner.invoke(main, ["verify", str(report_file), "--min-score", "99"])
        assert result.exit_code == 0
        assert "No findings match" in result.output

    def test_verify_level_filter(self, tmp_path: pytest.TempPathFactory) -> None:
        from idotaku.cli import main
        report = {
            "summary": {"total_unique_ids": 1, "ids_with_origin": 0,
                        "ids_with_usage": 1, "total_flows": 1},
            "tracked_ids": {},
            "flows": [],
            "potential_idor": [
                {
                    "id_value": "12345",
                    "id_type": "numeric",
                    "usages": [{
                        "url": "https://example.com/users/12345",
                        "method": "GET",
                        "location": "url_path",
                        "field_name": None,
                        "timestamp": "2024-01-01T00:00:00",
                    }],
                    "reason": "test",
                },
            ],
        }
        report_file = tmp_path / "report.json"  # type: ignore[operator]
        report_file.write_text(json.dumps(report))

        runner = CliRunner()
        result = runner.invoke(
            main, ["verify", str(report_file), "--level", "critical"]
        )
        assert result.exit_code == 0
        assert "No findings match" in result.output

    @patch("idotaku.commands.verify_cmd.questionary")
    def test_verify_auth_denied(
        self, mock_q: MagicMock, tmp_path: pytest.TempPathFactory,
    ) -> None:
        from idotaku.cli import main
        report = {
            "summary": {"total_unique_ids": 1, "ids_with_origin": 0,
                        "ids_with_usage": 1, "total_flows": 1},
            "tracked_ids": {},
            "flows": [],
            "potential_idor": [
                {
                    "id_value": "12345",
                    "id_type": "numeric",
                    "usages": [{
                        "url": "https://example.com/users/12345",
                        "method": "GET",
                        "location": "url_path",
                        "field_name": None,
                        "timestamp": "2024-01-01T00:00:00",
                    }],
                    "reason": "test",
                },
            ],
        }
        report_file = tmp_path / "report.json"  # type: ignore[operator]
        report_file.write_text(json.dumps(report))

        mock_q.confirm.return_value.ask.return_value = False
        runner = CliRunner()
        result = runner.invoke(main, ["verify", str(report_file)])
        assert result.exit_code == 0
        assert "Aborted" in result.output

    @patch("idotaku.commands.verify_cmd.questionary")
    def test_verify_full_flow_quit_immediately(
        self, mock_q: MagicMock, tmp_path: pytest.TempPathFactory,
    ) -> None:
        from idotaku.cli import main
        report = {
            "summary": {"total_unique_ids": 1, "ids_with_origin": 0,
                        "ids_with_usage": 1, "total_flows": 1},
            "tracked_ids": {},
            "flows": [{
                "url": "https://example.com/users/12345",
                "method": "GET",
                "flow_id": "f1",
                "timestamp": "2024-01-01T00:00:00",
                "request_ids": [],
                "response_ids": [],
                "request_headers": {"Authorization": "Bearer tok"},
                "request_body": None,
                "status_code": 200,
                "response_headers": {},
                "response_body": '{"id": 12345}',
            }],
            "potential_idor": [{
                "id_value": "12345",
                "id_type": "numeric",
                "usages": [{
                    "url": "https://example.com/users/12345",
                    "method": "GET",
                    "location": "url_path",
                    "field_name": None,
                    "timestamp": "2024-01-01T00:00:00",
                }],
                "reason": "test",
            }],
        }
        report_file = tmp_path / "report.json"  # type: ignore[operator]
        report_file.write_text(json.dumps(report))

        # auth=Yes, then select=__quit__
        mock_q.confirm.return_value.ask.return_value = True
        mock_q.select.return_value.ask.return_value = "__quit__"

        runner = CliRunner()
        result = runner.invoke(main, ["verify", str(report_file), "--no-save"])
        assert result.exit_code == 0

    @patch("idotaku.commands.verify_cmd.VerifyHttpClient")
    @patch("idotaku.commands.verify_cmd.questionary")
    def test_verify_full_flow_send_request(
        self, mock_q: MagicMock, mock_client_cls: MagicMock,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        from idotaku.cli import main
        report = {
            "summary": {"total_unique_ids": 1, "ids_with_origin": 0,
                        "ids_with_usage": 1, "total_flows": 1},
            "tracked_ids": {},
            "flows": [{
                "url": "https://example.com/users/12345",
                "method": "GET",
                "flow_id": "f1",
                "timestamp": "2024-01-01T00:00:00",
                "request_ids": [],
                "response_ids": [],
                "request_headers": {"Authorization": "Bearer tok"},
                "request_body": None,
                "status_code": 200,
                "response_headers": {"content-type": "application/json"},
                "response_body": '{"id": 12345}',
            }],
            "potential_idor": [{
                "id_value": "12345",
                "id_type": "numeric",
                "usages": [{
                    "url": "https://example.com/users/12345",
                    "method": "GET",
                    "location": "url_path",
                    "field_name": None,
                    "timestamp": "2024-01-01T00:00:00",
                }],
                "reason": "test",
            }],
        }
        report_file = tmp_path / "report.json"  # type: ignore[operator]
        report_file.write_text(json.dumps(report))
        output_file = tmp_path / "results.json"  # type: ignore[operator]

        # Mock questionary calls in order:
        # 1. confirm auth -> True
        # 2. select finding -> "0"
        # 3. select modification -> "0" (first suggestion: +1)
        # 4. confirm send -> True
        # 5. confirm continue -> False
        confirm_results = [True, True, False]
        mock_q.confirm.return_value.ask.side_effect = confirm_results
        mock_q.select.return_value.ask.side_effect = ["0", "0"]

        mock_response = ResponseData(
            status_code=200, headers={}, body='{"id": 12346}',
            content_length=13, elapsed_ms=50.0,
        )
        mock_client_cls.return_value.send.return_value = mock_response

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["verify", str(report_file), "-o", str(output_file)],
        )
        assert result.exit_code == 0
        assert output_file.exists()

    @patch("idotaku.commands.verify_cmd.VerifyHttpClient")
    @patch("idotaku.commands.verify_cmd.questionary")
    def test_verify_request_error(
        self, mock_q: MagicMock, mock_client_cls: MagicMock,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        from idotaku.cli import main
        report = {
            "summary": {"total_unique_ids": 1, "ids_with_origin": 0,
                        "ids_with_usage": 1, "total_flows": 1},
            "tracked_ids": {},
            "flows": [{
                "url": "https://example.com/users/12345",
                "method": "GET",
                "flow_id": "f1",
                "timestamp": "2024-01-01T00:00:00",
                "request_ids": [],
                "response_ids": [],
                "request_headers": {},
                "request_body": None,
                "status_code": 200,
                "response_headers": {},
                "response_body": "",
            }],
            "potential_idor": [{
                "id_value": "12345",
                "id_type": "numeric",
                "usages": [{
                    "url": "https://example.com/users/12345",
                    "method": "GET",
                    "location": "url_path",
                    "field_name": None,
                    "timestamp": "2024-01-01T00:00:00",
                }],
                "reason": "test",
            }],
        }
        report_file = tmp_path / "report.json"  # type: ignore[operator]
        report_file.write_text(json.dumps(report))

        # auth=True, send=True; after error loops back -> select quit
        mock_q.confirm.return_value.ask.side_effect = [True, True]
        mock_q.select.return_value.ask.side_effect = ["0", "0", "__quit__"]
        mock_client_cls.return_value.send.side_effect = ConnectionError("timeout")

        runner = CliRunner()
        result = runner.invoke(
            main, ["verify", str(report_file), "--no-save"],
        )
        assert result.exit_code == 0
        assert "Request failed" in result.output


# --- TestComparisonEdgeCases ---


class TestComparisonEdgeCases:
    """Test edge cases for response comparison."""

    def test_different_status_other_with_original(self) -> None:
        """Different status code (not 401/403/404) should be INCONCLUSIVE."""
        original = ResponseData(status_code=200, content_length=1000)
        modified = ResponseData(status_code=302, content_length=0)
        result = compare_responses(modified, original)
        assert result.verdict == "INCONCLUSIVE"
        assert "Different status code" in result.details[-1]

    def test_standalone_404_inconclusive(self) -> None:
        modified = ResponseData(status_code=404, content_length=50)
        result = compare_responses(modified)
        assert result.verdict == "INCONCLUSIVE"
        assert "not found" in result.details[-1].lower()

    def test_standalone_401_not_vulnerable(self) -> None:
        modified = ResponseData(status_code=401, content_length=50)
        result = compare_responses(modified)
        assert result.verdict == "NOT_VULNERABLE"

    def test_standalone_unexpected_status(self) -> None:
        modified = ResponseData(status_code=302, content_length=0)
        result = compare_responses(modified)
        assert result.verdict == "INCONCLUSIVE"
        assert "manual review" in result.details[-1].lower()

    def test_standalone_503_server_error(self) -> None:
        modified = ResponseData(status_code=503, content_length=100)
        result = compare_responses(modified)
        assert result.verdict == "INCONCLUSIVE"
        assert "Server error" in result.details[-1]

    def test_with_original_500_inconclusive(self) -> None:
        original = ResponseData(status_code=200, content_length=1000)
        modified = ResponseData(status_code=500, content_length=100)
        result = compare_responses(modified, original)
        assert result.verdict == "INCONCLUSIVE"


# --- TestFindHeaderKey ---


class TestFindHeaderKey:
    """Test header key lookup."""

    def test_case_insensitive_match(self) -> None:
        headers = {"X-User-Id": "123", "Content-Type": "application/json"}
        assert _find_header_key(headers, "x-user-id") == "X-User-Id"

    def test_with_colon_prefix(self) -> None:
        headers = {"Cookie": "session=abc"}
        assert _find_header_key(headers, "cookie:session_id") == "Cookie"

    def test_no_match(self) -> None:
        headers = {"Authorization": "Bearer token"}
        assert _find_header_key(headers, "x-custom") is None


# --- TestDisplayFunctions ---


class TestDisplayFunctions:
    """Test display helper functions (smoke tests)."""

    def test_display_legal_warning(self) -> None:
        # Should not raise
        _display_legal_warning()

    def test_display_request_minimal(self) -> None:
        req = RequestData(method="GET", url="https://example.com/test")
        _display_request(req, "Test Request")

    def test_display_request_with_headers_and_body(self) -> None:
        headers = {f"Header-{i}": f"value-{i}" for i in range(15)}
        req = RequestData(
            method="POST",
            url="https://example.com/test",
            headers=headers,
            body="x" * 300,
        )
        _display_request(req, "Large Request")

    def test_display_response_success(self) -> None:
        resp = ResponseData(
            status_code=200, content_length=100, elapsed_ms=50.0,
            body='{"result": "ok"}',
        )
        _display_response(resp)

    def test_display_response_error(self) -> None:
        resp = ResponseData(
            status_code=500, content_length=50, elapsed_ms=100.0,
            body="Internal Server Error",
        )
        _display_response(resp)

    def test_display_response_long_body(self) -> None:
        resp = ResponseData(
            status_code=200, content_length=500, elapsed_ms=50.0,
            body="x" * 500,
        )
        _display_response(resp)

    def test_display_comparison(self) -> None:
        comp = ComparisonResult(
            status_match=True, status_original=200, status_modified=200,
            content_length_diff=10, verdict="VULNERABLE",
            details=["Same status", "Similar length"],
        )
        _display_comparison(comp)

    def test_display_comparison_unknown_verdict(self) -> None:
        comp = ComparisonResult(
            status_match=False, status_original=200, status_modified=418,
            content_length_diff=-100, verdict="UNKNOWN_VERDICT",
            details=["Teapot"],
        )
        _display_comparison(comp)

    def test_display_summary(self) -> None:
        results = [
            VerifyResult(
                finding_id_value="12345",
                finding_id_type="numeric",
                original_request=RequestData(method="GET", url="https://example.com/1"),
                modified_request=RequestData(method="GET", url="https://example.com/2"),
                modification=Modification(
                    original_value="1", modified_value="2",
                    location="url_path", field_name=None, description="+1",
                ),
                response=ResponseData(status_code=200, content_length=100),
                original_response=None,
                comparison=ComparisonResult(
                    status_match=False, status_original=None,
                    status_modified=200, content_length_diff=None,
                    verdict="LIKELY_VULNERABLE",
                ),
                timestamp="2024-01-01T00:00:00Z",
            ),
        ]
        _display_summary(results)


# --- TestSaveResults ---


class TestSaveResults:
    """Test result saving."""

    def test_save_and_load_results(self, tmp_path: pytest.TempPathFactory) -> None:
        results = [
            VerifyResult(
                finding_id_value="12345",
                finding_id_type="numeric",
                original_request=RequestData(method="GET", url="https://example.com/1"),
                modified_request=RequestData(method="GET", url="https://example.com/2"),
                modification=Modification(
                    original_value="1", modified_value="2",
                    location="url_path", field_name=None, description="+1",
                ),
                response=ResponseData(
                    status_code=200, content_length=100, elapsed_ms=50.0,
                ),
                original_response=ResponseData(
                    status_code=200, content_length=95,
                ),
                comparison=ComparisonResult(
                    status_match=True, status_original=200,
                    status_modified=200, content_length_diff=5,
                    verdict="VULNERABLE",
                ),
                timestamp="2024-01-01T00:00:00Z",
            ),
        ]
        output = str(tmp_path / "results.json")  # type: ignore[operator]
        _save_results(results, output, "test_report.json")

        with open(output, encoding="utf-8") as f:
            data = json.load(f)

        assert data["session"]["source_report"] == "test_report.json"
        assert len(data["results"]) == 1
        assert data["results"][0]["verdict"] == "VULNERABLE"
        assert data["results"][0]["original_response"]["status_code"] == 200

    def test_save_result_without_original_response(
        self, tmp_path: pytest.TempPathFactory,
    ) -> None:
        results = [
            VerifyResult(
                finding_id_value="abc",
                finding_id_type="token",
                original_request=RequestData(method="GET", url="https://example.com"),
                modified_request=RequestData(method="GET", url="https://example.com"),
                modification=Modification(
                    original_value="abc", modified_value="xyz",
                    location="url_path", field_name=None, description="test",
                ),
                response=ResponseData(status_code=403, content_length=20),
                original_response=None,
                comparison=ComparisonResult(
                    status_match=False, status_original=None,
                    status_modified=403, content_length_diff=None,
                    verdict="NOT_VULNERABLE",
                ),
                timestamp="2024-01-01T00:00:00Z",
            ),
        ]
        output = str(tmp_path / "results2.json")  # type: ignore[operator]
        _save_results(results, output, "report.json")

        with open(output, encoding="utf-8") as f:
            data = json.load(f)

        assert data["results"][0]["original_response"] is None
        assert data["results"][0]["verdict"] == "NOT_VULNERABLE"

    def test_result_to_dict(self) -> None:
        result = VerifyResult(
            finding_id_value="999",
            finding_id_type="numeric",
            original_request=RequestData(method="DELETE", url="https://example.com/999"),
            modified_request=RequestData(method="DELETE", url="https://example.com/1000"),
            modification=Modification(
                original_value="999", modified_value="1000",
                location="url_path", field_name=None, description="+1",
            ),
            response=ResponseData(
                status_code=204, content_length=0, elapsed_ms=30.0,
            ),
            original_response=None,
            comparison=ComparisonResult(
                status_match=False, status_original=None,
                status_modified=204, content_length_diff=None,
                verdict="INCONCLUSIVE",
            ),
            timestamp="2024-01-01T00:00:00Z",
        )
        d = _result_to_dict(result)
        assert d["finding_id"] == "999"
        assert d["modification"]["location"] == "url_path"
        assert d["request"]["method"] == "DELETE"
        assert d["response"]["elapsed_ms"] == 30.0


# --- TestApplyModificationEdgeCases ---


class TestApplyModificationEdgeCases:
    """Test edge cases for modification application."""

    def test_query_fallback_no_field_name(self) -> None:
        request = RequestData(
            method="GET",
            url="https://api.example.com/search?q=12345&page=1",
        )
        mod = Modification(
            original_value="12345",
            modified_value="12346",
            location="query",
            field_name=None,
            description="test",
        )
        result = _apply_modification(request, mod)
        assert "12346" in result.url
        assert "12345" not in result.url

    def test_body_non_json_replacement(self) -> None:
        request = RequestData(
            method="POST",
            url="https://api.example.com/form",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            body="user_id=12345&action=test",
        )
        mod = Modification(
            original_value="12345",
            modified_value="12346",
            location="body",
            field_name="user_id",
            description="test",
        )
        result = _apply_modification(request, mod)
        assert "12346" in result.body
        assert "12345" not in result.body

    def test_body_no_body(self) -> None:
        request = RequestData(
            method="GET",
            url="https://api.example.com/test",
            body=None,
        )
        mod = Modification(
            original_value="12345",
            modified_value="12346",
            location="body",
            field_name=None,
            description="test",
        )
        result = _apply_modification(request, mod)
        assert result.body is None

    def test_header_no_field_name(self) -> None:
        request = RequestData(
            method="GET",
            url="https://api.example.com/test",
            headers={"X-Id": "12345"},
        )
        mod = Modification(
            original_value="12345",
            modified_value="12346",
            location="header",
            field_name=None,
            description="test",
        )
        result = _apply_modification(request, mod)
        # No field_name -> no modification
        assert result.headers["X-Id"] == "12345"

    def test_header_no_matching_key(self) -> None:
        request = RequestData(
            method="GET",
            url="https://api.example.com/test",
            headers={"X-Id": "12345"},
        )
        mod = Modification(
            original_value="12345",
            modified_value="12346",
            location="header",
            field_name="x-nonexistent",
            description="test",
        )
        result = _apply_modification(request, mod)
        assert result.headers["X-Id"] == "12345"

    def test_set_nested_value_missing_intermediate(self) -> None:
        data = {"a": {"b": 1}}
        _set_nested_value(data, "a.c.d", "1", "2")
        # Should not modify since path doesn't exist
        assert data == {"a": {"b": 1}}

    def test_set_nested_value_int_to_non_int(self) -> None:
        data = {"id": 12345}
        _set_nested_value(data, "id", "12345", "not_a_number")
        assert data["id"] == "not_a_number"
