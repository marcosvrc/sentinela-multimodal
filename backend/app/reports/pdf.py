"""Renderizacao do conteudo do relatorio em PDF.

Funcao pura: recebe o dict ja montado por `app.reports.builder` e devolve
bytes de PDF via `reportlab` (biblioteca pura Python, sem dependencia de
binario externo como wkhtmltopdf/weasyprint - reduz risco de instalacao em
ambientes restritos). Nao acessa banco, storage ou rede.

Estrutura segue os 3 blocos da tela de revisao:
  A - Dados clinicos estruturados (risco + achados + conduta)
  B - Dados multimodais (termos + observacoes + hipoteses + tecnico)
  C - Analise consolidada IA (risco assistido + resumo + apoio clinico)
"""

from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _format_datetime(value: str | None) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return value


_RISK_COLOR_HEX = {
    1: "#1f8a4c",
    2: "#b7860b",
    3: "#c2650a",
    4: "#d1372b",
    5: "#8b2fc4",
    6: "#7a0d1f",
}

_RULE_SET_CODE_LABELS = {
    "blood_pressure": "Pressão arterial",
    "bmi": "Índice de massa corporal (IMC)",
    "consciousness_acvpu": "Nível de consciência (ACVPU)",
    "gait": "Padrão de marcha",
    "glycemia_fasting": "Glicemia em jejum",
    "heart_rate": "Frequência cardíaca",
    "movement_activity": "Movimentação do paciente",
    "pain": "Dor",
    "posture": "Postura corporal",
    "respiratory_rate": "Frequência respiratória",
    "seizure": "Convulsão",
    "speech_alteration": "Alteração de fala",
    "spo2": "Saturação de oxigênio (SpO2)",
    "surgery_adverse_events": "Eventos adversos cirúrgicos",
    "surgery_flow": "Fluxo procedimental cirúrgico",
    "surgery_team": "Equipe cirúrgica",
    "surgery_tools": "Ferramentas cirúrgicas",
    "temperature": "Temperatura corporal",
    "urine_output": "Débito urinário",
}


def _rule_set_code_label(code: str) -> str:
    return _RULE_SET_CODE_LABELS.get(code, code)


_MODALITY_LABELS = {"IMAGE": "Imagem", "AUDIO": "Áudio", "VIDEO": "Vídeo", "TEXT": "Texto"}


def _modality_label(modality_type: str) -> str:
    return _MODALITY_LABELS.get(modality_type, modality_type)


_QUALITY_STATE_LABELS = {
    "ADEQUATE": "Adequada", "MODERATE": "Moderada",
    "INSUFFICIENT": "Insuficiente", "INVALID": "Inválida",
}


def _quality_state_label(quality_state: str) -> str:
    return _QUALITY_STATE_LABELS.get(quality_state, quality_state)


_NEGATION_LABELS = {"AFFIRMED": "Presente", "NEGATED": "Negado"}
_TEMPORALITY_LABELS = {"CURRENT": "Atual", "PAST": "Passado", "FUTURE": "Futuro"}
_CERTAINTY_LABELS = {
    "CONFIRMED": "Confirmado", "SUSPECTED": "Suspeito",
    "POSSIBLE": "Possível", "CONDITIONAL": "Condicional",
}
_EXPERIENCER_LABELS = {"PATIENT": "Paciente", "FAMILY_MEMBER": "Familiar", "OTHER": "Outro"}


def _negation_label(v: str) -> str:
    return _NEGATION_LABELS.get(v, v.capitalize() if v else "-")


def _temporality_label(v: str) -> str:
    return _TEMPORALITY_LABELS.get(v, v.capitalize() if v else "-")


def _certainty_label(v: str) -> str:
    return _CERTAINTY_LABELS.get(v, v.capitalize() if v else "-")


def _experiencer_label(v: str) -> str:
    return _EXPERIENCER_LABELS.get(v, v.capitalize() if v else "-")


_REPORT_STATE_LABELS = {"DRAFT": "Rascunho", "CONFIRMED": "Confirmado"}


def render_report_pdf(content: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    heading = styles["Heading2"]
    body = styles["BodyText"]
    small = ParagraphStyle("Small", parent=body, fontSize=8, textColor=colors.grey)
    cell_style = ParagraphStyle(
        "CellText", parent=body, fontSize=8, leading=10, spaceBefore=1, spaceAfter=1
    )
    block_heading = ParagraphStyle(
        "BlockHeading", parent=heading, fontSize=13,
        textColor=colors.HexColor("#333333"), spaceAfter=6,
    )

    story = []

    # === CABEÇALHO ===
    story.append(Paragraph("SentinelHealth - Relatório de Análise Multimodal", styles["Title"]))
    story.append(Paragraph(
        "Sistema de apoio a decisão clínica. Não realiza diagnóstico autônomo; toda "
        "classificação está sujeita a revisão profissional.", small,
    ))
    story.append(Spacer(1, 0.5 * cm))

    # === PACIENTE ===
    identification = content["identification"]
    patient = identification["patient"]
    story.append(Paragraph("Paciente", heading))
    story.append(Paragraph(
        f"<b>{patient['full_name']}</b> · Prontuário: {patient['medical_record_number']} · "
        f"Nascimento: {patient['birth_date']}<br/>"
        f"Profissional: {identification['created_by']} · "
        f"Data da análise: {_format_datetime(identification['created_at'])} · "
        f"Status: {_REPORT_STATE_LABELS.get(content['report_state'], content['report_state'])}",
        body,
    ))
    story.append(Spacer(1, 0.5 * cm))

    # ══════════════════════════════════════════════════════════════════
    # BLOCO A — DADOS CLÍNICOS ESTRUTURADOS
    # ══════════════════════════════════════════════════════════════════
    story.append(Paragraph("A. DADOS CLÍNICOS ESTRUTURADOS", block_heading))
    story.append(Paragraph(
        "Resultado do motor de regras determinístico — única fonte de classificação de risco.",
        small,
    ))
    story.append(Spacer(1, 0.2 * cm))

    # Risco calculado
    risk = content["calculated_risk"]
    if risk["outcome"] == "MATCHED":
        color_hex = _RISK_COLOR_HEX.get(risk["risk_level"], "#000000")
        risk_table = Table(
            [[f"Nível {risk['risk_level']}", risk["classification_label"]]],
            colWidths=[3 * cm, 10 * cm],
        )
        risk_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(color_hex)),
            ("TEXTCOLOR", (0, 0), (0, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 11),
            ("ALIGN", (0, 0), (0, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(risk_table)
    else:
        story.append(Paragraph(
            f"Inconclusivo — {risk.get('inconclusive_reason', '-')}: "
            f"{risk.get('inconclusive_detail', 'sem detalhe')}",
            body,
        ))
    story.append(Spacer(1, 0.3 * cm))

    # Achados determinísticos
    story.append(Paragraph("Achados determinísticos", heading))
    if content["deterministic_findings"]:
        det_rows = [[
            Paragraph("<b>Dado clínico</b>", cell_style),
            Paragraph("<b>Resultado</b>", cell_style),
            Paragraph("<b>Nível</b>", cell_style),
            Paragraph("<b>Classificação</b>", cell_style),
        ]]
        for item in content["deterministic_findings"]:
            det_rows.append([
                Paragraph(_rule_set_code_label(item["code"]), cell_style),
                Paragraph(
                    "Classificado" if item["outcome"] == "MATCHED" else "Inconclusivo",
                    cell_style,
                ),
                Paragraph(str(item["risk_level"] or "-"), cell_style),
                Paragraph(
                    item["classification_label"] or item.get("inconclusive_reason") or "-",
                    cell_style,
                ),
            ])
        table = Table(det_rows, colWidths=[4 * cm, 3 * cm, 1.5 * cm, 7.5 * cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("Nenhuma entrada clínica estruturada avaliada.", body))
    story.append(Spacer(1, 0.2 * cm))

    # Conduta
    story.append(Paragraph("Conduta prevista pelo protocolo", heading))
    story.append(Paragraph(content.get("protocol_conduct") or "Nenhuma conduta associada.", body))
    story.append(Spacer(1, 0.5 * cm))

    # ══════════════════════════════════════════════════════════════════
    # BLOCO B — DADOS MULTIMODAIS
    # ══════════════════════════════════════════════════════════════════
    story.append(Paragraph("B. DADOS MULTIMODAIS (áudio, vídeo, imagem, texto)", block_heading))
    story.append(Paragraph(
        "Achados produzidos pelos processadores de cada tipo de dado. "
        "Nunca determinam o nível de risco — são informações de apoio.",
        small,
    ))
    story.append(Spacer(1, 0.2 * cm))

    # Termos clínicos (tabela agrupada)
    clinical_terms = [
        item for item in content["model_observations"]
        if item.get("details", {}).get("term") and item.get("details", {}).get("extraction_method")
    ]
    if clinical_terms:
        story.append(Paragraph("Termos clínicos identificados", heading))
        term_rows = [[
            Paragraph("<b>Termo</b>", cell_style),
            Paragraph("<b>Status</b>", cell_style),
            Paragraph("<b>Temporalidade</b>", cell_style),
            Paragraph("<b>Certeza</b>", cell_style),
            Paragraph("<b>Experienciador</b>", cell_style),
        ]]
        # Agrupa por atributos
        seen: dict[str, int] = {}
        grouped_terms: list[tuple[dict, int]] = []
        for item in clinical_terms:
            d = item["details"]
            key = f"{d.get('term')}|{d.get('negation')}|{d.get('temporality')}|{d.get('certainty')}|{d.get('experiencer')}"
            if key in seen:
                idx = seen[key]
                grouped_terms[idx] = (grouped_terms[idx][0], grouped_terms[idx][1] + 1)
            else:
                seen[key] = len(grouped_terms)
                grouped_terms.append((item, 1))

        for item, count in grouped_terms:
            d = item["details"]
            term_text = f"<b>{d.get('term', '-')}</b>"
            if count > 1:
                term_text += f" (x{count})"
            term_rows.append([
                Paragraph(term_text, cell_style),
                Paragraph(_negation_label(d.get("negation", "")), cell_style),
                Paragraph(_temporality_label(d.get("temporality", "")), cell_style),
                Paragraph(_certainty_label(d.get("certainty", "")), cell_style),
                Paragraph(_experiencer_label(d.get("experiencer", "")), cell_style),
            ])
        table = Table(term_rows, colWidths=[3.5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(table)
        story.append(Spacer(1, 0.3 * cm))

    # Outras observações
    other_obs = [
        item for item in content["model_observations"]
        if not (item.get("details", {}).get("term") and item.get("details", {}).get("extraction_method"))
    ]
    if other_obs:
        story.append(Paragraph("Outras observações dos processadores", heading))
        obs_rows = [[
            Paragraph("<b>Modalidade</b>", cell_style),
            Paragraph("<b>Data/hora</b>", cell_style),
            Paragraph("<b>Observação</b>", cell_style),
        ]]
        for item in other_obs:
            obs_rows.append([
                Paragraph(_modality_label(item["modality_type"]), cell_style),
                Paragraph(_format_datetime(item["observed_at"]), cell_style),
                Paragraph(item["summary"], cell_style),
            ])
        table = Table(obs_rows, colWidths=[2.5 * cm, 3 * cm, 10.5 * cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(table)
        story.append(Spacer(1, 0.3 * cm))

    # Hipóteses assistidas
    if content["assisted_hypotheses"]:
        story.append(Paragraph("Hipóteses assistidas não confirmadas", heading))
        hyp_rows = [[
            Paragraph("<b>Modalidade</b>", cell_style),
            Paragraph("<b>Data/hora</b>", cell_style),
            Paragraph("<b>Hipótese</b>", cell_style),
        ]]
        for item in content["assisted_hypotheses"]:
            hyp_rows.append([
                Paragraph(_modality_label(item["modality_type"]), cell_style),
                Paragraph(_format_datetime(item["observed_at"]), cell_style),
                Paragraph(f"{item['summary']} <i>(não confirmada)</i>", cell_style),
            ])
        table = Table(hyp_rows, colWidths=[2.5 * cm, 3 * cm, 10.5 * cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(table)
        story.append(Spacer(1, 0.3 * cm))

    # Detalhamento técnico
    evidence_items = [e for e in content["modality_evidence"] if "termo clinico candidato" not in e["summary"].lower()]
    if evidence_items:
        story.append(Paragraph("Detalhamento técnico", heading))
        ev_rows = [[
            Paragraph("<b>Modalidade</b>", cell_style),
            Paragraph("<b>Data/hora</b>", cell_style),
            Paragraph("<b>Qualidade</b>", cell_style),
            Paragraph("<b>Fatores</b>", cell_style),
            Paragraph("<b>Resumo</b>", cell_style),
        ]]
        for item in evidence_items:
            factors = ", ".join(item.get("quality_factors") or []) or "-"
            ev_rows.append([
                Paragraph(_modality_label(item["modality_type"]), cell_style),
                Paragraph(_format_datetime(item["observed_at"]), cell_style),
                Paragraph(_quality_state_label(item.get("quality_state") or ""), cell_style),
                Paragraph(factors, cell_style),
                Paragraph(item["summary"], cell_style),
            ])
        table = Table(ev_rows, colWidths=[2 * cm, 2.5 * cm, 2.5 * cm, 3 * cm, 6 * cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(table)
    story.append(Spacer(1, 0.5 * cm))

    # ══════════════════════════════════════════════════════════════════
    # BLOCO C — ANÁLISE CONSOLIDADA (IA)
    # ══════════════════════════════════════════════════════════════════
    story.append(Paragraph("C. ANÁLISE CONSOLIDADA (IA)", block_heading))
    story.append(Paragraph(
        "Correlaciona dados clínicos + multimodais via inteligência artificial. "
        "Nunca substitui a avaliação do profissional.",
        small,
    ))
    story.append(Spacer(1, 0.2 * cm))

    # Risco assistido por IA
    assisted_risk = content.get("assisted_risk")
    if assisted_risk:
        ar_color = _RISK_COLOR_HEX.get(assisted_risk["risk_level"], "#5b6472")
        ar_table = Table(
            [[f"Nível {assisted_risk['risk_level']}", assisted_risk["classification_label"]]],
            colWidths=[3 * cm, 10 * cm],
        )
        ar_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(ar_color)),
            ("TEXTCOLOR", (0, 0), (0, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 11),
            ("ALIGN", (0, 0), (0, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(Paragraph("Risco sugerido por IA (dados multimodais)", heading))
        story.append(ar_table)
        story.append(Paragraph(assisted_risk["justification"], body))
        if assisted_risk.get("uncertainty_note"):
            story.append(Paragraph(f"<i>{assisted_risk['uncertainty_note']}</i>", small))
        story.append(Spacer(1, 0.3 * cm))

    # Resumo explicativo
    story.append(Paragraph("Resumo explicativo", heading))
    ai_summary = content["ai_summary"]
    story.append(Paragraph(ai_summary["text"] or "Resumo não disponível.", body))
    if ai_summary.get("uncertainty_note"):
        story.append(Paragraph(f"<i>{ai_summary['uncertainty_note']}</i>", small))
    story.append(Spacer(1, 0.3 * cm))

    # Apoio à análise clínica
    clinical_support = content.get("clinical_support_summary")
    if clinical_support:
        story.append(Paragraph("Apoio à análise clínica (IA)", heading))
        story.append(Paragraph(f"<b>Visão clínica:</b> {clinical_support['summary_text']}", body))
        story.append(Paragraph(f"<b>Causas prováveis:</b> {clinical_support['probable_causes']}", body))
        story.append(Paragraph(f"<b>Direcionamento sugerido:</b> {clinical_support['suggested_next_steps']}", body))
        story.append(Paragraph(f"<i>{clinical_support['uncertainty_note']}</i>", small))
        story.append(Paragraph(
            f"Gerado em {_format_datetime(clinical_support['generated_at'])} · "
            f"modelo {clinical_support['model']} · "
            f"{clinical_support['findings_considered']} achado(s) considerados.",
            small,
        ))
    story.append(Spacer(1, 0.5 * cm))

    # ══════════════════════════════════════════════════════════════════
    # SEÇÕES FINAIS
    # ══════════════════════════════════════════════════════════════════
    if content["inconsistencies"]:
        story.append(Paragraph("Inconsistências e dados ausentes", heading))
        for item in content["inconsistencies"]:
            story.append(Paragraph(f"• {item}", body))
        story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("Revisão e decisão do profissional", heading))
    review = content["professional_review"]
    if review["confirmed_by"]:
        story.append(Paragraph(
            f"Confirmado por {review['confirmed_by']} em {_format_datetime(review['confirmed_at'])}.",
            body,
        ))
    else:
        story.append(Paragraph("Aguardando confirmação do profissional responsável.", body))
    story.append(Spacer(1, 0.3 * cm))

    # Proveniência
    story.append(Paragraph("Proveniência e versões", heading))
    provenance = content["provenance"]
    evaluated_rule_labels = [_rule_set_code_label(c) for c in provenance["rule_codes_evaluated"]]
    story.append(Paragraph(
        f"Regras avaliadas: {', '.join(evaluated_rule_labels) or 'nenhuma'}<br/>"
        f"LLM: {provenance['llm_provider'] or '-'} / {provenance['llm_model'] or '-'} "
        f"(prompt {provenance['llm_prompt_version'] or '-'})<br/>"
        f"Hash entrada/saída: {provenance['llm_input_hash'] or '-'} / "
        f"{provenance['llm_output_hash'] or '-'}",
        small,
    ))

    doc.build(story)
    return buffer.getvalue()
