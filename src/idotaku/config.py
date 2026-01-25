"""Configuration loader for idotaku."""

import re
from pathlib import Path
from dataclasses import dataclass, field

# ruamel.yaml is already a dependency of mitmproxy
from ruamel.yaml import YAML


@dataclass
class IdotakuConfig:
    """idotaku configuration."""

    # 出力設定
    output: str = "id_tracker_report.json"
    min_numeric: int = 100

    # ID検出パターン（名前 -> 正規表現文字列）
    patterns: dict[str, str] = field(default_factory=lambda: {
        "uuid": r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        "numeric": r"\b[1-9]\d{2,10}\b",
        "token": r"\b[A-Za-z0-9_-]{20,}\b",
    })

    # 除外パターン（ID候補から除外する正規表現）
    exclude_patterns: list[str] = field(default_factory=lambda: [
        r"^\d{10,13}$",      # Unix timestamp
        r"^\d+\.\d+\.\d+$",  # Version numbers
    ])

    # 追跡対象Content-Type
    trackable_content_types: list[str] = field(default_factory=lambda: [
        "application/json",
        "application/x-www-form-urlencoded",
        "text/html",
        "text/plain",
    ])

    # 除外ヘッダー（ブラックリスト）
    ignore_headers: set[str] = field(default_factory=lambda: {
        # 標準的なメタデータ
        "content-type", "content-length", "content-encoding",
        "accept", "accept-encoding", "accept-language", "accept-charset",
        "user-agent", "host", "connection", "origin", "referer",
        # キャッシュ系
        "cache-control", "pragma", "etag", "last-modified", "expires",
        "if-none-match", "if-modified-since",
        # CORS
        "access-control-allow-origin", "access-control-allow-methods",
        "access-control-allow-headers", "access-control-expose-headers",
        "access-control-max-age", "access-control-allow-credentials",
        # その他
        "date", "server", "vary", "transfer-encoding", "keep-alive",
        "upgrade", "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform",
        "sec-fetch-dest", "sec-fetch-mode", "sec-fetch-site", "sec-fetch-user",
        "dnt", "upgrade-insecure-requests",
    })

    # 追加で除外したいヘッダー（ユーザー定義）
    extra_ignore_headers: list[str] = field(default_factory=list)

    # ターゲットドメイン（ホワイトリスト、空なら全ドメイン）
    target_domains: list[str] = field(default_factory=list)

    # 除外ドメイン（ブラックリスト）
    exclude_domains: list[str] = field(default_factory=list)

    # 除外拡張子（静的ファイルなど）
    exclude_extensions: list[str] = field(default_factory=lambda: [
        # スタイル・スクリプト
        ".css", ".js", ".map",
        # 画像
        ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp",
        # フォント
        ".woff", ".woff2", ".ttf", ".eot", ".otf",
        # メディア
        ".mp3", ".mp4", ".webm", ".ogg", ".wav",
        # その他
        ".pdf", ".zip", ".gz",
    ])

    def get_compiled_patterns(self) -> dict[str, re.Pattern]:
        """コンパイル済み正規表現を返す"""
        return {
            name: re.compile(pattern, re.IGNORECASE if name == "uuid" else 0)
            for name, pattern in self.patterns.items()
        }

    def get_compiled_exclude_patterns(self) -> list[re.Pattern]:
        """コンパイル済み除外パターンを返す"""
        return [re.compile(p) for p in self.exclude_patterns]

    def get_all_ignore_headers(self) -> set[str]:
        """全ての除外ヘッダーを返す"""
        return self.ignore_headers | set(h.lower() for h in self.extra_ignore_headers)

    @staticmethod
    def match_domain(domain: str, pattern: str) -> bool:
        """ドメインがパターンにマッチするかチェック（ワイルドカード対応）

        Examples:
            match_domain("api.example.com", "api.example.com") -> True
            match_domain("api.example.com", "*.example.com") -> True
            match_domain("sub.api.example.com", "*.example.com") -> True
            match_domain("example.com", "*.example.com") -> False
        """
        domain = domain.lower()
        pattern = pattern.lower()

        if pattern.startswith("*."):
            # ワイルドカードパターン: *.example.com
            suffix = pattern[1:]  # .example.com
            return domain.endswith(suffix) and domain != pattern[2:]
        else:
            # 完全一致
            return domain == pattern

    def should_track_domain(self, domain: str) -> bool:
        """ドメインを追跡すべきかチェック

        Returns:
            True: 追跡する
            False: 追跡しない
        """
        domain = domain.lower()

        # ブラックリストチェック（優先）
        for pattern in self.exclude_domains:
            if self.match_domain(domain, pattern):
                return False

        # ホワイトリストチェック（空なら全ドメイン許可）
        if not self.target_domains:
            return True

        for pattern in self.target_domains:
            if self.match_domain(domain, pattern):
                return True

        return False

    def should_track_path(self, path: str) -> bool:
        """パスを追跡すべきかチェック（拡張子フィルタリング）

        Returns:
            True: 追跡する
            False: 追跡しない（除外拡張子にマッチ）
        """
        # クエリパラメータを除去してパスのみ取得
        path_only = path.lower().split("?")[0]
        for ext in self.exclude_extensions:
            if path_only.endswith(ext.lower()):
                return False
        return True


def load_config(config_path: str | Path | None = None) -> IdotakuConfig:
    """設定ファイルを読み込む"""
    config = IdotakuConfig()

    if config_path is None:
        # デフォルトの設定ファイルパスを探す
        search_paths = [
            Path.cwd() / "idotaku.yaml",
            Path.cwd() / "idotaku.yml",
            Path.cwd() / ".idotaku.yaml",
            Path.cwd() / ".idotaku.yml",
        ]
        for path in search_paths:
            if path.exists():
                config_path = path
                break

    if config_path is None:
        return config  # デフォルト設定を返す

    config_path = Path(config_path)
    if not config_path.exists():
        return config

    yaml = YAML()
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.load(f)

    if data is None:
        return config

    # idotaku セクションがある場合はその中を見る
    if "idotaku" in data:
        data = data["idotaku"]

    # 設定を適用
    if "output" in data:
        config.output = data["output"]

    if "min_numeric" in data:
        config.min_numeric = int(data["min_numeric"])

    if "patterns" in data:
        # デフォルトパターンにマージ（上書き or 追加）
        config.patterns.update(data["patterns"])

    if "exclude_patterns" in data:
        config.exclude_patterns = list(data["exclude_patterns"])

    if "trackable_content_types" in data:
        config.trackable_content_types = list(data["trackable_content_types"])

    if "ignore_headers" in data:
        config.ignore_headers = set(h.lower() for h in data["ignore_headers"])

    if "extra_ignore_headers" in data:
        config.extra_ignore_headers = list(data["extra_ignore_headers"])

    if "target_domains" in data:
        config.target_domains = list(data["target_domains"])

    if "exclude_domains" in data:
        config.exclude_domains = list(data["exclude_domains"])

    if "exclude_extensions" in data:
        config.exclude_extensions = list(data["exclude_extensions"])

    return config


def get_default_config_yaml() -> str:
    """デフォルト設定のYAMLテンプレートを返す"""
    return '''# idotaku configuration
# Place this file as idotaku.yaml in your working directory

idotaku:
  # Output file path
  output: id_tracker_report.json

  # Minimum numeric ID value to track (smaller values are ignored)
  min_numeric: 100

  # ID detection patterns (name: regex)
  # These patterns are used to extract IDs from requests/responses
  patterns:
    uuid: "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    numeric: "[1-9]\\d{2,10}"
    token: "[A-Za-z0-9_-]{20,}"
    # Add custom patterns here:
    # order_id: "ORD-[A-Z]{2}-\\d{8}"
    # custom_id: "ID-[A-Z]{3}-\\d{6}"

  # Patterns to exclude from ID detection (false positives)
  exclude_patterns:
    - "^\\d{10,13}$"      # Unix timestamp
    - "^\\d+\\.\\d+\\.\\d+$"  # Version numbers

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
