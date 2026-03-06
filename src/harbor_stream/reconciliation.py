"""Final summary generation and ATIF replay."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from .events import make_event, summarize_trial_result

STATUS_PATH = Path("agent/.harbor-stream/status.json")
TRAJECTORY_MAIN = "trajectory.json"


@dataclass(frozen=True)
class TrialRuntimeContext:
    job_name: str
    trial_id: str
    task_name: str
    agent_name: str | None
    environment_type: str | None


def load_helper_status(trial_dir: Path) -> dict | None:
    path = trial_dir / STATUS_PATH
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def load_trajectory_segments(agent_dir: Path) -> list[Path]:
    main_path = agent_dir / TRAJECTORY_MAIN
    continuation_paths = sorted(
        agent_dir.glob("trajectory.cont-*.json"),
        key=lambda path: int(re.search(r"cont-(\d+)", path.name).group(1)),  # type: ignore[union-attr]
    )
    paths: list[Path] = []
    if main_path.exists():
        paths.append(main_path)
    paths.extend(continuation_paths)
    return paths


def _emit_step_events(
    *,
    sink: object,
    context: TrialRuntimeContext,
    delivery: str,
    session_id: str | None,
    steps: list[dict],
) -> None:
    session_sent = False
    for step in steps:
        if not session_sent:
            sink.emit(
                make_event(
                    source="host",
                    delivery=delivery,
                    event_type="agent.session_started",
                    job_name=context.job_name,
                    trial_id=context.trial_id,
                    task_name=context.task_name,
                    agent_name=context.agent_name,
                    environment_type=context.environment_type,
                    data={"session_id": session_id, "model_name": step.get("model_name")},
                )
            )
            session_sent = True

        if step.get("source") != "agent":
            continue

        if step.get("reasoning_content"):
            sink.emit(
                make_event(
                    source="host",
                    delivery=delivery,
                    event_type="agent.reasoning",
                    job_name=context.job_name,
                    trial_id=context.trial_id,
                    task_name=context.task_name,
                    agent_name=context.agent_name,
                    environment_type=context.environment_type,
                    data={
                        "step_id": step.get("step_id"),
                        "timestamp": step.get("timestamp"),
                        "text": step.get("reasoning_content"),
                    },
                )
            )

        tool_calls = step.get("tool_calls") or []
        if tool_calls:
            for tool_call in tool_calls:
                sink.emit(
                    make_event(
                        source="host",
                        delivery=delivery,
                        event_type="agent.tool_call",
                        job_name=context.job_name,
                        trial_id=context.trial_id,
                        task_name=context.task_name,
                        agent_name=context.agent_name,
                        environment_type=context.environment_type,
                        data={
                            "step_id": step.get("step_id"),
                            "timestamp": step.get("timestamp"),
                            "call_id": tool_call.get("tool_call_id"),
                            "tool_name": tool_call.get("function_name"),
                            "arguments": tool_call.get("arguments"),
                        },
                    )
                )
            observation = step.get("observation") or {}
            for result in observation.get("results", []):
                sink.emit(
                    make_event(
                        source="host",
                        delivery=delivery,
                        event_type="agent.tool_result",
                        job_name=context.job_name,
                        trial_id=context.trial_id,
                        task_name=context.task_name,
                        agent_name=context.agent_name,
                        environment_type=context.environment_type,
                        data={
                            "step_id": step.get("step_id"),
                            "timestamp": step.get("timestamp"),
                            "call_id": result.get("source_call_id"),
                            "content": result.get("content"),
                        },
                    )
                )
            continue

        if step.get("message"):
            sink.emit(
                make_event(
                    source="host",
                    delivery=delivery,
                    event_type="agent.message",
                    job_name=context.job_name,
                    trial_id=context.trial_id,
                    task_name=context.task_name,
                    agent_name=context.agent_name,
                    environment_type=context.environment_type,
                    data={
                        "step_id": step.get("step_id"),
                        "timestamp": step.get("timestamp"),
                        "text": step.get("message"),
                    },
                )
            )


def maybe_replay_trajectory(
    *,
    sink: object,
    trial_dir: Path,
    context: TrialRuntimeContext,
    helper_status: dict | None,
) -> dict:
    agent_dir = trial_dir / "agent"
    trajectories = load_trajectory_segments(agent_dir)
    summary = {
        "trajectory_present": bool(trajectories),
        "trajectory_files": [path.name for path in trajectories],
        "steps_count": 0,
    }

    if not trajectories:
        return summary

    should_replay = not helper_status or int(helper_status.get("events_emitted", 0)) == 0

    for path in trajectories:
        payload = json.loads(path.read_text())
        steps = payload.get("steps", [])
        summary["steps_count"] += len(steps)
        if should_replay:
            _emit_step_events(
                sink=sink,
                context=context,
                delivery="final_replay",
                session_id=payload.get("session_id"),
                steps=steps,
            )

    return summary


def emit_final_summary(
    *,
    sink: object,
    trial_dir: Path,
    context: TrialRuntimeContext,
    result: object | None,
) -> None:
    helper_status = load_helper_status(trial_dir)
    trajectory_summary = maybe_replay_trajectory(
        sink=sink,
        trial_dir=trial_dir,
        context=context,
        helper_status=helper_status,
    )
    data = summarize_trial_result(result)
    data["helper_status"] = helper_status
    data["trajectory"] = trajectory_summary

    sink.emit(
        make_event(
            source="host",
            delivery="final_summary",
            event_type="agent.final.summary",
            job_name=context.job_name,
            trial_id=context.trial_id,
            task_name=context.task_name,
            agent_name=context.agent_name,
            environment_type=context.environment_type,
            data=data,
        )
    )
