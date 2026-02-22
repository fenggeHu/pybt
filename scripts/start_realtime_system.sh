#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: bash scripts/start_realtime_system.sh [options]

Options:
  --check                 Validate environment and exit
  --detach                Run server and bot in background and exit
  --run-config PATH       After startup, submit config JSON/JSONC and start one run
  --host HOST             Override PYBT_SERVER_HOST
  --port PORT             Override PYBT_SERVER_PORT
  --base-dir DIR          Override PYBT_BASE_DIR
  --help                  Show this help

Required env vars:
  PYBT_API_KEY
  TELEGRAM_BOT_TOKEN
  TELEGRAM_ADMIN_PASSWORD

Optional env vars:
  PYBT_PYTHON             Python executable (default: .venv/bin/python, python3.11, python3)
  PYBT_SERVER_HOST        Default: 127.0.0.1
  PYBT_SERVER_PORT        Default: 8765
  PYBT_BASE_DIR           Default: $HOME/.pybt
  PYBT_MAX_CONCURRENT_RUNS Default: 4
  PYBT_SERVER_URL         Default: http://$PYBT_SERVER_HOST:$PYBT_SERVER_PORT

Examples:
  bash scripts/start_realtime_system.sh --check
  bash scripts/start_realtime_system.sh --detach
  bash scripts/start_realtime_system.sh --run-config ./prod_live.json
EOF
}

CHECK_ONLY=0
DETACH=0
RUN_CONFIG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)
      CHECK_ONLY=1
      shift
      ;;
    --detach)
      DETACH=1
      shift
      ;;
    --run-config)
      if [[ $# -lt 2 ]]; then
        echo "--run-config requires a file path" >&2
        exit 1
      fi
      RUN_CONFIG="$2"
      shift 2
      ;;
    --host)
      if [[ $# -lt 2 ]]; then
        echo "--host requires a value" >&2
        exit 1
      fi
      export PYBT_SERVER_HOST="$2"
      shift 2
      ;;
    --port)
      if [[ $# -lt 2 ]]; then
        echo "--port requires a value" >&2
        exit 1
      fi
      export PYBT_SERVER_PORT="$2"
      shift 2
      ;;
    --base-dir)
      if [[ $# -lt 2 ]]; then
        echo "--base-dir requires a value" >&2
        exit 1
      fi
      export PYBT_BASE_DIR="$2"
      shift 2
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -f "${REPO_ROOT}/.env.realtime" ]]; then
  set -a
  source "${REPO_ROOT}/.env.realtime"
  set +a
fi

: "${PYBT_SERVER_HOST:=127.0.0.1}"
: "${PYBT_SERVER_PORT:=8765}"
: "${PYBT_BASE_DIR:=${HOME}/.pybt}"
: "${PYBT_MAX_CONCURRENT_RUNS:=4}"
: "${PYBT_SERVER_URL:=http://${PYBT_SERVER_HOST}:${PYBT_SERVER_PORT}}"
export PYBT_SERVER_HOST PYBT_SERVER_PORT PYBT_BASE_DIR PYBT_MAX_CONCURRENT_RUNS PYBT_SERVER_URL

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
export PYBT_PYTHON

missing=()
for var in PYBT_API_KEY TELEGRAM_BOT_TOKEN TELEGRAM_ADMIN_PASSWORD; do
  if [[ -z "${!var:-}" ]]; then
    missing+=("${var}")
  fi
done
if (( ${#missing[@]} > 0 )); then
  echo "Missing required env vars: ${missing[*]}" >&2
  exit 1
fi

LOG_DIR="${PYBT_BASE_DIR}/logs"
PID_DIR="${PYBT_BASE_DIR}/pids"
SERVER_LOG="${LOG_DIR}/server.log"
BOT_LOG="${LOG_DIR}/bot.log"
SERVER_PID_FILE="${PID_DIR}/pybt-server.pid"
BOT_PID_FILE="${PID_DIR}/pybt-bot.pid"

mkdir -p "${LOG_DIR}" "${PID_DIR}" "${PYBT_BASE_DIR}"

if (( CHECK_ONLY == 1 )); then
  echo "Environment check passed"
  echo "PYBT_PYTHON=${PYBT_PYTHON}"
  echo "PYBT_BASE_DIR=${PYBT_BASE_DIR}"
  echo "PYBT_SERVER_URL=${PYBT_SERVER_URL}"
  exit 0
fi

is_running() {
  local pid="$1"
  kill -0 "${pid}" >/dev/null 2>&1
}

check_pid_file() {
  local file="$1"
  if [[ -f "${file}" ]]; then
    local pid
    pid="$(cat "${file}" 2>/dev/null || true)"
    if [[ -n "${pid}" ]] && is_running "${pid}"; then
      echo "Process already running (pid=${pid}, file=${file})" >&2
      exit 1
    fi
    rm -f "${file}"
  fi
}

check_pid_file "${SERVER_PID_FILE}"
check_pid_file "${BOT_PID_FILE}"

export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

wait_server_health() {
  local deadline=$((SECONDS + 30))
  while (( SECONDS < deadline )); do
    if "${PYBT_PYTHON}" - <<'PY' >/dev/null 2>&1
import json
import os
import urllib.request

url = f"http://{os.environ['PYBT_SERVER_HOST']}:{os.environ['PYBT_SERVER_PORT']}/health"
req = urllib.request.Request(url, headers={"Accept": "application/json", "X-API-Key": os.environ["PYBT_API_KEY"]})
try:
    with urllib.request.urlopen(req, timeout=2) as resp:
        raw = resp.read().decode("utf-8")
        data = json.loads(raw) if raw else {}
except Exception:
    raise SystemExit(1)

raise SystemExit(0 if str(data.get("ok", "")).lower() == "true" else 1)
PY
    then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

start_optional_run() {
  local config_path="$1"
  if [[ ! -f "${config_path}" ]]; then
    echo "Run config file not found: ${config_path}" >&2
    return 1
  fi

  "${PYBT_PYTHON}" - "$config_path" <<'PY'
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from pybt.configuration import load_config_dict

config_path = pathlib.Path(sys.argv[1])
base_url = f"http://{os.environ['PYBT_SERVER_HOST']}:{os.environ['PYBT_SERVER_PORT']}"
api_key = os.environ["PYBT_API_KEY"]

cfg = load_config_dict(config_path)

def request_json(method: str, path: str, body: dict | None = None) -> dict:
    url = base_url + path
    headers = {"Accept": "application/json", "X-API-Key": api_key}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}

name = f"autostart_{int(time.time())}.json"
request_json("POST", "/configs/validate", {"config": cfg})
request_json("POST", f"/configs/{urllib.parse.quote(name)}", cfg)
run = request_json("POST", "/runs", {"config_name": name})
print(f"Auto-started run_id={run.get('run_id')} config={name}")
PY
}

cd "${REPO_ROOT}"

"${PYBT_PYTHON}" -m apps.server >"${SERVER_LOG}" 2>&1 &
SERVER_PID=$!
echo "${SERVER_PID}" >"${SERVER_PID_FILE}"

if ! wait_server_health; then
  echo "Server failed health check. See ${SERVER_LOG}" >&2
  kill "${SERVER_PID}" >/dev/null 2>&1 || true
  rm -f "${SERVER_PID_FILE}"
  exit 1
fi

"${PYBT_PYTHON}" -m apps.telegram_bot.telegram_bot >"${BOT_LOG}" 2>&1 &
BOT_PID=$!
echo "${BOT_PID}" >"${BOT_PID_FILE}"

if [[ -n "${RUN_CONFIG}" ]]; then
  start_optional_run "${RUN_CONFIG}"
fi

echo "Started pybt server pid=${SERVER_PID} log=${SERVER_LOG}"
echo "Started pybt bot    pid=${BOT_PID} log=${BOT_LOG}"
echo "API: http://${PYBT_SERVER_HOST}:${PYBT_SERVER_PORT}"

if (( DETACH == 1 )); then
  echo "Detached mode enabled. Stop with: kill \
  \$(cat '${SERVER_PID_FILE}') \$(cat '${BOT_PID_FILE}')"
  exit 0
fi

cleanup() {
  local exit_code=$?
  if is_running "${BOT_PID}"; then
    kill "${BOT_PID}" >/dev/null 2>&1 || true
  fi
  if is_running "${SERVER_PID}"; then
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
  fi
  rm -f "${BOT_PID_FILE}" "${SERVER_PID_FILE}"
  exit "${exit_code}"
}

trap cleanup INT TERM EXIT

echo "Foreground mode. Press Ctrl+C to stop both processes."
while true; do
  if ! is_running "${SERVER_PID}"; then
    echo "Server process exited unexpectedly. See ${SERVER_LOG}" >&2
    exit 1
  fi
  if ! is_running "${BOT_PID}"; then
    echo "Bot process exited unexpectedly. See ${BOT_LOG}" >&2
    exit 1
  fi
  sleep 2
done
