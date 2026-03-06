"""Harbor-integrated runner."""

from __future__ import annotations

import asyncio
from pathlib import Path

from .config import load_job_config, prepare_stream_settings
from .events import make_event
from .harbor_compat import get_job_class
from .proxying import rewrite_job_config
from .reconciliation import TrialRuntimeContext, emit_final_summary
from .sink import EventSink


def _environment_type_name(job_config: object) -> str | None:
    env_type = getattr(job_config.environment, "type", None)
    return getattr(env_type, "value", env_type)


def _trial_dir(hook_event: object) -> Path:
    config = hook_event.config
    return Path(config.trials_dir) / hook_event.trial_id


def _agent_name_from_result(hook_event: object) -> str | None:
    result = getattr(hook_event, "result", None)
    agent_info = getattr(result, "agent_info", None)
    if agent_info is not None and getattr(agent_info, "name", None):
        return agent_info.name
    kwargs = getattr(hook_event.config.agent, "kwargs", {})
    return kwargs.get("target_name")


async def run_harbor_stream(
    *,
    config_path: str,
    stream_url: str,
    stream_token: str | None,
    job_name: str | None,
    jobs_dir: str | None,
) -> int:
    base_config = load_job_config(config_path, job_name=job_name, jobs_dir=jobs_dir)
    environment_type = _environment_type_name(base_config)
    preliminary_rewrite = rewrite_job_config(
        base_config,
        helper_url=stream_url,
        stream_token=stream_token,
    )
    stream_settings = prepare_stream_settings(
        stream_url=stream_url,
        stream_token=stream_token,
        environment_type=environment_type,
        helper_required=preliminary_rewrite.helper_required,
    )
    rewritten = rewrite_job_config(
        base_config,
        helper_url=stream_settings.helper_url,
        stream_token=stream_settings.token,
    )

    sink = EventSink(url=stream_settings.sink_url, token=stream_settings.token)
    sink.start()

    Job = get_job_class()
    job = Job(rewritten.config)

    async def emit_trial_event(hook_event: object, event_type: str) -> None:
        sink.emit(
            make_event(
                source="host",
                delivery="live",
                event_type=event_type,
                job_name=rewritten.config.job_name,
                trial_id=hook_event.trial_id,
                task_name=hook_event.task_name,
                agent_name=_agent_name_from_result(hook_event),
                environment_type=_environment_type_name(hook_event.config),
                data={"timestamp": str(getattr(hook_event, "timestamp", ""))},
            )
        )

    async def on_trial_started(hook_event: object) -> None:
        await emit_trial_event(hook_event, "trial.started")

    async def on_environment_started(hook_event: object) -> None:
        await emit_trial_event(hook_event, "trial.environment_started")

    async def on_agent_started(hook_event: object) -> None:
        await emit_trial_event(hook_event, "trial.agent_started")

    async def on_verification_started(hook_event: object) -> None:
        await emit_trial_event(hook_event, "trial.verification_started")

    async def on_trial_cancelled(hook_event: object) -> None:
        await emit_trial_event(hook_event, "trial.cancelled")

    async def on_trial_ended(hook_event: object) -> None:
        await emit_trial_event(hook_event, "trial.finished")
        context = TrialRuntimeContext(
            job_name=rewritten.config.job_name,
            trial_id=hook_event.trial_id,
            task_name=hook_event.task_name,
            agent_name=_agent_name_from_result(hook_event),
            environment_type=_environment_type_name(hook_event.config),
        )
        emit_final_summary(
            sink=sink,
            trial_dir=_trial_dir(hook_event),
            context=context,
            result=getattr(hook_event, "result", None),
        )

    job.on_trial_started(on_trial_started)
    job.on_environment_started(on_environment_started)
    job.on_agent_started(on_agent_started)
    job.on_verification_started(on_verification_started)
    job.on_trial_cancelled(on_trial_cancelled)
    job.on_trial_ended(on_trial_ended)

    try:
        await job.run()
    finally:
        await asyncio.to_thread(sink.close)

    return 0
