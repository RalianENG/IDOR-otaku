"""CSV exporter for idotaku reports."""

import csv
from pathlib import Path
from typing import Union

from ..report.models import ReportData


def export_idor_csv(
    output_path: Union[str, Path],
    report_data: ReportData,
) -> None:
    """Export IDOR candidates to CSV.

    Columns: id_value, id_type, method, url, location, field, reason
    """
    fieldnames = ["id_value", "id_type", "method", "url", "location", "field", "reason"]

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for finding in report_data.potential_idor:
            for usage in finding.get("usages", []):
                writer.writerow({
                    "id_value": finding.get("id_value", ""),
                    "id_type": finding.get("id_type", ""),
                    "method": usage.get("method", ""),
                    "url": usage.get("url", ""),
                    "location": usage.get("location", ""),
                    "field": usage.get("field", usage.get("field_name", "")),
                    "reason": finding.get("reason", ""),
                })


def export_flows_csv(
    output_path: Union[str, Path],
    report_data: ReportData,
) -> None:
    """Export flow records to CSV.

    Columns: timestamp, method, url, request_id_count, response_id_count, request_ids, response_ids
    """
    fieldnames = [
        "timestamp", "method", "url",
        "request_id_count", "response_id_count",
        "request_ids", "response_ids",
    ]

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for flow in report_data.sorted_flows:
            req_ids = flow.get("request_ids", [])
            res_ids = flow.get("response_ids", [])
            writer.writerow({
                "timestamp": flow.get("timestamp", ""),
                "method": flow.get("method", ""),
                "url": flow.get("url", ""),
                "request_id_count": len(req_ids),
                "response_id_count": len(res_ids),
                "request_ids": "; ".join(i.get("value", "") for i in req_ids),
                "response_ids": "; ".join(i.get("value", "") for i in res_ids),
            })


def export_csv(
    output_path: Union[str, Path],
    report_data: ReportData,
    mode: str = "idor",
) -> None:
    """Export report data to CSV.

    Args:
        output_path: Path to output CSV file
        report_data: ReportData instance
        mode: "idor" for IDOR candidates, "flows" for flow records
    """
    if mode == "idor":
        export_idor_csv(output_path, report_data)
    elif mode == "flows":
        export_flows_csv(output_path, report_data)
    else:
        raise ValueError(f"Unknown export mode: {mode}")
