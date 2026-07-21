# Governança LGPD e Regulatória (Anvisa) — SentinelHealth

Este diretório reúne os artefatos de governança de privacidade e
regulatórios exigidos pela ESCOPO_PROJETO.md seções 8 e 9, produzidos como
parte do item 16 do backlog de implementação.

## O que existe aqui e o que ainda depende de aprovação humana

Cada documento abaixo mistura dois tipos de conteúdo, sempre identificados
explicitamente dentro do próprio arquivo:

1. **Fatos técnicos verificáveis no código** (ex.: quais tabelas existem,
   que criptografia é usada, quais eventos de auditoria são gerados, quais
   integrações externas o sistema já faz). Esses trechos foram derivados
   diretamente da implementação e dos ADRs — não são suposições.
2. **Decisões, prazos, avaliações de risco e aprovações que exigem
   julgamento jurídico, clínico ou de negócio** (base legal por operação,
   prazos de retenção definitivos, classificação regulatória Anvisa,
   aceitação de risco residual). Esses campos estão marcados como
   **PENDENTE DE APROVAÇÃO** — preencher um valor aqui sem a revisão
   correspondente (jurídico/DPO/encarregado, equipe clínica, segurança)
   seria fabricar uma aprovação que não existe, o que o projeto trata como
   inaceitável (mesmo princípio de "nunca fingir" já aplicado ao restante
   do sistema — ex.: seções 6 e 7 do laudo clínico permanecem vazias
   enquanto não houver reconhecimento de conteúdo real por IA).

Nenhum documento aqui autoriza o uso do sistema com dados reais de
pacientes. Isso só pode ocorrer após as aprovações pendentes serem obtidas
(ESCOPO_PROJETO.md seção 8: "Antes de usar dados reais...").

## Índice

| Documento | Cobre |
| --- | --- |
| [INVENTARIO_TRATAMENTO.md](./INVENTARIO_TRATAMENTO.md) | Registro das operações de tratamento (LGPD art. 37) |
| [TABELA_RETENCAO.md](./TABELA_RETENCAO.md) | Prazos de retenção/exclusão por categoria de dado (ADR 0015) |
| [PLANO_RESPOSTA_INCIDENTES.md](./PLANO_RESPOSTA_INCIDENTES.md) | Classificação, papéis e playbooks mínimos de incidente |
| [RIPD.md](./RIPD.md) | Esqueleto do Relatório de Impacto à Proteção de Dados |
| [AVALIACAO_ANVISA_SAMD.md](./AVALIACAO_ANVISA_SAMD.md) | Avaliação preliminar de enquadramento como Software como Dispositivo Médico |

## Testes de segurança e integração relacionados

A parte tecnicamente verificável desta governança (isolamento
multi-tenant, RBAC, resistência a prompt injection, integridade da cadeia
de auditoria) é validada por testes automatizados, não apenas descrita em
prosa:

- `backend/tests/test_integration_end_to_end.py` — fluxo clínico completo
  ponta a ponta, isolamento entre instituições e RBAC (`@pytest.mark.integration`).
- `backend/tests/test_prompt_injection_security.py` — conteúdo adversarial
  em `additional_text` nunca altera o risco calculado nem escapa para o
  payload do LLM.
- `backend/tests/test_audit_hashing.py` — detecção de adulteração na
  cadeia de auditoria.
- Demais arquivos `test_*_api.py` — isolamento e RBAC por módulo (paciente,
  mídia, regras, auditoria, relatório).
- `backend/scripts/load_test.py` — instrumento inicial de teste de carga
  (`make load-test`).
