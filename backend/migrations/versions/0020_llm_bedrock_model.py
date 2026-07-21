"""feature_flags: modelo Amazon Bedrock

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-17

Novo campo `llm_bedrock_model` na linha singleton de feature flags, para
o adaptador real de LLM via Amazon Bedrock (`app.integrations.llm.
bedrock_adapter.BedrockLlmAdapter`) - alternativa a `OpenAiLlmAdapter`
dentro do mesmo Protocol `LlmAdapter`, selecionavel via
`llm_provider=BEDROCK` (novo valor do enum `LlmProvider`).

Mesmo padrao de `llm_openai_model` (migration 0017): o modelo e escolhido
na tela `/admin/feature-flags`, nunca fixo em codigo.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEFAULT_MODEL = "anthropic.claude-3-5-sonnet-20241022-v2:0"


def upgrade() -> None:
    op.add_column(
        "feature_flags",
        sa.Column(
            "llm_bedrock_model",
            sa.String(length=200),
            nullable=False,
            server_default=_DEFAULT_MODEL,
        ),
    )
    # server_default so para preencher a linha singleton ja existente sem
    # erro de NOT NULL; remove depois para o modelo ORM permanecer a fonte
    # de verdade do valor em novas inserts (mesmo padrao da migration 0018).
    op.alter_column("feature_flags", "llm_bedrock_model", server_default=None)


def downgrade() -> None:
    op.drop_column("feature_flags", "llm_bedrock_model")
