"""Report loading and analysis for idotaku."""

from .loader import load_report
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

__all__ = [
    "load_report",
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
]
