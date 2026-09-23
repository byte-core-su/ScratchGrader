import unittest

from grading_calibration import (CALIBRATION_CASES, calibration_policy_fingerprint,
                                 score_matches_expected_range)


class CalibrationTests(unittest.TestCase):
    def test_all_four_required_sample_types_are_defined(self):
        self.assertEqual(CALIBRATION_CASES,
                         ("complete", "missing_rule", "incomplete", "logic_trap"))

    def test_expected_score_range_is_inclusive_and_rejects_invalid_range(self):
        self.assertTrue(score_matches_expected_range(75, 75, 89))
        self.assertTrue(score_matches_expected_range(89, 75, 89))
        self.assertFalse(score_matches_expected_range(74, 75, 89))
        self.assertFalse(score_matches_expected_range(80, 90, 70))

    def test_calibration_expires_after_model_or_rule_change(self):
        config = {"model_name": "gemini-2.5-flash", "rules": "使用清單", "theme": "點名"}
        changed_model = dict(config, model_name="gemini-2.5-flash-lite")
        changed_rules = dict(config, rules="使用清單並顯示人數")
        original = calibration_policy_fingerprint(config, False, "", "1")
        self.assertNotEqual(original, calibration_policy_fingerprint(changed_model, False, "", "1"))
        self.assertNotEqual(original, calibration_policy_fingerprint(changed_rules, False, "", "1"))


if __name__ == "__main__":
    unittest.main()
