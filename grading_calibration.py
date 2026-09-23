# -*- coding: utf-8 -*-
"""Dependency-free calibration rules for a Scratch grading level."""
import hashlib
import json

from grading_policy import grading_policy_fingerprint


CALIBRATION_CASES = ("complete", "missing_rule", "incomplete", "logic_trap")


def calibration_policy_fingerprint(config, fallback_enabled=False, fallback_model="", prompt_version="1"):
    """A calibration expires if rules, primary model, fallback, or prompt changes."""
    cfg = config or {}
    identity = {
        "grading_policy": grading_policy_fingerprint("", cfg),
        "primary_model": cfg.get("model_name", ""),
        "fallback_enabled": bool(fallback_enabled),
        "fallback_model": fallback_model or "",
        "prompt_version": str(prompt_version or "1"),
    }
    raw = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def score_matches_expected_range(score, expected_min, expected_max):
    """Return whether an observed score meets the teacher-defined calibration range."""
    try:
        score = int(score)
        expected_min = int(expected_min)
        expected_max = int(expected_max)
    except (TypeError, ValueError):
        return False
    return expected_min <= expected_max and expected_min <= score <= expected_max
