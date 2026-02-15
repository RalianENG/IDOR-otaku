"""Data models for idotaku reports."""

from dataclasses import dataclass, field
from typing import Optional, TypedDict


class FlowIDDict(TypedDict, total=False):
    """TypedDict for flow ID data."""

    value: str
    type: str
    location: str
    field: Optional[str]


class UsageDict(TypedDict, total=False):
    """TypedDict for ID usage data."""

    url: str
    method: str
    location: str
    field_name: Optional[str]
    timestamp: str


class TrackedIDDict(TypedDict, total=False):
    """TypedDict for tracked ID data in report."""

    type: str
    first_seen: str
    origin: Optional[UsageDict]
    usage_count: int
    usages: list[UsageDict]


class AuthContextDict(TypedDict, total=False):
    """TypedDict for auth context data."""

    auth_type: str
    token_hash: str


class FlowDict(TypedDict, total=False):
    """TypedDict for flow record data."""

    flow_id: str
    method: str
    url: str
    timestamp: str
    request_ids: list[FlowIDDict]
    response_ids: list[FlowIDDict]
    auth_context: Optional[AuthContextDict]
    request_headers: dict[str, str]
    request_body: Optional[str]
    status_code: int
    response_headers: dict[str, str]
    response_body: Optional[str]


class IDORFindingDict(TypedDict, total=False):
    """TypedDict for IDOR finding data."""

    id_value: str
    id_type: str
    usages: list[UsageDict]
    reason: str
    risk_score: int
    risk_level: str
    risk_factors: list[str]
    cross_user: bool
    auth_tokens: list[str]


@dataclass
class IDOccurrence:
    """ID occurrence in request/response."""

    url: str
    method: str
    location: str  # "url_path", "query", "body", "header"
    field_name: Optional[str]
    timestamp: str


@dataclass
class TrackedID:
    """Tracked ID information."""

    value: str
    id_type: str  # "numeric", "uuid", "token"
    first_seen: str
    origin: Optional[IDOccurrence] = None
    usages: list[IDOccurrence] = field(default_factory=list)


@dataclass
class FlowID:
    """ID found in a flow."""

    value: str
    type: str
    location: str
    field: Optional[str] = None


@dataclass
class FlowRecord:
    """Single HTTP flow record."""

    flow_id: str
    method: str
    url: str
    timestamp: str
    request_ids: list[FlowID] = field(default_factory=list)
    response_ids: list[FlowID] = field(default_factory=list)


@dataclass
class IDORTarget:
    """Potential IDOR target."""

    id_value: str
    id_type: str
    usages: list[IDOccurrence]
    reason: str


@dataclass
class ReportSummary:
    """Report summary statistics."""

    total_unique_ids: int = 0
    ids_with_origin: int = 0
    ids_with_usage: int = 0
    total_flows: int = 0


@dataclass
class ReportData:
    """Complete report data container."""

    summary: ReportSummary
    tracked_ids: dict[str, TrackedIDDict]
    flows: list[FlowDict]
    potential_idor: list[IDORFindingDict]

    # Cached derived data
    _sorted_flows: list[FlowDict] = field(default_factory=list, repr=False)
    _idor_values: set[str] = field(default_factory=set, repr=False)

    def __post_init__(self) -> None:
        """Initialize cached derived data."""
        self._sorted_flows = sorted(
            self.flows, key=lambda x: x.get("timestamp", "")
        )
        self._idor_values = {
            item.get("id_value", "") for item in self.potential_idor
            if item.get("id_value")
        }

    @property
    def sorted_flows(self) -> list[FlowDict]:
        """Get flows sorted by timestamp."""
        return self._sorted_flows

    @property
    def idor_values(self) -> set[str]:
        """Get set of potential IDOR ID values."""
        return self._idor_values

    def is_idor(self, id_value: str) -> bool:
        """Check if an ID is a potential IDOR target."""
        return id_value in self._idor_values
