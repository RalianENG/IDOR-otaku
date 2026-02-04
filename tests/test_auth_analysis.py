"""Tests for auth context analysis."""

import json

import pytest

from idotaku.report.auth_analysis import (
    detect_cross_user_access,
    enrich_idor_with_auth,
    CrossUserAccess,
)


@pytest.fixture
def flows_with_cross_user():
    """Flows where two users access the same resource with the same ID."""
    return [
        {
            "method": "GET",
            "url": "https://api.example.com/users/12345",
            "timestamp": "2024-01-01T10:00:00",
            "request_ids": [{"value": "12345", "type": "numeric", "location": "url_path"}],
            "response_ids": [],
            "auth_context": {"auth_type": "Bearer", "token_hash": "aabbccdd"},
        },
        {
            "method": "GET",
            "url": "https://api.example.com/users/12345",
            "timestamp": "2024-01-01T10:01:00",
            "request_ids": [{"value": "12345", "type": "numeric", "location": "url_path"}],
            "response_ids": [],
            "auth_context": {"auth_type": "Bearer", "token_hash": "eeff0011"},
        },
    ]


@pytest.fixture
def flows_single_user():
    """Flows where the same user accesses a resource."""
    return [
        {
            "method": "GET",
            "url": "https://api.example.com/users/12345",
            "timestamp": "2024-01-01T10:00:00",
            "request_ids": [{"value": "12345", "type": "numeric", "location": "url_path"}],
            "response_ids": [],
            "auth_context": {"auth_type": "Bearer", "token_hash": "aabbccdd"},
        },
        {
            "method": "GET",
            "url": "https://api.example.com/users/12345",
            "timestamp": "2024-01-01T10:01:00",
            "request_ids": [{"value": "12345", "type": "numeric", "location": "url_path"}],
            "response_ids": [],
            "auth_context": {"auth_type": "Bearer", "token_hash": "aabbccdd"},
        },
    ]


class TestDetectCrossUserAccess:
    def test_no_auth_context(self):
        flows = [
            {
                "method": "GET", "url": "https://api.example.com/users/123",
                "request_ids": [{"value": "123", "type": "numeric", "location": "url_path"}],
                "response_ids": [],
            },
        ]
        result = detect_cross_user_access(flows)
        assert len(result) == 0

    def test_single_user_no_detection(self, flows_single_user):
        result = detect_cross_user_access(flows_single_user)
        assert len(result) == 0

    def test_cross_user_detected(self, flows_with_cross_user):
        result = detect_cross_user_access(flows_with_cross_user)
        assert len(result) == 1
        assert result[0].id_value == "12345"
        assert len(result[0].auth_tokens) == 2

    def test_different_ids_no_cross_user(self):
        flows = [
            {
                "method": "GET", "url": "https://api.example.com/users/111",
                "request_ids": [{"value": "111", "type": "numeric", "location": "url_path"}],
                "response_ids": [],
                "auth_context": {"auth_type": "Bearer", "token_hash": "aabbccdd"},
            },
            {
                "method": "GET", "url": "https://api.example.com/users/222",
                "request_ids": [{"value": "222", "type": "numeric", "location": "url_path"}],
                "response_ids": [],
                "auth_context": {"auth_type": "Bearer", "token_hash": "eeff0011"},
            },
        ]
        result = detect_cross_user_access(flows)
        assert len(result) == 0

    def test_empty_flows(self):
        result = detect_cross_user_access([])
        assert len(result) == 0


class TestEnrichIdorWithAuth:
    def test_adds_cross_user_flag(self, flows_with_cross_user):
        findings = [
            {"id_value": "12345", "id_type": "numeric", "reason": "test", "usages": []},
        ]
        cross_user = detect_cross_user_access(flows_with_cross_user)
        enriched = enrich_idor_with_auth(findings, cross_user)

        assert enriched[0]["cross_user"] is True
        assert len(enriched[0]["auth_tokens"]) == 2

    def test_no_cross_user(self, flows_single_user):
        findings = [
            {"id_value": "12345", "id_type": "numeric", "reason": "test", "usages": []},
        ]
        cross_user = detect_cross_user_access(flows_single_user)
        enriched = enrich_idor_with_auth(findings, cross_user)

        assert "cross_user" not in enriched[0]

    def test_does_not_mutate_original(self, flows_with_cross_user):
        findings = [
            {"id_value": "12345", "id_type": "numeric", "reason": "test", "usages": []},
        ]
        cross_user = detect_cross_user_access(flows_with_cross_user)
        enrich_idor_with_auth(findings, cross_user)

        # Original should not be modified
        assert "cross_user" not in findings[0]
