"""Report loading functionality."""

import json
from pathlib import Path
from typing import Union

from .models import ReportData, ReportSummary


def load_report(report_file: Union[str, Path]) -> ReportData:
    """Load and parse a report file.

    Args:
        report_file: Path to the JSON report file

    Returns:
        ReportData instance with parsed data

    Raises:
        FileNotFoundError: If the report file doesn't exist
        json.JSONDecodeError: If the file is not valid JSON
    """
    report_path = Path(report_file)

    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Parse summary
    summary_data = data.get("summary", {})
    summary = ReportSummary(
        total_unique_ids=summary_data.get("total_unique_ids", 0),
        ids_with_origin=summary_data.get("ids_with_origin", 0),
        ids_with_usage=summary_data.get("ids_with_usage", 0),
        total_flows=summary_data.get("total_flows", 0),
    )

    return ReportData(
        summary=summary,
        tracked_ids=data.get("tracked_ids", {}),
        flows=data.get("flows", []),
        potential_idor=data.get("potential_idor", []),
    )
