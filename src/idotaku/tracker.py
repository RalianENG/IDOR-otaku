"""ID Tracker core logic."""

import json
import hashlib
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse, parse_qs

from mitmproxy import http, ctx

try:
    from .config import load_config, IdotakuConfig
except ImportError:
    # 直接実行時（mitmproxy -s tracker.py）
    from config import load_config, IdotakuConfig


@dataclass
class IDOccurrence:
    """IDの出現情報"""

    id_value: str
    id_type: str  # "numeric", "uuid", "token"
    location: str  # "url_path", "query", "body", "header"
    field_name: Optional[str]
    url: str
    method: str
    timestamp: str
    direction: str  # "request" or "response"


@dataclass
class TrackedID:
    """追跡対象のID"""

    value: str
    id_type: str
    first_seen: str
    origin: Optional[IDOccurrence] = None
    usages: list[IDOccurrence] = field(default_factory=list)


@dataclass
class FlowRecord:
    """リクエスト-レスポンスのペア"""

    flow_id: str
    url: str
    method: str
    timestamp: str
    request_ids: list[dict] = field(default_factory=list)   # [{value, type, location, field}]
    response_ids: list[dict] = field(default_factory=list)  # [{value, type, location, field}]
    auth_context: dict | None = None  # {"auth_type": str, "token_hash": str}


class IDTracker:
    """APIコールからIDを追跡するmitmproxyアドオン"""

    def __init__(self, config: IdotakuConfig | None = None):
        self.tracked_ids: dict[str, TrackedID] = {}
        self.request_log: list[IDOccurrence] = []
        self.response_log: list[IDOccurrence] = []
        self.flow_records: dict[str, FlowRecord] = {}  # flow_id -> FlowRecord
        self._use_ctx = True  # mitmproxy context available
        self._config_path: str | None = "__uninitialized__"  # sentinel value

        # 設定を適用
        self._apply_config(config or IdotakuConfig())

    def _apply_config(self, config: IdotakuConfig):
        """設定を適用"""
        self.config = config
        self.min_numeric = config.min_numeric
        self.output_file = config.output
        self.patterns = config.get_compiled_patterns()
        self.exclude_patterns = config.get_compiled_exclude_patterns()
        self.trackable_content_types = config.trackable_content_types
        self.ignore_headers = config.get_all_ignore_headers()
        self.target_domains = config.target_domains
        self.exclude_domains = config.exclude_domains

    def _should_track_url(self, url: str) -> bool:
        """URLを追跡すべきかチェック（ドメイン・拡張子フィルタリング）"""
        parsed = urlparse(url)
        domain = parsed.netloc.split(":")[0]  # ポート番号を除去

        # ドメインチェック
        if not self.config.should_track_domain(domain):
            return False

        # 拡張子チェック
        if not self.config.should_track_path(parsed.path):
            return False

        return True

    def load(self, loader):
        """mitmproxy addon loader."""
        loader.add_option(
            name="idotaku_config",
            typespec=str,
            default="",
            help="Path to idotaku config file (YAML)",
        )
        loader.add_option(
            name="idotaku_output",
            typespec=str,
            default="",
            help="Output file for ID tracking report (overrides config)",
        )
        loader.add_option(
            name="idotaku_min_numeric",
            typespec=int,
            default=0,
            help="Minimum value for numeric IDs to track (overrides config)",
        )

    def configure(self, updates):
        """mitmproxy configuration update."""
        # 設定ファイルが指定されたら読み込む
        if "idotaku_config" in updates:
            config_path = ctx.options.idotaku_config or None
            if config_path != self._config_path:
                self._config_path = config_path
                config = load_config(config_path)
                self._apply_config(config)
                self._log("info", f"[IDOTAKU] Config loaded: {config_path or 'default'}")
                self._log("info", f"[IDOTAKU] target_domains: {self.target_domains}")
                self._log("info", f"[IDOTAKU] exclude_extensions: {self.config.exclude_extensions[:5]}...")

        # コマンドラインオプションで上書き
        if "idotaku_output" in updates and ctx.options.idotaku_output:
            self.output_file = ctx.options.idotaku_output
        if "idotaku_min_numeric" in updates and ctx.options.idotaku_min_numeric > 0:
            self.min_numeric = ctx.options.idotaku_min_numeric

    def _log(self, level: str, message: str):
        """Log message."""
        if self._use_ctx:
            try:
                if level == "info":
                    ctx.log.info(message)
                elif level == "warn":
                    ctx.log.warn(message)
                elif level == "error":
                    ctx.log.error(message)
            except Exception:
                print(f"[{level.upper()}] {message}")
        else:
            print(f"[{level.upper()}] {message}")

    def _should_exclude(self, value: str) -> bool:
        """除外すべき値かチェック"""
        for pattern in self.exclude_patterns:
            if pattern.match(value):
                return True
        return False

    def _extract_ids_from_text(self, text: str) -> list[tuple[str, str]]:
        """テキストからIDを抽出"""
        found_ids = []

        for id_type, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                value = match.group()
                if not self._should_exclude(value):
                    if id_type == "numeric":
                        try:
                            if int(value) < self.min_numeric:
                                continue
                        except ValueError:
                            continue
                    found_ids.append((value, id_type))

        return found_ids

    def _extract_ids_from_json(self, data, prefix="") -> list[tuple[str, str, str]]:
        """JSONからIDとフィールド名を抽出"""
        found_ids = []

        if isinstance(data, dict):
            for key, value in data.items():
                field_path = f"{prefix}.{key}" if prefix else key
                if isinstance(value, (str, int)):
                    str_value = str(value)
                    for id_value, id_type in self._extract_ids_from_text(str_value):
                        found_ids.append((id_value, id_type, field_path))
                elif isinstance(value, (dict, list)):
                    found_ids.extend(self._extract_ids_from_json(value, field_path))
        elif isinstance(data, list):
            for i, item in enumerate(data):
                field_path = f"{prefix}[{i}]"
                found_ids.extend(self._extract_ids_from_json(item, field_path))

        return found_ids

    def _parse_body(self, content: bytes, content_type: str) -> Optional[dict | str]:
        """ボディをパース"""
        if not content:
            return None

        try:
            if "application/json" in content_type:
                return json.loads(content.decode("utf-8", errors="ignore"))
            else:
                return content.decode("utf-8", errors="ignore")
        except Exception:
            return None

    def _record_id(self, occurrence: IDOccurrence):
        """IDを記録"""
        id_value = occurrence.id_value

        if id_value not in self.tracked_ids:
            self.tracked_ids[id_value] = TrackedID(
                value=id_value,
                id_type=occurrence.id_type,
                first_seen=occurrence.timestamp,
            )

        tracked = self.tracked_ids[id_value]

        if occurrence.direction == "response":
            self.response_log.append(occurrence)
            if tracked.origin is None:
                tracked.origin = occurrence
                self._log("info", f"[ID ORIGIN] {occurrence.id_type}: {id_value} @ {occurrence.url}")
        else:
            self.request_log.append(occurrence)
            tracked.usages.append(occurrence)
            self._log(
                "info",
                f"[ID USAGE] {occurrence.id_type}: {id_value} @ {occurrence.method} {occurrence.url}",
            )

    def _collect_ids_from_url(self, url: str) -> list[dict]:
        """URLからIDを収集して返す"""
        found = []
        parsed = urlparse(url)

        for id_value, id_type in self._extract_ids_from_text(parsed.path):
            found.append({"value": id_value, "type": id_type, "location": "url_path", "field": None})

        query_params = parse_qs(parsed.query)
        for param_name, values in query_params.items():
            for value in values:
                for id_value, id_type in self._extract_ids_from_text(value):
                    found.append({"value": id_value, "type": id_type, "location": "query", "field": param_name})

        return found

    def _collect_ids_from_body(self, body: bytes, content_type: str) -> list[dict]:
        """ボディからIDを収集して返す"""
        found = []
        parsed = self._parse_body(body, content_type)
        if parsed is None:
            return found

        if isinstance(parsed, (dict, list)):
            for id_value, id_type, field_name in self._extract_ids_from_json(parsed):
                found.append({"value": id_value, "type": id_type, "location": "body", "field": field_name})
        elif isinstance(parsed, str):
            for id_value, id_type in self._extract_ids_from_text(parsed):
                found.append({"value": id_value, "type": id_type, "location": "body", "field": None})

        return found

    def _collect_ids_from_headers(self, headers) -> list[dict]:
        """ヘッダーからIDを収集して返す（ブラックリスト以外）"""
        found = []

        for header_name, header_value in headers.items():
            # 除外ヘッダーはスキップ
            if header_name.lower() in self.ignore_headers:
                continue

            # Cookie は key=value をパース
            if header_name.lower() == "cookie":
                for cookie_part in header_value.split(";"):
                    cookie_part = cookie_part.strip()
                    if "=" in cookie_part:
                        cookie_name, cookie_value = cookie_part.split("=", 1)
                        for id_value, id_type in self._extract_ids_from_text(cookie_value):
                            found.append({
                                "value": id_value,
                                "type": id_type,
                                "location": "header",
                                "field": f"cookie:{cookie_name.strip()}",
                            })
            # Set-Cookie も同様
            elif header_name.lower() == "set-cookie":
                cookie_part = header_value.split(";")[0]  # 最初の key=value だけ
                if "=" in cookie_part:
                    cookie_name, cookie_value = cookie_part.split("=", 1)
                    for id_value, id_type in self._extract_ids_from_text(cookie_value):
                        found.append({
                            "value": id_value,
                            "type": id_type,
                            "location": "header",
                            "field": f"set-cookie:{cookie_name.strip()}",
                        })
            # Authorization は Bearer トークン等を抽出
            elif header_name.lower() == "authorization":
                # "Bearer xxx" や "Basic xxx" から値部分を抽出
                parts = header_value.split(" ", 1)
                auth_value = parts[1] if len(parts) > 1 else header_value
                for id_value, id_type in self._extract_ids_from_text(auth_value):
                    found.append({
                        "value": id_value,
                        "type": id_type,
                        "location": "header",
                        "field": f"authorization:{parts[0].lower()}" if len(parts) > 1 else "authorization",
                    })
            # その他のヘッダーはそのまま値を抽出
            else:
                for id_value, id_type in self._extract_ids_from_text(header_value):
                    found.append({
                        "value": id_value,
                        "type": id_type,
                        "location": "header",
                        "field": header_name.lower(),
                    })

        return found

    def _extract_auth_context(self, headers) -> dict | None:
        """リクエストヘッダーから認証コンテキストを抽出"""
        auth_header = headers.get("authorization", "")
        if auth_header:
            parts = auth_header.split(" ", 1)
            auth_type = parts[0] if parts else "Unknown"
            token = parts[1] if len(parts) > 1 else auth_header
            token_hash = hashlib.sha256(token.encode()).hexdigest()[:8]
            return {"auth_type": auth_type, "token_hash": token_hash}

        cookie_header = headers.get("cookie", "")
        if cookie_header:
            session_names = {"session", "sessionid", "sid", "session_id", "jsessionid", "phpsessid"}
            for part in cookie_header.split(";"):
                part = part.strip()
                if "=" in part:
                    name, value = part.split("=", 1)
                    if name.strip().lower() in session_names:
                        token_hash = hashlib.sha256(value.encode()).hexdigest()[:8]
                        return {"auth_type": "Cookie", "token_hash": token_hash}

        return None

    def _process_url(self, url: str, method: str, direction: str, timestamp: str):
        """URLからIDを抽出"""
        parsed = urlparse(url)

        for id_value, id_type in self._extract_ids_from_text(parsed.path):
            self._record_id(
                IDOccurrence(
                    id_value=id_value,
                    id_type=id_type,
                    location="url_path",
                    field_name=None,
                    url=url,
                    method=method,
                    timestamp=timestamp,
                    direction=direction,
                )
            )

        query_params = parse_qs(parsed.query)
        for param_name, values in query_params.items():
            for value in values:
                for id_value, id_type in self._extract_ids_from_text(value):
                    self._record_id(
                        IDOccurrence(
                            id_value=id_value,
                            id_type=id_type,
                            location="query",
                            field_name=param_name,
                            url=url,
                            method=method,
                            timestamp=timestamp,
                            direction=direction,
                        )
                    )

    def _process_body(
        self, body: bytes, content_type: str, url: str, method: str, direction: str, timestamp: str
    ):
        """ボディからIDを抽出"""
        parsed = self._parse_body(body, content_type)
        if parsed is None:
            return

        if isinstance(parsed, (dict, list)):
            for id_value, id_type, field_name in self._extract_ids_from_json(parsed):
                self._record_id(
                    IDOccurrence(
                        id_value=id_value,
                        id_type=id_type,
                        location="body",
                        field_name=field_name,
                        url=url,
                        method=method,
                        timestamp=timestamp,
                        direction=direction,
                    )
                )
        elif isinstance(parsed, str):
            for id_value, id_type in self._extract_ids_from_text(parsed):
                self._record_id(
                    IDOccurrence(
                        id_value=id_value,
                        id_type=id_type,
                        location="body",
                        field_name=None,
                        url=url,
                        method=method,
                        timestamp=timestamp,
                        direction=direction,
                    )
                )

    def request(self, flow: http.HTTPFlow):
        """リクエストを処理"""
        url = flow.request.pretty_url

        # ドメインフィルタリング
        if not self._should_track_url(url):
            return

        timestamp = datetime.now().isoformat()
        method = flow.request.method
        flow_id = flow.id

        # FlowRecordを作成
        if flow_id not in self.flow_records:
            self.flow_records[flow_id] = FlowRecord(
                flow_id=flow_id,
                url=url,
                method=method,
                timestamp=timestamp,
            )

        # 認証コンテキストを抽出
        auth_ctx = self._extract_auth_context(flow.request.headers)
        if auth_ctx:
            self.flow_records[flow_id].auth_context = auth_ctx

        # IDを収集
        found_ids = []
        found_ids.extend(self._collect_ids_from_url(url))
        found_ids.extend(self._collect_ids_from_headers(flow.request.headers))

        content_type = flow.request.headers.get("content-type", "")
        if any(ct in content_type for ct in self.trackable_content_types):
            found_ids.extend(self._collect_ids_from_body(flow.request.content, content_type))

        # FlowRecordに追加 & TrackedIDに記録
        for id_info in found_ids:
            self.flow_records[flow_id].request_ids.append(id_info)
            self._record_id(IDOccurrence(
                id_value=id_info["value"],
                id_type=id_info["type"],
                location=id_info["location"],
                field_name=id_info.get("field"),
                url=url,
                method=method,
                timestamp=timestamp,
                direction="request",
            ))

    def response(self, flow: http.HTTPFlow):
        """レスポンスを処理"""
        url = flow.request.pretty_url

        # ドメインフィルタリング
        if not self._should_track_url(url):
            return

        timestamp = datetime.now().isoformat()
        method = flow.request.method
        flow_id = flow.id

        # FlowRecordがなければ作成（通常はrequestで作成済み）
        if flow_id not in self.flow_records:
            self.flow_records[flow_id] = FlowRecord(
                flow_id=flow_id,
                url=url,
                method=method,
                timestamp=timestamp,
            )

        # IDを収集
        found_ids = []
        found_ids.extend(self._collect_ids_from_headers(flow.response.headers))

        content_type = flow.response.headers.get("content-type", "")
        if any(ct in content_type for ct in self.trackable_content_types):
            found_ids.extend(self._collect_ids_from_body(flow.response.content, content_type))

        # FlowRecordに追加 & TrackedIDに記録
        for id_info in found_ids:
            self.flow_records[flow_id].response_ids.append(id_info)
            self._record_id(IDOccurrence(
                id_value=id_info["value"],
                id_type=id_info["type"],
                location=id_info["location"],
                field_name=id_info.get("field"),
                url=url,
                method=method,
                timestamp=timestamp,
                direction="response",
            ))

    def done(self):
        """終了時にレポートを出力"""
        report = self.generate_report()

        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        self._log("info", f"[IDOTAKU] Report saved to {self.output_file}")
        self.print_summary()

    def generate_report(self) -> dict:
        """レポートを生成"""
        report = {
            "summary": {
                "total_unique_ids": len(self.tracked_ids),
                "ids_with_origin": sum(1 for t in self.tracked_ids.values() if t.origin),
                "ids_with_usage": sum(1 for t in self.tracked_ids.values() if t.usages),
                "total_flows": len(self.flow_records),
            },
            "flows": [],
            "tracked_ids": {},
            "potential_idor": [],
        }

        # Flow単位のレポート
        for flow_id, flow_rec in self.flow_records.items():
            flow_dict = {
                "flow_id": flow_rec.flow_id,
                "method": flow_rec.method,
                "url": flow_rec.url,
                "timestamp": flow_rec.timestamp,
                "request_ids": flow_rec.request_ids,
                "response_ids": flow_rec.response_ids,
            }
            if flow_rec.auth_context:
                flow_dict["auth_context"] = flow_rec.auth_context
            report["flows"].append(flow_dict)

        for id_value, tracked in self.tracked_ids.items():
            report["tracked_ids"][id_value] = {
                "type": tracked.id_type,
                "first_seen": tracked.first_seen,
                "origin": self._occurrence_to_dict(tracked.origin) if tracked.origin else None,
                "usage_count": len(tracked.usages),
                "usages": [self._occurrence_to_dict(u) for u in tracked.usages],
            }

            if tracked.usages and not tracked.origin:
                report["potential_idor"].append(
                    {
                        "id_value": id_value,
                        "id_type": tracked.id_type,
                        "usages": [self._occurrence_to_dict(u) for u in tracked.usages],
                        "reason": "ID used in request but never seen in response",
                    }
                )

        return report

    def _occurrence_to_dict(self, occ: IDOccurrence) -> dict:
        """IDOccurrenceを辞書に変換"""
        return {
            "url": occ.url,
            "method": occ.method,
            "location": occ.location,
            "field_name": occ.field_name,
            "timestamp": occ.timestamp,
        }

    def print_summary(self):
        """サマリーを出力"""
        self._log("info", "=" * 60)
        self._log("info", "[IDOTAKU] Summary")
        self._log("info", "=" * 60)
        self._log("info", f"Total unique IDs tracked: {len(self.tracked_ids)}")

        potential_idor = [
            (id_val, tracked)
            for id_val, tracked in self.tracked_ids.items()
            if tracked.usages and not tracked.origin
        ]

        if potential_idor:
            self._log("warn", f"[!] Potential IDOR targets: {len(potential_idor)}")
            for id_val, tracked in potential_idor[:10]:
                self._log("warn", f"    - {tracked.id_type}: {id_val}")


# mitmproxy addon entry point
addons = [IDTracker()]
