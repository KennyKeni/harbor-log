from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path


def _write_executable_script(contents: str) -> Path:
    handle = tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False)
    handle.write(contents)
    handle.close()
    path = Path(handle.name)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _simple_install_script() -> Path:
    return _write_executable_script("#!/bin/sh\nexit 0\n")


def _trajectory_payload(step_count: int) -> dict:
    steps = [
        {
            "step_id": 1,
            "timestamp": "2026-03-05T00:00:00+00:00",
            "source": "agent",
            "message": "starting",
        }
    ]
    if step_count >= 2:
        steps.append(
            {
                "step_id": 2,
                "timestamp": "2026-03-05T00:00:01+00:00",
                "source": "agent",
                "tool_calls": [
                    {
                        "tool_call_id": "call-1",
                        "function_name": "bash",
                        "arguments": {"cmd": "echo Hello, world! > hello.txt"},
                    }
                ],
                "observation": {
                    "results": [
                        {
                            "source_call_id": "call-1",
                            "content": "done",
                        }
                    ]
                },
            }
        )
    if step_count >= 3:
        steps.append(
            {
                "step_id": 3,
                "timestamp": "2026-03-05T00:00:02+00:00",
                "source": "agent",
                "message": "finished",
            }
        )
    return {
        "schema_version": "ATIF-v1.5",
        "session_id": "session-1",
        "agent": {
            "name": "fake",
            "version": "1.0.0",
            "model_name": "fake/model",
        },
        "steps": steps,
    }


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _hello_world_command() -> str:
    return "echo 'Hello, world!' > /app/hello.txt"


def _claude_stream_command() -> str:
    events = [
        '{"type":"system","subtype":"init","session_id":"session-1","model":"fake/model","tools":["bash"]}',
        '{"type":"assistant","message":{"content":[{"type":"text","text":"starting"}]}}',
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"bash","id":"call-1","input":{"cmd":"echo \\"Hello, world!\\" > /app/hello.txt"}}]}}',
        '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"call-1","is_error":false}]},"tool_use_result":{"stdout":"done","stderr":""}}',
        '{"type":"assistant","message":{"content":[{"type":"text","text":"finished"}]}}',
    ]
    commands = [
        "mkdir -p /logs/agent",
        "rm -f /logs/agent/claude-code.txt",
        f"printf '%s\\n' '{events[0]}' >> /logs/agent/claude-code.txt",
        "sleep 1",
        f"printf '%s\\n' '{events[1]}' >> /logs/agent/claude-code.txt",
        "sleep 1",
        f"printf '%s\\n' '{events[2]}' >> /logs/agent/claude-code.txt",
        _hello_world_command(),
        "sleep 1",
        f"printf '%s\\n' '{events[3]}' >> /logs/agent/claude-code.txt",
        "sleep 1",
        f"printf '%s\\n' '{events[4]}' >> /logs/agent/claude-code.txt",
    ]
    return " && ".join(commands)


def _codex_stream_command() -> str:
    events = [
        '{"type":"session_meta","payload":{"id":"session-1","cli_version":"1.0.0"}}',
        '{"type":"turn_context","payload":{"model":"fake/model"}}',
        '{"type":"response_item","payload":{"type":"message","role":"assistant","content":[{"text":"starting"}]}}',
        '{"type":"response_item","payload":{"type":"function_call","call_id":"call-1","name":"bash","arguments":"{\\"cmd\\": \\"echo Hello, world! > /app/hello.txt\\"}"}}',
        '{"type":"response_item","payload":{"type":"function_call_output","call_id":"call-1","output":"{\\"output\\": \\"done\\"}"}}',
        '{"type":"response_item","payload":{"type":"message","role":"assistant","content":[{"text":"finished"}]}}',
    ]
    commands = [
        "mkdir -p /logs/agent",
        "rm -f /logs/agent/codex.txt",
        *[
            f"printf '%s\\n' '{event}' >> /logs/agent/codex.txt && sleep 1"
            for event in events[:4]
        ],
        _hello_world_command(),
        f"printf '%s\\n' '{events[4]}' >> /logs/agent/codex.txt",
        "sleep 1",
        f"printf '%s\\n' '{events[5]}' >> /logs/agent/codex.txt",
    ]
    return " && ".join(commands)


try:
    from harbor.agents.base import BaseAgent
    from harbor.agents.installed.base import BaseInstalledAgent, ExecInput
    from harbor.agents.terminus_2 import Terminus2
    from harbor.models.agent.context import AgentContext
except Exception:  # pragma: no cover - integration only
    BaseAgent = object
    BaseInstalledAgent = object
    Terminus2 = object
    ExecInput = object
    AgentContext = object


class FakeClaudeCodeAgent(BaseInstalledAgent):  # pragma: no cover - integration only
    SUPPORTS_ATIF = True

    @staticmethod
    def name() -> str:
        return "claude-code"

    @property
    def _install_agent_template_path(self) -> Path:
        return _simple_install_script()

    def version(self) -> str | None:
        return "1.0.0"

    def populate_context_post_run(self, context: AgentContext) -> None:
        _write_json(self.logs_dir / "trajectory.json", _trajectory_payload(3))

    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        return [ExecInput(command=_claude_stream_command())]


class FakeCodexAgent(BaseInstalledAgent):  # pragma: no cover - integration only
    SUPPORTS_ATIF = True

    @staticmethod
    def name() -> str:
        return "codex"

    @property
    def _install_agent_template_path(self) -> Path:
        return _simple_install_script()

    def version(self) -> str | None:
        return "1.0.0"

    def populate_context_post_run(self, context: AgentContext) -> None:
        _write_json(self.logs_dir / "trajectory.json", _trajectory_payload(3))

    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        return [ExecInput(command=_codex_stream_command())]


class FakeRawInstalledAgent(BaseInstalledAgent):  # pragma: no cover - integration only
    SUPPORTS_ATIF = False

    @staticmethod
    def name() -> str:
        return "fake-goose"

    @property
    def _install_agent_template_path(self) -> Path:
        return _simple_install_script()

    def version(self) -> str | None:
        return "1.0.0"

    def populate_context_post_run(self, context: AgentContext) -> None:
        return None

    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        command = (
            "mkdir -p /logs/agent && "
            "printf '%s\\n' 'raw output line 1' > /logs/agent/goose.txt && "
            f"{_hello_world_command()} && "
            "sleep 1 && "
            "printf '%s\\n' 'raw output line 2' >> /logs/agent/goose.txt"
        )
        return [ExecInput(command=command)]


class FakeTerminus2(Terminus2):  # pragma: no cover - integration only
    SUPPORTS_ATIF = True

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        logger=None,
        mcp_servers=None,
        skills_dir: str | None = None,
        *args,
        **kwargs,
    ):
        BaseAgent.__init__(
            self,
            logs_dir=logs_dir,
            model_name=model_name or "fake/model",
            logger=logger,
            mcp_servers=mcp_servers,
            skills_dir=skills_dir,
        )

    @staticmethod
    def name() -> str:
        return "terminus-2"

    def version(self) -> str | None:
        return "2.0.0"

    async def setup(self, environment) -> None:
        return None

    async def run(self, instruction: str, environment, context) -> None:
        trajectory_path = self.logs_dir / "trajectory.json"
        _write_json(trajectory_path, _trajectory_payload(1))
        await environment.exec("sleep 1", timeout_sec=5)
        _hello_world = _hello_world_command()
        await environment.exec(_hello_world, timeout_sec=10)
        _write_json(trajectory_path, _trajectory_payload(2))
        await environment.exec("sleep 1", timeout_sec=5)
        _write_json(trajectory_path, _trajectory_payload(3))
