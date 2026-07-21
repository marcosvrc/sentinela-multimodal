# ADR 0014: Estrategia de auditoria imutavel

**Status:** Aceito
**Data:** 2026-07-11

## Contexto

O sistema precisa de uma trilha de auditoria completa, integra e resistente
a adulteracao, cobrindo autenticacao, autorizacao, dados, arquivos,
administracao, analise, IA e revisao (secao 6.14 do escopo).

## Decisao

O registro transacional append-only no PostgreSQL e a primeira camada,
protegido por um mecanismo de integridade encadeada (hash chaining).
Eventos sao exportados de forma assincrona para armazenamento
separado e imutavel (WORM), com retencao propria, controle de acesso
distinto e reconciliacao periodica. Falha na exportacao gera alerta
operacional e nao bloqueia a operacao de negocio, mas o evento permanece
retido ate exportacao bem-sucedida. Falha no registro primario, por outro
lado, bloqueia a operacao que o originou.

## Alternativas consideradas

- Apenas logs de aplicacao (CloudWatch) sem tabela transacional dedicada:
  rejeitado por nao garantir integridade referencial com as entidades de
  dominio nem busca estruturada eficiente.
- Exportacao sincrona para o armazenamento imutavel: rejeitado por
  acoplar a latencia de cada operacao de negocio a disponibilidade do
  armazenamento externo.

## Consequencias

- Toda escrita relevante do dominio gera um evento de auditoria antes de
  ser considerada concluida.
- Consultas e exportacoes da propria auditoria tambem sao auditadas.
