import styles from "./AnalysisReviewStats.module.css";
import type { AnalysisStats, ReportContent } from "@/types/analysis";
import { modalityLabel } from "@/app/enumLabels";
import { InfoButton } from "@/components/ui/InfoButton";

const RISK_COLOR_BY_LEVEL: Record<number, string> = {
  1: "var(--risk-low)",
  2: "var(--risk-mild)",
  3: "var(--risk-moderate)",
  4: "var(--risk-high)",
  5: "var(--risk-very-high)",
  6: "var(--risk-critical)",
};

interface ClinicalDataStatsProps {
  content: ReportContent;
  stats: AnalysisStats | undefined;
}

/** Big numbers do bloco A — dados clínicos estruturados. */
export function ClinicalDataStats({ content, stats }: ClinicalDataStatsProps) {
  const isConclusive = content.calculated_risk.outcome === "MATCHED";
  const riskLevel = content.calculated_risk.risk_level;
  const riskColor = riskLevel !== null ? RISK_COLOR_BY_LEVEL[riskLevel] : "var(--risk-inconclusive)";
  const hasClinicalData = Object.keys(content.identification.structured_clinical_inputs).length > 0;

  return (
    <div className={styles.cardsGrid}>
      <div className={styles.card} style={{ background: riskColor, color: "#fff", borderColor: riskColor }}>
        <span className={styles.cardLabel} style={{ color: "rgba(255,255,255,0.85)" }}>
          Nível de risco
          <InfoButton title="Escala de risco clínico" size="sm">
            <p>Classificação calculada exclusivamente pelo motor de regras determinístico:</p>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, marginTop: 8 }}>
              <tbody>
                <tr style={{ borderBottom: "1px solid #eee" }}><td style={{ padding: "4px 8px" }}><span style={{ display: "inline-block", width: 14, height: 14, borderRadius: 3, background: "#1f8a4c", verticalAlign: "middle", marginRight: 6 }} />1</td><td style={{ padding: "4px 8px" }}>Baixo — Registrar e seguir rotina</td></tr>
                <tr style={{ borderBottom: "1px solid #eee" }}><td style={{ padding: "4px 8px" }}><span style={{ display: "inline-block", width: 14, height: 14, borderRadius: 3, background: "#b7860b", verticalAlign: "middle", marginRight: 6 }} />2</td><td style={{ padding: "4px 8px" }}>Leve — Acompanhar ou repetir medição</td></tr>
                <tr style={{ borderBottom: "1px solid #eee" }}><td style={{ padding: "4px 8px" }}><span style={{ display: "inline-block", width: 14, height: 14, borderRadius: 3, background: "#c2650a", verticalAlign: "middle", marginRight: 6 }} />3</td><td style={{ padding: "4px 8px" }}>Moderado — Solicitar avaliação clínica</td></tr>
                <tr style={{ borderBottom: "1px solid #eee" }}><td style={{ padding: "4px 8px" }}><span style={{ display: "inline-block", width: 14, height: 14, borderRadius: 3, background: "#d1372b", verticalAlign: "middle", marginRight: 6 }} />4</td><td style={{ padding: "4px 8px" }}>Alto — Alertar equipe assistencial</td></tr>
                <tr style={{ borderBottom: "1px solid #eee" }}><td style={{ padding: "4px 8px" }}><span style={{ display: "inline-block", width: 14, height: 14, borderRadius: 3, background: "#8b2fc4", verticalAlign: "middle", marginRight: 6 }} />5</td><td style={{ padding: "4px 8px" }}>Muito alto — Intervenção prioritária</td></tr>
                <tr style={{ borderBottom: "1px solid #eee" }}><td style={{ padding: "4px 8px" }}><span style={{ display: "inline-block", width: 14, height: 14, borderRadius: 3, background: "#7a0d1f", verticalAlign: "middle", marginRight: 6 }} />6</td><td style={{ padding: "4px 8px" }}>Crítico — Seguir protocolo de emergência</td></tr>
                <tr><td style={{ padding: "4px 8px" }}><span style={{ display: "inline-block", width: 14, height: 14, borderRadius: 3, background: "#5b6472", verticalAlign: "middle", marginRight: 6 }} />-</td><td style={{ padding: "4px 8px" }}>Inconclusivo — Sem dados ou regra aplicável</td></tr>
              </tbody>
            </table>
            <p style={{ marginTop: 8, fontSize: 12, color: "#666" }}>Fonte: motor de regras determinístico sobre sinais vitais. Nunca influenciado por IA.</p>
          </InfoButton>
        </span>
        <span className={styles.cardNumber}>{riskLevel ?? "-"}</span>
        <span className={styles.cardHint} style={{ color: "rgba(255,255,255,0.9)" }}>{content.calculated_risk.classification_label ?? "Sem classificação"}</span>
      </div>

      <div className={styles.card} style={{ color: hasClinicalData ? "var(--risk-low)" : "var(--risk-inconclusive)" }}>
        <span className={styles.cardLabel}>
          Dados informados
          <InfoButton title="Dados clínicos informados" size="sm">
            <p>Quantidade de sinais vitais estruturados incluídos nesta análise (ex.: pressão arterial, SpO₂, frequência cardíaca).</p>
            <p style={{ marginTop: 8 }}><strong>0</strong> = nenhum dado clínico foi informado — o motor de regras não tem como calcular risco (resultado será Inconclusivo).</p>
            <p style={{ marginTop: 4 }}><strong>1+</strong> = cada sinal é avaliado independentemente contra as regras publicadas.</p>
          </InfoButton>
        </span>
        <span className={styles.cardNumber}>{hasClinicalData ? Object.keys(content.identification.structured_clinical_inputs).length : "0"}</span>
        <span className={styles.cardHint}>{hasClinicalData ? "sinal(is) avaliado(s)" : "Sem dados para o motor de regras"}</span>
      </div>
      <div className={styles.card} style={{ color: isConclusive ? "var(--risk-low)" : "var(--risk-inconclusive)" }}>
        <span className={styles.cardLabel}>
          Resultado
          <InfoButton title="Resultado da avaliação" size="sm">
            <p><strong>Conclusivo</strong> = o motor de regras encontrou ao menos uma regra publicada que casou com os valores informados — um nível de risco (1 a 6) foi calculado.</p>
            <p style={{ marginTop: 8 }}><strong>Inconclusivo</strong> = nenhuma regra casou. Possíveis causas:</p>
            <ul style={{ margin: "4px 0 0 16px", fontSize: 13 }}>
              <li>Dados clínicos não informados</li>
              <li>Regras para o código ainda não publicadas</li>
              <li>Valores fora das faixas cobertas pelas regras</li>
            </ul>
            <p style={{ marginTop: 8, fontSize: 12, color: "#666" }}>Inconclusivo NÃO significa "normal" — significa que o sistema não pode classificar.</p>
          </InfoButton>
        </span>
        <span className={styles.cardNumber}>{isConclusive ? "Conclusivo" : "Inconclusivo"}</span>
        <span className={styles.cardHint}>{isConclusive ? "Regra aplicável encontrada" : "Sem regra aplicável"}</span>
      </div>
      <div className={styles.card}>
        <span className={styles.cardLabel}>
          Taxa conclusiva
          <InfoButton title="Taxa de análises conclusivas" size="sm">
            <p>Percentual de todas as análises da instituição que resultaram em classificação conclusiva (regra encontrada).</p>
            <p style={{ marginTop: 8 }}>Uma taxa baixa pode indicar: falta de regras publicadas para certos sinais, ou muitas análises submetidas sem dados clínicos estruturados.</p>
          </InfoButton>
        </span>
        <span className={styles.cardNumber}>{stats ? `${stats.conclusive_rate_percent}%` : "-"}</span>
        <span className={styles.cardHint}>{stats ? `${stats.conclusive_count} de ${stats.total_analyses_consolidated}` : "Carregando..."}</span>
      </div>
    </div>
  );
}

interface MultimodalStatsProps {
  content: ReportContent;
}

/** Big numbers do bloco B — dados multimodais. */
export function MultimodalStats({ content }: MultimodalStatsProps) {
  const modalityTypes = [...new Set(content.modality_evidence.map((item) => item.modality_type))];
  const clinicalTerms = content.model_observations.filter((o) => o.details?.term && o.details?.extraction_method);
  const hypothesesCount = content.assisted_hypotheses.length;
  const relevantModalities = (content.modality_summary ?? []).filter((m) => m.clinically_relevant);

  // Qualidade geral: pior qualidade entre todas as modalidades (ORIGINAL_DATA)
  const qualityOrder = ["ADEQUATE", "MODERATE", "INSUFFICIENT", "INVALID"];
  const qualityLabels: Record<string, string> = { ADEQUATE: "Adequada", MODERATE: "Moderada", INSUFFICIENT: "Insuficiente", INVALID: "Inválida" };
  const qualityColors: Record<string, string> = { ADEQUATE: "var(--risk-low)", MODERATE: "var(--risk-mild)", INSUFFICIENT: "var(--risk-moderate)", INVALID: "var(--risk-high)" };
  const evidenceQualities = content.modality_evidence
    .map((e) => e.quality_state as string | undefined)
    .filter((q): q is string => !!q);
  const worstQualityIdx = Math.max(...evidenceQualities.map((q) => qualityOrder.indexOf(q)), 0);
  const worstQuality = qualityOrder[worstQualityIdx] || "ADEQUATE";

  return (
    <div className={styles.cardsGrid}>
      <div className={styles.card}>
        <span className={styles.cardLabel}>
          Modalidades
          <InfoButton title="Modalidades processadas" size="sm">
            <p>Tipos de dado enviados e processados nesta análise:</p>
            <ul style={{ margin: "4px 0 0 16px", fontSize: 13 }}>
              <li><strong>Áudio</strong> — gravações de consulta (transcrição + análise acústica)</li>
              <li><strong>Vídeo</strong> — sessões de fisioterapia, cirurgias (pose + detecção)</li>
              <li><strong>Imagem</strong> — fotos clínicas, radiografias (categorização + rótulos)</li>
              <li><strong>Texto</strong> — anotações do profissional (extração de termos NegEx)</li>
            </ul>
          </InfoButton>
        </span>
        <span className={styles.cardNumber}>{modalityTypes.length}</span>
        <span className={styles.cardHint}>{modalityTypes.map((t) => modalityLabel(t)).join(", ") || "-"}</span>
      </div>
      <div className={styles.card} style={{ color: relevantModalities.length > 0 ? "var(--risk-low)" : "var(--risk-inconclusive)" }}>
        <span className={styles.cardLabel}>
          Com relevância clínica
          <InfoButton title="Relevância clínica" size="sm">
            <p>Quantidade de modalidades que apresentaram achados clinicamente significativos:</p>
            <ul style={{ margin: "4px 0 0 16px", fontSize: 13 }}>
              <li>Termos clínicos identificados no texto/transcrição</li>
              <li>Hipótese de alteração vocal no áudio</li>
              <li>Rótulos médicos reconhecidos na imagem</li>
            </ul>
            <p style={{ marginTop: 8, fontSize: 12, color: "#666" }}>Modalidades sem relevância clínica (ex.: foto de paisagem, áudio de música) são desconsideradas na correlação final.</p>
          </InfoButton>
        </span>
        <span className={styles.cardNumber}>{relevantModalities.length}</span>
        <span className={styles.cardHint}>{relevantModalities.length > 0 ? relevantModalities.map((m) => modalityLabel(m.modality_type)).join(", ") : "Nenhuma"}</span>
      </div>
      <div className={styles.card}>
        <span className={styles.cardLabel}>
          Termos clínicos
          <InfoButton title="Termos clínicos extraídos" size="sm">
            <p>Quantidade de termos médicos/clínicos identificados automaticamente no texto e/ou transcrição de áudio pelo motor NegEx/ConText.</p>
            <p style={{ marginTop: 8 }}>Cada termo traz contexto: se está <strong>presente</strong> ou <strong>negado</strong>, se é <strong>atual</strong> ou passado, e o grau de <strong>certeza</strong>.</p>
            <p style={{ marginTop: 8, fontSize: 12, color: "#666" }}>Exemplos: "dor torácica" (presente), "febre" (negado pelo paciente), "dispneia" (suspeita).</p>
          </InfoButton>
        </span>
        <span className={styles.cardNumber}>{clinicalTerms.length}</span>
        <span className={styles.cardHint}>{clinicalTerms.length > 0 ? "Extraídos do texto/transcrição" : "Nenhum identificado"}</span>
      </div>
      <div className={styles.card} style={{ color: hypothesesCount > 0 ? "var(--risk-moderate)" : undefined }}>
        <span className={styles.cardLabel}>
          Hipóteses
          <InfoButton title="Hipóteses assistidas" size="sm">
            <p>Hipóteses geradas automaticamente pelos processadores de modalidade que requerem avaliação do profissional:</p>
            <ul style={{ margin: "4px 0 0 16px", fontSize: 13 }}>
              <li><strong>Possível redução de energia vocal</strong> — detectada na análise acústica do áudio</li>
              <li><strong>Possível padrão de fala fragmentada</strong> — proporção de pausas elevada</li>
              <li><strong>Possível ausência de pessoa</strong> — nenhuma pessoa detectada nos quadros de vídeo</li>
            </ul>
            <p style={{ marginTop: 8, fontSize: 12, color: "#666" }}>São sugestões, nunca diagnóstico. O profissional deve avaliar cada uma individualmente.</p>
          </InfoButton>
        </span>
        <span className={styles.cardNumber}>{hypothesesCount}</span>
        <span className={styles.cardHint}>{hypothesesCount > 0 ? "Requerem avaliação" : "Nenhuma gerada"}</span>
      </div>
      <div className={styles.card} style={{ color: qualityColors[worstQuality] }}>
        <span className={styles.cardLabel}>
          Qualidade geral
          <InfoButton title="Qualidade e confiabilidade dos dados" size="md">
            <p>Indicador da <strong>pior qualidade</strong> encontrada entre todas as modalidades processadas.</p>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, marginTop: 8 }}>
              <tbody>
                <tr style={{ borderBottom: "1px solid #eee" }}><td style={{ padding: "4px 8px" }}><span style={{ display: "inline-block", width: 12, height: 12, borderRadius: 3, background: "#1f8a4c", verticalAlign: "middle", marginRight: 6 }} /></td><td style={{ padding: "4px 8px" }}><strong>Adequada</strong> — todos os dados com qualidade boa</td></tr>
                <tr style={{ borderBottom: "1px solid #eee" }}><td style={{ padding: "4px 8px" }}><span style={{ display: "inline-block", width: 12, height: 12, borderRadius: 3, background: "#b7860b", verticalAlign: "middle", marginRight: 6 }} /></td><td style={{ padding: "4px 8px" }}><strong>Moderada</strong> — aceitável, mas com ressalvas</td></tr>
                <tr style={{ borderBottom: "1px solid #eee" }}><td style={{ padding: "4px 8px" }}><span style={{ display: "inline-block", width: 12, height: 12, borderRadius: 3, background: "#c2650a", verticalAlign: "middle", marginRight: 6 }} /></td><td style={{ padding: "4px 8px" }}><strong>Insuficiente</strong> — pode comprometer a análise</td></tr>
                <tr><td style={{ padding: "4px 8px" }}><span style={{ display: "inline-block", width: 12, height: 12, borderRadius: 3, background: "#d1372b", verticalAlign: "middle", marginRight: 6 }} /></td><td style={{ padding: "4px 8px" }}><strong>Inválida</strong> — dado não utilizável</td></tr>
              </tbody>
            </table>
            <h4 style={{ marginTop: 12, marginBottom: 6 }}>Confiabilidade por modalidade</h4>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, marginTop: 4 }}>
              <thead><tr style={{ borderBottom: "1px solid #ddd", textAlign: "left" }}><th style={{ padding: "4px 6px" }}>Modalidade</th><th style={{ padding: "4px 6px" }}>Qualidade</th><th style={{ padding: "4px 6px" }}>Indicadores</th></tr></thead>
              <tbody>
                {(() => {
                  const byMod = new Map<string, { quality: string; scores: string }>();
                  for (const e of content.modality_evidence) {
                    if (!byMod.has(e.modality_type)) {
                      byMod.set(e.modality_type, { quality: e.quality_state || "-", scores: "-" });
                    }
                  }
                  // Enrich with sentiment scores if available
                  for (const o of content.model_observations) {
                    const scores = o.details?.scores as Record<string, number> | undefined;
                    if (scores && byMod.has(o.modality_type)) {
                      const entry = byMod.get(o.modality_type)!;
                      // Sentiment scores: mostrar como "Sentimento" não como confiança
                      const sentiment = o.details?.sentiment as string | undefined;
                      if (sentiment && entry.scores === "-") {
                        const sentLabel = sentiment === "NEGATIVE" ? "Negativo" : sentiment === "POSITIVE" ? "Positivo" : sentiment === "MIXED" ? "Misto" : "Neutro";
                        entry.scores = `Sentimento: ${sentLabel}`;
                      }
                    }
                    // Video/Image: detection_findings com confidence
                    const detFindings = o.details?.detection_findings as Array<{ confidence: number }> | undefined;
                    if (detFindings && detFindings.length > 0 && byMod.has(o.modality_type)) {
                      const entry = byMod.get(o.modality_type)!;
                      const avgConf = detFindings.reduce((sum, d) => sum + d.confidence, 0) / detFindings.length;
                      if (entry.scores === "-") {
                        entry.scores = `Confiança média: ${Math.round(avgConf * 100)}% (${detFindings.length} detecções)`;
                      }
                    }
                  }
                  return Array.from(byMod.entries()).map(([mod, data]) => (
                    <tr key={mod} style={{ borderBottom: "1px solid #eee" }}>
                      <td style={{ padding: "4px 6px" }}>{modalityLabel(mod)}</td>
                      <td style={{ padding: "4px 6px" }}>{qualityLabels[data.quality] || data.quality}</td>
                      <td style={{ padding: "4px 6px" }}>{data.scores}</td>
                    </tr>
                  ));
                })()}
              </tbody>
            </table>
          </InfoButton>
        </span>
        <span className={styles.cardNumber}>{qualityLabels[worstQuality]}</span>
        <span className={styles.cardHint}>{worstQuality === "ADEQUATE" ? "Todos os dados com boa qualidade" : "Ao menos um dado com qualidade reduzida"}</span>
      </div>
    </div>
  );
}
