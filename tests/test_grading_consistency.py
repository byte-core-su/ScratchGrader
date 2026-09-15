import unittest

from grading_policy import grading_policy_fingerprint, should_fallback_to_anthropic


class GradingConsistencyTests(unittest.TestCase):
    def test_fallback_only_for_503_or_two_500_errors(self):
        self.assertTrue(should_fallback_to_anthropic("HTTP 503 capacity"))
        self.assertFalse(should_fallback_to_anthropic("HTTP 500 internal", 1))
        self.assertTrue(should_fallback_to_anthropic("HTTP 500 internal", 2))
        self.assertFalse(should_fallback_to_anthropic("HTTP 429 quota", 9))

    def test_same_program_and_rules_keep_same_cache_identity_across_models(self):
        base = {"theme": "迷宮", "rules": "碰到終點得 100 分", "model_name": "gemini-2.5-flash"}
        with_claude_selected = dict(base, model_name="claude-haiku-4-5-20251001")
        self.assertEqual(
            grading_policy_fingerprint("程式", base),
            grading_policy_fingerprint("程式", with_claude_selected),
        )
        changed_rules = dict(base, rules="碰到終點得 90 分")
        self.assertNotEqual(
            grading_policy_fingerprint("程式", base),
            grading_policy_fingerprint("程式", changed_rules),
        )


if __name__ == "__main__":
    unittest.main()
