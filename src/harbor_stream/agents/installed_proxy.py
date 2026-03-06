"""Proxy for Harbor installed agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..harbor_compat import (
    get_agent_config_class,
    get_agent_factory_class,
    get_base_installed_agent_class,
)
from ..helper import upload_and_start_helper

BaseInstalledAgent = get_base_installed_agent_class()


def _delegate_mode(agent_name: str) -> str:
    if agent_name == "claude-code":
        return "claude"
    if agent_name == "codex":
        return "codex"
    return "raw"


class StreamingInstalledAgentProxy(BaseInstalledAgent):
    """Delegate to a Harbor installed agent and launch the helper alongside it."""

    SUPPORTS_ATIF = True

    def __init__(
        self,
        logs_dir,
        model_name: str | None = None,
        *,
        target_name: str | None,
        target_import_path: str | None,
        target_kwargs: dict[str, Any] | None = None,
        target_env: dict[str, str] | None = None,
        stream_url: str,
        stream_token: str | None = None,
        logger=None,
        mcp_servers=None,
        skills_dir: str | None = None,
        **kwargs,
    ):
        super().__init__(
            logs_dir=logs_dir,
            model_name=model_name,
            logger=logger,
            mcp_servers=mcp_servers,
            skills_dir=skills_dir,
        )
        agent_config_class = get_agent_config_class()
        agent_factory = get_agent_factory_class()
        delegate_name = None if target_import_path else target_name

        config = agent_config_class(
            name=delegate_name,
            import_path=target_import_path,
            model_name=model_name,
            kwargs=target_kwargs or {},
            env=target_env or {},
        )
        self._delegate = agent_factory.create_agent_from_config(
            config,
            logs_dir=logs_dir,
            logger=logger or self.logger,
            mcp_servers=list(mcp_servers or getattr(self, "mcp_servers", [])),
            skills_dir=skills_dir,
        )
        self._stream_url = stream_url
        self._stream_token = stream_token
        self._target_name = target_name or self._delegate.name()

    @staticmethod
    def name() -> str:
        return "harbor-stream-installed-proxy"

    def version(self) -> str | None:
        return self._delegate.version()

    def to_agent_info(self):
        return self._delegate.to_agent_info()

    @property
    def _install_agent_template_path(self) -> Path:
        return Path(__file__)

    def create_run_agent_commands(self, instruction: str) -> list:
        raise NotImplementedError("StreamingInstalledAgentProxy delegates run commands")

    def populate_context_post_run(self, context) -> None:
        populate = getattr(self._delegate, "populate_context_post_run", None)
        if callable(populate):
            populate(context)

    async def setup(self, environment) -> None:
        await self._delegate.setup(environment)
        await upload_and_start_helper(
            environment=environment,
            mode=_delegate_mode(self._target_name),
            stream_url=self._stream_url,
            stream_token=self._stream_token,
            job_name=self.logs_dir.parent.parent.name,
            trial_id=environment.session_id,
            task_name=environment.environment_name,
            agent_name=self._target_name,
            environment_type=getattr(environment.type(), "value", None),
        )

    async def run(self, instruction, environment, context) -> None:
        await self._delegate.run(instruction, environment, context)
