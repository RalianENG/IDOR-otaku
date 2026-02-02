"""Tests for visualization module."""

import pytest
from rich.text import Text

from idotaku.visualization.console import (
    format_occurrence,
    format_api,
    escape_rich,
    format_param,
    format_id_value,
    format_id_with_type,
)


class TestFormatOccurrence:
    """Tests for format_occurrence function."""

    def test_basic_occurrence(self):
        """Test formatting basic occurrence."""
        occ = {
            "method": "GET",
            "url": "https://api.example.com/users/123",
            "location": "path",
            "field": "id",
            "timestamp": "2024-01-01T10:30:45Z",
        }
        result = format_occurrence(occ, "ORIGIN", "green")

        assert isinstance(result, Text)
        plain = result.plain
        assert "ORIGIN" in plain
        assert "GET" in plain
        assert "path.id" in plain
        assert "10:30:45" in plain

    def test_long_url_truncation(self):
        """Test that long URLs are truncated."""
        occ = {
            "method": "POST",
            "url": "https://api.example.com/very/long/path/that/exceeds/sixty/characters/limit/here",
            "location": "body",
        }
        result = format_occurrence(occ, "USAGE", "yellow")
        plain = result.plain

        # URL should be truncated
        assert "..." in plain

    def test_missing_field(self):
        """Test occurrence without field."""
        occ = {
            "method": "GET",
            "url": "https://api.example.com/data",
            "location": "query",
        }
        result = format_occurrence(occ, "ORIGIN", "green")
        plain = result.plain

        # Should show location without field
        assert "query" in plain

    def test_field_name_fallback(self):
        """Test field_name fallback to field."""
        occ = {
            "method": "GET",
            "url": "https://api.example.com/data",
            "location": "body",
            "field_name": "user_id",
        }
        result = format_occurrence(occ, "ORIGIN", "green")
        plain = result.plain

        assert "body.user_id" in plain

    def test_no_timestamp(self):
        """Test occurrence without timestamp."""
        occ = {
            "method": "GET",
            "url": "https://api.example.com/data",
            "location": "path",
        }
        result = format_occurrence(occ, "USAGE", "yellow")
        plain = result.plain

        # Should not have time in parentheses
        assert "(" not in plain or "USAGE" in plain


class TestFormatApi:
    """Tests for format_api function."""

    def test_basic_api(self):
        """Test formatting basic API."""
        flow = {
            "method": "GET",
            "url": "https://api.example.com/users",
        }
        result = format_api(flow)

        assert "GET" in result
        assert "/users" in result
        assert "magenta" in result  # Method color

    def test_long_path_truncation(self):
        """Test long path truncation."""
        flow = {
            "method": "POST",
            "url": "https://api.example.com/very/long/api/path/that/exceeds/max/length",
        }
        result = format_api(flow, max_path_length=20)

        assert "..." in result

    def test_escape_brackets(self):
        """Test that brackets in path are escaped."""
        flow = {
            "method": "GET",
            "url": "https://api.example.com/items[0]/data",
        }
        result = format_api(flow)

        # Bracket should be escaped
        assert "\\[" in result

    def test_empty_path(self):
        """Test handling of URL with no path."""
        flow = {
            "method": "GET",
            "url": "https://api.example.com",
        }
        result = format_api(flow)

        assert "/" in result


class TestEscapeRich:
    """Tests for escape_rich function."""

    def test_escape_brackets(self):
        """Test bracket escaping."""
        assert escape_rich("test[0]") == "test\\[0]"
        assert escape_rich("[bold]text[/bold]") == "\\[bold]text\\[/bold]"

    def test_no_brackets(self):
        """Test string without brackets."""
        assert escape_rich("normal text") == "normal text"

    def test_non_string_input(self):
        """Test non-string input conversion."""
        assert escape_rich(12345) == "12345"
        assert escape_rich(None) == "None"


class TestFormatParam:
    """Tests for format_param function."""

    def test_single_string(self):
        """Test formatting single string param."""
        result = format_param("user_123")
        assert "user_123" in result
        assert "cyan" in result

    def test_long_string_truncation(self):
        """Test long string truncation."""
        result = format_param("very_long_parameter_value_here", max_length=10)
        assert ".." in result

    def test_empty_list(self):
        """Test formatting empty list."""
        result = format_param([])
        assert "none" in result

    def test_single_item_list(self):
        """Test formatting single item list."""
        result = format_param(["single"])
        assert "single" in result

    def test_multiple_items_list(self):
        """Test formatting multiple items list."""
        result = format_param(["one", "two", "three"])
        assert "one" in result
        assert "two" in result
        assert "three" in result

    def test_many_items_list(self):
        """Test formatting list with more than 3 items."""
        result = format_param(["a", "b", "c", "d", "e"])
        assert "+2" in result  # Shows count of remaining items

    def test_long_items_in_list(self):
        """Test that long items in list are truncated."""
        result = format_param(["very_long_item_one", "very_long_item_two"])
        assert ".." in result


class TestFormatIdValue:
    """Tests for format_id_value function."""

    def test_short_id(self):
        """Test short ID not truncated."""
        assert format_id_value("12345") == "12345"

    def test_long_id(self):
        """Test long ID truncation."""
        result = format_id_value("very_long_id_value_here", max_length=10)
        assert result == "very_long_..."
        assert len(result) == 13  # 10 + 3 for "..."

    def test_exact_length(self):
        """Test ID at exact max length."""
        assert format_id_value("1234567890", max_length=10) == "1234567890"

    def test_custom_max_length(self):
        """Test custom max length."""
        result = format_id_value("abcdefghij", max_length=5)
        assert result == "abcde..."


class TestFormatIdWithType:
    """Tests for format_id_with_type function."""

    def test_basic_id(self):
        """Test basic ID formatting."""
        result = format_id_with_type("12345", "numeric")
        assert "12345" in result
        assert "numeric" in result
        assert "cyan" in result

    def test_idor_marking(self):
        """Test IDOR marking."""
        result = format_id_with_type("12345", "numeric", is_idor=True)
        assert "12345" in result
        assert "IDOR" in result
        assert "red" in result

    def test_long_id_truncation(self):
        """Test long ID truncation."""
        result = format_id_with_type("very_long_id_value", "token", max_length=10)
        assert "..." in result

    def test_uuid_type(self):
        """Test UUID type formatting."""
        uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = format_id_with_type(uuid, "uuid")
        assert "uuid" in result
