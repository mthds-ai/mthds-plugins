SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c

VIRTUAL_ENV := $(CURDIR)/.venv
VENV_PYTHON := "$(VIRTUAL_ENV)/bin/python"
VENV_PYTEST := "$(VIRTUAL_ENV)/bin/pytest"
VENV_RUFF := "$(VIRTUAL_ENV)/bin/ruff"
VENV_PYRIGHT := "$(VIRTUAL_ENV)/bin/pyright"
VENV_MYPY := "$(VIRTUAL_ENV)/bin/mypy"

UV_MIN_VERSION = $(shell grep -m1 'required-version' pyproject.toml | sed -E 's/.*= *"[^0-9]*([0-9][0-9.]*).*/\1/')

.PHONY: \
	help env check-uv install lock li \
	gen-skill-docs build check agent-check \
	format lint ruff-format ruff-lint pyright mypy fix-unused-imports fui \
	test agent-test gha-tests tp \
	cleanderived cleanenv cleanall reinstall ri

##########################################################################################
### SETUP
##########################################################################################

check-uv: ## Ensure uv is installed (auto-installs if missing)
	@command -v uv >/dev/null 2>&1 || { \
		echo "uv not found – installing latest (minimum $(UV_MIN_VERSION)) …"; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
	}
	@uv self update >/dev/null 2>&1 || true

env: check-uv ## Create virtual environment
	@test -d "$(VIRTUAL_ENV)" || uv venv "$(VIRTUAL_ENV)" --quiet

lock: env ## Refresh uv.lock without updating anything
	@uv lock

install: env ## Create venv + install all deps
	@uv sync --all-extras --quiet

li: lock install ## Lock + install
	@echo "> done: li = lock install"

##########################################################################################
### CLEANING
##########################################################################################

cleanderived: ## Remove caches/compiled files
	@find . -name '.coverage' -delete && \
	find . -wholename '**/*.pyc' -delete && \
	find . -type d -wholename '__pycache__' -exec rm -rf {} + && \
	find . -type d -wholename './.cache' -exec rm -rf {} + && \
	find . -type d -wholename './.mypy_cache' -exec rm -rf {} + && \
	find . -type d -wholename './.ruff_cache' -exec rm -rf {} + && \
	find . -type d -wholename '.pytest_cache' -exec rm -rf {} + && \
	find . -type d -wholename '**/.pytest_cache' -exec rm -rf {} + && \
	echo "Cleaned up derived files"

cleanenv: ## Remove virtual env and lock files
	@find . -name 'uv.lock' -delete && \
	find . -type d -wholename './.venv' -exec rm -rf {} + && \
	echo "Cleaned up virtual env and lock files"

cleanall: cleanderived cleanenv ## Remove all derived files + env

reinstall: cleanenv install ## Clean env and reinstall
	@echo "Reinstalled dependencies"

ri: reinstall ## Shorthand -> reinstall

##########################################################################################
### LINTING & FORMATTING
##########################################################################################

ruff-format: install ## Format Python with ruff
	@$(VENV_RUFF) format .

ruff-lint: install ## Lint Python with ruff
	@$(VENV_RUFF) check . --fix

format: ruff-format ## Format all
	@echo "> done: format"

lint: ruff-lint ## Lint all
	@echo "> done: lint"

pyright: install ## Type-check with pyright
	@$(VENV_PYRIGHT) --pythonpath $(VENV_PYTHON) --project pyproject.toml

mypy: install ## Type-check with mypy
	@$(VENV_MYPY)

fix-unused-imports: install ## Fix unused imports with ruff
	@$(VENV_RUFF) check --select=F401 --fix .

fui: fix-unused-imports ## Shorthand -> fix-unused-imports

##########################################################################################
### CHECKS
##########################################################################################

check: install ## Verify shared refs + version consistency + template freshness + format + lint + typecheck
	@python3 scripts/check.py
	@$(VENV_PYTHON) scripts/gen_skill_docs.py --check
	@$(VENV_RUFF) format --check .
	@$(VENV_RUFF) check .
	@$(MAKE) --no-print-directory pyright mypy

agent-check: fix-unused-imports format lint ## Full quality check (for AI agents)
	@python3 scripts/check.py
	@$(VENV_PYTHON) scripts/gen_skill_docs.py --check
	@$(VENV_RUFF) format --check .
	@$(VENV_RUFF) check .
	@$(MAKE) --no-print-directory pyright mypy
	@echo "• All checks passed."

##########################################################################################
### TESTING
##########################################################################################

test: install ## Run unit tests
	@$(VENV_PYTEST) tests/ -v

tp: install ## Run tests with prints (TEST=name to filter)
	@if [ -n "$(TEST)" ]; then \
		$(VENV_PYTEST) tests/ -s -v -k "$(TEST)"; \
	else \
		$(VENV_PYTEST) tests/ -s -v; \
	fi

gha-tests: install ## Run tests for GitHub Actions (exit on first failure, quiet)
	@$(VENV_PYTEST) --exitfirst --quiet

agent-test: install ## Run unit tests quietly (output only on failure)
	@echo "• Running unit tests..."
	@tmpfile=$$(mktemp); \
	if $(VENV_PYTEST) -o log_level=WARNING --tb=short -q > "$$tmpfile" 2>&1; then \
		exit_code=0; \
	else \
		exit_code=$$?; \
	fi; \
	if [ $$exit_code -ne 0 ]; then cat "$$tmpfile"; fi; \
	rm -f "$$tmpfile"; \
	if [ $$exit_code -eq 0 ]; then echo "• All tests passed."; fi; \
	exit $$exit_code

##########################################################################################
### HELP
##########################################################################################

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

##########################################################################################
### BUILD
##########################################################################################

gen-skill-docs: install ## Generate SKILL.md from .j2 templates
	@$(VENV_PYTHON) scripts/gen_skill_docs.py

build: gen-skill-docs
	@echo "Done: built all skill docs from templates"
