.PHONY: help check-prereqs setup dev stop format lint typecheck test test-integration load-test build check \
        migrate migration rules-validate rules-seed compose-up compose-down \
        codegen export-openapi seed-dev-data seed-care-units seed-employees seed-patients \
        worker worker-loop up logs health \
        test-db-create test-db-migrate setup-azure setup-yolo check-env

# =============================================================================
# Variáveis
# =============================================================================

BACKEND  := backend
FRONTEND := frontend

TEST_DATABASE_URL ?= postgresql+psycopg://sentinel:sentinel@localhost:5432/sentinelhealth_test

# Cores
GREEN  = \033[0;32m
YELLOW = \033[0;33m
RED    = \033[0;31m
BLUE   = \033[0;36m
NC     = \033[0m

# =============================================================================
# AJUDA
# =============================================================================

help:
	@echo "$(BLUE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo "$(BLUE)  SentinelHealth — Apoio à Decisão Clínica Multimodal$(NC)"
	@echo "$(BLUE)  Tech Challenge Fase 4 · PosTech 2026$(NC)"
	@echo "$(BLUE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo "  $(BLUE)▸ SETUP$(NC)"
	@echo "    $(GREEN)make check-prereqs$(NC)    - Verifica pré-requisitos (Python, Node, Docker, etc)"
	@echo "    $(GREEN)make setup$(NC)            - Instala dependências (backend + frontend)"
	@echo "    $(GREEN)make compose-up$(NC)       - Sobe o PostgreSQL local via Docker Compose"
	@echo "    $(GREEN)make migrate$(NC)          - Aplica migrations pendentes no banco"
	@echo ""
	@echo "  $(BLUE)▸ EXECUÇÃO$(NC)"
	@echo "    $(GREEN)make dev$(NC)              - Sobe Postgres e orienta subir API/frontend"
	@echo "    $(GREEN)make worker$(NC)           - Roda uma iteração do worker do orquestrador"
	@echo "    $(GREEN)make worker-loop$(NC)      - Roda o worker em loop contínuo"
	@echo "    $(GREEN)make up$(NC)               - Sobe tudo via Docker Compose (Postgres+API+worker+frontend)"
	@echo "    $(GREEN)make stop$(NC)             - Derruba os containers do Compose"
	@echo "    $(GREEN)make logs$(NC)             - Exibe logs dos containers em tempo real"
	@echo "    $(GREEN)make health$(NC)           - Verifica se a API está respondendo"
	@echo ""
	@echo "  $(BLUE)▸ QUALIDADE$(NC)"
	@echo "    $(GREEN)make format$(NC)           - Formata backend (ruff) e frontend (prettier)"
	@echo "    $(GREEN)make lint$(NC)             - Lint backend (ruff) e frontend (eslint)"
	@echo "    $(GREEN)make typecheck$(NC)        - Checagem de tipos (mypy + tsc)"
	@echo "    $(GREEN)make check$(NC)            - Validação completa (lint+typecheck+test+regras)"
	@echo ""
	@echo "  $(BLUE)▸ TESTES$(NC)"
	@echo "    $(GREEN)make test$(NC)             - Testes unitários (backend + frontend)"
	@echo "    $(GREEN)make test-integration$(NC) - Testes de integração (requer Postgres)"
	@echo "    $(GREEN)make test-db-create$(NC)   - Cria banco de teste (idempotente)"
	@echo "    $(GREEN)make test-db-migrate$(NC)  - Aplica migrations no banco de teste"
	@echo ""
	@echo "  $(BLUE)▸ DADOS$(NC)"
	@echo "    $(GREEN)make rules-validate$(NC)   - Valida regras clínicas (YAML vs schema)"
	@echo "    $(GREEN)make rules-seed$(NC)       - Carrega regras clínicas no banco"
	@echo "    $(GREEN)make seed-dev-data$(NC)    - Cria instituição e usuários de dev"
	@echo "    $(GREEN)make seed-care-units$(NC)  - Popula unidades assistenciais"
	@echo "    $(GREEN)make seed-employees$(NC)   - Popula funcionários fictícios"
	@echo "    $(GREEN)make seed-patients$(NC)    - Popula pacientes fictícios"
	@echo ""
	@echo "  $(BLUE)▸ BUILD & DEPLOY$(NC)"
	@echo "    $(GREEN)make build$(NC)            - Build das imagens Docker"
	@echo "    $(GREEN)make codegen$(NC)          - Gera enums TypeScript a partir do Python"
	@echo "    $(GREEN)make export-openapi$(NC)   - Gera snapshot OpenAPI (docs/contracts)"
	@echo ""
	@echo "  $(BLUE)▸ INTEGRAÇÕES$(NC)"
	@echo "    $(GREEN)make setup-azure$(NC)      - Cria recursos Azure (Speech, Language, Vision)"
	@echo "    $(GREEN)make setup-yolo$(NC)       - Instala YOLOv8 para análise de vídeo"
	@echo "    $(GREEN)make check-env$(NC)        - Verifica quais integrações estão configuradas"
	@echo ""
	@echo "  $(BLUE)▸ BANCO$(NC)"
	@echo "    $(GREEN)make migration name=\"...\"$(NC)  - Cria nova migration Alembic"
	@echo "    $(GREEN)make compose-down$(NC)     - Derruba Compose e remove volumes"
	@echo ""
	@echo "$(BLUE)═══════════════════════════════════════════════════════════════════$(NC)"

# =============================================================================
# SETUP
# =============================================================================

check-prereqs:
	@echo "$(BLUE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo "$(BLUE)  Verificação de pré-requisitos$(NC)"
	@echo "$(BLUE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@ERRORS=0; \
	echo "  $(BLUE)▸ Python (gerenciado pelo uv)$(NC)"; \
	if uv python find ">=3.11,<3.13" >/dev/null 2>&1; then \
		echo "    $(GREEN)✓ Python $$(uv python find '>=3.11,<3.13' 2>/dev/null | xargs -I{} {} --version 2>/dev/null || echo '3.11+')$(NC)"; \
	elif python3 --version 2>/dev/null | grep -qE "3\.(11|12)"; then \
		echo "    $(GREEN)✓ $$(python3 --version) (sistema)$(NC)"; \
	else \
		echo "    $(YELLOW)○ Python 3.11/3.12 não encontrado — o uv instalará automaticamente$(NC)"; \
	fi; \
	echo ""; \
	echo "  $(BLUE)▸ uv (gerenciador de pacotes Python)$(NC)"; \
	if which uv >/dev/null 2>&1; then \
		echo "    $(GREEN)✓ $$(uv --version)$(NC)"; \
	else \
		echo "    $(RED)✗ uv não encontrado — instale: curl -LsSf https://astral.sh/uv/install.sh | sh$(NC)"; \
		ERRORS=$$((ERRORS+1)); \
	fi; \
	echo ""; \
	echo "  $(BLUE)▸ Node.js$(NC)"; \
	if node --version 2>/dev/null | grep -qE "^v(2[2-9]|[3-9])"; then \
		echo "    $(GREEN)✓ Node.js $$(node --version)$(NC)"; \
	else \
		echo "    $(RED)✗ Node.js 22+ não encontrado$(NC)"; \
		ERRORS=$$((ERRORS+1)); \
	fi; \
	echo ""; \
	echo "  $(BLUE)▸ npm$(NC)"; \
	if which npm >/dev/null 2>&1; then \
		echo "    $(GREEN)✓ npm $$(npm --version)$(NC)"; \
	else \
		echo "    $(RED)✗ npm não encontrado$(NC)"; \
		ERRORS=$$((ERRORS+1)); \
	fi; \
	echo ""; \
	echo "  $(BLUE)▸ Docker$(NC)"; \
	if which docker >/dev/null 2>&1; then \
		echo "    $(GREEN)✓ $$(docker --version | head -1)$(NC)"; \
	else \
		echo "    $(RED)✗ Docker não encontrado$(NC)"; \
		ERRORS=$$((ERRORS+1)); \
	fi; \
	echo ""; \
	echo "  $(BLUE)▸ Docker Compose$(NC)"; \
	if docker compose version >/dev/null 2>&1; then \
		echo "    $(GREEN)✓ $$(docker compose version)$(NC)"; \
	else \
		echo "    $(RED)✗ Docker Compose não encontrado$(NC)"; \
		ERRORS=$$((ERRORS+1)); \
	fi; \
	echo ""; \
	echo "  $(BLUE)▸ Git$(NC)"; \
	if which git >/dev/null 2>&1; then \
		echo "    $(GREEN)✓ $$(git --version)$(NC)"; \
	else \
		echo "    $(RED)✗ Git não encontrado$(NC)"; \
		ERRORS=$$((ERRORS+1)); \
	fi; \
	echo ""; \
	echo "  $(BLUE)▸ ffmpeg (opcional, para áudio/vídeo)$(NC)"; \
	if which ffmpeg >/dev/null 2>&1; then \
		echo "    $(GREEN)✓ $$(ffmpeg -version 2>&1 | head -1)$(NC)"; \
	else \
		echo "    $(YELLOW)○ ffmpeg não encontrado (necessário para análise de áudio/vídeo)$(NC)"; \
	fi; \
	echo ""; \
	echo "  $(BLUE)▸ Azure CLI (opcional, para setup-azure)$(NC)"; \
	if which az >/dev/null 2>&1; then \
		echo "    $(GREEN)✓ $$(az version --query '\"azure-cli\"' -o tsv 2>/dev/null)$(NC)"; \
	else \
		echo "    $(YELLOW)○ Azure CLI não encontrada (necessária apenas para make setup-azure)$(NC)"; \
	fi; \
	echo ""; \
	echo "$(BLUE)═══════════════════════════════════════════════════════════════════$(NC)"; \
	if [ $$ERRORS -eq 0 ]; then \
		echo "$(GREEN)  Todos os pré-requisitos obrigatórios estão instalados!$(NC)"; \
		echo "$(GREEN)  Rode: make setup$(NC)"; \
	else \
		echo "$(RED)  $$ERRORS pré-requisito(s) obrigatório(s) não encontrado(s).$(NC)"; \
		echo "$(RED)  Instale os itens marcados com ✗ antes de continuar.$(NC)"; \
	fi; \
	echo "$(BLUE)═══════════════════════════════════════════════════════════════════$(NC)"

setup: check-prereqs
	@echo "$(BLUE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo "$(BLUE)  Setup — SentinelHealth$(NC)"
	@echo "$(BLUE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo "$(YELLOW)Instalando dependências do backend (uv sync)...$(NC)"
	@cd $(BACKEND) && ( \
		.venv/bin/python -c "import ultralytics" >/dev/null 2>&1 && \
		uv sync --group vision || uv sync \
	) && echo "$(GREEN)Backend OK$(NC)"
	@echo ""
	@echo "$(YELLOW)Instalando dependências do frontend (npm install)...$(NC)"
	@cd $(FRONTEND) && npm install && echo "$(GREEN)Frontend OK$(NC)"
	@echo ""
	@test -f .env || (cp .env.example .env && echo "$(YELLOW).env criado a partir de .env.example$(NC)")
	@echo ""
	@echo "$(GREEN)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)  Setup concluído!$(NC)"
	@echo "$(GREEN)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo "  Próximos passos:"
	@echo "  $(GREEN)make compose-up$(NC)       - Sobe o PostgreSQL"
	@echo "  $(GREEN)make migrate$(NC)          - Aplica as migrations"
	@echo "  $(GREEN)make rules-seed$(NC)       - Carrega regras clínicas"
	@echo "  $(GREEN)make seed-dev-data$(NC)    - Cria usuários de desenvolvimento"
	@echo "  $(GREEN)make dev$(NC)              - Inicia o sistema"
	@echo ""

# =============================================================================
# EXECUÇÃO
# =============================================================================

dev: compose-up
	@echo "$(GREEN)Postgres disponível em localhost:5432.$(NC)"
	@echo ""
	@echo "$(YELLOW)Em terminais separados, rode:$(NC)"
	@echo "  $(GREEN)cd backend  && uv run uvicorn app.main:app --reload$(NC)"
	@echo "  $(GREEN)cd backend  && PYTHONPATH=. uv run python -m scripts.run_orchestrator_worker$(NC)"
	@echo "  $(GREEN)cd frontend && npm run dev$(NC)"
	@echo ""
	@echo "$(BLUE)API: http://localhost:8000 · Swagger: http://localhost:8000/docs$(NC)"
	@echo "$(BLUE)Frontend: http://localhost:5173$(NC)"

stop:
	@echo "$(YELLOW)Derrubando containers...$(NC)"
	@docker compose -f compose.yaml down && echo "$(GREEN)Containers parados$(NC)"

worker:
	@echo "$(BLUE)Rodando worker do orquestrador (uma iteração)...$(NC)"
	@cd $(BACKEND) && PYTHONPATH=. uv run python -m scripts.run_orchestrator_worker --once

worker-loop:
	@echo "$(BLUE)Rodando worker do orquestrador (loop contínuo)...$(NC)"
	@echo "$(YELLOW)Ctrl+C para parar$(NC)"
	@cd $(BACKEND) && PYTHONPATH=. uv run python -m scripts.run_orchestrator_worker

up:
	@echo "$(BLUE)Subindo todos os serviços via Docker Compose...$(NC)"
	@docker compose -f compose.yaml up -d --build && echo "$(GREEN)Serviços disponíveis$(NC)"
	@echo ""
	@echo "  $(GREEN)API:$(NC)       http://localhost:8000"
	@echo "  $(GREEN)Swagger:$(NC)   http://localhost:8000/docs"
	@echo "  $(GREEN)Frontend:$(NC)  http://localhost:5173"
	@echo "  $(GREEN)Postgres:$(NC)  localhost:5432"

logs:
	@docker compose -f compose.yaml logs -f --tail=50

health:
	@echo "$(BLUE)Verificando saúde da API...$(NC)"
	@curl -sf http://localhost:8000/health > /dev/null 2>&1 && \
		echo "$(GREEN)✓ API respondendo em http://localhost:8000$(NC)" || \
		echo "$(RED)✗ API não está respondendo (rode 'make dev' ou 'make up' primeiro)$(NC)"
	@curl -sf http://localhost:5173 > /dev/null 2>&1 && \
		echo "$(GREEN)✓ Frontend respondendo em http://localhost:5173$(NC)" || \
		echo "$(YELLOW)○ Frontend não está respondendo$(NC)"

# =============================================================================
# QUALIDADE
# =============================================================================

format:
	@echo "$(BLUE)Formatando código...$(NC)"
	@cd $(BACKEND) && uv run ruff format . && echo "$(GREEN)Backend formatado$(NC)"
	@cd $(FRONTEND) && npm run format && echo "$(GREEN)Frontend formatado$(NC)"

lint:
	@echo "$(BLUE)Executando lint...$(NC)"
	@cd $(BACKEND) && uv run ruff check . && echo "$(GREEN)Backend lint OK$(NC)"
	@cd $(FRONTEND) && npm run lint && echo "$(GREEN)Frontend lint OK$(NC)"

typecheck:
	@echo "$(BLUE)Checagem de tipos...$(NC)"
	@cd $(BACKEND) && uv run mypy app && echo "$(GREEN)Backend types OK$(NC)"
	@cd $(FRONTEND) && npm run typecheck && echo "$(GREEN)Frontend types OK$(NC)"

check: lint typecheck test rules-validate
	@echo ""
	@echo "$(GREEN)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)  Todas as validações passaram!$(NC)"
	@echo "$(GREEN)═══════════════════════════════════════════════════════════════════$(NC)"

# =============================================================================
# TESTES
# =============================================================================

test:
	@echo "$(BLUE)Rodando testes unitários...$(NC)"
	@cd $(BACKEND) && DATABASE_URL="$(TEST_DATABASE_URL)" uv run pytest && echo "$(GREEN)Backend tests OK$(NC)"
	@cd $(FRONTEND) && npm run test && echo "$(GREEN)Frontend tests OK$(NC)"

test-integration:
	@echo "$(BLUE)Rodando testes de integração...$(NC)"
	@cd $(BACKEND) && DATABASE_URL="$(TEST_DATABASE_URL)" uv run pytest -m integration

test-db-create:
	@echo "$(YELLOW)Criando banco de teste (idempotente)...$(NC)"
	@docker compose -f compose.yaml exec -T postgres psql -U $${POSTGRES_USER:-sentinel} -d postgres \
		-tc "SELECT 1 FROM pg_database WHERE datname = '$${POSTGRES_TEST_DB:-sentinelhealth_test}'" \
		| grep -q 1 || docker compose -f compose.yaml exec -T postgres \
		createdb -U $${POSTGRES_USER:-sentinel} $${POSTGRES_TEST_DB:-sentinelhealth_test}
	@echo "$(GREEN)Banco de teste pronto$(NC)"

test-db-migrate:
	@echo "$(YELLOW)Aplicando migrations no banco de teste...$(NC)"
	@cd $(BACKEND) && DATABASE_URL="$(TEST_DATABASE_URL)" uv run alembic upgrade head
	@echo "$(GREEN)Migrations aplicadas$(NC)"

load-test:
	@echo "$(BLUE)Rodando teste de carga (cenário: $(or $(scenario),health))...$(NC)"
	@cd $(BACKEND) && uv run python -m scripts.load_test --scenario $(or $(scenario),health)

# =============================================================================
# DADOS & REGRAS CLÍNICAS
# =============================================================================

rules-validate:
	@echo "$(BLUE)Validando regras clínicas...$(NC)"
	@cd $(BACKEND) && uv run python -m clinical_rules.cli validate && echo "$(GREEN)Regras válidas$(NC)"

rules-seed:
	@echo "$(BLUE)Carregando regras clínicas no banco...$(NC)"
	@cd $(BACKEND) && uv run python -m clinical_rules.cli seed && echo "$(GREEN)Regras carregadas$(NC)"

seed-dev-data:
	@echo "$(BLUE)Criando instituição e usuários de desenvolvimento...$(NC)"
	@cd $(BACKEND) && PYTHONPATH=. uv run python -m scripts.seed_dev_data

seed-care-units:
	@echo "$(BLUE)Populando unidades assistenciais...$(NC)"
	@cd $(BACKEND) && PYTHONPATH=. uv run python -m scripts.seed_care_units

seed-employees:
	@echo "$(BLUE)Populando funcionários fictícios...$(NC)"
	@cd $(BACKEND) && PYTHONPATH=. uv run python -m scripts.seed_employees

seed-patients:
	@echo "$(BLUE)Populando pacientes fictícios...$(NC)"
	@cd $(BACKEND) && PYTHONPATH=. uv run python -m scripts.seed_patients

# =============================================================================
# BUILD & CONTRATOS
# =============================================================================

build:
	@echo "$(BLUE)Construindo imagens Docker...$(NC)"
	@docker compose -f compose.yaml build && echo "$(GREEN)Build concluído$(NC)"

codegen:
	@echo "$(BLUE)Gerando enums TypeScript...$(NC)"
	@cd $(BACKEND) && PYTHONPATH=. uv run python -m scripts.export_enums && echo "$(GREEN)Enums gerados$(NC)"

export-openapi:
	@echo "$(BLUE)Exportando snapshot OpenAPI...$(NC)"
	@cd $(BACKEND) && PYTHONPATH=. uv run python -m scripts.export_openapi && echo "$(GREEN)OpenAPI exportado$(NC)"

# =============================================================================
# BANCO DE DADOS
# =============================================================================

migrate:
	@echo "$(BLUE)Aplicando migrations...$(NC)"
	@cd $(BACKEND) && uv run alembic upgrade head && echo "$(GREEN)Migrations aplicadas$(NC)"

migration:
	@echo "$(BLUE)Criando nova migration: $(name)$(NC)"
	@cd $(BACKEND) && uv run alembic revision -m "$(name)"

# =============================================================================
# DOCKER COMPOSE
# =============================================================================

compose-up:
	@echo "$(BLUE)Subindo PostgreSQL...$(NC)"
	@docker compose -f compose.yaml up -d postgres && echo "$(GREEN)Postgres disponível$(NC)"

compose-down:
	@echo "$(YELLOW)Derrubando Compose e removendo volumes...$(NC)"
	@docker compose -f compose.yaml down -v && echo "$(GREEN)Containers e volumes removidos$(NC)"


# =============================================================================
# INTEGRAÇÕES (Azure, OpenAI, YOLOv8)
# =============================================================================

check-env:
	@echo "$(BLUE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo "$(BLUE)  Status das integrações$(NC)"
	@echo "$(BLUE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo "  $(BLUE)▸ OpenAI (LLM + GPT-4 Vision)$(NC)"
	@grep -q "^OPENAI_API_KEY=" .env 2>/dev/null && grep "^OPENAI_API_KEY=" .env | grep -qv "^OPENAI_API_KEY=$$" && \
		echo "    $(GREEN)✓ OPENAI_API_KEY configurada$(NC)" || \
		echo "    $(RED)✗ OPENAI_API_KEY não configurada$(NC)"
	@grep -q "^LLM_PROVIDER=OPENAI" .env 2>/dev/null && \
		echo "    $(GREEN)✓ LLM_PROVIDER=OPENAI$(NC)" || \
		echo "    $(YELLOW)○ LLM_PROVIDER=LOCAL (template determinístico)$(NC)"
	@echo ""
	@echo "  $(BLUE)▸ Azure AI Speech (transcrição de áudio)$(NC)"
	@grep -q "^AZURE_SPEECH_KEY=" .env 2>/dev/null && grep "^AZURE_SPEECH_KEY=" .env | grep -qv "^AZURE_SPEECH_KEY=$$" && \
		echo "    $(GREEN)✓ AZURE_SPEECH_KEY configurada$(NC)" || \
		echo "    $(RED)✗ AZURE_SPEECH_KEY não configurada$(NC)"
	@grep -q "^TRANSCRIPTION_PROVIDER=AZURE_SPEECH" .env 2>/dev/null && \
		echo "    $(GREEN)✓ TRANSCRIPTION_PROVIDER=AZURE_SPEECH$(NC)" || \
		echo "    $(YELLOW)○ TRANSCRIPTION_PROVIDER=LOCAL$(NC)"
	@echo ""
	@echo "  $(BLUE)▸ Azure AI Language (sentimento)$(NC)"
	@grep -q "^AZURE_LANGUAGE_KEY=" .env 2>/dev/null && grep "^AZURE_LANGUAGE_KEY=" .env | grep -qv "^AZURE_LANGUAGE_KEY=$$" && \
		echo "    $(GREEN)✓ AZURE_LANGUAGE_KEY configurada$(NC)" || \
		echo "    $(RED)✗ AZURE_LANGUAGE_KEY não configurada$(NC)"
	@echo "    $(YELLOW)Requer feature flag: sentiment_analysis_enabled$(NC)"
	@echo ""
	@echo "  $(BLUE)▸ Azure AI Vision (reconhecimento de imagem)$(NC)"
	@grep -q "^AZURE_VISION_KEY=" .env 2>/dev/null && grep "^AZURE_VISION_KEY=" .env | grep -qv "^AZURE_VISION_KEY=$$" && \
		echo "    $(GREEN)✓ AZURE_VISION_KEY configurada$(NC)" || \
		echo "    $(RED)✗ AZURE_VISION_KEY não configurada$(NC)"
	@echo "    $(YELLOW)Requer feature flag: image_recognition_enabled$(NC)"
	@echo ""
	@echo "  $(BLUE)▸ Azure DICOM Service (imagens médicas)$(NC)"
	@grep -q "^AZURE_DICOM_ENDPOINT=" .env 2>/dev/null && grep "^AZURE_DICOM_ENDPOINT=" .env | grep -qv "^AZURE_DICOM_ENDPOINT=$$" && \
		echo "    $(GREEN)✓ AZURE_DICOM_ENDPOINT configurada$(NC)" || \
		echo "    $(RED)✗ AZURE_DICOM_ENDPOINT não configurada$(NC)"
	@echo "    $(YELLOW)Requer feature flag: dicom_service_enabled$(NC)"
	@echo ""
	@echo "  $(BLUE)▸ YOLOv8 (detecção de objetos em vídeo)$(NC)"
	@grep -q "^VISION_PROVIDER=OPENPOSE_YOLOV8" .env 2>/dev/null && \
		echo "    $(GREEN)✓ VISION_PROVIDER=OPENPOSE_YOLOV8$(NC)" || \
		echo "    $(YELLOW)○ VISION_PROVIDER=LOCAL$(NC)"
	@cd $(BACKEND) && uv run python -c "import ultralytics; print('OK')" 2>/dev/null && \
		echo "    $(GREEN)✓ ultralytics instalado$(NC)" || \
		echo "    $(RED)✗ ultralytics não instalado (rode: make setup-yolo)$(NC)"
	@echo "    $(YELLOW)Requer feature flag: vision_detection_enabled$(NC)"
	@echo ""
	@which ffmpeg >/dev/null 2>&1 && \
		echo "  $(GREEN)✓ ffmpeg disponível no PATH$(NC)" || \
		echo "  $(RED)✗ ffmpeg não encontrado (necessário para áudio/vídeo)$(NC)"
	@echo ""
	@echo "$(BLUE)═══════════════════════════════════════════════════════════════════$(NC)"

setup-azure:
	@echo "$(BLUE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo "$(BLUE)  Criando recursos Azure para SentinelHealth$(NC)"
	@echo "$(BLUE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@which az >/dev/null 2>&1 || (echo "$(RED)Azure CLI não encontrada. Instale: https://aka.ms/installazurecli$(NC)" && exit 1)
	@az account show >/dev/null 2>&1 || (echo "$(RED)Não autenticado. Rode: az login$(NC)" && exit 1)
	@echo "$(GREEN)Azure CLI autenticada$(NC)"
	@echo ""
	@echo "$(YELLOW)Criando resource group rg-sentinelhealth...$(NC)"
	@az group create --name rg-sentinelhealth --location eastus -o none 2>/dev/null && echo "$(GREEN)Resource group OK$(NC)"
	@echo ""
	@echo "$(YELLOW)Criando Azure AI Speech (S0)...$(NC)"
	@az cognitiveservices account create --name sentinelhealth-speech --resource-group rg-sentinelhealth --kind SpeechServices --sku S0 --location eastus --yes -o none 2>/dev/null && echo "$(GREEN)Speech OK$(NC)" || echo "$(YELLOW)Speech já existe ou falhou$(NC)"
	@echo ""
	@echo "$(YELLOW)Criando Azure AI Language (S)...$(NC)"
	@az cognitiveservices account create --name sentinelhealth-language --resource-group rg-sentinelhealth --kind TextAnalytics --sku S --location eastus --yes -o none 2>/dev/null && echo "$(GREEN)Language OK$(NC)" || echo "$(YELLOW)Language já existe ou falhou$(NC)"
	@echo ""
	@echo "$(YELLOW)Criando Azure AI Vision (S1)...$(NC)"
	@az cognitiveservices account create --name sentinelhealth-vision --resource-group rg-sentinelhealth --kind ComputerVision --sku S1 --location eastus --yes -o none 2>/dev/null && echo "$(GREEN)Vision OK$(NC)" || echo "$(YELLOW)Vision já existe ou falhou$(NC)"
	@echo ""
	@echo "$(GREEN)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)  Recursos criados! Extraia as chaves com:$(NC)"
	@echo "$(GREEN)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo "  $(GREEN)az cognitiveservices account keys list --name sentinelhealth-speech --resource-group rg-sentinelhealth --query key1 -o tsv$(NC)"
	@echo "  $(GREEN)az cognitiveservices account keys list --name sentinelhealth-language --resource-group rg-sentinelhealth --query key1 -o tsv$(NC)"
	@echo "  $(GREEN)az cognitiveservices account keys list --name sentinelhealth-vision --resource-group rg-sentinelhealth --query key1 -o tsv$(NC)"
	@echo ""
	@echo "  Preencha as variáveis correspondentes no .env"
	@echo ""

setup-yolo:
	@echo "$(BLUE)Instalando YOLOv8 (grupo de dependências vision)...$(NC)"
	@cd $(BACKEND) && uv sync --group vision && echo "$(GREEN)YOLOv8 instalado$(NC)"
	@echo ""
	@echo "$(YELLOW)Configure no .env:$(NC)"
	@echo "  $(GREEN)VISION_PROVIDER=OPENPOSE_YOLOV8$(NC)"
	@echo ""
	@echo "$(YELLOW)Ligue a feature flag na tela /admin/feature-flags:$(NC)"
	@echo "  $(GREEN)vision_detection_enabled = true$(NC)"
	@echo ""
