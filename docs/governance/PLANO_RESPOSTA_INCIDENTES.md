# Plano de Resposta a Incidentes (ESCOPO_PROJETO.md seção 8.6)

> Este documento define estrutura, papéis e os playbooks mínimos exigidos
> pelo escopo. Nomes de responsáveis, canais de acionamento e a decisão
> final de comunicar ou não a ANPD/titulares em um incidente real são
> **PENDENTE DE APROVAÇÃO** (exigem estrutura organizacional que não existe
> apenas no código). O que este documento fixa com segurança é o que a
> arquitetura atual permite detectar, conter e evidenciar tecnicamente.

## 1. Classificação e severidade

| Severidade | Critério | Exemplo |
| --- | --- | --- |
| SEV1 — Crítico | Exposição confirmada de dados de saúde de pacientes reais, ou indisponibilidade total do sistema em produção | Bucket S3 de mídia exposto publicamente; RDS acessível pela internet |
| SEV2 — Alto | Risco de exposição não confirmado, ou falha de controle de acesso detectada sem evidência de exploração | Credencial de serviço vazada em log; falha de isolamento multi-tenant descoberta em teste |
| SEV3 — Moderado | Degradação de serviço sem exposição de dados | Fila com DLQ crescendo, workers não processando |
| SEV4 — Baixo | Achado de segurança sem exploração nem exposição | Dependência com CVE conhecida, sem exploit ativo no ambiente |

## 2. Papéis (estrutura mínima — nomes reais PENDENTES)

| Papel | Responsabilidade |
| --- | --- |
| Coordenador de incidente | Decide severidade, aciona os demais papéis, decide comunicação |
| Responsável técnico | Contenção, erradicação, recuperação |
| Encarregado (DPO) | Avalia obrigação de comunicar ANPD/titulares (LGPD/Resolução CD/ANPD 15/2024) |
| Responsável clínico | Avalia impacto assistencial (ex.: laudos afetados, decisões clínicas baseadas em dado corrompido) |
| Comunicação | Notificação a clientes/instituições e, se decidido, à ANPD/titulares |

## 3. Fluxo padrão

1. **Detecção** — alerta automático (a instrumentar) ou relato manual.
2. **Classificação** — severidade inicial atribuída pelo coordenador.
3. **Contenção** — isolar o vetor (revogar credencial, bloquear IP,
   desabilitar integração) sem destruir evidência.
4. **Preservação de evidência** — os eventos de `audit_events` (cadeia de
   hash imutável, `app.audit.hashing.verify_chain`) são a primeira fonte
   de evidência técnica confiável: permitem provar exatamente quem
   acessou o quê, quando, e detectar se algum registro foi adulterado.
5. **Erradicação** — remover a causa raiz.
6. **Recuperação** — restaurar serviço/dados a partir de backup íntegro.
7. **Avaliação de risco/dano** — encarregado avalia se houve dado pessoal
   exposto, a quem, e a gravidade.
8. **Decisão de comunicação** — fundamentada e auditável (registrar a
   decisão e sua justificativa, mesmo quando a decisão for não comunicar).
9. **Lições aprendidas** — post-mortem sem culpabilização individual,
   ações de prevenção com dono e prazo.

Quando aplicável, comunicação à ANPD e aos titulares no prazo regulatório
vigente (atualmente três dias úteis, Resolução CD/ANPD nº 15/2024).

## 4. Capacidades técnicas já disponíveis para resposta a incidentes

| Capacidade | Onde |
| --- | --- |
| Trilha de auditoria imutável e verificável | `app.audit` — detecta inserção/remoção/alteração de eventos |
| Isolamento multi-tenant | `institution_id` derivado sempre do servidor (`app.core.security`), nunca do cliente — reduz superfície de um vazamento cross-tenant |
| Segredos nunca em código/state | RDS com `manage_master_user_password`, OpenAI key via Secrets Manager com placeholder (`infra/modules/secrets`) |
| Criptografia em repouso | KMS único por ambiente cobrindo S3, SQS, Secrets Manager, RDS (`infra/modules/kms`) |
| Revogação de credencial | Rotação nativa via Secrets Manager/RDS; chave OpenAI substituível fora do Terraform |
| Filas com DLQ | Mensagens que falham repetidamente ficam isoladas em `infra/modules/queue` (DLQ), não se perdem silenciosamente |

## 5. Playbooks mínimos (ESCOPO_PROJETO.md seção 8.6)

Cada playbook abaixo segue o fluxo da seção 3. Passos específicos:

### 5.1 Ransomware
- Isolar workloads afetados (parar tasks ECS do serviço comprometido).
- Verificar integridade de backups do RDS antes de restaurar.
- Não pagar resgate sem decisão formal do controlador.

### 5.2 Bucket S3 exposto
- Aplicar/objeto verificar `aws_s3_bucket_public_access_block` (já
  configurado por padrão em `infra/modules/storage` — investigar como foi
  contornado).
- Rotacionar URLs pré-assinadas emitidas (reduzir `upload_url_ttl_seconds`
  temporariamente se necessário).
- Auditar `audit_events` por downloads/uploads no período de exposição.

### 5.3 Credencial comprometida
- Rotacionar via Secrets Manager (RDS: `manage_master_user_password` já
  suporta rotação nativa; OpenAI: substituir o valor do secret).
- Revisar `audit_events` por ações do `external_subject`/role associado à
  credencial no período.

### 5.4 Acesso interno indevido
- Consultar `audit_events` filtrando por `actor`/`resource_type` — a
  auditoria da própria consulta de auditoria também é registrada
  (`AUDIT_QUERY`), permitindo reconstruir quem investigou o quê.
- Revisar se o RBAC (`require_role`) permitiu o acesso indevido por
  configuração incorreta de papel.

### 5.5 Relatório enviado incorretamente
- Identificar o `Report`/`analysis_id` envolvido (`reports` table).
- Avaliar se o destinatário incorreto está em outra instituição (violação
  de isolamento) ou é erro operacional dentro da mesma instituição.

### 5.6 Vazamento em fornecedor (OpenAI ou AWS)
- Consultar `RiskConsolidation.llm_input_hash`/`llm_output_hash` para
  identificar quais análises tiveram chamada ao LLM no período afetado
  (os hashes não revelam o conteúdo, mas permitem correlação com logs do
  fornecedor sem reexpor dado clínico).
- Acionar plano de resposta do fornecedor conforme contrato (**contrato
  ainda PENDENTE de formalização com cláusulas de incidente**, seção 8.5).

### 5.7 Mídia publicada indevidamente
- Revogar acesso público (bucket já bloqueia por padrão — investigar
  causa).
- Verificar `MediaAsset` associado e todas as `Analysis`/`Patient`
  relacionadas para dimensionar o impacto.

### 5.8 Corrupção/exclusão de dados
- Restaurar do backup do RDS (retenção configurada em
  `infra/modules/database`: `backup_retention_days`).
- Validar integridade da cadeia de auditoria pós-restauração
  (`verify_chain`).

### 5.9 Indisponibilidade
- Verificar saúde do ALB/ECS (`infra/modules/ecs`), filas (SQS/DLQ) e RDS.
- Escalar `api_desired_count`/`workers[*].desired_count` conforme
  necessário.

### 5.10 Adulteração de modelo/regra
- Toda `ClinicalRuleSet` é versionada e nunca sobrescrita
  (`app.rules_engine`); comparar `content_hash` da versão em uso com a
  versão aprovada esperada.
- Analisar `audit_events` categoria relevante para identificar quem alterou
  regras/configuração de `llm_provider`.

### 5.11 Dependência comprometida (supply chain)
- Consultar SBOM/SCA (a instrumentar em CI, seção 7 do escopo:
  "SAST, SCA, DAST, SBOM, scan de IaC/container e pentest").
- Fixar/revisar versões em `backend/pyproject.toml` e `frontend/package.json`.

## 6. Exercícios

Exercícios de mesa e testes técnicos (incluindo restauração de backup e
comunicação simulada) devem ocorrer periodicamente — **calendário
PENDENTE de definição** pela equipe de operação.
