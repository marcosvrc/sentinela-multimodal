# ADR 0012: Estrategia multi-tenant com Row-Level Security

**Status:** Aceito
**Data:** 2026-07-11

## Contexto

Multiplas instituicoes (hospitais) compartilham a mesma aplicacao. O
isolamento entre instituicoes e um requisito de seguranca critico (secao
6.5 e 16 do escopo) e nao pode depender apenas de filtros aplicados na
camada de aplicacao.

## Decisao

`tenant_id` e derivado exclusivamente da identidade autenticada, nunca
aceito do frontend. PostgreSQL Row-Level Security (ou mecanismo
equivalente) e aplicado em todas as entidades, jobs, objetos e eventos
sujeitos a segregacao. Identificadores externos usam UUIDs nao
previsiveis.

## Alternativas consideradas

- Isolamento apenas por filtro `WHERE tenant_id = :tenant` na aplicacao:
  rejeitado por depender de disciplina de codigo em cada query, sem
  garantia estrutural contra erro humano.
- Banco de dados separado por instituicao: nao descartado como evolucao
  futura para instituicoes de grande porte, mas fora do MVP pelo custo
  operacional.

## Consequencias

- Toda migration que cria tabela sujeita a tenant deve habilitar RLS e
  policy correspondente.
- Testes automatizados tentam acessar recursos de outra instituicao como
  parte do gate de aceite (secao 12 do escopo).
