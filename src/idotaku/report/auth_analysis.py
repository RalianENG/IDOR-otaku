"""Auth context analysis for cross-user IDOR detection."""

from collections import defaultdict
from dataclasses import dataclass, field

from ..utils.url import normalize_api_path


@dataclass
class CrossUserAccess:
    """A case where different auth contexts access the same resource with the same ID."""

    id_value: str
    url_pattern: str
    auth_tokens: list[str] = field(default_factory=list)
    flows: list[dict] = field(default_factory=list)


def detect_cross_user_access(flows: list[dict]) -> list[CrossUserAccess]:
    """Detect cases where different auth tokens access the same resource with the same ID.

    Args:
        flows: List of flow record dicts (with optional auth_context)

    Returns:
        List of CrossUserAccess instances
    """
    access_map: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"tokens": set(), "flows": []}
    )

    for flow in flows:
        auth = flow.get("auth_context")
        if not auth or not auth.get("token_hash"):
            continue

        token_hash = auth["token_hash"]

        for req_id in flow.get("request_ids", []):
            id_value = req_id.get("value", "")
            if not id_value:
                continue
            url = flow.get("url", "")
            method = flow.get("method", "?")
            url_pattern = f"{method} {normalize_api_path(url)}"

            key = (id_value, url_pattern)
            access_map[key]["tokens"].add(token_hash)
            access_map[key]["flows"].append(flow)

    # Filter to cases with multiple auth tokens
    results = []
    for (id_value, url_pattern), data in access_map.items():
        if len(data["tokens"]) > 1:
            results.append(CrossUserAccess(
                id_value=id_value,
                url_pattern=url_pattern,
                auth_tokens=sorted(data["tokens"]),
                flows=data["flows"],
            ))

    return results


def enrich_idor_with_auth(
    potential_idor: list[dict],
    cross_user_accesses: list[CrossUserAccess],
) -> list[dict]:
    """Enrich IDOR findings with cross-user access info.

    Adds 'cross_user': True and 'auth_tokens' to findings that
    show cross-user access patterns.
    """
    cross_user_map = {ca.id_value: ca for ca in cross_user_accesses}

    enriched = []
    for finding in potential_idor:
        finding = {**finding}
        id_val = finding.get("id_value", "")
        if id_val and id_val in cross_user_map:
            ca = cross_user_map[id_val]
            finding["cross_user"] = True
            finding["auth_tokens"] = ca.auth_tokens
        enriched.append(finding)

    return enriched
