#!/usr/bin/env python3
"""Stage built helper binaries into the Python package assets directory."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--amd64", type=Path, required=True)
    parser.add_argument("--arm64", type=Path, required=True)
    parser.add_argument(
        "--asset-dir",
        type=Path,
        default=Path("src/harbor_stream/assets"),
    )
    return parser.parse_args()


def stage_binary(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Missing helper binary: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    destination.chmod(0o755)


def main() -> None:
    args = parse_args()
    stage_binary(
        args.amd64,
        args.asset_dir / "harbor-stream-helper-linux-amd64",
    )
    stage_binary(
        args.arm64,
        args.asset_dir / "harbor-stream-helper-linux-arm64",
    )


if __name__ == "__main__":
    main()
