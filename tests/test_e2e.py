from __future__ import annotations

import asyncio
from contextlib import contextmanager
import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest


HARBOR_AVAILABLE = importlib.util.find_spec("harbor") is not None
RUN_E2E = os.environ.get("HARBOR_STREAM_RUN_E2E") == "1"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _harbor_task_path() -> Path:
    return Path(os.environ["HARBOR_STREAM_TEST_TASK_PATH"])


def _event_types(events: list[dict]) -> list[str]:
    return [event["event_type"] for event in events]


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _CollectorHandler(BaseHTTPRequestHandler):
    events: list[dict] = []

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers["Content-Length"])
        payload = json.loads(self.rfile.read(length))
        self.__class__.events.append(payload)
        self.send_response(200)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return None


@contextmanager
def collector_server():
    port = _find_free_port()
    _CollectorHandler.events = []
    server = ThreadingHTTPServer(("0.0.0.0", port), _CollectorHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/events", _CollectorHandler.events
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def write_job_config(
    path: Path,
    *,
    agent_import_path: str,
    model_name: str | None = "fake/model",
) -> None:
    payload = {
        "job_name": "e2e-job",
        "jobs_dir": str(path.parent / "jobs"),
        "tasks": [{"path": str(_harbor_task_path())}],
        "agents": [
            {
                "import_path": agent_import_path,
                "model_name": model_name,
            }
        ],
        "environment": {"type": "docker", "delete": True},
    }
    path.write_text(json.dumps(payload))


def wait_for(predicate, *, timeout: float = 120.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.25)
    raise AssertionError("condition not met before timeout")


@unittest.skipUnless(HARBOR_AVAILABLE and RUN_E2E, "set HARBOR_STREAM_RUN_E2E=1 with Harbor installed")
class HarborStreamE2ETests(unittest.TestCase):
    def run_job(self, *, agent_import_path: str, expected_event_type: str) -> list[dict]:
        from harbor_stream.runner import run_harbor_stream

        with tempfile.TemporaryDirectory() as tmp, collector_server() as (stream_url, events):
            tmp_path = Path(tmp)
            config_path = tmp_path / "job.json"
            write_job_config(config_path, agent_import_path=agent_import_path)

            exit_code = asyncio.run(
                run_harbor_stream(
                    config_path=str(config_path),
                    stream_url=stream_url,
                    stream_token=None,
                    job_name=None,
                    jobs_dir=None,
                )
            )
            self.assertEqual(exit_code, 0)

            wait_for(lambda: any(event["event_type"] == "agent.final.summary" for event in events))
            self.assertIn(expected_event_type, _event_types(events))
            self.assertIn("trial.finished", _event_types(events))
            return list(events)

    def test_claude_semantic_live(self) -> None:
        events = self.run_job(
            agent_import_path="tests.integration_agents:FakeClaudeCodeAgent",
            expected_event_type="agent.tool_call",
        )
        helper_events = [event for event in events if event["source"] == "helper"]
        self.assertTrue(any(event["event_type"] == "agent.tool_call" for event in helper_events))
        self.assertTrue(any(event["event_type"] == "agent.tool_result" for event in helper_events))

    def test_codex_semantic_live(self) -> None:
        events = self.run_job(
            agent_import_path="tests.integration_agents:FakeCodexAgent",
            expected_event_type="agent.tool_result",
        )
        helper_events = [event for event in events if event["source"] == "helper"]
        self.assertTrue(any(event["event_type"] == "agent.tool_call" for event in helper_events))
        self.assertTrue(any(event["event_type"] == "agent.tool_result" for event in helper_events))

    def test_terminus2_semantic_live(self) -> None:
        events = self.run_job(
            agent_import_path="tests.integration_agents:FakeTerminus2",
            expected_event_type="agent.message",
        )
        helper_events = [event for event in events if event["source"] == "helper"]
        self.assertTrue(any(event["event_type"] == "agent.tool_call" for event in helper_events))
        self.assertTrue(any(event["event_type"] == "agent.tool_result" for event in helper_events))

    def test_raw_fallback(self) -> None:
        events = self.run_job(
            agent_import_path="tests.integration_agents:FakeRawInstalledAgent",
            expected_event_type="agent.raw_line",
        )
        self.assertTrue(any(event["event_type"] == "agent.final.summary" for event in events))


if __name__ == "__main__":
    unittest.main()
