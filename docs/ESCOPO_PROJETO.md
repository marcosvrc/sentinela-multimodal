# SentinelHealth — Escopo do Projeto

## 1. Visão Geral

**Nome do sistema:** SentinelHealth  
**Tipo:** Sistema hospitalar de apoio a análises clínicas com inteligência artificial multimodal  
**Contexto:** Monitoramento contínuo de pacientes por meio de dados multimodais (áudio, vídeo, imagem e texto) para identificação precoce de sinais de risco clínico.

**Natureza do produto:** sistema de apoio à decisão clínica. O SentinelHealth não realiza diagnóstico autônomo, não substitui a avaliação de profissionais habilitados e não deve executar condutas terapêuticas sem confirmação humana.

**Escopo inicial (MVP):** análise sob demanda de dados e arquivos enviados por um profissional. Monitoramento contínuo e alertas em tempo real constituem evolução posterior e dependem de integração validada com dispositivos e prontuário hospitalar.

**População inicial:** pacientes adultos. Pediatria, gestação e outras populações com referências clínicas próprias ficam fora do MVP até que existam protocolos específicos aprovados.

---

## 2. Desafio

O hospital já possui IA integrada aos processos médicos (análise de exames, documentos e apoio a decisões clínicas). O próximo passo é o monitoramento contínuo e multimodal dos pacientes.

O sistema deve ser capaz de:

- Analisar vídeos de cirurgias ou sessões de fisioterapia para identificar padrões anômalos
- Processar gravações de voz de pacientes em consultas, detectando sintomas relacionados à fala (fadiga, disartria)
- Detectar anomalias em sinais vitais, prescrições e evolução clínica; no MVP, gerar alertas no fluxo sob demanda
- Integrar todos os processamentos com serviços gerenciados em nuvem (AWS)

---

## 3. Objetivo

- Realizar a análise e fusão de diferentes tipos de dados médicos (texto, áudio, vídeo, imagem)
- Utilizar serviços em nuvem para ampliar a capacidade de processamento e inteligência
- Aplicar técnicas de detecção de anomalias para monitoramento preventivo, preparando evolução futura para tempo real
- Apresentar resultados explicáveis, rastreáveis e sujeitos à validação do profissional responsável
- Preservar privacidade, confidencialidade, integridade e disponibilidade dos dados de saúde

## 3.1 Princípios de Segurança Clínica

- O risco clínico será calculado por regras determinísticas, versionadas e aprovadas; o LLM não será a fonte de verdade da classificação.
- O profissional deverá visualizar dados de origem, regras acionadas, resultados dos modelos e limitações antes de confirmar o relatório.
- Resultados com baixa confiança, dados conflitantes ou informações obrigatórias ausentes serão marcados como **inconclusivos** e não como normais.
- Falhas de AWS, OpenAI ou dos modelos multimodais não podem impedir o registro clínico nem ocultar alertas determinísticos já identificados.
- Toda classificação representa apoio à triagem e deve seguir o protocolo institucional vigente.

---

## 4. Entregas Técnicas Obrigatórias

### 4.1 Análise de Vídeo

| Aspecto       | Detalhe                                                                 |
| ------------- | ----------------------------------------------------------------------- |
| Entrada       | Vídeos clínicos (sessões de fisioterapia, cirurgias gravadas)           |
| Processamento | Detecção de movimentos ou eventos fora do padrão esperado               |
| Modelos       | OpenPose (análise postural) + YOLOv8 (detecção de objetos/áreas críticas) |
| Saída         | Evidências temporais e relatório preliminar de possíveis desvios, sujeito à revisão humana |

Os modelos devem informar versão, confiança, limitações, trecho/frame usado como evidência e protocolo de referência. Inferências como dor, confusão, sangramento ou erro procedimental não poderão ser tratadas como diagnóstico apenas com base no vídeo.

**Decomposição técnica do vídeo:**

```text
Vídeo
├── Quadros/segmentos selecionados → processamento visual
├── Faixa de áudio → transcrição e análise acústica autorizada
├── Movimento ao longo do tempo → modelo temporal
└── Metadados → duração, resolução, FPS, câmera e qualidade
```

O processamento deverá correlacionar eventos ao longo do tempo, preservando timestamp inicial/final, segmentos, frames e trajetórias que sustentem cada achado. Não será permitido classificar cada frame isoladamente e apenas concatenar os resultados como se representassem um único evento clínico.

### 4.2 Análise de Áudio

| Aspecto       | Detalhe                                                                          |
| ------------- | -------------------------------------------------------------------------------- |
| Entrada       | Áudios de consultas médicas                                                      |
| Processamento | Detecção de alterações vocais indicativas de condições médicas (cansaço, dispneia) |
| Serviço AWS no MVP | Amazon Transcribe padrão, batch, idioma `pt-BR`                              |
| Saída         | Transcrição, termos clínicos candidatos e rascunho de nota clínica para revisão   |

Análise de sentimento, quando utilizada, será apenas contextual e nunca determinará risco clínico. Alterações vocais deverão ser apresentadas como observações ou hipóteses, não como diagnóstico.

### 4.3 Análise de Texto Clínico

O processamento textual deverá considerar, quando aplicável:

- Negação: presente, ausente ou incerta;
- Temporalidade: atual, passado, futuro, início, duração ou resolvido;
- Certeza: confirmado, suspeito, possível ou condicionado;
- Experienciador: paciente, familiar, acompanhante ou terceiro;
- Fonte: paciente, profissional, transcrição ou documento;
- Seção/contexto do documento;
- Conflitos entre registros e versões.

Exemplo: “paciente apresenta dor”, “paciente nega dor”, “apresentou dor ontem” e “histórico familiar de dor” deverão produzir representações diferentes. A confiança de extração textual não deverá ser apresentada como certeza clínica.

### 4.4 Análise de Imagem

Imagens deverão ser classificadas por categoria e encaminhadas ao processador específico configurado. Um único modelo genérico não será considerado adequado para fotografia clínica, documento digitalizado e imagem radiológica.

No MVP, as categorias efetivamente suportadas serão definidas e validadas antes da implementação. Categorias não suportadas deverão ser rejeitadas ou marcadas como inconclusivas, sem tentativa de diagnóstico genérico.

**Saída mínima:** área ou elemento de interesse, localização aproximada, evidência visual, qualidade, modelo/versão, limitações e recomendação de revisão especializada. Imagens sem laudo ou sem modelo validado deverão ser encaminhadas para profissional da especialidade, sem conclusão diagnóstica automática.

Integrações futuras com imagens radiológicas deverão considerar DICOM, estudo/série, metadados e PACS, fora do caminho crítico do MVP.

### 4.5 Detecção de Anomalias

Aplicar técnicas de detecção de anomalias em:

| Domínio                     | Exemplos                                            |
| --------------------------- | --------------------------------------------------- |
| Séries temporais            | Batimentos, pressão arterial, oxigenação             |
| Prescrições                 | Alterações inesperadas no tratamento                 |
| Movimentação do paciente    | Padrões durante a internação                         |

**Saída:** Alertas automáticos para a equipe médica com base nas anomalias detectadas.

Cada alerta deverá conter severidade, evidência, horário, paciente, regra/modelo de origem, confiança quando aplicável e ação esperada. O fluxo deverá registrar reconhecimento, responsável, tempo de resposta, escalonamento e encerramento. Prescrições somente serão analisadas após definição de fontes farmacológicas, interações, doses, alergias e validação farmacêutica/clínica.

### 4.6 Evidência por Achado

Todo achado deverá apontar sua origem e permitir que o profissional compreenda por que ele foi apresentado.

| Campo | Descrição |
| --- | --- |
| Achado | Nome descritivo do sinal ou observação |
| Natureza | Dado estruturado, observação de modelo, hipótese assistida ou decisão profissional |
| Fonte/modalidade | Equipamento, texto, áudio, vídeo, imagem ou regra |
| Valor/evidência | Valor original, trecho, frame, região ou intervalo temporal |
| Data/hora | Momento da medição ou ocorrência |
| Qualidade | Qualidade da fonte/modalidade e fatores de degradação |
| Confiança técnica | Confiança do modelo, quando aplicável; não representa certeza clínica |
| Regra/modelo | Identificador e versão |
| Limitações | Dados ausentes, ruído, contexto e restrições conhecidas |
| Revisão | Pendente, aceito, corrigido ou rejeitado |

Medições recebidas de equipamentos ou inseridas manualmente não receberão “100% de confiança”. Para elas, serão registrados origem, método, qualidade, validação e integridade disponíveis.

---

## 5. Requisitos Funcionais

### 5.1 Cadastro de Pacientes

O sistema deve permitir o cadastro com:

**Dados Pessoais:**

| Campo | Tipo   |
| ----- | ------ |
| Identificador institucional/prontuário | texto |
| Nome | texto |
| Data de nascimento | data |
| Idade na data da análise | calculado |
| Email | texto opcional |
| Sexo registrado ao nascimento | enum configurável |

**Dados Clínicos:**

| Campo               | Unidade |
| ------------------- | ------- |
| Pressão arterial    | mmHg    |
| Altura              | cm      |
| Peso                | kg      |
| Saturação (SpO₂)   | %       |
| Glicemia            | mg/dL   |
| Temperatura corporal | °C     |
| Frequência cardíaca | bpm |
| Frequência respiratória | irpm |
| Dor | escala 0–10 |
| Consciência | ACVPU |

**Campo texto:** Análises iniciais de queixas e informações importantes para avaliação clínica.

Toda observação deverá registrar data/hora, origem, autor, unidade, método/equipamento, qualidade da leitura e contexto aplicável. O cadastro também deverá permitir alergias, medicamentos, diagnósticos relevantes, uso de oxigênio, protocolo clínico aplicável e histórico longitudinal.

Cada tipo de observação terá uma janela de atualidade definida pelo protocolo versionado. Valores fora dessa janela serão apresentados como **desatualizados**, e não como ausentes ou normais. O sistema exibirá horário da medição, tempo decorrido e necessidade de nova coleta. Não será adotado um prazo universal para todos os sinais.

**Campos adicionais obrigatórios para Glicemia:**

| Campo            | Valores Possíveis                                        |
| ---------------- | -------------------------------------------------------- |
| Momento          | Jejum / Antes da refeição / Após a refeição / Aleatória |
| Tipo de paciente | Diabético / Não diabético                                |
| Uso de insulina  | Sim / Não                                                |

### 5.2 Módulo de Autenticação

- Login, senha forte e segundo fator de autenticação para todos os profissionais
- Controle de acesso baseado em papéis, contexto assistencial e menor privilégio
- Perfis mínimos: administrador técnico, administrador clínico, médico, enfermeiro e auditor
- Administradores técnicos não acessam conteúdo clínico por padrão
- Bloqueio por tentativas, expiração de sessão, recuperação segura e trilha de autenticação
- Proibição de contas compartilhadas e identificação individual de contas de serviço
- Provisionamento, mudança de função e desligamento integrados ao processo institucional
- Revogação imediata de sessões após desligamento, bloqueio ou incidente
- Revisão periódica de contas, vínculos, privilégios e acessos inativos

Além do papel, cada autorização deverá considerar instituição, unidade, vínculo assistencial com o paciente, recurso, ação e contexto. O frontend não será fonte de autorização.

**Acesso emergencial (`break glass`):** quando permitido pela instituição, exigirá reautenticação, justificativa, prazo limitado, auditoria destacada, notificação e revisão posterior.

### 5.3 Módulo de Administração

| CRUD                    | Campos                                                  |
| ----------------------- | ------------------------------------------------------- |
| Especialidade médica    | Nome da especialidade                                   |
| Funcionários (médicos)  | Nome, CPF, matrícula, email, especialidade médica       |
| Dados clínicos          | Gestão das referências de dados clínicos                |

Somente o administrador clínico pode publicar referências e regras clínicas. Toda mudança deve possuir versão, justificativa, fonte, aprovador, vigência e possibilidade de rollback.

### 5.4 Módulo de Análise Multimodal

**Fluxo:**

1. Consultar paciente (já vem com dados pessoais, dados clínicos e campo texto preenchidos)
2. Habilitar seção de análise multimodal com importação de:
   - Áudio
   - Vídeo
   - Imagem
   - Campo texto adicional (opcional)
3. Clicar no botão "Realizar Análise" → análise completa de todos os itens fornecidos

O fluxo deve também validar formato, tamanho, malware, qualidade e metadados dos arquivos; permitir cancelamento e reprocessamento; tratar timeout e indisponibilidade; e informar claramente modalidades ausentes ou inconclusivas.

Cada modalidade produzirá uma avaliação de qualidade independente do achado clínico. Essa avaliação deverá informar estado (`adequada`, `moderada`, `insuficiente` ou `inválida`), métricas disponíveis e fatores como ruído, resolução, iluminação, oclusão, duração, perda de frames, idioma ou legibilidade. Qualidade insuficiente poderá impedir a classificação conforme o protocolo e deverá resultar em limitação explícita ou estado inconclusivo.

### 5.5 Consolidação Final com LLM

- Compor todas as modalidades utilizadas (áudio, vídeo, imagem, texto)
- Gerar resumo explicável e rascunho de relatório a partir de resultados estruturados
- Utilizar LLM (GPT da OpenAI) exclusivamente para organização, síntese e explicação dos resultados
- Proibir que o LLM altere silenciosamente valores, criticidade calculada ou conduta protocolar
- Exigir saída estruturada, citações das evidências internas, indicação de incerteza e revisão do profissional
- Registrar modelo, versão, parâmetros, prompt versionado e resposta para rastreabilidade, respeitando a política de retenção

A consolidação deverá preservar a distinção entre:

| Tipo | Definição |
| --- | --- |
| Dado original | Informação recebida de formulário, equipamento, documento ou integração |
| Classificação determinística | Resultado de regra clínica versionada |
| Observação de modelo | Achado técnico derivado de áudio, vídeo, imagem ou texto |
| Hipótese assistida | Possibilidade apresentada para avaliação, sempre não confirmada |
| Diagnóstico registrado | Diagnóstico já informado por fonte clínica autorizada, com proveniência |
| Decisão profissional | Aceite, correção, rejeição ou conclusão do profissional responsável |

O LLM não poderá converter observação ou hipótese em diagnóstico. Hipóteses deverão ser rotuladas como não confirmadas, apontar evidências relacionadas e permanecer separadas da criticidade calculada pelo motor de regras.

### 5.6 Relatório de Resultados

O relatório deve conter:

- Informações consolidadas de todas as análises
- Nível de criticidade
- Classificação dos dados clínicos e das análises multimodais
- Qualidade e limitações de cada modalidade
- Evidências e correlação temporal por achado
- Dados ausentes, conflitantes ou desatualizados
- Separação explícita entre dados, observações, hipóteses e decisão profissional

**Tabela canônica de Classificação de Risco (apresentada ao profissional):**

| Nível | Classificação             | Cor                  | Hex       | Significado              |
| ----: | ------------------------- | -------------------- | --------- | ------------------------ |
| 1 | Baixo | 🟢 Verde | `#2E7D32` | Registrar e seguir rotina |
| 2 | Leve | 🟡 Amarelo | `#F9A825` | Acompanhar ou repetir medição |
| 3 | Moderado | 🟠 Laranja | `#EF6C00` | Solicitar avaliação clínica |
| 4 | Alto | 🔴 Vermelho | `#C62828` | Alertar equipe assistencial |
| 5 | Muito alto | 🟣 Roxo | `#6A1B9A` | Intervenção prioritária |
| 6 | Crítico | ⚫ Vermelho escuro | `#4A0000` | Seguir protocolo de emergência |

A cor não será o único meio de comunicação: nível numérico, rótulo, ícone e texto devem ser exibidos. A categoria técnica **Inconclusivo** não constitui nível de risco e será usada quando não houver evidência suficiente para classificar.

**Estrutura mínima do resultado:**

1. Identificação e contexto da análise;
2. Estado do relatório;
3. Resumo assistido por IA;
4. Risco calculado pelo motor determinístico;
5. Achados determinísticos;
6. Observações derivadas dos modelos;
7. Hipóteses assistidas não confirmadas;
8. Evidências por modalidade e correlação temporal;
9. Inconsistências, dados ausentes ou desatualizados;
10. Qualidade e limitações técnicas;
11. Condutas sistêmicas previstas pelo protocolo;
12. Revisão e decisão do profissional;
13. Proveniência e versões.

**Download:** Deve ser possível exportar o relatório em PDF contendo dados do paciente, médico e análise completa.

### 5.7 Módulo de Histórico de Análises

Exibe informações de:

- Paciente
- Médico ou enfermeiro responsável
- Resultado da análise
- Status de revisão (rascunho, confirmado, corrigido ou cancelado)
- Versões das regras e modelos utilizados

### 5.8 Módulo de Auditoria

**Pesquisa por:** matrícula do profissional, paciente, análise, ação, recurso, resultado, instituição, unidade ou período.

**Dados retornados:**

| Campo              | Descrição                         |
| ------------------ | --------------------------------- |
| Paciente | Identificador pseudonimizado por padrão; revelação controlada quando necessária |
| Ator | Identificador, matrícula, papel, instituição e unidade |
| Evento | Ação, recurso, resultado, justificativa e origem |
| Análise | Evidências por referência, confiança e versões |
| Correlação | `request_id`, `analysis_id`, `workflow_id` e `job_id` quando aplicável |
| Data e hora | Timestamp UTC gerado pelo servidor |

Não se atribuirá "acurácia" a uma inferência individual. O sistema exibirá confiança quando o modelo a fornecer e, separadamente, métricas de validação da versão. O log deve ser íntegro, pesquisável, exportado para armazenamento imutável e acessível apenas aos perfis autorizados. Consultas e exportações da própria auditoria também serão auditadas.

A tela mostrará o mínimo necessário. Nome, conteúdo clínico integral e valores anteriores/posteriores ficarão protegidos por permissão específica e visualização sob demanda. Exportações exigirão justificativa, serão identificadas, terão prazo de expiração e poderão receber marca d'água.

### 5.9 Revisão e Feedback Clínico

- O profissional pode aceitar, corrigir ou rejeitar cada achado, com justificativa.
- Relatórios somente se tornam definitivos após identificação e confirmação do profissional responsável.
- Correções não apagam o resultado original; ambas as versões permanecem auditáveis.
- Feedback clínico não será usado automaticamente para treinamento de modelos sem governança e base legal próprias.

---

## 6. Requisitos Técnicos

### 6.1 Stack de Desenvolvimento

| Camada | Tecnologia / Diretriz |
| --- | --- |
| Backend | Python com FastAPI, contratos OpenAPI e validação por Pydantic |
| Persistência | SQLAlchemy e migrations versionadas com Alembic |
| Frontend | React com TypeScript |
| Estilo | CSS Modules, CSS responsivo e acessível, sem biblioteca visual obrigatória |
| Banco principal | PostgreSQL para dados transacionais, estados, resultados e auditoria append-only |
| Armazenamento de objetos | Amazon S3 para áudio, vídeo, imagem, artefatos intermediários e PDFs |
| Mensageria | Amazon SQS com fila de mensagens não processadas (DLQ) |
| Containers | Docker; imagens separadas para API e workers quando necessário |
| Testes backend | Pytest, testes de integração e contratos de fornecedores |

MongoDB não será uma dependência do MVP. Sua adoção futura exigirá uma necessidade comprovada que não possa ser atendida adequadamente pelo PostgreSQL e pelo armazenamento de objetos.

Os requisitos detalhados de interface, rotas, componentes, responsividade, acessibilidade e contratos de frontend estão definidos em [`ESPECIFICACAO_FRONTEND.md`](./ESPECIFICACAO_FRONTEND.md).

### 6.2 Integrações e Serviços

| Serviço/Ferramenta     | Uso                                              |
| ---------------------- | ------------------------------------------------ |
| Amazon S3 | Armazenamento criptografado de mídias, artefatos e relatórios |
| Amazon SQS | Desacoplamento entre API e processamento assíncrono |
| Orquestrador Python + Amazon SQS | Coordenação do pipeline multimodal no MVP |
| Amazon ECS | Execução da API e dos workers em containers |
| Amazon Transcribe padrão (`pt-BR`, batch) | Transcrição dos áudios armazenados no S3 |
| OpenAI (GPT) | Síntese e explicação de resultados estruturados via adaptador |
| OpenPose | Candidato para análise postural em worker de vídeo |
| YOLOv8 | Candidato para detecção em worker de vídeo/imagem |
| Provedor OIDC | Amazon Cognito em User Pool exclusivo do projeto |
| AWS KMS e Secrets Manager | Chaves de criptografia e segredos de aplicação |
| CloudWatch/OpenTelemetry | Logs, métricas, traces e alertas operacionais |
| HL7 FHIR | Padrão candidato para interoperabilidade futura com prontuários e sistemas hospitalares |

Para a entrega do MVP, Amazon Comprehend Medical e AWS HealthScribe não serão utilizados, pois a cadeia principal opera em português brasileiro e esses serviços não são necessários para demonstrar o fluxo. O Amazon Transcribe padrão será usado em modo batch com `pt-BR`, condicionado a uma prova de conceito de qualidade, latência e custo. Se a prova falhar, o adaptador permitirá substituição sem alterar o domínio.

### 6.2.1 Interoperabilidade Futura com HL7 FHIR

HL7 FHIR permanecerá apenas no roadmap e não será implementado no primeiro MVP.

| Informação | Recurso FHIR candidato |
| --- | --- |
| Paciente | `Patient` |
| Medição clínica | `Observation` |
| Relatório de exame | `DiagnosticReport` |
| Estudo de imagem | `ImagingStudy` |
| Condição registrada | `Condition` |
| Alergia | `AllergyIntolerance` |
| Medicamento | `MedicationRequest` ou `MedicationStatement` |
| Profissional | `Practitioner` |
| Atendimento | `Encounter` |
| Documento | `DocumentReference` |

Antes de implementar a integração deverão ser definidos versão FHIR, perfis, terminologias, identificadores institucionais, provenance, validação, autorização, auditoria e tratamento de erros. O modelo interno do domínio não deverá depender diretamente das classes de uma biblioteca FHIR.

### 6.2.2 Estratégia de Acesso aos Serviços AWS

CLI, SDK, Terraform e chamadas HTTP terão finalidades distintas e não serão tratados como mecanismos intercambiáveis.

| Contexto | Mecanismo obrigatório/preferencial | Finalidade |
| --- | --- | --- |
| Backend e workers | AWS SDK for Python (`boto3`) | Chamadas AWS executadas pela aplicação |
| Frontend para S3 | HTTP `PUT`/`GET` com URL pré-assinada | Transferência direta de mídias e relatórios autorizados |
| Infraestrutura | Terraform AWS Provider | Criar e alterar recursos, políticas e configurações |
| Desenvolvimento local | AWS CLI v2 + IAM Identity Center/perfil | Autenticação, diagnóstico e testes manuais |
| Operação administrativa | AWS CLI v2 ou scripts controlados | Inspeção e ações pontuais autorizadas |
| CI/CD | Terraform e ferramentas AWS com OIDC | Plan, deploy e verificações automatizadas |

#### Uso do SDK na Aplicação

- As chamadas de runtime a S3, SQS, Secrets Manager, Transcribe e demais serviços utilizados serão realizadas com `boto3`.
- O SDK ficará encapsulado em adaptadores de infraestrutura; módulos de domínio dependerão de interfaces como `ObjectStorage`, `MessageQueue`, `WorkflowOrchestrator` e `TranscriptionProvider`.
- Nenhum módulo de domínio importará diretamente `boto3` ou tipos específicos da AWS.
- Clientes do SDK serão criados na inicialização do processo, configurados e reutilizados, evitando criação por item processado sem necessidade.
- Cada cliente terá região explícita, timeouts, política de retry, limite de tentativas e observabilidade configurados.
- Erros do SDK serão convertidos para erros internos estáveis, sem expor mensagens, ARNs, buckets ou detalhes sensíveis ao frontend.
- Operações serão idempotentes quando suportadas e carregarão identificadores de correlação.
- A aplicação não executará comandos `aws` por `subprocess`, shell ou mecanismo equivalente.

#### Frontend e URLs Pré-assinadas

- O frontend não utilizará AWS CLI nem receberá chaves IAM.
- Para upload/download autorizado, a API gerará URL pré-assinada e cabeçalhos obrigatórios; o navegador executará a transferência por HTTP diretamente com o S3.
- A API confirmará e validará o objeto antes de publicá-lo para processamento.
- URLs pré-assinadas não serão persistidas no frontend, logs ou auditoria e respeitarão as regras de segurança de uploads definidas neste documento.

#### Credenciais e Identidade por Ambiente

| Ambiente | Autenticação AWS |
| --- | --- |
| ECS/EC2 em produção | IAM Task Role ou Instance Role com credenciais temporárias |
| Desenvolvimento local | IAM Identity Center/login federado e perfil AWS separado |
| GitHub Actions | OIDC para assumir IAM Role temporária |
| Terraform local autorizado | Perfil federado/temporário específico para infraestrutura |

- Access keys permanentes não serão incluídas no código, `.env`, imagem, repositório ou secrets do CI/CD.
- O `boto3` usará a cadeia padrão de credenciais e obterá automaticamente as credenciais temporárias do IAM Role em produção.
- Perfis locais não serão fixados no código; sua seleção ocorrerá apenas por configuração de desenvolvimento.
- Cada processo terá IAM Role próprio: API, worker de áudio, worker de vídeo/imagem, worker de relatório e orquestrador não compartilharão permissões amplas.
- A `task execution role` do ECS será separada da `task role` utilizada pelo código da aplicação.
- As políticas IAM restringirão ações, buckets/prefixos, filas, segredos, chaves e workflows ao mínimo necessário.

#### Uso da AWS CLI

A AWS CLI v2 será permitida para desenvolvimento, diagnóstico e operações administrativas controladas, por exemplo: validar a identidade ativa, consultar metadados, inspecionar filas e acompanhar logs. Não será dependência da imagem da aplicação nem caminho normal de integração em runtime.

Comandos administrativos deverão utilizar identidade federada, ser executados por pessoal autorizado e, quando alterarem estado, estar associados a procedimento, justificativa e auditoria. Operações recorrentes ou complexas serão implementadas como código testável ou automação versionada, e não como sequência manual de comandos.

### 6.3 Infraestrutura e DevOps

| Item | Descrição |
| --- | --- |
| Docker | Imagens reproduzíveis e imutáveis para API, workers CPU e workers GPU |
| Registro de imagens | Amazon ECR com imagens identificadas pelo commit |
| CI/CD | GitHub Actions para validação, build, scan e implantação |
| IaC | Terraform com módulos, estados remotos, locking e ambientes separados |
| Banco de dados | Alembic para migrations; cargas de referência idempotentes, sem DML manual em produção |
| Entrada HTTP | Application Load Balancer (ALB) para a API no ECS |
| Compute da API | ECS Fargate, sem processamento pesado na requisição HTTP |
| Compute CPU | Workers ECS Fargate para áudio, regras, consolidação e PDF quando compatível |
| Visão computacional no MVP | Worker Docker executando OpenPose/YOLO em CPU sobre amostras pequenas; desempenho não produtivo |
| Compute GPU futuro | ECS sobre EC2 com GPU, fora da entrega obrigatória do MVP |
| Banco AWS | Amazon RDS for PostgreSQL em eventual ambiente de demonstração AWS |
| Rede | VPC, serviços e bancos em sub-redes privadas, entrada por ALB e regras mínimas de Security Group |
| Ambientes | Local, homologação e produção isolados por configuração, credenciais e recursos |
| Arquitetura | Diagramas de contexto, containers, implantação e sequência do pipeline |

### 6.4 Estilo Arquitetural do Backend

O MVP adotará um **monólito modular**, evitando microserviços prematuros. A API e os workers poderão utilizar o mesmo código-base, mas serão executados como processos e imagens independentes quando possuírem perfis diferentes de carga.

| Módulo | Responsabilidade |
| --- | --- |
| API/Controllers | Endpoints, autenticação, validação e contratos HTTP |
| Pacientes | Cadastro, consulta e vínculo com observações clínicas |
| Identidade e Acesso | Usuários, papéis, instituições e autorização |
| Observações Clínicas | Registro original, unidades, contexto e histórico |
| Mídias | Metadados, URLs assinadas, hash, retenção e vínculo com S3 |
| Trabalhos de Análise | Criação, estados, idempotência, cancelamento e reprocessamento |
| Orquestrador | Coordenação das modalidades e dependências do workflow |
| Processadores de Modalidade | Áudio, vídeo, imagem e texto, isolados por interface |
| Motor de Regras | Execução determinística de regras versionadas |
| Consolidador de Risco | Aplicação da política de consolidação aprovada |
| Adaptadores Externos | AWS, OpenAI, armazenamento, mensageria e identidade |
| Relatórios | Composição estruturada e geração do PDF |
| Revisão | Aceite, correção ou rejeição pelo profissional |
| Auditoria | Registro append-only de ações e mudanças |

O domínio não deverá depender diretamente de SDKs da AWS ou OpenAI. As integrações serão acessadas por interfaces, permitindo mocks, substituição de fornecedor, testes de contrato e execução local.

### 6.5 Arquitetura de Persistência

- O PostgreSQL será a fonte de verdade de pacientes, usuários, observações, análises, estados, resultados estruturados, versões e auditoria.
- Arquivos binários não serão armazenados no PostgreSQL. O banco manterá apenas identificador, chave do objeto, hash, tamanho, MIME, estado e metadados.
- O S3 armazenará originais, derivados, evidências, frames selecionados e relatórios, com criptografia, versionamento e política de ciclo de vida.
- Uploads e downloads serão realizados por URLs pré-assinadas de curta duração; o backend não receberá arquivos grandes como intermediário.
- As chaves de objetos serão únicas e não reutilizadas, evitando sobrescrita acidental.
- Eventos de auditoria serão append-only. Correções gerarão novos eventos e não apagarão registros anteriores.
- O isolamento entre instituições utilizará `tenant_id` derivado da identidade autenticada, nunca aceito livremente do frontend, e PostgreSQL Row-Level Security ou mecanismo equivalente.
- Todas as entidades, jobs, objetos e eventos sujeitos a segregação carregarão o contexto da instituição.
- Testes automatizados tentarão acessar recursos de outra instituição, unidade, equipe e paciente.

### 6.6 Processamento Assíncrono

Áudio, vídeo, imagem, geração de PDF e chamadas demoradas a fornecedores não serão executados dentro da requisição HTTP.

**Fluxo técnico:**

1. O frontend solicita a criação da análise.
2. A API cria um `analysis_id` em estado `CREATED`.
3. A API fornece URLs pré-assinadas e o frontend envia os arquivos diretamente ao S3.
4. A API valida os metadados e publica a solicitação na fila SQS.
5. O orquestrador inicia processadores independentes para cada modalidade.
6. Workers gravam resultados estruturados e referências de artefatos.
7. O motor de regras e o consolidador processam os resultados disponíveis.
8. O LLM redige o resumo sem alterar a classificação calculada.
9. O relatório passa para revisão profissional e, depois de confirmado, o PDF é gerado.
10. O frontend acompanha o estado por consulta periódica; notificação push poderá ser adicionada posteriormente.

Mensagens transportarão somente identificadores e metadados mínimos. Mídias e respostas extensas permanecerão no S3 ou PostgreSQL.

### 6.7 Máquina de Estados da Análise

| Estado | Significado |
| --- | --- |
| `CREATED` | Registro criado, aguardando mídias |
| `UPLOADING` | Uploads em andamento |
| `QUEUED` | Solicitação aceita pela fila |
| `PROCESSING` | Uma ou mais modalidades em processamento |
| `PARTIALLY_COMPLETED` | Parte das modalidades terminou e há falhas ou pendências |
| `WAITING_REVIEW` | Resultado consolidado aguardando profissional |
| `COMPLETED` | Relatório confirmado e finalizado |
| `FAILED_RETRYABLE` | Falha transitória que permite nova tentativa |
| `FAILED_FINAL` | Tentativas esgotadas ou erro não recuperável |
| `CANCELLED` | Cancelamento solicitado e efetivado |

Cada modalidade terá estado próprio. A política deverá definir se a consolidação aceita resultado parcial. Transições serão atômicas, idempotentes e auditáveis.

### 6.8 Resiliência das Integrações

Cada adaptador externo deverá implementar:

- Timeout explícito e configurável;
- Retry com backoff apenas para falhas transitórias;
- Chave de idempotência;
- Circuit breaker;
- Limite de concorrência e tratamento de rate limit;
- Registro de latência, custo, fornecedor, modelo e versão;
- Identificador de correlação propagado pelo workflow;
- Fila DLQ para trabalhos que esgotarem as tentativas;
- Reprocessamento manual seguro, sem duplicar resultados definitivos.

O MVP utilizará orquestrador Python próprio baseado em SQS e workers. Step Functions e Celery não farão parte da entrega inicial.

### 6.9 Separação de Cargas

- A API executará somente operações rápidas e não utilizará GPU.
- Workers CPU tratarão regras, texto, áudio compatível, consolidação e PDF.
- O worker de visão executará OpenPose/YOLO em CPU para arquivos pequenos de demonstração; execução em GPU será uma evolução.
- Os workers serão stateless; estado e artefatos permanecerão em PostgreSQL/S3.
- Concorrência, CPU, memória e GPU serão configuradas por tipo de trabalho.
- Processamento interrompido poderá ser retomado ou refeito a partir de etapas persistidas.

### 6.10 Identidade e Segurança Técnica

- Autenticação será delegada ao Amazon Cognito. O ambiente de desenvolvimento poderá usar um User Pool de desenvolvimento ou adaptador local controlado para testes automatizados.
- Tokens de acesso terão curta duração; MFA será obrigatório para todos os profissionais.
- A API verificará autenticação, papel, instituição, unidade, vínculo assistencial, recurso e ação em cada operação.
- O frontend não armazenará credenciais AWS nem será considerado barreira de autorização.
- Serviços usarão papéis IAM distintos e permissões mínimas por recurso e ação.
- Segredos e chaves de API ficarão no Secrets Manager ou serviço equivalente, nunca no código, imagem ou repositório.
- PostgreSQL, workers e serviços internos ficarão em sub-redes privadas; somente o ponto de entrada HTTP será público.
- Todo tráfego utilizará TLS; dados em repouso serão criptografados com KMS ou mecanismo equivalente.
- Uploads passarão por validação de extensão, MIME, assinatura do arquivo, tamanho e varredura antimalware antes do processamento.
- Endpoints públicos terão rate limiting, proteção de aplicação e limites de payload.

**Política de sessão:**

- Definir duração do access token, refresh token e timeout por inatividade;
- Rotacionar refresh tokens e detectar reutilização;
- Revogar sessões em logout, bloqueio, desligamento e incidente;
- Exigir reautenticação para exportação, acesso emergencial e alterações privilegiadas;
- Não incluir CPF, prontuário ou conteúdo clínico em tokens;
- Usar cookies `HttpOnly`, `Secure` e `SameSite` e proteção CSRF quando a arquitetura utilizar cookies;
- Definir limite e visualização de sessões ativas.

**Segurança da API:**

- Validar todas as entradas por schema e rejeitar campos desconhecidos;
- Usar consultas parametrizadas e proteção contra mass assignment;
- Aplicar paginação e limites de tamanho, profundidade e concorrência;
- Restringir CORS por allowlist;
- Aplicar cabeçalhos de segurança e política uniforme de erros;
- Testar IDOR/BOLA em pacientes, análises, mídias, relatórios e eventos;
- Executar testes de isolamento entre instituições e perfis;
- Realizar DAST e teste de intrusão antes da produção.

**Gestão de chaves:**

- Utilizar chaves separadas por ambiente e finalidade quando aplicável;
- Definir rotação, administradores, auditoria de uso e recuperação;
- Criptografar banco, objetos, filas, snapshots, logs e backups;
- Impedir exclusão imediata de chaves e separar administração da aplicação e das chaves.

### 6.10.1 Segurança de Uploads e Mídias

- Buckets serão privados, com bloqueio de acesso público e políticas mínimas por serviço.
- URLs pré-assinadas terão curta duração, chave aleatória, escopo restrito e vínculo com usuário, paciente, análise e modalidade.
- Uploads exigirão tamanho máximo, MIME permitido e checksum; extensão e MIME informado não serão considerados prova suficiente do tipo.
- Arquivos entrarão em bucket/prefixo de quarentena e somente serão promovidos após validação e varredura antimalware.
- Arquivos compactados, poliglotas, incompletos, abandonados ou reprovados terão tratamento e expiração específicos.
- A geração e o uso de URLs, upload, download, promoção, rejeição e exclusão serão auditados.
- URLs pré-assinadas, credenciais e conteúdo integral da mídia não serão registrados em logs.

### 6.11 Observabilidade

API, orquestrador e workers deverão propagar os identificadores `request_id`, `analysis_id`, `workflow_id` e `job_id`. Identificadores clínicos em logs serão pseudonimizados.

**Métricas mínimas:**

- Latência e taxa de erro por endpoint;
- Profundidade da fila e idade da mensagem mais antiga;
- Tempo de espera e processamento por modalidade;
- Número de retries, itens na DLQ e reprocessamentos;
- Taxa de erro, timeout e rate limit por fornecedor;
- Uso de CPU, memória, armazenamento e GPU;
- Custo estimado por análise e por modalidade;
- Quantidade de análises em cada estado;
- Versão dos modelos, regras e aplicação em uso.

Logs serão estruturados e não conterão, por padrão, nome do paciente, prontuário, transcrição, prompt completo, mídia ou resultado clínico integral. Métricas, logs e traces terão retenção e acesso definidos.

**Alertas de segurança mínimos:** logins falhos em volume, MFA recusado, downloads em massa, acesso anômalo a pacientes, uso de `break glass`, tentativas entre instituições, concessão de privilégio, alteração de políticas IAM/S3/KMS, falha de auditoria, arquivos maliciosos, desativação de logs e uso anormal de fornecedores de IA.

### 6.12 CI/CD e Gestão de Versões

| Etapa | Verificações/ações |
| --- | --- |
| Pull request | Formatação, lint, tipos, testes unitários, testes de integração e validação do Terraform |
| Segurança | Scan de dependências, segredos, containers e infraestrutura como código |
| Build | Imagens imutáveis da API e workers, identificadas pelo commit e publicadas no ECR |
| Homologação | Deploy automático, migrations e testes de fumaça/contrato |
| Produção | Aprovação manual, estratégia gradual e verificação pós-deploy |
| Banco | Migrations compatíveis com atualização gradual e plano de recuperação |
| Rollback | Retorno da aplicação, configuração, regra e modelo para versão aprovada anterior |

Modelos, prompts, regras clínicas e aplicação possuirão versões independentes. Um relatório deverá permitir reconstruir exatamente quais versões participaram da análise.

O pipeline também produzirá SBOM, executará SAST, SCA e DAST conforme a etapa, verificará migrations e assinará imagens/artefatos quando suportado. Dependências terão versões fixadas; branches serão protegidas; exceções de vulnerabilidade exigirão responsável, justificativa, aprovação e prazo. O GitHub Actions usará identidade federada/OIDC em vez de credenciais AWS permanentes.

### 6.13 Estrutura Sugerida do Código

```text
backend/
├── app/
│   ├── api/
│   ├── identity/
│   ├── patients/
│   ├── observations/
│   ├── media/
│   ├── analysis_jobs/
│   ├── orchestration/
│   ├── modality_processors/
│   ├── rules_engine/
│   ├── risk_consolidation/
│   ├── reports/
│   ├── review/
│   ├── audit/
│   └── integrations/
├── migrations/
└── tests/

frontend/
├── src/
│   ├── features/
│   ├── components/
│   ├── services/
│   └── types/
└── tests/

infra/
├── modules/
└── environments/
```

Essa estrutura é uma referência e poderá ser simplificada, desde que os limites entre domínio, infraestrutura, integrações e apresentação sejam preservados.

### 6.14 Arquitetura de Auditoria

O registro transacional append-only no PostgreSQL será a primeira camada. Eventos serão exportados de forma assíncrona para armazenamento separado e imutável/WORM, com retenção própria, controle de acesso distinto, verificação de integridade e reconciliação periódica. Uma falha nessa exportação deverá gerar alerta.

**Eventos mínimos:**

| Categoria | Eventos |
| --- | --- |
| Autenticação | Login, falha, MFA, logout, recuperação, bloqueio e revogação |
| Autorização | Acesso permitido/negado, acesso emergencial e tentativa entre instituições |
| Dados | Criação, leitura, alteração, correção, exclusão lógica e mudança de vínculo |
| Arquivos | URL gerada, upload, download, varredura, promoção, rejeição, expiração e exclusão |
| Administração | Usuário, papel, vínculo, configuração, regra clínica, retenção e rollback |
| Análise | Criação, estado, modalidade, modelo, regra, retry, DLQ e reprocessamento |
| IA | Fornecedor, região, modelo, versão do prompt, hash de entrada/saída e resultado |
| Revisão | Aceite, correção, rejeição, justificativa e confirmação do relatório |
| Auditoria | Consulta, revelação de identidade, exportação e alteração de permissão de auditor |

Cada evento conterá identificador, schema versionado, timestamp UTC do servidor, ator, papel, instituição, unidade, ação, recurso, resultado, justificativa e identificadores de correlação aplicáveis. Os relógios da infraestrutura serão sincronizados.

Logs não copiarão indiscriminadamente transcrições, prompts, respostas, imagens, prontuários, tokens ou URLs assinadas. Conteúdo anterior/posterior somente será guardado quando necessário, com proteção e retenção próprias.

### 6.15 Continuidade e Recuperação

- Definir RPO e RTO por PostgreSQL, S3, identidade, auditoria e processamento.
- Manter backups criptografados e cópias imutáveis em conta/papel segregado.
- Restringir exclusão de backups e chaves e registrar todas as operações.
- Testar restauração periodicamente e guardar evidências do teste.
- Incluir regras, prompts, modelos, migrations, configurações e Terraform no plano de recuperação.
- Documentar operação degradada para falha de AWS, OpenAI, região, identidade ou banco.
- Executar exercícios de ransomware, corrupção de dados e indisponibilidade prolongada.
- Garantir que restauração não reative usuários revogados, dados expirados ou configurações inseguras sem revisão.

## 7. Requisitos Não Funcionais

Os valores definitivos serão aprovados antes da produção. Para o MVP, ficam estabelecidos os seguintes critérios mínimos:

| Categoria | Requisito mínimo |
| --- | --- |
| Disponibilidade | Falha de serviço externo deve produzir estado explícito, retry controlado e possibilidade de reprocessamento |
| Desempenho | Tempo por etapa e total registrados; limites por modalidade configuráveis e testados |
| Integridade | Requisições idempotentes e arquivos identificados por hash |
| Assincronismo | Operações pesadas retornam `analysis_id` sem manter conexão HTTP aberta |
| Resiliência | Filas com retry, backoff, DLQ e reprocessamento idempotente |
| Upload | Lista permitida de formatos, limite de tamanho, validação de MIME e varredura antimalware |
| Observabilidade | Logs estruturados sem conteúdo clínico desnecessário, métricas, traces e alertas operacionais |
| Recuperação | Backup criptografado, teste de restauração e definição de RPO/RTO |
| Escalabilidade | API, workers CPU e workers GPU escaláveis independentemente |
| Acessibilidade | Interface navegável por teclado e risco comunicado por texto, número, ícone e cor |
| Compatibilidade | Navegadores e resoluções suportados documentados |
| Qualidade de IA | Métricas por versão, população e modalidade; monitoramento de drift e falsos alertas |
| Testes | Unitários, integração, contrato, carga, segurança, recuperação e validação clínica |
| Segurança de aplicação | SAST, SCA, DAST, testes de autorização/isolamento e pentest antes da produção |
| Auditoria | Eventos completos, armazenamento imutável, reconciliação e alertas de falha |
| Privacidade | Inventário, RIPD, retenção, direitos e fornecedores aprovados antes de dados reais |

Antes da entrada em produção deverão ser definidos numericamente: SLA, RPO, RTO, latência máxima, volume simultâneo, limites de arquivos, sensibilidade mínima para eventos críticos e taxa máxima aceitável de falsos alertas.

## 8. Privacidade, Segurança e LGPD

- Dados de saúde, voz, imagem, vídeo e biometria serão tratados como dados pessoais sensíveis quando vinculados ou vinculáveis a uma pessoa.
- Controlador, operadores, encarregado, finalidades e bases legais devem ser documentados por operação de tratamento.
- Será elaborado Relatório de Impacto à Proteção de Dados Pessoais (RIPD), incluindo fornecedores e transferência internacional.
- Coletar apenas dados necessários; pseudonimizar mídias e identificadores sempre que possível.
- Definir tabela de retenção e descarte para originais, derivados, relatórios, prompts, respostas, logs e backups.
- Criptografar dados em trânsito e repouso, com gestão centralizada de chaves e segredos.
- Segregar ambientes, instituições e pacientes; usar somente dados sintéticos ou adequadamente anonimizados fora de produção.
- Contratos e configurações de AWS/OpenAI devem prever finalidade, suboperadores, localização, retenção, exclusão e resposta a incidentes.
- Deve existir plano de resposta, registro e comunicação de incidentes conforme LGPD e regulamentação da ANPD.
- Direitos dos titulares, sigilo profissional e acesso excepcional devem possuir fluxos documentados e auditáveis.

### 8.1 Inventário de Tratamento

Antes de usar dados reais, será mantido registro das operações de tratamento contendo:

| Campo | Conteúdo mínimo |
| --- | --- |
| Operação e finalidade | O que é feito e por quê |
| Categorias de dados e titulares | Identificação, saúde, voz, imagem, profissionais etc. |
| Base legal | Hipótese aplicável por finalidade, validada pelo responsável jurídico/privacidade |
| Agentes | Controlador, operador, suboperadores e encarregado |
| Fluxo e localização | Origem, destino, países, regiões e transferências posteriores |
| Acesso | Perfis, contexto e justificativa |
| Retenção | Prazo, fundamento, evento inicial e descarte |
| Segurança | Controles técnicos e organizacionais |
| Direitos e riscos | Atendimento aos titulares e resultado do RIPD |

Consentimento não será assumido como base padrão para assistência. Quando utilizado, será específico, destacado, versionado, registrará ciência/revogação e será separado de tratamentos sustentados por outras bases legais.

### 8.2 Minimização, Pseudonimização e Ambientes

- Cada integração receberá somente os campos necessários à sua finalidade.
- Dados de identificação serão removidos ou substituídos antes do envio a modelos sempre que possível.
- A tabela de correspondência da pseudonimização terá acesso separado.
- Dados pseudonimizados continuarão sendo tratados como dados pessoais.
- Voz, rosto e vídeo não serão considerados anônimos apenas pela remoção de nome ou prontuário.
- Produção não será copiada integralmente para desenvolvimento, teste ou suporte.
- Dados sintéticos serão a opção padrão fora de produção; exceções exigirão aprovação, minimização, prazo e auditoria.

### 8.3 Retenção e Exclusão

Será aprovada uma tabela por categoria, cobrindo cadastro, observações, mídias originais, derivados, transcrição, resultados, prompt/resposta, rascunhos, relatórios, auditoria, logs, backups, quarentena, uploads incompletos e DLQ.

Cada regra definirá prazo, fundamento, evento inicial, responsável, método de exclusão, exceções, `legal hold` e evidência da execução. A exclusão deverá considerar PostgreSQL, versões do S3, caches, índices, filas, backups e fornecedores. Expiração não será implementada apenas como exclusão lógica.

### 8.4 Direitos dos Titulares e Transparência

O processo deverá permitir recebimento, autenticação do solicitante, localização dos dados, análise de exceções, aprovação, resposta, comunicação aos operadores e comprovação de prazo.

Serão preparados avisos de privacidade adequados para pacientes, profissionais e administradores, descrevendo finalidades, bases, categorias, áudio/vídeo/imagem, fornecedores de IA, transferências internacionais, retenção, direitos e contato do encarregado. O texto publicado deverá corresponder ao fluxo técnico real.

### 8.5 Fornecedores e Transferência Internacional

Para AWS, OpenAI e demais operadores/suboperadores serão documentados:

- Serviço, finalidade, dados e população envolvidos;
- Países/regiões de armazenamento e processamento;
- Retenção, exclusão e transferências posteriores;
- Mecanismo aplicável do artigo 33 da LGPD e da Resolução CD/ANPD nº 19/2024;
- Cláusulas-padrão ou outro instrumento autorizado;
- Medidas técnicas complementares;
- Obrigações de incidente, auditoria, direitos e encerramento contratual;
- Plano de substituição e exportação/exclusão ao encerrar o fornecedor.

Nenhum novo fornecedor receberá dados reais sem avaliação de segurança, privacidade, contrato, suboperadores, região, retenção e aprovação do controlador.

### 8.6 Resposta a Incidentes

O plano definirá classificação, severidade, papéis, preservação de evidências, contenção, erradicação, recuperação, avaliação de risco/dano, decisão de comunicação e lições aprendidas.

Quando aplicável, o controlador deverá comunicar a ANPD e os titulares no prazo regulatório vigente — atualmente três dias úteis segundo a Resolução CD/ANPD nº 15/2024 — admitindo complementação quando prevista. A decisão de comunicar ou não será fundamentada e auditável.

**Playbooks mínimos:** ransomware; bucket exposto; credencial comprometida; acesso interno indevido; relatório enviado incorretamente; vazamento em fornecedor; mídia publicada; corrupção/exclusão; indisponibilidade; adulteração de modelo/regra; dependência comprometida.

Exercícios de mesa e testes técnicos ocorrerão periodicamente, incluindo restauração e comunicação simulada.

### 8.7 RIPD e Governança

O RIPD será concluído antes de dados reais e revisto quando houver nova modalidade, fornecedor, país, finalidade, população, integração, decisão automatizada ou mudança relevante de risco. Terá responsáveis, aprovação, riscos residuais e plano de tratamento com prazo.

O controlador manterá inventário de ativos, diagrama de fluxo de dados e responsáveis por cada sistema. Segurança, privacidade, jurídico, equipe clínica e engenharia participarão das decisões de alto risco.

### 8.8 Segurança Específica de IA

- Conteúdo clínico, transcrições e documentos serão tratados como dados não confiáveis, nunca como instruções para o modelo.
- Instruções do sistema e dados serão separados e delimitados.
- O LLM receberá allowlist de campos minimizados e produzirá saída por schema rígido.
- O LLM de consolidação não terá acesso livre ao banco, S3, internet ou ferramentas externas.
- Respostas serão validadas e sanitizadas antes de persistência ou renderização.
- Serão testados prompt injection, exfiltração, conteúdo adversarial e tentativa de alterar criticidade.
- Segredos, tokens, URLs assinadas e credenciais nunca entrarão no contexto.
- O sistema registrará template/versionamento e hash do prompt; conteúdo integral terá armazenamento e retenção próprios somente quando necessário.
- Configurações da OpenAI deverão definir projeto exclusivo, chaves por ambiente, região, `store=false` quando aplicável, controles de retenção e compatibilidade com Zero Data Retention quando exigido.
- Recursos que ampliem o compartilhamento, como busca web ou ferramentas externas, ficarão desabilitados para conteúdo clínico salvo aprovação específica.

## 9. Governança Clínica e Regulatória

- Definir propósito pretendido, usuário, população, ambiente, indicações, contraindicações e limitações do produto.
- Avaliar formalmente o enquadramento como Software como Dispositivo Médico segundo a regulamentação vigente da Anvisa, antes de uso assistencial.
- Cada regra clínica deverá indicar fonte, população, exclusões, versão, vigência, responsável e aprovação clínica.
- Mudanças em modelo, prompt, limiar ou regra exigem avaliação de impacto, validação, aprovação e rollback.
- Os modelos serão avaliados por subgrupos relevantes para detectar vieses e degradação de desempenho.
- Resultados experimentais devem ser claramente identificados e não utilizados para conduta clínica.
- O sistema deverá manter plano de gerenciamento de risco, validação clínica e vigilância pós-implantação compatíveis com seu enquadramento.

## 10. Arquitetura de Decisão

1. Validar qualidade, contexto e completude dos dados.
2. Normalizar unidades sem alterar o registro original.
3. Executar regras clínicas determinísticas e versionadas.
4. Executar modelos especializados, preservando evidências e confiança.
5. Correlacionar achados pela linha do tempo, respeitando janela, origem e qualidade.
6. Detectar conflitos, ausência, desatualização e resultados inconclusivos.
7. Consolidar o nível pelo motor de regras aprovado, nunca pelo LLM isoladamente.
8. Usar o LLM para produzir resumo explicável em formato estruturado.
9. Exigir revisão humana antes do relatório definitivo.
10. Registrar toda a cadeia de proveniência e decisão na auditoria.

## 11. Fora do Escopo do MVP

- Diagnóstico ou prescrição autônoma.
- Alteração automática de prontuário, prescrição ou equipamento médico.
- Atendimento pediátrico ou obstétrico sem protocolos próprios.
- Monitoramento contínuo em tempo real e integração direta com dispositivos.
- Identificação biométrica de pacientes ou profissionais por imagem/voz.
- Treinamento automático com dados assistenciais.
- Liberação para uso clínico sem validação e avaliação regulatória.

## 12. Critérios de Aceite do MVP

- A mesma entrada e a mesma versão de regras produzem a mesma classificação determinística.
- O sistema nunca converte dado ausente, inválido ou inconclusivo em resultado normal.
- Todo achado apresenta origem, evidência, horário e versão de regra/modelo.
- O relatório distingue observação, hipótese, classificação, risco e decisão do profissional.
- Cada modalidade apresenta qualidade, limitações e fatores de degradação independentemente da confiança do modelo.
- Achados de vídeo apontam segmentos/frames e preservam correlação temporal.
- O processador textual diferencia negação, temporalidade, certeza, fonte e experienciador nos casos de teste.
- Dados fora da janela do protocolo são marcados como desatualizados e solicitam nova medição quando aplicável.
- Imagens não suportadas ou sem qualidade/modelo adequado não geram diagnóstico e são encaminhadas para revisão especializada.
- Hipóteses assistidas permanecem rotuladas como não confirmadas e não alteram a criticidade determinística.
- Alterações e confirmações são auditáveis sem apagar o histórico.
- A indisponibilidade de uma integração é apresentada de forma explícita e permite reprocessamento.
- Usuários somente acessam pacientes e funções autorizados para seu papel e instituição.
- Dados enviados a terceiros respeitam a configuração de minimização e retenção aprovada.
- Casos clínicos de teste, inclusive limites e conflitos entre sinais, passam pela validação do responsável clínico.
- Upload de mídia ocorre diretamente entre frontend e S3 por URL pré-assinada, sem trafegar o arquivo pelo backend.
- A API retorna rapidamente após criar a análise e não aguarda processamento multimodal síncrono.
- Cada modalidade possui estado próprio e pode ser repetida sem duplicar resultados ou eventos definitivos.
- Falhas transitórias são reenfileiradas; falhas esgotadas chegam à DLQ e podem ser diagnosticadas e reprocessadas.
- A API, os workers CPU e os workers GPU podem ser implantados e escalados independentemente.
- PostgreSQL é a fonte de verdade transacional; mídias e PDFs ficam no S3 e não como campos binários no banco.
- Nenhum módulo de domínio importa diretamente SDKs da AWS ou OpenAI; integrações são acessadas por adaptadores testáveis.
- Logs correlacionam a execução ponta a ponta sem expor conteúdo clínico desnecessário.
- Imagens de container, migrations, modelos, prompts e regras possuem versões rastreáveis.
- O pipeline executa testes e scans antes da implantação e exige aprovação para produção.
- MFA é exigido para todos os profissionais e sessões podem ser revogadas centralmente.
- O acesso a paciente depende de papel, instituição, unidade e vínculo assistencial válido.
- O fluxo `break glass` exige reautenticação, justificativa, prazo, alerta e revisão.
- Testes comprovam que identificadores de outra instituição não podem ser acessados ou inferidos.
- URLs pré-assinadas expiram, não podem sobrescrever objetos e uploads reprovados não chegam aos workers.
- Todo acesso, leitura, alteração, download, exportação, administração e decisão de IA relevante gera evento de auditoria.
- Eventos são exportados para armazenamento imutável e reconciliados; falha de exportação gera alerta.
- Logs e auditoria não contêm tokens, URLs assinadas ou conteúdo clínico integral sem necessidade aprovada.
- Inventário de tratamento, diagrama de fluxo de dados e RIPD estão aprovados antes de dados reais.
- Cada fornecedor possui região, retenção, suboperadores e mecanismo de transferência internacional documentados.
- A tabela de retenção cobre banco, S3, filas, logs, backups e fornecedores e possui teste de exclusão.
- Solicitação de titular pode localizar dados, acionar operadores e registrar o atendimento.
- O plano de incidente contempla avaliação e comunicação no prazo regulatório e foi exercitado.
- Backups imutáveis foram restaurados em teste e atenderam aos RPO/RTO aprovados.
- Testes demonstram que conteúdo clínico não consegue alterar instruções, criticidade ou obter segredos do LLM.
- O LLM não possui acesso livre a banco, objetos, internet ou ferramentas externas.
- SAST, SCA, DAST, SBOM, scan de IaC/container e pentest não possuem achado crítico aberto sem exceção formal.
- Chamadas AWS em runtime utilizam `boto3` encapsulado em adaptadores; a aplicação não invoca AWS CLI por shell ou `subprocess`.
- API, orquestrador e cada tipo de worker utilizam IAM Roles distintos e com permissões mínimas.
- Produção e CI/CD funcionam exclusivamente com credenciais temporárias; não existem access keys permanentes armazenadas.
- O frontend transfere arquivos por HTTP com URLs pré-assinadas e nunca recebe credenciais IAM.
- Terraform é o mecanismo autorizado para alterações reproduzíveis da infraestrutura; mudanças manuais excepcionais são detectadas e reconciliadas.
- Clientes `boto3` possuem região, timeout, retry, correlação e tratamento de erros configurados e testados.

### 12.1 Gate para Início do Desenvolvimento Funcional

O desenvolvimento de funcionalidades de negócio começará após a conclusão do scaffold, dos contratos fundamentais e das decisões P0 descritas abaixo. Antes desse gate, o trabalho deverá se limitar à fundação técnica, provas de conceito e documentação arquitetural.

#### 12.1.1 Scaffold do Repositório

Devem existir e funcionar:

```text
sentinela-multimodal/
├── backend/
│   ├── app/
│   ├── clinical_rules/
│   ├── migrations/
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   ├── tests/
│   └── package.json
├── infra/
│   ├── modules/
│   └── environments/
├── docs/
│   ├── architecture/
│   └── adr/
├── compose.yaml
├── Makefile
├── .env.example
├── .gitignore
└── README.md
```

**Critérios:**

- Backend FastAPI inicia e responde a health/readiness checks;
- Frontend React inicia e consome uma rota pública de health da API;
- PostgreSQL local inicia pelo Compose;
- Primeira migration é aplicada em banco vazio;
- API, frontend e worker possuem imagens Docker reproduzíveis;
- GitHub Actions executa o conjunto mínimo de verificações;
- README documenta setup, comandos e resolução dos problemas comuns.

#### 12.1.2 Configuração e Ambientes

- Criar `.env.example` apenas com nomes, valores seguros e documentação das variáveis.
- Manter `.env` e variações locais fora do versionamento.
- Centralizar a configuração Python em classe tipada, com validação no startup e falha rápida para campos obrigatórios.
- Separar configuração pública, configuração interna e segredos.
- O frontend receberá apenas valores públicos, como URL da API, issuer e client ID OIDC.
- Produção utilizará Task Definition/Parameter Store para configuração não sensível, Secrets Manager para segredos e IAM Roles para credenciais AWS.
- Não armazenar access keys, segredos, database URLs de produção ou chaves OpenAI no repositório, build do frontend ou imagem.
- Definir os ambientes `local`, `test`, `homologation` e `production`, com recursos, credenciais e políticas isolados.
- Manter tabela documentada com nome, tipo, obrigatoriedade, segredo, ambiente, valor padrão e responsável por cada configuração.

#### 12.1.3 Automação Local e Build

O repositório terá uma interface única de comandos, preferencialmente `Makefile` ou `Taskfile`, utilizada também pelo CI/CD.

**Comandos mínimos:**

```text
make setup
make dev
make stop
make format
make lint
make typecheck
make test
make test-integration
make build
make check
make migrate
make migration
make rules-validate
make rules-seed
make compose-up
make compose-down
```

O `pyproject.toml` deverá fixar ferramentas e comandos para instalação, formatação, lint, tipos, testes e build da imagem/pacote Python. O `package.json` deverá oferecer scripts equivalentes para desenvolvimento, formatação, lint, typecheck, testes, build e E2E do frontend.

`make check` será a validação local equivalente ao gate de pull request. A lógica das verificações não deverá existir apenas no YAML do GitHub Actions.

#### 12.1.4 Contratos Fundamentais

Antes dos módulos funcionais deverão estar definidos e versionados:

- OpenAPI inicial;
- Padrão de erros e `request_id`;
- Paginação, ordenação e filtros;
- Autenticação e claims OIDC;
- Modelo de autorização e ações permitidas;
- Enums de estado da análise e de cada modalidade;
- Contrato de criação, upload, confirmação e cancelamento;
- Contrato de resultado, achado, evidência, qualidade, limitação e revisão;
- Contrato dos eventos de auditoria;
- Schema das regras clínicas e arquivos de seed;
- Política de versionamento e compatibilidade dos contratos.

Enums e schemas compartilhados deverão possuir uma única fonte de verdade ou geração automatizada. O frontend não duplicará manualmente regras de transição ou classificação do backend.

#### 12.1.5 Modelo de Dados e Migrations

Antes de implementar CRUDs deverão existir:

- Diagrama entidade-relacionamento;
- Convenção de identificadores;
- Datas armazenadas em UTC;
- Estratégia de concorrência otimista;
- Definição de `tenant_id` e Row-Level Security;
- Entidades de paciente, usuário, vínculo, observação, mídia, análise, modalidade, achado, evidência, revisão, relatório e auditoria;
- Índices e constraints essenciais;
- Migration inicial e teste de upgrade em banco vazio;
- Estratégia de seed idempotente;
- Procedimento de backup/restauração para os ambientes aplicáveis.

#### 12.1.6 Persistência das Regras Clínicas

O arquivo `CLASSIFICACAO_DADOS_CLINICOS.md` permanecerá como referência legível por humanos. A aplicação não deverá interpretar o Markdown diretamente nem persistir todo o documento como uma única regra textual.

As regras operacionais serão representadas em formato estruturado e validável, versionadas em arquivos YAML/JSON e carregadas de forma idempotente no PostgreSQL.

**Entidades mínimas:**

```text
risk_levels
clinical_rule_sets
clinical_rules
clinical_rule_conditions
clinical_rule_actions
clinical_rule_sources
clinical_rule_approvals
clinical_rule_versions
```

Cada conjunto deverá possuir código, versão, população, contexto, status, vigência, fonte, aprovadores e hash do conteúdo. Publicações criarão nova versão imutável; não sobrescreverão regras utilizadas anteriormente.

O fluxo será:

```text
Documento clínico
→ revisão/aprovação
→ YAML ou JSON estruturado
→ validação de schema e casos-limite
→ seed idempotente
→ PostgreSQL
→ publicação controlada
```

O processo disponibilizará comandos para validar, carregar e exportar regras. LLM não converterá automaticamente Markdown em regra publicável.

#### 12.1.7 Decisões Arquiteturais — ADRs

Antes de consolidar a implementação, registrar Architecture Decision Records para:

1. Monólito modular;
2. PostgreSQL como fonte de verdade e ausência de MongoDB no MVP;
3. S3 para mídias e relatórios;
4. SQS e estratégia de retry/DLQ;
5. Orquestrador Python próprio com SQS, sem Step Functions/Celery no MVP;
6. ECS Fargate para API/workers e visão em CPU no MVP, GPU como evolução;
7. Amazon Cognito como provedor OIDC;
8. `uv` com `pyproject.toml` para dependências Python;
9. `npm` com `package-lock.json` para dependências Node.js;
10. Estratégia de testes locais e de contrato com AWS;
11. Formato, versionamento e publicação das regras clínicas;
12. Estratégia multi-tenant e Row-Level Security;
13. Versão/perfis FHIR quando a integração entrar no roadmap;
14. Estratégia de auditoria imutável;
15. Política de retenção e exclusão de mídias/derivados.

Cada ADR informará contexto, decisão, alternativas, consequências, status e data.

#### 12.1.8 Decisões Simplificadas para a Entrega

As seguintes escolhas estão fechadas para evitar bifurcações durante a construção:

| Tema | Decisão do MVP |
| --- | --- |
| Backend | Python + FastAPI |
| Dependências Python | `uv` + `pyproject.toml` + lockfile |
| Frontend | React + TypeScript + Vite |
| Dependências Node | `npm` + `package-lock.json` |
| Estilo | CSS Modules e tokens próprios |
| Banco local | PostgreSQL via Docker Compose |
| Banco AWS | RDS PostgreSQL somente para demonstração implantada |
| Mídias local | Adaptador de filesystem para desenvolvimento/testes |
| Mídias AWS | Amazon S3 |
| Fila local | Adaptador in-memory para testes e worker local controlado |
| Fila AWS | Amazon SQS + DLQ |
| Orquestração | Worker-orquestrador Python próprio |
| Autenticação | Amazon Cognito; adaptador local apenas para testes |
| Entrada AWS | ALB → ECS Fargate |
| Containers | Docker + Docker Compose local; ECR/ECS na AWS |
| Áudio | Amazon Transcribe padrão batch em `pt-BR` |
| NLP médico AWS | Comprehend Medical e HealthScribe fora do MVP |
| Visão | OpenPose/YOLO em CPU com amostras pequenas |
| GPU gerenciada | Fora do MVP |
| LLM | OpenAI via adaptador, apenas síntese/explicação |
| FHIR/PACS/DICOM | Roadmap, fora do primeiro MVP |
| Infraestrutura | Terraform |
| Automação | Makefile chamando `uv`, `npm`, Docker e Terraform |
| Dados | Somente dados sintéticos na entrega e demonstração |

Integrações locais simplificadas não alteram os contratos de domínio. Testes de integração separados validarão S3, SQS, Cognito e Transcribe em uma conta AWS de desenvolvimento quando credenciais estiverem disponíveis.

#### 12.1.9 Documentação de Arquitetura

Criar no mínimo:

- Diagrama de contexto;
- Diagrama de containers/componentes;
- Diagrama de implantação AWS;
- Sequência da análise multimodal;
- Sequência de upload seguro;
- Fluxo de autenticação/autorização;
- Fluxo de auditoria;
- Diagrama de dados/ER;
- Diagrama de fluxo de dados pessoais para o RIPD.

Os diagramas lógicos poderão ser mantidos em Mermaid ou C4 versionável. A vista de implantação poderá ter uma versão de apresentação com ícones oficiais AWS em diagrams.net, mantendo também uma fonte textual ou editável no repositório.

#### 12.1.10 Definition of Done do Gate

O gate será considerado concluído quando:

- Um novo desenvolvedor conseguir executar `make setup` e `make dev` seguindo apenas o README;
- `make check` passar localmente e no GitHub Actions;
- Backend, frontend, PostgreSQL e worker iniciarem no ambiente local;
- Migration e seed de regras executarem duas vezes sem produzir inconsistência;
- Contratos e estados fundamentais estiverem publicados;
- Testes básicos de isolamento, configuração ausente e health check passarem;
- ADRs P0 estiverem aceitos;
- Diagramas mínimos estiverem versionados;
- Nenhum segredo real estiver presente no repositório ou nas imagens.

### 12.2 Gate para Uso com Dados Reais

O uso de dados reais fica bloqueado até que estejam concluídos:

1. Autorização contextual e isolamento entre instituições;
2. Inventário de tratamento, fluxo de dados e RIPD;
3. Tabela de retenção e exclusão ponta a ponta;
4. Contratos e mecanismo de transferência internacional dos fornecedores;
5. Auditoria de leitura/download/administração com cópia imutável;
6. Plano de incidentes, playbooks e exercício inicial;
7. Quarentena e varredura dos uploads;
8. Controles de minimização e retenção em AWS/OpenAI;
9. Proteção e testes contra prompt injection;
10. Backup imutável e restauração comprovada;
11. Testes de autorização, isolamento, vulnerabilidades e pentest;
12. Avisos de privacidade e fluxo de direitos dos titulares.

## 13. Referências Normativas e Técnicas Iniciais

- Lei nº 13.709/2018 — Lei Geral de Proteção de Dados Pessoais (LGPD): <https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm>
- ANPD — Resolução CD/ANPD nº 15/2024 e Comunicação de Incidente de Segurança: <https://www.gov.br/anpd/pt-br/canais_atendimento/agente-de-tratamento/comunicado-de-incidente-de-seguranca-cis>
- ANPD — Transferência Internacional de Dados e Resolução CD/ANPD nº 19/2024: <https://www.gov.br/anpd/pt-br/assuntos/assuntos-internacionais/transferencia-internacional-de-dados>
- ANPD — materiais e guias de segurança e privacidade: <https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes>
- Anvisa — RDC nº 657/2022 e orientações sobre Software como Dispositivo Médico: <https://www.gov.br/anvisa/pt-br/centraisdeconteudo/publicacoes/produtos-para-a-saude/manuais/software-como-dispositivo-medico-perguntas-e-respostas/view>
- Royal College of Physicians — NEWS2: <https://www.rcplondon.ac.uk/projects/outputs/national-early-warning-score-news-2>
- AWS — idiomas suportados no Amazon Transcribe: <https://docs.aws.amazon.com/transcribe/latest/dg/supported-languages.html>
- AWS — Amazon Comprehend Medical: <https://docs.aws.amazon.com/comprehend-medical/latest/dev/comprehendmedical-welcome.html>
- AWS — uploads no S3 com URLs pré-assinadas: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html>
- AWS — workloads com GPU no ECS: <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-gpu.html>
- AWS — filas de mensagens não processadas no SQS: <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html>
- AWS — AWS CLI v2: <https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-welcome.html>
- AWS — credenciais e IAM Roles no Boto3: <https://docs.aws.amazon.com/boto3/latest/guide/credentials.html>
- OpenAI — controles de dados da API: <https://platform.openai.com/docs/models/default-usage-policies-by-endpoint>

As versões e a vigência dessas referências deverão ser verificadas durante a avaliação regulatória e antes de cada liberação do sistema.
