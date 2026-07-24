# Relatório Técnico — Tech Challenge Fase 4

**Projeto:** SentinelHealth — sistema de apoio a análises clínicas com IA multimodal
**Repositório:** `sentinela-multimodal`

Este documento atende ao entregável "Relatório técnico" da Fase 4:
descrição do fluxo multimodal, modelos aplicados por tipo de dado, e
resultados obtidos com exemplos de anomalias detectadas. Para o escopo
completo do produto, ver [`ESCOPO_PROJETO.md`](ESCOPO_PROJETO.md); para
decisões arquiteturais individuais, ver [`adr/`](adr/).

---

## 1. Visão geral do sistema

O SentinelHealth é um sistema de apoio à decisão clínica que analisa
dados multimodais (áudio, vídeo, imagem e texto) enviados por um
profissional de saúde, aplica um motor de regras determinístico sobre
dados clínicos estruturados e produz um relatório revisável antes de se
tornar definitivo. **Não realiza diagnóstico autônomo**: o risco clínico
vem exclusivamente de regras versionadas e aprovadas — modelos de IA
(visão computacional, transcrição, LLM) produzem apenas observações e
hipóteses, nunca a classificação de risco final.

A única nuvem gerenciada utilizada é o **Azure Cognitive Services**
(Speech, Language, Vision). Não há dependência de nenhum serviço AWS no
código nem na infraestrutura.

---

## 2. Descrição do fluxo multimodal

```text
1. Profissional cadastra o paciente e cria uma análise
2. Upload de mídia(s) via URL/token assinado (audio/video/imagem)
   + texto adicional e/ou dados clínicos estruturados (sinais vitais)
3. Confirmação do upload -> varredura antimalware -> promoção do arquivo
4. Submissão da análise -> status QUEUED -> mensagem publicada na fila
5. Worker do orquestrador consome a fila (assíncrono, fora do ciclo HTTP):
   a. Um processador por modalidade pendente roda de forma independente
      (áudio, vídeo, imagem, texto)
   b. Cada processador grava achados tipados (qualidade estrutural,
      observação de modelo, hipótese assistida)
6. Motor de regras determinístico avalia os dados clínicos estruturados
   e calcula o nível de risco (1-6, tabela `risk_levels`)
7. LLM (opcional) gera um resumo textual explicativo, sem alterar o
   risco calculado
8. Relatório fica em DRAFT, disponível para revisão
9. Profissional aceita/corrige/rejeita cada achado e confirma o relatório
10. PDF final é gerado e disponibilizado para download
```

O fluxo é **assíncrono via fila** (implementação atual: tabela
PostgreSQL com `SELECT ... FOR UPDATE SKIP LOCKED`, adaptador único do
MVP) — a API nunca bloqueia a requisição HTTP esperando o processamento
multimodal. Essa é uma decisão de escopo documentada em
[`ESCOPO_PROJETO.md`](ESCOPO_PROJETO.md) (seção 1, "Escopo inicial
(MVP): análise sob demanda"): monitoramento contínuo e alertas em tempo
real ficam como evolução futura, condicionados a integração validada com
dispositivos e prontuário hospitalar.

Cada modalidade tem estado próprio (`AnalysisModalityState`) e pode ser
reprocessada individualmente sem duplicar resultados definitivos. Falhas
de um provedor de IA (Azure, OpenAI) nunca bloqueiam o registro clínico
nem ocultam alertas determinísticos já identificados — o adaptador real
falha explicitamente (`status=FAILED`/`UNAVAILABLE` com motivo), nunca
finge um resultado.

---

## 3. Modelos e serviços aplicados por tipo de dado

### 3.1 Vídeo

| Aspecto | Detalhe |
| --- | --- |
| Entrada | Vídeos clínicos (MP4/MOV — sessões de fisioterapia, cirurgias gravadas) |
| Duração | Calculada a partir dos metadados reais do container ISO BMFF (`mvhd`) |
| Modelo de pose | **OpenPose** (BODY_25) — worker self-hosted, keypoints articulares por quadro amostrado |
| Modelo de detecção | **YOLOv8** (`ultralytics`, CPU) — objetos/áreas críticas por quadro amostrado |
| Amostragem | `max_sample_frames` quadros extraídos via `ffmpeg`, não o vídeo inteiro (mantém a análise viável em CPU) |
| Saída | Contagem de pessoas detectadas + confiança média dos keypoints (pose), rótulos + confiança por objeto (detecção) |
| Hipótese assistida | "Possível ausência de pessoa no campo de captura" quando o motor de pose roda e nenhuma pessoa é detectada em nenhum quadro |

Por que worker self-hosted em vez de um serviço gerenciado: avaliação
registrada em [`ADR 0016`](adr/0016-avaliacao-componentes-aws-gerenciados.md)
concluiu que serviços de visão gerenciados (incluindo Azure AI Vision) não
oferecem estimativa de pose articulada, requisito central desta
modalidade. OpenPose e YOLOv8 continuam sendo os motores de vídeo mesmo
após a migração da infraestrutura de nuvem para Azure.

Os dois motores (pose/detecção) são independentes e configuráveis por
feature flag (`vision_pose_enabled`/`vision_detection_enabled`),
permitindo ligar um sem depender da instalação do outro.

### 3.2 Áudio

| Aspecto | Detalhe |
| --- | --- |
| Entrada | Áudios de consultas médicas (WAV) |
| Análise acústica (sempre ativa, sem nuvem) | DSP real sobre as amostras PCM: energia RMS por janela, taxa de cruzamento por zero, proporção de pausas, contagem de segmentos de fala |
| Hipóteses geradas | "Possível padrão de fala fragmentada" (proporção de pausas ≥ 50% com ≥ 3 segmentos de fala) e "possível redução de energia vocal" (RMS médio abaixo do limiar) — associáveis a fadiga/dispneia, nunca apresentadas como diagnóstico |
| Transcrição | **Azure AI Speech** (Fast Transcription API), idioma `pt-BR`, síncrona — envia os bytes do áudio direto no corpo da requisição |
| Termos clínicos | Extraídos da transcrição pelo mesmo motor NegEx/ConText usado no texto (negação, temporalidade, certeza, experienciador) |
| Sentimento (contextual) | **Azure AI Language** (`SentimentAnalysis` + `KeyPhraseExtraction`) sobre a transcrição — nunca influencia o risco clínico calculado |

### 3.3 Imagem

| Aspecto | Detalhe |
| --- | --- |
| Entrada | Fotografias clínicas, radiológicas ou documentos digitalizados (PNG/JPEG) |
| Qualidade | Dimensões reais extraídas do arquivo, avaliadas por resolução |
| Categorização | Heurística de cor/textura própria (não é um classificador treinado): `PHOTOGRAPH` / `SCANNED_DOCUMENT` / `RADIOLOGICAL`, com área de maior densidade de borda como aproximação de "região de interesse" |
| Reconhecimento (opcional) | **Azure AI Vision** (Image Analysis) — rótulos genéricos (ex.: "Person", "X-Ray") como achado complementar, nunca substituindo a categorização heurística |
| Guardrail de relevância clínica | Rótulos genéricos (ex.: "Mountain", "Car") marcam o achado como não relevante clinicamente e o excluem das consideranções finais do apoio automático |

### 3.4 Texto

| Aspecto | Detalhe |
| --- | --- |
| Entrada | Texto adicional informado pelo profissional na criação da análise |
| Processamento | Motor NegEx/ConText próprio: identifica termos clínicos candidatos com negação, temporalidade, certeza e experienciador |
| Sentimento (contextual) | Azure AI Language, mesmo adaptador do áudio |

### 3.5 Consolidação de risco (LLM)

| Aspecto | Detalhe |
| --- | --- |
| Modelo | OpenAI (GPT, ex.: `gpt-4o-mini`) via adaptador com JSON Schema estrito, ou template determinístico local (padrão, sem chamada de rede) |
| Papel | Síntese e explicação textual dos achados **já calculados** pelo motor de regras — nunca decide nem altera o nível de risco |
| Entrada minimizada | Recebe apenas uma allowlist de campos estruturados já minimizados, nunca mídia bruta nem identificadores diretos |
| Falha | `LlmCallStatus.FAILED`/`SKIPPED` nunca bloqueia o registro clínico — o risco determinístico já foi calculado antes da chamada ao LLM |

---

## 4. Motor de regras determinístico e resultados

O risco clínico é **sempre** calculado por regras versionadas
(`ClinicalRuleSet`), nunca por LLM ou estatística. Cada regra tem uma
condição (`when`, avaliada por um interpretador de expressões seguro,
sem `eval` genérico), um `risk_level` (1 a 6) e um rótulo. Quando
múltiplas regras casam, prevalece o `risk_level` mais alto.

### 4.1 Exemplo real — pressão arterial (`clinical_rules/seeds/blood_pressure.yaml`)

| Faixa | Classificação | Nível de risco |
| --- | --- | --- |
| Sistólica ≤ 90 mmHg | Hipotensão grave | 6 (Crítico) |
| Sistólica 111–119 e diastólica < 80 | Normal | 1 (Baixo) |
| Sistólica 120–129 e diastólica < 80 | Pressão elevada | 3 (Moderado) |
| Sistólica 140–180 ou diastólica 90–120 | Hipertensão estágio 2 | 4 (Alto) |
| Sistólica > 180 ou diastólica > 120 | Crise hipertensiva | 6 (Crítico) |

### 4.2 Exemplo real — SpO2 (`clinical_rules/seeds/spo2.yaml`)

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

Quando não há regra aplicável ou faltam dados obrigatórios, o resultado
é explicitamente **inconclusivo** — nunca tratado como "normal" por
omissão.

### 4.3 Detecção de anomalias em séries temporais (monitoramento preventivo)

Distinta do motor de regras: avalia cada nova observação de sinal vital
contra o **histórico recente do próprio paciente**, gerando um alerta
consultivo separado (nunca altera o risco calculado pelo motor de
regras).

Dois critérios independentes (`app/anomaly_detection/detection.py`):

1. **Desvio de baseline**: média/desvio-padrão das últimas leituras
   (mínimo 3 amostras); dispara em `MODERATE` (≥ 2σ), `HIGH` (≥ 3σ) ou
   `CRITICAL` (≥ 4σ).
2. **Variação abrupta (rate-of-change)**: mudança absoluta entre leituras
   consecutivas dentro de uma janela de tempo — ex.: frequência cardíaca
   subindo ≥ 40 bpm em até 30 minutos dispara `HIGH`, independentemente
   do desvio de baseline.

**Exemplo de anomalia detectada:** paciente com histórico estável de
SpO2 em torno de 97% (desvio-padrão baixo); uma nova leitura de 88%
ultrapassa 4 desvios-padrão da baseline → alerta `CRITICAL` criado
automaticamente, com evidência anexada (`baseline_mean`,
`baseline_stddev`, `deviation_sd`) e ação esperada registrada
("Acionar a equipe assistencial imediatamente; considerar avaliação
médica urgente"). O alerta fica visível em
`GET /patients/{id}/alerts` e pode ser reconhecido, escalado ou
resolvido pela equipe (`POST /alerts/{id}/acknowledge|escalate|resolve`).

Sinais cobertos: frequência cardíaca, frequência respiratória, SpO2,
temperatura, pressão arterial (sistólica e diastólica) e débito urinário.

**Limitação conhecida, documentada no próprio código:** evolução de
prescrições e padrões de movimentação do paciente ao longo do tempo
não têm detecção de anomalia implementada — exigiriam, respectivamente,
uma base farmacológica estruturada (doses, interações, alergias) e um
mecanismo de agregação longitudinal de achados de pose entre múltiplas
análises de vídeo, nenhum dos quais existe hoje. Registrado como lacuna
conhecida, não fingido.

---

## 5. Entrega de alertas à equipe médica

Alertas de anomalia e achados clínicos ficam disponíveis via API/tela
para consulta pela equipe assistencial (médico/enfermeiro, sujeito a
vínculo assistencial com o paciente ou acesso de emergência
"break glass" auditado). **Não há push/e-mail/WebSocket** — a entrega é
por consulta (pull), consistente com a decisão de escopo "análise sob
demanda" do MVP. Notificação em tempo real fica registrada como evolução
futura.

---

## 6. Segurança, privacidade e auditoria (resumo)

- Isolamento multi-tenant: `institution_id` sempre derivado do servidor, nunca aceito do cliente.
- RBAC por papel (médico, enfermeiro, administrador técnico/clínico, auditor) + vínculo assistencial por paciente.
- Auditoria append-only com cadeia de hash verificável (`app.audit`), cobrindo autenticação, autorização, dados, análises, decisões de IA e revisão.
- Prompt injection: instruções do LLM e dados de entrada são separados e delimitados; testes automatizados verificam que conteúdo clínico não altera a criticidade nem extrai segredos do LLM.
- Nenhum dado real de paciente é usado neste repositório — apenas dados sintéticos.

---

## 7. Stack técnica

| Camada | Tecnologia |
| --- | --- |
| Backend | Python 3.11+, FastAPI, SQLAlchemy, Alembic |
| Frontend | React, TypeScript, Vite |
| Banco de dados | PostgreSQL |
| Fila | Tabela PostgreSQL (`SELECT ... FOR UPDATE SKIP LOCKED`) |
| Armazenamento de mídia | Filesystem local (MVP) |
| Nuvem gerenciada | Azure Cognitive Services (Speech, Language, Vision) |
| LLM | OpenAI (opcional) ou template determinístico local |
| Visão computacional de vídeo | OpenPose + YOLOv8, worker self-hosted em CPU |
| Testes | Pytest (backend), Vitest (frontend) |
| Containerização | Docker + Docker Compose |

---

## 8. Como reproduzir os resultados

Ver [`MANUAL_EXECUCAO.md`](MANUAL_EXECUCAO.md) para o passo a passo
completo. Resumo:

```bash
make setup                                   # instala dependências, cria .env
make compose-up                              # sobe o PostgreSQL local
cd backend && uv run alembic upgrade head     # aplica as migrations
cd backend && uv run uvicorn app.main:app --reload   # API em :8000
cd frontend && npm run dev                    # SPA em :5173
make worker                                   # processa a fila (uma iteração)
```

Para exercitar os adaptadores reais do Azure (em vez do modo `LOCAL`,
padrão sem nenhuma credencial), configurar no `.env`:

```bash
TRANSCRIPTION_PROVIDER=AZURE_SPEECH
AZURE_SPEECH_KEY=...
AZURE_SPEECH_REGION=...
```

E, na tela `/admin/feature-flags`, ligar `sentiment_analysis_enabled`
(com `AZURE_LANGUAGE_KEY`/`AZURE_LANGUAGE_ENDPOINT` no `.env`) e/ou
`image_recognition_enabled` (com `AZURE_VISION_KEY`/`AZURE_VISION_ENDPOINT`).
