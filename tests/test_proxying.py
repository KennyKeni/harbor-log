from __future__ import annotations

from dataclasses import dataclass, field
import unittest

from harbor_stream.proxying import (
    INSTALLED_PROXY_IMPORT,
    TERMINUS2_PROXY_IMPORT,
    rewrite_job_config,
)


@dataclass
class FakeAgentConfig:
    name: str | None = None
    import_path: str | None = None
    kwargs: dict = field(default_factory=dict)
    env: dict = field(default_factory=dict)


@dataclass
class FakeConfig:
    agents: list[FakeAgentConfig]


class ProxyRewriteTests(unittest.TestCase):
    def test_supported_agents_are_rewritten_to_proxies(self) -> None:
        config = FakeConfig(
            agents=[
                FakeAgentConfig(name="claude-code"),
                FakeAgentConfig(name="terminus-2"),
                FakeAgentConfig(name="oracle"),
            ]
        )

        rewritten = rewrite_job_config(
            config,
            helper_url="https://collector.example/events",
            stream_token="secret",
        )

        self.assertTrue(rewritten.helper_required)
        claude = rewritten.config.agents[0]
        terminus2 = rewritten.config.agents[1]
        oracle = rewritten.config.agents[2]

        self.assertIsNone(claude.name)
        self.assertEqual(claude.import_path, INSTALLED_PROXY_IMPORT)
        self.assertEqual(claude.kwargs["target_name"], "claude-code")
        self.assertEqual(claude.kwargs["stream_url"], "https://collector.example/events")

        self.assertIsNone(terminus2.name)
        self.assertEqual(terminus2.import_path, TERMINUS2_PROXY_IMPORT)
        self.assertEqual(terminus2.kwargs["target_name"], "terminus-2")

        self.assertEqual(oracle.name, "oracle")
        self.assertIsNone(oracle.import_path)


if __name__ == "__main__":
    unittest.main()
