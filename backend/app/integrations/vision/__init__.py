"""Selecao do adaptador de visao computacional por configuracao (mesmo
padrao de `app.integrations.llm` e `app.integrations.transcription`).

A decisao de LIGAR cada motor (YOLOv8/OpenPose) vem da linha singleton de
`app.feature_flags` (banco, mutavel em runtime via tela `/admin/feature-
flags`) - por isso esta fabrica exige `db: Session` e nunca usa
`@lru_cache`. `Settings.vision_provider` (.env) continua controlando se o
adaptador REAL (worker self-hosted) esta disponivel neste processo (nunca
tenta importar `ultralytics`/OpenPose fora do worker de video dedicado);
a flag decide apenas qual(is) motor(es) usar dentro dele.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import VisionProvider
from app.feature_flags.service import get_feature_flags
from app.integrations.vision.base import VideoAnalysisAdapter
from app.integrations.vision.local import LocalUnavailableVisionAdapter


def get_vision_adapter(db: Session) -> VideoAnalysisAdapter:
    settings = get_settings()

    if settings.vision_provider is VisionProvider.LOCAL:
        return LocalUnavailableVisionAdapter()

    if settings.vision_provider is VisionProvider.OPENPOSE_YOLOV8:
        # Import tardio: `ffmpeg`/`ultralytics`/OpenPose sao dependencias
        # pesadas do worker de video self-hosted, nao da API nem dos demais
        # workers. Nenhuma delas esta instalada neste ambiente de
        # desenvolvimento/sandbox - a fabrica so as importa
        # quando VISION_PROVIDER=OPENPOSE_YOLOV8 esta explicitamente
        # configurado (worker de video em homologacao/producao). Dentro
        # desse modo, YOLOv8 (deteccao) e OpenPose (pose) sao ligados
        # INDEPENDENTEMENTE pela feature flag (`vision_detection_enabled`/
        # `vision_pose_enabled`) - permite considerar cada motor
        # separadamente (ex.: so YOLOv8, sem exigir o binario OpenPose
        # compilado) so mudando a tela de administracao, sem alterar codigo.
        from app.integrations.vision.ffmpeg_frame_extractor import FfmpegFrameExtractor
        from app.integrations.vision.openpose_yolo import OpenPoseYoloVideoAdapter

        flags = get_feature_flags(db)

        pose_engine = None
        if flags.vision_pose_enabled:
            from app.integrations.vision.real_engines import OpenPosePoseEngine

            pose_engine = OpenPosePoseEngine()

        detection_engine = None
        if flags.vision_detection_enabled:
            from app.integrations.vision.real_engines import YoloV8DetectionEngine

            detection_engine = YoloV8DetectionEngine()

        if pose_engine is None and detection_engine is None:
            raise RuntimeError(
                "vision_provider=OPENPOSE_YOLOV8 exige ao menos um motor habilitado: "
                "ligue 'YOLOv8' e/ou 'OpenPose' na tela de feature flags."
            )

        return OpenPoseYoloVideoAdapter(
            frame_extractor=FfmpegFrameExtractor(),
            pose_engine=pose_engine,
            detection_engine=detection_engine,
        )

    raise RuntimeError(f"Provedor de visao computacional desconhecido: {settings.vision_provider}")
