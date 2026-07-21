# Manual de Execução — SentinelHealth

Guia passo a passo para colocar o SentinelHealth em funcionamento em uma
máquina local. Cobre desde os pré-requisitos até um fluxo de demonstração
completo (paciente → análise → revisão → laudo em PDF), incluindo o passo
de publicação de regras clínicas exigido pela seção 5.3 do escopo.

Todos os comandos abaixo assumem que o terminal está na raiz do repositório
(`sentinela-multimodal/`), salvo indicação contrária.

---

## 1. Pré-requisitos

| Ferramenta | Versão | Observação |
| --- | --- | --- |
| Python | 3.11 ou 3.12 | Gerenciado por [`uv`](https://docs.astral.sh/uv/) |
| `uv` | atual | Instala o Python e as dependências do backend |
| Node.js | 22+ | Frontend (Vite) |
| npm | atual | Vem com o Node |
| Docker + Docker Compose | atual | Sobe o PostgreSQL local (e, opcionalmente, os containers da API/SPA) |

Verifique rapidamente:

```bash
python3 --version
uv --version
node --version
npm --version
docker --version
docker compose version
```

---

## 2. Obter o código e configurar o ambiente

```bash
git clone <url-do-repositorio> sentinela-multimodal
cd sentinela-multimodal
cp .env.example .env
```

Abra `.env` e confira os valores padrão (já vêm prontos para uso local):

- `DATABASE_URL` aponta para o Postgres do Docker Compose.
- `LLM_PROVIDER=LOCAL`, `TRANSCRIPTION_PROVIDER=LOCAL`, `VISION_PROVIDER=LOCAL`,
  `MEDIA_STORAGE_BACKEND=LOCAL` — todos os adaptadores externos (OpenAI,
  Amazon Transcribe, OpenPose/YOLOv8, S3) começam desligados, usando
  adaptadores locais honestos (nunca inventam resultado; ver seção 6 abaixo).
- Nenhum segredo real é necessário para rodar o projeto localmente.

Não é preciso editar mais nada para o fluxo de demonstração.

---

## 3. Instalar dependências

```bash
make setup
```

Isso roda `uv sync` (backend) e `npm install` (frontend), e cria o `.env`
caso ainda não exista.

---

## 4. Subir o banco de dados

```bash
make compose-up
```

Sobe o container do PostgreSQL (porta `5432`). Confirme com:

```bash
docker compose -f compose.yaml ps
```

---

## 5. Aplicar as migrations

```bash
cd backend
uv run alembic upgrade head
cd ..
```

(ou, de forma equivalente, `make migrate`). Isso cria todas as tabelas,
incluindo a tabela canônica de níveis de risco (`risk_levels`, já
populada pela primeira migration).

---

## 6. Carregar e publicar as regras clínicas

As regras clínicas (pressão arterial, SpO₂, glicemia, frequência cardíaca
etc.) vivem em YAML versionado (`backend/clinical_rules/seeds/`) e são
carregadas no banco de forma idempotente:

```bash
make rules-validate   # valida os YAML contra o schema
make rules-seed        # carrega no PostgreSQL
```

**Importante:** as regras carregadas pelo seed entram em estado `draft`
(rascunho) — isso é intencional. O sistema nunca trata uma regra como
clinicamente aprovada só porque ela foi carregada em banco; a própria
seed avisa isso no terminal ao final da carga. Antes de publicá-las, o
motor de regras não classifica nenhum sinal (toda avaliação retorna
"inconclusivo"). O passo de publicação está na seção 10 deste manual,
depois que a API e um usuário administrador clínico estiverem disponíveis.

---

## 7. Criar instituição e usuários de desenvolvimento

Não há login real neste MVP (autenticação de credencial/MFA fica fora do
escopo — ver `docs/governance/VALIDACAO_ESCOPO.md`). A identidade é resolvida por
um cabeçalho HTTP (`X-Dev-Subject`) que aponta para um usuário já
cadastrado no banco. Crie a instituição e os cinco usuários padrão (um por
papel):

```bash
make seed-dev-data
```

Saída esperada (os valores impressos são os identificadores a usar no
passo 9):

```text
Instituicao de desenvolvimento: <uuid> (Instituicao de Desenvolvimento)

Usuarios de desenvolvimento (cabecalho X-Dev-Subject):
  MEDICO                   X-Dev-Subject: dev-medico
  ENFERMEIRO                X-Dev-Subject: dev-enfermeiro
  ADMINISTRADOR_TECNICO     X-Dev-Subject: dev-admin-tecnico
  ADMINISTRADOR_CLINICO     X-Dev-Subject: dev-admin-clinico
  AUDITOR                   X-Dev-Subject: dev-auditor
```

Guarde esses valores — você vai colar `dev-medico` ou `dev-admin-clinico`
na sessão de desenvolvimento do frontend.

---

## 8. Subir a API, o worker e o frontend

São três processos independentes. Abra três terminais (todos a partir da
raiz do repositório):

**Terminal 1 — API:**

```bash
cd backend
uv run uvicorn app.main:app --reload
```

API disponível em `http://localhost:8000`; documentação interativa em
`http://localhost:8000/docs`.

**Terminal 2 — worker do orquestrador** (processa áudio/vídeo/imagem/texto
de forma assíncrona; sem ele, uma análise fica parada em `QUEUED`):

```bash
cd backend
PYTHONPATH=. uv run python -m scripts.run_orchestrator_worker
```

Deixe rodando em loop contínuo (sem `--once`) durante a demonstração.

**Terminal 3 — frontend:**

```bash
cd frontend
npm run dev
```

SPA disponível em `http://localhost:5173`.

---

## 9. Configurar a sessão de desenvolvimento no navegador

Abra `http://localhost:5173`. No topo da aplicação, o **banner de sessão de
desenvolvimento** pede um `external_subject`. Cole `dev-medico` (do passo
7) para navegar como médico. Troque para `dev-admin-clinico` sempre que
precisar acessar a tela **Administração** (publicação de regras) — o
backend valida o papel em cada chamada, então colar um `subject` sem
permissão resulta em erro `403` nas ações restritas.

---

## 10. Publicar as regras clínicas (obrigatório para classificar risco)

Com a sessão configurada como `dev-admin-clinico`:

1. Vá em **Administração** no menu lateral.
2. Na seção **Dados clínicos (regras)**, cada conjunto carregado no
   passo 6 aparece com status `draft`.
3. Clique em **Publicar**, preencha **Aprovador** e **Justificativa**
   (obrigatórios — ficam registrados na trilha de auditoria) e confirme.
4. O status muda para `published`. Só a partir daqui o motor de regras
   passa a classificar risco para aquele código/população.

Repita para os conjuntos que forem necessários à demonstração (no mínimo
os sinais vitais que você pretende testar, ex.: `blood_pressure`, `spo2`).

Essa mesma tela também permite:
- Cadastrar **especialidades médicas** e **funcionários** (nome, CPF,
  matrícula, email, especialidade).
- **Reverter (rollback)** uma publicação para uma versão anterior, caso
  uma nova versão publicada apresente problema.

---

## 11. Fluxo de demonstração ponta a ponta

Com a sessão como `dev-medico` (ou `dev-enfermeiro`):

1. **Pacientes → Novo paciente**: cadastre um paciente sintético (nunca
   use dados reais — ver seção 13).
2. Abra o paciente e registre uma ou mais **observações clínicas** (ex.:
   pressão arterial, SpO₂) — use valores que cruzem os limiares das regras
   publicadas no passo 10, para ver uma classificação de risco real.
3. **Nova análise**: crie a análise vinculada ao paciente e, se desejar,
   envie arquivos de áudio/vídeo/imagem/texto (upload direto para o
   armazenamento local via URL pré-assinada, sem passar pelo backend).
4. Clique em **Realizar análise**. O estado muda para `QUEUED`; o worker
   do Terminal 2 processa cada modalidade e você acompanha o progresso na
   tela de detalhe da análise (`PROCESSING` → `WAITING_REVIEW`).
5. Em **Revisão**, confira o resumo assistido por IA (template
   determinístico local, já que `LLM_PROVIDER=LOCAL`), o risco calculado
   pelo motor de regras, os achados por modalidade e as limitações
   declaradas. Aceite, corrija ou rejeite achados e confirme o laudo.
6. Baixe o **PDF** do relatório confirmado.
7. Em **Histórico**, veja a análise listada com seu status de revisão.
8. Em **Auditoria**, pesquise os eventos gerados por todo o fluxo acima
   (cadastro, upload, avaliação de regra, decisão de IA, revisão,
   confirmação) — a cadeia de hash garante que nenhum evento foi alterado
   silenciosamente.

---

## 12. Verificação e testes

```bash
make check              # lint + typecheck + testes unitarios + validação das regras
make test                # só os testes unitários (backend + frontend)
make test-integration    # testes de integração (Postgres precisa estar de pé)
```

Testes de integração usam `pytest.mark.skipif` e são pulados
automaticamente se o Postgres não estiver acessível — rode `make
compose-up` antes de `make test-integration` para exercitá-los de fato.

Os testes do backend usam um **banco de dados separado** do de
desenvolvimento (`sentinelhealth_test`, no mesmo Postgres do Compose),
porque vários testes gravam dados diretamente (ex.: conjuntos de regras
clínicas) sem limpeza no final — se rodassem contra `sentinelhealth`,
esses dados apareceriam permanentemente nas telas da aplicação (ex.:
"Dados clínicos (regras)" acumulando registros `acs-spo2-<uuid>`). Antes
do primeiro `make test`/`make test-integration` após subir o Postgres:

```bash
make test-db-create    # cria o banco sentinelhealth_test (idempotente)
make test-db-migrate   # aplica as migrations nele
```

`make test`/`make test-integration` já apontam automaticamente para esse
banco (`TEST_DATABASE_URL` no Makefile). Uma trava em
`backend/tests/conftest.py` recusa rodar a suíte se `DATABASE_URL` não
contiver "test" no nome do banco, para evitar rodar `pytest` direto (sem
passar pelo Makefile) contra o banco de desenvolvimento por engano.

---

## 13. Alternativa: tudo via Docker Compose

Para rodar API e frontend também containerizados (sem `uv run`/`npm run
dev` nos terminais 1 e 3):

```bash
docker compose -f compose.yaml up -d
```

Isso sobe Postgres, backend (porta `8000`) e frontend (porta `5173`,
servido via build de produção). Ainda é necessário rodar as migrations,
o seed de regras/dados de desenvolvimento e o worker do orquestrador
separadamente (passos 5, 6, 7 e o Terminal 2 do passo 8), pois nenhum
desses processos é automático dentro dos containers.

---

## 14. Variáveis de ambiente relevantes

| Variável | Padrão local | Efeito |
| --- | --- | --- |
| `LLM_PROVIDER` | `LOCAL` | `OPENAI` exige `OPENAI_API_KEY` real |
| `TRANSCRIPTION_PROVIDER` | `LOCAL` | `AZURE_SPEECH` exige `AZURE_SPEECH_KEY`/`AZURE_SPEECH_REGION` |
| `VISION_PROVIDER` | `LOCAL` | `OPENPOSE_YOLOV8` exige o worker de vídeo com `ffmpeg`/modelos instalados |
| `DATABASE_URL` | Postgres do Compose | Ajuste se usar um Postgres externo |

Nenhuma dessas integrações reais é necessária para o fluxo de demonstração
deste manual — todos os adaptadores `LOCAL` produzem comportamento honesto
(nunca inventam transcrição, resumo ou achado de visão computacional; ver
`docs/governance/VALIDACAO_ESCOPO.md` para o detalhamento de cada lacuna).

---

## 15. Solução de problemas comuns

**`uv sync` falha ao baixar o interpretador Python.**
Garanta acesso à rede ou instale localmente uma versão compatível (3.11
ou 3.12) e rode `uv python pin 3.11`.

**API não conecta ao Postgres.**
Confirme `docker compose -f compose.yaml ps` (o serviço `postgres` deve
estar `healthy`) e que `DATABASE_URL` no `.env` aponta para
`localhost:5432`.

**Frontend não encontra a API (`ERR_CONNECTION_REFUSED`).**
Verifique `VITE_API_BASE_URL` no `.env` e se `GET http://localhost:8000/health`
responde.

**Análise fica parada em `QUEUED`/`PROCESSING`.**
O worker do orquestrador (Terminal 2, passo 8) precisa estar rodando em
loop contínuo — sem ele, nenhuma modalidade é processada.

**Toda avaliação de regra retorna "inconclusivo".**
As regras carregadas pelo seed começam em `draft`. Publique-as pela tela
Administração (passo 10) com um usuário `dev-admin-clinico`.

**`403 FORBIDDEN_ROLE` ao chamar `/admin/...` ou publicar regras.**
Confirme que a sessão de desenvolvimento está com `dev-admin-tecnico`
(especialidade/funcionário) ou `dev-admin-clinico` (publicação/rollback
de regras) — outros papéis são bloqueados de propósito.

**Migration falha em banco já existente.**
Use `make compose-down` (remove o volume) seguido de `make compose-up` e
rode as migrations do zero.

---

## 16. Documentação relacionada

- [`docs/MANUAL_INSTALACAO.md`](MANUAL_INSTALACAO.md) — configuração de cada integração real (banco, Docker, Azure Speech/Language/Vision, OpenAI/GPT, visão computacional self-hosted).
- [`README.md`](../README.md) — visão geral rápida do repositório.
- [`docs/ESCOPO_PROJETO.md`](ESCOPO_PROJETO.md) — escopo completo do produto.
- [`docs/ESPECIFICACAO_FRONTEND.md`](ESPECIFICACAO_FRONTEND.md) — telas e contratos de frontend.
- [`docs/governance/VALIDACAO_ESCOPO.md`](governance/VALIDACAO_ESCOPO.md) — o que está implementado de fato versus o escopo, seção a seção.
- [`docs/adr/`](adr/) — decisões arquiteturais.
- Nenhum dado real de paciente deve ser usado em nenhum ambiente deste
  repositório — apenas dados sintéticos (ESCOPO_PROJETO.md seção 8.2).
