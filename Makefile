.PHONY: install dev providers

install:  ## Install all dependencies (Python via uv, frontend via bun)
	cd mock_apis && uv sync
	cd proxy && uv sync
	cd frontend && bun install

dev:  ## Run everything (3 Providers + proxy + frontend) with hot reload
	./dev.sh

providers:  ## Run only the three mock Provider APIs
	uv --project mock_apis run uvicorn mock_apis.provider_a:app --port 9001 --reload & \
	uv --project mock_apis run uvicorn mock_apis.provider_b:app --port 9002 --reload & \
	uv --project mock_apis run uvicorn mock_apis.provider_c:app --port 9003 --reload & \
	wait
