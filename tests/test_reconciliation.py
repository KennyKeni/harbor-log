from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from harbor_stream.reconciliation import TrialRuntimeContext, emit_final_summary


class FakeSink:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def emit(self, payload: dict) -> None:
        self.events.append(payload)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


class ReconciliationTests(unittest.TestCase):
    def test_final_summary_replays_when_helper_has_no_live_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trial_dir = Path(tmp)
            write_json(
                trial_dir / "agent" / "trajectory.json",
                {
                    "session_id": "session-1",
                    "steps": [
                        {
                            "step_id": 1,
                            "timestamp": "2026-03-05T00:00:00+00:00",
                            "source": "agent",
                            "message": "hello",
                        },
                        {
                            "step_id": 2,
                            "timestamp": "2026-03-05T00:00:01+00:00",
                            "source": "agent",
                            "tool_calls": [
                                {
                                    "tool_call_id": "call-1",
                                    "function_name": "bash",
                                    "arguments": {"cmd": "ls"},
                                }
                            ],
                            "observation": {
                                "results": [
                                    {"source_call_id": "call-1", "content": "stdout"}
                                ]
                            },
                        },
                    ],
                },
            )

            sink = FakeSink()
            emit_final_summary(
                sink=sink,
                trial_dir=trial_dir,
                context=TrialRuntimeContext(
                    job_name="job",
                    trial_id="trial",
                    task_name="task",
                    agent_name="claude-code",
                    environment_type="docker",
                ),
                result=None,
            )

            event_types = [event["event_type"] for event in sink.events]
            self.assertIn("agent.session_started", event_types)
            self.assertIn("agent.message", event_types)
            self.assertIn("agent.tool_call", event_types)
            self.assertIn("agent.tool_result", event_types)
            self.assertEqual(event_types[-1], "agent.final.summary")

    def test_final_summary_skips_replay_when_helper_reported_live_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trial_dir = Path(tmp)
            write_json(
                trial_dir / "agent" / "trajectory.json",
                {"session_id": "session-1", "steps": [{"step_id": 1, "source": "agent"}]},
            )
            write_json(
                trial_dir / "agent" / ".harbor-stream" / "status.json",
                {"events_emitted": 4},
            )

            sink = FakeSink()
            emit_final_summary(
                sink=sink,
                trial_dir=trial_dir,
                context=TrialRuntimeContext(
                    job_name="job",
                    trial_id="trial",
                    task_name="task",
                    agent_name="codex",
                    environment_type="modal",
                ),
                result=None,
            )

            self.assertEqual(
                [event["event_type"] for event in sink.events],
                ["agent.final.summary"],
            )


if __name__ == "__main__":
    unittest.main()
