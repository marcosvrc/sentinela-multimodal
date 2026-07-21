# SentinelHealth — Especificação de Frontend

## 1. Objetivo

Este documento traduz as referências visuais `Image1.png`, `Image2.png`, `Image3.png` e `Image4.png` em requisitos implementáveis para o frontend do SentinelHealth.

As imagens serão utilizadas como inspiração de composição, hierarquia, densidade e responsividade. Não deverão ser copiadas literalmente. Marca, textos, ícones, fotografias e elementos específicos do sistema WellNest deverão ser substituídos por ativos próprios ou licenciados.

## 2. Avaliação das Referências

### Padrões que devem ser aproveitados

- Navegação lateral fixa e compacta no desktop;
- Cabeçalho com título, ações globais, notificações e menu do usuário;
- Fundo muito claro com cartões brancos;
- Azul-marinho para ações primárias e turquesa para seleção e destaques;
- Bordas discretas, cantos arredondados e sombras suaves;
- Tabelas densas com busca, filtros, status e paginação;
- Cards para métricas, detalhes e resumos;
- Layout desktop amplo e adaptação mobile com menu recolhido;
- Hierarquia baseada em título, contexto, ação primária e conteúdo;
- Uso de gráficos somente quando facilitarem comparação ou tendência.

### Elementos que não pertencem ao MVP

- Inventário hospitalar;
- Pagamentos e faturamento;
- Agenda médica completa;
- Mensagens/chat interno;
- Avaliações públicas de médicos;
- Propagandas ou cards de upgrade;
- Redes sociais e elementos promocionais.

Esses itens não devem aparecer na navegação inicial do SentinelHealth.

## 3. Arquitetura de Informação

### Navegação principal

| Item | Rota | Perfis | Objetivo |
| --- | --- | --- | --- |
| Visão geral | `/dashboard` | Médico, enfermeiro, admin clínico | Resumo operacional das análises |
| Pacientes | `/patients` | Médico, enfermeiro | Busca e consulta de pacientes autorizados |
| Nova análise | `/analyses/new` | Médico, enfermeiro autorizado | Selecionar paciente e iniciar análise |
| Histórico | `/analyses` | Médico, enfermeiro | Consultar análises e estados |
| Auditoria | `/audit` | Auditor, admin autorizado | Pesquisar eventos e ações |
| Administração | `/admin` | Administradores | Gerenciar usuários, especialidades e regras |

Configurações pessoais, ajuda e sair ficarão no menu do usuário, e não como itens principais da sidebar.

### Rotas complementares

```text
/login
/forgot-password
/dashboard
/patients
/patients/new
/patients/:patientId
/patients/:patientId/edit
/patients/:patientId/analyses/new
/analyses
/analyses/:analysisId
/analyses/:analysisId/review
/audit
/admin/users
/admin/specialties
/admin/employees
/admin/clinical-rules
/admin/care-units
/profile
/access-denied
/not-found
```

Todas as rotas protegidas devem verificar autenticação e autorização no carregamento. A ocultação de menus é apenas uma conveniência visual; o backend continua sendo responsável pela autorização efetiva.

### Navegação com submenus

A navegação lateral principal admite itens com submenu (inspirado na
composição de "Main Menu" com itens expansíveis das referências visuais,
seção 2). "Administração" é um item de nível superior com um ícone de
expandir/recolher (chevron) e cinco filhos, cada um uma rota própria (não
uma aba dentro de uma única tela):

```text
Administração
├── Usuários e papéis        /admin/users
├── Especialidades           /admin/specialties
├── Funcionários             /admin/employees
├── Dados clínicos (regras)  /admin/clinical-rules
└── Unidades assistenciais   /admin/care-units
```

Regras do submenu:

- O grupo abre automaticamente quando a rota ativa pertence a um de seus
  filhos, e permanece fechado por padrão nas demais rotas;
- Apenas um grupo de submenu fica aberto por vez no desktop, para manter a
  navegação enxuta;
- O item pai nunca navega por si só (não tem `href`/rota própria) — ele
  apenas expande/recolha os filhos;
- No mobile (drawer), os grupos podem permanecer abertos simultaneamente;
- Cada filho ativo é destacado com a cor de seleção (`color-accent-500`);
- Grupos de submenu são um padrão reutilizável (`NavGroup`), não exclusivo
  da Administração — outras áreas futuras podem adotá-lo.

## 3.1 Padrão de CRUD nas telas de administração

Cada tela filha de Administração (Usuários, Especialidades, Funcionários,
Unidades assistenciais) segue o mesmo padrão de tela única com quatro
operações:

- **Inclusão**: botão de ação primária no cabeçalho da tela ("+ Novo") abre
  um modal (`Modal`/`ConfirmDialog` — seção 6) com o formulário de
  cadastro. Não é mais um formulário inline acima da tabela;
- **Consulta**: `DataTable` com paginação (usa `page`/`page_size` que a API
  já retorna em `PageResponse`), sem exigir mais que a página 1;
- **Edição**: ação "Editar" por linha da tabela abre o mesmo modal de
  cadastro, pré-preenchido, chamando a operação de atualização já exposta
  pelo backend;
- **Deleção**: por decisão de arquitetura (trilha de auditoria — nenhum
  registro de instituição, papel, análise ou observação é apagado
  fisicamente), "Excluir" desativa o registro (`active = false`) após
  confirmação em `ConfirmDialog`. O rótulo do botão pode usar o verbo
  "Excluir" na interface, mas o texto do diálogo de confirmação deve
  deixar claro que o registro é desativado e pode ser reativado, nunca
  apagado.

`Dados clínicos (regras)` é uma excessão intencional: o conteúdo vem de
YAML versionado (seed), então não há criação/edição/exclusão de conjunto
de regras pela interface — apenas publicação e reversão (rollback), ambas
com confirmação reforçada (aprovador + justificativa) em `ConfirmDialog`.

## 4. Estrutura Geral da Interface

### Desktop — largura a partir de 1200 px

```text
┌───────────────┬──────────────────────────────────────────────┐
│ SentinelHealth│ Topbar: título, contexto, alertas e usuário │
│               ├──────────────────────────────────────────────┤
│ Navegação     │                                              │
│ lateral       │ Conteúdo da rota                             │
│               │                                              │
│               │                                              │
└───────────────┴──────────────────────────────────────────────┘
```

- Sidebar expandida: 240 px;
- Sidebar recolhida: 72 px;
- Topbar: 64–72 px;
- Conteúdo máximo recomendado: 1440 px;
- Margem do conteúdo: 24–32 px;
- Grid principal: 12 colunas;
- Espaçamento entre cartões: 16–24 px.

### Tablet — 768 a 1199 px

- Sidebar recolhida em ícones ou drawer;
- Cards de métricas em duas colunas;
- Painéis laterais movidos para baixo do conteúdo principal;
- Tabelas com colunas secundárias ocultáveis;
- Filtros dentro de painel expansível.

### Mobile — abaixo de 768 px

- Topbar com botão de menu, título e perfil;
- Navegação em drawer;
- Conteúdo em uma coluna;
- Tabelas críticas convertidas em lista de cards, sem depender de rolagem horizontal extensa;
- Ação primária fixa ou facilmente acessível;
- Modal de tela cheia para formulários e revisão quando necessário;
- Alvos de toque com pelo menos 44 × 44 px.

## 5. Design System Inicial

Os valores abaixo são aproximações inspiradas nas imagens e deverão ser confirmados durante a implementação visual.

### Cores neutras e da marca

| Token | Valor inicial | Uso |
| --- | --- | --- |
| `color-primary-900` | `#0B2D4D` | Botões primários, navegação e títulos fortes |
| `color-primary-800` | `#123B5D` | Hover e elementos secundários escuros |
| `color-accent-500` | `#67DDD8` | Item selecionado e destaques |
| `color-accent-100` | `#DDF8F6` | Fundo suave de seleção |
| `color-background` | `#F4F8F8` | Fundo geral |
| `color-surface` | `#FFFFFF` | Cards, tabelas e modais |
| `color-border` | `#E4EBED` | Divisores e bordas |
| `color-text` | `#172B3A` | Texto principal |
| `color-text-muted` | `#687983` | Texto secundário |
| `color-focus` | `#1565C0` | Contorno de foco acessível |

### Cores clínicas

As cores clínicas devem reutilizar a escala canônica do escopo, sempre acompanhadas por nível, texto e ícone.

| Nível | Token | Cor |
| ---: | --- | --- |
| 1 | `risk-low` | `#2E7D32` |
| 2 | `risk-mild` | `#F9A825` |
| 3 | `risk-moderate` | `#EF6C00` |
| 4 | `risk-high` | `#C62828` |
| 5 | `risk-very-high` | `#6A1B9A` |
| 6 | `risk-critical` | `#4A0000` |
| — | `risk-inconclusive` | `#546E7A` |

### Tipografia

- Família sugerida: Inter, Source Sans 3 ou fonte sans-serif equivalente;
- Texto base: 16 px;
- Texto auxiliar: 14 px;
- Legendas e metadados: 12 px, sem uso para conteúdo essencial;
- Título de página: 28–32 px;
- Título de seção: 20–24 px;
- Peso 600 para títulos e ações; 400–500 para conteúdo.

### Espaçamento e forma

- Escala: 4, 8, 12, 16, 24, 32 e 48 px;
- Raio de campos e botões: 8–10 px;
- Raio de cards: 12–16 px;
- Borda padrão: 1 px;
- Sombras suaves apenas para elevação; não usar sombra como única indicação de limite;
- Altura de inputs: 44–48 px;
- Altura de linhas de tabela: 56–64 px.

### Ícones e imagens

- Adotar uma única biblioteca de ícones com traço consistente;
- Ícones precisam de texto acessível ou `aria-label` quando forem botões;
- Avatares são opcionais; quando ausentes, mostrar iniciais;
- Não usar fotografias de pacientes como requisito para identificação;
- Logo e ilustrações do SentinelHealth deverão ser ativos próprios.

## 6. Componentes Compartilhados

### Estrutura

- `AppShell`;
- `Sidebar`;
- `MobileNavigationDrawer`;
- `Topbar`;
- `PageHeader`;
- `Breadcrumbs`;
- `UserMenu`;
- `NotificationMenu`.

### Dados e feedback

- `DataTable` com ordenação, filtros, paginação e seleção;
- `FilterBar`;
- `SearchField` com debounce;
- `MetricCard`;
- `StatusBadge`;
- `RiskBadge`;
- `EmptyState`;
- `Skeleton`;
- `InlineError`;
- `ErrorState` com ação para tentar novamente;
- `Toast` para confirmação não crítica;
- `Modal` como base de sobreposição (fecha com `Esc`, clique fora e botão
  fechar; foco preso dentro do conteúdo; foco devolvido ao elemento que
  abriu ao fechar; `role="dialog"` e `aria-modal="true"`);
- `ConfirmDialog` construído sobre `Modal`, para ações destrutivas,
  irreversíveis ou que exigem justificativa (desativação de registro,
  publicação/rollback de regra clínica, revogação de sessão);
- `Pagination` para navegação entre páginas de `DataTable`, refletindo
  `page`/`page_size`/`total_pages` de `PageResponse`.

### Formulários

- `TextField`, `NumberField`, `DateField` e `SelectField`;
- `BloodPressureField` com sistólica e diastólica separadas;
- `MeasurementField` com valor, unidade, data/hora e contexto;
- `FormSection`;
- `FieldError` associado semanticamente ao campo;
- `UnsavedChangesGuard`;
- `StepIndicator` para fluxos extensos.

### Mídias e análises

- `FileDropzone` por modalidade;
- `UploadItem` com nome, tipo, tamanho, progresso, hash e remoção;
- `MediaPreview`;
- `AnalysisProgress`;
- `ModalityStatusCard`;
- `EvidenceViewer` para trecho de áudio, frame ou texto;
- `FindingCard`;
- `RiskSummary`;
- `ProfessionalReviewPanel`;
- `AuditTimeline`.

## 7. Especificação das Telas

### 7.1 Login

**Conteúdo:** logo, título, email/matrícula, senha, entrar, recuperar acesso e mensagens de erro.

**Estados:** inicial, enviando, credenciais inválidas, conta bloqueada, MFA necessário e indisponibilidade.

O login não deve revelar se um email existe. Após autenticação, o redirecionamento considera o perfil e preserva somente uma rota interna segura.

### 7.2 Dashboard

Inspirado nos cards e gráficos das referências, porém orientado a análises:

- Análises aguardando revisão;
- Em processamento;
- Concluídas no período;
- Falhas que requerem atenção;
- Distribuição por nível de risco;
- Lista de análises recentes;
- Atalhos para buscar paciente e iniciar análise.

Não mostrar métricas decorativas ou financeiras. Cada card deve abrir sua lista filtrada. Gráficos terão alternativa tabular e filtros de período.

### 7.3 Lista de Pacientes

Adapta diretamente o padrão de tabela da `Image4.png`.

**Colunas desktop:**

- Paciente;
- Prontuário;
- Data de nascimento/idade calculada;
- Última observação;
- Última análise;
- Maior risco recente;
- Status;
- Ações.

**Filtros:** busca por nome/prontuário, status, período da última análise e risco. Não pesquisar automaticamente enquanto houver menos de três caracteres, salvo prontuário exato.

**Ações:** visualizar paciente e iniciar análise. Editar aparece apenas a perfis autorizados.

### 7.4 Cadastro/Edição de Paciente

Organizar em seções:

1. Identificação;
2. Contato;
3. Informações clínicas relevantes;
4. Oxigênio e protocolo aplicável;
5. Observações iniciais.

Regras:

- Data de nascimento em vez de idade editável;
- Salvamento explícito;
- Validação no cliente e servidor;
- Erros do backend associados aos campos;
- Alerta ao sair com mudanças não salvas;
- Confirmação e evento de auditoria após alteração.

### 7.5 Detalhes do Paciente

Adapta a tela de detalhes presente na `Image1.png`:

- Cabeçalho com identificação, prontuário, status e ação “Nova análise”;
- Cards de informações pessoais e contexto clínico;
- Últimas medições;
- Alertas ou condições relevantes;
- Histórico de análises;
- Relatórios disponíveis;
- Timeline de alterações autorizadas.

Dados sensíveis adicionais não devem aparecer por padrão se não forem necessários à tarefa atual.

### 7.6 Nova Análise Multimodal

Usar fluxo em etapas:

1. Selecionar ou confirmar paciente;
2. Revisar dados clínicos/contexto;
3. Adicionar áudio, vídeo, imagem e texto;
4. Revisar arquivos e consentimentos/avisos aplicáveis;
5. Enviar e acompanhar processamento.

Cada modalidade deve informar:

- Formatos aceitos;
- Limite de tamanho;
- Qualidade mínima esperada;
- Progresso de upload;
- Sucesso, falha e opção de tentar novamente;
- Possibilidade de remoção antes da confirmação.

O frontend envia os arquivos diretamente ao S3 por URL pré-assinada. O botão “Realizar análise” somente é habilitado quando os uploads obrigatórios terminarem e os campos mínimos estiverem válidos.

### 7.7 Acompanhamento da Análise

Exibir o estado geral e um card por modalidade:

| Estado backend | Apresentação |
| --- | --- |
| `CREATED` | Preparando análise |
| `UPLOADING` | Enviando arquivos com progresso |
| `QUEUED` | Aguardando processamento |
| `PROCESSING` | Processando, com etapas concluídas |
| `PARTIALLY_COMPLETED` | Resultado parcial e pendências explícitas |
| `WAITING_REVIEW` | Pronta para revisão profissional |
| `COMPLETED` | Finalizada |
| `FAILED_RETRYABLE` | Falha temporária com opção de tentar novamente |
| `FAILED_FINAL` | Não concluída; orientar contato ou nova análise |
| `CANCELLED` | Cancelada |

Não apresentar percentual inventado quando o backend não souber o progresso real. Nesses casos, usar indicador indeterminado e mostrar as etapas concluídas.

### 7.8 Resultado e Revisão

Ordem recomendada:

1. Identificação do paciente e análise;
2. Resumo de risco;
3. Alertas e achados prioritários;
4. Resultados por modalidade;
5. Evidências;
6. Dados ausentes, conflitos e limitações;
7. Texto consolidado;
8. Revisão profissional;
9. Histórico e versões.

O nível de risco deve exibir número, rótulo, ícone, cor e conduta textual. Achados terão ações “Aceitar”, “Corrigir” e “Rejeitar”, com justificativa quando aplicável. A interface deve diferenciar claramente resultado do sistema e decisão do profissional.

O botão de PDF somente fica ativo após a análise estar confirmada ou deve marcar explicitamente o documento como rascunho.

### 7.9 Histórico de Análises

**Colunas:** paciente, responsável, criação, modalidades, estado, risco, revisão e ações.

**Filtros:** paciente, profissional, período, modalidade, estado e risco. Os filtros devem ser refletidos na URL para permitir retorno, compartilhamento interno autorizado e navegação consistente.

### 7.10 Auditoria

Exibir busca por matrícula, paciente, ação, período e análise. A tabela deve mostrar data/hora, ator, papel, ação, recurso, resultado e identificador de correlação.

Detalhes técnicos ou valores anteriores/posteriores ficam em drawer sob demanda. Exportação, se existir, deve exigir permissão específica e ser auditada.

### 7.11 Administração

Cada seção é uma rota própria, acessada pelo submenu "Administração" da
navegação lateral (seção 3.1), nunca abas dentro de uma única tela:

- Usuários e papéis (`/admin/users`);
- Especialidades (`/admin/specialties`);
- Funcionários (`/admin/employees`);
- Referências/regras clínicas (`/admin/clinical-rules`);
- Unidades assistenciais (`/admin/care-units`).

Usuários, Especialidades, Funcionários e Unidades assistenciais seguem o
padrão de CRUD completo da seção 3.1 (inclusão via modal, consulta paginada,
edição via modal, "exclusão" como desativação confirmada). Regras clínicas
não têm inclusão/edição/exclusão pela interface — apenas publicação e
rollback. A publicação de regra deve exibir versão, vigência, responsável e
confirmação reforçada. Administrador técnico não visualiza dados clínicos
por padrão.

## 8. Estados Obrigatórios de Cada Tela

Toda tela que consome API deve possuir estados explícitos:

- Carregando;
- Sucesso com dados;
- Sucesso sem dados;
- Erro recuperável;
- Erro de validação;
- Não autorizado (`401`);
- Acesso negado (`403`);
- Recurso não encontrado (`404`);
- Conflito de versão (`409`);
- Limite excedido (`413` ou `429`);
- Serviço indisponível;
- Sessão expirada.

Skeletons devem preservar aproximadamente a estrutura final. Não usar spinner de página inteira para todas as operações.

## 9. Contratos Necessários do Backend

### Padrão de erro

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Não foi possível salvar os dados.",
  "field_errors": {
    "birth_date": "A data informada é inválida."
  },
  "request_id": "req_01..."
}
```

### Resposta paginada

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total_items": 0,
  "total_pages": 0
}
```

### Criação de análise

```json
{
  "analysis_id": "ana_01...",
  "status": "CREATED",
  "required_uploads": [
    {
      "media_id": "med_01...",
      "modality": "VIDEO",
      "upload_url": "https://...",
      "expires_at": "2028-07-20T12:00:00Z",
      "required_headers": {}
    }
  ]
}
```

### Estado da análise

```json
{
  "analysis_id": "ana_01...",
  "status": "PROCESSING",
  "created_at": "2028-07-20T11:30:00Z",
  "updated_at": "2028-07-20T11:34:00Z",
  "modalities": [
    {"type": "AUDIO", "status": "COMPLETED"},
    {"type": "VIDEO", "status": "PROCESSING"},
    {"type": "IMAGE", "status": "FAILED_RETRYABLE"}
  ],
  "available_actions": ["CANCEL", "RETRY_IMAGE"]
}
```

O backend deve fornecer `available_actions`; o frontend não deve deduzir sozinho quais transições são permitidas.

## 10. Estratégia Técnica do React

### Organização sugerida

```text
src/
├── app/
│   ├── router/
│   ├── providers/
│   └── layouts/
├── features/
│   ├── auth/
│   ├── dashboard/
│   ├── patients/
│   ├── analyses/
│   ├── audit/
│   └── admin/
├── components/
│   ├── ui/
│   ├── forms/
│   ├── data-display/
│   └── feedback/
├── services/
│   ├── api/
│   └── uploads/
├── hooks/
├── styles/
├── types/
└── test/
```

### Responsabilidades de estado

- Estado de servidor: cache de consultas, invalidação e mutations;
- Estado de formulário: valores, validação e campos tocados;
- Estado de rota: filtros, ordenação, página e identificadores;
- Estado local: abertura de drawer, modal e seleção temporária;
- Estado de autenticação: sessão fornecida pelo cliente OIDC;
- Não duplicar respostas da API em um store global sem necessidade.

Bibliotecas poderão ser escolhidas durante a implementação. Opções adequadas incluem React Router, TanStack Query, React Hook Form e validação por Zod, desde que fixadas em versões aprovadas e cobertas por testes.

## 11. Acessibilidade

- Meta mínima: WCAG 2.2 nível AA;
- Navegação completa por teclado;
- Foco visível e ordem lógica;
- Skip link para o conteúdo principal;
- Landmarks semânticos (`header`, `nav`, `main`, `aside`);
- Tabelas com cabeçalhos e descrições adequadas;
- Campos com labels persistentes, não apenas placeholders;
- Mensagens de erro associadas aos respectivos campos;
- Atualizações assíncronas importantes anunciadas por região `aria-live`;
- Contraste mínimo validado para texto e controles;
- Estado clínico nunca comunicado somente por cor;
- Respeitar preferência por redução de movimento;
- Gráficos com resumo textual e acesso aos dados tabulares.

## 12. Segurança no Frontend

- Não persistir tokens sensíveis em `localStorage` quando a estratégia OIDC permitir sessão mais segura;
- Não incluir dados clínicos em URLs, analytics, logs do navegador ou ferramentas de sessão;
- Não renderizar HTML produzido pelo LLM sem sanitização e política explícita;
- Escapar conteúdo textual por padrão;
- Não expor segredos ou credenciais em variáveis incorporadas ao build;
- Limpar estado sensível no logout e na expiração de sessão;
- Desabilitar cache indevido de respostas sensíveis conforme estratégia HTTP;
- Mostrar dados mínimos necessários ao papel e à tela;
- Tratar URLs pré-assinadas como temporárias e não persistir seu valor.

## 13. Testes do Frontend

| Tipo | Cobertura esperada |
| --- | --- |
| Unitário | Funções de formatação, validação e mapeamento de estados |
| Componente | Formulários, tabelas, badges de risco e controles de upload |
| Integração | Fluxos com API simulada e tratamento de erros |
| Contrato | Compatibilidade com OpenAPI e enums do backend |
| E2E | Login, cadastro, upload, acompanhamento, revisão e PDF |
| Acessibilidade | Auditoria automatizada e testes manuais por teclado/leitor de tela |
| Responsividade | Viewports mobile, tablet e desktop definidos |
| Visual | Regressão dos componentes e telas principais |

Casos E2E mínimos:

1. Usuário sem permissão tenta acessar administração;
2. Cadastro rejeita data e medições inválidas;
3. Upload falha, expira e é repetido;
4. Análise transita de fila para revisão;
5. Uma modalidade falha e a análise fica parcial;
6. Sessão expira durante preenchimento;
7. Profissional corrige um achado e confirma o relatório;
8. Usuário navega integralmente por teclado;
9. Risco crítico é compreensível sem depender de cor;
10. Tabela mobile mantém todas as ações essenciais.

## 14. Critérios de Aceite Visual e Funcional

- Layout mantém a linguagem clara, clínica e discreta das referências;
- Navegação contém somente módulos do SentinelHealth;
- Todas as páginas possuem estados de loading, vazio e erro;
- Sidebar funciona expandida, recolhida e como drawer mobile;
- Tabelas preservam busca, filtros e paginação no desktop e tornam-se utilizáveis no mobile;
- Componentes usam tokens, sem cores e espaçamentos arbitrários espalhados pelo código;
- A escala clínica é apresentada consistentemente em todas as telas;
- Uploads exibem progresso e recuperação de falha;
- Estado da análise corresponde exatamente ao backend;
- Ações permitidas são fornecidas pelo backend e respeitadas pela interface;
- Formulários impedem perda acidental de dados;
- A interface atende aos testes essenciais de acessibilidade;
- Não há cópia de marca, imagens, textos ou ativos proprietários das referências.

## 15. Ordem Sugerida de Implementação

1. Tokens, tipografia, ícones e componentes básicos;
2. `AppShell`, sidebar, topbar e rotas protegidas;
3. Autenticação e autorização visual;
4. Lista, cadastro e detalhes de pacientes;
5. Upload e criação de análise;
6. Acompanhamento dos estados assíncronos;
7. Resultado e revisão profissional;
8. Histórico e PDF;
9. Auditoria e administração;
10. Dashboard e gráficos;
11. Revisão de acessibilidade, responsividade e regressão visual.

O dashboard deve ser implementado depois dos fluxos principais, pois seus indicadores dependem dos dados e estados já estabilizados.

