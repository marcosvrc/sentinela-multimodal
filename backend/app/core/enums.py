"""Enums compartilhados - fonte unica de verdade do backend.

O frontend nao duplica manualmente estes valores: eles sao exportados para
TypeScript por `scripts/export_enums.py` (ver `make codegen`), gerando
`frontend/src/types/enums.generated.ts`. Qualquer mudanca de estado ou
transicao valida deve ser feita aqui primeiro.
"""

from __future__ import annotations

from enum import Enum


class AnalysisStatus(str, Enum):
    """Maquina de estados da analise."""

    CREATED = "CREATED"
    UPLOADING = "UPLOADING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    WAITING_REVIEW = "WAITING_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_FINAL = "FAILED_FINAL"
    CANCELLED = "CANCELLED"


# Transicoes validas da maquina de estados.
# Unica fonte de verdade: o backend valida contra este mapa; o frontend
# nunca deduz transicoes permitidas por conta propria (usa available_actions).
ANALYSIS_STATUS_TRANSITIONS: dict[AnalysisStatus, tuple[AnalysisStatus, ...]] = {
    AnalysisStatus.CREATED: (AnalysisStatus.UPLOADING, AnalysisStatus.CANCELLED),
    AnalysisStatus.UPLOADING: (AnalysisStatus.QUEUED, AnalysisStatus.CANCELLED),
    AnalysisStatus.QUEUED: (AnalysisStatus.PROCESSING, AnalysisStatus.CANCELLED),
    AnalysisStatus.PROCESSING: (
        AnalysisStatus.PARTIALLY_COMPLETED,
        AnalysisStatus.WAITING_REVIEW,
        AnalysisStatus.FAILED_RETRYABLE,
        AnalysisStatus.FAILED_FINAL,
        AnalysisStatus.CANCELLED,
    ),
    AnalysisStatus.PARTIALLY_COMPLETED: (
        AnalysisStatus.WAITING_REVIEW,
        AnalysisStatus.FAILED_FINAL,
        AnalysisStatus.CANCELLED,
    ),
    AnalysisStatus.FAILED_RETRYABLE: (AnalysisStatus.QUEUED, AnalysisStatus.CANCELLED),
    AnalysisStatus.WAITING_REVIEW: (AnalysisStatus.COMPLETED,),
    AnalysisStatus.COMPLETED: (),
    AnalysisStatus.FAILED_FINAL: (),
    AnalysisStatus.CANCELLED: (),
}


class ObservationType(str, Enum):
    """Tipos de dado clinico do cadastro de paciente."""

    BLOOD_PRESSURE = "BLOOD_PRESSURE"
    HEIGHT = "HEIGHT"
    WEIGHT = "WEIGHT"
    SPO2 = "SPO2"
    GLYCEMIA = "GLYCEMIA"
    TEMPERATURE = "TEMPERATURE"
    HEART_RATE = "HEART_RATE"
    RESPIRATORY_RATE = "RESPIRATORY_RATE"
    PAIN = "PAIN"
    CONSCIOUSNESS = "CONSCIOUSNESS"
    # Debito urinario/diurese: sinal classico de monitoramento em UTI/sepse,
    # complementado por `URINE_OUTPUT_RATE_THRESHOLDS`/`urine_output.yaml`.
    URINE_OUTPUT = "URINE_OUTPUT"
    # Convulsao como observacao clinica isolada - antes so existia dentro
    # do contexto de eventos adversos cirurgicos (`surgery_adverse_
    # events.yaml`); agora tambem registravel fora de cirurgia (ex.:
    # paciente internado com epilepsia).
    SEIZURE = "SEIZURE"


class ModalityType(str, Enum):
    """Modalidades suportadas pela analise multimodal."""

    AUDIO = "AUDIO"
    VIDEO = "VIDEO"
    IMAGE = "IMAGE"
    TEXT = "TEXT"


class ModalityStatus(str, Enum):
    """Estado por modalidade dentro de uma analise."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_FINAL = "FAILED_FINAL"


class ModalityQualityState(str, Enum):
    """Qualidade da modalidade, independente do achado clinico."""

    ADEQUATE = "ADEQUATE"
    MODERATE = "MODERATE"
    INSUFFICIENT = "INSUFFICIENT"
    INVALID = "INVALID"


class ObservationReadingQuality(str, Enum):
    """Qualidade da leitura de uma observacao clinica, considerando o
    contexto minimo exigido para toda medicao clinica registrada.
    """

    VALID = "VALID"
    DOUBTFUL = "DOUBTFUL"
    INVALID = "INVALID"


class FindingNature(str, Enum):
    """Natureza do achado, conforme a tabela de tipos de achado clinico."""

    ORIGINAL_DATA = "ORIGINAL_DATA"
    DETERMINISTIC_CLASSIFICATION = "DETERMINISTIC_CLASSIFICATION"
    MODEL_OBSERVATION = "MODEL_OBSERVATION"
    ASSISTED_HYPOTHESIS = "ASSISTED_HYPOTHESIS"
    REGISTERED_DIAGNOSIS = "REGISTERED_DIAGNOSIS"
    PROFESSIONAL_DECISION = "PROFESSIONAL_DECISION"


class ModalityAttentionLevel(str, Enum):
    """Nivel de atencao textual/visual agregado POR MODALIDADE, exibido na
    secao "Nivel de atencao por modalidade" da tela de revisao
    (`app.reports.builder`/`AnalysisReviewPage`).

    NUNCA e um calculo de risco clinico - risco e EXCLUSIVAMENTE calculado
    pelo motor de regras deterministico sobre dados clinicos estruturados
    (`app.risk_consolidation`). Este nivel
    e derivado apenas dos achados que os processadores de midia JA
    produzem hoje (`app.processors.clinical_relevance.is_clinically_
    relevant`) - existe unicamente para dar destaque visual a hipoteses/
    observacoes relevantes por modalidade durante a revisao humana, nunca
    para influenciar `RiskConsolidation.risk_level`.

    - `NONE`: nenhum achado relevante nesta modalidade (so dados tecnicos
      de qualidade, ou observacoes de modelo sem relevancia clinica
      confirmada - ex.: sentimento, categoria heuristica de imagem).
    - `OBSERVATION`: ha ao menos um `MODEL_OBSERVATION` clinicamente
      relevante confirmado (termo clinico extraido, rotulo Rekognition
      confirmado como relevante, metrica acustica real).
    - `ATTENTION`: ha ao menos uma `ASSISTED_HYPOTHESIS` (hipotese nao
      confirmada) nesta modalidade - o nivel mais alto, porque hipoteses
      assistidas sempre requerem avaliacao humana direta.
    """

    NONE = "NONE"
    OBSERVATION = "OBSERVATION"
    ATTENTION = "ATTENTION"


class ReviewStatus(str, Enum):
    """Estado de revisao de um achado."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    CORRECTED = "CORRECTED"
    REJECTED = "REJECTED"


class ReviewDecisionAction(str, Enum):
    """Acao tomada pelo profissional ao revisar um achado."""

    ACCEPT = "ACCEPT"
    CORRECT = "CORRECT"
    REJECT = "REJECT"


class ReportState(str, Enum):
    """Estado do relatorio."""

    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"


class RiskLevelCode(int, Enum):
    """Codigos da tabela canonica de risco.

    Rotulo, cor e significado ficam na tabela `risk_levels` do banco
    (fonte de verdade para o texto exibido); este enum existe apenas para
    validar o codigo numerico em contratos e evitar valores fora de 1-6.
    Inconclusivo NAO e um nivel de risco e nao pertence a este enum.
    """

    LOW = 1
    MILD = 2
    MODERATE = 3
    HIGH = 4
    VERY_HIGH = 5
    CRITICAL = 6


class AnalysisAction(str, Enum):
    """Acoes possiveis retornadas em `available_actions`.

    O frontend nunca deduz acoes permitidas sozinho; sempre consome esta
    lista devolvida pelo backend.
    """

    CANCEL = "CANCEL"
    RETRY_AUDIO = "RETRY_AUDIO"
    RETRY_VIDEO = "RETRY_VIDEO"
    RETRY_IMAGE = "RETRY_IMAGE"
    RETRY_TEXT = "RETRY_TEXT"
    CONFIRM_REPORT = "CONFIRM_REPORT"
    DOWNLOAD_PDF = "DOWNLOAD_PDF"


class AuditCategory(str, Enum):
    """Categoria do evento de auditoria."""

    AUTHENTICATION = "AUTHENTICATION"
    AUTHORIZATION = "AUTHORIZATION"
    DATA = "DATA"
    FILES = "FILES"
    ADMINISTRATION = "ADMINISTRATION"
    ANALYSIS = "ANALYSIS"
    AI = "AI"
    REVIEW = "REVIEW"
    AUDIT = "AUDIT"


class AuditResult(str, Enum):
    """Resultado de um evento de auditoria."""

    SUCCESS = "SUCCESS"
    DENIED = "DENIED"
    ERROR = "ERROR"


class UserRole(str, Enum):
    """Perfis minimos de acesso.

    A autorizacao real considera papel + instituicao + unidade + vinculo
    assistencial + recurso + acao + contexto; este enum cobre apenas o eixo
    "papel", usado pelas dependencias `require_role` (app/core/security.py)
    como primeira camada de controle de acesso.
    """

    ADMINISTRADOR_TECNICO = "ADMINISTRADOR_TECNICO"
    ADMINISTRADOR_CLINICO = "ADMINISTRADOR_CLINICO"
    MEDICO = "MEDICO"
    ENFERMEIRO = "ENFERMEIRO"
    AUDITOR = "AUDITOR"


class EmployeeProfessionalType(str, Enum):
    """Profissao-base do funcionario, distinta
    da especialidade medica (mais granular, ex: "Cardiologia", e opcional).

    Determina quais papeis de acesso (`UserRole`) o funcionario pode
    receber ao ser cadastrado: um Enfermeiro so pode ocupar o papel
    ENFERMEIRO; um Medico pode ocupar MEDICO ou qualquer papel
    administrativo/de auditoria (ADMINISTRADOR_TECNICO,
    ADMINISTRADOR_CLINICO, AUDITOR) - ver
    `app.administration.service.ALLOWED_ROLES_BY_PROFESSIONAL_TYPE`.
    """

    MEDICO = "MEDICO"
    ENFERMEIRO = "ENFERMEIRO"


class MediaUploadState(str, Enum):
    """Ciclo de vida do upload de uma midia, ate ser promovida ou rejeitada.

    Distinto de `ModalityStatus` (que cobre o PROCESSAMENTO da modalidade
    apos a midia estar aprovada - sera usado a partir do orquestrador).
    Este enum cobre apenas a etapa de upload/quarentena: os arquivos
    entram em bucket/prefixo de quarentena e so sao promovidos apos
    validacao e varredura antimalware.
    """

    AWAITING_UPLOAD = "AWAITING_UPLOAD"
    QUARANTINED = "QUARANTINED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class LlmProvider(str, Enum):
    """Adaptador de LLM usado pelo consolidador de risco.

    `LOCAL` e um adaptador deterministico (template fixo, sem chamada de
    rede) para desenvolvimento/testes; `OPENAI` e o adaptador real via
    `openai` (uso do LLM restrito a organizacao, sintese e explicacao,
    nunca como fonte de classificacao de risco); `GEMINI` esta registrado
    como opcao na tela de feature flags (`app.feature_flags`) mas AINDA
    NAO TEM adaptador real implementado - selecionar `GEMINI` falha
    explicitamente (nunca finge funcionar). Selecionado por
    `FeatureFlags` (banco, mutavel em runtime via tela de administracao),
    com `Settings.llm_provider` (.env) como fallback quando a linha de
    flags ainda nao existir.
    """

    LOCAL = "LOCAL"
    OPENAI = "OPENAI"
    GEMINI = "GEMINI"


class TranscriptionProvider(str, Enum):
    """Adaptador de transcricao de audio usado pelo processador AUDIO.

    `LOCAL` nao tem motor de ASR (reconhecimento de fala) real - retorna
    status `UNAVAILABLE` de forma honesta, sem inventar transcricao;
    `AZURE_SPEECH` e o adaptador real via REST (Azure AI Speech, API de
    audio curto - envia os bytes lidos do storage aprovado diretamente no
    corpo da requisicao, `pt-BR`). Selecionado por
    `Settings.transcription_provider`.
    """

    LOCAL = "LOCAL"
    AZURE_SPEECH = "AZURE_SPEECH"


class VisionProvider(str, Enum):
    """Adaptador de visao computacional usado pelo processador VIDEO.

    `LOCAL` nao tem motor de pose/deteccao real - retorna status
    `UNAVAILABLE` de forma honesta, sem inventar keypoints ou objetos;
    `OPENPOSE_YOLOV8` e o adaptador real, worker self-hosted (OpenPose para
    analise postural + YOLOv8 para deteccao de objetos/areas criticas,
    ambos em CPU, executando sobre amostras pequenas para manter a analise
    viavel em CPU). Selecionado por `Settings.vision_provider`. O worker
    self-hosted foi escolhido porque servicos gerenciados de visao (ex.:
    Azure AI Vision) nao oferecem estimativa de pose articulada, que e
    o requisito central desta modalidade.
    """

    LOCAL = "LOCAL"
    OPENPOSE_YOLOV8 = "OPENPOSE_YOLOV8"


class VisionAnalysisStatus(str, Enum):
    """Resultado da chamada ao adaptador de visao computacional - nunca
    bloqueia o registro clinico nem a avaliacao de qualidade estrutural ja
    calculada (mesmo principio de `TranscriptionStatus`)."""

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


class TranscriptionStatus(str, Enum):
    """Resultado da chamada ao adaptador de transcricao - nunca bloqueia o
    registro clinico nem a avaliacao de qualidade/acustica ja calculada
    (mesmo principio de `LlmCallStatus`)."""

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


class SentimentAnalysisStatus(str, Enum):
    """Resultado da chamada ao adaptador de analise de sentimento (Azure
    AI Language) - nunca bloqueia o registro clinico nem a avaliacao de
    qualidade ja calculada (mesmo principio de `TranscriptionStatus`).
    Sentimento e sempre CONTEXTUAL - quando utilizada, a analise de
    sentimento e apenas contextual e nunca determina risco clinico - o
    achado gerado nunca alimenta o motor de regras nem o resumo do LLM de
    consolidacao de risco."""

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


class LlmCallStatus(str, Enum):
    """Resultado da chamada ao LLM de consolidacao (nunca bloqueia o risco
    deterministico - falhas do provedor de LLM nao podem impedir o
    registro clinico nem ocultar alertas deterministicos ja
    identificados)."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ClinicalRuleSetStatus(str, Enum):
    """Ciclo de vida de publicacao de um `ClinicalRuleSet` (somente o
    administrador clinico pode publicar referencias e regras clinicas).

    `DRAFT` e o estado de carga (seed/YAML) - conteudo real, mas ainda nao
    aprovado para uso em avaliacao de risco. `PUBLISHED` e o unico estado
    que `app.rules_engine.service.get_current_rule_set` considera vigente.
    `RETIRED` e uma versao anteriormente publicada e depois substituida ou
    revertida (rollback) - permanece no banco (imutavel, auditavel), nunca
    excluida. Ver `app.administration.service.publish_rule_set` /
    `rollback_rule_set`.
    """

    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"


class RuleEvaluationOutcome(str, Enum):
    """Resultado de uma execucao do motor de regras deterministico.

    `Inconclusivo` explicito e nao um nivel de risco - nao pertence ao
    enum `RiskLevelCode`; esta e a modelagem correspondente no motor de
    execucao.
    """

    MATCHED = "MATCHED"
    INCONCLUSIVE = "INCONCLUSIVE"


class RuleEvaluationInconclusiveReason(str, Enum):
    """Por que uma avaliacao nao produziu uma classificacao de risco."""

    NO_RULE_SET_AVAILABLE = "NO_RULE_SET_AVAILABLE"
    MISSING_REQUIRED_INPUT = "MISSING_REQUIRED_INPUT"
    INVALID_INPUT = "INVALID_INPUT"
    NO_RULE_MATCHED = "NO_RULE_MATCHED"


class AlertSeverity(str, Enum):
    """Severidade de um alerta de anomalia.

    Deliberadamente distinto de `RiskLevelCode`: um alerta de anomalia e um
    desvio estatistico em relacao ao proprio historico recente do paciente
    (monitoramento preventivo), nao uma classificacao clinica de risco - o
    risco continua vindo exclusivamente do motor de regras deterministico
    (LLM e estatistica nunca sao a fonte de verdade da classificacao).
    Nunca alimenta nem substitui `RiskConsolidation`.
    """

    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    """Ciclo de vida de um alerta de anomalia. O fluxo registra
    reconhecimento, responsavel, tempo de resposta, escalonamento e
    encerramento."""

    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
