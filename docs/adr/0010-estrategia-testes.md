# ADR 0010: Estrategia de testes locais e de contrato com AWS

**Status:** Aceito
**Data:** 2026-07-11

## Contexto

O dominio nao deve depender diretamente de SDKs da AWS/OpenAI, mas o
comportamento real desses fornecedores precisa ser validado antes da
producao, sem exigir credenciais AWS reais para rodar a suite de testes
padrao.

## Decisao

Testes unitarios e de integracao padrao rodam contra adaptadores locais
(filesystem para S3, fila in-memory para SQS, adaptador local para
identidade). Testes de contrato separados (marcados e executados
opcionalmente) validam o comportamento real de S3, SQS, Cognito e
Transcribe em uma conta AWS de desenvolvimento, quando credenciais
estiverem disponiveis.

## Alternativas consideradas

- Mockar todas as chamadas AWS sem testes de contrato: rejeitado por
  correr o risco de os adaptadores locais divergirem do comportamento real
  dos servicos gerenciados.
- Exigir credenciais AWS para toda a suite de testes: rejeitado por
  inviabilizar execucao local e no CI sem acesso a conta AWS.

## Consequencias

- `make test` roda localmente sem AWS. `make test-integration` roda os
  testes de contrato quando aplicavel.
- Os adaptadores implementam a mesma interface de dominio, garantindo que
  o codigo testado localmente seja o mesmo executado em producao.
