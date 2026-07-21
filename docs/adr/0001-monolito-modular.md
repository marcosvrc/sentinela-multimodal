# ADR 0001: Monolito modular no MVP

**Status:** Aceito
**Data:** 2026-07-11

## Contexto

O MVP precisa entregar analise multimodal, regras clinicas, consolidacao e
auditoria em prazo limitado, sem o custo operacional de coordenar dezenas
de servicos desde o inicio. A equipe e pequena e a carga de producao ainda
e desconhecida.

## Decisao

Adotar um monolito modular: modulos de dominio isolados por responsabilidade
(pacientes, identidade, midias, trabalhos de analise, orquestrador,
processadores de modalidade, motor de regras, consolidador, relatorios,
revisao, auditoria), compartilhando o mesmo codigo-base mas executados como
processos/imagens independentes (API vs workers) quando o perfil de carga
justificar.

## Alternativas consideradas

- Microservicos desde o inicio: rejeitado por aumentar complexidade
  operacional (deploy, observabilidade, contratos entre servicos) sem
  beneficio claro no volume esperado do MVP.
- Monolito unico sem separacao de modulos: rejeitado por dificultar a
  evolucao futura para servicos independentes quando necessario.

## Consequencias

- Limites de modulo devem ser respeitados no codigo (sem imports cruzados
  de infraestrutura entre dominios) para permitir extracao futura.
- API e workers podem escalar independentemente mesmo compartilhando
  codigo-base, pois sao implantados como imagens/processos separados.
