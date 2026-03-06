#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ROOT="$(repo_root)"
PYTHON_CMD="$(default_python)"

cd "${ROOT}"

if ! command -v cross >/dev/null 2>&1; then
  cargo install cross --locked
fi

cross build --manifest-path watcher-rs/Cargo.toml --release --target x86_64-unknown-linux-musl --target-dir watcher-rs/target/cross-x86_64
cross build --manifest-path watcher-rs/Cargo.toml --release --target aarch64-unknown-linux-musl --target-dir watcher-rs/target/cross-aarch64

"${PYTHON_CMD}" scripts/stage_helper_assets.py \
  --amd64 watcher-rs/target/cross-x86_64/x86_64-unknown-linux-musl/release/harbor-stream-helper \
  --arm64 watcher-rs/target/cross-aarch64/aarch64-unknown-linux-musl/release/harbor-stream-helper
