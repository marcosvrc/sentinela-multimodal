"""Processador da modalidade VIDEO.

Duracao real e calculada para MP4/MOV (`parse_isobmff_duration_seconds`,
ISO BMFF - `video/mp4` e `video/quicktime` sao os dois tipos aceitos por
`app.media.validation.ALLOWED_MIME_TYPES[VIDEO]`, ambos ISO BMFF).

Roda a **analise de visao computacional** (`app.integrations.vision`) quando
VISION_PROVIDER=OPENPOSE_YOLOV8 esta configurado. Quando LOCAL (padrao),
retorna "indisponivel" honestamente.

Adicionalmente, roda a **analise contextual via GPT-4 Vision** (sempre que
OPENAI_API_KEY esta configurada): extrai quadros do video via ffmpeg e
envia ao GPT-4o para descricao clinica contextualizada (expressao facial,
postura, sinais de dor/desconforto, movimentacao). Esta analise funciona
independentemente do VISION_PROVIDER - nao precisa de OpenPose nem YOLOv8.
"""

from __future__ import annotations

import base64
import logging
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.enums import FindingNature, ModalityQualityState, ModalityType, VisionAnalysisStatus
from app.integrations.vision import get_vision_adapter
from app.integrations.vision.base import VideoAnalysisRequest, VideoAnalysisResult
from app.orchestrator.models import AnalysisModalityState
from app.processors.base import load_approved_media_asset, record_finding
from app.processors.media_analysis import parse_isobmff_duration_seconds
from app.processors.quality import (
    MIN_VIDEO_SECONDS_ADEQUATE,
    MIN_VIDEO_SECONDS_MODERATE,
    assess_duration_based_quality,
)
from app.storage import get_storage_adapter

_logger = logging.getLogger(__name__)

_ISOBMFF_MIME_TYPES = ("video/mp4", "video/quicktime")
_MEDIA_FORMAT_BY_MIME = {"video/mp4": "mp4", "video/quicktime": "mov"}

# Tradução dos rótulos COCO (YOLOv8) para português
_YOLO_LABEL_PT: dict[str, str] = {
    "person": "pessoa",
    "bicycle": "bicicleta",
    "car": "carro",
    "motorcycle": "motocicleta",
    "bus": "ônibus",
    "truck": "caminhão",
    "traffic light": "semáforo",
    "bench": "banco",
    "bird": "pássaro",
    "cat": "gato",
    "dog": "cachorro",
    "horse": "cavalo",
    "backpack": "mochila",
    "umbrella": "guarda-chuva",
    "handbag": "bolsa",
    "suitcase": "mala",
    "bottle": "garrafa",
    "cup": "copo",
    "fork": "garfo",
    "knife": "faca",
    "spoon": "colher",
    "bowl": "tigela",
    "chair": "cadeira",
    "couch": "sofá",
    "bed": "cama/leito",
    "dining table": "mesa",
    "tv": "monitor/tela",
    "laptop": "notebook",
    "mouse": "mouse",
    "keyboard": "teclado",
    "cell phone": "celular",
    "microwave": "micro-ondas",
    "oven": "forno",
    "refrigerator": "geladeira",
    "book": "livro",
    "clock": "relógio",
    "scissors": "tesoura",
    "toothbrush": "escova de dentes",
    "sink": "pia",
    "toilet": "vaso sanitário",
}


def _translate_yolo_label(label: str) -> str:
    return _YOLO_LABEL_PT.get(label.lower(), label)


def _run_vision_analysis(
    db: Session,
    modality_state: AnalysisModalityState,
    *,
    content: bytes,
    storage_key: str,
    media_format: str,
    quality_state: ModalityQualityState,
) -> None:
    from app.core.config import get_settings

    adapter = get_vision_adapter(db)
    request = VideoAnalysisRequest(
        storage_key=storage_key,
        media_format=media_format,
        max_sample_frames=get_settings().vision_max_sample_frames,
        video_bytes=content,
    )
    result = adapter.analyze(request)

    _record_vision_summary_finding(db, modality_state, result, quality_state)

    if result.status is not VisionAnalysisStatus.COMPLETED:
        return

    _record_vision_absence_hypothesis(db, modality_state, result, quality_state)


def _record_vision_summary_finding(
    db: Session,
    modality_state: AnalysisModalityState,
    result: VideoAnalysisResult,
    quality_state: ModalityQualityState,
) -> None:
    if result.status is VisionAnalysisStatus.UNAVAILABLE:
        summary = f"Analise de visao computacional indisponivel: {result.error}"
    elif result.status is VisionAnalysisStatus.FAILED:
        summary = f"Analise de visao computacional falhou: {result.error}"
    else:
        # Cada motor (pose/deteccao) pode estar desligado independentemente
        # (feature flags vision_pose_enabled/vision_detection_enabled) - o
        # resumo so menciona o resultado de um motor quando ele de fato
        # rodou, nunca "0 deteccoes" para um motor desligado (isso
        # pareceria um achado negativo real, quando na verdade a analise
        # nem foi tentada).
        summary_parts = [f"{result.frames_analyzed} quadro(s) amostrado(s)"]
        if result.pose_enabled:
            total_persons = sum(p.person_count for p in result.pose_findings)
            summary_parts.append(f"{total_persons} deteccao(oes) de pessoa (pose)")
        if result.detection_enabled:
            distinct_labels = sorted({_translate_yolo_label(d.label) for d in result.detection_findings})
            summary_parts.append(f"objetos identificados: {', '.join(distinct_labels) or 'nenhum'}")
        summary = ", ".join(summary_parts) + "."

    finding = record_finding(
        modality_state=modality_state,
        modality_type=ModalityType.VIDEO,
        quality_state=quality_state,
        quality_metrics={
            "status": result.status.value,
            "provider": result.provider,
            "frames_analyzed": result.frames_analyzed,
            "pose_enabled": result.pose_enabled,
            "detection_enabled": result.detection_enabled,
            "pose_findings": [
                {
                    "frame_index": p.frame_index,
                    "person_count": p.person_count,
                    "mean_keypoint_confidence": p.mean_keypoint_confidence,
                    "model_version": p.model_version,
                }
                for p in result.pose_findings
            ],
            "detection_findings": [
                {
                    "frame_index": d.frame_index,
                    "label": _translate_yolo_label(d.label),
                    "confidence": d.confidence,
                    "model_version": d.model_version,
                }
                for d in result.detection_findings
            ],
            "error": result.error,
        },
        quality_factors=[],
        summary=summary,
        nature=FindingNature.MODEL_OBSERVATION,
    )
    db.add(finding)


def _record_vision_absence_hypothesis(
    db: Session,
    modality_state: AnalysisModalityState,
    result: VideoAnalysisResult,
    quality_state: ModalityQualityState,
) -> None:
    # So gera hipotese quando o motor de pose estava LIGADO e rodou sobre
    # quadros, e NENHUM tem pessoa detectada - achado real (agregado dos
    # quadros amostrados), nunca uma conclusao clinica. Pode indicar
    # enquadramento de camera fora do paciente tanto quanto qualquer outra
    # causa; cabe ao profissional interpretar. Com vision_pose_enabled=
    # false nao ha achado de pose nenhum - a ausencia de `pose_findings`
    # aqui significaria "motor desligado", nunca "ninguem detectado".
    if not result.pose_enabled or not result.pose_findings:
        return
    if any(p.person_count > 0 for p in result.pose_findings):
        return

    hypothesis = record_finding(
        modality_state=modality_state,
        modality_type=ModalityType.VIDEO,
        quality_state=quality_state,
        quality_metrics={
            "label": "possivel_ausencia_de_pessoa_no_campo_de_captura",
            "frames_analyzed": result.frames_analyzed,
        },
        quality_factors=[],
        summary=(
            f"Nenhuma pessoa detectada nos {result.frames_analyzed} quadro(s) amostrado(s) - "
            "pode indicar ausencia do paciente no campo de captura ou limitacao do "
            "enquadramento; nao e um diagnostico."
        ),
        nature=FindingNature.ASSISTED_HYPOTHESIS,
    )
    db.add(hypothesis)


def process_video_modality(db: Session, modality_state: AnalysisModalityState) -> None:
    media_asset = load_approved_media_asset(db, modality_state)
    storage = get_storage_adapter()
    content = storage.read_approved_object(media_asset.storage_key)

    duration_seconds = parse_isobmff_duration_seconds(content)

    assessment = assess_duration_based_quality(
        duration_seconds,
        adequate_threshold=MIN_VIDEO_SECONDS_ADEQUATE,
        moderate_threshold=MIN_VIDEO_SECONDS_MODERATE,
    )
    summary = (
        f"Video com duracao de {duration_seconds:.1f}s."
        if duration_seconds is not None
        else "Duracao do video nao pode ser determinada a partir do arquivo."
    )

    finding = record_finding(
        modality_state=modality_state,
        modality_type=ModalityType.VIDEO,
        quality_state=assessment.state,
        quality_metrics=assessment.metrics,
        quality_factors=assessment.factors,
        summary=summary,
    )
    db.add(finding)

    # `detected_mime_type` guarda o resultado literal da assinatura de
    # arquivo (`container/isobmff` para MP4/MOV - ambos usam o mesmo
    # container ISO BMFF e a assinatura por si so nao distingue um do
    # outro, ver app.media.validation.detect_mime_type_from_signature).
    # O MIME especifico ja foi validado contra essa assinatura em
    # `signature_matches_declared_mime` na confirmacao do upload; usar
    # `declared_mime_type` aqui e seguro e e o unico campo que de fato
    # diferencia MP4 de MOV.
    media_format = _MEDIA_FORMAT_BY_MIME.get(media_asset.declared_mime_type)
    if media_format is not None and assessment.state not in (
        ModalityQualityState.INSUFFICIENT,
        ModalityQualityState.INVALID,
    ):
        _run_vision_analysis(
            db,
            modality_state,
            content=content,
            storage_key=media_asset.storage_key,
            media_format=media_format,
            quality_state=assessment.state,
        )
        # GPT-4 Vision para análise contextual clínica do vídeo
        _run_video_gpt_vision(
            db,
            modality_state,
            content=content,
            media_format=media_format or "mp4",
            quality_state=assessment.state,
        )


def _run_video_gpt_vision(
    db: Session,
    modality_state: AnalysisModalityState,
    *,
    content: bytes,
    media_format: str,
    quality_state: ModalityQualityState,
) -> None:
    """Extrai quadros do vídeo via ffmpeg e envia ao GPT-4o para análise
    contextual clínica detalhada (sequência temporal de eventos)."""
    try:
        from openai import OpenAI

        from app.core.config import get_settings

        settings = get_settings()
        if not settings.openai_api_key:
            return

        # Extrai 12 quadros equidistantes para capturar a sequência temporal
        frames = _extract_frames_from_video(content, media_format, num_frames=12)
        if not frames:
            return

        client = OpenAI(api_key=settings.openai_api_key)
        # Usa gpt-4o (não mini) para melhor análise de vídeo
        model = "gpt-4o"

        # Monta mensagem com os frames em sequência temporal
        image_contents: list[dict] = []
        for _i, frame_bytes in enumerate(frames):
            b64 = base64.b64encode(frame_bytes).decode("utf-8")
            image_contents.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"},
            })
        image_contents.append({
            "type": "text",
            "text": (
                f"Estes são {len(frames)} quadros extraídos sequencialmente de um vídeo "
                "clínico (do início ao fim). Analise a SEQUÊNCIA TEMPORAL de eventos."
            ),
        })

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Voce e um assistente de apoio clinico especializado em analise de "
                        "video. Os quadros fornecidos estao em ORDEM CRONOLOGICA (do inicio "
                        "ao fim do video). Analise a SEQUENCIA TEMPORAL e descreva:\n\n"
                        "1. RESUMO DA CENA: o que esta acontecendo no video.\n"
                        "2. SEQUENCIA DE EVENTOS: descreva frame a frame o que muda "
                        "(postura, movimento, posicao, expressao). Identifique QUANDO "
                        "ocorrem mudancas significativas.\n"
                        "3. EVENTOS CLINICOS DETECTADOS: liste objetivamente o que observou "
                        "(quedas, perda de equilibrio, uso de dispositivos auxiliares, "
                        "imobilidade, sinais de dor/desconforto, presenca/ausencia de "
                        "auxilio, postura anormal).\n"
                        "4. CLASSIFICACAO DE RISCO: sugira um nivel (Baixo/Moderado/Alto/"
                        "Critico) baseado nos eventos observados, com justificativa.\n\n"
                        "Seja detalhado e objetivo. Responda em portugues do Brasil."
                    ),
                },
                {"role": "user", "content": image_contents},
            ],
            max_tokens=1500,
            store=False,
        )

        description = response.choices[0].message.content or ""
        if not description.strip():
            return

        is_not_relevant = any(
            p in description.lower()
            for p in ["não há contexto clínico", "nao ha contexto clinico", "sem relevância clínica", "nao tem conteudo clinico"]
        )

        finding = record_finding(
            modality_state=modality_state,
            modality_type=ModalityType.VIDEO,
            quality_state=quality_state,
            quality_metrics={
                "provider": "openai",
                "model": model,
                "analysis_type": "vision_contextual_video",
                "frames_analyzed": len(frames),
                "clinical_relevance": "NOT_RELEVANT" if is_not_relevant else "RELEVANT",
            },
            quality_factors=[],
            summary=f"Análise contextual de vídeo (GPT-4 Vision, {len(frames)} quadros): {description.strip()}",
            nature=FindingNature.MODEL_OBSERVATION,
        )
        db.add(finding)

    except Exception as exc:  # noqa: BLE001
        _logger.warning("GPT-4 Vision video analysis failed: %s", exc)


def _extract_frames_from_video(content: bytes, media_format: str, num_frames: int = 12) -> list[bytes]:
    """Extrai N quadros equidistantes do vídeo via ffmpeg. Retorna lista de bytes JPEG."""
    try:
        ext = f".{media_format}"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as src:
            src.write(content)
            src_path = Path(src.name)

        out_dir = Path(tempfile.mkdtemp())

        # Primeiro: obter duração para calcular intervalo
        subprocess.run(
            ["ffmpeg", "-i", str(src_path), "-f", "null", "-"],
            capture_output=True, timeout=15,
        )
        # Extrai frames usando fps filter (mais confiável)
        # Se o vídeo tem 10s e queremos 12 frames: fps=12/10=1.2
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(src_path),
                "-vf", f"fps={num_frames}/10,scale=512:-1",
                "-frames:v", str(num_frames),
                "-q:v", "3",
                str(out_dir / "frame_%03d.jpg"),
            ],
            capture_output=True, timeout=60,
        )
        src_path.unlink(missing_ok=True)

        if result.returncode != 0:
            # Fallback: extrair o que conseguir com filtro simples
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as src2:
                src2.write(content)
                src2_path = Path(src2.name)
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", str(src2_path),
                    "-vf", "fps=1",
                    "-frames:v", str(num_frames),
                    "-q:v", "3",
                    str(out_dir / "frame_%03d.jpg"),
                ],
                capture_output=True, timeout=60,
            )
            src2_path.unlink(missing_ok=True)

        frames: list[bytes] = []
        for jpg_file in sorted(out_dir.glob("frame_*.jpg")):
            frames.append(jpg_file.read_bytes())
            jpg_file.unlink()
        out_dir.rmdir()
        return frames

    except Exception as exc:  # noqa: BLE001
        _logger.warning("Frame extraction failed: %s", exc)
        return []
