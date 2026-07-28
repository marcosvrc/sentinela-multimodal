# Análises Disponíveis — SentinelHealth

Este documento detalha **o que cada análise produz de fato** no sistema:
os modelos/algoritmos aplicados por tipo de dado, o motor de regras
determinístico que calcula o risco clínico, e a detecção de anomalias em
série temporal.

**Princípio central, repetido em todo este documento:** o risco clínico
**nunca** vem de um modelo de IA. Todo `risk_level` exibido no sistema é
calculado por um motor de regras determinístico e versionado
(`clinical_rules/`). Modelos de IA (visão computacional, transcrição,
LLM, análise de sentimento) produzem apenas **observações** e
**hipóteses assistidas** — nunca a classificação de risco final.

---

## 1. Análise de vídeo

| Aspecto | Detalhe |
| --- | --- |
| Entrada aceita | MP4/MOV — sessões de fisioterapia, cirurgias gravadas, vídeos clínicos gerais |
| Duração | Extraída dos metadados reais do container ISO BMFF (`mvhd`), não estimada |
| Amostragem | `VISION_MAX_SAMPLE_FRAMES` quadros extraídos via `ffmpeg` (padrão: 8) — não o vídeo inteiro, para manter a análise viável em CPU |
| Modelo de pose | **OpenPose** (BODY_25) — keypoints articulares por quadro amostrado. Worker self-hosted (não é um serviço de nuvem gerenciado) |
| Modelo de detecção | **YOLOv8** (`ultralytics`, execução em CPU) — objetos/áreas por quadro amostrado |
| Saída de pose | Contagem de pessoas detectadas + confiança média dos keypoints |
| Saída de detecção | Rótulos + confiança por objeto detectado |
| Hipótese assistida | "Possível ausência de pessoa no campo de captura" — gerada quando o motor de pose está ativo e nenhuma pessoa é detectada em nenhum quadro amostrado |

Os dois motores (pose e detecção) são **independentes** e ligados por
feature flags separadas (`vision_pose_enabled`/`vision_detection_enabled`)
— é possível usar só YOLOv8 (mais simples de instalar) sem depender do
binário do OpenPose. Quando um motor está desligado, o resumo do achado
nunca menciona "0 detecções"/"0 pessoas" para ele (isso pareceria um
achado negativo real); só relata o resultado dos motores que de fato
rodaram.

**Por que self-hosted em vez de um serviço gerenciado:** avaliação
registrada em [ADR 0016](adr/0016-avaliacao-componentes-aws-gerenciados.md)
concluiu que nenhum serviço de visão gerenciado (incluindo Azure AI
Vision) oferece estimativa de pose articulada — requisito central desta
modalidade. Essa conclusão continua válida mesmo após a migração da
infraestrutura de nuvem para Azure-only.

Sem `VISION_PROVIDER=OPENPOSE_YOLOV8` configurado (padrão `LOCAL`), o
processador de vídeo nunca inventa keypoints ou detecções — registra
"indisponível" explicitamente e segue com a avaliação de qualidade
baseada na duração real do arquivo.

---

## 2. Análise de áudio

| Aspecto | Detalhe |
| --- | --- |
| Entrada aceita | WAV — áudios de consultas médicas |
| Análise acústica (sempre ativa, sem nuvem) | DSP real sobre as amostras PCM: energia RMS por janela, taxa de cruzamento por zero, proporção de pausas, contagem de segmentos de fala |
| Transcrição | **Azure AI Speech** (Fast Transcription API), síncrona, idioma fixo `pt-BR` — envia os bytes do áudio direto no corpo da requisição, sem exigir upload prévio a um Blob Storage |
| Termos clínicos na transcrição | Extraídos pelo mesmo motor NegEx/ConText usado no texto (negação, temporalidade, certeza, experienciador) |
| Sentimento (contextual) | **Azure AI Language** (`SentimentAnalysis` + `KeyPhraseExtraction`) sobre a transcrição — nunca influencia o risco clínico |

### 2.1 Hipóteses assistidas geradas pela análise acústica

| Hipótese | Condição de disparo | Associação (nunca diagnóstico) |
| --- | --- | --- |
| "Possível padrão de fala fragmentada" | Proporção de pausas ≥ 50% com ≥ 3 segmentos de fala | Fadiga/dispneia |
| "Possível redução de energia vocal" | Energia RMS média abaixo do limiar configurado | Fadiga/dispneia |

Essas duas hipóteses **não dependem de transcrição** — funcionam mesmo
com `TRANSCRIPTION_PROVIDER=LOCAL` (sem Azure Speech configurado), porque
são calculadas diretamente sobre as amostras PCM do áudio.

Sem Azure AI Speech configurado, a transcrição retorna "indisponível"
explicitamente — a análise acústica DSP continua rodando normalmente
(não depende de ASR).

---

## 3. Análise de imagem

| Aspecto | Detalhe |
| --- | --- |
| Entrada aceita | PNG/JPEG — fotografias clínicas, radiológicas ou documentos digitalizados |
| Qualidade | Dimensões reais extraídas do arquivo, avaliadas por resolução (`ADEQUATE`/`MODERATE`/`INSUFFICIENT`/`INVALID`) |
| Categorização heurística (sempre ativa, sem nuvem) | Heurística própria de cor/textura — não é um classificador treinado: `PHOTOGRAPH` / `SCANNED_DOCUMENT` / `RADIOLOGICAL`, com a área de maior densidade de borda como aproximação de "região de interesse" |
| Reconhecimento (opcional, feature flag `image_recognition_enabled`) | **Azure AI Vision** (Image Analysis, feature `tags`) — rótulos genéricos (ex.: "Person", "X-Ray") como achado complementar, roda **depois** da heurística e nunca a substitui |

### 3.1 Guardrail de relevância clínica de rótulos

Rótulos genéricos do Azure AI Vision não têm noção de contexto clínico —
uma foto de paisagem recebe rótulos como qualquer outra imagem. Por
isso, cada conjunto de rótulos passa por uma heurística de palavra-chave
(`app.vision.clinical_relevance.assess_label_clinical_relevance`) que
classifica o achado como:

- **`RELEVANT`**: rótulos sugerem conteúdo clinicamente relevante (ex.:
  "X-Ray", "Bandage", "Wound").
- **`NOT_RELEVANT`**: rótulos claramente não clínicos (ex.: "Mountain",
  "Car") — o achado é marcado com aviso explícito no laudo e **excluído**
  de todo apoio automático (resumo de IA, apoio clínico, resumo por
  modalidade).
- **`UNDETERMINED`**: rótulos ambíguos — mesma exclusão de
  `NOT_RELEVANT`, tratado com a mesma cautela.

Esse guardrail é a mesma regra reaproveitada em três lugares do sistema
(`app.processors.clinical_relevance.is_clinically_relevant`): no cálculo
de "nível de atenção por modalidade", no "resumo por modalidade" da tela
de revisão, e no filtro de achados enviados ao LLM no apoio à análise
clínica — nunca há duas implementações divergentes da mesma decisão.

---

## 4. Análise de texto

| Aspecto | Detalhe |
| --- | --- |
| Entrada | Texto adicional informado pelo profissional na criação da análise |
| Processamento (sempre ativo, sem nuvem) | Motor NegEx/ConText próprio (`app.clinical_nlp`) — identifica termos clínicos candidatos de uma lista curada, com negação (afirmado/negado), temporalidade (atual/passado/futuro), certeza (confirmado/suspeito/possível/condicional) e experienciador (paciente/familiar/outro) |
| Sentimento (contextual, opcional) | **Azure AI Language**, mesmo adaptador do áudio — feature flag `sentiment_analysis_enabled` |

Exemplo real: o texto "Paciente nega dor torácica" produz um achado
`MODEL_OBSERVATION` com `term="dor torácica"`, `negation=NEGATED` — nunca
tratado como se o paciente tivesse relatado dor.

O extrator de termos é "seguro por construção": só produz achado quando
um termo da lista curada de vocabulário clínico é de fato encontrado —
nunca inventa um termo a partir de texto livre arbitrário.

---

## 5. Consolidação de risco por IA (síntese, nunca decisão)

| Aspecto | Detalhe |
| --- | --- |
| Modelo | OpenAI (GPT, ex. `gpt-4o-mini`) via adaptador com JSON Schema estrito, ou template determinístico local (padrão, sem chamada de rede) |
| Papel | Síntese/explicação textual dos achados **já calculados** pelo motor de regras — nunca decide nem altera `risk_level` |
| Entrada minimizada | Allowlist de campos estruturados já resumidos (nunca mídia bruta, nunca identificadores diretos do paciente) |
| Falha | `LlmCallStatus.FAILED`/`SKIPPED` nunca bloqueia o registro clínico — o risco determinístico já foi calculado antes da chamada ao LLM |

Distinto do "Apoio à análise clínica" (seção 7): este resumo (`ai_summary`)
é automático, sempre gerado durante a consolidação de risco, e usa os
achados de qualidade estrutural (`ORIGINAL_DATA`) de cada modalidade como
contexto — não filtra por relevância clínica confirmada.

---

## 6. Motor de regras determinístico (o único que calcula risco)

Cada regra clínica (`ClinicalRuleSet`, versionada em YAML) tem uma
condição (`when`, avaliada por um interpretador de expressões seguro, sem
`eval` genérico), um `risk_level` (1 a 6) e um rótulo de classificação.
Quando múltiplas regras casam para o mesmo código, prevalece o
`risk_level` mais alto. Regras carregadas via seed entram em `draft` e só
passam a classificar risco depois de **publicadas** por um administrador
clínico (aprovador + justificativa, sempre auditados).

### 6.1 Escala canônica de risco

| Nível | Rótulo |
| --- | --- |
| 1 | Baixo |
| 2 | Leve |
| 3 | Moderado |
| 4 | Alto |
| 5 | Muito alto |
| 6 | Crítico |
| — | Inconclusivo (nenhuma regra casou, ou dados obrigatórios ausentes) |

Quando não há regra aplicável ou faltam dados obrigatórios, o resultado
é explicitamente **inconclusivo** — nunca tratado como "normal" por
omissão.

### 6.2 Exemplo real — Pressão arterial (`clinical_rules/seeds/blood_pressure.yaml`)

| Faixa | Classificação | Nível de risco |
| --- | --- | --- |
| Sistólica ≤ 90 mmHg | Hipotensão grave | 6 (Crítico) |
| Sistólica 111–119 e diastólica < 80 | Normal | 1 (Baixo) |
| Sistólica 120–129 e diastólica < 80 | Pressão elevada | 3 (Moderado) |
| Sistólica 140–180 ou diastólica 90–120 | Hipertensão estágio 2 | 4 (Alto) |
| Sistólica > 180 ou diastólica > 120 | Crise hipertensiva | 6 (Crítico) |

### 6.3 Exemplo real — SpO2 (`clinical_rules/seeds/spo2.yaml`)

| Faixa | Classificação | Nível de risco |
| --- | --- | --- |
| ≥ 96% | Normal | 1 (Baixo) |
| 94–95% | Levemente reduzida | 3 (Moderado) |
| 92–93% | Hipoxemia | 4 (Alto) |
| ≤ 91% | Hipoxemia grave | 6 (Crítico) |

Regras adicionais publicadas cobrem: frequência cardíaca, frequência
respiratória, temperatura, glicemia, IMC, dor, nível de consciência,
convulsão, débito urinário, marcha/postura, atividade/movimento, e
eventos de cirurgia (equipe, ferramentas, fluxo, eventos adversos).

---

## 7. Apoio à análise clínica (sob demanda, distinto do resumo automático)

Botão "Analisar dados clínicos", disponível em duas variantes:

| Variante | Escopo | Onde |
| --- | --- | --- |
| Por paciente | Histórico completo recente (observações + alertas de anomalia) | Tela de detalhe do paciente |
| Por análise | Achados já produzidos pelos processadores desta análise + risco já calculado | Tela de revisão da análise |

Ambas seguem o mesmo padrão: chamam o LLM configurado com um payload
minimizado, **nunca persistem automaticamente** (cada clique gera um
resumo novo a partir do estado atual — exceto o resultado por análise,
que fica salvo em `Report.clinical_support_summary` para sobreviver à
reabertura da tela). Diferente da consolidação de risco (seção 5), aqui o
próprio resultado da funcionalidade **é** o texto do LLM — uma falha é
reportada como erro ao profissional, nunca mascarada com um resumo
inventado.

O apoio por análise já filtra achados por relevância clínica confirmada
(exclui achados com `clinical_relevance` em `NOT_RELEVANT`/`UNDETERMINED`,
ver seção 3.1) antes de montar o prompt.

---

## 8. Resumo por modalidade e resumo final correlacionado (tela de revisão)

Consolidação estruturada por modalidade, calculada em
`app.reports.builder._compute_modality_summary`, exibida como tabela na
tela de revisão:

| Coluna | Origem |
| --- | --- |
| Modalidade | `ModalityType` presente na análise |
| Qualidade | Pior `quality_state` entre os achados `ORIGINAL_DATA` da modalidade |
| Dados clínicos? | Mesma regra de relevância clínica da seção 3.1/6, aplicada aos achados `MODEL_OBSERVATION`/`ASSISTED_HYPOTHESIS` da modalidade |
| Resumo | Texto dos achados relevantes (ou, na ausência, dos achados de qualidade) |
| Usado na análise final | `true` quando a modalidade tem ao menos um achado clinicamente relevante confirmado |

O **resumo final correlacionado** (`clinical_correlation_summary`) é
determinístico (não depende de LLM/nuvem — sempre disponível) e
correlaciona **apenas** as modalidades marcadas como "usadas na análise
final" na tabela acima, listando as demais como desconsideradas por
falta de dados clínicos relevantes.

---

## 9. Detecção de anomalias em séries temporais

Distinta do motor de regras (seção 6): avalia cada **nova observação** de
sinal vital contra o **histórico recente do próprio paciente**, gerando
um alerta consultivo separado (`app.anomaly_detection`) — nunca altera o
risco calculado pelo motor de regras. Requer no mínimo 3 amostras
anteriores do mesmo tipo de sinal para calcular uma baseline.

### 9.1 Critério 1 — Desvio de baseline (média/desvio-padrão)

Calcula quantos desvios-padrão (`σ`) a nova leitura está da média das
leituras recentes:

| Severidade | Limiar |
| --- | --- |
| `MODERATE` | ≥ 2σ |
| `HIGH` | ≥ 3σ |
| `CRITICAL` | ≥ 4σ |

### 9.2 Critério 2 — Variação abrupta (rate-of-change)

Mudança absoluta entre leituras consecutivas, dentro de uma janela de
tempo — dispara `HIGH` independentemente do desvio de baseline (o valor
absoluto já é calibrado para representar uma mudança clinicamente
relevante em si, sem um segundo limiar "crítico" separado):

| Sinal | Variação absoluta | Janela |
| --- | --- | --- |
| Frequência cardíaca | ≥ 40 bpm | 30 minutos |
| Frequência respiratória | ≥ 10 rpm | 30 minutos |
| SpO2 | ≥ 6 pontos percentuais | 30 minutos |
| Temperatura | ≥ 1,5 °C | 2 horas |
| Pressão sistólica | ≥ 40 mmHg | 30 minutos |
| Pressão diastólica | ≥ 25 mmHg | 30 minutos |
| Débito urinário | ≥ 30 mL | 1 hora |

Quando os dois critérios disparam simultaneamente, o alerta usa a
severidade mais alta entre os dois (`MODERATE < HIGH < CRITICAL`).

### 9.3 Exemplo numérico completo

Paciente com histórico estável de SpO2 em torno de **97%** (média das
últimas leituras = 97, desvio-padrão = 0,5). Uma nova leitura de **88%**
chega:

```text
deviation_sd = |88 - 97| / 0.5 = 18σ
```

18σ ultrapassa o limiar `CRITICAL` (≥ 4σ) por uma margem enorme → alerta
`CRITICAL` criado automaticamente, com evidência anexada
(`baseline_mean=97`, `baseline_stddev=0.5`, `deviation_sd=18`) e ação
esperada registrada ("Acionar a equipe assistencial imediatamente;
considerar avaliação médica urgente"). Além disso, se a leitura anterior
foi há menos de 30 minutos, o critério de variação abrupta (≥ 6 pontos
percentuais) também dispara (`delta=9`), reforçando a severidade `HIGH`
— o resultado final permanece `CRITICAL` (o mais alto dos dois).

O alerta fica visível em `GET /patients/{id}/alerts` e na tela de
detalhe do paciente, podendo ser reconhecido, escalado ou resolvido pela
equipe (`POST /alerts/{id}/acknowledge|escalate|resolve`).

### 9.4 Sinais cobertos

Frequência cardíaca, frequência respiratória, SpO2, temperatura, pressão
arterial (sistólica e diastólica) e débito urinário.

### 9.5 Limitações conhecidas (documentadas, não fingidas)

- **Evolução de prescrições**: sem detecção de anomalia — exigiria uma
  base farmacológica estruturada (doses, interações, alergias) que não
  existe hoje.
- **Padrões de movimentação ao longo do tempo**: sem detecção de
  anomalia — exigiria um mecanismo de agregação longitudinal de achados
  de pose entre múltiplas análises de vídeo do mesmo paciente, que não
  existe hoje.

---

## 10. Entrega de alertas e resultados

Alertas de anomalia e achados clínicos ficam disponíveis via API/tela
para consulta pela equipe assistencial (sujeito a vínculo assistencial
ou acesso de emergência auditado). **Não há push/e-mail/WebSocket** — a
entrega é por consulta (pull), consistente com a decisão de escopo
"análise sob demanda" do MVP (ver
[`ESCOPO_PROJETO.md`](ESCOPO_PROJETO.md) seção 1). Notificação em tempo
real é evolução futura, não implementada hoje.

---

## 11. Como interpretar a tela de revisão da análise (passo a passo)

Esta seção explica **exatamente como cada número e cada texto exibido em
`/analyses/:id/review` é calculado**, na ordem em que aparecem na tela.
Objetivo: um profissional de saúde conseguir olhar para qualquer valor da
tela e saber de onde ele vem, sem precisar adivinhar.

A tela é dividida em três blocos, sinalizados por uma faixa colorida à
esquerda:

| Bloco | Cor | Conteúdo | Influencia o `risk_level`? |
| --- | --- | --- | --- |
| A — Dados clínicos estruturados | Verde | Sinais vitais + motor de regras | **Sim — é a única fonte** |
| B — Dados multimodais | Azul | Áudio/vídeo/imagem/texto processados | Não |
| C — Análise consolidada (IA) | Azul-escuro | Síntese e sugestão da IA | Não |

### 11.1 Bloco A — Dados clínicos estruturados

**Nível de risco (1–6) e classificação.** Vem de
`content.calculated_risk`, calculado em
`app.risk_consolidation.engine.consolidate_code_evaluations`
(`backend/app/risk_consolidation/engine.py`). O cálculo, passo a passo:

1. Para cada código de sinal vital informado nesta análise (ex.:
   `blood_pressure`, `spo2`), o motor busca o conjunto de regras
   **publicado** vigente para aquele código e avalia cada condição da
   regra (`app.rules_engine.engine.evaluate_rule_set`) contra o valor
   informado.
2. Se **mais de uma regra do mesmo conjunto** casar com o valor (não
   deveria ocorrer em um conjunto bem desenhado, mas o motor não assume
   isso), vence o `risk_level` **mais alto** — postura conservadora de
   segurança do paciente.
3. Se a análise tem **mais de um sinal vital** (ex.: pressão arterial +
   SpO2), cada um produz seu próprio resultado, e o mesmo critério se
   repete entre eles: o `risk_level` mais alto entre todos os sinais
   avaliados é o que aparece como "Nível de risco" da análise.
4. O resultado é **`Inconclusivo`** (não um nível de risco "seguro") em
   qualquer um destes casos: nenhum dado clínico foi informado, falta uma
   entrada obrigatória exigida pelo conjunto de regras, o conjunto de
   regras para aquele código ainda está em rascunho (não publicado), ou
   nenhuma regra publicada casou com o valor informado. **Inconclusivo
   nunca significa "normal".**

**Dados informados.** Contagem simples: `Object.keys(structured_clinical_inputs).length`
— o número de **sinais vitais diferentes** informados nesta análise (não
o número de campos dentro de cada sinal; ex.: pressão arterial conta como
1, mesmo tendo sistólica + diastólica).

**Resultado (Conclusivo/Inconclusivo).** Mesmo cálculo do "Nível de
risco" acima — `Conclusivo` quando `outcome == "MATCHED"` (ao menos uma
regra publicada casou), `Inconclusivo` em qualquer outro caso.

**Taxa conclusiva.** Estatística **agregada de toda a instituição**
(não apenas desta análise), calculada em
`app.risk_consolidation.service.get_analysis_consolidation_stats`
(`backend/app/risk_consolidation/service.py`): conta todas as análises da
instituição com risco já consolidado, calcula `(conclusivas / total) × 100`,
sem filtro de período — é o histórico completo. Uma taxa baixa geralmente
indica falta de regras publicadas para os sinais mais usados, ou muitas
análises submetidas sem dados clínicos estruturados.

**Achados determinísticos.** Lista, um item por sinal vital avaliado, com
o código do sinal, o resultado (`Classificado`/`Inconclusivo`), o rótulo
da regra que casou (ex.: "Hipertensão estágio 2") e — quando inconclusivo
— o motivo exato (dado obrigatório ausente, regra não publicada, ou
nenhuma regra casou com o valor).

### 11.2 Bloco B — Dados multimodais

**Big numbers (linha de cima):**

| Card | Cálculo |
| --- | --- |
| Modalidades | Quantidade de tipos de dado (áudio/vídeo/imagem/texto) com ao menos um achado nesta análise |
| Com relevância clínica | Quantidade de modalidades com ao menos um achado que passou pelo guardrail de relevância clínica (ver abaixo) |
| Termos clínicos | Quantidade de observações com `term` + `extraction_method` presentes (ver extração de termos abaixo) |
| Hipóteses | `content.assisted_hypotheses.length` — hipóteses geradas pelos processadores (nunca pela IA generativa) |
| Qualidade geral | **Pior** `quality_state` entre todos os achados técnicos (`ORIGINAL_DATA`) de todas as modalidades — uma única modalidade com qualidade `INSUFFICIENT` "arrasta" o indicador geral para baixo, mesmo que as demais estejam `ADEQUATE` |

**Guardrail de relevância clínica** (decide "Com relevância clínica" e
também filtra o que entra no resumo final): função
`is_clinically_relevant` em `app.processors.clinical_relevance`
(`backend/app/processors/clinical_relevance.py`). Regra por tipo de
achado:

- Hipótese assistida (qualquer modalidade) → **sempre** relevante.
- Termo clínico extraído do texto/transcrição, ou métrica acústica do
  áudio (energia vocal, pausas) → **sempre** relevante (só existem
  quando algo real foi encontrado).
- Rótulo do Azure AI Vision → relevante **somente** se marcado como
  `RELEVANT` pelo próprio guardrail de imagem (seção 3.1) — nunca
  `NOT_RELEVANT`/`UNDETERMINED`.
- Sentimento (Azure AI Language) ou categorização heurística de imagem
  (foto/documento/radiológica) → **nunca** contam por si só, são sempre
  contextuais.
- Qualidade estrutural pura (`ORIGINAL_DATA`, ex.: "Imagem 300×300") →
  **nunca** conta — é metadado técnico, não fala do conteúdo.

**Extração de termos clínicos** (tabela "Termos clínicos e observações").
Método primário: **LLM** (`extract_clinical_terms`, GPT-4o) — envia o
texto e recebe termo + negação + temporalidade + certeza + experienciador
já estruturados. Se a chamada ao LLM falhar (rede, credencial), o sistema
cai automaticamente para o motor **NegEx/ConText determinístico**
(`app.clinical_nlp.text_analysis`), que funciona assim:

1. Varre o texto por frase (segmentado por `. ! ? ; \n`) buscando termos
   de uma lista curada (ex.: "dor torácica", "dispneia", "febre").
2. Para cada termo encontrado, procura "pistas" (palavras-chave) **antes**
   do termo, dentro da mesma frase: `nega`, `sem`, `ausência de` →
   negação. Conjunções como "mas"/"porém" interrompem esse alcance —
   ex.: "nega febre, mas relata dor" não marca "dor" como negado.
3. Certeza: `suspeita de` → Suspeito; `possível` → Possível; senão
   Confirmado (padrão).
4. Temporalidade: `ontem`/`histórico de` → Passado; senão Atual.
5. Experienciador: pistas de parentesco (`mãe`, `familiar`) → Familiar;
   senão Paciente.

Cada linha da tabela é uma combinação única de termo+negação+temporalidade
+certeza+experienciador — ocorrências repetidas da mesma combinação são
agrupadas e contadas ("2x", "3x"), não duplicadas.

**Qualidade técnica por modalidade** (coluna da tabela de detalhamento
técnico), thresholds exatos em `app.processors.quality`
(`backend/app/processors/quality.py`):

| Modalidade | Insuficiente | Moderada | Adequada |
| --- | --- | --- | --- |
| Imagem (menor dimensão) | < 200 px | 200–479 px | ≥ 480 px |
| Áudio / Vídeo (duração) | < 1,0 s | 1,0–2,9 s | ≥ 3,0 s |
| Texto (caracteres) | < 20 (ou vazio = Inválida) | 20–59 | ≥ 60 |

Duração/dimensão que não pôde ser determinada no arquivo é classificada
como `Moderada` por padrão (nunca `Adequada` por omissão).

### 11.3 Bloco C — Análise consolidada (IA)

**Risco sugerido (assisted_risk).** Calculado por uma chamada **separada**
ao LLM (`assess_modality_risk`, prompt dedicado em
`app.integrations.llm.openai_adapter`), executada em
`consolidate_analysis_risk` (`backend/app/risk_consolidation/service.py`)
**antes** do resumo explicativo. Recebe como entrada: os achados
multimodais clinicamente relevantes desta análise (ou, se não houver
nenhum, um resumo sintético dos próprios dados clínicos estruturados) e o
`risk_level`/`outcome` **determinístico já calculado**, apenas como
contexto — o prompt deixa explícito que o LLM pode sugerir um nível
diferente se os achados multimodais justificarem, mas nunca pode
substituir ou apagar o resultado determinístico. `uncertainty_note` é
texto livre gerado pelo próprio modelo (o backend não valida seu
conteúdo, apenas garante que o campo existe no schema). O valor é
clampado entre 1 e 6 no código antes de ser salvo, mesmo que o modelo
devolva algo fora da faixa.

Quando o risco sugerido diverge do determinístico, trate ambos como
informações complementares: o determinístico é a classificação **oficial**
usada em todo o restante do sistema (protocolo, alertas, relatório); o
sugerido é um alerta de que os dados multimodais podem indicar algo que
os sinais vitais isolados não capturam — vale a pena revisar a
justificativa antes de decidir.

**Resumo explicativo.** Chamada **diferente** da anterior
(`summarize`, mesmo módulo), que recebe o risco determinístico, os
achados de qualidade de cada modalidade, até 15 achados multimodais
clinicamente relevantes, e o resultado do risco sugerido acima (para
poder mencionar uma divergência explicitamente, ex.: "o risco
determinístico é nível 1, porém a análise assistida por IA sugere nível 4
devido a..."). O prompt proíbe explicitamente o modelo de alterar o
`risk_level` — sua única função é explicar em português por que o
resultado já calculado chegou a esse valor. Nunca recebe texto livre bruto
do paciente, apenas os campos já estruturados acima.

**Apoio à análise clínica** (botão "Analisar dados clínicos"). Terceira
chamada de LLM, independente das duas anteriores, disparada sob demanda
(ou automaticamente, se a feature flag `auto_clinical_support_enabled`
estiver ligada). Filtra os achados pelo mesmo guardrail de relevância
clínica da seção 11.2 antes de montar o prompt, e devolve quatro textos
separados: visão clínica, causas prováveis, direcionamento sugerido e nota
de incerteza. Fica salvo em `Report.clinical_support_summary` — sobrevive
à reabertura da tela, mas cada novo clique gera uma versão nova a partir
do estado atual dos achados.

### 11.4 Resumo por modalidade e correlação final

A tabela "Resumo por modalidade" (quando exibida) e o texto de correlação
final são **determinísticos** — não dependem de LLM nem de nuvem, sempre
disponíveis. Calculados em `app.reports.builder._compute_modality_summary`:
para cada modalidade presente na análise, cruza a pior qualidade técnica
(`ORIGINAL_DATA`) com a relevância clínica (mesma regra da seção 11.2) e
decide se a modalidade entra na correlação final — só entram modalidades
com ao menos um achado clinicamente relevante confirmado; qualidade
técnica isoladamente nunca é suficiente.

---

## Documentação relacionada

- [`docs/MANUAL_USO.md`](MANUAL_USO.md) — como usar cada análise pela interface
- [`docs/MANUAL_CAMPOS.md`](MANUAL_CAMPOS.md) — campos e regras de cada tela, incluindo a de revisão
- [`docs/MANUAL_INSTALACAO.md`](MANUAL_INSTALACAO.md) — como ligar cada integração real (Azure, OpenAI, visão)
- [`docs/ARQUITETURA.md`](ARQUITETURA.md) — arquitetura do sistema
- [`docs/ESCOPO_PROJETO.md`](ESCOPO_PROJETO.md) — escopo completo do produto
- [`README.md`](../README.md) — visão geral do repositório
