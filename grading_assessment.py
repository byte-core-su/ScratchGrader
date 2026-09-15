"""Deterministic course-style achievement labels for an AI score."""


def assessment_from_score(score, pass_score=75, excellence_score=90):
    """Convert a numeric score into a 0/2/3-star completion outcome."""
    try:
        score = float(score)
    except (TypeError, ValueError):
        score = 0
    try:
        pass_score = max(0, float(pass_score))
        excellence_score = max(pass_score, float(excellence_score))
    except (TypeError, ValueError):
        pass_score, excellence_score = 75, 90

    if score >= excellence_score:
        return {"stars": 3, "is_passed": True, "level": "excellent",
                "message": "表現優秀，已完成本次任務！"}
    if score >= pass_score:
        return {"stars": 2, "is_passed": True, "level": "passed",
                "message": "已達成任務要求！"}
    return {"stars": 0, "is_passed": False, "level": "needs_revision",
            "message": "尚未達成任務要求；請依建議修改後再送一次。"}


def add_assessment(result, config):
    """Attach a deterministic completion outcome without asking the AI again."""
    result = dict(result or {})
    result["assessment"] = assessment_from_score(
        result.get("score"),
        (config or {}).get("pass_score", 75),
        (config or {}).get("excellence_score", 90),
    )
    return result
