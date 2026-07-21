"""Loop do worker do orquestrador (item 10 do backlog).

Uso:
    uv run python -m scripts.run_orchestrator_worker           # loop continuo
    uv run python -m scripts.run_orchestrator_worker --once    # uma mensagem e sai

Usa os processadores reais registrados em `app.processors.registry` (item
11): TEXT, AUDIO, IMAGE e VIDEO produzem achados estruturais genuinos
(dimensao, duracao, tamanho de texto); nenhum deles faz reconhecimento de
conteudo (isso depende de integracao futura com LLM/Transcribe/visao).
"""

from __future__ import annotations

import argparse
import time

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.logging import configure_logging
from app.orchestrator.worker import process_next_message
from app.processors.registry import PROCESSORS
from app.queue import get_queue_adapter

# Mesma configuracao de log (JSON estruturado) usada pela API em
# `app/main.py` - sem isso, `logging.getLogger(...).info(...)` chamado
# pelos processadores/adaptadores (ex.: `AwsRekognitionImageAdapter`) nao
# aparece na saida do worker (o logger raiz do Python, sem handler
# configurado, so imprime WARNING+ via o "last resort handler").
configure_logging(get_settings().log_level)

POLL_INTERVAL_SECONDS = 2


def run(*, once: bool) -> None:
    queue = get_queue_adapter()
    while True:
        session = SessionLocal()
        try:
            outcome = process_next_message(session, queue, PROCESSORS)
        finally:
            session.close()

        if outcome is not None:
            modalidades = ", ".join(
                f"{result.modality_type}({result.status})" for result in outcome.modality_results
            )
            print(
                f"[processado] analysis_id={outcome.analysis_id} "
                f"final_status={outcome.final_status.value} "
                f"modalidades=[{modalidades}]"
            )
        elif once:
            print("Nenhuma mensagem na fila.")

        if once:
            return
        if outcome is None:
            time.sleep(POLL_INTERVAL_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Processa uma mensagem e sai")
    args = parser.parse_args()
    run(once=args.once)


if __name__ == "__main__":
    main()
