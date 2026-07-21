import { useMutation } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import styles from "./ClinicalSupportPanel.module.css";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/feedback/Skeleton";
import { ErrorState } from "@/components/feedback/ErrorState";
import { useToast } from "@/components/feedback/ToastProvider";
import { extractErrorMessage } from "@/lib/errorMessage";
import { generateClinicalSupportSummary } from "@/services/api/patients";

interface ClinicalSupportPanelProps {
  devSubject: string;
  patientId: string;
}

/**
 * Apoio a analise clinica assistido por LLM (abaixo do painel de alertas
 * de anomalia). Ao clicar em "Analisar dados clinicos", consolida as
 * series de observacoes e os alertas de anomalia do paciente em um
 * sumario com visao clinica, causas provaveis e direcionamento sugerido -
 * sempre como apoio, nunca como diagnostico: nao impede nem substitui a
 * propria analise do profissional responsavel, que deve ser sempre
 * realizada (ver `app.clinical_support.service`).
 *
 * Gerado sob demanda (nao persiste, nao usa `useQuery`): cada clique
 * produz um resumo novo a partir do estado atual dos dados do paciente.
 */
export function ClinicalSupportPanel({ devSubject, patientId }: ClinicalSupportPanelProps) {
  const { showError } = useToast();
  const mutation = useMutation({
    mutationFn: () => generateClinicalSupportSummary(devSubject, patientId),
    onError: (error: unknown) => {
      showError(extractErrorMessage(error, "Não foi possível gerar o apoio à análise clínica."));
    },
  });

  return (
    <section style={{ marginBottom: "var(--space-6)" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "var(--space-3)",
        }}
      >
        <div>
          <h2 style={{ fontSize: 20, margin: 0 }}>Apoio a analise clinica (IA)</h2>
          <p
            style={{
              color: "var(--color-text-muted)",
              fontSize: 14,
              marginTop: "var(--space-1)",
              marginBottom: 0,
            }}
          >
            Consolida as observacoes clinicas e os alertas de anomalia do paciente em um sumario
            explicativo, com visao clinica, causas provaveis e direcionamento sugerido - um apoio
            que nao substitui a analise do profissional responsavel.
          </p>
        </div>
        <Button type="button" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
          <Sparkles size={16} strokeWidth={2} aria-hidden="true" />
          {mutation.isPending ? "Analisando..." : "Analisar dados clinicos"}
        </Button>
      </div>

      {mutation.isPending && <Skeleton rows={4} />}

      {mutation.isError && (
        <ErrorState
          description={(mutation.error as Error).message}
          onRetry={() => mutation.mutate()}
        />
      )}

      {mutation.isSuccess && (
        <div className={styles.box} role="region" aria-label="Resultado do apoio a analise clinica">
          <h3 className={styles.sectionTitle}>Visao clinica</h3>
          <p className={styles.sectionText}>{mutation.data.summary_text}</p>

          <h3 className={styles.sectionTitle}>Causas provaveis</h3>
          <p className={styles.sectionText}>{mutation.data.probable_causes}</p>

          <h3 className={styles.sectionTitle}>Direcionamento sugerido</h3>
          <p className={styles.sectionText}>{mutation.data.suggested_next_steps}</p>

          <p className={styles.disclaimer} role="alert">
            {mutation.data.uncertainty_note}
          </p>

          <p className={styles.meta}>
            Gerado em {new Date(mutation.data.generated_at).toLocaleString("pt-BR")} ·{" "}
            {mutation.data.observations_considered} observacao(oes) e{" "}
            {mutation.data.alerts_considered} alerta(s) considerados · modelo{" "}
            {mutation.data.model}
          </p>
        </div>
      )}
    </section>
  );
}
