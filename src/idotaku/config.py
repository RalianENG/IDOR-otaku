"""Configuration loader for idotaku."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ruamel.yaml is already a dependency of mitmproxy
from ruamel.yaml import YAML, YAMLError


@dataclass
class IdotakuConfig:
    """idotaku configuration."""

    # Output settings
    output: str = "id_tracker_report.json"
    min_numeric: int = 100

    # ID detection patterns (name -> regex string)
    patterns: dict[str, str] = field(default_factory=lambda: {
        "uuid": r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        "numeric": r"\b[1-9]\d{2,10}\b",
        "token": r"\b[A-Za-z0-9_-]{20,}\b",
    })

    # Exclude patterns (regex to exclude from ID candidates)
    exclude_patterns: list[str] = field(default_factory=lambda: [
        r"^\d{10,13}$",      # Unix timestamp
        r"^\d+\.\d+\.\d+$",  # Version numbers
    ])

    # Trackable Content-Types
    trackable_content_types: list[str] = field(default_factory=lambda: [
        "application/json",
        "application/x-www-form-urlencoded",
        "text/html",
        "text/plain",
    ])

    # Ignore headers (blacklist)
    ignore_headers: set[str] = field(default_factory=lambda: {
        # Standard metadata
        "content-type", "content-length", "content-encoding",
        "accept", "accept-encoding", "accept-language", "accept-charset",
        "user-agent", "host", "connection", "origin", "referer",
        # Cache-related
        "cache-control", "pragma", "etag", "last-modified", "expires",
        "if-none-match", "if-modified-since",
        # CORS
        "access-control-allow-origin", "access-control-allow-methods",
        "access-control-allow-headers", "access-control-expose-headers",
        "access-control-max-age", "access-control-allow-credentials",
        # Others
        "date", "server", "vary", "transfer-encoding", "keep-alive",
        "upgrade", "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform",
        "sec-fetch-dest", "sec-fetch-mode", "sec-fetch-site", "sec-fetch-user",
        "dnt", "upgrade-insecure-requests",
    })

    # Additional headers to ignore (user-defined)
    extra_ignore_headers: list[str] = field(default_factory=list)

    # Target domains (whitelist, empty means all domains)
    target_domains: list[str] = field(default_factory=list)

    # Exclude domains (blacklist)
    exclude_domains: list[str] = field(default_factory=list)

    # Maximum body size to store in report (bytes, 0 = unlimited)
    max_body_size: int = 51200  # 50KB

    # Exclude extensions (static files, etc.)
    exclude_extensions: list[str] = field(default_factory=lambda: [
        # Styles and scripts
        ".css", ".js", ".map",
        # Images
        ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp",
        # Fonts
        ".woff", ".woff2", ".ttf", ".eot", ".otf",
        # Media
        ".mp3", ".mp4", ".webm", ".ogg", ".wav",
        # Others
        ".pdf", ".zip", ".gz",
    ])

    def get_compiled_patterns(self) -> dict[str, re.Pattern[str]]:
        """Return compiled regex patterns."""
        return {
            name: re.compile(pattern, re.IGNORECASE if name == "uuid" else 0)
            for name, pattern in self.patterns.items()
        }

    def get_compiled_exclude_patterns(self) -> list[re.Pattern[str]]:
        """Return compiled exclude patterns."""
        return [re.compile(p) for p in self.exclude_patterns]

    def get_all_ignore_headers(self) -> set[str]:
        """Return all headers to ignore."""
        return self.ignore_headers | set(h.lower() for h in self.extra_ignore_headers)

    @staticmethod
    def match_domain(domain: str, pattern: str) -> bool:
        """Check if domain matches pattern (wildcard supported).

        Examples:
            match_domain("api.example.com", "api.example.com") -> True
            match_domain("api.example.com", "*.example.com") -> True
            match_domain("sub.api.example.com", "*.example.com") -> True
            match_domain("example.com", "*.example.com") -> False
        """
        domain = domain.lower()
        pattern = pattern.lower()

        if pattern.startswith("*."):
            # Wildcard pattern: *.example.com
            suffix = pattern[1:]  # .example.com
            return domain.endswith(suffix) and domain != pattern[2:]
        else:
            # Exact match
            return domain == pattern

    def should_track_domain(self, domain: str) -> bool:
        """Check if domain should be tracked.

        Returns:
            True: track this domain
            False: don't track this domain
        """
        domain = domain.lower()

        # Blacklist check (takes priority)
        for pattern in self.exclude_domains:
            if self.match_domain(domain, pattern):
                return False

        # Whitelist check (empty allows all domains)
        if not self.target_domains:
            return True

        for pattern in self.target_domains:
            if self.match_domain(domain, pattern):
                return True

        return False

    def should_track_path(self, path: str) -> bool:
        """Check if path should be tracked (extension filtering).

        Returns:
            True: track this path
            False: don't track (matches excluded extension)
        """
        # Remove query params and get path only
        path_only = path.lower().split("?")[0]
        for ext in self.exclude_extensions:
            if path_only.endswith(ext.lower()):
                return False
        return True


CONFIG_SEARCH_PATHS = [
    "idotaku.yaml",
    "idotaku.yml",
    ".idotaku.yaml",
    ".idotaku.yml",
]

LIST_FIELDS = {
    "exclude_patterns", "trackable_content_types",
    "extra_ignore_headers", "target_domains",
    "exclude_domains", "exclude_extensions",
}

KNOWN_KEYS = {
    "output", "min_numeric", "patterns", "exclude_patterns",
    "trackable_content_types", "ignore_headers",
    "extra_ignore_headers", "target_domains",
    "exclude_domains", "exclude_extensions",
    "max_body_size",
}


def find_config_path() -> Path | None:
    """Find the active config file path, or None if no config file exists."""
    for name in CONFIG_SEARCH_PATHS:
        path = Path.cwd() / name
        if path.exists():
            return path
    return None


def save_config_value(config_path: Path, key: str, value: str) -> None:
    """Set a single key in the YAML config file (round-trip, preserving comments).

    Supports dotted keys like 'patterns.uuid' for nested dicts.
    For list values, the value string is split on commas.
    """
    yaml = YAML()
    yaml.preserve_quotes = True

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.load(f)

    if data is None:
        data = {}

    # Navigate to the idotaku section
    target = data
    if "idotaku" in data:
        target = data["idotaku"]

    # Handle dotted keys (e.g. "patterns.uuid")
    parts = key.split(".")
    for part in parts[:-1]:
        if part not in target or not isinstance(target[part], dict):
            target[part] = {}
        target = target[part]

    final_key = parts[-1]

    if final_key in LIST_FIELDS:
        target[final_key] = [v.strip() for v in value.split(",")]
    else:
        try:
            target[final_key] = int(value)
        except ValueError:
            if value.lower() in ("true", "false"):
                target[final_key] = value.lower() == "true"
            else:
                target[final_key] = value

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)


def validate_config(config_path: Path) -> list[str]:
    """Validate a config file and return a list of error messages (empty = valid)."""
    errors: list[str] = []

    try:
        yaml = YAML()
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.load(f)
    except YAMLError as e:
        return [f"Invalid YAML syntax: {e}"]
    except OSError as e:
        return [f"Cannot read file: {e}"]

    if data is None:
        return []

    if isinstance(data, dict) and "idotaku" in data:
        data = data["idotaku"]

    if not isinstance(data, dict):
        return [f"Config must be a YAML mapping, got {type(data).__name__}"]

    for key in data:
        if key not in KNOWN_KEYS:
            errors.append(f"Unknown key: '{key}'")

    if "min_numeric" in data:
        try:
            int(data["min_numeric"])
        except (ValueError, TypeError):
            errors.append(f"'min_numeric' must be an integer, got: {data['min_numeric']}")

    if "patterns" in data:
        if not isinstance(data["patterns"], dict):
            errors.append("'patterns' must be a mapping (name: regex)")
        else:
            for name, pattern in data["patterns"].items():
                try:
                    re.compile(str(pattern))
                except re.error as e:
                    errors.append(f"Invalid regex in patterns.{name}: {e}")

    if "exclude_patterns" in data:
        if not isinstance(data["exclude_patterns"], list):
            errors.append("'exclude_patterns' must be a list")
        else:
            for i, p in enumerate(data["exclude_patterns"]):
                try:
                    re.compile(str(p))
                except re.error as e:
                    errors.append(f"Invalid regex in exclude_patterns[{i}]: {e}")

    for list_key in ("trackable_content_types", "extra_ignore_headers",
                     "target_domains", "exclude_domains", "exclude_extensions",
                     "ignore_headers"):
        if list_key in data and not isinstance(data[list_key], list):
            errors.append(f"'{list_key}' must be a list")

    return errors


def load_config(config_path: str | Path | None = None) -> IdotakuConfig:
    """Load configuration file."""
    config = IdotakuConfig()
    explicit = config_path is not None

    if config_path is None:
        config_path = find_config_path()

    if config_path is None:
        return config  # Return default config

    config_path = Path(config_path)
    if not config_path.exists():
        if explicit:
            print(f"Error: Config file not found: {config_path}", file=sys.stderr)
            sys.exit(1)
        return config

    try:
        yaml = YAML()
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.load(f)
    except YAMLError as e:
        print(f"Error: Invalid YAML in {config_path}: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Error: Cannot read config file {config_path}: {e}", file=sys.stderr)
        sys.exit(1)

    if data is None:
        return config

    # If there's an idotaku section, use its contents
    if isinstance(data, dict) and "idotaku" in data:
        data = data["idotaku"]

    if not isinstance(data, dict):
        print(f"Error: Config must be a YAML mapping, got {type(data).__name__}", file=sys.stderr)
        sys.exit(1)

    # Apply settings
    if "output" in data:
        config.output = str(data["output"])

    if "min_numeric" in data:
        try:
            config.min_numeric = int(data["min_numeric"])
        except (ValueError, TypeError):
            print(f"Error: min_numeric must be an integer, got: {data['min_numeric']}", file=sys.stderr)
            sys.exit(1)

    if "patterns" in data:
        if not isinstance(data["patterns"], dict):
            print("Error: 'patterns' must be a mapping (name: regex)", file=sys.stderr)
            sys.exit(1)
        # Validate regex patterns at load time
        for name, pattern in data["patterns"].items():
            try:
                re.compile(str(pattern))
            except re.error as e:
                print(f"Error: Invalid regex pattern '{name}': {e}", file=sys.stderr)
                sys.exit(1)
        config.patterns.update({k: str(v) for k, v in data["patterns"].items()})

    if "exclude_patterns" in data:
        if not isinstance(data["exclude_patterns"], list):
            print("Error: 'exclude_patterns' must be a list", file=sys.stderr)
            sys.exit(1)
        for p in data["exclude_patterns"]:
            try:
                re.compile(str(p))
            except re.error as e:
                print(f"Error: Invalid exclude pattern '{p}': {e}", file=sys.stderr)
                sys.exit(1)
        config.exclude_patterns = [str(p) for p in data["exclude_patterns"]]

    if "trackable_content_types" in data:
        if not isinstance(data["trackable_content_types"], list):
            print("Error: 'trackable_content_types' must be a list", file=sys.stderr)
            sys.exit(1)
        config.trackable_content_types = [str(ct) for ct in data["trackable_content_types"]]

    if "ignore_headers" in data:
        if not isinstance(data["ignore_headers"], list):
            print("Error: 'ignore_headers' must be a list", file=sys.stderr)
            sys.exit(1)
        config.ignore_headers = set(str(h).lower() for h in data["ignore_headers"])

    if "extra_ignore_headers" in data:
        if not isinstance(data["extra_ignore_headers"], list):
            print("Error: 'extra_ignore_headers' must be a list", file=sys.stderr)
            sys.exit(1)
        config.extra_ignore_headers = [str(h) for h in data["extra_ignore_headers"]]

    if "target_domains" in data:
        if not isinstance(data["target_domains"], list):
            print("Error: 'target_domains' must be a list", file=sys.stderr)
            sys.exit(1)
        config.target_domains = [str(d) for d in data["target_domains"]]

    if "exclude_domains" in data:
        if not isinstance(data["exclude_domains"], list):
            print("Error: 'exclude_domains' must be a list", file=sys.stderr)
            sys.exit(1)
        config.exclude_domains = [str(d) for d in data["exclude_domains"]]

    if "exclude_extensions" in data:
        if not isinstance(data["exclude_extensions"], list):
            print("Error: 'exclude_extensions' must be a list", file=sys.stderr)
            sys.exit(1)
        config.exclude_extensions = [str(e) for e in data["exclude_extensions"]]

    if "max_body_size" in data:
        try:
            config.max_body_size = int(data["max_body_size"])
        except (ValueError, TypeError):
            print(f"Error: max_body_size must be an integer, got: {data['max_body_size']}", file=sys.stderr)
            sys.exit(1)

    return config


def get_default_config_yaml() -> str:
    """Return default YAML config template."""
    return r'''# idotaku configuration
# Place this file as idotaku.yaml in your working directory

idotaku:
  # Output file path
  output: id_tracker_report.json

  # Minimum numeric ID value to track (smaller values are ignored)
  min_numeric: 100

  # ID detection patterns (name: regex)
  # These patterns are used to extract IDs from requests/responses
  patterns:
    uuid: '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
    numeric: '[1-9]\d{2,10}'
    token: '[A-Za-z0-9_-]{20,}'
    # Add custom patterns here:
    # order_id: 'ORD-[A-Z]{2}-\d{8}'
    # custom_id: 'ID-[A-Z]{3}-\d{6}'

  # Patterns to exclude from ID detection (false positives)
  exclude_patterns:
    - '^\d{10,13}$'      # Unix timestamp
    - '^\d+\.\d+\.\d+$'  # Version numbers

  # Content types to parse for IDs
  trackable_content_types:
    - application/json
    - application/x-www-form-urlencoded
    - text/html
    - text/plain

  # Headers to ignore (blacklist) - all other headers are scanned for IDs
  # Uncomment to override defaults completely:
  # ignore_headers:
  #   - content-type
  #   - content-length
  #   - ...

  # Additional headers to ignore (added to defaults)
  extra_ignore_headers: []
    # - x-internal-trace-id
    # - x-debug-info

  # Target domains - whitelist (empty = all domains)
  # target_domains:
  #   - api.example.com
  #   - "*.example.com"

  # Exclude domains - blacklist (takes priority over target_domains)
  # exclude_domains:
  #   - analytics.example.com
  #   - "*.tracking.com"
'''
