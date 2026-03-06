#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ROOT="$(repo_root)"
PYTHON_CMD="$(default_python)"
HARBOR_DIR="${HARBOR_DIR:-/tmp/harbor}"
TASK_PATH="${HARBOR_STREAM_TEST_TASK_PATH:-${HARBOR_DIR}/examples/tasks/hello-world}"

cd "${ROOT}"

if [[ "${INSTALL_PACKAGE:-1}" == "1" ]]; then
  "${PYTHON_CMD}" -m pip install --upgrade pip
  "${PYTHON_CMD}" -m pip install .
else
  export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
fi

if [[ ! -d "${TASK_PATH}" ]]; then
  if [[ ! -d "${HARBOR_DIR}" ]]; then
    git clone --depth 1 https://github.com/harbor-framework/harbor "${HARBOR_DIR}"
  fi
fi

export HARBOR_STREAM_TEST_TASK_PATH="${TASK_PATH}"

export HARBOR_STREAM_RUN_E2E="${HARBOR_STREAM_RUN_E2E:-1}"

"${PYTHON_CMD}" -m unittest tests.test_e2e
