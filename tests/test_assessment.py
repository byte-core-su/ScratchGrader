import unittest

from grading_assessment import add_assessment, assessment_from_score


class AssessmentTests(unittest.TestCase):
    def test_course_style_thresholds(self):
        self.assertEqual(assessment_from_score(74)["stars"], 0)
        self.assertFalse(assessment_from_score(74)["is_passed"])
        self.assertEqual(assessment_from_score(75)["stars"], 2)
        self.assertTrue(assessment_from_score(75)["is_passed"])
        self.assertEqual(assessment_from_score(90)["stars"], 3)

    def test_custom_thresholds_are_applied(self):
        result = add_assessment({"score": 81}, {"pass_score": 80, "excellence_score": 95})
        self.assertEqual(result["assessment"]["stars"], 2)

    def test_invalid_excellence_threshold_cannot_be_lower_than_pass(self):
        self.assertEqual(assessment_from_score(80, pass_score=80, excellence_score=60)["stars"], 3)
