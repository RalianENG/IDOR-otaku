"""Report loading and analysis for idotaku."""

from .loader import load_report, ReportLoadError
from .models import ReportData, ReportSummary
from .scoring import score_idor_finding, score_all_findings, RiskScore
from .diff import diff_reports, diff_to_dict, DiffResult
from .auth_analysis import (
    detect_cross_user_access,
    enrich_idor_with_auth,
    CrossUserAccess,
)

# Public API — only symbols listed here are part of the stable interface.
# Internal helpers (models, analysis functions) should be imported
# directly from their submodules (e.g. from idotaku.report.analysis import ...).
__all__ = [
    # Core
    "load_report",
    "ReportLoadError",
    "ReportData",
    "ReportSummary",
    # Scoring
    "score_idor_finding",
    "score_all_findings",
    "RiskScore",
    # Diff
    "diff_reports",
    "diff_to_dict",
    "DiffResult",
    # Auth analysis
    "detect_cross_user_access",
    "enrich_idor_with_auth",
    "CrossUserAccess",
]
