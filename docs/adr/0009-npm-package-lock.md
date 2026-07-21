# ADR 0009: npm com package-lock.json para dependencias Node.js

**Status:** Aceito
**Data:** 2026-07-11

## Contexto

O frontend React + TypeScript + Vite precisa de um gerenciador de pacotes
padrao, amplamente suportado pelo ecossistema de CI/CD e sem necessidade de
ferramentas adicionais.

## Decisao

Usar `npm` com `package-lock.json` versionado como unico gerenciador de
dependencias do frontend, com `npm ci` no CI/CD para instalacao
reprodutivel.

## Alternativas consideradas

- pnpm: rejeitado no MVP por adicionar uma ferramenta extra sem necessidade
  comprovada de economia de espaco/tempo no volume atual de dependencias.
- yarn: rejeitado pelo mesmo motivo; `npm` ja vem com o Node.js.

## Consequencias

- `package-lock.json` e a fonte de verdade das versoes instaladas e deve
  ser commitado.
- O CI usa `npm ci`, nunca `npm install`, para garantir reprodutibilidade.
