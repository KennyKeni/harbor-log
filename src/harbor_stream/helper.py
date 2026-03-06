"""Runtime helper asset resolution and launch."""

from __future__ import annotations

from importlib import resources
import os
from pathlib import Path
import shlex


STATUS_DIR = "/logs/agent/.harbor-stream"
STATUS_PATH = f"{STATUS_DIR}/status.json"
REMOTE_HELPER_PATH = f"{STATUS_DIR}/helper"

ARCH_TO_ASSET = {
    "x86_64": "harbor-stream-helper-linux-amd64",
    "amd64": "harbor-stream-helper-linux-amd64",
    "aarch64": "harbor-stream-helper-linux-arm64",
    "arm64": "harbor-stream-helper-linux-arm64",
}


class HelperAssetError(RuntimeError):
    """Raised when helper assets cannot be resolved or started."""


def _candidate_override(asset_name: str) -> str | None:
    key = asset_name.upper().replace("-", "_")
    return os.environ.get(f"HARBOR_STREAM_ASSET_{key}")


def resolve_local_helper_asset(remote_arch: str) -> Path:
    asset_name = ARCH_TO_ASSET.get(remote_arch.strip())
    if asset_name is None:
        raise HelperAssetError(f"Unsupported helper architecture: {remote_arch}")

    override = _candidate_override(asset_name)
    if override:
        return Path(override)

    asset_root = resources.files("harbor_stream").joinpath("assets")
    asset = asset_root.joinpath(asset_name)
    if not asset.is_file():
        raise HelperAssetError(
            f"Helper asset {asset_name} is missing. "
            "Build or stage helper binaries before running supported agents."
        )
    return Path(asset)


async def detect_remote_arch(environment: object) -> str:
    result = await environment.exec("uname -m", timeout_sec=5)
    output = (result.stdout or "").strip().splitlines()
    if not output:
        raise HelperAssetError("Failed to detect remote architecture")
    return output[0]


async def detect_patch_root(environment: object) -> str:
    result = await environment.exec("pwd", timeout_sec=5)
    output = (result.stdout or "").strip().splitlines()
    if output:
        return output[0]
    return "/app"


async def upload_and_start_helper(
    *,
    environment: object,
    mode: str,
    stream_url: str,
    stream_token: str | None,
    job_name: str,
    trial_id: str,
    task_name: str,
    agent_name: str,
    environment_type: str | None,
) -> None:
    remote_arch = await detect_remote_arch(environment)
    local_asset = resolve_local_helper_asset(remote_arch)
    patch_root = await detect_patch_root(environment)

    await environment.exec(f"mkdir -p {shlex.quote(STATUS_DIR)}", timeout_sec=10)
    await environment.upload_file(str(local_asset), REMOTE_HELPER_PATH)
    await environment.exec(f"chmod +x {shlex.quote(REMOTE_HELPER_PATH)}", timeout_sec=10)

    env_exports = {
        "HARBOR_STREAM_MODE": mode,
        "HARBOR_STREAM_STREAM_URL": stream_url,
        "HARBOR_STREAM_JOB_NAME": job_name,
        "HARBOR_STREAM_TRIAL_ID": trial_id,
        "HARBOR_STREAM_TASK_NAME": task_name,
        "HARBOR_STREAM_AGENT_NAME": agent_name,
        "HARBOR_STREAM_ENVIRONMENT_TYPE": environment_type or "",
        "HARBOR_STREAM_PATCH_ROOT": patch_root,
        "HARBOR_STREAM_STATUS_PATH": STATUS_PATH,
        "HARBOR_STREAM_LOG_ROOT": "/logs/agent",
    }
    if stream_token:
        env_exports["HARBOR_STREAM_STREAM_TOKEN"] = stream_token

    env_prefix = " ".join(
        f"{key}={shlex.quote(value)}" for key, value in env_exports.items()
    )
    command = (
        f"{env_prefix} nohup {shlex.quote(REMOTE_HELPER_PATH)} "
        f"> {shlex.quote(STATUS_DIR)}/helper.stdout "
        f"2> {shlex.quote(STATUS_DIR)}/helper.stderr "
        "< /dev/null &"
    )
    await environment.exec(command, timeout_sec=10)
