"""Tests for configuration module."""

import pytest

from idotaku.config import IdotakuConfig, load_config, get_default_config_yaml


class TestIdotakuConfigDefaults:
    """Tests for IdotakuConfig default values."""

    def test_default_output(self):
        """Test default output path."""
        config = IdotakuConfig()
        assert config.output == "id_tracker_report.json"

    def test_default_min_numeric(self):
        """Test default minimum numeric value."""
        config = IdotakuConfig()
        assert config.min_numeric == 100

    def test_default_patterns(self):
        """Test default ID patterns."""
        config = IdotakuConfig()
        assert "uuid" in config.patterns
        assert "numeric" in config.patterns
        assert "token" in config.patterns

    def test_default_exclude_extensions(self):
        """Test default excluded extensions."""
        config = IdotakuConfig()
        assert ".css" in config.exclude_extensions
        assert ".js" in config.exclude_extensions
        assert ".png" in config.exclude_extensions

    def test_default_ignore_headers(self):
        """Test default ignored headers."""
        config = IdotakuConfig()
        assert "content-type" in config.ignore_headers
        assert "user-agent" in config.ignore_headers


class TestIdotakuConfigMethods:
    """Tests for IdotakuConfig methods."""

    def test_get_compiled_patterns(self):
        """Test pattern compilation."""
        config = IdotakuConfig()
        compiled = config.get_compiled_patterns()

        assert "uuid" in compiled
        assert "numeric" in compiled

        # Test UUID pattern matches
        uuid_pattern = compiled["uuid"]
        assert uuid_pattern.search("550e8400-e29b-41d4-a716-446655440000")
        assert not uuid_pattern.search("not-a-uuid")

        # Test numeric pattern matches
        numeric_pattern = compiled["numeric"]
        assert numeric_pattern.search("12345")
        assert not numeric_pattern.search("12")  # Too short

    def test_get_compiled_exclude_patterns(self):
        """Test exclude pattern compilation."""
        config = IdotakuConfig()
        compiled = config.get_compiled_exclude_patterns()

        assert len(compiled) >= 2

        # Test timestamp exclusion
        timestamp_pattern = compiled[0]
        assert timestamp_pattern.match("1234567890123")

    def test_get_all_ignore_headers(self):
        """Test combined ignore headers."""
        config = IdotakuConfig()
        config.extra_ignore_headers = ["X-Custom-Header", "X-Debug"]

        all_headers = config.get_all_ignore_headers()

        assert "content-type" in all_headers
        assert "x-custom-header" in all_headers  # Should be lowercased
        assert "x-debug" in all_headers


class TestMatchDomain:
    """Tests for match_domain static method."""

    def test_exact_match(self):
        """Test exact domain matching."""
        assert IdotakuConfig.match_domain("api.example.com", "api.example.com")
        assert not IdotakuConfig.match_domain("api.example.com", "other.example.com")

    def test_wildcard_match(self):
        """Test wildcard domain matching."""
        assert IdotakuConfig.match_domain("api.example.com", "*.example.com")
        assert IdotakuConfig.match_domain("sub.api.example.com", "*.example.com")
        assert not IdotakuConfig.match_domain("example.com", "*.example.com")

    def test_case_insensitive(self):
        """Test case insensitive matching."""
        assert IdotakuConfig.match_domain("API.Example.COM", "api.example.com")
        assert IdotakuConfig.match_domain("api.example.com", "*.EXAMPLE.COM")


class TestShouldTrackDomain:
    """Tests for should_track_domain method."""

    def test_no_filters(self):
        """Test with no domain filters (track all)."""
        config = IdotakuConfig()
        assert config.should_track_domain("any.domain.com")

    def test_whitelist_only(self):
        """Test with whitelist only."""
        config = IdotakuConfig()
        config.target_domains = ["api.example.com", "*.trusted.com"]

        assert config.should_track_domain("api.example.com")
        assert config.should_track_domain("sub.trusted.com")
        assert not config.should_track_domain("other.com")

    def test_blacklist_only(self):
        """Test with blacklist only."""
        config = IdotakuConfig()
        config.exclude_domains = ["analytics.example.com", "*.tracking.com"]

        assert config.should_track_domain("api.example.com")
        assert not config.should_track_domain("analytics.example.com")
        assert not config.should_track_domain("sub.tracking.com")

    def test_blacklist_priority(self):
        """Test that blacklist takes priority over whitelist."""
        config = IdotakuConfig()
        config.target_domains = ["*.example.com"]
        config.exclude_domains = ["analytics.example.com"]

        assert config.should_track_domain("api.example.com")
        assert not config.should_track_domain("analytics.example.com")


class TestShouldTrackPath:
    """Tests for should_track_path method."""

    def test_track_api_paths(self):
        """Test that API paths are tracked."""
        config = IdotakuConfig()
        assert config.should_track_path("/api/users")
        assert config.should_track_path("/api/v1/data?query=1")

    def test_exclude_static_files(self):
        """Test that static files are excluded."""
        config = IdotakuConfig()
        assert not config.should_track_path("/assets/style.css")
        assert not config.should_track_path("/images/logo.png")
        assert not config.should_track_path("/scripts/app.js")

    def test_case_insensitive_extension(self):
        """Test case insensitive extension matching."""
        config = IdotakuConfig()
        assert not config.should_track_path("/assets/STYLE.CSS")
        assert not config.should_track_path("/images/LOGO.PNG")

    def test_query_string_ignored(self):
        """Test that query string is ignored for extension check."""
        config = IdotakuConfig()
        assert not config.should_track_path("/file.js?v=123")
        assert config.should_track_path("/api/data?file=test.js")  # Extension in query, not path


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_default_config(self):
        """Test loading default config when no file exists."""
        config = load_config(None)
        assert isinstance(config, IdotakuConfig)
        assert config.output == "id_tracker_report.json"

    def test_load_nonexistent_file(self, tmp_path):
        """Test loading from explicitly specified non-existent file exits with error."""
        import pytest
        with pytest.raises(SystemExit):
            load_config(tmp_path / "nonexistent.yaml")

    def test_load_valid_config(self, tmp_path):
        """Test loading valid config file."""
        config_file = tmp_path / "idotaku.yaml"
        config_file.write_text("""
idotaku:
  output: custom_report.json
  min_numeric: 500
  target_domains:
    - api.example.com
  exclude_domains:
    - analytics.example.com
""")
        config = load_config(config_file)

        assert config.output == "custom_report.json"
        assert config.min_numeric == 500
        assert "api.example.com" in config.target_domains
        assert "analytics.example.com" in config.exclude_domains

    def test_load_config_without_idotaku_section(self, tmp_path):
        """Test loading config without idotaku section."""
        config_file = tmp_path / "idotaku.yaml"
        config_file.write_text("""
output: direct_report.json
min_numeric: 200
""")
        config = load_config(config_file)

        assert config.output == "direct_report.json"
        assert config.min_numeric == 200

    def test_load_empty_config(self, tmp_path):
        """Test loading empty config file."""
        config_file = tmp_path / "idotaku.yaml"
        config_file.write_text("")

        config = load_config(config_file)
        assert isinstance(config, IdotakuConfig)

    def test_load_config_patterns_merge(self, tmp_path):
        """Test that custom patterns are merged with defaults."""
        config_file = tmp_path / "idotaku.yaml"
        config_file.write_text("""
idotaku:
  patterns:
    custom_id: "CID-[0-9]+"
""")
        config = load_config(config_file)

        # Custom pattern added
        assert "custom_id" in config.patterns
        # Default patterns still exist
        assert "uuid" in config.patterns
        assert "numeric" in config.patterns

    def test_load_config_extra_ignore_headers(self, tmp_path):
        """Test loading extra ignore headers."""
        config_file = tmp_path / "idotaku.yaml"
        config_file.write_text("""
idotaku:
  extra_ignore_headers:
    - X-Debug-Info
    - X-Internal-Id
""")
        config = load_config(config_file)

        all_headers = config.get_all_ignore_headers()
        assert "x-debug-info" in all_headers
        assert "x-internal-id" in all_headers


class TestGetDefaultConfigYaml:
    """Tests for get_default_config_yaml function."""

    def test_returns_yaml_string(self):
        """Test that function returns YAML string."""
        yaml_str = get_default_config_yaml()
        assert isinstance(yaml_str, str)
        assert "idotaku:" in yaml_str
        assert "output:" in yaml_str
        assert "patterns:" in yaml_str

    def test_yaml_has_required_sections(self):
        """Test that returned YAML has required sections."""
        yaml_str = get_default_config_yaml()

        # Should have key sections
        assert "idotaku:" in yaml_str
        assert "output:" in yaml_str
        assert "min_numeric:" in yaml_str
        assert "patterns:" in yaml_str
        assert "exclude_patterns:" in yaml_str
        assert "target_domains:" in yaml_str
        assert "exclude_domains:" in yaml_str


class TestLoadConfigErrors:
    """Tests for load_config error handling."""

    def test_invalid_yaml_syntax(self, tmp_path):
        """Test loading file with invalid YAML syntax."""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("invalid: yaml: syntax: [unclosed")
        with pytest.raises(SystemExit):
            load_config(config_file)

    def test_non_dict_config(self, tmp_path):
        """Test loading config that is not a mapping."""
        config_file = tmp_path / "list.yaml"
        config_file.write_text("- item1\n- item2\n")
        with pytest.raises(SystemExit):
            load_config(config_file)

    def test_invalid_min_numeric_type(self, tmp_path):
        """Test loading config with invalid min_numeric type."""
        config_file = tmp_path / "invalid_numeric.yaml"
        config_file.write_text("idotaku:\n  min_numeric: not_a_number\n")
        with pytest.raises(SystemExit):
            load_config(config_file)

    def test_patterns_not_dict(self, tmp_path):
        """Test loading config with patterns as list instead of dict."""
        config_file = tmp_path / "invalid_patterns.yaml"
        config_file.write_text("idotaku:\n  patterns:\n    - pattern1\n")
        with pytest.raises(SystemExit):
            load_config(config_file)

    def test_invalid_regex_pattern(self, tmp_path):
        """Test loading config with invalid regex pattern."""
        config_file = tmp_path / "invalid_regex.yaml"
        config_file.write_text('idotaku:\n  patterns:\n    broken: "[unclosed"\n')
        with pytest.raises(SystemExit):
            load_config(config_file)

    def test_exclude_patterns_not_list(self, tmp_path):
        """Test loading config with exclude_patterns as string."""
        config_file = tmp_path / "invalid_exclude.yaml"
        config_file.write_text('idotaku:\n  exclude_patterns: "not a list"\n')
        with pytest.raises(SystemExit):
            load_config(config_file)

    def test_invalid_exclude_pattern_regex(self, tmp_path):
        """Test loading config with invalid exclude pattern regex."""
        config_file = tmp_path / "invalid_exclude_regex.yaml"
        config_file.write_text('idotaku:\n  exclude_patterns:\n    - "[invalid"\n')
        with pytest.raises(SystemExit):
            load_config(config_file)

    def test_trackable_content_types_not_list(self, tmp_path):
        """Test loading config with trackable_content_types as string."""
        config_file = tmp_path / "invalid_ct.yaml"
        config_file.write_text('idotaku:\n  trackable_content_types: "application/json"\n')
        with pytest.raises(SystemExit):
            load_config(config_file)

    def test_ignore_headers_not_list(self, tmp_path):
        """Test loading config with ignore_headers as string."""
        config_file = tmp_path / "invalid_headers.yaml"
        config_file.write_text('idotaku:\n  ignore_headers: "content-type"\n')
        with pytest.raises(SystemExit):
            load_config(config_file)

    def test_target_domains_not_list(self, tmp_path):
        """Test loading config with target_domains as string."""
        config_file = tmp_path / "invalid_domains.yaml"
        config_file.write_text('idotaku:\n  target_domains: "example.com"\n')
        with pytest.raises(SystemExit):
            load_config(config_file)


class TestLoadConfigAutoDiscovery:
    """Tests for automatic config file discovery."""

    def test_discover_idotaku_yaml(self, tmp_path, monkeypatch):
        """Test discovering idotaku.yaml in cwd."""
        config_file = tmp_path / "idotaku.yaml"
        config_file.write_text("idotaku:\n  output: discovered.json\n")
        monkeypatch.chdir(tmp_path)
        config = load_config(None)
        assert config.output == "discovered.json"

    def test_discover_idotaku_yml(self, tmp_path, monkeypatch):
        """Test discovering idotaku.yml in cwd."""
        config_file = tmp_path / "idotaku.yml"
        config_file.write_text("idotaku:\n  output: discovered_yml.json\n")
        monkeypatch.chdir(tmp_path)
        config = load_config(None)
        assert config.output == "discovered_yml.json"

    def test_no_config_returns_default(self, tmp_path, monkeypatch):
        """Test that missing config returns default."""
        monkeypatch.chdir(tmp_path)
        config = load_config(None)
        assert isinstance(config, IdotakuConfig)
        assert config.output == "id_tracker_report.json"
