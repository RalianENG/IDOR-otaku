"""Report loading functionality."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Union

from .models import ReportData, ReportSummary


class ReportLoadError(Exception):
    """Exception raised when report loading fails."""

    pass


def load_report(
    report_file: Union[str, Path],
    *,
    exit_on_error: bool = True,
) -> ReportData:
    """Load and parse a report file.

    Args:
        report_file: Path to the JSON report file
        exit_on_error: If True (default), print error and exit on failure.
                       If False, raise ReportLoadError instead.

    Returns:
        ReportData instance with parsed data

    Raises:
        ReportLoadError: If exit_on_error is False and loading fails
    """
    report_path = Path(report_file)

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON in report file '{report_path}': {e}"
        if exit_on_error:
            print(f"Error: {msg}", file=sys.stderr)
            sys.exit(1)
        raise ReportLoadError(msg) from e
    except OSError as e:
        msg = f"Cannot read report file '{report_path}': {e}"
        if exit_on_error:
            print(f"Error: {msg}", file=sys.stderr)
            sys.exit(1)
        raise ReportLoadError(msg) from e

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
