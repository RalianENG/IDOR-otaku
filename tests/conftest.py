"""Pytest fixtures for idotaku tests."""

import json

import pytest


@pytest.fixture
def sample_report_data():
    """Sample report data for testing."""
    return {
        "summary": {
            "total_unique_ids": 5,
            "ids_with_origin": 4,
            "ids_with_usage": 3,
            "total_flows": 10,
        },
        "tracked_ids": {
            "12345": {
                "type": "numeric",
                "first_seen": "2024-01-01T10:00:00",
                "origin": {
                    "method": "POST",
                    "url": "https://api.example.com/users",
                    "location": "body",
                    "field": "id",
                    "timestamp": "2024-01-01T10:00:00",
                },
                "usages": [
                    {
                        "method": "GET",
                        "url": "https://api.example.com/users/12345",
                        "location": "path",
                        "field": None,
                        "timestamp": "2024-01-01T10:01:00",
                    },
                ],
            },
            "abc-def-123": {
                "type": "uuid",
                "first_seen": "2024-01-01T10:02:00",
                "origin": {
                    "method": "POST",
                    "url": "https://api.example.com/sessions",
                    "location": "body",
                    "field": "session_id",
                    "timestamp": "2024-01-01T10:02:00",
                },
                "usages": [],
            },
            "external_999": {
                "type": "numeric",
                "first_seen": "2024-01-01T10:03:00",
                "origin": None,
                "usages": [
                    {
                        "method": "GET",
                        "url": "https://api.example.com/items/999",
                        "location": "path",
                        "field": None,
                        "timestamp": "2024-01-01T10:03:00",
                    },
                ],
            },
        },
        "flows": [
            {
                "method": "POST",
                "url": "https://api.example.com/users",
                "timestamp": "2024-01-01T10:00:00",
                "request_ids": [],
                "response_ids": [
                    {"value": "12345", "type": "numeric", "location": "body", "field": "id"},
                ],
            },
            {
                "method": "GET",
                "url": "https://api.example.com/users/12345",
                "timestamp": "2024-01-01T10:01:00",
                "request_ids": [
                    {"value": "12345", "type": "numeric", "location": "path", "field": None},
                ],
                "response_ids": [
                    {"value": "67890", "type": "numeric", "location": "body", "field": "order_id"},
                ],
            },
            {
                "method": "POST",
                "url": "https://api.example.com/sessions",
                "timestamp": "2024-01-01T10:02:00",
                "request_ids": [],
                "response_ids": [
                    {"value": "abc-def-123", "type": "uuid", "location": "body", "field": "session_id"},
                ],
            },
            {
                "method": "GET",
                "url": "https://api.example.com/orders/67890",
                "timestamp": "2024-01-01T10:03:00",
                "request_ids": [
                    {"value": "67890", "type": "numeric", "location": "path", "field": None},
                ],
                "response_ids": [],
            },
        ],
        "potential_idor": [
            {
                "id_value": "external_999",
                "id_type": "numeric",
                "reason": "Used in request but no origin found",
                "usages": [
                    {
                        "method": "GET",
                        "url": "https://api.example.com/items/999",
                        "location": "path",
                    },
                ],
            },
        ],
    }


@pytest.fixture
def sample_report_file(sample_report_data, tmp_path):
    """Create a temporary report file for testing."""
    report_file = tmp_path / "test_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(sample_report_data, f)
    return report_file


@pytest.fixture
def empty_report_data():
    """Empty report data for edge case testing."""
    return {
        "summary": {
            "total_unique_ids": 0,
            "ids_with_origin": 0,
            "ids_with_usage": 0,
            "total_flows": 0,
        },
        "tracked_ids": {},
        "flows": [],
        "potential_idor": [],
    }


@pytest.fixture
def empty_report_file(empty_report_data, tmp_path):
    """Create an empty report file for testing."""
    report_file = tmp_path / "empty_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(empty_report_data, f)
    return report_file
