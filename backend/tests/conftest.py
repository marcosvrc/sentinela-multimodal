from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def pytest_configure(config: pytest.Config) -> None:
    """Trava de seguranca: recusa rodar a suite contra um banco que nao
    pareca ser um banco de teste dedicado.

    Varios testes (ex.: `test_analysis_clinical_support_api.py`,
    `test_administration_api.py`) fazem seed/commit direto no banco
    (`ClinicalRuleSet`, `Patient`, etc.) sem teardown - correto para um
    banco de teste descartavel, mas perigoso contra o banco de
    desenvolvimento (os dados de teste ficam la para sempre e poluem
    telas como "Dados clinicos (regras)"). `make test`/`make
    test-integration` ja exportam `DATABASE_URL` apontando para
    `TEST_DATABASE_URL` (ver Makefile); esta checagem cobre quem rodar
    `pytest` direto sem passar pelo Makefile.
    """
    database_name = get_settings().database_url.path or ""
    database_name = database_name.lstrip("/")
    if "test" not in database_name.lower():
        raise pytest.UsageError(
            f"DATABASE_URL aponta para o banco '{database_name}', que nao parece ser um "
            "banco de teste (esperado algo como 'sentinelhealth_test'). Varios testes "
            "gravam dados permanentemente sem limpeza - rodar contra o banco de "
            "desenvolvimento polui as telas da aplicacao. Use 'make test' / 'make "
            "test-integration' (que ja apontam para TEST_DATABASE_URL), ou exporte "
            "DATABASE_URL manualmente para um banco de teste antes de rodar pytest."
        )


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())
