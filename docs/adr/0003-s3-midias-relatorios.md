# ADR 0003: S3 para midias, artefatos e relatorios

**Status:** Aceito
**Data:** 2026-07-11

## Contexto

Audio, video, imagem e PDFs sao arquivos binarios grandes. Armazena-los no
PostgreSQL degradaria performance, backups e replicacao.

## Decisao

Amazon S3 armazena originais, derivados, evidencias (frames selecionados) e
relatorios PDF, com criptografia, versionamento e politica de ciclo de
vida. O PostgreSQL guarda apenas identificador, chave do objeto, hash,
tamanho, MIME, estado e metadados. Upload/download ocorrem via URLs
pre-assinadas de curta duracao, sem o backend atuar como intermediario de
arquivos grandes.

## Alternativas consideradas

- Armazenar binarios no PostgreSQL (bytea/large object): rejeitado por
  impacto em performance, backup e custo.
- Filesystem compartilhado (EFS) como fonte de verdade: rejeitado por nao
  oferecer o mesmo nivel de controle de acesso granular e ciclo de vida
  que o S3 oferece nativamente.

## Consequencias

- Chaves de objeto sao unicas e prefixadas por tenant_id, nunca reutilizadas.
- Adaptador local de filesystem substitui o S3 apenas em desenvolvimento e
  testes, atras da interface `ObjectStorage`.
