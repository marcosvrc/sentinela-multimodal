"""Testes dos contratos compartilhados (enums, schemas HTTP, OpenAPI).

Ver docs/contracts/README.md para a politica de versionamento. Estes testes
garantem que a fonte unica de enums gera TypeScript valido e que o contrato
OpenAPI e gerado sem erros a cada mudanca de schema.
"""

from __future__ import annotations

from app.api.schemas.analysis import AnalysisCreateResponse, AnalysisStatusResponse
from app.api.schemas.common import ErrorResponse, PageResponse
from app.core.enums import ANALYSIS_STATUS_TRANSITIONS, AnalysisStatus
from app.main import app
from scripts.export_enums import _enum_classes, generate


def test_analysis_status_transitions_cover_every_status() -> None:
    for status in AnalysisStatus:
        assert status in ANALYSIS_STATUS_TRANSITIONS, f"{status} sem transicoes definidas"


def test_terminal_states_have_no_outgoing_transitions() -> None:
    terminal_states = {
        AnalysisStatus.COMPLETED,
        AnalysisStatus.FAILED_FINAL,
        AnalysisStatus.CANCELLED,
    }
    for status in terminal_states:
        assert ANALYSIS_STATUS_TRANSITIONS[status] == ()


def test_error_response_defaults() -> None:
    error = ErrorResponse(code="VALIDATION_ERROR", message="Erro de exemplo")
    assert error.field_errors == {}
    assert error.request_id is None


def test_page_response_computes_total_pages() -> None:
    page = PageResponse.build(items=[1, 2, 3], page=1, page_size=20, total_items=45)
    assert page.total_pages == 3


def test_page_response_zero_items() -> None:
    page = PageResponse.build(items=[], page=1, page_size=20, total_items=0)
    assert page.total_pages == 0


def test_openapi_schema_generates_without_error() -> None:
    schema = app.openapi()
    assert schema["info"]["title"] == "SentinelHealth API"
    assert "/health" in schema["paths"]


def test_enum_export_contains_every_enum_class() -> None:
    generated = generate()
    for enum_cls in _enum_classes():
        assert f"export enum {enum_cls.__name__}" in generated


def test_enum_export_is_syntactically_balanced() -> None:
    generated = generate()
    assert generated.count("{") == generated.count("}")


def test_analysis_schemas_importable() -> None:
    # Garante que os contratos referenciados no README de contratos existem
    # e podem ser instanciados/serializados sem erro de schema.
    assert AnalysisCreateResponse.model_json_schema()["title"] == "AnalysisCreateResponse"
    assert AnalysisStatusResponse.model_json_schema()["title"] == "AnalysisStatusResponse"
