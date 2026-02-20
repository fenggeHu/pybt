#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="${PYBT_BASE_DIR:-$HOME/.pybt}"
PID_DIR="${BASE_DIR}/pids"
SERVER_PID_FILE="${PID_DIR}/pybt-server.pid"
BOT_PID_FILE="${PID_DIR}/pybt-bot.pid"

stop_by_pid_file() {
  local pid_file="$1"
  local name="$2"

  if [[ ! -f "${pid_file}" ]]; then
    echo "${name}: pid file not found (${pid_file})"
    return 0
  fi

  local pid
  pid="$(cat "${pid_file}" 2>/dev/null || true)"
  if [[ -z "${pid}" ]]; then
    echo "${name}: pid file is empty (${pid_file})"
    rm -f "${pid_file}"
    return 0
  fi

  if kill -0 "${pid}" >/dev/null 2>&1; then
    kill "${pid}" >/dev/null 2>&1 || true
    sleep 0.5
    if kill -0 "${pid}" >/dev/null 2>&1; then
      kill -9 "${pid}" >/dev/null 2>&1 || true
    fi
    echo "${name}: stopped (pid=${pid})"
  else
    echo "${name}: process not running (pid=${pid})"
  fi

  rm -f "${pid_file}"
}

stop_by_pid_file "${BOT_PID_FILE}" "pybt-bot"
stop_by_pid_file "${SERVER_PID_FILE}" "pybt-server"
