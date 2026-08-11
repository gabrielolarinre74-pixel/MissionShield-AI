"""Tests for the health endpoint."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_returns_ok(test_client):
    response = await test_client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "MissionShield API"
    assert "version" in body


@pytest.mark.asyncio
async def test_health_does_not_expose_secrets(test_client):
    response = await test_client.get("/api/health")
    text = response.text
    # Ensure no secret-looking values appear in the health response.
    for forbidden in ["APIKEY", "api_key", "password", "secret", "token"]:
        assert forbidden.lower() not in text.lower(), (
            f"Health response must not contain '{forbidden}'"
        )
