"""Contrato HTTP das rotas de submissao/cancelamento/retentativa (item 10).

Fluxo completo (com banco) ja e exercitado em tests/test_orchestrator.py
via `app.orchestrator.service` diretamente; aqui cobrimos apenas o
contrato HTTP (autenticacao) que nao exige Postgres.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_submit_without_auth_header_returns_401(client: TestClient) -> None:
    response = client.post(f"/analyses/{uuid.uuid4()}/submit")
    assert response.status_code == 401
    assert response.json()["code"] == "MISSING_AUTH_CONTEXT"


def test_cancel_without_auth_header_returns_401(client: TestClient) -> None:
    response = client.post(f"/analyses/{uuid.uuid4()}/cancel")
    assert response.status_code == 401


def test_retry_without_auth_header_returns_401(client: TestClient) -> None:
    response = client.post(f"/analyses/{uuid.uuid4()}/retry")
    assert response.status_code == 401


def test_list_modalities_without_auth_header_returns_401(client: TestClient) -> None:
    response = client.get(f"/analyses/{uuid.uuid4()}/modalities")
    assert response.status_code == 401
