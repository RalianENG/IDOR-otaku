"""Tests for utility functions."""


from idotaku.utils import (
    normalize_api_path,
    extract_domain,
    get_base_domain,
    truncate_text,
    truncate_id,
)


class TestNormalizeApiPath:
    """Tests for normalize_api_path function."""

    def test_numeric_id_replacement(self):
        """Test that numeric IDs are replaced with {id}."""
        assert normalize_api_path("https://api.example.com/users/12345") == "/users/{id}"
        assert normalize_api_path("https://api.example.com/users/1/posts/2") == "/users/{id}/posts/{id}"

    def test_uuid_replacement(self):
        """Test that UUIDs are replaced with {uuid}."""
        url = "https://api.example.com/items/550e8400-e29b-41d4-a716-446655440000"
        assert normalize_api_path(url) == "/items/{uuid}"

    def test_token_replacement(self):
        """Test that long alphanumeric tokens are replaced with {token}."""
        url = "https://api.example.com/auth/abcdefghijklmnopqrstuvwxyz"
        assert normalize_api_path(url) == "/auth/{token}"

    def test_static_path_unchanged(self):
        """Test that static paths remain unchanged."""
        assert normalize_api_path("https://api.example.com/users") == "/users"
        assert normalize_api_path("https://api.example.com/api/v1/health") == "/api/v1/health"

    def test_empty_path(self):
        """Test handling of empty or root path."""
        assert normalize_api_path("https://api.example.com") == "/"
        assert normalize_api_path("https://api.example.com/") == "/"


class TestExtractDomain:
    """Tests for extract_domain function."""

    def test_basic_domain(self):
        """Test extracting domain from URL."""
        assert extract_domain("https://api.example.com/users") == "api.example.com"
        assert extract_domain("http://localhost:8080/api") == "localhost:8080"

    def test_invalid_url(self):
        """Test handling of invalid URL."""
        assert extract_domain("not-a-url") == ""
        assert extract_domain("") == ""


class TestGetBaseDomain:
    """Tests for get_base_domain function."""

    def test_subdomain(self):
        """Test extracting base domain from subdomain."""
        assert get_base_domain("api.example.com") == "example.com"
        assert get_base_domain("www.api.example.com") == "example.com"

    def test_base_domain(self):
        """Test that base domain returns itself."""
        assert get_base_domain("example.com") == "example.com"

    def test_single_part(self):
        """Test handling of single-part domain."""
        assert get_base_domain("localhost") == "localhost"


class TestTruncateText:
    """Tests for truncate_text function."""

    def test_short_text(self):
        """Test that short text is not truncated."""
        assert truncate_text("hello", 10) == "hello"

    def test_long_text(self):
        """Test that long text is truncated with suffix."""
        assert truncate_text("hello world", 8) == "hello..."
        assert truncate_text("hello world", 8, "..") == "hello .."

    def test_exact_length(self):
        """Test text at exact max length."""
        assert truncate_text("hello", 5) == "hello"


class TestTruncateId:
    """Tests for truncate_id function."""

    def test_short_id(self):
        """Test that short ID is not truncated."""
        assert truncate_id("12345") == "12345"

    def test_long_id(self):
        """Test that long ID is truncated."""
        long_id = "abcdefghijklmnopqrstuvwxyz"
        result = truncate_id(long_id, 16)
        assert len(result) == 16 + 3  # 16 chars + "..."
        assert result.endswith("...")

    def test_uuid(self):
        """Test truncation of UUID."""
        uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = truncate_id(uuid)
        assert result.endswith("...")
