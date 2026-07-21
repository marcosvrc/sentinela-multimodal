# ADR 0005: Orquestrador Python proprio com SQS (sem Step Functions/Celery no MVP)

**Status:** Aceito
**Data:** 2026-07-11

## Contexto

O pipeline multimodal precisa coordenar processadores independentes por
modalidade, com estados por modalidade e consolidacao final. Ferramentas
gerenciadas (Step Functions) ou frameworks de fila (Celery) adicionam
dependencias e curva de aprendizado que nao se justificam no volume do MVP.

## Decisao

Implementar um orquestrador Python proprio sobre SQS e workers Fargate,
responsavel por: dispatch de processadores por modalidade, gravacao de
resultados estruturados, deteccao de estado terminal e transicao da
maquina de estados da analise.

## Alternativas consideradas

- AWS Step Functions: rejeitado no MVP pelo custo de aprendizado e pela
  necessidade de modelar o dominio em ASL antes de estabilizar o fluxo;
  permanece candidato para evolucao futura.
- Celery com broker Redis/RabbitMQ: rejeitado por introduzir um componente
  de infraestrutura adicional quando SQS ja atende ao desacoplamento
  necessario.

## Consequencias

- O orquestrador propaga request_id, analysis_id, workflow_id e job_id em
  toda a cadeia de processamento.
- Uma futura migracao para Step Functions e possivel sem alterar os
  contratos de dominio, pois a interface `WorkflowOrchestrator` isola a
  implementacao.
