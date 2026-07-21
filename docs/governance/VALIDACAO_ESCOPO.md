# Validação da Implementação contra ESCOPO_PROJETO.md

> Auditoria seção a seção do que foi implementado nos 16 itens do backlog
> original mais os 4 sub-itens da seção 4 (4.1 vídeo, 4.2 áudio, 4.3 texto,
> 4.4 imagem), o item 4.5 (detecção de anomalias), o item 5.3
> (administração) e a identidade real via Cognito + unidade/vínculo
> assistencial + break glass (seções 5.2/6.10) contra os requisitos do
> escopo.
> Convenções: ✅ atende, 🟡 atende
> parcialmente (MVP reduzido, com lacuna disclosed no próprio código/docs),
> ❌ não implementado. Toda linha cita o arquivo/mecanismo real que
> sustenta a avaliação — nada aqui é uma autoavaliação sem evidência.

## Contexto geral

O escopo descreve um sistema de produção completo (visão computacional
real com OpenPose/YOLO, transcrição real via Amazon Transcribe, Cognito
com MFA, CRUD administrativo completo, SAST/DAST/pentest, RIPD aprovado
etc.). O que foi construído nos 16 itens do backlog original mais os 4
sub-itens da seção 4 (4.1–4.4), o item 5.3 (administração) e a identidade
real via Cognito (seções 5.2/6.10) é a **fundação arquitetural, o fluxo de
ponta a ponta do MVP, uma primeira camada real de análise de conteúdo por
modalidade** (NLP clínico determinístico, DSP acústico, heurística de
categoria de imagem, orquestração de pose/detecção de vídeo), **o CRUD
administrativo de especialidade/funcionário/publicação de regras clínicas
e de usuários/papéis de acesso, e o adaptador de identidade real (Cognito:
verificação de token JWKS, MFA obrigatório em produção, sessão revogável
centralmente, bloqueio por tentativa, unidade + vínculo assistencial,
break glass)** — deliberadamente sem simular capacidades de IA treinada
que não existem, nem regulatório/compliance que exige assinatura humana
(RIPD, Anvisa). Esse padrão se confirma seção a seção abaixo.

---

## Seção 4 — Entregas Técnicas Obrigatórias

| Requisito | Status | Evidência |
| --- | --- | --- |
| 4.1 Análise de vídeo com OpenPose/YOLO, evidências temporais, correlação de eventos | 🟡 | Adaptador real `app/integrations/vision/openpose_yolo.py` orquestra extração de quadros amostrados (`FrameExtractor`) + estimativa de pose (`PoseEngine`, OpenPose) + detecção de objetos (`DetectionEngine`, YOLOv8), seguindo o mesmo padrão dos demais adaptadores (Protocol + injeção de dependência); testado com colaboradores falsos (`test_vision_adapters.py`), não exercitado contra `ffmpeg`/OpenPose/YOLOv8 reais (não instalados neste sandbox — ver `app/integrations/vision/real_engines.py` e `ffmpeg_frame_extractor.py`). Adaptador LOCAL retorna `UNAVAILABLE` honesto (nunca pose/detecção fabricada). Evidência por quadro (`frame_index`) preservada nos achados. Avaliação de alternativas gerenciadas da AWS documentada na ADR 0016 — Rekognition Video não oferece estimativa de pose, requisito central desta seção, por isso mantido o worker self-hosted do escopo |
| 4.2 Análise de áudio com Amazon Transcribe, termos clínicos, rascunho de nota | 🟡 | Adaptador real `app/integrations/transcription/aws_transcribe.py` (boto3, `start_transcription_job`/`get_transcription_job`, pt-BR) segue o mesmo padrão do adaptador LLM (item 12); testado com cliente boto3 falso (`test_transcription_adapters.py`), não exercitado contra AWS real (sem credenciais neste sandbox). Adaptador LOCAL retorna `UNAVAILABLE` honesto (nunca transcrição fabricada). Quando há transcrição real, reaproveita o NLP da seção 4.3 para termos clínicos candidatos e monta rascunho de nota. Também adicionada análise acústica real (energia/pausas/segmentos via DSP em `app/acoustics/voice_analysis.py`) gerando hipóteses de alteração vocal rotuladas como não confirmadas |
| 4.3 Análise de texto clínico (negação, temporalidade, certeza, experienciador) | ✅ | `app/clinical_nlp/text_analysis.py` implementa NegEx/ConText determinístico real (regras/pistas lexicais, não estatístico) para os 4 eixos exigidos; wired em `app/processors/text.py`, populando `model_observations` do laudo (`app/reports/builder.py`) e testado com os 4 exemplos literais do escopo (`test_clinical_nlp_text_analysis.py`, `test_integration_end_to_end.py`). Léxico de termos clínicos é curado/MVP, não versionado como `ClinicalRuleSet` — disclosed no docstring do módulo |
| 4.4 Análise de imagem por categoria com processador específico | 🟡 | `app/vision/image_category.py` roteia por categoria (fotografia/documento/radiológica/não suportada) via heurística real de cor/textura sobre pixels decodificados (Pillow), com área de maior interesse, qualidade, método/versão, limitações e recomendação de revisão — testado com imagens sintéticas reais (`test_vision_image_category.py`, `test_processors_image.py`). Não é um classificador clínico treinado (disclosed no módulo); categorias não suportadas não recebem tentativa de diagnóstico, conforme exigido |
| 4.5 Detecção de anomalias com alertas, reconhecimento, escalonamento | 🟡 | `app/anomaly_detection/` implementa deteção estatística real (não um modelo treinado) para os sinais explicitamente citados pela seção 4.5 ("Batimentos, pressão arterial, oxigenação" — `HEART_RATE`/`BLOOD_PRESSURE`/`SPO2`, mais `RESPIRATORY_RATE`/`TEMPERATURE` por serem o mesmo tipo de sinal): desvio da linha de base do próprio paciente (média/desvio-padrão das leituras recentes) e variação abrupta entre leituras consecutivas, ambos determinísticos e auditáveis (`app/anomaly_detection/detection.py`, 10 testes puros). `evaluate_and_create_alerts` roda na mesma transação de `create_observation` — uma leitura anômala cria um `ClinicalAlert` atomicamente. Fluxo completo de reconhecer/escalar/encerrar via `/alerts/{id}/acknowledge|escalate|resolve`, testado ponta a ponta em `test_anomaly_alerts_api.py` (spike cria alerta, leituras estáveis não criam, ação exige vínculo assistencial). Frontend: `AlertsPanel.tsx` na tela do paciente. Nunca alimenta `RiskConsolidation` (eixo deliberadamente separado, ver docstring de `AlertSeverity`). **Não implementado**: as outras duas linhas da tabela da própria seção 4.5 — anomalia em **prescrições** (a seção condiciona isso a "definição de fontes farmacológicas, interações, doses, alergias e validação farmacêutica/clínica", nenhuma das quais existe) e em **padrão de movimentação do paciente** (exigiria agregar achados de pose do item 4.1 entre múltiplas análises de vídeo do mesmo paciente ao longo do tempo — mecanismo de agregação longitudinal ainda não existe) |
| 4.6 Evidência por achado (natureza, fonte, valor, qualidade, confiança, regra/versão, limitações, revisão) | 🟡 | `ModalityFinding` (item 11) registra modalidade/qualidade/métricas/summary; achados de vídeo (4.1) e áudio (4.2) preservam `frame_index`/timestamps como evidência dentro de `quality_metrics`; `RiskConsolidation.code_evaluations` rastreia regra/versão. Falta o campo `revisão` (aceito/corrigido/rejeitado) por achado individual — só existe confirmação do laudo como um todo |

**Leitura (atualizada após a implementação real de 4.1/4.2/4.3/4.4):** os
quatro processadores de modalidade deixaram de ser só avaliadores de
qualidade — todos rodam análise real (NLP clínico determinístico para
texto/transcrição, DSP acústico para áudio, roteamento por categoria para
imagem, extração de quadros + pose/detecção orquestrada para vídeo),
populando de fato as seções 6/7 do laudo quando há achado. Nenhuma dessas
análises é um modelo de IA treinado sobre conteúdo clínico real — são
heurísticas/DSP/regras determinísticas ou adaptadores reais para serviços
externos (Transcribe) e worker self-hosted (OpenPose/YOLOv8), todos
honestamente rotulados como tal em cada módulo. O adaptador de vídeo
(`OpenPoseYoloVideoAdapter`) tem sua orquestração testada com
colaboradores falsos, mas não foi exercitado contra `ffmpeg`/OpenPose/
YOLOv8 reais neste sandbox (sem esses binários/pesos instalados) — a
mesma limitação de "código real, não exercitado ao vivo" já disclosed
para `AwsTranscribeAdapter` no item 4.2.

---

## Seção 5 — Requisitos Funcionais

| Requisito | Status | Evidência |
| --- | --- | --- |
| 5.1 Cadastro de paciente (dados pessoais) | 🟡 | `Patient` tem prontuário, nome, nascimento, idade calculada, sexo, email. Docstring do próprio modelo admite: "campos clínicos completos, alergias, medicamentos e histórico longitudinal serão adicionados" — não implementados |
| 5.1 Dados clínicos com unidade/contexto/janela de atualidade | 🟡 | Observações estruturadas existem e o motor de regras usa unidade/contexto por regra (`ClinicalRuleSet.required_inputs`). O conceito de "janela de atualidade" / marcação **desatualizado** não foi implementado como campo de observação |
| 5.1 Campos extras de glicemia (momento, tipo paciente, uso de insulina) | ✅ | `test_glycemia_observation_without_context_returns_422` exige esses campos |
| 5.2 Login + MFA + Cognito | 🟡 | `app/core/security.py` tem dois adaptadores selecionados por `Settings.identity_provider`: `LOCAL` (cabeçalho `X-Dev-Subject`, só dev/testes, bloqueado por `Settings.requires_real_identity_provider` em homologation/production) e `COGNITO` (`app/integrations/identity/cognito.py`: valida assinatura RS256 via JWKS, emissor, audiência por tipo de token, expiração, `token_use`; exige `amr` conter MFA quando `settings.is_production`). Testado com par de chaves RSA gerado em memória (`test_cognito_identity_verifier.py`, 9 casos: token válido, expirado, emissor/audiência/tipo de token errados, claim ausente, assinatura de outra chave). **Não exercitado contra um User Pool Cognito real** (sem credenciais AWS neste sandbox) — mesma limitação de "código real, não exercitado ao vivo" dos demais adaptadores AWS. O provisionamento de credencial (senha/MFA) em si continua inteiramente no Cognito, fora deste backend |
| 5.2 RBAC por papel | ✅ | `require_role`, 5 papéis (`UserRole`), testado em cada módulo (`test_*_api.py`) |
| 5.2 RBAC por instituição/unidade/vínculo assistencial | ✅ | Isolamento por instituição implementado e testado (multi-tenant). Unidade (`CareUnit`) e vínculo assistencial (`PatientCareAssignment`) agora existem como conceito real: `app.core.security.require_patient_access` exige vínculo ativo (ou break glass) e é chamado em toda rota que recebe `patient_id` (`patients.py`, `media.py`, `orchestrator.py`, `reports.py`); CRUD de vínculo/unidade em `/patients/{id}/care-assignments` e `/admin/care-units`. Testado em `test_identity_access_controls_api.py` (acesso negado sem vínculo, concedido após vínculo, negado de novo após encerrar vínculo) |
| 5.2 Break glass | ✅ | `POST /patients/{patient_id}/break-glass` (`BreakGlassGrant`, prazo máx. 4h, justificativa obrigatória ≥10 caracteres) concede acesso imediato fora do vínculo formal; gera evento `AUTHORIZATION`/`BREAK_GLASS_GRANTED` na concessão e `PATIENT_ACCESS_VIA_BREAK_GLASS` em cada acesso subsequente sob o grant — nunca um bypass silencioso. Limite de taxa mais restrito (`rate_limit_auth`) por ser a única ação de elevação de acesso exposta diretamente pela API. Testado em `test_identity_access_controls_api.py` |
| 5.2 Bloqueio por tentativa, expiração de sessão, revogação | ✅ | `AuthFailedAttempt`/`is_locked_out` (janela deslizante, `login_max_failed_attempts`/`login_lockout_window_seconds`) bloqueia o adaptador COGNITO após tentativas malsucedidas (token de conta inativa/inexistente repetido); `UserSession` registra cada token verificado (`jti`) e permite revogação centralizada mesmo com JWT ainda válido (`get_active_session`, consultado a cada requisição); `revoke_all_sessions_for_user` é acionado automaticamente ao trocar o papel ou desativar um usuário (`app/administration/service.py::update_user_role`) e sob demanda via `POST /admin/users/{id}/revoke-sessions`. Testado unitariamente (`test_identity_access_controls_api.py::TestLoginLockout`) |
| 5.3 Administração (especialidade, funcionários, dados clínicos, usuários/papéis) | ✅ | CRUD real: `app/administration/` (models/service) + `app/api/routes/administration.py` (`/admin/specialties`, `/admin/employees`, ambos restritos a administrador técnico/clínico) — testado em `test_administration_api.py`. "Dados clínicos" tem o fluxo de publicação/rollback exigido pelo escopo (`publish_rule_set`/`rollback_rule_set`, restrito a administrador clínico): `ClinicalRuleSet.status` é filtrado de verdade por `get_current_rule_set` — conjuntos ficam em `draft` até publicados, nunca contam como vigentes antes disso. CRUD de usuários/papéis de acesso (`create_user`/`list_users`/`get_user`/`update_user_role`/`revoke_user_sessions`, `/admin/users*`) fecha a lacuna final da seção: é o equivalente local ao `AdminCreateUser` do Cognito — o espelho de instituição/papel que `get_current_user` sempre consulta, testado em `test_identity_access_controls_api.py::TestUserCrud`. Frontend: área de administração dividida em telas/rotas próprias por seção (ESPECIFICACAO_FRONTEND.md seção 7.11 — "separar em abas ou rotas"), não mais uma única tela empilhada: `/admin/specialties`, `/admin/employees`, `/admin/clinical-rules`, `/admin/users`, `/admin/care-units` (`AdminLayout.tsx` + uma página por seção em `src/features/admin/`), cada uma testada isoladamente. `GET /admin/care-units` (listagem, antes só existia criação) foi adicionado para a tela de unidades funcionar |
| 5.4 Fluxo de análise multimodal (consultar paciente → habilitar mídia → "Realizar Análise") | ✅ | Implementado ponta a ponta: `AnalysisNewPage.tsx` → `POST /analyses` → upload → `POST /analyses/{id}/submit` |
| 5.4 Validação de formato/tamanho/malware/metadados | 🟡 | Validação de MIME/assinatura/tamanho/checksum implementada (`app/media/validation.py`, item 8). Varredura antimalware real (engine de vírus) **não implementada** — só validação estrutural |
| 5.4 Cancelamento e reprocessamento | ✅ | `cancel_analysis`/`retry_analysis` (item 10), testados |
| 5.4 Avaliação de qualidade por modalidade (estado, métricas, fatores) | ✅ | `app/processors/quality.py`, estados ADEQUATE/MODERATE/INSUFFICIENT/INVALID, testado |
| 5.5 Consolidação com LLM (síntese, não decisão) | ✅ | `app/risk_consolidation` + `app/integrations/llm` — risco sempre do motor determinístico, LLM sem campo capaz de alterá-lo (testado em `test_prompt_injection_security.py`) |
| 5.5 Rastreabilidade (modelo, versão, prompt, hash) | ✅ | `RiskConsolidation.llm_provider/model/prompt_version/input_hash/output_hash` |
| 5.6 Relatório com as 13 seções mínimas | 🟡 | `app/reports/builder.py` implementa as 13 seções da estrutura mínima. Seções 6 (observações de modelo) e 7 (hipóteses assistidas) agora populam de fato quando há achado real (NLP clínico, DSP acústico, categoria de imagem, pose/detecção de vídeo — seção 4.1-4.4); ficam vazias apenas quando nenhum achado é gerado (ex.: adaptador LOCAL sem motor real, texto sem termo clínico reconhecido) |
| 5.6 Tabela canônica de risco (cor+número+rótulo+ícone) | 🟡 | Cores/níveis implementados no backend e frontend (`RiskBadge`). Não validei se o frontend exibe ícone além de cor/número/texto — a exigir checagem visual |
| 5.6 Download em PDF | ✅ | `app/reports/pdf.py`, `GET /analyses/{id}/report/pdf`, testado (`%PDF-` real) |
| 5.7 Histórico de análises | ✅ | `AnalysesListPage.tsx`, `GET /analyses` paginado |
| 5.8 Auditoria pesquisável, com pseudonimização de paciente | 🟡 | Busca por ator/ação/recurso/resultado implementada (`GET /audit/events`). Pseudonimização do identificador de paciente na tela de auditoria **não implementada** — `resource_id` é o UUID real |
| 5.8 Exportação com armazenamento imutável (WORM) separado | ❌ | Auditoria é append-only no PostgreSQL (item 6), mas **não há exportação assíncrona para armazenamento WORM separado** exigida pela seção 6.14 |
| 5.9 Aceitar/corrigir/rejeitar cada achado com justificativa | 🟡 | Existe confirmação binária do laudo inteiro (`confirm_report`). **Não existe** revisão granular por achado individual (aceito/corrigido/rejeitado por `ModalityFinding`) |
| 5.9 Correções não apagam original | ✅ (por construção) | Nada no sistema faz UPDATE destrutivo de achado; `Report` é DRAFT→CONFIRMED, nunca reescrito silenciosamente |

---

## Seção 6 — Requisitos Técnicos

| Requisito | Status | Evidência |
| --- | --- | --- |
| 6.1 Stack (FastAPI/Pydantic/SQLAlchemy/Alembic/React+TS/PostgreSQL/S3/SQS/Docker/Pytest) | ✅ | Confirmado em `backend/pyproject.toml`, `frontend/package.json`, `docker-compose.yml`, estrutura de `app/` |
| 6.2 boto3 encapsulado em adaptadores, domínio não importa AWS/OpenAI diretamente | ✅ | `app/storage/s3.py`, `app/queue/sqs.py`, `app/integrations/llm/openai_adapter.py` isolam os SDKs; módulos de domínio dependem de `StorageAdapter`/`QueueAdapter`/`LlmAdapter` (Protocols) |
| 6.2 Amazon Transcribe | 🟡 | `AwsTranscribeAdapter` (item 4.2) implementa o fluxo batch real (`start_transcription_job`/poll/`get_object`), `pt-BR`; testado com cliente `boto3` falso, não exercitado contra AWS real (sem credenciais neste sandbox) |
| 6.2 OpenPose/YOLOv8 (candidatos para worker de vídeo) | 🟡 | `OpenPoseYoloVideoAdapter` (item 4.1) implementa a orquestração real (extração de quadros + pose + detecção); os motores concretos (`app/integrations/vision/real_engines.py`, `ffmpeg_frame_extractor.py`) chamam `ultralytics`/binário do OpenPose/`ffmpeg`, nenhum instalado neste sandbox — não exercitados ao vivo |
| 6.2.2 Frontend só usa URL pré-assinada, nunca IAM | ✅ | `app/storage/*` gera URL pré-assinada; frontend usa `uploadFileToPresignedUrl` (item 14), nunca recebe credencial |
| 6.2.2 IAM Role por processo | ✅ | `infra/modules/ecs/main.tf` — uma `aws_iam_role.task` por entrada de `var.workers` + API, nenhuma compartilhada (item 15) |
| 6.2.2 Execution role separada da task role | ✅ | `aws_iam_role.execution` vs `aws_iam_role.task[*]` em `infra/modules/ecs/main.tf` |
| 6.2.2 Sem access key permanente no código | ✅ | RDS usa `manage_master_user_password`; OpenAI key via Secrets Manager placeholder (`infra/modules/secrets`) |
| 6.3 Terraform modular, estado remoto, ambientes separados | ✅ | `infra/modules/*` + `infra/environments/{local,homologation,production}` (item 15) — validado apenas sintaticamente (`python-hcl2`), sem `terraform validate`/`plan` reais (disclosed no item 15) |
| 6.3 ECR com imagem por commit | 🟡 | Módulo `infra/modules/ecr` existe e cria repositórios; a prática de taggear por commit no CI **não foi implementada** (não há pipeline de build/push) |
| 6.3 CI/CD (GitHub Actions) | 🟡 | Existe workflow mínimo (item 6, `.github/workflows`) com verificação; **não cobre** scan de segurança, build de imagem, deploy — escopo original da seção 6.12 |
| 6.4 Monólito modular com módulos do domínio listados | ✅ | Estrutura `app/{patients,identity,media,orchestrator,processors,rules_engine,risk_consolidation,reports,audit,integrations,...}` corresponde à tabela da seção 6.4 |
| 6.5 PostgreSQL fonte de verdade; binários só no S3 | ✅ | `MediaAsset` guarda só chave/hash/MIME/tamanho (ADR 0002/0003) |
| 6.5 RLS ou mecanismo equivalente de isolamento por tenant | 🟡 | Isolamento por `institution_id` aplicado em toda query de serviço (não RLS nativo do Postgres) — ADR 0012 documenta essa escolha como "mecanismo equivalente", mas **não é RLS literal** |
| 6.6 Fluxo assíncrono (analysis_id imediato, URL pré-assinada, fila, workers) | ✅ | Implementado e testado ponta a ponta (item 10, `test_integration_end_to_end.py`) |
| 6.7 Máquina de estados (10 estados) | ✅ | `app/orchestrator/state_machine.py` implementa exatamente os 10 estados do escopo |
| 6.8 Resiliência (timeout, retry, backoff, DLQ, idempotência, circuit breaker) | 🟡 | DLQ com redrive existe (`infra/modules/queue`, item 15). Retry com backoff no processamento existe via reenfileiramento (`retry_analysis`). **Circuit breaker e rate limit por fornecedor não implementados** |
| 6.9 API sem GPU, workers CPU separados, IAM por processo | ✅ | Confirmado na seção 6.2.2 acima + `infra/modules/ecs` |
| 6.10 Identidade real via Cognito | 🟡 | Módulo `identity` Terraform existe (infra pronta, item 15) e a aplicação agora **consome** Cognito de fato quando `identity_provider=COGNITO` (`app/integrations/identity/cognito.py`, seção 5.2 acima) — não exercitado contra um User Pool real neste sandbox (sem credenciais AWS) |
| 6.10 TLS, criptografia em repouso (KMS) | ✅ (infra) | `infra/modules/kms` cobre S3/SQS/Secrets/RDS |
| 6.10 Rate limiting / proteção de aplicação | ✅ | `slowapi` registrado em `app/main.py` (`app/core/rate_limit.py`): limite padrão por IP (`rate_limit_default`, 120/min) em toda rota, limite mais restrito (`rate_limit_auth`, 10/min) na concessão de break glass; erro 429 no formato padrão da API (`code=RATE_LIMIT_EXCEEDED`). `Settings.rate_limit_*` já existiam configurados mas nunca haviam sido de fato registrados — lacuna fechada nesta rodada |
| 6.10.1 Quarentena, promoção, varredura antimalware | 🟡 | Quarentena/promoção implementadas (`app/media/service.py`); varredura antimalware real **não implementada** (só validação de assinatura de arquivo) |
| 6.11 Observabilidade (request_id, métricas, alertas de segurança) | 🟡 | `RequestIdMiddleware` existe. Métricas estruturadas (latência por endpoint, profundidade de fila, custo por análise) e alertas de segurança **não implementados** |
| 6.12 SBOM, SAST, SCA, DAST, assinatura de imagem | ❌ | Não instrumentado no CI atual |
| 6.14 Auditoria (eventos mínimos, cadeia de hash, exportação WORM) | 🟡 | Cadeia de hash imutável implementada e testada (item 6, `verify_chain`). Exportação assíncrona para armazenamento WORM separado **não implementada** |
| 6.15 Continuidade e recuperação (RPO/RTO, backup, restauração testada) | ❌ | RDS tem `backup_retention_days` configurável (infra), mas RPO/RTO não definidos, teste de restauração não realizado |

---

## Seção 7 — Requisitos Não Funcionais

| Requisito | Status | Evidência |
| --- | --- | --- |
| Disponibilidade/Resiliência | 🟡 | Estados explícitos de falha (`FAILED_RETRYABLE`/`FAILED_FINAL`), reprocessamento manual — sem retry automático com backoff configurável testado |
| Integridade (idempotência, hash) | 🟡 | Upload usa checksum (item 8); análise não tem chave de idempotência formal na criação (`create_analysis` não deduplicada por client-supplied idempotency key) |
| Assincronismo | ✅ | `analysis_id` retornado imediatamente, processamento fora do request HTTP |
| Testes (unitário/integração/contrato/carga/segurança/recuperação/clínica) | 🟡 | Unitário/integração/segurança implementados (itens 1-16). **Carga**: instrumento inicial só (`scripts/load_test.py`), não teste de carga real. **Recuperação**: não testada. **Validação clínica**: não realizada (depende de responsável clínico humano) |
| Segurança de aplicação (SAST/SCA/DAST/pentest) | ❌ | Não instrumentado |
| Acessibilidade | 🟡 | Não auditada nesta validação (fora do escopo de código backend revisado aqui) |
| Qualidade de IA (métricas por versão/população, drift) | ❌ | Não implementado — não há mecanismo de monitoramento de drift |

---

## Seção 8 — LGPD

| Requisito | Status | Evidência |
| --- | --- | --- |
| Inventário de tratamento | 🟡 | `docs/governance/INVENTARIO_TRATAMENTO.md` criado — bases legais e finalidades marcadas **PENDENTE DE APROVAÇÃO**, não aprovadas |
| RIPD | 🟡 | `docs/governance/RIPD.md` — esqueleto com riscos identificados, sem aprovação/assinatura |
| Minimização/pseudonimização | 🟡 | Minimização real implementada para o LLM (allowlist testada). Pseudonimização de identificador de paciente em telas/auditoria **não implementada** (seção 5.8 acima) |
| Tabela de retenção | 🟡 | `docs/governance/TABELA_RETENCAO.md` mapeia categoria→mecanismo; **job de expurgo automático não existe** (lacuna admitida no próprio documento) |
| Direitos dos titulares | ❌ | Fluxo não implementado |
| Fornecedores/transferência internacional | ❌ | Avaliação formal de AWS/OpenAI (DPA, SCC, art. 33) não realizada |
| Plano de resposta a incidentes | 🟡 | `docs/governance/PLANO_RESPOSTA_INCIDENTES.md` — estrutura e 11 playbooks descritos; nunca exercitado, papéis reais não nomeados |

---

## Seção 9 — Governança Clínica/Anvisa

| Requisito | Status | Evidência |
| --- | --- | --- |
| Avaliação de enquadramento SaMD | 🟡 | `docs/governance/AVALIACAO_ANVISA_SAMD.md` — avaliação preliminar técnica, explicitamente não substitui avaliação regulatória formal |
| Metadados de regra clínica (fonte, população, versão, aprovador) | ✅ | `ClinicalRuleSet` tem `version`, `population`, `status`, `effective_from/to`; `content_hash` garante imutabilidade de versão publicada |
| Avaliação de viés por subgrupo | ❌ | Não implementado |
| Plano de gerenciamento de risco/vigilância pós-implantação | ❌ | Não elaborado |

---

## Seção 12 — Critérios de Aceite (itens objetivamente testáveis)

| Critério | Status | Evidência |
| --- | --- | --- |
| Mesma entrada + mesma versão de regra → mesma classificação | ✅ | Motor determinístico puro (`app/rules_engine`), testado |
| Dado ausente/inválido nunca vira "normal" | ✅ | `RuleEvaluationOutcome.INCONCLUSIVE` explícito, testado (`test_consolidate_without_structured_inputs_is_inconclusive`) |
| Hipóteses não alteram criticidade determinística | ✅ | `LlmSummaryResult` sem campo de risco (testado em `test_prompt_injection_security.py`) |
| Upload direto frontend→S3 sem passar pelo backend | ✅ | URL pré-assinada (item 8) |
| API retorna rápido, sem aguardar processamento síncrono | ✅ | `POST /analyses` e `/submit` não bloqueiam no processamento |
| Modalidade repetível sem duplicar resultado | ✅ | `RiskConsolidation`/`Report` fazem upsert idempotente |
| Falha transitória reenfileira; falha esgotada vai a DLQ | 🟡 | Estados existem; DLQ de infraestrutura existe (item 15); **o código da aplicação não testa esgotamento de tentativas até DLQ real** |
| Domínio não importa SDK AWS/OpenAI diretamente | ✅ | Confirmado via adaptadores |
| MFA obrigatório, sessões revogáveis centralmente | 🟡 | Implementado no adaptador COGNITO (`verified.mfa_verified` obrigatório quando `settings.is_production`; `UserSession`/`revoke_all_sessions_for_user` para revogação centralizada) — não exercitado contra um User Pool real; adaptador LOCAL (dev/testes) continua sem MFA/sessão real por design |
| Acesso a paciente depende de papel+instituição+unidade+vínculo | ✅ | Papel (`require_role`) + instituição (isolamento multi-tenant) + unidade/vínculo assistencial (`require_patient_access`, `PatientCareAssignment`/`BreakGlassGrant`) — os quatro eixos aplicados e testados |
| Testes provam isolamento entre instituições | ✅ | `test_integration_end_to_end.py`, `test_*_api.py` (cross-tenant 404) |
| URLs pré-assinadas expiram e não sobrescrevem objeto | ✅ | TTL configurável (`upload_url_ttl_seconds`), chave única por objeto |
| Todo acesso relevante gera evento de auditoria | 🟡 | Cobertura ampla nos módulos implementados, incluindo administração (`USER_CREATE`/`USER_UPDATE`/`USER_SESSIONS_REVOKED`/`CARE_ASSIGNMENT_CREATE`/`CARE_ASSIGNMENT_END`) e autorização (`PATIENT_ACCESS_DENIED`/`PATIENT_ACCESS_VIA_BREAK_GLASS`/`BREAK_GLASS_GRANTED`); **não cobre** tudo (ex.: leituras de listagem em massa não são auditadas, só acesso a paciente específico) |
| RIPD aprovado antes de dados reais | ❌ | Esqueleto apenas, não aprovado — **dados reais não devem ser usados** |
| Testes provam que LLM não pode ser manipulado para alterar risco/vazar segredo | ✅ | `test_prompt_injection_security.py` |
| LLM sem acesso livre a banco/objetos/internet/ferramentas | ✅ | `OpenAiLlmAdapter` só recebe o payload minimizado, sem tools/function calling para recursos externos |
| SAST/SCA/DAST/SBOM/pentest sem achado crítico aberto | ❌ | Não instrumentado — critério não pode ser considerado atendido |
| Terraform como mecanismo autorizado de infraestrutura | ✅ | `infra/` completo (item 15), com ressalva de validação sintática apenas |

---

## Síntese: gaps críticos antes de qualquer uso com paciente real

1. **Reconhecimento de conteúdo por modelo de IA treinado ainda não foi exercitado ao vivo (seção 4)** — as quatro modalidades já rodam análise real de conteúdo (NLP clínico determinístico para texto/transcrição, DSP acústico para áudio, heurística de categoria para imagem, orquestração de pose/detecção para vídeo), mas os adaptadores que dependem de fornecedor/binário externo (Amazon Transcribe, OpenPose, YOLOv8, `ffmpeg`) nunca foram exercitados contra o serviço/binário real neste ambiente — só testados com colaboradores falsos injetados. Isso ainda é uma lacuna relevante antes de qualquer uso assistencial, mas menor do que "nenhuma análise de conteúdo existe".
2. **Identidade real (Cognito + MFA) existe em código, mas não foi exercitada contra um User Pool real** — `app/integrations/identity/cognito.py` valida assinatura JWKS/emissor/audiência/expiração/MFA de verdade (9 testes com par de chaves RSA em memória), e `app/core/security.py` usa esse adaptador quando `identity_provider=COGNITO` (obrigatório em homologation/production via `Settings.requires_real_identity_provider`). O que falta para uso real é puramente operacional: provisionar o User Pool Cognito de fato (o módulo Terraform já existe, item 15) e configurar `COGNITO_USER_POOL_ID`/`COGNITO_CLIENT_ID`/`COGNITO_ISSUER_URL`. O adaptador `X-Dev-Subject` continua existindo só para dev/testes, com a trava de segurança impedindo seu uso fora de local.
3. **Módulo de administração de identidade (CRUD de usuários/papéis de acesso) foi implementado** — especialidade, funcionário, publicação/rollback de regras clínicas e agora também usuários/papéis de acesso (`app/administration/service.py::create_user`/`list_users`/`get_user`/`update_user_role`/`revoke_user_sessions`, `/admin/users*`) têm CRUD real e auditável. O que falta é apenas o provisionamento da credencial em si (senha/MFA), que acontece inteiramente dentro do Cognito (AdminCreateUser), fora do escopo de qualquer backend de aplicação.
4. **RIPD, inventário de tratamento e avaliação de fornecedores não estão aprovados** — só o esqueleto existe; usar dados reais de paciente hoje violaria a própria seção 8 do escopo. Este é um gap organizacional/regulatório que não pode ser fechado por código: exige assinatura humana (DPO, responsável clínico) e não deve ser simulado.
5. **SAST/SCA/DAST/pentest não estão instrumentados** — nenhuma evidência de varredura de segurança automatizada. Depende de infraestrutura de CI (runners, licenças de ferramenta) fora do escopo de código de aplicação.
6. **Job de expurgo por retenção não existe** — exclusão de dado pessoal hoje seria manual.
7. **Exportação de auditoria para armazenamento WORM separado não existe** — a auditoria é forte (hash encadeado, append-only) mas vive só no PostgreSQL transacional.

## O que está solidamente implementado e testado

O esqueleto arquitetural do MVP é consistente com a seção 6: monólito
modular, adaptadores isolando AWS/OpenAI do domínio, máquina de estados
completa, isolamento multi-tenant testado, motor de regras determinístico
versionado, LLM estruturalmente incapaz de alterar risco (testado com
conteúdo adversarial), auditoria com cadeia de hash verificável, RBAC
testado por módulo, e infraestrutura Terraform cobrindo IAM mínimo por
processo. A isso se soma a seção 4 completa em nível de MVP: as
quatro modalidades (texto, áudio, imagem, vídeo) rodam análise real de
conteúdo — determinística/heurística onde isso é suficiente (NLP
NegEx/ConText, DSP acústico, categoria de imagem por cor/textura) e via
adaptador real para os casos que dependem de fornecedor/binário externo
(Amazon Transcribe, OpenPose/YOLOv8), com o mesmo padrão honesto de
"UNAVAILABLE em vez de fabricado" quando o motor real não está disponível.

A seção 5.2/5.3/6.10 (identidade, autorização, administração) também
deixou de ser um esqueleto: o adaptador Cognito valida token real
(assinatura/emissor/audiência/expiração/MFA), sessões são revogáveis
centralmente, bloqueio por tentativa existe, o eixo "unidade + vínculo
assistencial" é aplicado em toda rota que acessa dado de paciente
identificado (`require_patient_access`), break glass gera auditoria em
duas pontas (concessão e cada acesso sob o grant), o CRUD de
usuários/papéis fecha o provisionamento local de conta, e rate limiting
por IP protege toda a API com um limite mais restrito na única rota de
elevação de acesso (break glass). Nenhum desses adaptadores foi
exercitado contra o serviço AWS real (sem credenciais neste sandbox) —
mesma limitação já disclosed para Transcribe/OpenPose/YOLOv8 — mas a
lógica de validação em si tem cobertura de teste real (9 casos com par de
chaves RSA gerado em memória para o verificador Cognito, mais os fluxos
de vínculo/break glass/CRUD de usuário via API).

Esse é o alicerce sobre o qual os controles de governança regulatória
pendentes (seção 8: RIPD/LGPD; seção 9: Anvisa — ambos exigem assinatura
humana e não podem ser simulados por código), a detecção de anomalias
sobre série temporal (4.5), a instrumentação de segurança (SAST/SCA/DAST/
pentest, seção 6.12) e a validação clínica humana das heurísticas de
conteúdo precisam ser construídos antes de qualquer uso assistencial com
paciente real.
