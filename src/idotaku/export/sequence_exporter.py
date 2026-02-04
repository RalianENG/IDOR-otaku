"""Sequence diagram HTML exporter for idotaku."""

import json
from pathlib import Path
from typing import Union
from urllib.parse import urlparse

from ..utils.url import normalize_api_path, extract_domain
from .sequence_styles import SEQUENCE_STYLES
from .sequence_scripts import SEQUENCE_SCRIPTS


def _build_lifeline_key(flow: dict) -> str:
    """Build a lifeline key from a flow (domain + normalized path)."""
    url = flow.get("url", "")
    domain = extract_domain(url)
    normalized = normalize_api_path(url)
    method = flow.get("method", "?")
    if domain:
        return f"{method} {domain}{normalized}"
    return f"{method} {normalized}"


def _build_sequence_data(
    sorted_flows: list[dict],
    tracked_ids: dict,
    potential_idor: list[dict],
    max_lifelines: int = 10,
) -> dict:
    """Build JSON-serializable data for the sequence diagram.

    Args:
        sorted_flows: List of flow records sorted by timestamp
        tracked_ids: Tracked ID information from report
        potential_idor: Potential IDOR targets from report
        max_lifelines: Maximum number of endpoint lifelines to show

    Returns:
        Dictionary ready for JSON serialization
    """
    if not sorted_flows:
        return {
            "flows": [],
            "lifelines": ["Client"],
            "flow_lifeline_map": [],
            "idor_values": [],
            "id_info": {},
        }

    # Count flows per lifeline key to find top endpoints
    lifeline_counts: dict[str, int] = {}
    flow_keys: list[str] = []

    for flow in sorted_flows:
        key = _build_lifeline_key(flow)
        flow_keys.append(key)
        lifeline_counts[key] = lifeline_counts.get(key, 0) + 1

    # Sort by frequency, take top N
    sorted_lifelines = sorted(lifeline_counts.items(), key=lambda x: x[1], reverse=True)

    if len(sorted_lifelines) > max_lifelines:
        top_keys = {k for k, _ in sorted_lifelines[:max_lifelines]}
        lifeline_list = ["Client"] + [k for k, _ in sorted_lifelines[:max_lifelines]] + ["Other"]
        other_index = len(lifeline_list) - 1
    else:
        top_keys = {k for k, _ in sorted_lifelines}
        lifeline_list = ["Client"] + [k for k, _ in sorted_lifelines]
        other_index = None

    # Map lifeline keys to column indices
    lifeline_index_map: dict[str, int] = {}
    for i, ll in enumerate(lifeline_list):
        if ll != "Client" and ll != "Other":
            lifeline_index_map[ll] = i

    # Map each flow to its lifeline column
    flow_lifeline_map: list[int] = []
    for key in flow_keys:
        if key in lifeline_index_map:
            flow_lifeline_map.append(lifeline_index_map[key])
        elif other_index is not None:
            flow_lifeline_map.append(other_index)
        else:
            # Shouldn't happen, but fallback to last column
            flow_lifeline_map.append(len(lifeline_list) - 1)

    # Build flow data with path info
    flows_data = []
    for flow in sorted_flows:
        url = flow.get("url", "")
        parsed_path = urlparse(url).path or "/"
        flows_data.append({
            "method": flow.get("method", "?"),
            "url": url,
            "path": parsed_path,
            "timestamp": flow.get("timestamp", ""),
            "request_ids": flow.get("request_ids", []),
            "response_ids": flow.get("response_ids", []),
        })

    # Build IDOR values list
    idor_values = [item.get("id_value", "") for item in potential_idor]

    # Build ID info for summary panel
    id_info: dict[str, dict] = {}

    # Collect all ID values seen across all flows
    for i, flow in enumerate(sorted_flows):
        for res_id in flow.get("response_ids", []):
            val = res_id.get("value", "")
            if val and val not in id_info:
                id_info[val] = {
                    "type": res_id.get("type", "?"),
                    "origin_flow": i,
                    "usage_count": 0,
                }
        for req_id in flow.get("request_ids", []):
            val = req_id.get("value", "")
            if val:
                if val not in id_info:
                    id_info[val] = {
                        "type": req_id.get("type", "?"),
                        "origin_flow": None,
                        "usage_count": 0,
                    }
                id_info[val]["usage_count"] += 1

    # Supplement with tracked_ids data
    for id_val, id_data in tracked_ids.items():
        if id_val not in id_info:
            id_info[id_val] = {
                "type": id_data.get("type", "?"),
                "origin_flow": None,
                "usage_count": 0,
            }
        if "type" in id_data:
            id_info[id_val]["type"] = id_data["type"]

    return {
        "flows": flows_data,
        "lifelines": lifeline_list,
        "flow_lifeline_map": flow_lifeline_map,
        "idor_values": idor_values,
        "id_info": id_info,
    }


def export_sequence_html(
    output_path: Union[str, Path],
    sorted_flows: list[dict],
    tracked_ids: dict,
    potential_idor: list[dict],
) -> None:
    """Export sequence diagram to interactive HTML.

    Args:
        output_path: Path to output HTML file
        sorted_flows: List of flow records sorted by timestamp
        tracked_ids: Tracked ID information from report
        potential_idor: Potential IDOR targets from report
    """
    seq_data = _build_sequence_data(sorted_flows, tracked_ids, potential_idor)
    seq_json = json.dumps(seq_data)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>idotaku - API Sequence Diagram</title>
    <style>
{SEQUENCE_STYLES}
    </style>
</head>
<body>
    <div class="seq-panel">
        <h1>API Sequence Diagram</h1>
        <div class="security-warning">
            <strong>Warning:</strong> This report may contain sensitive data extracted from intercepted HTTP traffic
            (tokens, session IDs, API keys, cookies). Do not share this file publicly.
        </div>
        <div class="subtitle">Click any ID chip to highlight all occurrences across the timeline</div>
        <div id="seq-header" class="seq-header"></div>
        <div id="seq-body" class="seq-body"></div>
    </div>

    <div class="id-summary-panel" id="id-summary">
        <div class="panel-header">
            <span class="panel-title"></span>
            <span class="panel-close" onclick="clearHighlight()">&times;</span>
        </div>
        <div class="panel-row">
            <span class="panel-label">Type</span>
            <span class="panel-value" id="summary-type"></span>
        </div>
        <div class="panel-row">
            <span class="panel-label">Origin</span>
            <span class="panel-value" id="summary-origin"></span>
        </div>
        <div class="panel-row">
            <span class="panel-label">Used in requests</span>
            <span class="panel-value" id="summary-usage"></span>
        </div>
        <span class="idor-badge" id="summary-idor" style="display:none">Potential IDOR</span>
    </div>

    <div class="hint" id="hint">Click any ID chip to trace parameter flow</div>

    <script>
{SEQUENCE_SCRIPTS.replace("{sequence_json}", seq_json)}
    </script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
