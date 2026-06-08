#!/usr/bin/env bash
# Starts everything: the three mock Provider APIs, the proxy, and the frontend.
# Ctrl-C stops them all.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pids=()

cleanup() {
  echo
  echo "Shutting down..."
  for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

# Load credentials from .env if present.
if [ -f "$ROOT/.env" ]; then
  set -a; . "$ROOT/.env"; set +a
fi

echo "Starting mock Providers (9001 / 9002 / 9003)..."
( cd "$ROOT" && uv --project "$ROOT/mock_apis" run uvicorn mock_apis.provider_a:app --port 9001 --reload ) & pids+=($!)
( cd "$ROOT" && uv --project "$ROOT/mock_apis" run uvicorn mock_apis.provider_b:app --port 9002 --reload ) & pids+=($!)
( cd "$ROOT" && uv --project "$ROOT/mock_apis" run uvicorn mock_apis.provider_c:app --port 9003 --reload ) & pids+=($!)

echo "Starting proxy (8000)..."
( cd "$ROOT/proxy" && uv run uvicorn main:app --port 8000 --reload ) & pids+=($!)

echo "Starting frontend (3000)..."
( cd "$ROOT/frontend" && bun --bun run dev ) & pids+=($!)

echo
echo "  Frontend : http://localhost:3000"
echo "  Proxy    : http://localhost:8000/docs"
echo "  Atlas    : http://localhost:9001/docs"
echo "  Beacon   : http://localhost:9002/docs"
echo "  Cobalt   : http://localhost:9003/docs"
echo
wait
