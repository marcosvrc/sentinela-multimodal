import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { X } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { FormField } from "@/components/ui/FormField";
import { Button } from "@/components/ui/Button";
import { Section } from "@/components/ui/Section";
import { EmptyState } from "@/components/feedback/EmptyState";
import { Skeleton } from "@/components/feedback/Skeleton";
import { useToast } from "@/components/feedback/ToastProvider";
import { useDevSession } from "@/hooks/useDevSession";
import { getPatient, listObservations } from "@/services/api/patients";
import {
  computeSha256,
  confirmMediaUpload,
  createAnalysis,
  requestMediaUpload,
  submitAnalysis,
  uploadFileToPresignedUrl,
} from "@/services/api/analyses";
import { ApiRequestError } from "@/types/api";
import { ModalityType, ObservationType } from "@/types/enums.generated";
import type { Patient } from "@/types/patient";
import formStyles from "@/components/ui/FormField.module.css";
import { MODALITY_LABELS } from "@/app/enumLabels";
import { PatientSearchField } from "./PatientSearchField";
import { PatientPersonalDataCard } from "./PatientPersonalDataCard";
import { PatientClinicalDataSelector } from "./PatientClinicalDataSelector";
import {
  BMI_CODE,
  CLINICAL_DATA_OPTIONS,
  buildStructuredClinicalInputs,
  formatBmiValue,
  latestObservationByType,
} from "./clinicalDataSelection";
import { AnalysisStepper, type AnalysisStep } from "./AnalysisStepper";
import { OBSERVATION_TYPE_CONFIG, formatObservationValue } from "@/features/patients/observationConfig";
import styles from "./AnalysisNewPage.module.css";

const UPLOADABLE_MODALITIES = [ModalityType.IMAGE, ModalityType.AUDIO, ModalityType.VIDEO];
const SELECTABLE_MODALITIES = [
  ModalityType.TEXT,
  ModalityType.IMAGE,
  ModalityType.VIDEO,
  ModalityType.AUDIO,
];

const STEPS: AnalysisStep[] = [
  { key: "patient", label: "Paciente" },
  { key: "clinical-data", label: "Dados clínicos" },
  { key: "modalities", label: "Modalidades" },
  { key: "review", label: "Consolidado" },
];

type StepStatus = "idle" | "running" | "done" | "error";

/** Uma analise aceita mais de um arquivo por modalidade (ex.: duas fotos
 * ou dois videos) - cada midia aprovada gera seu proprio processamento
 * independente (ver `app.orchestrator.service.submit_analysis`), entao o
 * formulario acumula uma LISTA de arquivos por modalidade, nao um unico
 * arquivo. Selecionar mais arquivos no mesmo campo ACUMULA (nao
 * substitui) a lista anterior; cada arquivo pode ser removido
 * individualmente antes do envio. */
type FilesByModality = Partial<Record<ModalityType, File[]>>;

export function AnalysisNewPage() {
  const { patientId: patientIdFromRoute } = useParams<{ patientId?: string }>();
  const { subject } = useDevSession();
  const navigate = useNavigate();
  const { showSuccess, showError } = useToast();

  const [stepIndex, setStepIndex] = useState(0);

  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [selectedClinicalCodes, setSelectedClinicalCodes] = useState<Set<string>>(new Set());
  const [selectedModalities, setSelectedModalities] = useState<Set<ModalityType>>(new Set());
  const [additionalText, setAdditionalText] = useState("");
  const [files, setFiles] = useState<FilesByModality>({});

  const [status, setStatus] = useState<StepStatus>("idle");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  function toggleClinicalCode(code: string, checked: boolean) {
    setSelectedClinicalCodes((current) => {
      const next = new Set(current);
      if (checked) next.add(code);
      else next.delete(code);
      return next;
    });
  }

  function toggleModality(modality: ModalityType, checked: boolean) {
    setSelectedModalities((current) => {
      const next = new Set(current);
      if (checked) next.add(modality);
      else next.delete(modality);
      return next;
    });
  }

  function addFiles(modality: ModalityType, newFiles: File[]) {
    if (newFiles.length === 0) return;
    setFiles((current) => ({
      ...current,
      [modality]: [...(current[modality] ?? []), ...newFiles],
    }));
  }

  function removeFile(modality: ModalityType, index: number) {
    setFiles((current) => {
      const remaining = (current[modality] ?? []).filter((_, i) => i !== index);
      return { ...current, [modality]: remaining };
    });
  }

  // Quando a rota ja traz o paciente (aberto a partir do detalhe do
  // paciente), carrega o registro completo para alimentar o painel de
  // dados pessoais sem exigir busca manual.
  const routePatientQuery = useQuery({
    queryKey: ["patient", subject, patientIdFromRoute],
    queryFn: () => getPatient(subject as string, patientIdFromRoute as string),
    enabled: Boolean(subject && patientIdFromRoute),
  });

  const selectedPatientId = patientIdFromRoute ?? selectedPatient?.id ?? "";
  const displayedPatient = patientIdFromRoute ? (routePatientQuery.data ?? null) : selectedPatient;

  // Carregada aqui (nao so dentro de `PatientClinicalDataSelector`)
  // porque o resumo da etapa de consolidado tambem precisa listar os
  // valores clinicos escolhidos - evita duas chamadas concorrentes ao
  // mesmo endpoint.
  const observationsQuery = useQuery({
    queryKey: ["observations", selectedPatientId],
    queryFn: () => listObservations(subject as string, selectedPatientId),
    enabled: Boolean(subject && selectedPatientId),
  });

  const latestObservationsByType = useMemo(
    () => latestObservationByType(observationsQuery.data ?? []),
    [observationsQuery.data],
  );

  const hasTextModality = selectedModalities.has(ModalityType.TEXT);

  const canAdvanceFromPatientStep = Boolean(selectedPatientId);
  // A analise precisa de ao menos UM conteudo entre: dado clinico
  // selecionado, texto/imagem/video/audio (`app.orchestrator.service.
  // submit_analysis` aceita midia aprovada, texto adicional OU dados
  // clinicos estruturados). Dados clinicos sao escolhidos na etapa
  // anterior - por isso ja contam aqui, mesmo que nenhuma modalidade
  // desta etapa seja marcada.
  const canAdvanceFromModalitiesStep =
    selectedModalities.size > 0 || selectedClinicalCodes.size > 0;

  const mutation = useMutation({
    mutationFn: async () => {
      if (!subject) throw new Error("Sessao de desenvolvimento nao configurada.");
      if (!selectedPatientId) throw new Error("Selecione um paciente.");

      setStatus("running");
      setErrorMessage(null);

      const structuredClinicalInputs = buildStructuredClinicalInputs(
        selectedClinicalCodes,
        latestObservationsByType,
        displayedPatient?.height_cm ?? null,
      );

      setStatusMessage("Criando analise...");
      const analysis = await createAnalysis(subject, {
        patient_id: selectedPatientId,
        additional_text: hasTextModality && additionalText ? additionalText : undefined,
        structured_clinical_inputs: structuredClinicalInputs,
      });

      for (const modality of UPLOADABLE_MODALITIES) {
        if (!selectedModalities.has(modality)) continue;
        const modalityFiles = files[modality] ?? [];
        for (const [index, file] of modalityFiles.entries()) {
          const label = MODALITY_LABELS[modality].toLowerCase();
          const countSuffix = modalityFiles.length > 1 ? ` (${index + 1}/${modalityFiles.length})` : "";

          setStatusMessage(`Enviando ${label}${countSuffix}...`);
          const upload = await requestMediaUpload(subject, analysis.id, {
            modality_type: modality,
            filename: file.name,
            mime_type: file.type || "application/octet-stream",
            size_bytes: file.size,
          });
          await uploadFileToPresignedUrl(
            upload.upload_url,
            upload.upload_method,
            upload.upload_headers,
            file,
          );
          const checksum = await computeSha256(file);
          setStatusMessage(`Confirmando ${label}${countSuffix}...`);
          await confirmMediaUpload(subject, analysis.id, upload.media_id, checksum);
        }
      }

      setStatusMessage("Submetendo analise para processamento...");
      await submitAnalysis(subject, analysis.id);

      setStatus("done");
      return analysis;
    },
    onSuccess: (analysis) => {
      showSuccess("Análise criada e enviada para processamento com sucesso.");
      navigate(`/analyses/${analysis.id}`);
    },
    onError: (error: unknown) => {
      setStatus("error");
      let message: string;
      if (error instanceof ApiRequestError) {
        message = error.message;
      } else if (error instanceof Error) {
        message = error.message;
      } else {
        message = "Nao foi possivel iniciar a analise.";
      }
      setErrorMessage(message);
      showError(message);
    },
  });

  if (!subject) {
    return <EmptyState title="Configure o usuario de desenvolvimento primeiro." />;
  }

  return (
    <>
      <PageHeader
        title="Nova analise"
        description="Selecione o paciente, os dados clínicos e as modalidades, e revise antes de enviar para processamento."
      />

      <AnalysisStepper steps={STEPS} currentIndex={stepIndex} />

      {/* Etapa 1: paciente ------------------------------------------------ */}
      {stepIndex === 0 && (
        <>
          {!patientIdFromRoute && (
            <Section title="Paciente">
              <PatientSearchField
                devSubject={subject}
                selectedPatient={selectedPatient}
                onSelect={setSelectedPatient}
                onClear={() => setSelectedPatient(null)}
              />
            </Section>
          )}

          {patientIdFromRoute && routePatientQuery.isLoading && <Skeleton rows={1} />}

          {displayedPatient && (
            <PatientPersonalDataCard devSubject={subject} patient={displayedPatient} />
          )}

          <div className={styles.stepActions}>
            <Button type="button" onClick={() => setStepIndex(1)} disabled={!canAdvanceFromPatientStep}>
              Avançar
            </Button>
          </div>
        </>
      )}

      {/* Etapa 2: dados clínicos -------------------------------------------- */}
      {stepIndex === 1 && (
        <>
          <Section
            title="Dados clínicos"
            description="Marque quais observações clínicas já registradas do paciente entram nesta análise. É usado o valor mais recente de cada uma; o histórico completo aparece abaixo, ao marcar, para conferência."
          >
            <PatientClinicalDataSelector
              devSubject={subject}
              patientId={selectedPatientId}
              patientHeightCm={displayedPatient?.height_cm ?? null}
              selectedCodes={selectedClinicalCodes}
              onToggle={toggleClinicalCode}
            />
          </Section>

          <div className={styles.stepActions}>
            <Button type="button" variant="secondary" onClick={() => setStepIndex(0)}>
              Voltar
            </Button>
            <Button type="button" onClick={() => setStepIndex(2)}>
              Avançar
            </Button>
          </div>
        </>
      )}

      {/* Etapa 3: modalidades ---------------------------------------------- */}
      {stepIndex === 2 && (
        <>
          <Section
            title="Modalidade"
            description="Selecione ao menos uma modalidade. É possível escolher todas ou apenas algumas."
          >
            <ul className={styles.modalityGrid}>
              {SELECTABLE_MODALITIES.map((modality) => (
                <li key={modality}>
                  <label className={styles.modalityOption}>
                    <input
                      type="checkbox"
                      checked={selectedModalities.has(modality)}
                      onChange={(event) => toggleModality(modality, event.target.checked)}
                    />
                    <span>{MODALITY_LABELS[modality]}</span>
                  </label>
                </li>
              ))}
            </ul>
          </Section>

          {hasTextModality && (
            <Section title="Texto adicional">
              <div style={{ maxWidth: 560 }}>
                <FormField id="additional_text" label="Texto adicional">
                  <textarea
                    id="additional_text"
                    className={formStyles.input}
                    rows={4}
                    value={additionalText}
                    onChange={(event) => setAdditionalText(event.target.value)}
                    placeholder="Relato clinico, contexto ou observacoes complementares."
                  />
                </FormField>
              </div>
            </Section>
          )}

          {UPLOADABLE_MODALITIES.filter((modality) => selectedModalities.has(modality)).map(
            (modality) => {
              const modalityFiles = files[modality] ?? [];
              return (
                <Section key={modality} title={MODALITY_LABELS[modality]}>
                  <div style={{ maxWidth: 560 }}>
                    <FormField
                      id={`file-${modality}`}
                      label={`${MODALITY_LABELS[modality]} (pode selecionar mais de um arquivo)`}
                    >
                      <input
                        id={`file-${modality}`}
                        type="file"
                        multiple
                        onChange={(event) => {
                          // Converte o FileList para array JA AQUI (sincrono,
                          // antes de limpar o input abaixo) - o React 18
                          // enfileira `setFiles`/`addFiles` para rodar depois
                          // deste handler terminar, e limpar `value` invalida
                          // a referencia ao FileList original no navegador
                          // real (diferente do jsdom usado nos testes, onde
                          // isso nao se manifestava). Sem essa copia
                          // sincrona, o arquivo selecionado nunca chegava a
                          // entrar no estado.
                          const selectedFiles = Array.from(event.target.files ?? []);
                          addFiles(modality, selectedFiles);
                          // Limpa o input para permitir selecionar o MESMO
                          // arquivo de novo depois de remove-lo da lista
                          // (sem isso, o navegador nao dispara "change" de
                          // novo para um arquivo com o mesmo caminho).
                          event.target.value = "";
                        }}
                      />
                      {modalityFiles.length > 0 && (
                        <ul className={styles.fileList}>
                          {modalityFiles.map((file, index) => (
                            <li key={`${file.name}-${file.lastModified}-${index}`} className={styles.fileItem}>
                              <span>{file.name}</span>
                              <button
                                type="button"
                                onClick={() => removeFile(modality, index)}
                                aria-label={`Remover ${file.name}`}
                                className={styles.fileRemoveButton}
                              >
                                <X size={14} strokeWidth={2} aria-hidden="true" />
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}
                    </FormField>
                  </div>
                </Section>
              );
            },
          )}

          <div className={styles.stepActions}>
            <Button type="button" variant="secondary" onClick={() => setStepIndex(1)}>
              Voltar
            </Button>
            <Button
              type="button"
              onClick={() => setStepIndex(3)}
              disabled={!canAdvanceFromModalitiesStep}
            >
              Avançar
            </Button>
          </div>
        </>
      )}

      {/* Etapa 4: consolidado ------------------------------------------------ */}
      {stepIndex === 3 && (
        <>
          <Section title="Paciente">
            {displayedPatient && (
              <p className={styles.reviewLine}>
                {displayedPatient.full_name} (prontuário {displayedPatient.medical_record_number})
              </p>
            )}
          </Section>

          <Section title="Dados clínicos selecionados">
            {selectedClinicalCodes.size === 0 ? (
              <p className={styles.reviewMuted}>Nenhum dado clínico selecionado.</p>
            ) : (
              <ul className={styles.reviewList}>
                {CLINICAL_DATA_OPTIONS.filter((option) => selectedClinicalCodes.has(option.code)).map(
                  (option) => {
                    const observation = latestObservationsByType.get(option.observationType);
                    const config = OBSERVATION_TYPE_CONFIG[option.observationType];
                    return (
                      <li key={option.code}>
                        {config.label}
                        {observation && `: ${formatObservationValue(config, observation.value)}`}
                      </li>
                    );
                  },
                )}
                {selectedClinicalCodes.has(BMI_CODE) &&
                  (() => {
                    const weightValue = latestObservationsByType.get(ObservationType.WEIGHT)?.value
                      .value;
                    const latestWeightKg = typeof weightValue === "number" ? weightValue : null;
                    const bmiDisplayValue = formatBmiValue(
                      displayedPatient?.height_cm ?? null,
                      latestWeightKg,
                    );
                    return (
                      <li key={BMI_CODE}>
                        Índice de massa corporal (IMC)
                        {bmiDisplayValue && `: ${bmiDisplayValue}`}
                      </li>
                    );
                  })()}
              </ul>
            )}
          </Section>

          <Section title="Modalidades selecionadas">
            <ul className={styles.reviewList}>
              {SELECTABLE_MODALITIES.filter((modality) => selectedModalities.has(modality)).map(
                (modality) => (
                  <li key={modality}>{MODALITY_LABELS[modality]}</li>
                ),
              )}
            </ul>
          </Section>

          {hasTextModality && (
            <Section title="Texto adicional">
              <p className={styles.reviewLine}>{additionalText || "(nenhum texto informado)"}</p>
            </Section>
          )}

          {UPLOADABLE_MODALITIES.filter((modality) => selectedModalities.has(modality)).map(
            (modality) => (
              <Section key={modality} title={MODALITY_LABELS[modality]}>
                {(files[modality] ?? []).length === 0 ? (
                  <p className={styles.reviewMuted}>Nenhum arquivo selecionado.</p>
                ) : (
                  <ul className={styles.reviewList}>
                    {(files[modality] ?? []).map((file, index) => (
                      <li key={`${file.name}-${index}`}>{file.name}</li>
                    ))}
                  </ul>
                )}
              </Section>
            ),
          )}

          <p className={styles.reviewMuted}>
            É necessário ao menos um dado clínico selecionado, texto adicional ou uma mídia para
            submeter a análise.
          </p>

          {status === "running" && statusMessage && <p role="status">{statusMessage}</p>}
          {status === "error" && errorMessage && <p role="alert">{errorMessage}</p>}

          <div className={styles.stepActions}>
            <Button
              type="button"
              variant="secondary"
              onClick={() => setStepIndex(2)}
              disabled={mutation.isPending}
            >
              Voltar
            </Button>
            <Button type="button" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
              {mutation.isPending ? "Processando..." : "Realizar análise"}
            </Button>
          </div>
        </>
      )}
    </>
  );
}
