# ADR 0002: PostgreSQL como fonte de verdade; sem MongoDB no MVP

**Status:** Aceito
**Data:** 2026-07-11

## Contexto

O dominio clinico exige transacoes ACID, integridade referencial, Row-Level
Security para isolamento multi-tenant e auditoria append-only consistente.
Os dados estruturados (pacientes, observacoes, analises, achados, regras,
auditoria) sao majoritariamente relacionais.

## Decisao

PostgreSQL e a fonte de verdade transacional de todo o dominio. MongoDB nao
sera adotado no MVP; sua introducao futura exigira necessidade comprovada
que o PostgreSQL e o S3 nao atendam.

## Alternativas consideradas

- MongoDB para resultados semi-estruturados de modelos: rejeitado no MVP
  porque adicionaria uma segunda fonte de verdade sem necessidade
  demonstrada, complicando transacoes e auditoria.
- Banco poliglota desde o inicio: rejeitado por aumentar a superficie
  operacional sem beneficio validado.

## Consequencias

- Resultados semi-estruturados de modelos (JSON de achados, evidencias)
  sao armazenados em colunas JSONB do PostgreSQL, mantendo uma unica fonte
  de verdade transacional.
- Migrations Alembic sao o unico mecanismo de evolucao de schema.
