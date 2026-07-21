"""Schemas HTTP compartilhados.

Todo endpoint da API usa estes contratos para erro e paginacao, evitando
formatos divergentes entre modulos.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorResponse(BaseModel):
    """Formato uniforme de erro. Ver app.core.errors.ApiError."""

    code: str = Field(..., description="Codigo estavel do erro, ex: VALIDATION_ERROR")
    message: str
    field_errors: dict[str, str] = Field(default_factory=dict)
    request_id: str | None = None


class PageParams(BaseModel):
    """Parametros de paginacao aceitos por endpoints de listagem."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PageResponse(BaseModel, Generic[T]):
    """Envelope de resposta paginada."""

    items: list[T]
    page: int
    page_size: int
    total_items: int
    total_pages: int

    @classmethod
    def build(cls, items: list[T], page: int, page_size: int, total_items: int) -> PageResponse[T]:
        total_pages = (total_items + page_size - 1) // page_size if page_size else 0
        return cls(
            items=items,
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
        )
