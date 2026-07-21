"""Schema da identidade autenticada atual (`GET /me`).

Distinto de `UserRead` (app.api.schemas.administration): aquele e o
formato de item de uma listagem administrativa (exige papel de admin para
ser consultado); este e o "quem sou eu" que QUALQUER usuario autenticado
pode ler sobre si mesmo, usado pelo frontend para decidir quais itens de
menu/rota exibir de acordo com o papel. A ocultacao de menus e apenas
conveniencia visual; o backend continua responsavel pela autorizacao
efetiva.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class CurrentUserRead(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    external_subject: str
    full_name: str
    role: str
