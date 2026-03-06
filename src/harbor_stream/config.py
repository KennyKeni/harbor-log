"""Config loading and stream URL validation."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from .harbor_compat import get_job_config_class

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


class StreamConfigError(ValueError):
    """Raised when the stream settings are invalid."""


@dataclass(frozen=True)
class StreamSettings:
    sink_url: str
    helper_url: str
    token: str | None


def normalize_stream_url(url: str) -> str:
    return url.rstrip("/")


def _rewrite_loopback_for_docker(url: str) -> str:
    parsed = urlparse(url)
    auth = ""
    if parsed.username is not None:
        auth = parsed.username
        if parsed.password is not None:
            auth = f"{auth}:{parsed.password}"
        auth = f"{auth}@"
    port = f":{parsed.port}" if parsed.port is not None else ""
    docker_host = os.environ.get("HARBOR_STREAM_DOCKER_HOST", "host.docker.internal")
    return urlunparse(parsed._replace(netloc=f"{auth}{docker_host}{port}"))


def prepare_stream_settings(
    *,
    stream_url: str,
    stream_token: str | None,
    environment_type: str | None,
    helper_required: bool,
) -> StreamSettings:
    sink_url = normalize_stream_url(stream_url)
    helper_url = sink_url
    parsed = urlparse(sink_url)
    hostname = parsed.hostname or ""

    if helper_required and hostname in LOOPBACK_HOSTS:
        if environment_type == "docker":
            helper_url = _rewrite_loopback_for_docker(sink_url)
        else:
            raise StreamConfigError(
                "--stream-url uses a loopback address, but the selected Harbor "
                "environment cannot reach the host. Provide a container-reachable URL."
            )

    return StreamSettings(sink_url=sink_url, helper_url=helper_url, token=stream_token)


def load_job_config(
    config_path: str | Path,
    *,
    job_name: str | None,
    jobs_dir: str | None,
):
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file does not exist: {path}")

    raw = path.read_text()
    job_config_class = get_job_config_class()
    if path.suffix in {".yaml", ".yml"}:
        import yaml

        config = job_config_class.model_validate(yaml.safe_load(raw))
    elif path.suffix == ".json":
        config = job_config_class.model_validate_json(raw)
    else:
        raise StreamConfigError(
            f"Unsupported config extension {path.suffix!r}; use .yaml, .yml, or .json"
        )

    if job_name is not None:
        config.job_name = job_name
    if jobs_dir is not None:
        config.jobs_dir = Path(jobs_dir)

    return config


def dump_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)
