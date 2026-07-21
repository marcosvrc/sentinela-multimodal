from __future__ import annotations

from fastapi.testclient import TestClient


def test_healthz_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_healthz_propagates_request_id(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-Id": "req_test123"})
    assert response.headers["X-Request-Id"] == "req_test123"


def test_unknown_route_returns_404(client: TestClient) -> None:
    response = client.get("/does-not-exist")
    assert response.status_code == 404
