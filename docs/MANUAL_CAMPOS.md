# Manual de Campos e Regras — SentinelHealth

Documento de referência para cada tela do sistema: o que faz, quais
informações armazena, regras de campos e o que cada campo representa.
Complementa o [`MANUAL_USO.md`](MANUAL_USO.md) (navegação tela a tela)
com detalhamento técnico dos campos.

---

## 1. Cadastro de Paciente (`/patients/new`)

**Objetivo:** Registrar um novo paciente no sistema.

| Campo | Tipo | Obrigatório | Regras | O que representa |
| --- | --- | --- | --- | --- |
| Nome completo | Texto | Sim | Mínimo 3 caracteres | Nome civil completo do paciente |
| Prontuário | Texto | Sim | Único por instituição | Identificador institucional (MRN) |
| Data de nascimento | Data | Sim | Não pode ser futura | Data de nascimento (idade é calculada) |
| Sexo registrado | Seleção | Sim | masculino / feminino / prefere não informar | Sexo biológico registrado |
| Altura (cm) | Número | Não | 30–272 cm | Altura em centímetros (faixa fisiológica adulto) |

**Dados armazenados:** `patients` (banco). Nunca usar dados reais — apenas sintéticos.

---

## 2. Edição de Paciente (`/patients/:id/edit`)

Mesmos campos do cadastro. Não permite alterar prontuário após criação.
Alterações geram evento de auditoria.

---

## 3. Observações Clínicas (Tela de Paciente → Registro)

**Objetivo:** Registrar sinais vitais medidos do paciente.

| Tipo de observação | Campos | Unidade | Faixa válida |
| --- | --- | --- | --- |
| Pressão arterial | Sistólica + Diastólica | mmHg | 40–300 / 20–200 |
| Saturação (SpO₂) | Valor | % | 50–100 |
| Frequência cardíaca | Valor | bpm | 20–250 |
| Frequência respiratória | Valor | irpm | 4–60 |
| Temperatura | Valor + Local + Método | °C | 32–43 |
| Glicemia em jejum | Valor + Momento + Tipo paciente | mg/dL | 20–600 |
| IMC | Peso + Altura | kg/m² | Calculado automaticamente |
| Dor | Escala (0–10) + Localização + Início súbito | — | 0–10 |
| Nível de consciência | ACVPU (A/C/V/P/U) | — | Seleção |
| Débito urinário | Valor | mL/h | 0–500 |

**Campos comuns a todas:**
- Data/hora da medição (obrigatório)
- Profissional responsável (preenchido automaticamente pela sessão)

**Regras:**
- Valores fora da faixa fisiológica são rejeitados com erro de validação
- Cada registro gera evento de auditoria
- Observações alimentam o motor de detecção de anomalias (baseline do paciente)

---

## 4. Nova Análise Multimodal (`/analyses/new`)

**Objetivo:** Criar e submeter uma análise com dados multimodais.

| Campo | Tipo | Obrigatório | Regras |
| --- | --- | --- | --- |
| Paciente | Seleção/busca | Sim | Deve ter vínculo assistencial ativo |
| Texto adicional | Texto livre | Não | Se preenchido, passa pela extração de termos clínicos |
| Dados clínicos estruturados | Seleção de sinais vitais + valores | Não | Se informados, alimentam o motor de regras |
| Upload de áudio | Arquivo | Não | WAV, MP3, M4A. Limite de tamanho configurável |
| Upload de vídeo | Arquivo | Não | MP4, MOV. Limite de tamanho configurável |
| Upload de imagem | Arquivo | Não | PNG, JPEG, DICOM. Limite de tamanho configurável |

**Formatos aceitos por modalidade:**

| Modalidade | MIME types aceitos |
| --- | --- |
| Áudio | audio/wav, audio/x-wav, audio/mpeg, audio/mp3, audio/mp4 |
| Vídeo | video/mp4, video/quicktime |
| Imagem | image/jpeg, image/png, application/dicom |

**Fluxo após submissão:**
1. Upload direto ao storage via URL pré-assinada (nunca passa pelo corpo da API)
2. Validação de MIME por assinatura (não confia no header declarado)
3. Status muda para QUEUED → worker processa assincronamente

---

## 5. Revisão da Análise (`/analyses/:id/review`)

**Objetivo:** Revisar os resultados da análise multimodal antes de confirmar.

### Bloco A — Dados clínicos estruturados

| Informação | Fonte | O que representa |
| --- | --- | --- |
| Nível de risco (1–6) | Motor de regras | Classificação calculada sobre sinais vitais |
| Achados determinísticos | Motor de regras | Resultado por código de regra avaliado |

### Bloco B — Dados multimodais

| Informação | Fonte | O que representa |
| --- | --- | --- |
| Termos clínicos | GPT-4o (extração via LLM) | Termos médicos com negação/temporalidade/certeza |
| Transcrição | Azure AI Speech | Texto transcrito do áudio |
| Sentimento | Azure AI Language | Tom emocional do relato (contextual) |
| Análise acústica | DSP local | Energia vocal, pausas, segmentos |
| Contexto visual (imagem) | GPT-4 Vision | Descrição contextual da imagem |
| Análise de vídeo | GPT-4 Vision + YOLOv8 | Sequência temporal + objetos detectados |
| Hipóteses assistidas | Processadores | Sugestões não confirmadas (alteração vocal, ausência) |

### Bloco C — Análise consolidada (IA)

| Informação | Fonte | O que representa |
| --- | --- | --- |
| Risco assistido por IA | GPT-4o | Nível sugerido baseado nos achados multimodais |
| Resumo explicativo | GPT-4o | Texto que explica o porquê da classificação |
| Apoio à análise clínica | GPT-4o | Visão clínica + causas prováveis + direcionamento |

### Ações disponíveis

| Ação | Quando | O que faz |
| --- | --- | --- |
| Confirmar relatório | Status = DRAFT | Muda para CONFIRMED, gera PDF |
| Baixar PDF | Status = CONFIRMED | Download do relatório em PDF |

---

## 6. Histórico de Análises (`/analyses`)

**Objetivo:** Listar todas as análises com filtros.

| Filtro | O que filtra |
| --- | --- |
| Paciente | Nome ou prontuário |
| Profissional | Quem criou a análise |
| Período | Data de criação |
| Status | QUEUED, PROCESSING, WAITING_REVIEW, COMPLETED, FAILED |

---

## 7. Auditoria (`/audit`)

**Objetivo:** Consultar trilha de auditoria imutável.

| Campo | O que representa |
| --- | --- |
| Data/hora | Quando o evento ocorreu |
| Ator | Quem realizou a ação (subject) |
| Papel | Papel do ator (MEDICO, ENFERMEIRO, etc.) |
| Ação | O que foi feito (ex.: PATIENT_CREATED, ANALYSIS_SUBMITTED) |
| Recurso | Entidade afetada (paciente, análise, regra) |
| Resultado | SUCCESS ou ERROR |
| Correlação | ID para agrupar eventos da mesma operação |

---

## 8. Administração

### 8.1 Usuários e papéis (`/admin/users`)

| Campo | Regras |
| --- | --- |
| Nome completo | Obrigatório, min 3 chars |
| Subject externo | Identificador único (X-Dev-Subject no MVP) |
| Papel | MEDICO, ENFERMEIRO, ADMINISTRADOR_TECNICO, ADMINISTRADOR_CLINICO, AUDITOR |
| Ativo | true/false (desativar não apaga) |

### 8.2 Especialidades (`/admin/specialties`)

| Campo | Regras |
| --- | --- |
| Nome | Obrigatório, único |

### 8.3 Funcionários (`/admin/employees`)

| Campo | Regras |
| --- | --- |
| Nome completo | Obrigatório |
| CPF | 11 dígitos, único |
| Matrícula | Única por instituição |
| E-mail | Formato válido |
| Tipo profissional | Médico, Enfermeiro, Técnico, etc. |
| Especialidade | Opcional (seleção dentre as cadastradas) |

### 8.4 Dados clínicos — Regras (`/admin/clinical-rules`)

**Não há CRUD pela interface.** Conteúdo vem de YAML (`clinical_rules/seeds/`).

| Ação | Quem pode | O que exige |
| --- | --- | --- |
| Publicar | Administrador clínico | Aprovador + justificativa |
| Reverter (rollback) | Administrador clínico | Aprovador + justificativa |

### 8.5 Unidades assistenciais (`/admin/care-units`)

| Campo | Regras |
| --- | --- |
| Nome | Obrigatório, único por instituição |

### 8.6 Feature flags (`/admin/feature-flags`)

| Flag | O que controla | Padrão |
| --- | --- | --- |
| `llm_provider_enabled` | Usar OpenAI real vs template local | false |
| `sentiment_analysis_enabled` | Azure AI Language (sentimento) | false |
| `image_recognition_enabled` | Azure AI Vision (rótulos genéricos) | false |
| `vision_detection_enabled` | YOLOv8 (detecção de objetos em vídeo) | false |
| `vision_pose_enabled` | OpenPose (estimativa de pose) | false |
| `auto_clinical_support_enabled` | Gerar apoio clínico automaticamente | false |
| `dicom_service_enabled` | Aceitar uploads DICOM | false |

---

## 9. Papéis e permissões

| Papel | Pacientes | Análises | Auditoria | Administração |
| --- | --- | --- | --- | --- |
| Médico | ✓ | ✓ | — | — |
| Enfermeiro | ✓ | ✓ | — | — |
| Administrador técnico | — | — | ✓ | ✓ (exceto publicar regras) |
| Administrador clínico | — | — | ✓ | ✓ (incluindo publicar regras) |
| Auditor | — | — | ✓ | — |

Acesso a pacientes requer **vínculo assistencial** ativo (ou break glass auditado).

---

## Documentação relacionada

- [`docs/MANUAL_USO.md`](MANUAL_USO.md) — navegação tela a tela
- [`docs/ANALISES_DISPONIVEIS.md`](ANALISES_DISPONIVEIS.md) — detalhamento das análises
- [`docs/COMO_RODAR.md`](COMO_RODAR.md) — instalação e execução
- [`README.md`](../README.md) — visão geral
