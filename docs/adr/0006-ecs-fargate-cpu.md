# ADR 0006: ECS Fargate para API/workers; visao computacional em CPU no MVP

**Status:** Parcialmente superado (ver nota abaixo)
**Data:** 2026-07-11

> **Atualizacao (2026-07-21):** o projeto passou a usar exclusivamente
> Azure como nuvem gerenciada, removendo toda a infraestrutura AWS
> (incluindo ECS Fargate). O MVP roda em Docker Compose local; a decisao
> de manter a visao computacional (OpenPose/YOLO) em CPU sobre amostras
> pequenas, sem GPU no MVP, permanece valida e inalterada. Uma eventual
> plataforma de containers gerenciada (ex.: Azure Container Apps) e
> avaliacao futura, fora do escopo obrigatorio.

## Contexto

O MVP precisa de containers gerenciados sem a complexidade operacional de
um cluster Kubernetes. OpenPose/YOLO se beneficiam de GPU, mas a validacao
inicial do fluxo nao depende de desempenho de producao.

## Decisao

API e workers CPU executam em ECS Fargate. O worker de visao computacional
roda OpenPose/YOLO em CPU sobre amostras pequenas de demonstracao,
explicitamente marcado como nao produtivo em desempenho. GPU gerenciada
(ECS sobre EC2 com GPU) fica fora da entrega obrigatoria do MVP.

## Alternativas consideradas

- Kubernetes (EKS): rejeitado por complexidade operacional desproporcional
  ao estagio do projeto.
- GPU desde o MVP: rejeitado por custo e por nao ser necessario para
  demonstrar o fluxo funcional com amostras pequenas.

## Consequencias

- A imagem do worker de visao e separada da imagem dos workers CPU.
- A migracao para GPU e um trabalho de infraestrutura isolado, sem impacto
  no contrato do processador de modalidade de video.
