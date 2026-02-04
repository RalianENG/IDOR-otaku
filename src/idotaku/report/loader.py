"""Report loading functionality."""

import json
import sys
from pathlib import Path
from typing import Union

from .models import ReportData, ReportSummary


def load_report(report_file: Union[str, Path]) -> ReportData:
    """Load and parse a report file.

    Args:
        report_file: Path to the JSON report file

    Returns:
        ReportData instance with parsed data
    """
    report_path = Path(report_file)

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in report file '{report_path}': {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Error: Cannot read report file '{report_path}': {e}", file=sys.stderr)
        sys.exit(1)

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
