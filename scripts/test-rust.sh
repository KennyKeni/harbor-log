#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ROOT="$(repo_root)"

cd "${ROOT}"
cargo test --manifest-path watcher-rs/Cargo.toml
