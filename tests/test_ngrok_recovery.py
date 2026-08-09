import unittest
from unittest.mock import patch

import ngrok_recovery


class NgrokRecoveryTests(unittest.TestCase):
    def test_domain_comparison_requires_exact_host(self):
        self.assertTrue(ngrok_recovery._endpoint_matches_domain(
            {"url": "https://grader.ngrok-free.app"}, "grader.ngrok-free.app"))
        self.assertFalse(ngrok_recovery._endpoint_matches_domain(
            {"url": "https://other.ngrok-free.app"}, "grader.ngrok-free.app"))

    def test_only_matching_domain_session_is_stopped(self):
        calls = []

        def fake_request(api_key, method, url, body=None):
            calls.append((method, url, body))
            if method == "GET":
                return 200, {"endpoints": [
                    {"url": "https://grader.ngrok-free.app", "tunnel_session": {"id": "target"}},
                    {"url": "https://other.ngrok-free.app", "tunnel_session": {"id": "other"}},
                ], "next_page_uri": None}
            return 204, {}

        with patch.object(ngrok_recovery, "_api_request", side_effect=fake_request):
            result = ngrok_recovery.stop_stale_domain_sessions(
                "grader.ngrok-free.app", "api-key", wait_seconds=0)

        self.assertTrue(result["ok"])
        self.assertEqual(result["stopped_session_ids"], ["target"])
        stop_calls = [call for call in calls if call[0] == "POST"]
        self.assertEqual(len(stop_calls), 1)
        self.assertIn("/tunnel_sessions/target/stop", stop_calls[0][1])


if __name__ == "__main__":
    unittest.main()
