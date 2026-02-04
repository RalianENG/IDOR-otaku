"""HAR file importer for idotaku.

Parses HAR (HTTP Archive) JSON files and produces the same report
format as the mitmproxy tracker output.
"""

import json
import re
import uuid
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlparse, parse_qs

from .config import IdotakuConfig


def _should_exclude(value: str, exclude_patterns: list[re.Pattern]) -> bool:
    """Check if a value should be excluded."""
    for pattern in exclude_patterns:
        if pattern.match(value):
            return True
    return False


def _extract_ids_from_text(
    text: str,
    patterns: dict[str, re.Pattern],
    exclude_patterns: list[re.Pattern],
    min_numeric: int = 100,
) -> list[tuple[str, str]]:
    """Extract IDs from text using compiled patterns.

    Returns:
        List of (id_value, id_type) tuples
    """
    found = []
    for id_type, pattern in patterns.items():
        for match in pattern.finditer(text):
            value = match.group()
            if _should_exclude(value, exclude_patterns):
                continue
            if id_type == "numeric":
                try:
                    if int(value) < min_numeric:
                        continue
                except ValueError:
                    continue
            found.append((value, id_type))
    return found


def _extract_ids_from_json(
    data,
    patterns: dict[str, re.Pattern],
    exclude_patterns: list[re.Pattern],
    min_numeric: int,
    prefix: str = "",
) -> list[tuple[str, str, str]]:
    """Extract IDs from JSON data recursively.

    Returns:
        List of (id_value, id_type, field_path) tuples
    """
    found = []
    if isinstance(data, dict):
        for key, value in data.items():
            field_path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, (str, int)):
                for id_value, id_type in _extract_ids_from_text(
                    str(value), patterns, exclude_patterns, min_numeric
                ):
                    found.append((id_value, id_type, field_path))
            elif isinstance(value, (dict, list)):
                found.extend(_extract_ids_from_json(
                    value, patterns, exclude_patterns, min_numeric, field_path
                ))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            field_path = f"{prefix}[{i}]"
            found.extend(_extract_ids_from_json(
                item, patterns, exclude_patterns, min_numeric, field_path
            ))
    return found


def _collect_ids_from_url(
    url: str,
    patterns: dict[str, re.Pattern],
    exclude_patterns: list[re.Pattern],
    min_numeric: int,
) -> list[dict]:
    """Collect IDs from URL path and query parameters."""
    found = []
    parsed = urlparse(url)

    for id_value, id_type in _extract_ids_from_text(
        parsed.path, patterns, exclude_patterns, min_numeric
    ):
        found.append({"value": id_value, "type": id_type, "location": "url_path", "field": None})

    query_params = parse_qs(parsed.query)
    for param_name, values in query_params.items():
        for value in values:
            for id_value, id_type in _extract_ids_from_text(
                value, patterns, exclude_patterns, min_numeric
            ):
                found.append({"value": id_value, "type": id_type, "location": "query", "field": param_name})

    return found


def _collect_ids_from_body(
    body_text: str,
    content_type: str,
    patterns: dict[str, re.Pattern],
    exclude_patterns: list[re.Pattern],
    min_numeric: int,
) -> list[dict]:
    """Collect IDs from request/response body."""
    found = []
    if not body_text:
        return found

    if "application/json" in content_type:
        try:
            data = json.loads(body_text)
            for id_value, id_type, field_name in _extract_ids_from_json(
                data, patterns, exclude_patterns, min_numeric
            ):
                found.append({"value": id_value, "type": id_type, "location": "body", "field": field_name})
        except (json.JSONDecodeError, ValueError):
            for id_value, id_type in _extract_ids_from_text(
                body_text, patterns, exclude_patterns, min_numeric
            ):
                found.append({"value": id_value, "type": id_type, "location": "body", "field": None})
    else:
        for id_value, id_type in _extract_ids_from_text(
            body_text, patterns, exclude_patterns, min_numeric
        ):
            found.append({"value": id_value, "type": id_type, "location": "body", "field": None})

    return found


def _collect_ids_from_headers(
    headers: list[dict],
    patterns: dict[str, re.Pattern],
    exclude_patterns: list[re.Pattern],
    min_numeric: int,
    ignore_headers: set[str],
) -> list[dict]:
    """Collect IDs from HAR-format headers ([{name, value}])."""
    found = []
    for header in headers:
        name = header.get("name", "")
        value = header.get("value", "")
        name_lower = name.lower()

        if name_lower in ignore_headers:
            continue

        if name_lower == "cookie":
            for cookie_part in value.split(";"):
                cookie_part = cookie_part.strip()
                if "=" in cookie_part:
                    cookie_name, cookie_value = cookie_part.split("=", 1)
                    for id_value, id_type in _extract_ids_from_text(
                        cookie_value, patterns, exclude_patterns, min_numeric
                    ):
                        found.append({
                            "value": id_value, "type": id_type,
                            "location": "header", "field": f"cookie:{cookie_name.strip()}",
                        })
        elif name_lower == "set-cookie":
            cookie_part = value.split(";")[0]
            if "=" in cookie_part:
                cookie_name, cookie_value = cookie_part.split("=", 1)
                for id_value, id_type in _extract_ids_from_text(
                    cookie_value, patterns, exclude_patterns, min_numeric
                ):
                    found.append({
                        "value": id_value, "type": id_type,
                        "location": "header", "field": f"set-cookie:{cookie_name.strip()}",
                    })
        elif name_lower == "authorization":
            parts = value.split(" ", 1)
            auth_value = parts[1] if len(parts) > 1 else value
            for id_value, id_type in _extract_ids_from_text(
                auth_value, patterns, exclude_patterns, min_numeric
            ):
                field = f"authorization:{parts[0].lower()}" if len(parts) > 1 else "authorization"
                found.append({
                    "value": id_value, "type": id_type,
                    "location": "header", "field": field,
                })
        else:
            for id_value, id_type in _extract_ids_from_text(
                value, patterns, exclude_patterns, min_numeric
            ):
                found.append({
                    "value": id_value, "type": id_type,
                    "location": "header", "field": name_lower,
                })

    return found


def _parse_har_entry(
    entry: dict,
    patterns: dict[str, re.Pattern],
    exclude_patterns: list[re.Pattern],
    min_numeric: int,
    ignore_headers: set[str],
    config: IdotakuConfig,
) -> Optional[dict]:
    """Parse a single HAR entry into a flow record dict.

    Returns:
        Flow record dict, or None if the entry should be skipped.
    """
    request = entry.get("request", {})
    response = entry.get("response", {})
    url = request.get("url", "")

    # Domain filtering
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    if config.target_domains or config.exclude_domains:
        if not config.should_track_domain(domain):
            return None

    # Extension filtering
    if not config.should_track_path(parsed_url.path):
        return None

    timestamp = entry.get("startedDateTime", "")
    method = request.get("method", "GET")
    flow_id = str(uuid.uuid4())[:8]

    # Collect request IDs
    request_ids = []
    request_ids.extend(_collect_ids_from_url(url, patterns, exclude_patterns, min_numeric))
    request_ids.extend(_collect_ids_from_headers(
        request.get("headers", []), patterns, exclude_patterns, min_numeric, ignore_headers
    ))

    req_body = request.get("postData", {})
    if req_body:
        req_content_type = req_body.get("mimeType", "")
        req_text = req_body.get("text", "")
        if req_text and any(ct in req_content_type for ct in config.trackable_content_types):
            request_ids.extend(_collect_ids_from_body(
                req_text, req_content_type, patterns, exclude_patterns, min_numeric
            ))

    # Collect response IDs
    response_ids = []
    response_ids.extend(_collect_ids_from_headers(
        response.get("headers", []), patterns, exclude_patterns, min_numeric, ignore_headers
    ))

    res_content = response.get("content", {})
    if res_content:
        res_content_type = res_content.get("mimeType", "")
        res_text = res_content.get("text", "")
        if res_text and any(ct in res_content_type for ct in config.trackable_content_types):
            response_ids.extend(_collect_ids_from_body(
                res_text, res_content_type, patterns, exclude_patterns, min_numeric
            ))

    return {
        "flow_id": flow_id,
        "method": method,
        "url": url,
        "timestamp": timestamp,
        "request_ids": request_ids,
        "response_ids": response_ids,
    }


def _build_tracked_ids(flows: list[dict]) -> dict:
    """Build tracked_ids dict from flow records.

    Follows the same origin/usage logic as IDTracker:
    - Response IDs set the origin (first occurrence)
    - Request IDs are recorded as usages
    """
    tracked: dict[str, dict] = {}

    for flow in flows:
        timestamp = flow.get("timestamp", "")
        url = flow.get("url", "")
        method = flow.get("method", "")

        # Response IDs -> origin
        for id_info in flow.get("response_ids", []):
            value = id_info["value"]
            if value not in tracked:
                tracked[value] = {
                    "type": id_info["type"],
                    "first_seen": timestamp,
                    "origin": None,
                    "usage_count": 0,
                    "usages": [],
                }
            if tracked[value]["origin"] is None:
                tracked[value]["origin"] = {
                    "url": url,
                    "method": method,
                    "location": id_info["location"],
                    "field_name": id_info.get("field"),
                    "timestamp": timestamp,
                }

        # Request IDs -> usages
        for id_info in flow.get("request_ids", []):
            value = id_info["value"]
            if value not in tracked:
                tracked[value] = {
                    "type": id_info["type"],
                    "first_seen": timestamp,
                    "origin": None,
                    "usage_count": 0,
                    "usages": [],
                }
            usage = {
                "url": url,
                "method": method,
                "location": id_info["location"],
                "field_name": id_info.get("field"),
                "timestamp": timestamp,
            }
            tracked[value]["usages"].append(usage)
            tracked[value]["usage_count"] = len(tracked[value]["usages"])

    return tracked


def _build_potential_idor(tracked_ids: dict) -> list[dict]:
    """Build potential_idor list from tracked_ids.

    Same logic as IDTracker: IDs used in requests but never seen in responses.
    """
    idor = []
    for id_value, info in tracked_ids.items():
        if info["usages"] and info["origin"] is None:
            idor.append({
                "id_value": id_value,
                "id_type": info["type"],
                "usages": info["usages"],
                "reason": "ID used in request but never seen in response",
            })
    return idor


def import_har(
    har_path: Union[str, Path],
    config: Optional[IdotakuConfig] = None,
) -> dict:
    """Import a HAR file and produce a report dict.

    Args:
        har_path: Path to HAR JSON file
        config: Optional IdotakuConfig for ID extraction settings

    Returns:
        Report dict in the same format as IDTracker.generate_report()
    """
    config = config or IdotakuConfig()
    patterns = config.get_compiled_patterns()
    exclude_patterns = config.get_compiled_exclude_patterns()
    ignore_headers = config.get_all_ignore_headers()

    with open(har_path, "r", encoding="utf-8") as f:
        har_data = json.load(f)

    entries = har_data.get("log", {}).get("entries", [])

    # Parse entries into flows
    flows = []
    for entry in entries:
        flow = _parse_har_entry(
            entry, patterns, exclude_patterns,
            config.min_numeric, ignore_headers, config,
        )
        if flow is not None:
            flows.append(flow)

    # Sort by timestamp
    flows.sort(key=lambda x: x.get("timestamp", ""))

    # Build tracked IDs and detect IDOR
    tracked_ids = _build_tracked_ids(flows)
    potential_idor = _build_potential_idor(tracked_ids)

    return {
        "summary": {
            "total_unique_ids": len(tracked_ids),
            "ids_with_origin": sum(1 for t in tracked_ids.values() if t["origin"]),
            "ids_with_usage": sum(1 for t in tracked_ids.values() if t["usages"]),
            "total_flows": len(flows),
        },
        "flows": flows,
        "tracked_ids": tracked_ids,
        "potential_idor": potential_idor,
    }


def import_har_to_file(
    har_path: Union[str, Path],
    output_path: Union[str, Path],
    config: Optional[IdotakuConfig] = None,
) -> dict:
    """Import HAR and write report JSON file.

    Returns:
        The report dict
    """
    report = import_har(har_path, config)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report
