# -*- coding: utf-8 -*-
"""Pure, dependency-free rules for provider fallback and result identity."""
import hashlib
import json
import os


def should_fallback_to_anthropic(error_message, consecutive_500=0):
    """Only capacity / internal failures may spend the paid fallback budget."""
    text = str(error_message or "")
    return "503" in text or ("500" in text and consecutive_500 >= 2)


def grading_policy_fingerprint(clean_code, config):
    """Stable identity for one program under one set of grading rules.

    Provider/model are intentionally excluded: the first successful score remains
    canonical even if a later retry would otherwise use a different provider.
    """
    cfg = config or {}
    environment_version = os.getenv("GRADING_POLICY_VERSION", "").strip()
    policy = {
        # Deployment environment takes precedence so an administrator can reset
        # cache generations even when an older Firestore config already exists.
        "cache_version": environment_version or str(cfg.get("grading_policy_version", "1")),
        "clean_code": clean_code,
        "theme": cfg.get("theme", ""),
        "rules": cfg.get("rules", ""),
        "template_code": cfg.get("template_code", ""),
        "example_code": cfg.get("example_code", ""),
        "is_standard_answer": bool(cfg.get("is_standard_answer", True)),
        "use_custom_extension": bool(cfg.get("use_custom_extension", False)),
        "extension_rules": cfg.get("extension_rules", ""),
    }
    encoded = json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
