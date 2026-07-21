import { useEffect, useState, type CSSProperties } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, Pencil, RotateCcw, Upload } from "lucide-react";
import { ApproverSearchField } from "./ApproverSearchField";
import { DataTable, type DataTableColumn } from "@/components/data-display/DataTable";
import { Pagination } from "@/components/data-display/Pagination";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { Skeleton } from "@/components/feedback/Skeleton";
import { useToast } from "@/components/feedback/ToastProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Modal } from "@/components/ui/Modal";
import { RiskBadge } from "@/components/ui/RiskBadge";
import { Section } from "@/components/ui/Section";
import { SelectField } from "@/components/ui/SelectField";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { TextField } from "@/components/ui/TextField";
import { useDevSession } from "@/hooks/useDevSession";
import { extractErrorMessage } from "@/lib/errorMessage";
import {
  getClinicalRuleSet,
  listClinicalRuleSets,
  listEmployees,
  publishClinicalRuleSet,
  rollbackClinicalRuleSet,
  updateClinicalRule,
  updateClinicalRuleAction,
} from "@/services/api/administration";
import type {
  ClinicalRule,
  ClinicalRuleAction,
  ClinicalRuleApproval,
  ClinicalRuleSetSummary,
  Employee,
} from "@/types/administration";
import {
  exclusionLabel,
  populationLabel,
  requiredInputLabel,
  ruleSetCodeLabel,
} from "./clinicalDataLabels";

const RISK_LEVEL_OPTIONS = [
  { value: "1", label: "1 - Baixo" },
  { value: "2", label: "2 - Leve" },
  { value: "3", label: "3 - Moderado" },
  { value: "4", label: "4 - Alto" },
  { value: "5", label: "5 - Muito alto" },
  { value: "6", label: "6 - Critico" },
];

const PAGE_SIZE = 5;

/**
 * Tela de dados clinicos / regras (rota `/admin/clinical-rules`). Nao e
 * um formulario de conteudo clinico (o conjunto de regras vem do fluxo
 * YAML -> seed, ADR 0011) - aqui o administrador clinico publica um
 * conjunto em "draft" ou reverte (rollback) uma versao hoje publicada
 * para uma versao anteriormente publicada, sempre com justificativa
 * obrigatoria, confirmada em `ConfirmDialog`.
 *
 * O botao "Reverter (rollback)" aparece na linha PUBLISHED (nao mais nas
 * linhas RETIRED isoladas) - clicar abre um seletor com as versoes
 * anteriormente publicadas do mesmo `code`/`population` (`retired`), e
 * escolher uma delas abre a mesma confirmacao de aprovador+justificativa
 * usada pela publicacao. O backend continua exigindo que o alvo do
 * rollback esteja em `retired` (`app.administration.service.
 * rollback_rule_set`) - este seletor so torna essa pre-condicao visivel
 * e navegavel a partir do ponto de entrada natural (a versao vigente).
 */
export function ClinicalRuleSetsPage() {
  const { subject } = useDevSession();
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [page, setPage] = useState(1);

  const [actionTarget, setActionTarget] = useState<{
    kind: "publish" | "rollback";
    ruleSet: ClinicalRuleSetSummary;
  } | null>(null);
  const [approverEmployee, setApproverEmployee] = useState<Employee | null>(null);
  const [justification, setJustification] = useState("");

  const [detailTargetId, setDetailTargetId] = useState<string | null>(null);

  // Seletor de rollback (Opcao A: acionado a partir da linha PUBLISHED,
  // nao mais so a partir de cada versao RETIRED isolada) - guarda o
  // conjunto atualmente publicado para saber code/population e buscar as
  // versoes RETIRED candidatas a restauracao.
  const [rollbackSourceRuleSet, setRollbackSourceRuleSet] = useState<ClinicalRuleSetSummary | null>(
    null,
  );

  const [editRuleTarget, setEditRuleTarget] = useState<ClinicalRule | null>(null);
  const [ruleWhen, setRuleWhen] = useState("");
  const [ruleRiskLevel, setRuleRiskLevel] = useState("1");
  const [ruleLabel, setRuleLabel] = useState("");
  const [ruleNotes, setRuleNotes] = useState("");

  const [editActionTarget, setEditActionTarget] = useState<ClinicalRuleAction | null>(null);
  const [actionDescription, setActionDescription] = useState("");

  const query = useQuery({
    queryKey: ["admin", "clinical-rule-sets", subject, page],
    queryFn: () => listClinicalRuleSets(subject as string, { page, pageSize: PAGE_SIZE }),
    enabled: Boolean(subject),
  });

  const detailQuery = useQuery({
    queryKey: ["admin", "clinical-rule-sets", "detail", subject, detailTargetId],
    queryFn: () => getClinicalRuleSet(subject as string, detailTargetId as string),
    enabled: Boolean(subject) && Boolean(detailTargetId),
  });

  // Versoes RETIRED do mesmo code (o backend nao filtra por `population`
  // na listagem - refinado no cliente abaixo) - candidatas a restauracao
  // por rollback a partir da versao hoje PUBLISHED. Carregada sob demanda,
  // apenas quando o seletor esta aberto.
  const retiredVersionsQuery = useQuery({
    queryKey: ["admin", "clinical-rule-sets", "retired", subject, rollbackSourceRuleSet?.code],
    queryFn: () =>
      listClinicalRuleSets(subject as string, {
        code: rollbackSourceRuleSet!.code,
        status: "retired",
        pageSize: 100,
      }),
    enabled: Boolean(subject) && Boolean(rollbackSourceRuleSet),
  });
  const retiredVersions = (retiredVersionsQuery.data?.items ?? []).filter(
    (rs) => rs.population === rollbackSourceRuleSet?.population,
  );

  // Aprovador de publicacao/rollback so pode ser um medico ativo
  // cadastrado (nunca texto livre) - ver app.administration.service.
  // get_active_doctor_for_approval. Carregada sob demanda, apenas quando
  // o dialogo de confirmacao esta aberto.
  const approverOptionsQuery = useQuery({
    queryKey: ["admin", "employees", "approver-options", subject],
    queryFn: () =>
      listEmployees(subject as string, {
        pageSize: 100,
        professionalType: "MEDICO",
        active: true,
      }),
    enabled: Boolean(subject) && Boolean(actionTarget),
  });

  useEffect(() => {
    if (!editRuleTarget) return;
    setRuleWhen(editRuleTarget.when);
    setRuleRiskLevel(String(editRuleTarget.risk_level));
    setRuleLabel(editRuleTarget.classification_label);
    setRuleNotes(editRuleTarget.notes ?? "");
  }, [editRuleTarget]);

  useEffect(() => {
    if (!editActionTarget) return;
    setActionDescription(editActionTarget.description);
  }, [editActionTarget]);

  const updateRuleMutation = useMutation({
    mutationFn: () =>
      updateClinicalRule(subject as string, detailTargetId as string, editRuleTarget!.id, {
        when: ruleWhen,
        risk_level: Number(ruleRiskLevel),
        classification_label: ruleLabel,
        notes: ruleNotes.trim() ? ruleNotes : null,
      }),
    onSuccess: (updatedDetail) => {
      setEditRuleTarget(null);
      // Escreve a resposta ja atualizada direto no cache da query de
      // detalhe (em vez de so invalidar) para o modal refletir a edicao
      // imediatamente, sem depender de um refetch de rede.
      queryClient.setQueryData(
        ["admin", "clinical-rule-sets", "detail", subject, detailTargetId],
        updatedDetail,
      );
      queryClient.invalidateQueries({ queryKey: ["admin", "clinical-rule-sets"] });
      showSuccess("Regra atualizada com sucesso.");
    },
    onError: (error: unknown) => {
      showError(extractErrorMessage(error, "Não foi possível salvar a regra."));
    },
  });

  const updateActionMutation = useMutation({
    mutationFn: () =>
      updateClinicalRuleAction(
        subject as string,
        detailTargetId as string,
        editActionTarget!.id,
        { description: actionDescription },
      ),
    onSuccess: (updatedDetail) => {
      setEditActionTarget(null);
      queryClient.setQueryData(
        ["admin", "clinical-rule-sets", "detail", subject, detailTargetId],
        updatedDetail,
      );
      queryClient.invalidateQueries({ queryKey: ["admin", "clinical-rule-sets"] });
      showSuccess("Conduta atualizada com sucesso.");
    },
    onError: (error: unknown) => {
      showError(extractErrorMessage(error, "Não foi possível salvar a conduta."));
    },
  });

  const publishMutation = useMutation({
    mutationFn: (ruleSetId: string) =>
      publishClinicalRuleSet(subject as string, ruleSetId, {
        approver_employee_id: approverEmployee!.id,
        justification,
      }),
    onSuccess: () => {
      closeAction();
      showSuccess("Conjunto de regras publicado com sucesso.");
    },
    onError: (error: unknown) => {
      showError(extractErrorMessage(error, "Não foi possível publicar o conjunto de regras."));
    },
  });

  const rollbackMutation = useMutation({
    mutationFn: (ruleSetId: string) =>
      rollbackClinicalRuleSet(subject as string, ruleSetId, {
        approver_employee_id: approverEmployee!.id,
        justification,
      }),
    onSuccess: () => {
      closeAction();
      showSuccess("Reversão (rollback) concluída com sucesso.");
    },
    onError: (error: unknown) => {
      showError(extractErrorMessage(error, "Não foi possível reverter o conjunto de regras."));
    },
  });

  function closeAction() {
    setActionTarget(null);
    setApproverEmployee(null);
    setJustification("");
    queryClient.invalidateQueries({ queryKey: ["admin", "clinical-rule-sets"] });
  }

  function closeRollbackSelector() {
    setRollbackSourceRuleSet(null);
  }

  const pendingAction = publishMutation.isPending || rollbackMutation.isPending;
  const confirmDisabled = approverEmployee === null || justification.trim().length === 0;

  function handleConfirmAction() {
    if (!actionTarget) return;
    if (actionTarget.kind === "publish") publishMutation.mutate(actionTarget.ruleSet.id);
    else rollbackMutation.mutate(actionTarget.ruleSet.id);
  }

  const columns: DataTableColumn<ClinicalRuleSetSummary>[] = [
    { key: "code", header: "Dado clínico", render: (rs) => ruleSetCodeLabel(rs.code) },
    { key: "version", header: "Versao", render: (rs) => rs.version },
    { key: "population", header: "Populacao", render: (rs) => populationLabel(rs.population) },
    {
      key: "effective_from",
      header: "Vigencia desde",
      render: (rs) => rs.effective_from,
    },
    { key: "status", header: "Status", render: (rs) => <StatusBadge status={rs.status} /> },
    {
      key: "actions",
      header: "Acoes",
      render: (rs) => (
        <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
          <Button type="button" variant="secondary" onClick={() => setDetailTargetId(rs.id)}>
            <Eye size={14} strokeWidth={2} aria-hidden="true" />
            Ver detalhes
          </Button>
          {rs.status === "draft" && (
            <Button
              type="button"
              variant="secondary"
              onClick={() => setActionTarget({ kind: "publish", ruleSet: rs })}
            >
              <Upload size={14} strokeWidth={2} aria-hidden="true" />
              Publicar
            </Button>
          )}
          {rs.status === "published" && (
            <Button type="button" variant="secondary" onClick={() => setRollbackSourceRuleSet(rs)}>
              <RotateCcw size={14} strokeWidth={2} aria-hidden="true" />
              Reverter (rollback)
            </Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <section>
      <PageHeader
        title="Dados clinicos (regras)"
        description="Conjuntos de regras sao carregados por seed/YAML em estado draft e so contam para a classificacao de risco depois de publicados por um administrador clinico. Na versao publicada, 'Reverter (rollback)' permite escolher uma versao anterior para restaurar."
      />

      {query.isLoading && <Skeleton rows={4} />}
      {query.isError && (
        <ErrorState description={(query.error as Error).message} onRetry={() => query.refetch()} />
      )}
      {query.isSuccess && query.data.items.length === 0 && (
        <EmptyState title="Nenhum conjunto de regras carregado ainda" />
      )}
      {query.isSuccess && query.data.items.length > 0 && (
        <Section title="Conjuntos de regras">
          <DataTable columns={columns} rows={query.data.items} getRowKey={(rs) => rs.id} />
          <Pagination
            page={query.data.page}
            totalPages={query.data.total_pages}
            totalItems={query.data.total_items}
            onPageChange={setPage}
          />
        </Section>
      )}

      <Modal
        open={Boolean(rollbackSourceRuleSet)}
        title={
          rollbackSourceRuleSet
            ? `Reverter (rollback) ${ruleSetCodeLabel(rollbackSourceRuleSet.code)}`
            : "Reverter (rollback)"
        }
        onClose={closeRollbackSelector}
      >
        <p style={detailMutedStyle}>
          Selecione a versão anteriormente publicada para a qual restaurar. A versão atualmente
          publicada ({rollbackSourceRuleSet?.version}) será aposentada automaticamente.
        </p>
        {retiredVersionsQuery.isLoading && <Skeleton rows={2} />}
        {retiredVersionsQuery.isError && (
          <ErrorState
            description={(retiredVersionsQuery.error as Error).message}
            onRetry={() => retiredVersionsQuery.refetch()}
          />
        )}
        {retiredVersionsQuery.isSuccess && retiredVersions.length === 0 && (
          <EmptyState title="Nenhuma versão anterior disponível para restaurar." />
        )}
        {retiredVersionsQuery.isSuccess && retiredVersions.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            {retiredVersions.map((rs) => (
              <div
                key={rs.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "var(--space-3)",
                  padding: "var(--space-3)",
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-field)",
                }}
              >
                <div>
                  <p style={{ margin: 0, fontWeight: 600 }}>Versão {rs.version}</p>
                  <p style={{ ...detailMutedStyle, margin: 0 }}>Vigente desde {rs.effective_from}</p>
                </div>
                <Button
                  type="button"
                  onClick={() => {
                    setActionTarget({ kind: "rollback", ruleSet: rs });
                    setRollbackSourceRuleSet(null);
                  }}
                >
                  Restaurar esta versão
                </Button>
              </div>
            ))}
          </div>
        )}
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "var(--space-4)" }}>
          <Button type="button" variant="secondary" onClick={closeRollbackSelector}>
            Fechar
          </Button>
        </div>
      </Modal>

      <ConfirmDialog
        open={Boolean(actionTarget)}
        title={
          actionTarget?.kind === "publish"
            ? `Publicar ${ruleSetCodeLabel(actionTarget.ruleSet.code)} (${actionTarget.ruleSet.version})`
            : `Reverter (rollback) ${actionTarget ? ruleSetCodeLabel(actionTarget.ruleSet.code) : ""} (${actionTarget?.ruleSet.version})`
        }
        description={
          actionTarget?.kind === "publish"
            ? "Confirmar publicacao deste conjunto de regras (passa a valer para novas analises)."
            : "Confirmar reversao (rollback): esta versao volta a ficar publicada e a versao atualmente vigente sera aposentada."
        }
        confirmLabel="Confirmar"
        pending={pendingAction}
        confirmDisabled={confirmDisabled}
        onConfirm={handleConfirmAction}
        onCancel={closeAction}
        size="md"
      >
        <ApproverSearchField
          id="action-approver"
          label="Aprovador"
          required
          employees={approverOptionsQuery.data?.items ?? []}
          isLoading={approverOptionsQuery.isLoading}
          isError={approverOptionsQuery.isError}
          value={approverEmployee}
          onSelect={setApproverEmployee}
          onClear={() => setApproverEmployee(null)}
          hint="Busque por nome ou matrícula - apenas médicos ativos cadastrados em Funcionários podem ser selecionados."
        />
        <TextField
          id="action-justification"
          label="Justificativa"
          required
          value={justification}
          onChange={(event) => setJustification(event.target.value)}
        />
      </ConfirmDialog>

      <Modal
        open={Boolean(detailTargetId)}
        title={
          detailQuery.data
            ? `${ruleSetCodeLabel(detailQuery.data.code)} (${detailQuery.data.version})`
            : "Detalhes do conjunto de regras"
        }
        onClose={() => setDetailTargetId(null)}
        size="lg"
      >
        {detailQuery.isLoading && <Skeleton rows={4} />}
        {detailQuery.isError && (
          <ErrorState
            description={(detailQuery.error as Error).message}
            onRetry={() => detailQuery.refetch()}
          />
        )}
        {detailQuery.isSuccess && (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            <Section title="Resumo" variant="plain" action={<StatusBadge status={detailQuery.data.status} />}>
              <dl style={detailListStyle}>
                <dt style={detailTermStyle}>Populacao</dt>
                <dd style={detailDescriptionStyle}>{populationLabel(detailQuery.data.population)}</dd>

                <dt style={detailTermStyle}>Vigente desde</dt>
                <dd style={detailDescriptionStyle}>{detailQuery.data.effective_from}</dd>

                <dt style={detailTermStyle}>Vigente até</dt>
                <dd style={detailDescriptionStyle}>{detailQuery.data.effective_to ?? "-"}</dd>

                <dt style={detailTermStyle}>Hash do conteúdo</dt>
                <dd
                  style={{ ...detailDescriptionStyle, wordBreak: "break-all", fontFamily: "monospace" }}
                >
                  {detailQuery.data.content_hash}
                </dd>
              </dl>
            </Section>

            <Section title="Regras" variant="plain">
              {detailQuery.data.rules.length === 0 ? (
                <p style={detailMutedStyle}>Nenhuma regra cadastrada neste conjunto.</p>
              ) : (
                <RulesTable
                  rules={detailQuery.data.rules}
                  editable={detailQuery.data.status === "draft"}
                  onEdit={setEditRuleTarget}
                />
              )}
            </Section>

            <Section title="Conduta por nível de risco" variant="plain">
              {detailQuery.data.actions.length === 0 ? (
                <p style={detailMutedStyle}>Nenhuma conduta cadastrada neste conjunto.</p>
              ) : (
                <RuleActionsTable
                  actions={detailQuery.data.actions}
                  editable={detailQuery.data.status === "draft"}
                  onEdit={setEditActionTarget}
                />
              )}
            </Section>

            <Section title="Entradas obrigatórias" variant="plain">
              {detailQuery.data.required_inputs.length === 0 ? (
                <p style={detailMutedStyle}>Nenhuma entrada obrigatória declarada.</p>
              ) : (
                <ul style={detailListStyleType}>
                  {detailQuery.data.required_inputs.map((input) => (
                    <li key={input}>{requiredInputLabel(input)}</li>
                  ))}
                </ul>
              )}
            </Section>

            <Section title="Exclusões" variant="plain">
              {detailQuery.data.exclusions.length === 0 ? (
                <p style={detailMutedStyle}>Nenhuma exclusão declarada.</p>
              ) : (
                <ul style={detailListStyleType}>
                  {detailQuery.data.exclusions.map((exclusion) => (
                    <li key={exclusion}>{exclusionLabel(exclusion)}</li>
                  ))}
                </ul>
              )}
            </Section>

            <Section title="Histórico de aprovações" variant="plain">
              {detailQuery.data.approvals.length === 0 ? (
                <p style={detailMutedStyle}>Nenhuma publicação ou rollback registrado ainda.</p>
              ) : (
                <ApprovalsHistoryTable approvals={detailQuery.data.approvals} />
              )}
            </Section>

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <Button type="button" variant="secondary" onClick={() => setDetailTargetId(null)}>
                Fechar
              </Button>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        open={Boolean(editRuleTarget)}
        title={editRuleTarget ? `Editar regra: ${editRuleTarget.rule_key}` : "Editar regra"}
        onClose={() => setEditRuleTarget(null)}
      >
        {editRuleTarget && (
          <form
            style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}
            onSubmit={(event) => {
              event.preventDefault();
              updateRuleMutation.mutate();
            }}
          >
            <p style={detailMutedStyle}>
              A condição (when) usa uma sintaxe restrita e segura: comparações, and/or/not,
              nomes de variável e constantes numéricas, de texto ou booleanas. Ex.:{" "}
              <code>94 &lt;= spo2_percent &lt;= 95</code>.
            </p>
            <TextField
              id="rule-when"
              label="Condição (when)"
              required
              value={ruleWhen}
              onChange={(event) => setRuleWhen(event.target.value)}
            />
            <SelectField
              id="rule-risk-level"
              label="Nível de risco"
              required
              options={RISK_LEVEL_OPTIONS}
              value={ruleRiskLevel}
              onChange={(event) => setRuleRiskLevel(event.target.value)}
            />
            <TextField
              id="rule-label"
              label="Rótulo de classificação"
              required
              value={ruleLabel}
              onChange={(event) => setRuleLabel(event.target.value)}
            />
            <TextField
              id="rule-notes"
              label="Notas"
              value={ruleNotes}
              onChange={(event) => setRuleNotes(event.target.value)}
            />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setEditRuleTarget(null)}
                disabled={updateRuleMutation.isPending}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={updateRuleMutation.isPending}>
                {updateRuleMutation.isPending ? "Salvando..." : "Salvar"}
              </Button>
            </div>
          </form>
        )}
      </Modal>

      <Modal
        open={Boolean(editActionTarget)}
        title={
          editActionTarget
            ? `Editar conduta - nível ${editActionTarget.risk_level}`
            : "Editar conduta"
        }
        onClose={() => setEditActionTarget(null)}
      >
        {editActionTarget && (
          <form
            style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}
            onSubmit={(event) => {
              event.preventDefault();
              updateActionMutation.mutate();
            }}
          >
            <TextField
              id="action-description"
              label="Descrição da conduta"
              required
              value={actionDescription}
              onChange={(event) => setActionDescription(event.target.value)}
            />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setEditActionTarget(null)}
                disabled={updateActionMutation.isPending}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={updateActionMutation.isPending}>
                {updateActionMutation.isPending ? "Salvando..." : "Salvar"}
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </section>
  );
}

const detailListStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "160px 1fr",
  gap: "var(--space-2) var(--space-3)",
  margin: 0,
};

const detailTermStyle: CSSProperties = {
  color: "var(--color-text-muted)",
  fontSize: 13,
  fontWeight: 600,
};

const detailDescriptionStyle: CSSProperties = {
  margin: 0,
  fontSize: 14,
};

const detailMutedStyle: CSSProperties = {
  color: "var(--color-text-muted)",
  fontSize: 14,
  margin: 0,
};

const detailListStyleType: CSSProperties = {
  margin: 0,
  paddingLeft: "var(--space-5)",
  fontSize: 14,
};

const RULES_PAGE_SIZE = 5;

/** Lista de regras do conjunto, paginada no cliente (mesmo padrao de
 * `ApprovalsHistoryTable`) - `editable` so e true quando o conjunto esta
 * em `draft` (conjuntos publicados/retirados sao imutaveis). */
function RulesTable({
  rules,
  editable,
  onEdit,
}: {
  rules: ClinicalRule[];
  editable: boolean;
  onEdit: (rule: ClinicalRule) => void;
}) {
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(rules.length / RULES_PAGE_SIZE));
  const pageItems = rules.slice((page - 1) * RULES_PAGE_SIZE, page * RULES_PAGE_SIZE);

  const columns: DataTableColumn<ClinicalRule>[] = [
    { key: "rule_key", header: "Regra", render: (r) => r.rule_key },
    {
      key: "when",
      header: "Condição (when)",
      render: (r) => <code style={{ fontSize: 13 }}>{r.when}</code>,
    },
    {
      key: "risk_level",
      header: "Nível de risco",
      render: (r) => (
        <RiskBadge outcome="MATCHED" riskLevel={r.risk_level} classificationLabel={r.classification_label} />
      ),
    },
    { key: "notes", header: "Notas", render: (r) => r.notes ?? "-" },
    ...(editable
      ? ([
          {
            key: "actions",
            header: "Ações",
            render: (r: ClinicalRule) => (
              <Button type="button" variant="secondary" onClick={() => onEdit(r)}>
                <Pencil size={14} strokeWidth={2} aria-hidden="true" />
                Editar
              </Button>
            ),
          },
        ] satisfies DataTableColumn<ClinicalRule>[])
      : []),
  ];

  return (
    <>
      <DataTable columns={columns} rows={pageItems} getRowKey={(r) => r.id} />
      <Pagination page={page} totalPages={totalPages} totalItems={rules.length} onPageChange={setPage} />
    </>
  );
}

const ACTIONS_PAGE_SIZE = 5;

function RuleActionsTable({
  actions,
  editable,
  onEdit,
}: {
  actions: ClinicalRuleAction[];
  editable: boolean;
  onEdit: (action: ClinicalRuleAction) => void;
}) {
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(actions.length / ACTIONS_PAGE_SIZE));
  const pageItems = actions.slice((page - 1) * ACTIONS_PAGE_SIZE, page * ACTIONS_PAGE_SIZE);

  const columns: DataTableColumn<ClinicalRuleAction>[] = [
    {
      key: "risk_level",
      header: "Nível de risco",
      render: (a) => (
        <RiskBadge outcome="MATCHED" riskLevel={a.risk_level} classificationLabel={null} />
      ),
    },
    { key: "description", header: "Conduta", render: (a) => a.description },
    ...(editable
      ? ([
          {
            key: "actions",
            header: "Ações",
            render: (a: ClinicalRuleAction) => (
              <Button type="button" variant="secondary" onClick={() => onEdit(a)}>
                <Pencil size={14} strokeWidth={2} aria-hidden="true" />
                Editar
              </Button>
            ),
          },
        ] satisfies DataTableColumn<ClinicalRuleAction>[])
      : []),
  ];

  return (
    <>
      <DataTable columns={columns} rows={pageItems} getRowKey={(a) => a.id} />
      <Pagination
        page={page}
        totalPages={totalPages}
        totalItems={actions.length}
        onPageChange={setPage}
      />
    </>
  );
}

const approvalColumns: DataTableColumn<ClinicalRuleApproval>[] = [
  { key: "decision", header: "Decisão", render: (a) => <StatusBadge status={a.decision} /> },
  { key: "approver", header: "Aprovador", render: (a) => a.approver },
  { key: "justification", header: "Justificativa", render: (a) => a.justification },
  { key: "decided_at", header: "Data", render: (a) => a.decided_at },
];

const APPROVALS_PAGE_SIZE = 5;

/** `ClinicalRuleSetDetail.approvals` chega completo do backend (sem
 * paginacao de servidor - e uma lista de auditoria por conjunto de
 * regras, tipicamente pequena); pagina no cliente para manter o mesmo
 * padrao de 5 por pagina das demais tabelas do sistema. */
function ApprovalsHistoryTable({ approvals }: { approvals: ClinicalRuleApproval[] }) {
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(approvals.length / APPROVALS_PAGE_SIZE));
  const pageItems = approvals.slice((page - 1) * APPROVALS_PAGE_SIZE, page * APPROVALS_PAGE_SIZE);

  return (
    <>
      <DataTable columns={approvalColumns} rows={pageItems} getRowKey={(approval) => approval.id} />
      <Pagination
        page={page}
        totalPages={totalPages}
        totalItems={approvals.length}
        onPageChange={setPage}
      />
    </>
  );
}
