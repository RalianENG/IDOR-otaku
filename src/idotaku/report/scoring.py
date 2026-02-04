"""Risk scoring for IDOR findings."""

from dataclasses import dataclass, field


@dataclass
class RiskScore:
    """Risk assessment for an IDOR finding."""

    score: int          # 0-100
    level: str          # "critical", "high", "medium", "low"
    factors: list[str] = field(default_factory=list)


# Scoring weights
METHOD_WEIGHTS: dict[str, int] = {
    "DELETE": 30,
    "PUT": 25,
    "PATCH": 20,
    "POST": 15,
    "GET": 5,
}

LOCATION_WEIGHTS: dict[str, int] = {
    "url_path": 20,
    "path": 20,
    "query": 15,
    "body": 10,
    "header": 5,
}

ID_TYPE_WEIGHTS: dict[str, int] = {
    "numeric": 15,
    "uuid": 5,
    "token": 3,
}


def _level_from_score(score: int) -> str:
    """Map numeric score to risk level."""
    if score >= 75:
        return "critical"
    elif score >= 50:
        return "high"
    elif score >= 25:
        return "medium"
    else:
        return "low"


def score_idor_finding(finding: dict) -> RiskScore:
    """Score a single IDOR finding.

    Args:
        finding: Dict with keys id_value, id_type, reason, usages

    Returns:
        RiskScore with score (0-100), level, and factors
    """
    score = 0
    factors: list[str] = []
    usages = finding.get("usages", [])

    # Factor 1: HTTP method (highest weight across usages)
    methods = {u.get("method", "GET") for u in usages}
    if methods:
        best_method = max(methods, key=lambda m: METHOD_WEIGHTS.get(m, 5))
        method_score = METHOD_WEIGHTS.get(best_method, 5)
        score += method_score
        factors.append(f"method={best_method}(+{method_score})")

    # Factor 2: Parameter location (highest weight)
    locations = {u.get("location", "body") for u in usages}
    if locations:
        best_loc = max(locations, key=lambda loc: LOCATION_WEIGHTS.get(loc, 5))
        loc_score = LOCATION_WEIGHTS.get(best_loc, 5)
        score += loc_score
        factors.append(f"location={best_loc}(+{loc_score})")

    # Factor 3: ID type
    id_type = finding.get("id_type", "token")
    type_score = ID_TYPE_WEIGHTS.get(id_type, 3)
    score += type_score
    factors.append(f"type={id_type}(+{type_score})")

    # Factor 4: Usage count
    usage_count = len(usages)
    usage_score = min(usage_count * 5, 20)
    score += usage_score
    factors.append(f"usages={usage_count}(+{usage_score})")

    # Factor 5: Multiple endpoints
    unique_urls = {u.get("url", "") for u in usages}
    if len(unique_urls) > 1:
        multi_score = min(len(unique_urls) * 3, 15)
        score += multi_score
        factors.append(f"endpoints={len(unique_urls)}(+{multi_score})")

    score = min(score, 100)

    return RiskScore(
        score=score,
        level=_level_from_score(score),
        factors=factors,
    )


def score_all_findings(potential_idor: list[dict]) -> list[dict]:
    """Score all IDOR findings and return enriched list.

    Returns:
        List with added risk_score, risk_level, risk_factors keys,
        sorted by score descending.
    """
    scored = []
    for finding in potential_idor:
        risk = score_idor_finding(finding)
        enriched = {
            **finding,
            "risk_score": risk.score,
            "risk_level": risk.level,
            "risk_factors": risk.factors,
        }
        scored.append(enriched)

    scored.sort(key=lambda x: x.get("risk_score", 0), reverse=True)
    return scored
