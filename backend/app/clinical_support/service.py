"""Apoio a analise clinica assistido por LLM (botao "Analisar dados
clinicos" da tela de paciente, abaixo do painel de alertas de anomalia).

Diferente de `app.risk_consolidation.service` (que consolida o risco de
UMA analise multimodal especifica, sempre com o motor de regras decidindo
o `risk_level`), este modulo gera um resumo textual SOB DEMANDA a partir
de todo o historico clinico recente do paciente (series de observacoes +
alertas de anomalia), para apoiar - nunca substituir - a analise do
profissional responsavel. Nao produz nem influencia nenhuma classificacao
de risco: e puramente um resumo organizacional/explicativo, com a mesma
disciplina de seguranca de prompt do restante do sistema: allowlist de
campos ja estruturados, nunca texto livre do paciente; dados sempre
delimitados como informacao, nunca instrucao, dentro do adaptador OpenAI
(`app.integrations.llm.openai_adapter`).

Falha do LLM nunca deve impedir a tela de funcionar de forma degradada:
o chamador (rota) decide o codigo de erro apropriado quando a chamada
falha - mas, diferente da consolidacao de risco (onde ha sempre um
resultado deterministico para persistir mesmo se o LLM falhar), aqui o
proprio resultado da funcionalidade E o texto do LLM, entao uma falha e
reportada como erro ao usuario (nunca inventado/mascarado com um
resumo falso).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.anomaly_detection import service as alerts_service
from app.audit import service as audit_service
from app.core.enums import AuditCategory, AuditResult
from app.core.errors import ApiError
from app.integrations.llm import get_llm_adapter
from app.integrations.llm.base import (
    LlmAnalysisClinicalSupportRequest,
    LlmAnalysisModalityFindingInput,
    LlmAnalysisStructuredInputInput,
    LlmClinicalAlertSummaryInput,
    LlmClinicalObservationSummaryInput,
    LlmClinicalSupportRequest,
)
from app.media.models import Analysis
from app.media.service import get_analysis
from app.observations import service as observations_service
from app.observations.validation import compute_age
from app.patients.service import get_patient
from app.processors.clinical_relevance import is_clinically_relevant
from app.processors.models import ModalityFinding
from app.reports.models import Report
from app.risk_consolidation.models import RiskConsolidation

# Quantos registros mais recentes de cada tipo de observacao entram no
# resumo enviado ao LLM - mesmo tamanho de pagina usado nas tabelas da UI
# (padrao de 5 em 5), o suficiente para dar contexto de tendencia sem
# inflar o payload com o historico completo.
MAX_RECENT_VALUES_PER_OBSERVATION_TYPE = 5
# Alertas mais recentes (qualquer severidade/status) incluidos no resumo.
MAX_RECENT_ALERTS = 20


class ClinicalSupportSummary:
    """Resultado formatado, ja pronto para o schema de resposta da API."""

    def __init__(
        self,
        *,
        summary_text: str,
        probable_causes: str,
        suggested_next_steps: str,
        uncertainty_note: str,
        provider: str,
        model: str,
        prompt_version: str,
        input_hash: str,
        output_hash: str,
        generated_at: datetime,
        observations_considered: int,
        alerts_considered: int,
    ) -> None:
        self.summary_text = summary_text
        self.probable_causes = probable_causes
        self.suggested_next_steps = suggested_next_steps
        self.uncertainty_note = uncertainty_note
        self.provider = provider
        self.model = model
        self.prompt_version = prompt_version
        self.input_hash = input_hash
        self.output_hash = output_hash
        self.generated_at = generated_at
        self.observations_considered = observations_considered
        self.alerts_considered = alerts_considered


def _format_observation_value(observation_type: str, value: dict) -> str | None:
    """Formata o `value` de uma observacao como texto curto, sem repetir a
    logica completa de `app.observations.validation` - so o suficiente para
    o LLM entender a leitura (numero simples, ou par sistolica/diastolica
    para pressao arterial)."""
    if observation_type == "BLOOD_PRESSURE":
        systolic = value.get("systolic")
        diastolic = value.get("diastolic")
        if systolic is None or diastolic is None:
            return None
        return f"{systolic}/{diastolic}"
    raw = value.get("value")
    if raw is None:
        return None
    return str(raw)


def _build_observation_summaries(
    observations: list,
) -> tuple[LlmClinicalObservationSummaryInput, ...]:
    """Agrupa por tipo (mesma ordem de chegada, `measured_at` decrescente -
    ver `observations_service.list_observations`) e mantem apenas os `N`
    mais recentes de cada tipo."""
    grouped: dict[str, list] = {}
    for observation in observations:
        grouped.setdefault(observation.observation_type, []).append(observation)

    summaries: list[LlmClinicalObservationSummaryInput] = []
    for observation_type, items in grouped.items():
        recent_values: list[tuple[str, str]] = []
        for item in items[:MAX_RECENT_VALUES_PER_OBSERVATION_TYPE]:
            formatted = _format_observation_value(observation_type, item.value)
            if formatted is None:
                continue
            recent_values.append((formatted, item.measured_at.isoformat()))
        if not recent_values:
            continue
        summaries.append(
            LlmClinicalObservationSummaryInput(
                observation_type=observation_type,
                unit=items[0].unit,
                recent_values=tuple(recent_values),
            )
        )
    return tuple(summaries)


def generate_clinical_support_summary(
    db: Session,
    institution_id: uuid.UUID,
    patient_id: uuid.UUID,
    *,
    actor: str,
    actor_role: str | None,
) -> ClinicalSupportSummary:
    """Monta o payload minimizado (idade, sexo, series de observacoes,
    alertas de anomalia), chama o adaptador de LLM configurado
    (`app.integrations.llm.get_llm_adapter`) e registra o evento de
    auditoria categoria IA (mesmo padrao de `risk_consolidation.service`).

    Nunca persiste o resultado (e um apoio sob demanda, nao um dado clinico
    do paciente) - cada chamada gera um resumo novo a partir do estado
    atual dos dados."""
    patient = get_patient(db, institution_id, patient_id)
    observations = observations_service.list_observations(db, institution_id, patient_id)
    alerts, _total = alerts_service.list_alerts(
        db,
        institution_id,
        patient_id=patient_id,
        status=None,
        severity=None,
        page=1,
        page_size=MAX_RECENT_ALERTS,
    )

    observation_summaries = _build_observation_summaries(observations)
    alert_summaries = tuple(
        LlmClinicalAlertSummaryInput(
            signal_key=alert.signal_key,
            severity=alert.severity,
            status=alert.status,
            expected_action=alert.expected_action,
            detected_at=alert.detected_at.isoformat(),
        )
        for alert in alerts
    )

    request = LlmClinicalSupportRequest(
        patient_age=compute_age(patient.birth_date, date.today()),
        patient_sex=patient.registered_sex,
        observations=observation_summaries,
        alerts=alert_summaries,
    )

    adapter = get_llm_adapter(db)
    try:
        result = adapter.generate_clinical_support_summary(request)
    except Exception as exc:  # noqa: BLE001 - qualquer falha do provedor de LLM
        audit_service.record_event(
            db,
            actor=actor,
            actor_role=actor_role,
            category=AuditCategory.AI,
            action="CLINICAL_SUPPORT_SUMMARY_FAILED",
            resource_type="patient",
            resource_id=str(patient_id),
            result=AuditResult.ERROR,
            institution_id=institution_id,
            event_metadata={"error": str(exc)[:500]},
        )
        db.commit()
        raise ApiError(
            code="CLINICAL_SUPPORT_SUMMARY_UNAVAILABLE",
            message=(
                "Nao foi possivel gerar o apoio a analise clinica agora. "
                "Tente novamente em alguns instantes."
            ),
            status_code=502,
        ) from exc

    audit_service.record_event(
        db,
        actor=actor,
        actor_role=actor_role,
        category=AuditCategory.AI,
        action="CLINICAL_SUPPORT_SUMMARY_GENERATED",
        resource_type="patient",
        resource_id=str(patient_id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
        event_metadata={
            "provider": result.provider,
            "model": result.model,
            "prompt_version": result.prompt_version,
            "input_hash": result.input_hash,
            "output_hash": result.output_hash,
            "observations_considered": len(observation_summaries),
            "alerts_considered": len(alert_summaries),
        },
    )
    db.commit()

    return ClinicalSupportSummary(
        summary_text=result.summary_text,
        probable_causes=result.probable_causes,
        suggested_next_steps=result.suggested_next_steps,
        uncertainty_note=result.uncertainty_note,
        provider=result.provider,
        model=result.model,
        prompt_version=result.prompt_version,
        input_hash=result.input_hash,
        output_hash=result.output_hash,
        generated_at=datetime.now(tz=timezone.utc),
        observations_considered=len(observation_summaries),
        alerts_considered=len(alert_summaries),
    )


class AnalysisClinicalSupportSummary:
    """Resultado formatado do apoio a analise clinica de UMA analise
    multimodal especifica, ja pronto para o schema de resposta da API."""

    def __init__(
        self,
        *,
        summary_text: str,
        probable_causes: str,
        suggested_next_steps: str,
        uncertainty_note: str,
        provider: str,
        model: str,
        prompt_version: str,
        input_hash: str,
        output_hash: str,
        generated_at: datetime,
        findings_considered: int,
    ) -> None:
        self.summary_text = summary_text
        self.probable_causes = probable_causes
        self.suggested_next_steps = suggested_next_steps
        self.uncertainty_note = uncertainty_note
        self.provider = provider
        self.model = model
        self.prompt_version = prompt_version
        self.input_hash = input_hash
        self.output_hash = output_hash
        self.generated_at = generated_at
        self.findings_considered = findings_considered


def should_run_automatic_clinical_support(db: Session, analysis_id: uuid.UUID) -> bool:
    """Guardrail central do apoio a analise clinica AUTOMATICO (feature
    flag `auto_clinical_support_enabled`, ver `app.orchestrator.worker`):
    so retorna `True` quando ha ao menos UM dado clinico estruturado OU UM
    achado clinicamente relevante (ver `app.processors.clinical_relevance.
    is_clinically_relevant`) nesta analise - nunca chama o LLM so porque a
    analise tem midia, se essa midia nao tiver sinal clinico confirmado."""
    analysis = db.get(Analysis, analysis_id)
    if analysis is not None and analysis.structured_clinical_inputs:
        return True

    findings = db.scalars(
        select(ModalityFinding).where(ModalityFinding.analysis_id == analysis_id)
    ).all()
    return any(
        is_clinically_relevant(finding.nature, finding.quality_metrics) for finding in findings
    )


def generate_analysis_clinical_support_summary(
    db: Session,
    institution_id: uuid.UUID,
    analysis_id: uuid.UUID,
    *,
    actor: str,
    actor_role: str | None,
) -> AnalysisClinicalSupportSummary:
    """Apoio a analise clinica assistido por LLM para UMA ANALISE
    MULTIMODAL especifica (botao "Analisar dados clinicos" da tela de
    revisao da analise, mesmo padrao de `generate_clinical_support_summary`
    mas com o escopo de uma analise em vez do historico completo do
    paciente).

    Monta o payload minimizado (idade/sexo do paciente, achados JA
    PRODUZIDOS pelos processadores de modalidade desta analise, e o risco
    JA CALCULADO deterministicamente como contexto), chama o adaptador de
    LLM configurado e registra o evento de auditoria categoria IA (mesmo
    padrao de `risk_consolidation.service` e da funcao acima).

    Nunca persiste o resultado (e um apoio sob demanda) - cada chamada
    gera um resumo novo a partir do estado atual dos achados da analise."""
    analysis = get_analysis(db, institution_id, analysis_id)
    patient = get_patient(db, institution_id, analysis.patient_id)

    findings = list(
        db.scalars(
            select(ModalityFinding).where(ModalityFinding.analysis_id == analysis_id)
        ).all()
    )
    risk = db.scalar(
        select(RiskConsolidation).where(RiskConsolidation.analysis_id == analysis_id)
    )

    # Guardrail de relevancia clinica (app.vision.clinical_relevance):
    # achados de reconhecimento de imagem (Azure AI Vision) que foram
    # avaliados como NAO relevantes clinicamente, ou cuja relevancia
    # nao pode ser confirmada, sao EXCLUIDOS das consideracoes finais -
    # nunca influenciam o resumo de apoio a analise clinica. O aviso ainda
    # fica visivel ao profissional no laudo (`summary` do proprio achado,
    # `app.reports.builder`), apenas nao alimenta o prompt do LLM.
    finding_summaries = tuple(
        LlmAnalysisModalityFindingInput(
            modality_type=finding.modality_type,
            nature=finding.nature,
            quality_state=finding.quality_state,
            summary=finding.summary,
        )
        for finding in findings
        if finding.quality_metrics.get("clinical_relevance") not in ("NOT_RELEVANT", "UNDETERMINED")
    )
    # Correlaciona os achados por modalidade (imagem/audio/video/texto,
    # incluindo transcricao e termos clinicos extraidos) com os dados
    # clinicos estruturados ja registrados na propria analise - visao
    # multimodal completa em vez de apenas os achados de midia.
    structured_input_summaries = tuple(
        LlmAnalysisStructuredInputInput(code=code, inputs=inputs)
        for code, inputs in (analysis.structured_clinical_inputs or {}).items()
    )

    request = LlmAnalysisClinicalSupportRequest(
        patient_age=compute_age(patient.birth_date, date.today()),
        patient_sex=patient.registered_sex,
        risk_outcome=risk.outcome if risk else "INCONCLUSIVE",
        risk_level=risk.risk_level if risk else None,
        risk_classification_label=risk.classification_label if risk else None,
        structured_inputs=structured_input_summaries,
        findings=finding_summaries,
    )

    adapter = get_llm_adapter(db)
    try:
        result = adapter.generate_analysis_clinical_support_summary(request)
    except Exception as exc:  # noqa: BLE001 - qualquer falha do provedor de LLM
        audit_service.record_event(
            db,
            actor=actor,
            actor_role=actor_role,
            category=AuditCategory.AI,
            action="ANALYSIS_CLINICAL_SUPPORT_SUMMARY_FAILED",
            resource_type="analysis",
            resource_id=str(analysis_id),
            result=AuditResult.ERROR,
            institution_id=institution_id,
            analysis_id=str(analysis_id),
            event_metadata={"error": str(exc)[:500]},
        )
        db.commit()
        raise ApiError(
            code="ANALYSIS_CLINICAL_SUPPORT_SUMMARY_UNAVAILABLE",
            message=(
                "Nao foi possivel gerar o apoio a analise clinica agora. "
                "Tente novamente em alguns instantes."
            ),
            status_code=502,
        ) from exc

    audit_service.record_event(
        db,
        actor=actor,
        actor_role=actor_role,
        category=AuditCategory.AI,
        action="ANALYSIS_CLINICAL_SUPPORT_SUMMARY_GENERATED",
        resource_type="analysis",
        resource_id=str(analysis_id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
        analysis_id=str(analysis_id),
        event_metadata={
            "provider": result.provider,
            "model": result.model,
            "prompt_version": result.prompt_version,
            "input_hash": result.input_hash,
            "output_hash": result.output_hash,
            "findings_considered": len(finding_summaries),
            "structured_inputs_considered": len(structured_input_summaries),
        },
    )

    generated_at = datetime.now(tz=timezone.utc)

    # Persiste o resultado no relatorio (se ja existir - `generate_report`
    # roda antes deste botao ficar disponivel, ver `app.orchestrator.
    # worker`), para que o PDF exportado inclua o ultimo apoio gerado.
    # Sob demanda: cada chamada SOBRESCREVE o resumo anterior, nunca
    # acumula historico (mesmo principio de `RiskConsolidation`/
    # `Report.content` - sempre o estado mais recente).
    report = db.scalar(select(Report).where(Report.analysis_id == analysis_id))
    if report is not None:
        report.clinical_support_summary = {
            "summary_text": result.summary_text,
            "probable_causes": result.probable_causes,
            "suggested_next_steps": result.suggested_next_steps,
            "uncertainty_note": result.uncertainty_note,
            "provider": result.provider,
            "model": result.model,
            "prompt_version": result.prompt_version,
            "generated_at": generated_at.isoformat(),
            "findings_considered": len(finding_summaries),
        }
        db.flush()

    db.commit()

    return AnalysisClinicalSupportSummary(
        summary_text=result.summary_text,
        probable_causes=result.probable_causes,
        suggested_next_steps=result.suggested_next_steps,
        uncertainty_note=result.uncertainty_note,
        provider=result.provider,
        model=result.model,
        prompt_version=result.prompt_version,
        input_hash=result.input_hash,
        output_hash=result.output_hash,
        generated_at=generated_at,
        findings_considered=len(finding_summaries),
    )
