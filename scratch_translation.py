"""Scratch 官方繁體中文積木名稱與解析輸出工具。"""

from __future__ import annotations

import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path


_DATA_PATH = Path(__file__).with_name("scratch_official_zh_tw.json")
_SPECIAL_PLACEHOLDERS = {
    ("event_whenflagclicked", "%1"): "綠旗",
}


@lru_cache(maxsize=1)
def official_catalog() -> dict:
    """讀取內附、由 Scratch Foundation 官方來源產生的詞彙快照。"""
    try:
        data = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"無法讀取 Scratch 官方繁中詞彙表：{exc}") from exc
    if data.get("metadata", {}).get("locale") != "zh-tw":
        raise RuntimeError("Scratch 積木詞彙表不是繁體中文（zh-tw）版本")
    return data


def opcode_entry(opcode: str) -> dict | None:
    return official_catalog().get("opcodes", {}).get(opcode)


def render_official_block(opcode: str, parameters: list[tuple[str, str]] | None = None) -> str:
    """將 opcode 渲染為官方繁中積木文字；未知項目會明確標示。"""
    entry = opcode_entry(opcode)
    if not entry:
        return f"【未對照積木：{opcode}】"

    template = entry["template"]
    parameters = parameters or []
    named = {name: value for name, value in parameters}
    sequential = [value for _, value in parameters]

    def percent_replacer(match):
        token = match.group(0)
        special = _SPECIAL_PLACEHOLDERS.get((opcode, token))
        if special:
            return special
        index = int(token[1:]) - 1
        return sequential[index] if index < len(sequential) else ""

    template = re.sub(r"%[1-9][0-9]*", percent_replacer, template)
    position = 0

    def named_replacer(match):
        nonlocal position
        name = match.group(1)
        if name in named:
            return named[name]
        value = sequential[position] if position < len(sequential) else ""
        position += 1
        return value

    text = re.sub(r"\[([A-Z][A-Z0-9_]*)\]", named_replacer, template)
    return re.sub(r"\s+", " ", text).strip()


def project_opcode_coverage(raw_json: dict | None) -> dict:
    """回報專案實際使用的 opcode 是否已收錄於詞彙快照。"""
    counts = Counter()
    for target in (raw_json or {}).get("targets", []):
        for block in target.get("blocks", {}).values():
            if isinstance(block, dict) and block.get("opcode"):
                counts[block["opcode"]] += 1
    catalog = official_catalog().get("opcodes", {})
    unmapped = sorted(opcode for opcode in counts if opcode not in catalog)
    return {
        "total": sum(counts.values()),
        "mapped": sum(count for opcode, count in counts.items() if opcode in catalog),
        "unmapped_opcodes": unmapped,
    }
