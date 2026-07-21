# ADR 0011: Formato, versionamento e publicacao das regras clinicas

**Status:** Aceito
**Data:** 2026-07-11

## Contexto

`CLASSIFICACAO_DADOS_CLINICOS.md` e uma referencia legivel por humanos, mas
a aplicacao nao pode interpretar Markdown diretamente nem tratar o
documento inteiro como uma unica regra textual (secao 12.1.6 do escopo).

## Decisao

Regras operacionais sao representadas em arquivos YAML estruturados
(`backend/clinical_rules/seeds/*.yaml`), validados contra um JSON Schema
(`clinical_rule_set.schema.json`) e carregados de forma idempotente no
PostgreSQL em entidades versionadas (`clinical_rule_sets`,
`clinical_rules` e tabelas relacionadas). Publicacoes criam nova versao
imutavel; nunca sobrescrevem regras ja utilizadas em analises anteriores.

## Alternativas consideradas

- Interpretar o Markdown diretamente em runtime: rejeitado por fragilidade
  de parsing e ausencia de validacao formal antes da publicacao.
- Regras hardcoded no codigo Python: rejeitado por dificultar versionamento
  independente, aprovacao clinica e rollback.

## Consequencias

- `make rules-validate` e `make rules-seed` sao os comandos oficiais do
  fluxo Documento -> YAML -> validacao -> seed -> PostgreSQL -> publicacao.
- O LLM nunca converte Markdown em regra publicavel automaticamente.
