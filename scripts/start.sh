#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOAD_ENV_SH="$ROOT_DIR/scripts/load_env.sh"
VENV_DIR="$ROOT_DIR/.venv"
SYSTEM_PYTHON="$(command -v python3 || true)"

if [[ -f "$LOAD_ENV_SH" ]]; then
  # shellcheck disable=SC1090
  source "$LOAD_ENV_SH"
fi

if [[ -z "$SYSTEM_PYTHON" ]]; then
  echo "未找到 python3，请先安装 Python 3"
  exit 1
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "未找到虚拟环境，正在自动创建 .venv"
  "$SYSTEM_PYTHON" -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"
VENV_UVICORN="$VENV_DIR/bin/uvicorn"

if [[ ! -x "$VENV_UVICORN" ]]; then
  echo "初始化虚拟环境工具链..."
  "$VENV_PYTHON" -m ensurepip --upgrade
fi

echo "检查依赖..."
"$VENV_PYTHON" -m pip install --upgrade pip setuptools wheel
"$VENV_PIP" install -r "$ROOT_DIR/requirements.txt"

echo "启动 AutoJm: http://${AUTOJM_HOST:-0.0.0.0}:${AUTOJM_PORT:-8080}"
exec "$VENV_UVICORN" app.main:app --host "${AUTOJM_HOST:-0.0.0.0}" --port "${AUTOJM_PORT:-8080}"
