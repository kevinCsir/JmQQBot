#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOAD_ENV_SH="$ROOT_DIR/scripts/load_env.sh"

if [[ -f "$LOAD_ENV_SH" ]]; then
  # shellcheck disable=SC1090
  source "$LOAD_ENV_SH"
fi

VENV_PIP="$ROOT_DIR/.venv/bin/pip"
VENV_UVICORN="$ROOT_DIR/.venv/bin/uvicorn"

if [[ ! -x "$VENV_UVICORN" ]]; then
  echo "未找到虚拟环境，请先创建 .venv"
  exit 1
fi

echo "检查依赖..."
"$VENV_PIP" install -r "$ROOT_DIR/requirements.txt"

echo "启动 AutoJm: http://${AUTOJM_HOST:-0.0.0.0}:${AUTOJM_PORT:-8080}"
exec "$VENV_UVICORN" app.main:app --host "${AUTOJM_HOST:-0.0.0.0}" --port "${AUTOJM_PORT:-8080}"

