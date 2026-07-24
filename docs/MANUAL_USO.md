# Manual de Uso — SentinelHealth

Guia de uso do sistema já em execução, tela a tela. Para colocar o
sistema de pé antes de seguir este manual, veja
[`COMO_RODAR.md`](COMO_RODAR.md) (instalação) e
[`MANUAL_EXECUCAO.md`](MANUAL_EXECUCAO.md) (primeira execução completa,
incluindo seed de dados e publicação de regras clínicas). Para entender o
que cada análise produz de fato, veja
[`ANALISES_DISPONIVEIS.md`](ANALISES_DISPONIVEIS.md).

---

## 1. Sessão de desenvolvimento (login)

Não há autenticação real neste MVP (ver
[`docs/governance/VALIDACAO_ESCOPO.md`](governance/VALIDACAO_ESCOPO.md)).
Ao abrir `http://localhost:5173`, um **banner de sessão de
desenvolvimento** aparece no topo pedindo um `external_subject`. Cole um
dos valores criados por `make seed-dev-data`:

| Subject | Papel | Acesso |
| --- | --- | --- |
| `dev-medico` | Médico | Pacientes, análises |
| `dev-enfermeiro` | Enfermeiro | Pacientes, análises |
| `dev-admin-tecnico` | Administrador técnico | Administração (exceto publicar regras clínicas), auditoria |
| `dev-admin-clinico` | Administrador clínico | Administração (incluindo publicar/reverter regras clínicas), auditoria |
| `dev-auditor` | Auditor | Auditoria |

Cada chamada à API valida o papel do lado do servidor — colar um
`subject` sem permissão para uma ação resulta em erro `403` explícito,
nunca em uma tela quebrada silenciosamente.

---

## 2. Navegação principal

A barra lateral mostra apenas os itens que o papel ativo tem permissão
de acessar:

```text
Pacientes              /patients          (médico, enfermeiro)
Nova análise           /analyses/new      (médico, enfermeiro)
Histórico              /analyses          (médico, enfermeiro)
Auditoria              /audit             (auditor, administradores)
Administração ▾        /admin/...         (administradores)
  ├─ Usuários e papéis
  ├─ Especialidades
  ├─ Funcionários
  ├─ Dados clínicos (regras)
  ├─ Unidades assistenciais
  └─ Feature flags
```

---

## 3. Pacientes

### 3.1 Listar e buscar

`/patients` mostra a tabela paginada de pacientes cadastrados, com busca
por nome/prontuário.

### 3.2 Cadastrar um paciente

`/patients/new`: preencha identificação (nome completo, prontuário, data
de nascimento, sexo registrado). **Nunca cadastre dados reais de
paciente** — use apenas dados sintéticos (ver
[`ESCOPO_PROJETO.md`](ESCOPO_PROJETO.md) seção 8.2).

### 3.3 Detalhe do paciente

`/patients/:patientId` reúne:

- **Dados pessoais** e edição (`/patients/:patientId/edit`).
- **Observações clínicas** (sinais vitais): registro manual de pressão
  arterial, SpO2, frequência cardíaca/respiratória, temperatura,
  glicemia, IMC, dor, nível de consciência, entre outros, com gráfico de
  série temporal por tipo de observação.
- **Alertas de anomalia** (`AlertsPanel`): alertas gerados
  automaticamente quando uma nova observação se desvia do histórico
  recente do próprio paciente (ver seção 4 de
  [`ANALISES_DISPONIVEIS.md`](ANALISES_DISPONIVEIS.md)). Cada alerta pode
  ser reconhecido, escalado ou resolvido pela equipe assistencial.
- **Apoio a análise clínica** (`ClinicalSupportPanel`): botão "Analisar
  dados clínicos" que gera, sob demanda, um resumo assistido por LLM do
  histórico recente do paciente (observações + alertas) — nunca
  substitui a avaliação do profissional.
- **Histórico de análises** do paciente e ação "Nova análise".

### 3.4 Acesso e vínculo assistencial

Médicos/enfermeiros só acessam pacientes com vínculo assistencial ativo
(ou por acesso de emergência "break glass", sempre auditado). Um
administrador técnico ou clínico cria os vínculos pela tela de
Administração.

---

## 4. Nova análise multimodal

`/patients/:patientId/analyses/new` (a partir do paciente) ou
`/analyses/new` (selecionando o paciente na própria tela):

1. **Selecionar o paciente** (se ainda não vier pré-selecionado).
2. **Revisar dados clínicos**: opcionalmente, selecione observações
   clínicas já registradas do paciente para incluir na análise (o motor
   de regras roda sobre esses dados estruturados).
3. **Texto adicional**: campo livre para o profissional descrever o
   contexto clínico (ex.: "paciente nega dor torácica"). Passa pela
   extração de termos clínicos (negação/temporalidade/certeza).
4. **Upload de mídia** por modalidade (áudio, vídeo, imagem) — um
   `FileDropzone` por modalidade habilitada (ver feature flags). O
   upload vai direto para o armazenamento (URL pré-assinada), sem passar
   pelo corpo da requisição da API.
5. **Confirmar e enviar**: o botão "Realizar análise" só habilita quando
   os uploads obrigatórios terminam e os campos mínimos são válidos. Ao
   confirmar, a análise entra em `QUEUED`.

---

## 5. Acompanhamento da análise

`/analyses/:analysisId` mostra o estado atual e o progresso por
modalidade:

| Estado | Significado |
| --- | --- |
| `CREATED` | Análise criada, aguardando confirmação de upload |
| `QUEUED` | Na fila, aguardando o worker do orquestrador |
| `PROCESSING` | Processadores de modalidade em execução |
| `WAITING_REVIEW` | Processamento concluído, pronta para revisão profissional |
| `COMPLETED` | Relatório confirmado |
| `FAILED_RETRYABLE` / `FAILED_FINAL` | Falha no processamento (temporária ou definitiva) |
| `CANCELLED` | Cancelada |

Se a análise ficar parada em `QUEUED`/`PROCESSING` por muito tempo,
confirme que o worker do orquestrador está rodando (ver
[`COMO_RODAR.md`](COMO_RODAR.md) seção 8).

---

## 6. Revisão da análise (`/analyses/:analysisId/review`)

Esta é a tela central do apoio à decisão clínica. De cima para baixo:

1. **Risco calculado**: nível (1-6), rótulo e cor — sempre resultado do
   motor de regras determinístico, nunca de um modelo de IA.
2. **Resumo por modalidade** (tabela): uma linha por modalidade
   informada, com qualidade dos dados, se há relação com informações
   clínicas, resumo do que foi encontrado, e se será usado no resumo
   final correlacionado.
3. **Resumo final correlacionado**: texto determinístico que
   correlaciona apenas as modalidades marcadas como clinicamente
   relevantes na tabela acima.
4. **Resumo assistido por IA**: síntese textual gerada automaticamente na
   consolidação de risco (template local ou LLM real, dependendo da
   configuração) — organiza/explica o que já foi calculado, nunca altera
   o risco.
5. **Apoio a análise clínica** (botão "Analisar dados clínicos"): mesmo
   mecanismo da tela de paciente, mas com o escopo apenas desta análise.
6. **Achados determinísticos**: o resultado de cada regra clínica
   avaliada (código, classificação, motivo de inconclusão se houver).
7. **Observações derivadas dos modelos** e **hipóteses assistidas não
   confirmadas**: achados de IA por modalidade, sempre identificados como
   tal.
8. **Evidências por modalidade e qualidade técnica**: tabela paginada com
   todos os achados técnicos (qualidade estrutural de cada mídia).
9. **Inconsistências e dados ausentes**, quando houver.
10. **Conduta prevista pelo protocolo**.
11. **Decisão**: botão para confirmar o relatório (`DRAFT` →
    `CONFIRMED`) ou, já confirmado, baixar o PDF.

Depois de confirmado, o relatório e o PDF ficam disponíveis
permanentemente — nenhuma edição posterior é permitida sem uma nova
análise.

---

## 7. Histórico de análises (`/analyses`)

Tabela paginada com filtros por paciente, profissional responsável,
período, modalidade, estado e risco. Cada linha permite abrir a análise
ou, se já revisada, ir direto para o relatório.

---

## 8. Auditoria (`/audit`)

Disponível para auditores e administradores. Busca por matrícula,
paciente, ação, período e análise. Cada evento mostra data/hora, ator,
papel, ação, recurso afetado, resultado e identificador de correlação —
detalhes técnicos (valores antes/depois) ficam disponíveis sob demanda.
A trilha é append-only com cadeia de hash verificável: nenhum evento pode
ser alterado silenciosamente depois de gravado.

---

## 9. Administração (`/admin/...`)

Acesso restrito a administradores (técnico e/ou clínico, conforme a
seção).

### 9.1 Usuários e papéis

CRUD de usuários do sistema e seus papéis (médico, enfermeiro,
administrador técnico/clínico, auditor).

### 9.2 Especialidades

Cadastro das especialidades médicas usadas no cadastro de funcionários.

### 9.3 Funcionários

Cadastro de funcionários (nome, CPF, matrícula, e-mail, especialidade) —
usado, entre outras coisas, na aprovação de publicação de regras
clínicas e nos vínculos assistenciais.

### 9.4 Dados clínicos (regras)

Diferente das demais telas de administração, **não há criação/edição
pela interface** — o conteúdo vem de YAML versionado
(`backend/clinical_rules/seeds/`). Esta tela permite:

- Ver o status de cada conjunto de regras (`draft`/`published`).
- **Publicar** um conjunto em `draft` (exige aprovador e justificativa,
  registrados em auditoria) — só a partir da publicação o motor de
  regras passa a classificar risco para aquele código/população.
- **Reverter (rollback)** uma publicação para uma versão anterior.

### 9.5 Unidades assistenciais

Cadastro das unidades (setores/alas) usadas nos vínculos assistenciais
entre profissional e paciente.

### 9.6 Feature flags

Liga/desliga em runtime (sem reiniciar o processo), entre outros:

- Provedor de LLM (OpenAI real vs. template local).
- Modalidades de mídia aceitas em novas análises.
- Reconhecimento de imagem via Azure AI Vision.
- Análise de sentimento via Azure AI Language.
- Motores de visão computacional de vídeo (YOLOv8/OpenPose),
  independentemente um do outro.
- Apoio à análise clínica automático (roda o LLM sem precisar clicar no
  botão).

Toda alteração é registrada em auditoria com o valor antes/depois de
cada campo. Ver o detalhamento de cada flag em
[`MANUAL_INSTALACAO.md`](MANUAL_INSTALACAO.md) seção 11.

---

## 10. Boas práticas de uso

- **Nunca** cadastre dados reais de paciente, mesmo em ambiente de teste.
- Publique apenas as regras clínicas (`Dados clínicos (regras)`)
  necessárias para o que você pretende demonstrar — regras em `draft`
  fazem o motor retornar "inconclusivo" de propósito, para nunca
  classificar risco sem aprovação.
- Ao testar alertas de anomalia, registre ao menos 3 observações do
  mesmo tipo antes de uma leitura fora do padrão — a baseline exige um
  histórico mínimo (ver [`ANALISES_DISPONIVEIS.md`](ANALISES_DISPONIVEIS.md)
  seção 4).
- Ao revisar uma análise, trate "Resumo assistido por IA" e "Apoio a
  análise clínica" como apoio explicativo, nunca como o resultado
  clínico em si — o risco confiável é sempre o do motor de regras.

---

## Documentação relacionada

- [`docs/COMO_RODAR.md`](COMO_RODAR.md) — instalação e execução, passo a passo
- [`docs/MANUAL_EXECUCAO.md`](MANUAL_EXECUCAO.md) — primeira execução completa (seed, publicação de regras, demonstração)
- [`docs/ANALISES_DISPONIVEIS.md`](ANALISES_DISPONIVEIS.md) — o que cada análise produz, em detalhe
- [`docs/ESPECIFICACAO_FRONTEND.md`](ESPECIFICACAO_FRONTEND.md) — especificação completa de telas e design system
- [`README.md`](../README.md) — visão geral do repositório
