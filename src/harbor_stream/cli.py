"""harbor-stream CLI."""

from __future__ import annotations

import argparse
import asyncio
import sys

from .config import StreamConfigError
from .harbor_compat import HarborImportError
from .runner import run_harbor_stream


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="harbor-stream",
        description="Run Harbor jobs with streaming lifecycle and agent events.",
    )
    sub = parser.add_subparsers(dest="command")
    run_parser = sub.add_parser("run", help="Run Harbor with streaming")
    run_parser.add_argument(
        "--config", required=True,
        help="Harbor JobConfig file (.yaml, .yml, or .json)",
    )
    run_parser.add_argument(
        "--stream-url", required=True,
        help="HTTP endpoint that receives event envelopes",
    )
    run_parser.add_argument(
        "--stream-token", default=None,
        help="Optional bearer token for the event sink",
    )
    run_parser.add_argument(
        "--job-name", default=None,
        help="Override Harbor job_name before launch",
    )
    run_parser.add_argument(
        "--jobs-dir", default=None,
        help="Override Harbor jobs_dir before launch",
    )

    args = parser.parse_args()

    if args.command != "run":
        parser.print_help()
        sys.exit(1)

    try:
        exit_code = asyncio.run(
            run_harbor_stream(
                config_path=args.config,
                stream_url=args.stream_url,
                stream_token=args.stream_token,
                job_name=args.job_name,
                jobs_dir=args.jobs_dir,
            )
        )
    except (FileNotFoundError, HarborImportError, StreamConfigError) as exc:
        print(f"[harbor-stream] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:  # pragma: no cover - top-level guard
        print(f"[harbor-stream] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    sys.exit(exit_code)
