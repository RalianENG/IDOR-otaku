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
