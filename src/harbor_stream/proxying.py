"""Rewrite Harbor agent configs to proxy agents."""

from __future__ import annotations

import copy
from dataclasses import dataclass

from .harbor_compat import classify_agent_config


INSTALLED_PROXY_IMPORT = "harbor_stream.agents.installed_proxy:StreamingInstalledAgentProxy"
TERMINUS2_PROXY_IMPORT = "harbor_stream.agents.terminus2_proxy:StreamingTerminus2Proxy"


@dataclass(frozen=True)
class ProxyRewriteResult:
    config: object
    helper_required: bool


def rewrite_job_config(config: object, *, helper_url: str, stream_token: str | None) -> ProxyRewriteResult:
    rewritten = copy.deepcopy(config)
    helper_required = False

    for agent_config in rewritten.agents:
        classification = classify_agent_config(agent_config)
        if classification.proxy_kind == "none":
            continue

        helper_required = True
        original_kwargs = copy.deepcopy(getattr(agent_config, "kwargs", {}))
        original_env = copy.deepcopy(getattr(agent_config, "env", {}))

        agent_config.name = None
        agent_config.import_path = (
            TERMINUS2_PROXY_IMPORT
            if classification.proxy_kind == "terminus2"
            else INSTALLED_PROXY_IMPORT
        )
        agent_config.env = {}
        agent_config.kwargs = {
            "target_name": classification.original_name,
            "target_import_path": classification.original_import_path,
            "target_kwargs": original_kwargs,
            "target_env": original_env,
            "stream_url": helper_url,
            "stream_token": stream_token,
        }

    return ProxyRewriteResult(config=rewritten, helper_required=helper_required)
