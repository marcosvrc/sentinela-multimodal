# ADR 0015: Politica de retencao e exclusao de midias/derivados

**Status:** Aceito
**Data:** 2026-07-11

## Contexto

Midias originais, derivados, transcricoes, prompts/respostas, relatorios e
backups acumulam dados pessoais sensiveis de saude. A LGPD exige prazos de
retencao definidos e exclusao efetiva, nao apenas logica (secao 8.3 do
escopo).

## Decisao

Cada categoria de dado (cadastro, observacoes, midias originais, derivados,
transcricao, resultados, prompt/resposta, rascunhos, relatorios, auditoria,
logs, backups, quarentena, uploads incompletos, DLQ) tera uma regra de
retencao com prazo, fundamento, evento inicial, responsavel, metodo de
exclusao, excecoes e evidencia de execucao. A exclusao considera
PostgreSQL, versoes do S3, caches, indices, filas, backups e fornecedores.

## Alternativas consideradas

- Exclusao logica (soft delete) como unico mecanismo: rejeitado porque a
  LGPD e o escopo do projeto exigem exclusao efetiva, nao apenas ocultacao
  do registro.
- Retencao indefinida por padrao: rejeitado por violar o principio de
  minimizacao e aumentar a superficie de risco em caso de incidente.

## Consequencias

- Um job periodico aplicara a tabela de retencao e registrara evidencia de
  exclusao como evento de auditoria.
- A tabela de retencao definitiva sera aprovada antes do uso com dados
  reais (gate 12.2 do escopo).
