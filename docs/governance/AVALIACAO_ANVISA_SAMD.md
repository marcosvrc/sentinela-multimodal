# Avaliação Preliminar — Software como Dispositivo Médico (Anvisa)

> ESCOPO_PROJETO.md seção 9: "Avaliar formalmente o enquadramento como
> Software como Dispositivo Médico segundo a regulamentação vigente da
> Anvisa, antes de uso assistencial." Esta é uma avaliação **preliminar e
> técnica**, não a avaliação regulatória formal — que exige responsável
> técnico habilitado e, dependendo do enquadramento, submissão à Anvisa
> (RDC nº 657/2022). **Nenhuma conclusão aqui autoriza uso assistencial
> real.**

## 1. Propósito pretendido (a validar formalmente)

Apoiar profissionais de saúde (médico/enfermeiro) na triagem de risco
clínico a partir de sinais vitais estruturados e evidências multimodais
(texto, áudio, imagem, vídeo), produzindo uma classificação de risco
determinística e um resumo explicativo — **não** um diagnóstico, prescrição
ou conduta automática.

## 2. Usuário, população e ambiente pretendidos

| Campo | Valor atual do MVP |
| --- | --- |
| Usuário | Profissional de saúde (papéis `MEDICO`, `ENFERMEIRO`) — nunca o paciente diretamente |
| População | Adulto (fixado no MVP; `CLASSIFICACAO_DADOS_CLINICOS.md` seção "Contexto Mínimo": "Adulto no MVP; exceções exigem protocolo próprio") |
| Ambiente | Assistencial hospitalar/institucional (não definido com mais granularidade neste MVP) |

## 3. Indicações, contraindicações e limitações conhecidas

- **Indicação pretendida:** apoio à triagem/priorização de risco, sujeito a
  revisão humana obrigatória antes de qualquer laudo definitivo (a
  confirmação de laudo, `app.reports.service.confirm_report`, sempre exige
  ação humana explícita de um papel clínico).
- **Contraindicações/limitações já documentadas no domínio clínico**
  (`CLASSIFICACAO_DADOS_CLINICOS.md`):
  - Não substitui diagnóstico, prescrição ou conduta automática.
  - Não válido para gestantes/pediatria nas tabelas atuais (fora de
    escopo, exigem protocolo próprio).
  - Módulo de análise cirúrgica é "experimental" e não deve ser usado para
    atribuir culpa/erro médico.
  - Análise facial não confirma dor/sedação/confusão/estresse
    isoladamente; identificação biométrica está fora do escopo.
  - Achados de movimento/postura (OpenPose/YOLO) não diagnosticam lesão ou
    déficit neurológico.
  - Resultados "inconclusivo" nunca podem ser convertidos automaticamente
    em baixo risco.

## 4. Indícios técnicos relevantes para o enquadramento (não uma conclusão regulatória)

| Fator | Observação técnica |
| --- | --- |
| Decisão automatizada de risco | Existe (`app.risk_consolidation`), mas por motor de regras determinístico e versionado, não por modelo estatístico opaco — a rastreabilidade da regra aplicada é completa (`code_evaluations`, `matched_rule_codes`) |
| Uso de IA/LLM | Restrito a texto explicativo, sem capacidade estrutural de alterar o risco (`LlmSummaryResult` sem campo de risco) — relevante para diferenciar "IA auxilia explicação" de "IA decide conduta" |
| Revisão humana obrigatória | Sim — nenhum laudo é considerado definitivo sem confirmação humana explícita; PDF só existe após essa confirmação |
| Reconhecimento de conteúdo real por IA (ASR, visão computacional) | **Não implementado neste MVP** — processadores de áudio/imagem/vídeo (item 11) fazem apenas avaliação determinística de qualidade (duração, resolução), não extraem achados clínicos reais. Isso significa que a análise/hipótese assistida por IA descrita na seção 5.6 do escopo permanece **vazia por padrão** (`model_observations: []`, `assisted_hypotheses: []`) — não há, hoje, uma funcionalidade de "IA analisa a mídia e sugere achado" em produção |
| Rastreabilidade de versão de regra | Cada `ClinicalRuleSet` tem versão, hash de conteúdo, vigência e nunca é sobrescrita |

## 5. Plano de gerenciamento de risco, validação clínica e vigilância pós-implantação

**PENDENTE DE ELABORAÇÃO FORMAL.** O escopo (seção 9) exige que o sistema
mantenha esses três planos compatíveis com seu enquadramento regulatório
final — nenhum dos três está formalizado neste MVP. Pré-requisitos
técnicos já existentes que servirão de insumo:

- Auditoria completa e imutável como base para vigilância pós-implantação
  (permite reconstruir quem viu/confirmou cada laudo e quando).
- Versionamento de regra clínica como base para gerenciamento de mudança
  (nenhuma mudança de regra é silenciosa ou retroativa).
- Ausência de reconhecimento de conteúdo real por IA reduz, por ora, a
  superfície de risco associada a "falso achado gerado por IA" — mas isso
  também significa que qualquer expansão futura para essa capacidade
  reabre a necessidade de reavaliação regulatória completa (gatilho já
  previsto na seção 8.7 do RIPD).

## 6. Conclusão preliminar

**Este MVP ainda não deve ser usado para assistência real a pacientes.**
O enquadramento formal como Software como Dispositivo Médico (ou não)
segundo a RDC nº 657/2022 exige responsável técnico habilitado, avaliação
de risco formal (ISO 14971 ou equivalente) e, dependendo do resultado,
processo de registro/notificação junto à Anvisa antes de uso assistencial.
Nada neste repositório substitui essa avaliação.

## 7. Aprovação

| Papel | Nome | Data | Conclusão |
| --- | --- | --- | --- |
| Responsável técnico habilitado | **PENDENTE** | — | — |
| Responsável clínico | **PENDENTE** | — | — |
