"""Report loading and analysis for idotaku."""

from .loader import load_report, ReportLoadError
from .models import (
    ReportData,
    ReportSummary,
    TrackedID,
    FlowRecord,
    FlowID,
    IDOccurrence,
    IDORTarget,
)
from .analysis import (
    build_param_producer_consumer,
    build_param_flow_mappings,
    build_flow_graph,
    build_api_dependencies,
    build_id_transition_map,
    find_chain_roots,
)
from .scoring import score_idor_finding, score_all_findings, RiskScore
from .diff import diff_reports, diff_to_dict, DiffResult
from .auth_analysis import (
    detect_cross_user_access,
    enrich_idor_with_auth,
    CrossUserAccess,
)

__all__ = [
    "load_report",
    "ReportLoadError",
    "ReportData",
    "ReportSummary",
    "TrackedID",
    "FlowRecord",
    "FlowID",
    "IDOccurrence",
    "IDORTarget",
    "build_param_producer_consumer",
    "build_param_flow_mappings",
    "build_flow_graph",
    "build_api_dependencies",
    "build_id_transition_map",
    "find_chain_roots",
    "score_idor_finding",
    "score_all_findings",
    "RiskScore",
    "diff_reports",
    "diff_to_dict",
    "DiffResult",
    "detect_cross_user_access",
    "enrich_idor_with_auth",
    "CrossUserAccess",
]
