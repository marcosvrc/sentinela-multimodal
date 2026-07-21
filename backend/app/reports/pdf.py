"""Renderizacao do conteudo do relatorio em PDF.

Funcao pura: recebe o dict ja montado por `app.reports.builder` e devolve
bytes de PDF via `reportlab` (biblioteca pura Python, sem dependencia de
binario externo como wkhtmltopdf/weasyprint - reduz risco de instalacao em
ambientes restritos). Nao acessa banco, storage ou rede.
"""

from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_RISK_COLOR_HEX = {
    1: "#2E7D32",
    2: "#F9A825",
    3: "#EF6C00",
    4: "#C62828",
    5: "#6A1B9A",
    6: "#4A0000",
}

# Nome em portugues do dado clinico avaliado, por `ClinicalRuleSet.code`.
# Mantido em espelho manual do mapa equivalente do frontend
# (frontend/src/features/admin/clinicalDataLabels.ts) - nao ha geracao
# automatica porque o `code` vem de texto livre no YAML de seed, nao de
# um enum formal do backend.
_RULE_SET_CODE_LABELS = {
    "blood_pressure": "Pressao arterial",
    "bmi": "Indice de massa corporal (IMC)",
    "consciousness_acvpu": "Nivel de consciencia (ACVPU)",
    "gait": "Padrao de marcha",
    "glycemia_fasting": "Glicemia em jejum",
    "heart_rate": "Frequencia cardiaca",
    "movement_activity": "Movimentacao do paciente",
    "pain": "Dor",
    "posture": "Postura corporal",
    "respiratory_rate": "Frequencia respiratoria",
    "speech_alteration": "Alteracao de fala",
    "spo2": "Saturacao de oxigenio (SpO2)",
    "surgery_adverse_events": "Eventos adversos cirurgicos",
    "surgery_flow": "Fluxo procedimental cirurgico",
    "surgery_team": "Equipe cirurgica",
    "surgery_tools": "Ferramentas cirurgicas",
    "temperature": "Temperatura corporal",
}


def _rule_set_code_label(code: str) -> str:
    return _RULE_SET_CODE_LABELS.get(code, code)


_OUTCOME_LABELS = {
    "MATCHED": "Classificado",
    "INCONCLUSIVE": "Inconclusivo",
}


def _outcome_label(outcome: str) -> str:
    return _OUTCOME_LABELS.get(outcome, outcome)


_MODALITY_LABELS = {
    "IMAGE": "Imagem",
    "AUDIO": "Audio",
    "VIDEO": "Video",
    "TEXT": "Texto",
}


def _modality_label(modality_type: str) -> str:
    return _MODALITY_LABELS.get(modality_type, modality_type)


_ATTENTION_LEVEL_LABELS = {
    "NONE": "Sem pontos de atencao",
    "OBSERVATION": "Observacao",
    "ATTENTION": "Atencao",
}


def _attention_level_label(level: str) -> str:
    return _ATTENTION_LEVEL_LABELS.get(level, level)


_QUALITY_STATE_LABELS = {
    "ADEQUATE": "Adequada",
    "MODERATE": "Moderada",
    "INSUFFICIENT": "Insuficiente",
    "INVALID": "Invalida",
}


def _quality_state_label(quality_state: str) -> str:
    return _QUALITY_STATE_LABELS.get(quality_state, quality_state)


_REPORT_STATE_LABELS = {
    "DRAFT": "Rascunho",
    "CONFIRMED": "Confirmado",
}


def _report_state_label(report_state: str) -> str:
    return _REPORT_STATE_LABELS.get(report_state, report_state)


def render_report_pdf(content: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    heading = styles["Heading2"]
    body = styles["BodyText"]
    small = ParagraphStyle("Small", parent=body, fontSize=8, textColor=colors.grey)

    story = []

    story.append(Paragraph("SentinelHealth - Relatorio de Analise Multimodal", styles["Title"]))
    story.append(
        Paragraph(
            "Sistema de apoio a decisao clinica. Nao realiza diagnostico autonomo; toda "
            "classificacao esta sujeita a revisao profissional.",
            small,
        )
    )
    story.append(Spacer(1, 0.5 * cm))

    identification = content["identification"]
    patient = identification["patient"]
    story.append(Paragraph("1. Identificacao e contexto", heading))
    story.append(
        Paragraph(
            f"Analise: {identification['analysis_id']}<br/>"
            f"Paciente: {patient['full_name']} (prontuario {patient['medical_record_number']})<br/>"
            f"Nascimento: {patient['birth_date']}<br/>"
            f"Criado por: {identification['created_by']} em {identification['created_at']}",
            body,
        )
    )
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("2. Estado do relatorio", heading))
    story.append(Paragraph(_report_state_label(content["report_state"]), body))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("3. Resumo assistido por IA", heading))
    ai_summary = content["ai_summary"]
    summary_text = ai_summary["text"] or "Resumo nao disponivel."
    story.append(Paragraph(summary_text, body))
    if ai_summary.get("uncertainty_note"):
        story.append(Paragraph(f"<i>{ai_summary['uncertainty_note']}</i>", small))
    story.append(Spacer(1, 0.3 * cm))

    clinical_support = content.get("clinical_support_summary")
    if clinical_support:
        story.append(Paragraph("3.1 Apoio à análise clínica (IA)", heading))
        story.append(Paragraph(f"<b>Visão clínica:</b> {clinical_support['summary_text']}", body))
        story.append(
            Paragraph(f"<b>Causas prováveis:</b> {clinical_support['probable_causes']}", body)
        )
        story.append(
            Paragraph(
                f"<b>Direcionamento sugerido:</b> {clinical_support['suggested_next_steps']}", body
            )
        )
        story.append(Paragraph(f"<i>{clinical_support['uncertainty_note']}</i>", small))
        story.append(
            Paragraph(
                f"Gerado em {clinical_support['generated_at']} - "
                f"modelo {clinical_support['model']} - "
                f"{clinical_support['findings_considered']} achado(s) considerados.",
                small,
            )
        )
        story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("4. Risco calculado pelo motor deterministico", heading))
    risk = content["calculated_risk"]
    if risk["outcome"] == "MATCHED":
        color_hex = _RISK_COLOR_HEX.get(risk["risk_level"], "#000000")
        risk_table = Table(
            [[f"Nivel {risk['risk_level']}", risk["classification_label"]]],
            colWidths=[3 * cm, 10 * cm],
        )
        risk_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(color_hex)),
                    ("TEXTCOLOR", (0, 0), (0, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("ALIGN", (0, 0), (0, 0), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        story.append(risk_table)
    else:
        inconclusive_text = (
            f"Inconclusivo. Motivo: {risk['inconclusive_reason']} - {risk['inconclusive_detail']}"
        )
        story.append(Paragraph(inconclusive_text, body))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("5. Nivel de atencao por modalidade", heading))
    story.append(
        Paragraph(
            "Indicador visual de apoio a leitura, derivado das observacoes/hipoteses ja "
            "listadas nas secoes 7 e 8 - NUNCA e um calculo de risco clinico (risco e sempre "
            "exclusivo do motor de regras deterministico).",
            small,
        )
    )
    if content.get("modality_attention"):
        rows = [["Modalidade", "Nivel"]]
        for item in content["modality_attention"]:
            rows.append(
                [_modality_label(item["modality_type"]), _attention_level_label(item["level"])]
            )
        table = Table(rows, colWidths=[4 * cm, 4 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                ]
            )
        )
        story.append(table)
    else:
        story.append(Paragraph("Nenhuma modalidade processada nesta analise.", body))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("6. Achados deterministicos", heading))
    if content["deterministic_findings"]:
        rows = [["Dado clinico", "Resultado", "Nivel", "Classificacao"]]
        for item in content["deterministic_findings"]:
            rows.append(
                [
                    _rule_set_code_label(item["code"]),
                    _outcome_label(item["outcome"]),
                    str(item["risk_level"] or "-"),
                    item["classification_label"] or item["inconclusive_reason"] or "-",
                ]
            )
        table = Table(rows, colWidths=[4 * cm, 3 * cm, 2 * cm, 5 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                ]
            )
        )
        story.append(table)
    else:
        story.append(Paragraph("Nenhuma entrada clinica estruturada avaliada.", body))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("7. Observacoes derivadas dos modelos", heading))
    if content["model_observations"]:
        for item in content["model_observations"]:
            story.append(
                Paragraph(
                    f"<b>{_modality_label(item['modality_type'])}</b> "
                    f"({item['observed_at']}): {item['summary']}",
                    body,
                )
            )
    else:
        story.append(
            Paragraph(
                "Nenhuma observacao de modelo disponivel para esta analise (modalidade sem "
                "processador de reconhecimento de conteudo integrado, ou nenhum termo "
                "candidato identificado).",
                body,
            )
        )
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("8. Hipoteses assistidas nao confirmadas", heading))
    if content["assisted_hypotheses"]:
        for item in content["assisted_hypotheses"]:
            story.append(
                Paragraph(
                    f"<b>{_modality_label(item['modality_type'])}</b> "
                    f"({item['observed_at']}): {item['summary']} "
                    "<i>(hipotese nao confirmada)</i>",
                    body,
                )
            )
    else:
        story.append(Paragraph("Nenhuma hipotese assistida gerada para esta analise.", body))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("9. Evidencias por modalidade e qualidade tecnica", heading))
    if content["modality_evidence"]:
        for item in content["modality_evidence"]:
            factors = ", ".join(item["quality_factors"]) or "nenhum fator relevante"
            story.append(
                Paragraph(
                    f"<b>{_modality_label(item['modality_type'])}</b> "
                    f"({item['observed_at']}): {item['summary']} - "
                    f"Qualidade: {_quality_state_label(item['quality_state'])} ({factors})",
                    body,
                )
            )
    else:
        story.append(Paragraph("Nenhuma evidencia de modalidade registrada.", body))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("10. Inconsistencias, dados ausentes ou desatualizados", heading))
    if content["inconsistencies"]:
        for item in content["inconsistencies"]:
            story.append(Paragraph(f"- {item}", body))
    else:
        story.append(Paragraph("Nenhuma inconsistencia identificada.", body))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("11. Condutas sistemicas previstas pelo protocolo", heading))
    story.append(Paragraph(content["protocol_conduct"] or "Nenhuma conduta associada.", body))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("12. Revisao e decisao do profissional", heading))
    review = content["professional_review"]
    if review["confirmed_by"]:
        story.append(
            Paragraph(f"Confirmado por {review['confirmed_by']} em {review['confirmed_at']}.", body)
        )
    else:
        story.append(Paragraph("Aguardando confirmacao do profissional responsavel.", body))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("13. Proveniencia e versoes", heading))
    provenance = content["provenance"]
    evaluated_rule_labels = [
        _rule_set_code_label(code) for code in provenance["rule_codes_evaluated"]
    ]
    story.append(
        Paragraph(
            f"Regras avaliadas: {', '.join(evaluated_rule_labels) or 'nenhuma'}<br/>"
            f"LLM: {provenance['llm_provider'] or '-'} / {provenance['llm_model'] or '-'} "
            f"(prompt {provenance['llm_prompt_version'] or '-'})<br/>"
            f"Hash entrada/saida do LLM: {provenance['llm_input_hash'] or '-'} / "
            f"{provenance['llm_output_hash'] or '-'}",
            small,
        )
    )

    doc.build(story)
    return buffer.getvalue()
