"""SARIF exporter for idotaku reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Union

from ..report.models import IDORFindingDict, ReportData

SARIF_VERSION: Final[str] = "2.1.0"
SARIF_SCHEMA: Final[str] = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json"

TOOL_NAME: Final[str] = "idotaku"

RULES: Final[list[dict[str, Any]]] = [
    {
        "id": "IDOR001",
        "name": "IDUsedWithoutOrigin",
        "shortDescription": {
            "text": "ID used in request but never seen in response",
        },
        "helpUri": "https://owasp.org/Top10/A01_2021-Broken_Access_Control/",
        "defaultConfiguration": {"level": "warning"},
    },
]


def _build_sarif_result(finding: IDORFindingDict) -> dict[str, Any]:
    """Build a single SARIF result from an IDOR finding."""
    usages = finding.get("usages", [])

    locations = []
    for usage in usages:
        locations.append({
            "physicalLocation": {
                "artifactLocation": {
                    "uri": usage.get("url", ""),
                },
            },
            "properties": {
                "method": usage.get("method", ""),
                "location": usage.get("location", ""),
                "field": usage.get("field", usage.get("field_name", "")),
            },
        })

    return {
        "ruleId": "IDOR001",
        "ruleIndex": 0,
        "level": "warning",
        "message": {
            "text": f"Potential IDOR: {finding.get('id_type', 'unknown')} ID "
                    f"'{finding.get('id_value', '?')}' - {finding.get('reason', '')}",
        },
        "locations": locations or [{
            "physicalLocation": {
                "artifactLocation": {"uri": "unknown"},
            },
        }],
        "properties": {
            "id_value": finding.get("id_value", ""),
            "id_type": finding.get("id_type", ""),
            "usage_count": len(usages),
        },
    }


def export_sarif(
    output_path: Union[str, Path],
    report_data: ReportData,
) -> None:
    """Export IDOR findings to SARIF 2.1.0 format."""
    from .. import __version__

    sarif = {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": TOOL_NAME,
                        "version": __version__,
                        "rules": RULES,
                    },
                },
                "results": [
                    _build_sarif_result(finding)
                    for finding in report_data.potential_idor
                ],
            },
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sarif, f, indent=2, ensure_ascii=False)
