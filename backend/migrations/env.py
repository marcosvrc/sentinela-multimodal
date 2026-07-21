"""Ambiente de execucao do Alembic.

A URL do banco vem exclusivamente de `Settings` (variaveis de ambiente /
Secrets Manager), nunca fixada no arquivo de configuracao versionado.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Importa os modelos para que fiquem registrados em Base.metadata
from app.administration import models as administration_models  # noqa: F401
from app.anomaly_detection import models as anomaly_detection_models  # noqa: F401
from app.audit import models as audit_models  # noqa: F401
from app.core.config import get_settings
from app.core.db_base import Base
from app.identity import models as identity_models  # noqa: F401
from app.media import models as media_models  # noqa: F401
from app.observations import models as observations_models  # noqa: F401
from app.orchestrator import models as orchestrator_models  # noqa: F401
from app.patients import models as patients_models  # noqa: F401
from app.processors import models as processors_models  # noqa: F401
from app.queue import models as queue_models  # noqa: F401
from app.reports import models as reports_models  # noqa: F401
from app.risk_consolidation import models as risk_consolidation_models  # noqa: F401
from app.rules_engine import models as rules_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()
config.set_main_option("sqlalchemy.url", str(settings.database_url))


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
