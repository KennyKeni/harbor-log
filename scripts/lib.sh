#!/usr/bin/env bash

repo_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
}

default_python() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    printf '%s\n' "${PYTHON_BIN}"
    return
  fi

  if command -v python3 >/dev/null 2>&1; then
    printf 'python3\n'
    return
  fi

  printf 'python\n'
}

venv_python_path() {
  local venv_dir="$1"
  if [[ -x "${venv_dir}/bin/python" ]]; then
    printf '%s/bin/python\n' "${venv_dir}"
  else
    printf '%s/Scripts/python.exe\n' "${venv_dir}"
  fi
}

require_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    printf '[harbor-stream] missing required command: %s\n' "${cmd}" >&2
    return 1
  fi
}
