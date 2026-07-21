# ADR 0013: Versao/perfis FHIR como roadmap, fora do primeiro MVP

**Status:** Proposto (roadmap)
**Data:** 2026-07-11

## Contexto

Interoperabilidade com prontuarios hospitalares via HL7 FHIR e um objetivo
de longo prazo, mas exige definicoes (versao FHIR, perfis, terminologias,
identificadores institucionais, provenance) que nao sao necessarias para
demonstrar o fluxo do MVP.

## Decisao

FHIR permanece apenas no roadmap. O modelo interno de dominio nao depende
diretamente das classes de nenhuma biblioteca FHIR, preservando a
possibilidade de mapear entidades internas para recursos FHIR
(`Patient`, `Observation`, `DiagnosticReport` etc.) no futuro sem
retrabalho estrutural.

## Alternativas consideradas

- Adotar bibliotecas FHIR como modelo de dominio desde o inicio: rejeitado
  por acoplar o dominio a uma especificacao externa antes de haver decisao
  sobre versao, perfis e parceiro de integracao.

## Consequencias

- Antes de implementar a integracao, deverao ser definidos versao FHIR,
  perfis, terminologias, autorizacao, auditoria e tratamento de erros.
- Este ADR sera substituido por um novo ADR quando a integracao entrar em
  desenvolvimento.
