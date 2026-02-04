"""Tests for risk scoring."""

from idotaku.report.scoring import score_idor_finding, score_all_findings, RiskScore


class TestScoreIdorFinding:
    def test_delete_method_high_score(self):
        finding = {
            "id_value": "123",
            "id_type": "numeric",
            "reason": "test",
            "usages": [
                {"method": "DELETE", "url": "https://api.example.com/users/123", "location": "url_path"},
            ],
        }
        result = score_idor_finding(finding)
        assert result.score >= 50  # DELETE(30) + url_path(20) + numeric(15) + usages(5) = 70

    def test_get_method_low_score(self):
        finding = {
            "id_value": "abc-uuid",
            "id_type": "uuid",
            "reason": "test",
            "usages": [
                {"method": "GET", "url": "https://api.example.com/items/abc", "location": "body"},
            ],
        }
        result = score_idor_finding(finding)
        assert result.score < 50  # GET(5) + body(10) + uuid(5) + usages(5) = 25

    def test_path_location_higher_than_body(self):
        finding_path = {
            "id_value": "1",
            "id_type": "numeric",
            "reason": "test",
            "usages": [{"method": "GET", "url": "x", "location": "url_path"}],
        }
        finding_body = {
            "id_value": "1",
            "id_type": "numeric",
            "reason": "test",
            "usages": [{"method": "GET", "url": "x", "location": "body"}],
        }
        score_path = score_idor_finding(finding_path).score
        score_body = score_idor_finding(finding_body).score
        assert score_path > score_body

    def test_numeric_higher_than_uuid(self):
        finding_numeric = {
            "id_value": "123",
            "id_type": "numeric",
            "reason": "test",
            "usages": [{"method": "GET", "url": "x", "location": "body"}],
        }
        finding_uuid = {
            "id_value": "abc-def",
            "id_type": "uuid",
            "reason": "test",
            "usages": [{"method": "GET", "url": "x", "location": "body"}],
        }
        score_numeric = score_idor_finding(finding_numeric).score
        score_uuid = score_idor_finding(finding_uuid).score
        assert score_numeric > score_uuid

    def test_multiple_usages_increase_score(self):
        finding_one = {
            "id_value": "1",
            "id_type": "numeric",
            "reason": "test",
            "usages": [{"method": "GET", "url": "x", "location": "body"}],
        }
        finding_many = {
            "id_value": "1",
            "id_type": "numeric",
            "reason": "test",
            "usages": [
                {"method": "GET", "url": "x", "location": "body"},
                {"method": "GET", "url": "x", "location": "body"},
                {"method": "GET", "url": "x", "location": "body"},
            ],
        }
        assert score_idor_finding(finding_many).score > score_idor_finding(finding_one).score

    def test_score_capped_at_100(self):
        finding = {
            "id_value": "1",
            "id_type": "numeric",
            "reason": "test",
            "usages": [
                {"method": "DELETE", "url": f"https://api{i}.example.com/x", "location": "url_path"}
                for i in range(20)
            ],
        }
        result = score_idor_finding(finding)
        assert result.score <= 100

    def test_level_critical(self):
        finding = {
            "id_value": "1", "id_type": "numeric", "reason": "test",
            "usages": [
                {"method": "DELETE", "url": f"https://api{i}.com/x", "location": "url_path"}
                for i in range(5)
            ],
        }
        result = score_idor_finding(finding)
        assert result.level == "critical"

    def test_level_low(self):
        finding = {
            "id_value": "tok", "id_type": "token", "reason": "test",
            "usages": [{"method": "GET", "url": "x", "location": "header"}],
        }
        result = score_idor_finding(finding)
        assert result.level in ("low", "medium")

    def test_factors_populated(self):
        finding = {
            "id_value": "1", "id_type": "numeric", "reason": "test",
            "usages": [{"method": "GET", "url": "x", "location": "body"}],
        }
        result = score_idor_finding(finding)
        assert len(result.factors) >= 3


class TestScoreAllFindings:
    def test_returns_sorted_by_score(self):
        findings = [
            {
                "id_value": "low", "id_type": "token", "reason": "t",
                "usages": [{"method": "GET", "url": "x", "location": "header"}],
            },
            {
                "id_value": "high", "id_type": "numeric", "reason": "t",
                "usages": [{"method": "DELETE", "url": "x", "location": "url_path"}],
            },
        ]
        result = score_all_findings(findings)
        assert result[0]["id_value"] == "high"
        assert result[0]["risk_score"] >= result[1]["risk_score"]

    def test_enriches_with_risk_fields(self):
        findings = [
            {
                "id_value": "1", "id_type": "numeric", "reason": "t",
                "usages": [{"method": "GET", "url": "x", "location": "body"}],
            },
        ]
        result = score_all_findings(findings)
        assert "risk_score" in result[0]
        assert "risk_level" in result[0]
        assert "risk_factors" in result[0]

    def test_empty_list(self):
        result = score_all_findings([])
        assert result == []
