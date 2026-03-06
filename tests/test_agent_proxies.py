from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


HARBOR_AVAILABLE = importlib.util.find_spec("harbor") is not None


@unittest.skipUnless(HARBOR_AVAILABLE, "Harbor is required for proxy tests")
class AgentProxyTests(unittest.TestCase):
    def test_installed_proxy_prefers_target_import_path_over_name(self) -> None:
        from harbor_stream.agents.installed_proxy import StreamingInstalledAgentProxy

        captured: dict = {}

        class FakeDelegate:
            @staticmethod
            def name() -> str:
                return "claude-code"

            def version(self) -> str:
                return "1.0.0"

            def to_agent_info(self):
                return None

            async def setup(self, environment) -> None:
                return None

            async def run(self, instruction, environment, context) -> None:
                return None

        class FakeFactory:
            @staticmethod
            def create_agent_from_config(config, **kwargs):
                captured["name"] = config.name
                captured["import_path"] = config.import_path
                return FakeDelegate()

        class FakeConfig:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        with (
            patch("harbor_stream.agents.installed_proxy.get_agent_factory_class", return_value=FakeFactory),
            patch("harbor_stream.agents.installed_proxy.get_agent_config_class", return_value=FakeConfig),
        ):
            StreamingInstalledAgentProxy(
                logs_dir=Path("/tmp/job/trial/agent"),
                model_name="fake/model",
                target_name="claude-code",
                target_import_path="tests.integration_agents:FakeClaudeCodeAgent",
                target_kwargs={},
                target_env={},
                stream_url="http://127.0.0.1:9000/events",
            )

        self.assertIsNone(captured["name"])
        self.assertEqual(
            captured["import_path"],
            "tests.integration_agents:FakeClaudeCodeAgent",
        )

    def test_terminus_proxy_prefers_target_import_path_over_name(self) -> None:
        from harbor_stream.agents.terminus2_proxy import StreamingTerminus2Proxy

        captured: dict = {}

        class FakeDelegate:
            @staticmethod
            def name() -> str:
                return "terminus-2"

            def version(self) -> str:
                return "2.0.0"

            def to_agent_info(self):
                return None

            async def setup(self, environment) -> None:
                return None

            async def run(self, instruction, environment, context) -> None:
                return None

        class FakeFactory:
            @staticmethod
            def create_agent_from_config(config, **kwargs):
                captured["name"] = config.name
                captured["import_path"] = config.import_path
                return FakeDelegate()

        class FakeConfig:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        with (
            patch("harbor_stream.agents.terminus2_proxy.get_agent_factory_class", return_value=FakeFactory),
            patch("harbor_stream.agents.terminus2_proxy.get_agent_config_class", return_value=FakeConfig),
        ):
            StreamingTerminus2Proxy(
                logs_dir=Path("/tmp/job/trial/agent"),
                model_name="fake/model",
                target_name="terminus-2",
                target_import_path="tests.integration_agents:FakeTerminus2",
                target_kwargs={},
                target_env={},
                stream_url="http://127.0.0.1:9000/events",
            )

        self.assertIsNone(captured["name"])
        self.assertEqual(
            captured["import_path"],
            "tests.integration_agents:FakeTerminus2",
        )
