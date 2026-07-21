# Ambiente local

O ambiente local **nao usa Terraform** por padrao. Todos os componentes de
infra (Postgres, fila, storage compativel com S3 e o adaptador de
identidade local) sao provisionados via `docker-compose.yml`/`compose.yaml`
na raiz do repositorio, conforme decidido no item 5 do backlog (adaptadores
local vs. AWS).

Este diretorio existe apenas para manter a simetria com
`environments/homologation` e `environments/production` e para documentar
essa decisao explicitamente - nao ha `.tf` aqui de proposito.

Para subir o ambiente local, veja o `README.md` da raiz do projeto e o
`compose.yaml`.

## Variante: local conectado a servicos AWS reais

Se voce quer rodar a API/worker localmente (mesmo `compose.yaml`) mas usar
**S3, SQS e Amazon Transcribe reais** em vez dos adaptadores `LOCAL` (por
exemplo, para testar a integracao de verdade com Transcribe antes de fazer
deploy em homologacao), use o ambiente `environments/dev` - ver
`infra/environments/dev/README.md`. Ele so provisiona os recursos AWS
minimos (bucket S3, filas SQS, chave KMS); Postgres, API e workers
continuam rodando localmente via `compose.yaml`.
