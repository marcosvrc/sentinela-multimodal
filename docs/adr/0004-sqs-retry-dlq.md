# ADR 0004: Amazon SQS com estrategia de retry e DLQ

**Status:** Aceito
**Data:** 2026-07-11

## Contexto

O processamento multimodal e assincrono e sujeito a falhas transitorias
(timeout, rate limit, indisponibilidade de fornecedor). A API nao pode
aguardar o processamento pesado dentro do ciclo HTTP.

## Decisao

Amazon SQS desacopla a API dos workers. Cada fila principal possui uma
Dead Letter Queue (DLQ) associada. Falhas transitorias sao reenfileiradas
com backoff exponencial ate um limite de tentativas; falhas permanentes
vao para FAILED_FINAL sem consumir a DLQ. Mensagens transportam apenas
identificadores e metadados minimos.

## Alternativas consideradas

- Processamento sincrono na requisicao HTTP: rejeitado por violar o
  requisito de resposta rapida da API e nao permitir retry controlado.
- Fila unica sem DLQ: rejeitado por nao permitir diagnostico e
  reprocessamento seguro de falhas esgotadas.

## Consequencias

- Cada adaptador externo implementa timeout, retry com backoff e
  idempotencia (ver secao 6.8 do ESCOPO_PROJETO.md).
- Reprocessamento a partir da DLQ deve ser idempotente e nao duplicar
  resultados definitivos.
