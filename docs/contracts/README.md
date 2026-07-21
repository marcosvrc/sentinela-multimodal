# Contratos do SentinelHealth

Este diretorio guarda os contratos versionados consumidos por backend e
frontend, conforme o gate de inicio de desenvolvimento
(`ESCOPO_PROJETO.md`, secao 12.1.4).

## Arquivos

- `openapi.json` — snapshot do contrato HTTP da API, gerado por
  `make export-openapi` (`backend/scripts/export_openapi.py`). Comparar o
  diff deste arquivo no pull request e a forma primaria de revisar mudancas
  de contrato.
- `../adr/` — decisoes arquiteturais relacionadas aos contratos (ex: ADR
  0011 sobre o formato das regras clinicas).

## Enums compartilhados

Os enums de dominio (estado da analise, estado por modalidade, qualidade,
natureza do achado, decisao de revisao, acoes disponiveis) tem fonte unica
em `backend/app/core/enums.py`. O frontend nunca redefine esses valores
manualmente: `make codegen` gera
`frontend/src/types/enums.generated.ts` a partir do Python.

Fluxo:

```text
backend/app/core/enums.py  (fonte unica)
        |
        v
backend/scripts/export_enums.py
        |
        v
frontend/src/types/enums.generated.ts  (gerado, nao editar manualmente)
```

## Padrao de erro e paginacao

Definidos em `backend/app/api/schemas/common.py`
(`ErrorResponse`, `PageParams`, `PageResponse`) e usados por todos os
endpoints. Ver tambem `ESPECIFICACAO_FRONTEND.md` secao 9 para os exemplos
de JSON que o frontend espera.

## Politica de versionamento e compatibilidade

- Mudancas aditivas (novo campo opcional, novo enum member, novo endpoint)
  nao exigem nova versao maior da API e devem manter compatibilidade com
  clientes existentes.
- Mudancas que removem ou renomeiam campos, alteram o significado de um
  enum existente, ou tornam um campo opcional em obrigatorio sao mudancas
  quebradoras (*breaking*): exigem versionamento explicito do contrato
  (ex: prefixo `/v2`), comunicacao previa e periodo de convivencia entre
  versoes quando houver clientes externos.
- Todo pull request que altera `app/api/schemas/`, `app/core/enums.py` ou
  rotas publicas deve regenerar `openapi.json` e `enums.generated.ts`
  (`make codegen && make export-openapi`) e commitar o diff resultante.
- Enums de estado (`AnalysisStatus`, `ModalityStatus` etc.) sao aditivos
  por padrao: novos estados podem ser adicionados, mas um estado existente
  nunca muda de significado sem ADR e avaliacao de impacto (ver
  `ESCOPO_PROJETO.md` secao 9 — mudancas em modelo/regra exigem avaliacao
  de impacto, validacao, aprovacao e rollback).
- O campo `available_actions` e sempre a fonte de verdade das transicoes
  permitidas; o frontend nunca deduz transicoes por conta propria
  (`ANALYSIS_STATUS_TRANSITIONS` no backend e espelhado no arquivo gerado
  apenas para exibicao/depuracao, nao para decisao de UI).
