"""Registro real dos processadores de modalidade (item 11).

Substitui o dict vazio usado pelo worker no item 10
(`app.orchestrator.worker.process_next_message` ja aceita
`processors: dict[ModalityType, ModalityProcessor]`; ate aqui, nada era
passado). `scripts/run_orchestrator_worker.py` importa `PROCESSORS` deste
modulo.
"""

from __future__ import annotations

from app.core.enums import ModalityType
from app.orchestrator.worker import ModalityProcessor
from app.processors.audio import process_audio_modality
from app.processors.image import process_image_modality
from app.processors.text import process_text_modality
from app.processors.video import process_video_modality

PROCESSORS: dict[ModalityType, ModalityProcessor] = {
    ModalityType.TEXT: process_text_modality,
    ModalityType.AUDIO: process_audio_modality,
    ModalityType.IMAGE: process_image_modality,
    ModalityType.VIDEO: process_video_modality,
}
