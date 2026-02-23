#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

CONFIG_PATH="${1:-${REPO_ROOT}/configs/profiles/eastmoney_sse_prod.jsonc}"

if [[ ! -f "${CONFIG_PATH}" ]]; then
  echo "Config file not found: ${CONFIG_PATH}" >&2
  exit 1
fi

resolve_python() {
  if [[ -n "${PYBT_PYTHON:-}" ]]; then
    if [[ -x "${PYBT_PYTHON}" ]]; then
      echo "${PYBT_PYTHON}"
      return
    fi
    if command -v "${PYBT_PYTHON}" >/dev/null 2>&1; then
      command -v "${PYBT_PYTHON}"
      return
    fi
    echo "PYBT_PYTHON not executable: ${PYBT_PYTHON}" >&2
    exit 1
  fi

  if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    echo "${REPO_ROOT}/.venv/bin/python"
    return
  fi
  if command -v python3.11 >/dev/null 2>&1; then
    command -v python3.11
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi
  echo "No suitable Python found. Set PYBT_PYTHON explicitly." >&2
  exit 1
}

PYBT_PYTHON="$(resolve_python)"
export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

echo "Self-check config: ${CONFIG_PATH}"
exec "${PYBT_PYTHON}" -m pybt --config "${CONFIG_PATH}" --self-check
