"""Data models for idotaku reports."""

from dataclasses import dataclass, field
from typing import Optional


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
    tracked_ids: dict[str, dict]  # Raw dict for compatibility
    flows: list[dict]  # Raw dict for compatibility
    potential_idor: list[dict]  # Raw dict for compatibility

    # Cached derived data
    _sorted_flows: list[dict] = field(default_factory=list, repr=False)
    _idor_values: set[str] = field(default_factory=set, repr=False)

    def __post_init__(self):
        """Initialize cached derived data."""
        self._sorted_flows = sorted(
            self.flows, key=lambda x: x.get("timestamp", "")
        )
        self._idor_values = {
            item.get("id_value", "") for item in self.potential_idor
            if item.get("id_value")
        }

    @property
    def sorted_flows(self) -> list[dict]:
        """Get flows sorted by timestamp."""
        return self._sorted_flows

    @property
    def idor_values(self) -> set[str]:
        """Get set of potential IDOR ID values."""
        return self._idor_values

    def is_idor(self, id_value: str) -> bool:
        """Check if an ID is a potential IDOR target."""
        return id_value in self._idor_values
