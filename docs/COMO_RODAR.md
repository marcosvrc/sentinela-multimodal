# Como Rodar o Projeto — Windows, macOS e Linux

Guia passo a passo, camada por camada, para colocar o SentinelHealth
rodando localmente em qualquer um dos três sistemas operacionais. Depois
de concluir este guia, siga o
[`MANUAL_EXECUCAO.md`](MANUAL_EXECUCAO.md) para o fluxo de demonstração
completo (cadastro de paciente, análise, revisão e laudo em PDF) e o
[`MANUAL_INSTALACAO.md`](MANUAL_INSTALACAO.md) para configurar
integrações reais (Azure, OpenAI, visão computacional).

---

## 1. Pré-requisitos

| Ferramenta | Versão | Por quê |
| --- | --- | --- |
| Python | 3.11 ou 3.12 | Backend (gerenciado por `uv`, que instala o interpretador certo) |
| [`uv`](https://docs.astral.sh/uv/) | atual | Gerenciador de pacotes/ambiente do backend |
| Node.js | 22+ | Frontend (Vite) |
| npm | atual (vem com o Node) | Gerenciador de pacotes do frontend |
| Git | atual | Clonar o repositório |
| Docker + Docker Compose | atual | PostgreSQL local (e, opcionalmente, a aplicação inteira containerizada) |
| `make` | atual | Interface de comandos do projeto (ver `Makefile`) |

`ffmpeg` só é necessário se você for testar visão computacional de vídeo
real (`VISION_PROVIDER=OPENPOSE_YOLOV8`) — não é preciso para o fluxo
padrão. Ver [`MANUAL_INSTALACAO.md`](MANUAL_INSTALACAO.md) seção 10.

---

## 2. Instalação dos pré-requisitos por sistema operacional

### 2.1 Windows

Recomendado usar **PowerShell** (não é preciso WSL, mas WSL2 com Ubuntu
também funciona e simplifica os comandos abaixo, que ficam idênticos aos
de Linux).

**Opção A — PowerShell nativo:**

```powershell
# Gerenciador de pacotes winget já vem no Windows 10/11 atualizado
winget install Python.Python.3.12
winget install Git.Git
winget install OpenJS.NodeJS.LTS
winget install Docker.DockerDesktop
winget install ezwinports.make
# ou, alternativamente ao make: choco install make (via Chocolatey)

# uv (gerenciador do backend Python)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Abra um **novo terminal** após a instalação para que o `PATH` seja
atualizado. Confirme:

```powershell
python --version
uv --version
node --version
npm --version
git --version
docker --version
docker compose version
make --version
```

Inicie o **Docker Desktop** manualmente pelo menu Iniciar antes de
qualquer comando `docker`/`make compose-up` — no Windows ele não inicia
como serviço em segundo plano por padrão.

**Opção B — WSL2 (recomendado se `make`/scripts derem problema):**

```powershell
wsl --install -d Ubuntu
```

Depois, abra o Ubuntu (WSL) e siga exatamente os comandos da seção 2.3
(Linux) abaixo. O Docker Desktop para Windows já integra com o WSL2
automaticamente (ative em Settings → Resources → WSL Integration).

### 2.2 macOS

Recomendado usar [Homebrew](https://brew.sh):

```bash
# Instale o Homebrew se ainda não tiver
curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh | bash

brew install python@3.12 node git make
brew install --cask docker

# uv (gerenciador do backend Python)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Abra o aplicativo **Docker** (Docker Desktop) uma vez pelo Launchpad para
finalizar a inicialização antes de usar `docker`/`make compose-up`.
Abra um novo terminal (ou rode `source ~/.zshrc` / `source ~/.bashrc`)
para que o `uv` fique disponível no `PATH`.

Confirme:

```bash
python3 --version
uv --version
node --version
npm --version
git --version
docker --version
docker compose version
make --version
```

### 2.3 Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install -y python3 python3-venv git make ca-certificates curl gnupg

# Node.js 22 (via NodeSource)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

# uv (gerenciador do backend Python)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env   # ou abra um novo terminal

# Docker Engine + Compose plugin
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# Saia e entre de novo na sessão (ou rode `newgrp docker`) para o grupo
# fazer efeito sem precisar de sudo em todo comando docker.
```

Distribuições baseadas em RPM (Fedora/RHEL): substitua `apt` por `dnf` e
siga a [documentação oficial do Docker Engine](https://docs.docker.com/engine/install/)
para o passo de instalação do Docker.

Confirme:

```bash
python3 --version
uv --version
node --version
npm --version
git --version
docker --version
docker compose version
make --version
```

---

## 3. Obter o código

Idêntico nos três sistemas:

```bash
git clone <url-do-repositorio> sentinela-multimodal
cd sentinela-multimodal
```

---

## 4. Configurar variáveis de ambiente

```bash
# macOS / Linux
cp .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

Os valores padrão já funcionam para o fluxo local sem nenhuma
credencial externa (todos os adaptadores de nuvem começam em `LOCAL`).
Não é necessário editar nada nesta etapa — ver
[`MANUAL_INSTALACAO.md`](MANUAL_INSTALACAO.md) quando quiser ligar Azure
ou OpenAI de verdade.

---

## 5. Camada 1 — Banco de dados (PostgreSQL via Docker)

Idêntico nos três sistemas (o Docker Desktop no Windows/macOS expõe o
mesmo `docker compose` do Linux):

```bash
make compose-up
```

Confirme que o serviço está saudável:

```bash
docker compose -f compose.yaml ps
```

A coluna `STATUS` do serviço `postgres` deve mostrar `healthy`. Se
`make` não estiver disponível (ex.: Windows sem WSL e sem `make`
instalado), o comando equivalente é:

```bash
docker compose -f compose.yaml up -d postgres
```

---

## 6. Camada 2 — Backend (instalação de dependências + migrations)

```bash
cd backend
uv sync
```

Isso cria um ambiente virtual isolado em `backend/.venv/` e instala
exatamente as versões travadas em `uv.lock` — idêntico nos três sistemas
operacionais, já que o `uv` gerencia o interpretador Python sozinho.

Aplicar as migrations (cria todas as tabelas):

```bash
uv run alembic upgrade head
```

Carregar e validar as regras clínicas (ficam em `draft` até serem
publicadas pela tela de administração — ver o manual de execução):

```bash
uv run python -m clinical_rules.cli validate
uv run python -m clinical_rules.cli seed
```

Criar a instituição e os usuários de desenvolvimento (necessário para
usar o sistema sem um provedor de identidade real):

```bash
PYTHONPATH=. uv run python -m scripts.seed_dev_data
```

No **Windows PowerShell**, `PYTHONPATH=. comando` (sintaxe Unix) não
funciona diretamente — use:

```powershell
$env:PYTHONPATH="."; uv run python -m scripts.seed_dev_data
```

Ou rode os comandos `PYTHONPATH=.` dentro do WSL2/Git Bash, onde a
sintaxe Unix funciona normalmente.

Volte para a raiz do repositório antes do próximo passo:

```bash
cd ..
```

---

## 7. Camada 3 — Subir a API

Em um terminal dedicado (deixe rodando):

```bash
cd backend
uv run uvicorn app.main:app --reload
```

Idêntico nos três sistemas. A API fica disponível em
`http://localhost:8000`, com documentação interativa (Swagger) em
`http://localhost:8000/docs`. Confirme rapidamente:

```bash
curl http://localhost:8000/health
```

No Windows PowerShell, `curl` já é um alias de `Invoke-WebRequest` —
funciona igual, ou use `Invoke-RestMethod http://localhost:8000/health`.

---

## 8. Camada 4 — Subir o worker do orquestrador

Em **outro** terminal dedicado (também precisa ficar rodando; sem ele
nenhuma análise é processada):

```bash
cd backend
PYTHONPATH=. uv run python -m scripts.run_orchestrator_worker
```

**Windows PowerShell:**

```powershell
cd backend
$env:PYTHONPATH="."
uv run python -m scripts.run_orchestrator_worker
```

---

## 9. Camada 5 — Frontend

Em um terceiro terminal dedicado:

```bash
cd frontend
npm install
npm run dev
```

Idêntico nos três sistemas. O SPA fica disponível em
`http://localhost:5173`. O Vite já lê `VITE_API_BASE_URL` do
`.env`/`.env.example` (padrão: `http://localhost:8000`).

---

## 10. Verificação final

Com os três processos rodando (API, worker, frontend) e o Postgres de
pé, acesse `http://localhost:5173` no navegador. A tela inicial deve
carregar sem erro de conexão. Nesse ponto, siga
[`MANUAL_EXECUCAO.md`](MANUAL_EXECUCAO.md) a partir da seção 9
(configurar a sessão de desenvolvimento e publicar as regras clínicas)
para o fluxo completo de demonstração.

---

## 11. Resumo de comandos (depois do primeiro setup)

Depois da primeira instalação, o dia a dia para religar tudo é:

```bash
make compose-up                                      # Postgres

# Terminal 1
cd backend && uv run uvicorn app.main:app --reload

# Terminal 2
cd backend && PYTHONPATH=. uv run python -m scripts.run_orchestrator_worker

# Terminal 3
cd frontend && npm run dev
```

Ou, de forma equivalente e resumida (o `Makefile` já orienta os três
comandos acima):

```bash
make setup   # só na primeira vez (instala dependências, cria .env)
make dev     # sobe o Postgres e imprime os comandos dos terminais 1-3
```

---

## 12. Alternativa: tudo containerizado (sem instalar Python/Node localmente)

Se preferir não instalar Python/Node/`uv` na máquina host, rode a
aplicação inteira via Docker Compose (idêntico nos três sistemas, desde
que o Docker esteja instalado):

```bash
docker compose -f compose.yaml up -d --build
```

Sobe Postgres (`5432`), backend (`8000`), worker (processamento
contínuo) e frontend (`5173`, build de produção via Nginx). Migrations e
seed de regras/dados de desenvolvimento **não** sobem automaticamente
com os containers — rode-os manualmente uma vez, apontando para o
Postgres do compose:

```bash
cd backend
uv run alembic upgrade head
uv run python -m clinical_rules.cli seed
PYTHONPATH=. uv run python -m scripts.seed_dev_data
cd ..
```

(esses três comandos exigem `uv`/Python instalados localmente mesmo no
modo containerizado — eles se conectam ao Postgres do compose via
`localhost:5432`, não rodam dentro de um container).

---

## 13. Solução de problemas por sistema operacional

**Windows — `make` não é reconhecido.**
Instale via `winget install ezwinports.make`, via Chocolatey
(`choco install make`), ou rode os comandos equivalentes listados no
`Makefile` diretamente (cada alvo é auto-explicativo), ou use WSL2.

**Windows — `uv` não é encontrado depois da instalação.**
Abra um **novo** terminal (o instalador atualiza o `PATH`, mas terminais
já abertos não recarregam automaticamente).

**Windows — Docker Desktop "Cannot connect to the Docker daemon".**
Abra o Docker Desktop manualmente e aguarde o ícone da barra de tarefas
indicar que o daemon está pronto antes de rodar `make compose-up`.

**macOS — `docker compose` diz "command not found" mas `docker` existe.**
Você tem uma instalação antiga do Docker CLI standalone sem o plugin
Compose v2. Reinstale via `brew install --cask docker` (Docker Desktop
já inclui o plugin) em vez de `brew install docker` isolado.

**macOS (Apple Silicon) — `ultralytics`/dependências de visão demoram para instalar.**
Normal na primeira vez (compilação de dependências nativas). Só afeta
quem rodar `uv sync --group vision` (visão computacional real de
vídeo) — não é necessário para o fluxo padrão.

**Linux — `docker compose` pede `sudo` toda vez.**
Adicione seu usuário ao grupo `docker` (`sudo usermod -aG docker $USER`)
e abra uma nova sessão de terminal (ou `newgrp docker`).

**Qualquer sistema — `uv sync` falha ao baixar o interpretador Python.**
Garanta acesso à rede, ou instale localmente uma versão compatível
(3.11 ou 3.12) e rode `uv python pin 3.11` dentro de `backend/`.

**Qualquer sistema — API não conecta ao Postgres.**
Confirme `docker compose -f compose.yaml ps` (serviço `postgres` deve
estar `healthy`) e que `DATABASE_URL` no `.env` aponta para
`localhost:5432`.

**Qualquer sistema — Frontend não encontra a API (`ERR_CONNECTION_REFUSED`).**
Verifique `VITE_API_BASE_URL` no `.env` e se `GET http://localhost:8000/health`
responde.

---

## Documentação relacionada

- [`docs/MANUAL_EXECUCAO.md`](MANUAL_EXECUCAO.md) — fluxo de demonstração completo depois de subir o sistema
- [`docs/MANUAL_INSTALACAO.md`](MANUAL_INSTALACAO.md) — configuração de integrações reais (Azure, OpenAI, visão)
- [`docs/MANUAL_USO.md`](MANUAL_USO.md) — manual de uso do sistema, tela a tela
- [`docs/ARQUITETURA.md`](ARQUITETURA.md) — arquitetura do sistema
- [`README.md`](../README.md) — visão geral do repositório
