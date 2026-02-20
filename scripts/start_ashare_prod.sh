#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

CONFIG_PATH="${REPO_ROOT}/configs/ashare_live_prod.json"
if [[ $# -gt 0 && "${1:0:2}" != "--" ]]; then
  CONFIG_PATH="$1"
  shift
fi

if [[ ! -f "${CONFIG_PATH}" ]]; then
  echo "Config file not found: ${CONFIG_PATH}" >&2
  exit 1
fi

exec bash "${REPO_ROOT}/scripts/start_realtime_system.sh" --detach --run-config "${CONFIG_PATH}" "$@"
