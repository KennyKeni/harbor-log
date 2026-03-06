#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ROOT="$(repo_root)"
PYTHON_CMD="$(default_python)"
VENV_DIR="${VENV_DIR:-.venv}"

cd "${ROOT}"

"${PYTHON_CMD}" -m venv "${VENV_DIR}"
VENV_PYTHON="${VENV_PYTHON:-$(venv_python_path "${VENV_DIR}")}"

"${VENV_PYTHON}" -m pip install --upgrade pip build
"${VENV_PYTHON}" -m build
"${VENV_PYTHON}" -m pip install dist/*.whl
"${VENV_PYTHON}" -c "import harbor_stream; print('import-ok')"
"${VENV_PYTHON}" -m harbor_stream.cli run --help >/dev/null
