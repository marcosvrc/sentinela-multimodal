# Tabela de Retenção e Exclusão (ADR 0015, ESCOPO_PROJETO.md seção 8.3)

> Os **prazos** abaixo são placeholders explícitos, não aprovados — ADR
> 0015 já registra que "a tabela de retenção definitiva será aprovada
> antes do uso com dados reais". O que este documento adiciona é o
> mapeamento entre cada categoria exigida pela seção 8.3 do escopo e o
> mecanismo técnico real que hoje existe (ou não existe) para executá-la,
> para que a aprovação de prazos não fique bloqueada por descoberta tardia
> de que faltava um mecanismo de exclusão.

| Categoria | Onde vive hoje | Mecanismo técnico de exclusão disponível | Prazo | Status |
| --- | --- | --- | --- | --- |
| Cadastro (paciente) | Tabela `patients` (Postgres) | DELETE manual/script (nenhum job automático ainda) | **PENDENTE** | Mecanismo parcial |
| Observações clínicas | Tabelas de observação (Postgres) | DELETE manual/script | **PENDENTE** | Mecanismo parcial |
| Mídias originais | S3, bucket `media` (`infra/modules/storage`) | Lifecycle de versão configurado (`noncurrent_version_retention_days`, default 90) + delete de objeto atual manual | **PENDENTE** | Mecanismo parcial (lifecycle de versão existe; exclusão do objeto corrente ainda não é automática) |
| Derivados de mídia | Não existe hoje — nenhum processador gera derivado persistido (item 11 só grava metadados de qualidade em `ModalityFinding`, não recorte/transcrição) | N/A | N/A | Não aplicável ao MVP atual |
| Transcrição | Não existe — nenhum processador de ASR foi implementado (deliberado, ver `app/processors/audio.py`: só duração/qualidade) | N/A | N/A | Não aplicável ao MVP atual |
| Resultados (risco consolidado) | Tabela `risk_consolidations` (Postgres) | DELETE manual/script | **PENDENTE** | Mecanismo parcial |
| Prompt/resposta (LLM) | Resumo e hashes de entrada/saída em `risk_consolidations.llm_*` — **não** o prompt/resposta completos (não persistidos por padrão, seção 8.8: "conteúdo integral terá armazenamento e retenção próprios somente quando necessário") | DELETE manual/script | **PENDENTE** | Mecanismo parcial |
| Rascunhos de relatório (DRAFT) | Tabela `reports`, campo `content` (JSONB) | DELETE manual/script | **PENDENTE** | Mecanismo parcial |
| Relatórios confirmados (PDF) | S3, prefixo `generated/` + `reports.pdf_sha256` | Delete de objeto S3 manual | **PENDENTE** | Mecanismo parcial |
| Auditoria | Tabela `audit_events` (Postgres) — **append-only por design** (`app.audit.models`: "nenhuma rota ou serviço deve emitir UPDATE ou DELETE") | Nenhum — proposital. Exclusão de auditoria antes do prazo regulatório quebraria a cadeia de hash e a rastreabilidade exigida pela seção 6.14 | **Retenção longa a definir** (tipicamente maior que dados clínicos, por exigência de rastreabilidade) | Por design, sem exclusão seletiva |
| Logs de aplicação | Fora do escopo de código deste MVP — infra usa CloudWatch Logs (`infra/modules/ecs`: `log_retention_days`, default 90 em homologação / 365 em produção) | Retenção nativa do CloudWatch Log Group | Configurado (90/365 dias) — **valor final PENDENTE de aprovação** | Mecanismo existe |
| Backups | RDS automated backups (`infra/modules/database`: `backup_retention_days`) | Retenção nativa do RDS | Configurado (7 dias homologação / 30 dias produção) — **valor final PENDENTE** | Mecanismo existe |
| Quarentena (upload) | Objetos S3 antes da promoção (`app.media` — fluxo de quarentena/aprovação) | `delete_quarantined_object` já implementado (`app.storage.base.StorageAdapter`) | **PENDENTE** (definir prazo máximo em quarentena antes de exclusão automática) | Mecanismo técnico completo, falta job agendado |
| Uploads incompletos | Presigned URLs expiradas sem confirmação — objeto nunca chega a existir de fato no fluxo local; no S3 real, pode deixar multipart incompleto | Lifecycle `abort_incomplete_multipart_uploads` (7 dias, `infra/modules/storage`) | Configurado (7 dias) | Mecanismo existe |
| DLQ (fila de mensagens não processadas) | SQS DLQ (`infra/modules/queue`) | `message_retention_seconds` da fila (14 dias, máximo do SQS) | Configurado (14 dias) — **avaliar se é adequado ou se mensagens de DLQ precisam de reprocessamento/expurgo manual documentado** | Mecanismo existe, processo operacional pendente |

## Lacunas conhecidas a fechar antes de dados reais

1. **Nenhum job periódico de expurgo existe ainda** para as categorias
   armazenadas em PostgreSQL (cadastro, observações, resultados,
   rascunhos) — hoje a exclusão seria manual. ADR 0015 já antecipa "um job
   periódico aplicará a tabela de retenção e registrará evidência de
   exclusão como evento de auditoria"; esse job **não está implementado**
   neste MVP.
2. Exclusão do objeto S3 *corrente* (não apenas versões antigas) para
   mídias/relatórios ainda depende de operação manual — o lifecycle
   configurado cobre apenas versões não-correntes e uploads incompletos.
3. A exclusão precisa considerar todos os locais listados na seção 8.3 do
   escopo (PostgreSQL, versões do S3, caches, índices, filas, backups e
   fornecedores) — este MVP cobre PostgreSQL e S3; caches/índices
   adicionais não existem hoje (sem camada de cache), e a exclusão do lado
   do fornecedor OpenAI depende do contrato (`store=False` reduz a
   superfície, mas não elimina a necessidade de confirmação contratual).
4. Prazos numéricos definitivos para cada categoria continuam
   **PENDENTE DE APROVAÇÃO** pelo responsável de privacidade/jurídico,
   conforme já registrado no ADR 0015.
