#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ROOT="$(repo_root)"
PYTHON_CMD="$(default_python)"

cd "${ROOT}"
PYTHONPATH=src "${PYTHON_CMD}" -m unittest discover -s tests -p 'test_*.py'
