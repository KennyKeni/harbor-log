from __future__ import annotations

from datetime import datetime, timezone
import json
import unittest
from uuid import uuid4

from harbor_stream.events import make_event


class EventEnvelopeTests(unittest.TestCase):
    def test_make_event_converts_non_json_types(self) -> None:
        payload = make_event(
            source="host",
            delivery="final_summary",
            event_type="agent.final.summary",
            job_name="job",
            trial_id="trial",
            task_name="task",
            agent_name="codex",
            environment_type="docker",
            data={
                "started_at": datetime(2026, 3, 5, tzinfo=timezone.utc),
                "task_id": uuid4(),
            },
        )

        rendered = json.dumps(payload)
        self.assertIn("started_at", rendered)
        self.assertIn("task_id", rendered)


if __name__ == "__main__":
    unittest.main()
