# Relatório de Impacto à Proteção de Dados Pessoais (RIPD) — Esqueleto

> ESCOPO_PROJETO.md seção 8.7: "O RIPD será concluído antes de dados reais
> e revisto quando houver nova modalidade, fornecedor, país, finalidade,
> população, integração, decisão automatizada ou mudança relevante de
> risco." Este documento é o esqueleto estrutural com as seções exigidas,
> **não** o RIPD aprovado — a análise de risco/mitigação/aceitação é
> **PENDENTE DE APROVAÇÃO** por privacidade/jurídico/clínico/engenharia em
> conjunto (seção 8.7: "Segurança, privacidade, jurídico, equipe clínica e
> engenharia participarão das decisões de alto risco").

## 1. Descrição do tratamento

Sistema de apoio à decisão clínica que recebe texto adicional e mídia
(áudio/imagem/vídeo) associada a um paciente, aplica um motor de regras
clínicas determinístico e versionado sobre entradas estruturadas, e usa um
LLM (OpenAI) apenas para gerar um resumo textual explicativo de um risco
já calculado — nunca para decidir o risco. Ver
`docs/governance/INVENTARIO_TRATAMENTO.md` para o detalhamento por
operação.

## 2. Necessidade e proporcionalidade

**PENDENTE DE APROVAÇÃO.** Deve demonstrar que os dados coletados são o
mínimo necessário para a finalidade (o sistema já minimiza estruturalmente
o que chega ao LLM — ver `LlmSummaryRequest` — mas a necessidade de cada
categoria de dado coletada do paciente ainda exige justificativa formal).

## 3. Identificação e avaliação de riscos

| Risco | Fonte | Mitigação técnica existente | Risco residual |
| --- | --- | --- | --- |
| Vazamento de dado de saúde por falha de isolamento multi-tenant | Bug de aplicação | `institution_id` sempre derivado do servidor, nunca do cliente (`app.core.security`); testado em `test_integration_end_to_end.py` e em cada `test_*_api.py` | **PENDENTE avaliação** |
| Exfiltração de dado clínico via LLM | Prompt injection, campo mal minimizado | Allowlist rígida (`LlmSummaryRequest`), teste de guarda de schema, teste de fluxo completo com conteúdo adversarial (`test_prompt_injection_security.py`) | **PENDENTE avaliação** |
| Alteração indevida de nível de risco por manipulação do LLM | Resposta do LLM malformada/manipulada | `LlmSummaryResult` não tem nenhum campo capaz de carregar risco; risco vem sempre do motor determinístico | **PENDENTE avaliação** |
| Adulteração da trilha de auditoria | Acesso privilegiado indevido ao banco | Cadeia de hash encadeada, tabela append-only (sem UPDATE/DELETE), `verify_chain` | **PENDENTE avaliação** |
| Exposição de mídia por bucket mal configurado | Erro de infraestrutura | Bloqueio de acesso público por padrão, criptografia KMS, URLs pré-assinadas com TTL (`infra/modules/storage`) | **PENDENTE avaliação** |
| Retenção indevidamente longa de dado sensível | Ausência de job de expurgo automático | Ver `TABELA_RETENCAO.md` — lacuna conhecida, sem mitigação completa ainda | **Risco identificado, não mitigado** |
| Reidentificação de paciente a partir de voz/rosto | Dado biométrico | Nenhuma mitigação de anonimização real implementada (dado tratado como pessoal sensível por padrão, não anonimizado) | **Risco aceito por design — dado tratado como sensível, não uma mitigação de exposição** |
| Viés/degradação de desempenho por subgrupo | Modelo/regra não validada para população específica | Regras fixadas em população "adulto" (MVP), exclusões documentadas por regra (`CLASSIFICACAO_DADOS_CLINICOS.md` seção 14) | **PENDENTE validação clínica formal** |

## 4. Medidas de mitigação planejadas vs. implementadas

| Medida | Status |
| --- | --- |
| Minimização de dados enviados ao LLM | Implementada |
| Isolamento multi-tenant | Implementada, testada |
| Trilha de auditoria imutável | Implementada, testada |
| Criptografia em trânsito/repouso | Implementada (infra) |
| Job de expurgo automático por retenção | **Não implementada** |
| Pseudonimização de identificadores antes de envio a modelos | **Não implementada** (LLM já recebe apenas dados minimizados sem identificação, mas não há pseudonimização formal de tabela de correspondência separada) |
| RIPD revisado e aprovado | **Não concluído** (este documento) |
| Avaliação de fornecedores (DPA, SCC, região) | **Não concluída** |
| SAST/SCA/DAST/pentest | **Não instrumentado em CI neste MVP** |

## 5. Aprovação

| Papel | Nome | Data | Assinatura |
| --- | --- | --- | --- |
| Encarregado (DPO) | **PENDENTE** | — | — |
| Responsável clínico | **PENDENTE** | — | — |
| Responsável de segurança | **PENDENTE** | — | — |
| Controlador | **PENDENTE** | — | — |

Este RIPD deve ser revisto na próxima mudança relevante de risco, nova
modalidade, fornecedor, país, finalidade, população, integração ou decisão
automatizada (seção 8.7 do escopo).
