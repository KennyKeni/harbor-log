from __future__ import annotations

import unittest

from harbor_stream.config import StreamConfigError, prepare_stream_settings


class StreamSettingsTests(unittest.TestCase):
    def test_docker_loopback_is_rewritten_for_helper(self) -> None:
        settings = prepare_stream_settings(
            stream_url="http://127.0.0.1:8080/events",
            stream_token="token",
            environment_type="docker",
            helper_required=True,
        )

        self.assertEqual(settings.sink_url, "http://127.0.0.1:8080/events")
        self.assertEqual(
            settings.helper_url,
            "http://host.docker.internal:8080/events",
        )
        self.assertEqual(settings.token, "token")

    def test_non_docker_loopback_is_rejected_when_helper_needed(self) -> None:
        with self.assertRaises(StreamConfigError):
            prepare_stream_settings(
                stream_url="http://localhost:8080/events",
                stream_token=None,
                environment_type="modal",
                helper_required=True,
            )

    def test_loopback_is_allowed_when_no_helper_is_needed(self) -> None:
        settings = prepare_stream_settings(
            stream_url="http://localhost:8080/events",
            stream_token=None,
            environment_type="modal",
            helper_required=False,
        )

        self.assertEqual(settings.sink_url, "http://localhost:8080/events")
        self.assertEqual(settings.helper_url, "http://localhost:8080/events")


if __name__ == "__main__":
    unittest.main()
