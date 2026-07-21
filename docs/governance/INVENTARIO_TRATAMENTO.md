# Inventário de Operações de Tratamento (LGPD art. 37)

> Ver `docs/governance/README.md` para o que este documento cobre e o que
> permanece pendente de aprovação. Campos técnicos abaixo refletem o
> código atual; campos de base legal/finalidade aprovada são
> **PENDENTE DE APROVAÇÃO** (jurídico/encarregado).

## 1. Cadastro de paciente

| Campo | Conteúdo |
| --- | --- |
| Operação | Criação e consulta de registro de paciente (`app.patients`) |
| Finalidade | **PENDENTE DE APROVAÇÃO** — presumidamente "prestação de assistência à saúde/apoio à decisão clínica"; requer validação jurídica formal |
| Categorias de dados | Identificação (nome, prontuário), data de nascimento, sexo registrado — dado pessoal de saúde por vinculação |
| Titulares | Pacientes |
| Base legal | **PENDENTE DE APROVAÇÃO** (LGPD art. 11 — dado sensível; consentimento não é a base padrão do sistema, ver seção 8.1 do escopo) |
| Agentes | Controlador: **PENDENTE** (instituição de saúde cliente). Operador: equipe SentinelHealth |
| Fluxo/localização | PostgreSQL (RDS, região definida em `infra/environments/*`), sem transferência a terceiros nesta operação |
| Acesso | Papéis `MEDICO`/`ENFERMEIRO` (escrita), demais conforme RBAC (`app.core.security.require_role`) |
| Retenção | Ver `TABELA_RETENCAO.md` — categoria "Cadastro" |
| Segurança | Isolamento por `institution_id` (multi-tenant, ADR 0012), TLS em trânsito, criptografia em repouso via KMS (RDS) |
| Direitos/riscos | Cobertos pelo fluxo genérico da seção 8.4 do escopo; RIPD pendente |

## 2. Observações clínicas (sinais vitais)

| Campo | Conteúdo |
| --- | --- |
| Operação | Registro de observações clínicas estruturadas (`app.patients` / observações) |
| Finalidade | **PENDENTE DE APROVAÇÃO** |
| Categorias de dados | Sinais vitais e avaliações (SpO2, FC, FR, temperatura, glicemia, consciência, dor, IMC — ver `CLASSIFICACAO_DADOS_CLINICOS.md`) — dado de saúde |
| Titulares | Pacientes |
| Base legal | **PENDENTE DE APROVAÇÃO** |
| Fluxo/localização | PostgreSQL, mesma região do cadastro |
| Retenção | Ver `TABELA_RETENCAO.md` — categoria "Observações" |
| Segurança | Motor de regras determinístico versionado (`app.rules_engine`); nenhum dado sai do banco nesta etapa |

## 3. Upload de mídia (áudio/imagem/vídeo)

| Campo | Conteúdo |
| --- | --- |
| Operação | Upload via URL pré-assinada, quarentena, validação de MIME/checksum, promoção (`app.media`) |
| Finalidade | **PENDENTE DE APROVAÇÃO** — apoio multimodal à análise de risco |
| Categorias de dados | Voz, imagem, vídeo — dado sensível mesmo sem identificação direta (voz e rosto não são anônimos apenas por remoção de nome, seção 8.2 do escopo) |
| Titulares | Pacientes (e potencialmente equipe assistencial presente em vídeo, a avaliar no RIPD) |
| Base legal | **PENDENTE DE APROVAÇÃO** |
| Fluxo/localização | S3 (ADR 0003), criptografado com KMS (`infra/modules/kms`), bucket sem acesso público (`infra/modules/storage`) |
| Retenção | Ver `TABELA_RETENCAO.md` — categorias "Mídias originais"/"Derivados"/"Quarentena" |
| Segurança | Antimalware/validação de assinatura de MIME (`app.media.validation`), versionamento S3, lifecycle configurável |

## 4. Consolidação de risco com LLM (OpenAI)

| Campo | Conteúdo |
| --- | --- |
| Operação | Resumo textual explicativo gerado por LLM a partir de uma allowlist de campos já minimizados (`app.risk_consolidation`, `app.integrations.llm`) |
| Finalidade | Explicar, em linguagem natural, um resultado de risco já calculado deterministicamente — nunca decidir o risco |
| Categorias de dados enviadas ao fornecedor | Nível/rótulo de risco calculado, códigos de regra casados, resumos de qualidade por modalidade (texto/áudio/imagem/vídeo) — **nunca** nome, CPF, texto bruto do paciente ou mídia (ver `app/integrations/llm/base.py::LlmSummaryRequest`, travado por teste `test_allowlist_has_no_raw_patient_text_fields`) |
| Titulares | Pacientes (indiretamente, via dados minimizados) |
| Base legal | **PENDENTE DE APROVAÇÃO** |
| Agentes/suboperador | OpenAI (fornecedor de IA) — avaliação de segurança/contrato/DPA/região **PENDENTE** (seção 8.5 do escopo: nenhum fornecedor novo recebe dados reais sem essa avaliação) |
| Fluxo/localização | API OpenAI, região e política de retenção a confirmar no contrato; `store=False` e Zero Data Retention quando exigido (seção 8.8) |
| Retenção | Resumo e hash de entrada/saída armazenados em `RiskConsolidation` (ver `TABELA_RETENCAO.md` — categoria "Prompt/resposta") |
| Segurança | Allowlist de campos, saída por schema rígido sem campo de risco, prompt de sistema delimitando dados não confiáveis (`app.integrations.llm.openai_adapter`), falha do LLM nunca bloqueia o resultado determinístico |
| Transferência internacional | **PENDENTE DE APROVAÇÃO** — mecanismo do art. 33 da LGPD/Resolução CD/ANPD 19/2024 a documentar |

## 5. Relatório de análise (laudo)

| Campo | Conteúdo |
| --- | --- |
| Operação | Geração de laudo DRAFT e confirmação com PDF definitivo (`app.reports`) |
| Finalidade | **PENDENTE DE APROVAÇÃO** — documentação assistencial da análise |
| Categorias de dados | Conteúdo clínico consolidado (risco, conduta, evidências) + identificação do paciente/profissional revisor |
| Titulares | Pacientes, profissional que confirma o laudo |
| Base legal | **PENDENTE DE APROVAÇÃO** |
| Fluxo/localização | PDF gerado em memória (`app.reports.pdf`), armazenado em S3 sob prefixo `generated/` (`app.storage`) |
| Retenção | Ver `TABELA_RETENCAO.md` — categoria "Relatórios" |
| Segurança | PDF só é gerado/gravado na confirmação (nunca antes), garantindo que o arquivo baixado corresponde exatamente ao que foi revisado |

## 6. Auditoria

| Campo | Conteúdo |
| --- | --- |
| Operação | Registro append-only de todo acesso/ação relevante (`app.audit`) |
| Finalidade | Rastreabilidade, detecção de incidentes, prestação de contas (LGPD art. 37, seção 6.14 do escopo) |
| Categorias de dados | Metadados de ação (ator, papel, recurso, resultado, timestamp) — **sem** conteúdo clínico |
| Titulares | Usuários do sistema (profissionais, administradores) |
| Base legal | Legítimo interesse do controlador em segurança/auditoria — **confirmação formal PENDENTE** |
| Fluxo/localização | PostgreSQL, cadeia de hash encadeada (`app.audit.hashing`), imutável (sem UPDATE/DELETE) |
| Retenção | Ver `TABELA_RETENCAO.md` — categoria "Auditoria" (tipicamente mais longa que dados clínicos, por exigência regulatória) |

---

**Revisão:** este inventário deve ser revisto sempre que uma nova
modalidade, fornecedor, finalidade, país ou integração for adicionada
(mesmo gatilho definido para o RIPD, seção 8.7 do escopo).
