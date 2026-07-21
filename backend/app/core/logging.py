"""Logging estruturado (JSON) sem conteudo clinico por padrao.

Os logs propagam identificadores de correlacao e nao contem nome de
paciente, prontuario, transcricao, prompt completo, midia ou resultado
clinico integral.
"""

from __future__ import annotations

import logging
import sys

from pythonjsonlogger import jsonlogger


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s "
        "%(request_id)s %(analysis_id)s %(workflow_id)s %(job_id)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
        defaults={
            "request_id": None,
            "analysis_id": None,
            "workflow_id": None,
            "job_id": None,
        },
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
