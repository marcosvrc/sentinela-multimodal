"""Testes de `app.reports.builder.build_report_content` (pure, sem banco)."""

from __future__ import annotations

from app.reports.builder import (
    ReportAnalysisContext,
    ReportClinicalSupportSummary,
    ReportModalityFinding,
    ReportPatientContext,
    ReportProfessionalReview,
    ReportRiskConsolidation,
    build_report_content,
)

_PATIENT = ReportPatientContext(
    patient_id="patient-1",
    medical_record_number="MRN-1",
    full_name="Paciente Teste",
    birth_date="1990-01-01",
)

_ANALYSIS = ReportAnalysisContext(
    analysis_id="analysis-1",
    institution_id="institution-1",
    status="WAITING_REVIEW",
    created_at="2026-07-11T10:00:00+00:00",
    created_by="dr-teste",
    additional_text="Paciente relata tontura.",
    structured_clinical_inputs={"spo2": {"spo2_percent": 91}},
)


def _draft_review() -> ReportProfessionalReview:
    return ReportProfessionalReview(state="DRAFT")


def test_matched_risk_produces_calculated_risk_and_no_inconsistency() -> None:
    risk = ReportRiskConsolidation(
        outcome="MATCHED",
        risk_level=6,
        classification_label="Hipoxemia grave",
        inconclusive_reason=None,
        inconclusive_detail=None,
        code_evaluations=[
            {
                "code": "spo2",
                "outcome": "MATCHED",
                "risk_level": 6,
                "classification_label": "Hipoxemia grave",
                "inconclusive_reason": None,
            }
        ],
        llm_status="SUCCESS",
        llm_summary="Classificacao deterministica: nivel 6.",
        llm_uncertainty_note="Revisao profissional necessaria.",
        llm_provider="local",
        llm_model="local-template",
        llm_prompt_version="local-template-v1",
        llm_input_hash="a" * 64,
        llm_output_hash="b" * 64,
    )
    content = build_report_content(
        patient=_PATIENT,
        analysis=_ANALYSIS,
        risk=risk,
        modality_findings=[],
        protocol_action_description="Alertar equipe assistencial.",
        review=_draft_review(),
    )

    assert content["calculated_risk"]["risk_level"] == 6
    assert content["calculated_risk"]["outcome"] == "MATCHED"
    assert content["protocol_conduct"] == "Alertar equipe assistencial."
    assert content["inconsistencies"] == []
    assert content["identification"]["patient"]["full_name"] == "Paciente Teste"
    assert content["report_state"] == "DRAFT"
    assert content["professional_review"]["confirmed_by"] is None


def test_no_risk_consolidation_yields_inconsistency() -> None:
    content = build_report_content(
        patient=_PATIENT,
        analysis=_ANALYSIS,
        risk=None,
        modality_findings=[],
        protocol_action_description=None,
        review=_draft_review(),
    )

    assert content["calculated_risk"]["outcome"] == "INCONCLUSIVE"
    assert len(content["inconsistencies"]) == 1


def test_insufficient_quality_modality_is_flagged_as_inconsistency() -> None:
    finding = ReportModalityFinding(
        modality_type="IMAGE",
        nature="ORIGINAL_DATA",
        quality_state="INSUFFICIENT",
        quality_metrics={"width": 50, "height": 50},
        quality_factors=["resolucao_baixa"],
        summary="Imagem 50x50.",
        created_at="2026-07-11T10:05:00+00:00",
    )
    content = build_report_content(
        patient=_PATIENT,
        analysis=_ANALYSIS,
        risk=None,
        modality_findings=[finding],
        protocol_action_description=None,
        review=_draft_review(),
    )

    assert any("IMAGE" in item for item in content["inconsistencies"])
    # Evidencia e qualidade tecnica agora vivem na mesma lista unificada
    # (uma linha por achado, com todas as colunas juntas).
    assert content["modality_evidence"][0]["modality_type"] == "IMAGE"
    assert content["modality_evidence"][0]["quality_state"] == "INSUFFICIENT"
    assert content["modality_evidence"][0]["quality_factors"] == ["resolucao_baixa"]


def test_confirmed_review_is_reflected_in_content() -> None:
    review = ReportProfessionalReview(
        state="CONFIRMED", confirmed_by="dr-teste", confirmed_at="2026-07-11T12:00:00+00:00"
    )
    content = build_report_content(
        patient=_PATIENT,
        analysis=_ANALYSIS,
        risk=None,
        modality_findings=[],
        protocol_action_description=None,
        review=review,
    )

    assert content["report_state"] == "CONFIRMED"
    assert content["professional_review"]["confirmed_by"] == "dr-teste"


def test_model_observations_and_hypotheses_are_empty_without_matching_findings() -> None:
    """Trava contra falsificar achados de IA (secao 5.5): estas secoes so
    devem deixar de ser vazias quando um achado com a natureza correspondente
    (MODEL_OBSERVATION/ASSISTED_HYPOTHESIS) existir - nunca por dado
    inventado no proprio builder."""
    content = build_report_content(
        patient=_PATIENT,
        analysis=_ANALYSIS,
        risk=None,
        modality_findings=[],
        protocol_action_description=None,
        review=_draft_review(),
    )
    assert content["model_observations"] == []
    assert content["assisted_hypotheses"] == []


def test_clinical_support_summary_is_none_when_never_generated() -> None:
    """O profissional pode confirmar o relatorio sem nunca ter clicado no
    botao "Analisar dados clinicos" (apoio sob demanda, distinto do
    resumo automatico `ai_summary`) - o campo deve ser `None`, nunca
    inventado."""
    content = build_report_content(
        patient=_PATIENT,
        analysis=_ANALYSIS,
        risk=None,
        modality_findings=[],
        protocol_action_description=None,
        review=_draft_review(),
    )
    assert content["clinical_support_summary"] is None


def test_clinical_support_summary_populates_dedicated_section() -> None:
    """Regressao do bug "Apoio a analise clinica (IA) nao aparece no PDF":
    quando ha um resumo persistido (`Report.clinical_support_summary`),
    ele deve ser refletido em `content["clinical_support_summary"]`."""
    clinical_support_summary = ReportClinicalSupportSummary(
        summary_text="Paciente com risco critico por hipoxemia grave.",
        probable_causes="Insuficiencia respiratoria aguda.",
        suggested_next_steps="Avaliacao presencial imediata.",
        uncertainty_note="Apoio nao substitui a analise do profissional responsavel.",
        provider="openai",
        model="gpt-4o-mini",
        prompt_version="analysis-clinical-support-v1",
        generated_at="2026-07-17T10:00:00+00:00",
        findings_considered=3,
    )
    content = build_report_content(
        patient=_PATIENT,
        analysis=_ANALYSIS,
        risk=None,
        modality_findings=[],
        protocol_action_description=None,
        review=_draft_review(),
        clinical_support_summary=clinical_support_summary,
    )
    assert content["clinical_support_summary"]["summary_text"] == (
        "Paciente com risco critico por hipoxemia grave."
    )
    assert content["clinical_support_summary"]["provider"] == "openai"
    assert content["clinical_support_summary"]["findings_considered"] == 3


def test_model_observation_finding_populates_model_observations_section() -> None:
    """A partir da secao 4.3, o processador de texto produz achados
    MODEL_OBSERVATION reais (negacao/temporalidade/certeza/experienciador) -
    devem aparecer aqui, distintos dos achados ORIGINAL_DATA de qualidade."""
    quality_finding = ReportModalityFinding(
        modality_type="TEXT",
        nature="ORIGINAL_DATA",
        quality_state="ADEQUATE",
        quality_metrics={"length": 30, "word_count": 5},
        quality_factors=[],
        summary="Texto com 30 caracteres (5 palavras).",
        created_at="2026-07-11T10:05:00+00:00",
    )
    observation_finding = ReportModalityFinding(
        modality_type="TEXT",
        nature="MODEL_OBSERVATION",
        quality_state="ADEQUATE",
        quality_metrics={"term": "dor", "negation": "NEGATED"},
        quality_factors=[],
        summary="Termo clinico candidato 'dor' (negated).",
        created_at="2026-07-11T10:05:01+00:00",
    )
    content = build_report_content(
        patient=_PATIENT,
        analysis=_ANALYSIS,
        risk=None,
        modality_findings=[quality_finding, observation_finding],
        protocol_action_description=None,
        review=_draft_review(),
    )
    assert len(content["model_observations"]) == 1
    assert content["model_observations"][0]["summary"] == "Termo clinico candidato 'dor' (negated)."
    assert content["assisted_hypotheses"] == []
    # ambos os achados continuam aparecendo na evidencia/qualidade unificada.
    assert len(content["modality_evidence"]) == 2


class TestModalityAttention:
    """`content["modality_attention"]` (item 30 do backlog) - nivel de
    atencao visual por modalidade, NUNCA risco clinico. Reaproveita a
    mesma regra de relevancia de `app.processors.clinical_relevance.
    is_clinically_relevant`."""

    def test_empty_findings_yields_empty_attention_list(self) -> None:
        content = build_report_content(
            patient=_PATIENT,
            analysis=_ANALYSIS,
            risk=None,
            modality_findings=[],
            protocol_action_description=None,
            review=_draft_review(),
        )
        assert content["modality_attention"] == []

    def test_only_original_data_yields_none_level(self) -> None:
        finding = ReportModalityFinding(
            modality_type="IMAGE",
            nature="ORIGINAL_DATA",
            quality_state="ADEQUATE",
            quality_metrics={"width": 800, "height": 600},
            quality_factors=[],
            summary="Imagem 800x600.",
            created_at="2026-07-11T10:05:00+00:00",
        )
        content = build_report_content(
            patient=_PATIENT,
            analysis=_ANALYSIS,
            risk=None,
            modality_findings=[finding],
            protocol_action_description=None,
            review=_draft_review(),
        )
        assert content["modality_attention"] == [
            {
                "modality_type": "IMAGE",
                "level": "NONE",
                "relevant_findings_count": 0,
                "summaries": [],
            }
        ]

    def test_not_relevant_model_observation_yields_none_level(self) -> None:
        finding = ReportModalityFinding(
            modality_type="IMAGE",
            nature="MODEL_OBSERVATION",
            quality_state="ADEQUATE",
            quality_metrics={"clinical_relevance": "NOT_RELEVANT"},
            quality_factors=[],
            summary="Rotulos identificados: paisagem.",
            created_at="2026-07-11T10:05:00+00:00",
        )
        content = build_report_content(
            patient=_PATIENT,
            analysis=_ANALYSIS,
            risk=None,
            modality_findings=[finding],
            protocol_action_description=None,
            review=_draft_review(),
        )
        assert content["modality_attention"][0]["level"] == "NONE"

    def test_relevant_model_observation_yields_observation_level(self) -> None:
        finding = ReportModalityFinding(
            modality_type="TEXT",
            nature="MODEL_OBSERVATION",
            quality_state="ADEQUATE",
            quality_metrics={"term": "dor toracica"},
            quality_factors=[],
            summary="Termo clinico candidato 'dor toracica'.",
            created_at="2026-07-11T10:05:00+00:00",
        )
        content = build_report_content(
            patient=_PATIENT,
            analysis=_ANALYSIS,
            risk=None,
            modality_findings=[finding],
            protocol_action_description=None,
            review=_draft_review(),
        )
        assert content["modality_attention"] == [
            {
                "modality_type": "TEXT",
                "level": "OBSERVATION",
                "relevant_findings_count": 1,
                "summaries": ["Termo clinico candidato 'dor toracica'."],
            }
        ]

    def test_assisted_hypothesis_yields_attention_level_even_with_observation_present(
        self,
    ) -> None:
        """ATTENTION vence OBSERVATION dentro da mesma modalidade -
        hipotese assistida e sempre o nivel mais alto."""
        observation = ReportModalityFinding(
            modality_type="AUDIO",
            nature="MODEL_OBSERVATION",
            quality_state="ADEQUATE",
            quality_metrics={"rms_energy_mean": 0.02},
            quality_factors=[],
            summary="Energia media baixa.",
            created_at="2026-07-11T10:05:00+00:00",
        )
        hypothesis = ReportModalityFinding(
            modality_type="AUDIO",
            nature="ASSISTED_HYPOTHESIS",
            quality_state="ADEQUATE",
            quality_metrics={"label": "possivel_reducao_de_energia_vocal"},
            quality_factors=[],
            summary="Possivel reducao de energia vocal.",
            created_at="2026-07-11T10:05:01+00:00",
        )
        content = build_report_content(
            patient=_PATIENT,
            analysis=_ANALYSIS,
            risk=None,
            modality_findings=[observation, hypothesis],
            protocol_action_description=None,
            review=_draft_review(),
        )
        # Ambos os achados contam como relevantes (a observacao acustica
        # DSP tambem e relevante por si so, ver `is_clinically_relevant`)
        # - o que decide o `level` e a PRESENCA de uma hipotese, nao a
        # contagem total.
        assert content["modality_attention"] == [
            {
                "modality_type": "AUDIO",
                "level": "ATTENTION",
                "relevant_findings_count": 2,
                "summaries": ["Energia media baixa.", "Possivel reducao de energia vocal."],
            }
        ]

    def test_multiple_modalities_are_each_evaluated_independently(self) -> None:
        image_finding = ReportModalityFinding(
            modality_type="IMAGE",
            nature="MODEL_OBSERVATION",
            quality_state="ADEQUATE",
            quality_metrics={"clinical_relevance": "NOT_RELEVANT"},
            quality_factors=[],
            summary="Rotulos: paisagem.",
            created_at="2026-07-11T10:05:00+00:00",
        )
        video_hypothesis = ReportModalityFinding(
            modality_type="VIDEO",
            nature="ASSISTED_HYPOTHESIS",
            quality_state="ADEQUATE",
            quality_metrics={"label": "possivel_ausencia_de_pessoa_no_campo_de_captura"},
            quality_factors=[],
            summary="Nenhuma pessoa detectada nos quadros amostrados.",
            created_at="2026-07-11T10:05:00+00:00",
        )
        content = build_report_content(
            patient=_PATIENT,
            analysis=_ANALYSIS,
            risk=None,
            modality_findings=[image_finding, video_hypothesis],
            protocol_action_description=None,
            review=_draft_review(),
        )
        by_modality = {item["modality_type"]: item for item in content["modality_attention"]}
        assert by_modality["IMAGE"]["level"] == "NONE"
        assert by_modality["VIDEO"]["level"] == "ATTENTION"

    def test_modality_absent_from_analysis_is_not_listed(self) -> None:
        """So lista modalidades com pelo menos um achado nesta analise -
        nunca todas as 4 modalidades possiveis por padrao."""
        finding = ReportModalityFinding(
            modality_type="TEXT",
            nature="ORIGINAL_DATA",
            quality_state="ADEQUATE",
            quality_metrics={"length": 20, "word_count": 4},
            quality_factors=[],
            summary="Texto com 20 caracteres.",
            created_at="2026-07-11T10:05:00+00:00",
        )
        content = build_report_content(
            patient=_PATIENT,
            analysis=_ANALYSIS,
            risk=None,
            modality_findings=[finding],
            protocol_action_description=None,
            review=_draft_review(),
        )
        modality_types = {item["modality_type"] for item in content["modality_attention"]}
        assert modality_types == {"TEXT"}


class TestModalitySummaryAndClinicalCorrelation:
    """`content["modality_summary"]` (tabela consolidada: qualidade +
    relevancia clinica + resumo + uso na analise final) e `content[
    "clinical_correlation_summary"]` (resumo final deterministico
    correlacionando apenas modalidades clinicamente relevantes)."""

    def test_empty_findings_yields_empty_summary_and_no_included_modality(self) -> None:
        content = build_report_content(
            patient=_PATIENT,
            analysis=_ANALYSIS,
            risk=None,
            modality_findings=[],
            protocol_action_description=None,
            review=_draft_review(),
        )
        assert content["modality_summary"] == []
        assert content["clinical_correlation_summary"]["included_modality_types"] == []
        assert content["clinical_correlation_summary"]["excluded_modality_types"] == []
        assert "nenhuma modalidade" in content["clinical_correlation_summary"]["text"].lower()

    def test_only_quality_finding_is_not_clinically_relevant_and_excluded(self) -> None:
        finding = ReportModalityFinding(
            modality_type="IMAGE",
            nature="ORIGINAL_DATA",
            quality_state="ADEQUATE",
            quality_metrics={"width": 800, "height": 600},
            quality_factors=[],
            summary="Imagem 800x600.",
            created_at="2026-07-11T10:05:00+00:00",
        )
        content = build_report_content(
            patient=_PATIENT,
            analysis=_ANALYSIS,
            risk=None,
            modality_findings=[finding],
            protocol_action_description=None,
            review=_draft_review(),
        )
        assert content["modality_summary"] == [
            {
                "modality_type": "IMAGE",
                "quality_state": "ADEQUATE",
                "clinically_relevant": False,
                "summary": "Imagem 800x600.",
                "used_in_final_analysis": False,
            }
        ]
        assert content["clinical_correlation_summary"]["included_modality_types"] == []
        assert content["clinical_correlation_summary"]["excluded_modality_types"] == ["IMAGE"]

    def test_relevant_model_observation_marks_modality_as_used_in_final_analysis(self) -> None:
        quality_finding = ReportModalityFinding(
            modality_type="TEXT",
            nature="ORIGINAL_DATA",
            quality_state="ADEQUATE",
            quality_metrics={"length": 30, "word_count": 5},
            quality_factors=[],
            summary="Texto com 30 caracteres (5 palavras).",
            created_at="2026-07-11T10:05:00+00:00",
        )
        observation_finding = ReportModalityFinding(
            modality_type="TEXT",
            nature="MODEL_OBSERVATION",
            quality_state="ADEQUATE",
            quality_metrics={"term": "dor toracica"},
            quality_factors=[],
            summary="Termo clinico candidato 'dor toracica'.",
            created_at="2026-07-11T10:05:01+00:00",
        )
        content = build_report_content(
            patient=_PATIENT,
            analysis=_ANALYSIS,
            risk=None,
            modality_findings=[quality_finding, observation_finding],
            protocol_action_description=None,
            review=_draft_review(),
        )
        text_summary = content["modality_summary"][0]
        assert text_summary["modality_type"] == "TEXT"
        assert text_summary["quality_state"] == "ADEQUATE"
        assert text_summary["clinically_relevant"] is True
        assert text_summary["used_in_final_analysis"] is True
        assert "dor toracica" in text_summary["summary"]

        correlation = content["clinical_correlation_summary"]
        assert correlation["included_modality_types"] == ["TEXT"]
        assert correlation["excluded_modality_types"] == []
        assert "TEXT" in correlation["text"]

    def test_final_summary_correlates_only_clinically_relevant_modalities(self) -> None:
        """Duas modalidades presentes, so uma clinicamente relevante -
        o resumo final deve incluir so a relevante e listar a outra em
        `excluded_modality_types`."""
        irrelevant_image = ReportModalityFinding(
            modality_type="IMAGE",
            nature="MODEL_OBSERVATION",
            quality_state="ADEQUATE",
            quality_metrics={"clinical_relevance": "NOT_RELEVANT"},
            quality_factors=[],
            summary="Rotulos: paisagem.",
            created_at="2026-07-11T10:05:00+00:00",
        )
        relevant_video = ReportModalityFinding(
            modality_type="VIDEO",
            nature="ASSISTED_HYPOTHESIS",
            quality_state="ADEQUATE",
            quality_metrics={"label": "possivel_ausencia_de_pessoa_no_campo_de_captura"},
            quality_factors=[],
            summary="Nenhuma pessoa detectada nos quadros amostrados.",
            created_at="2026-07-11T10:05:00+00:00",
        )
        content = build_report_content(
            patient=_PATIENT,
            analysis=_ANALYSIS,
            risk=None,
            modality_findings=[irrelevant_image, relevant_video],
            protocol_action_description=None,
            review=_draft_review(),
        )
        by_modality = {item["modality_type"]: item for item in content["modality_summary"]}
        assert by_modality["IMAGE"]["used_in_final_analysis"] is False
        assert by_modality["VIDEO"]["used_in_final_analysis"] is True

        correlation = content["clinical_correlation_summary"]
        assert correlation["included_modality_types"] == ["VIDEO"]
        assert correlation["excluded_modality_types"] == ["IMAGE"]
        assert "IMAGE" not in correlation["text"]
        assert "VIDEO" in correlation["text"]

    def test_worst_quality_state_wins_when_modality_has_multiple_original_data_findings(
        self,
    ) -> None:
        """Uma analise pode ter mais de uma midia da mesma modalidade -
        o pior estado de qualidade entre elas deve prevalecer no
        resumo consolidado."""
        adequate = ReportModalityFinding(
            modality_type="AUDIO",
            nature="ORIGINAL_DATA",
            quality_state="ADEQUATE",
            quality_metrics={},
            quality_factors=[],
            summary="Audio 1 adequado.",
            created_at="2026-07-11T10:05:00+00:00",
        )
        insufficient = ReportModalityFinding(
            modality_type="AUDIO",
            nature="ORIGINAL_DATA",
            quality_state="INSUFFICIENT",
            quality_metrics={},
            quality_factors=["duracao_curta"],
            summary="Audio 2 curto demais.",
            created_at="2026-07-11T10:06:00+00:00",
        )
        content = build_report_content(
            patient=_PATIENT,
            analysis=_ANALYSIS,
            risk=None,
            modality_findings=[adequate, insufficient],
            protocol_action_description=None,
            review=_draft_review(),
        )
        assert content["modality_summary"][0]["quality_state"] == "INSUFFICIENT"
