# ADR 0008: uv com pyproject.toml para dependencias Python

**Status:** Aceito
**Data:** 2026-07-11

## Contexto

O backend e os workers precisam de resolucao de dependencias reprodutivel,
rapida e com lockfile, tanto localmente quanto no CI/CD e nas imagens
Docker.

## Decisao

Usar `uv` com `pyproject.toml` e lockfile (`uv.lock`) como unico mecanismo
de gestao de dependencias Python, tanto para desenvolvimento quanto para
build de imagem.

## Alternativas consideradas

- pip + requirements.txt: rejeitado por lockfile menos robusto e resolucao
  mais lenta.
- Poetry: rejeitado por velocidade inferior ao uv e por adicionar uma
  ferramenta extra quando uv cobre o mesmo escopo com melhor desempenho.

## Consequencias

- `make setup`, Dockerfiles e o workflow de CI usam `uv sync` de forma
  consistente.
- Dependencias tem versoes fixadas via lockfile, reduzindo builds nao
  reprodutiveis.
