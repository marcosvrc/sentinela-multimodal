"""Contrato do adaptador de LLM de consolidacao.

O LLM e usado EXCLUSIVAMENTE para sintese/explicacao textual de um
resultado ja calculado deterministicamente - nunca para decidir o
`risk_level`. Por isso `LlmSummaryRequest` carrega apenas uma allowlist de
campos ja minimizados (nunca o texto adicional bruto do paciente, nunca
midia, nunca segredos/tokens: o conteudo clinico e sempre tratado como
dado nao confiavel, nunca como instrucao para o modelo, e o LLM recebe
apenas essa allowlist de campos minimizados) e `LlmSummaryResult` nao tem
nenhum campo capaz de alterar risco ou conduta - apenas texto explicativo e
metadados de rastreabilidade.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class LlmModalitySummaryInput:
    """Um resumo minimizado de uma modalidade, ja sem dado bruto."""

    modality_type: str
    quality_state: str
    summary: str


@dataclass(frozen=True)
class LlmSummaryRequest:
    """Allowlist de campos que o LLM pode ver - nada alem disso.

    Campos deliberadamente ausentes: nome/CPF do paciente, texto adicional
    bruto, bytes de midia, tokens, URLs assinadas, prompts de sistema de
    outros modulos.
    """

    risk_outcome: str  # "MATCHED" | "INCONCLUSIVE"
    risk_level: int | None
    risk_classification_label: str | None
    inconclusive_reason: str | None
    matched_rule_codes: tuple[str, ...] = field(default_factory=tuple)
    modality_summaries: tuple[LlmModalitySummaryInput, ...] = field(default_factory=tuple)
    # Achados multimodais clinicamente relevantes (termos clínicos,
    # hipóteses, observações de modelo) - enriquecem o resumo explicativo
    # com contexto do que foi encontrado nas modalidades.
    clinical_findings: tuple[LlmModalitySummaryInput, ...] = field(default_factory=tuple)
    # Dados clínicos estruturados informados na análise (ex.: spo2=87,
    # systolic_mmhg=174) para que o LLM explique OS VALORES que geraram
    # o risco, não apenas o rótulo do resultado.
    structured_inputs: dict[str, object] = field(default_factory=dict)
    # Risco assistido por IA (quando disponível) — contexto para que o
    # resumo explicativo mencione divergências entre determinístico e IA.
    assisted_risk_level: int | None = None
    assisted_risk_label: str | None = None


@dataclass(frozen=True)
class LlmSummaryResult:
    summary_text: str
    uncertainty_note: str
    provider: str
    model: str
    prompt_version: str
    input_hash: str
    output_hash: str


@dataclass(frozen=True)
class LlmClinicalObservationSummaryInput:
    """Serie recente (ja limitada, ver `app.clinical_support.service`) de um
    tipo de observacao clinica - so os campos numericos/textuais ja
    estruturados que o paciente/profissional registrou, nunca texto livre."""

    observation_type: str
    unit: str | None
    # Cada item e um par (valor formatado, timestamp ISO) - formatado aqui
    # (nao no adaptador) para nao depender de logica de formatacao de
    # pressao arterial (par sistolica/diastolica) dentro do adaptador.
    recent_values: tuple[tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LlmClinicalAlertSummaryInput:
    """Um alerta de anomalia, ja resumido - mesma allowlist de campos
    exibida na UI (`AlertsPanel`), nunca a evidencia estatistica bruta
    completa."""

    signal_key: str
    severity: str
    status: str
    expected_action: str
    detected_at: str  # ISO 8601


@dataclass(frozen=True)
class LlmClinicalSupportRequest:
    """Allowlist de campos para o apoio a analise clinica sob demanda
    (botao "Analisar dados clinicos" da tela de paciente). Mesma disciplina
    de `LlmSummaryRequest`: nunca nome, CPF, texto livre do prontuario ou
    qualquer dado nao estruturado - apenas idade/sexo (sem identificacao) e
    series/alertas ja estruturados e ja exibidos na propria tela."""

    patient_age: int
    patient_sex: str
    observations: tuple[LlmClinicalObservationSummaryInput, ...] = field(default_factory=tuple)
    alerts: tuple[LlmClinicalAlertSummaryInput, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LlmClinicalSupportResult:
    """Saida do apoio a analise clinica - sempre texto explicativo, nunca
    um campo estruturado de risco/conduta (o LLM nao pode substituir o
    motor de regras nem a decisao do profissional)."""

    summary_text: str
    probable_causes: str
    suggested_next_steps: str
    uncertainty_note: str
    provider: str
    model: str
    prompt_version: str
    input_hash: str
    output_hash: str


@dataclass(frozen=True)
class LlmAnalysisModalityFindingInput:
    """Um achado ja registrado de uma analise multimodal especifica (ver
    `app.processors.models.ModalityFinding`) - mesma allowlist ja exibida
    ao profissional na tela de revisao (`AnalysisReviewPage`): apenas
    modalidade, natureza do achado, estado de qualidade e o texto de
    resumo JA SANITIZADO produzido pelo processador (nunca a midia em si,
    nunca o texto adicional bruto da analise)."""

    modality_type: str
    nature: str  # "ORIGINAL_DATA" | "MODEL_OBSERVATION" | "ASSISTED_HYPOTHESIS"
    quality_state: str
    summary: str


@dataclass(frozen=True)
class LlmAnalysisStructuredInputInput:
    """Uma entrada clinica estruturada ja conhecida no momento da criacao
    da analise (`Analysis.structured_clinical_inputs`, chaveada pelo
    `code` do conjunto de regras - ex.: spo2_percent, heart_rate_bpm) -
    mesmos campos ja avaliados pelo motor deterministico (`app.rules_
    engine`), nunca texto livre."""

    code: str
    inputs: dict[str, object]


@dataclass(frozen=True)
class LlmAnalysisClinicalSupportRequest:
    """Allowlist de campos para o apoio a analise clinica de UMA analise
    multimodal especifica (botao "Analisar dados clinicos" da tela de
    revisao da analise - mesmo padrao de `LlmClinicalSupportRequest`, mas
    com o escopo de dados de uma analise em vez do historico completo do
    paciente). O risco ja calculado deterministicamente (`app.risk_
    consolidation`) entra como CONTEXTO, nunca como algo que o LLM possa
    alterar - mesma disciplina de `LlmSummaryRequest`. `structured_inputs`
    correlaciona os achados por modalidade (imagem/audio/video/texto) com
    os dados clinicos estruturados ja registrados na analise, unificando
    dados clinicos e transcricao para permitir correlacionar um problema,
    dando ao LLM uma visao multimodal completa."""

    patient_age: int
    patient_sex: str
    risk_outcome: str  # "MATCHED" | "INCONCLUSIVE"
    risk_level: int | None
    risk_classification_label: str | None
    structured_inputs: tuple[LlmAnalysisStructuredInputInput, ...] = field(default_factory=tuple)
    findings: tuple[LlmAnalysisModalityFindingInput, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LlmTextRelevanceCheckRequest:
    """Texto a ser avaliado quanto a relevancia clinica ANTES de processar."""

    text: str


@dataclass(frozen=True)
class LlmTextRelevanceCheckResult:
    """Resultado da avaliacao de relevancia clinica do texto."""

    is_clinically_relevant: bool
    relevance_percent: int  # 0-100
    reason: str
    provider: str
    model: str


@dataclass(frozen=True)
class LlmModalityRiskAssessmentRequest:
    """Allowlist de campos para a avaliacao assistida de risco a partir dos
    achados multimodais. Chamada quando ha achados clinicamente relevantes
    mas o motor de regras deterministico nao pode classificar (falta de
    dados clinicos estruturados, ou como complemento quando os dois
    existem). O LLM deve retornar um nivel de risco (1-6) com justificativa
    - que sera apresentado ao profissional como SUGESTAO, nunca como
    classificacao definitiva."""

    findings: tuple[LlmAnalysisModalityFindingInput, ...] = field(default_factory=tuple)
    deterministic_risk_outcome: str | None = None  # "MATCHED"|"INCONCLUSIVE"|None
    deterministic_risk_level: int | None = None


@dataclass(frozen=True)
class LlmModalityRiskAssessmentResult:
    """Resultado da avaliacao assistida de risco por IA."""

    risk_level: int  # 1-6
    classification_label: str
    justification: str
    uncertainty_note: str
    provider: str
    model: str
    prompt_version: str
    input_hash: str
    output_hash: str


class LlmAdapter(Protocol):
    """Implementado por `LocalTemplateLlmAdapter` (dev/testes) e
    `OpenAiLlmAdapter` (real)."""

    def summarize(self, request: LlmSummaryRequest) -> LlmSummaryResult: ...

    def generate_clinical_support_summary(
        self, request: LlmClinicalSupportRequest
    ) -> LlmClinicalSupportResult: ...

    def generate_analysis_clinical_support_summary(
        self, request: LlmAnalysisClinicalSupportRequest
    ) -> LlmClinicalSupportResult: ...

    def assess_modality_risk(
        self, request: LlmModalityRiskAssessmentRequest
    ) -> LlmModalityRiskAssessmentResult: ...

    def check_text_clinical_relevance(
        self, request: LlmTextRelevanceCheckRequest
    ) -> LlmTextRelevanceCheckResult: ...

    def extract_clinical_terms(self, text: str) -> list[dict]: ...
