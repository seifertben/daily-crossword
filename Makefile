.PHONY: help install gen gen-stub gen-static dev web-dev web-dev-static build-web build-static static test lint typecheck clean

PY_MOD = uv run python -m generator
DATE ?=

help:           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

install:        ## Sync Python deps (uv)
	uv sync

gen:            ## Generate today's (or DATE=YYYY-MM-DD) puzzle using .env settings
	$(PY_MOD) $(DATE)

gen-stub:       ## Generate a puzzle with no API key / no network (stub mode)
	GEMINI_MODE=stub PUZZLE_STORE=local $(PY_MOD) $(DATE)

gen-static:     ## Generate a puzzle into web/public so a static build ships it
	GEMINI_MODE=stub PUZZLE_STORE=static $(PY_MOD) $(DATE)

dev:            ## Run FastAPI serving app with reload (phase 4)
	uv run uvicorn api.main:app --reload --port 8000

web-dev:        ## Run the Vite dev server (HMR) on :5173, proxies /api -> :8000
	cd web && npm run dev

web-dev-static: ## Vite dev server in static mode (puzzles from web/public, no API)
	cd web && VITE_PUZZLE_MODE=static npm run dev

build-web:      ## Build the React SPA into web/dist
	cd web && npm run build

build-static:   ## Build a fully static SPA (puzzles inlined from web/public)
	cd web && VITE_PUZZLE_MODE=static npm run build

static:         ## gen-static + build-static: produce a deployable static site
	$(MAKE) gen-static && cd web && VITE_PUZZLE_MODE=static npm run build

web-test:       ## Run frontend unit tests (vitest)
	cd web && npm run test

docker-web:     ## Build the web serving image (SPA + API)
	docker build -t daily-crossword-web -f Dockerfile.web .

docker-gen:     ## Build the generation job image
	docker build -t daily-crossword-gen -f Dockerfile.gen .

test:           ## Run offline unit tests (no API key, no cloud)
	uv run pytest -q

lint:           ## Lint Python
	uv run ruff check . && uv run ruff format --check .

typecheck:      ## Type-check Python
	uv run mypy generator api

clean:          ## Remove generated puzzles and caches
	rm -f local-data/puzzles/*.json
	rm -rf .pytest_cache .ruff_cache .mypy_cache
