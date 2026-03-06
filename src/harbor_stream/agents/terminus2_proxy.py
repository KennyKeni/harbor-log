"""Proxy for Harbor Terminus 2."""

from __future__ import annotations

from typing import Any

from ..harbor_compat import get_agent_config_class, get_agent_factory_class, get_base_agent_class
from ..helper import upload_and_start_helper

BaseAgent = get_base_agent_class()


class StreamingTerminus2Proxy(BaseAgent):
    """Delegate to Harbor Terminus 2 and attach the helper in trajectory mode."""

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
        return "harbor-stream-terminus2-proxy"

    def version(self) -> str | None:
        return self._delegate.version()

    def to_agent_info(self):
        return self._delegate.to_agent_info()

    async def setup(self, environment) -> None:
        await self._delegate.setup(environment)
        await upload_and_start_helper(
            environment=environment,
            mode="terminus2",
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
