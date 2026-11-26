#!/usr/bin/env bash
# Starts or rebuilds MetaStudio via Docker Compose with stable port selection.
# Keeps the same port across rebuilds/updates and advances to the next free port
# ONLY when a port is already occupied by another service.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

FRONTEND_START="${FRONTEND_START:-8080}"
FRONTEND_END="${FRONTEND_END:-8099}"
BACKEND_START="${BACKEND_START:-8000}"
BACKEND_END="${BACKEND_END:-8019}"

get_own_port() {
  local service="$1"
  local container_port="$2"
  local mapping
  mapping="$(docker compose port "${service}" "${container_port}" 2>/dev/null || true)"
  if [[ "${mapping}" =~ :([0-9]+)$ ]]; then
    echo "${BASH_REMATCH[1]}"
  fi
}

is_port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltnH 2>/dev/null | awk '{print $4}' | grep -Eq "(^|:)${port}$" && return 0 || return 1
  elif command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"${port}" -sTCP:LISTEN -Pn >/dev/null 2>&1 && return 0 || return 1
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c "import socket, sys; s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); rc = s.connect_ex(('127.0.0.1', ${port})); s.close(); sys.exit(0 if rc == 0 else 1)" && return 0 || return 1
  fi
  return 1
}

resolve_stable_port() {
  local service="$1"
  local container_port="$2"
  local start_port="$3"
  local end_port="$4"

  local own_port
  own_port="$(get_own_port "${service}" "${container_port}")"
  if [[ -n "${own_port}" && "${own_port}" -ge "${start_port}" && "${own_port}" -le "${end_port}" ]]; then
    echo "${own_port}"
    return 0
  fi

  local p
  for ((p = start_port; p <= end_port; p++)); do
    if ! is_port_in_use "${p}"; then
      echo "${p}"
      return 0
    fi
  done

  echo "Error: no free port found for ${service} in range ${start_port}-${end_port}" >&2
  exit 1
}

set_env_var() {
  local env_file="$1"
  local key="$2"
  local val="$3"
  if [[ ! -f "${env_file}" ]]; then
    if [[ -f "${REPO_ROOT}/.env.example" ]]; then
      cp "${REPO_ROOT}/.env.example" "${env_file}"
    else
      touch "${env_file}"
    fi
  fi
  if grep -qE "^${key}=" "${env_file}"; then
    sed -i.bak -E "s|^${key}=.*|${key}=${val}|" "${env_file}"
    rm -f "${env_file}.bak"
  else
    printf '\n%s=%s\n' "${key}" "${val}" >> "${env_file}"
  fi
}

FRONTEND_PORT="$(resolve_stable_port frontend 80 "${FRONTEND_START}" "${FRONTEND_END}")"
BACKEND_HOST_PORT="$(resolve_stable_port backend 8000 "${BACKEND_START}" "${BACKEND_END}")"

set_env_var "${REPO_ROOT}/.env" "FRONTEND_PORT" "${FRONTEND_PORT}"
set_env_var "${REPO_ROOT}/.env" "BACKEND_HOST_PORT" "${BACKEND_HOST_PORT}"

export FRONTEND_PORT BACKEND_HOST_PORT

echo "MetaStudio -> Frontend: http://localhost:${FRONTEND_PORT} | Backend: http://localhost:${BACKEND_HOST_PORT}"

if [[ "${1:-}" == "--no-build" ]]; then
  docker compose up -d
else
  docker compose up --build -d
fi
docker compose ps
