# Makefile — Overage development commands
# Usage: make <target>
# Run `make help` for a list of all available targets.
# Reference: INSTRUCTIONS.md Section 15 (Common Commands)

.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------
PYTHON   := $(shell command -v python3.12 2>/dev/null || command -v python3 2>/dev/null || echo python3)
SRC      := proxy
TESTS    := proxy/tests
DASH     := dashboard
PORT     := 8000
DASH_PORT := 8501

# ---------------------------------------------------------------------------
# Phony targets (these are commands, not files)
# ---------------------------------------------------------------------------
.PHONY: install install-dev venv-fresh git-usb-clean lint format typecheck test test-fast test-unit \
        test-integration security run run-dashboard run-doppler check-doppler secrets-verify sync-env-to-doppler \
        docker-up docker-down \
        docker-build migrate migrate-generate seed demo benchmark profile-tps report \
        clean pre-commit-install all check help

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

install: ## Install production dependencies
	COPYFILE_DISABLE=1 $(PYTHON) -m pip install --upgrade pip setuptools wheel
	COPYFILE_DISABLE=1 $(PYTHON) -m pip install -e .

install-dev: ## Install all dependencies (production + development)
	COPYFILE_DISABLE=1 $(PYTHON) -m pip install --upgrade pip setuptools wheel
	COPYFILE_DISABLE=1 $(PYTHON) -m pip install -e ".[dev]"

venv-fresh: ## Recreate .venv (copies not symlinks; copyfile_disable helps exfat/usb on macos)
	$(PYTHON) scripts/bootstrap_venv.py
	mkdir -p "$$HOME/.cache/overage-pip"
	env COPYFILE_DISABLE=1 PIP_CACHE_DIR=$$HOME/.cache/overage-pip .venv/bin/pip install --upgrade pip setuptools wheel
	env COPYFILE_DISABLE=1 PIP_CACHE_DIR=$$HOME/.cache/overage-pip .venv/bin/pip install -e ".[dev]"
	@if [ "$$(uname)" = "Darwin" ]; then dot_clean -m .venv 2>/dev/null || true; fi
	find .venv -name '._*' -type f -delete 2>/dev/null || true

git-usb-clean: ## Delete macos appledouble ._ files under .git (fixes non-monotonic pack index on exfat)
	find .git -name '._*' -type f -delete 2>/dev/null || true

pre-commit-install: ## Install pre-commit hooks and run initial check
	pre-commit install
	pre-commit run --all-files

# ---------------------------------------------------------------------------
# Code Quality
# ---------------------------------------------------------------------------

lint: ## Run linter (ruff check + format verification)
	ruff check $(SRC) $(TESTS) $(DASH)
	ruff format --check $(SRC) $(TESTS) $(DASH)

format: ## Auto-format code and fix lint issues
	ruff format $(SRC) $(TESTS) $(DASH)
	ruff check --fix $(SRC) $(TESTS) $(DASH)

typecheck: ## Run mypy in strict mode
	mypy $(SRC) --strict

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

test: ## Run all tests with coverage (floor matches .github/workflows/ci.yml)
	pytest $(TESTS) \
		-v \
		--cov=$(SRC) \
		--cov-report=term-missing \
		--cov-fail-under=55 \
		--timeout=60 \
		-m "not slow"

test-fast: ## Run tests, stop on first failure, no coverage (fast iteration)
	pytest $(TESTS) -v -x --no-cov --timeout=30

test-unit: ## Run unit tests only
	pytest $(TESTS)/unit -v --no-cov --timeout=30

test-integration: ## Run integration tests only
	pytest $(TESTS) -v -m integration --no-cov --timeout=120

coverage: ## Run tests with HTML coverage report
	pytest $(TESTS) \
		-v \
		--cov=$(SRC) \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--timeout=60
	@echo "Coverage report: open htmlcov/index.html"

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

security: ## Run security scans (bandit + safety)
	bandit -r $(SRC) -ll -ii --exclude $(TESTS)
	safety check --output text || true

# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------

run: ## Start the proxy server (port 8000, with hot reload)
	uvicorn $(SRC).main:app --reload --host 0.0.0.0 --port $(PORT)

run-dashboard: ## Start the Streamlit dashboard (port 8501)
	streamlit run $(DASH)/app.py --server.port $(DASH_PORT)

# ---------------------------------------------------------------------------
# Secrets (Doppler) — see docs/DOPPLER_1PASSWORD_SETUP.md and doppler.yaml
# ---------------------------------------------------------------------------

secrets-verify: ## Confirm Doppler CLI can inject env (requires doppler login + doppler.yaml)
	@command -v doppler >/dev/null || (echo "Install Doppler: brew install dopplerhq/cli/doppler" && exit 1)
	doppler run -- $(PYTHON) -c "import os; assert os.getenv('OVERAGE_ENV'), 'missing OVERAGE_ENV'; print('doppler ok:', os.getenv('OVERAGE_ENV'))"

check-doppler: ## Run full make check with secrets from Doppler (overage/dev)
	@command -v doppler >/dev/null || (echo "Install Doppler: brew install dopplerhq/cli/doppler" && exit 1)
	doppler run -- $(MAKE) check

run-doppler: ## Start proxy with env from Doppler
	@command -v doppler >/dev/null || (echo "Install Doppler: brew install dopplerhq/cli/doppler" && exit 1)
	doppler run -- $(MAKE) run

sync-env-to-doppler: ## Upload local .env to Doppler dev config (use --silent; keep .env out of git)
	@command -v doppler >/dev/null || (echo "Install Doppler: brew install dopplerhq/cli/doppler" && exit 1)
	test -f .env || (echo "missing .env — copy from .env.example first" && exit 1)
	doppler secrets upload .env --silent
	@echo "Uploaded .env to Doppler (silent)."

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

docker-build: ## Build Docker image
	docker build -t overage:latest .

docker-up: ## Start the full development stack (proxy + db + dashboard)
	docker compose up -d --build
	@echo "Proxy:     http://localhost:$(PORT)"
	@echo "Dashboard: http://localhost:$(DASH_PORT)"
	@echo "Database:  postgresql://overage:overage_dev@localhost:5432/overage"

docker-down: ## Stop and remove all containers + volumes
	docker compose down -v

docker-logs: ## Tail logs from all containers
	docker compose logs -f

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

migrate: ## Apply all pending database migrations
	alembic upgrade head

migrate-generate: ## Generate a new migration (usage: make migrate-generate MSG="add column")
	alembic revision --autogenerate -m "$(MSG)"

migrate-downgrade: ## Roll back the last migration
	alembic downgrade -1

migrate-history: ## Show migration history
	alembic history

# ---------------------------------------------------------------------------
# Scripts
# ---------------------------------------------------------------------------

seed: ## Seed the database with test data
	$(PYTHON) scripts/seed_test_calls.py

demo: ## Generate synthetic demo data (no API keys needed)
	$(PYTHON) scripts/demo_data.py --calls 500 --days 30

benchmark: ## Measure HTTP latency to GET /health (start proxy with `make run` first)
	$(PYTHON) scripts/benchmark.py

profile-tps: ## Profile tokens-per-second rates for supported models
	$(PYTHON) scripts/profile_tps.py

report: ## Generate a sample audit report
	$(PYTHON) scripts/generate_report.py

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

clean: ## Remove caches, build artifacts, and temp files
	rm -rf .mypy_cache .pytest_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	rm -rf dist build *.egg-info
	rm -f *.sqlite test.db overage_dev.db

# ---------------------------------------------------------------------------
# Composite targets
# ---------------------------------------------------------------------------

check: lint typecheck test security ## Run all checks (lint + typecheck + test + security)

all: check ## Alias for `make check`

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

help: ## Show this help message
	@echo "Overage Development Commands"
	@echo "============================"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Usage: make <target>"
