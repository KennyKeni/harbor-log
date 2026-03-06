"""Lazy Harbor imports and runtime classification helpers."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from typing import Any


class HarborImportError(RuntimeError):
    """Raised when Harbor is not installed or cannot be imported."""


def _import(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ImportError as exc:  # pragma: no cover - exercised via callers
        raise HarborImportError(
            "harbor-stream requires Harbor to be installed. "
            "Install `harbor` into the same environment as `harbor-stream`."
        ) from exc


def import_symbol(path: str) -> Any:
    module_path, _, symbol_name = path.partition(":")
    if not module_path or not symbol_name:
        raise ValueError(f"Invalid import path: {path}")
    module = _import(module_path)
    return getattr(module, symbol_name)


def get_job_class() -> type:
    return getattr(_import("harbor.job"), "Job")


def get_job_config_class() -> type:
    return getattr(_import("harbor.models.job.config"), "JobConfig")


def get_agent_config_class() -> type:
    return getattr(_import("harbor.models.trial.config"), "AgentConfig")


def get_agent_factory_class() -> type:
    return getattr(_import("harbor.agents.factory"), "AgentFactory")


def get_base_agent_class() -> type:
    return getattr(_import("harbor.agents.base"), "BaseAgent")


def get_base_installed_agent_class() -> type:
    return getattr(_import("harbor.agents.installed.base"), "BaseInstalledAgent")


def get_trial_paths_class() -> type:
    return getattr(_import("harbor.models.trial.paths"), "TrialPaths")


def get_terminus2_class() -> type:
    return getattr(_import("harbor.agents.terminus_2"), "Terminus2")


@dataclass(frozen=True)
class AgentRuntimeKind:
    """How the agent should be instrumented."""

    proxy_kind: str
    original_name: str | None
    original_import_path: str | None


FINAL_ONLY_NAMES = {"oracle", "nop"}


def _classify_by_name(name: str | None) -> AgentRuntimeKind | None:
    if name is None:
        return None
    if name in FINAL_ONLY_NAMES:
        return AgentRuntimeKind("none", name, None)
    if name == "terminus-2":
        return AgentRuntimeKind("terminus2", name, None)
    return AgentRuntimeKind("installed", name, None)


def classify_agent_config(agent_config: Any) -> AgentRuntimeKind:
    """Decide whether the config needs a proxy wrapper."""

    by_name = _classify_by_name(getattr(agent_config, "name", None))
    if by_name is not None:
        return by_name

    import_path = getattr(agent_config, "import_path", None)
    if not import_path:
        return AgentRuntimeKind("none", None, None)

    agent_class = import_symbol(import_path)
    if issubclass(agent_class, get_terminus2_class()):
        return AgentRuntimeKind("terminus2", agent_class.name(), import_path)
    if issubclass(agent_class, get_base_installed_agent_class()):
        return AgentRuntimeKind("installed", agent_class.name(), import_path)
    return AgentRuntimeKind("none", getattr(agent_class, "name", lambda: None)(), import_path)
