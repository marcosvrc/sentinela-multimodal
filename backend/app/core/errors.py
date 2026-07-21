"""Padrao uniforme de erro da API."""

from __future__ import annotations

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """Erro de dominio convertido em resposta HTTP estavel.

    Nunca deve carregar detalhes internos (stack trace, DSN, ARN etc).
    """

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        field_errors: dict[str, str] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.field_errors = field_errors or {}
        super().__init__(message)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "field_errors": exc.field_errors,
            "request_id": _request_id(request),
        },
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    field_errors: dict[str, str] = {}
    for error in exc.errors():
        field = ".".join(str(part) for part in error["loc"] if part != "body")
        field_errors[field or "_"] = error["msg"]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": "VALIDATION_ERROR",
            "message": "Nao foi possivel validar os dados enviados.",
            "field_errors": field_errors,
            "request_id": _request_id(request),
        },
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: ARG001
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": "INTERNAL_ERROR",
            "message": "Erro interno inesperado.",
            "field_errors": {},
            "request_id": _request_id(request),
        },
    )
