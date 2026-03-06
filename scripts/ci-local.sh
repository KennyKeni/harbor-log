#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bash "${ROOT}/scripts/test-python.sh"
bash "${ROOT}/scripts/test-rust.sh"

if [[ "${RUN_HELPER_ASSETS:-0}" == "1" ]]; then
  bash "${ROOT}/scripts/build-helper-assets.sh"
fi

if [[ "${RUN_PACKAGE_SMOKE:-0}" == "1" ]]; then
  bash "${ROOT}/scripts/package-smoke.sh"
fi

if [[ "${RUN_DOCKER_E2E:-0}" == "1" ]]; then
  bash "${ROOT}/scripts/e2e-docker.sh"
fi
