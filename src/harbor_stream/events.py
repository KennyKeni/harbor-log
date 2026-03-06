"""Shared event envelope helpers."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from uuid import UUID
import uuid

SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_jsonable(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date, UUID, Path, Enum)):
        return str(value)
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]
    return str(value)


def make_event(
    *,
    source: str,
    delivery: str,
    event_type: str,
    job_name: str,
    trial_id: str | None,
    task_name: str | None,
    agent_name: str | None,
    environment_type: str | None,
    data: dict,
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "timestamp": utc_now(),
        "source": source,
        "delivery": delivery,
        "job_name": job_name,
        "trial_id": trial_id,
        "task_name": task_name,
        "agent_name": agent_name,
        "environment_type": environment_type,
        "event_type": event_type,
        "data": to_jsonable(data),
    }


def summarize_trial_result(result: object | None) -> dict:
    if result is None:
        return {}

    verifier_result = getattr(result, "verifier_result", None)
    exception_info = getattr(result, "exception_info", None)
    agent_info = getattr(result, "agent_info", None)
    return {
        "started_at": getattr(result, "started_at", None),
        "finished_at": getattr(result, "finished_at", None),
        "task_name": getattr(result, "task_name", None),
        "task_id": str(getattr(result, "task_id", "")) or None,
        "agent_name": getattr(agent_info, "name", None) if agent_info else None,
        "agent_version": getattr(agent_info, "version", None) if agent_info else None,
        "reward": getattr(verifier_result, "reward", None) if verifier_result else None,
        "rewards": getattr(verifier_result, "rewards", None) if verifier_result else None,
        "exception_type": getattr(exception_info, "exception_type", None)
        if exception_info
        else None,
        "exception_message": getattr(exception_info, "exception_message", None)
        if exception_info
        else None,
    }
