"""Diff analysis between two idotaku reports."""

from dataclasses import dataclass, field

from .models import ReportData


@dataclass
class DiffResult:
    """Structured diff between two reports."""

    # IDOR changes
    new_idor: list[dict] = field(default_factory=list)
    removed_idor: list[dict] = field(default_factory=list)
    unchanged_idor: list[dict] = field(default_factory=list)

    # Tracked ID changes
    new_ids: list[str] = field(default_factory=list)
    removed_ids: list[str] = field(default_factory=list)

    # Flow count changes
    flow_count_a: int = 0
    flow_count_b: int = 0

    # Summary stats
    id_count_a: int = 0
    id_count_b: int = 0

    @property
    def has_changes(self) -> bool:
        """Check if there are any differences."""
        return bool(
            self.new_idor or self.removed_idor
            or self.new_ids or self.removed_ids
            or self.flow_count_a != self.flow_count_b
        )


def diff_reports(report_a: ReportData, report_b: ReportData) -> DiffResult:
    """Compare two reports and find differences.

    Args:
        report_a: The "before" report
        report_b: The "after" report

    Returns:
        DiffResult with all changes
    """
    # Compare IDOR findings by id_value
    idor_a = {item["id_value"]: item for item in report_a.potential_idor}
    idor_b = {item["id_value"]: item for item in report_b.potential_idor}

    new_idor = [idor_b[k] for k in idor_b if k not in idor_a]
    removed_idor = [idor_a[k] for k in idor_a if k not in idor_b]
    unchanged_idor = [idor_b[k] for k in idor_b if k in idor_a]

    # Compare tracked IDs
    ids_a = set(report_a.tracked_ids.keys())
    ids_b = set(report_b.tracked_ids.keys())

    return DiffResult(
        new_idor=new_idor,
        removed_idor=removed_idor,
        unchanged_idor=unchanged_idor,
        new_ids=sorted(ids_b - ids_a),
        removed_ids=sorted(ids_a - ids_b),
        flow_count_a=report_a.summary.total_flows,
        flow_count_b=report_b.summary.total_flows,
        id_count_a=report_a.summary.total_unique_ids,
        id_count_b=report_b.summary.total_unique_ids,
    )


def diff_to_dict(diff: DiffResult) -> dict:
    """Convert DiffResult to a serializable dict."""
    return {
        "has_changes": diff.has_changes,
        "idor": {
            "new": diff.new_idor,
            "removed": diff.removed_idor,
            "unchanged_count": len(diff.unchanged_idor),
        },
        "tracked_ids": {
            "new": diff.new_ids,
            "removed": diff.removed_ids,
        },
        "flows": {
            "before": diff.flow_count_a,
            "after": diff.flow_count_b,
            "delta": diff.flow_count_b - diff.flow_count_a,
        },
        "ids": {
            "before": diff.id_count_a,
            "after": diff.id_count_b,
            "delta": diff.id_count_b - diff.id_count_a,
        },
    }
