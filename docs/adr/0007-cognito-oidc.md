# ADR 0007: Amazon Cognito como provedor OIDC

**Status:** Superado (ver nota abaixo)
**Data:** 2026-07-11

> **Atualizacao (2026-07-21):** o projeto passou a usar exclusivamente
> Azure como nuvem gerenciada, removendo toda a infraestrutura e
> adaptadores AWS (incluindo Cognito). Autenticacao real gerenciada
> (senha/MFA/token) ficou fora do escopo do MVP; o unico adaptador de
> identidade hoje e o local (cabecalho `X-Dev-Subject`, dev/testes). Um
> provedor de identidade gerenciado real (ex.: Microsoft Entra ID) fica
> registrado como evolucao futura. Registro historico da decisao
> original.

## Contexto

O sistema exige autenticacao forte, MFA obrigatorio, controle de sessao e
integracao gerenciada, sem que a equipe precise operar sua propria infra de
identidade.

## Decisao

Amazon Cognito, em User Pool exclusivo do projeto, e o provedor OIDC de
producao. Ambientes de desenvolvimento e testes automatizados podem usar
um User Pool de desenvolvimento ou um adaptador local controlado, isolado
por configuracao.

## Alternativas consideradas

- Identity provider proprio (Keycloak self-hosted): rejeitado por adicionar
  operacao de infraestrutura sensivel (identidade) sem necessidade
  demonstrada frente ao Cognito gerenciado.
- Auth0/outros IdPs de terceiros: nao descartados no roadmap, mas fora do
  MVP por já haver adocao de AWS como nuvem principal.

## Consequencias

- O frontend nunca recebe credenciais IAM; apenas tokens OIDC de curta
  duracao.
- A troca futura de provedor de identidade fica isolada atras da interface
  `Identity_Service`.
