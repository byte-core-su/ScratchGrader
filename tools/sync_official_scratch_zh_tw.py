"""從 Scratch Foundation 官方來源產生繁體中文 opcode 對照表。

用法：
  python tools/sync_official_scratch_zh_tw.py \
    --l10n-root /path/to/scratch-l10n \
    --vm-root /path/to/scratch-vm

來源：LLK/scratch-l10n 的 editor/blocks/zh-tw.json、editor/extensions/zh-tw.json，
以及 LLK/scratch-vm 的官方 opcode 定義。此工具只在更新詞彙快照時使用；
執行中的批改系統只讀取產生出的 scratch_official_zh_tw.json。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


CORE_PREFIXES = {
    "control": "CONTROL",
    "data": "DATA",
    "event": "EVENT",
    "looks": "LOOKS",
    "motion": "MOTION",
    "operator": "OPERATORS",
    "procedures": "PROCEDURES",
    "sensing": "SENSING",
    "sound": "SOUND",
}

# Scratch VM opcode 與 scratch-l10n 訊息 ID 的歷史命名差異。
CORE_KEY_EXCEPTIONS = {
    "control_repeat_until": "CONTROL_REPEATUNTIL",
    "control_for_each": "CONTROL_FOREACH",
    "control_wait_until": "CONTROL_WAITUNTIL",
    "control_if_else": "CONTROL_IF",
    "control_create_clone_of": "CONTROL_CREATECLONEOF",
    "control_delete_this_clone": "CONTROL_DELETETHISCLONE",
    "control_get_counter": "CONTROL_COUNTER",
    "control_incr_counter": "CONTROL_INCRCOUNTER",
    "control_clear_counter": "CONTROL_CLEARCOUNTER",
    "control_all_at_once": "CONTROL_ALLATONCE",
    "control_start_as_clone": "CONTROL_STARTASCLONE",
    "operator_letter_of": "OPERATORS_LETTEROF",
    "sound_seteffectto": "SOUND_SETEFFECTO",
}

# 下列是 project.json 使用、但不會出現在 VM getPrimitives 的內部輸入/選單積木。
# 它們不是積木面板中可獨立選取的指令，仍保留中文說明以避免 AI 看到英文技術名稱。
INTERNAL_TEMPLATES = {
    "argument_reporter_boolean": "自訂積木布林參數 %1",
    "argument_reporter_string_number": "自訂積木文字或數字參數 %1",
    "data_listcontents": "清單 %1 的內容",
    "data_variable": "變數 %1",
    "sound_beats_menu": "%1 拍",
    "sound_effects_menu": "聲音效果 %1",
    "sound_sounds_menu": "音效 %1",
    "text": "%1",
    "math_angle": "%1",
    "math_integer": "%1",
    "math_number": "%1",
    "math_positive_number": "%1",
    "math_whole_number": "%1",
    "colour_picker": "%1",
    "procedures_call": "執行自訂積木 %1",
    "procedures_prototype": "自訂積木原型",
}

# 少數官方 message id 與 opcode 名稱不同，保留明確例外而非自行翻譯。
EXTENSION_MESSAGE_EXCEPTIONS = {
    "pen_changePenHueBy": "pen.changeHue",
    "speech2text_getSpeech": "speech.speechReporter",
    "translate_getViewerLanguage": "translate.viewerLanguage",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def git_revision(path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-c", f"safe.directory={path}", "-C", str(path), "rev-parse", "HEAD"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def core_message_key(opcode: str) -> str | None:
    if opcode in CORE_KEY_EXCEPTIONS:
        return CORE_KEY_EXCEPTIONS[opcode]
    prefix, separator, suffix = opcode.partition("_")
    if not separator or prefix not in CORE_PREFIXES:
        return None
    return f"{CORE_PREFIXES[prefix]}_{suffix.upper()}"


def collect_core(vm_root: Path, block_messages: dict) -> tuple[dict, list]:
    mapped, unresolved = {}, []
    for source in sorted((vm_root / "src" / "blocks").glob("scratch3_*.js")):
        text = source.read_text(encoding="utf-8")
        # getPrimitives 的可執行積木與 getHats 的事件積木都需收錄。
        candidates = re.findall(r"^\s{12}([a-z][a-z0-9_]*):\s*(?:this\.|\{)", text, re.M)
        for opcode in sorted(set(candidates)):
            if opcode.partition("_")[0] not in CORE_PREFIXES:
                continue
            key = core_message_key(opcode)
            if key and key in block_messages:
                mapped[opcode] = {
                    "template": block_messages[key],
                    "message_id": key,
                    "source": "scratch-l10n/editor/blocks/zh-tw.json",
                }
            elif opcode not in INTERNAL_TEMPLATES:
                unresolved.append(opcode)
    return mapped, sorted(set(unresolved))


def extension_id(source: str) -> str | None:
    """取得 getInfo() 回傳的 extension id。"""
    match = re.search(r"static\s+get\s+EXTENSION_ID\s*\(\)\s*\{\s*return\s+'([^']+)'", source)
    if match:
        return match.group(1)
    match = re.search(r"getInfo\s*\(\)\s*\{.*?return\s*\{\s*\bid:\s*'([^']+)'", source, re.S)
    return match.group(1) if match else None


def collect_extensions(vm_root: Path, extension_messages: dict) -> tuple[dict, list]:
    mapped, unresolved = {}, []
    for source_path in sorted((vm_root / "src" / "extensions").glob("scratch3_*/index.js")):
        source = source_path.read_text(encoding="utf-8")
        ext_id = extension_id(source)
        if not ext_id:
            unresolved.append(f"{source_path.parent.name}: missing extension id")
            continue
        for match in re.finditer(r"opcode:\s*'([^']+)'", source):
            # 每一個 block 定義都以同一層縮排的大括號包住；只在該 block
            # 物件內尋找訊息 ID，避免把下一個積木的翻譯錯配過來。
            start = source.rfind("\n                {", 0, match.start())
            end = source.find("\n                },", match.end())
            local = source[start:end] if start >= 0 and end >= 0 else ""
            id_match = re.search(r"\bid:\s*'([^']+)'", local)
            opcode = f"{ext_id}_{match.group(1)}"
            message_id = EXTENSION_MESSAGE_EXCEPTIONS.get(opcode)
            if not message_id and id_match:
                message_id = id_match.group(1)
            if message_id and message_id in extension_messages:
                mapped[opcode] = {
                    "template": extension_messages[message_id],
                    "message_id": message_id,
                    "source": "scratch-l10n/editor/extensions/zh-tw.json",
                }
            else:
                unresolved.append(opcode)
    return mapped, sorted(set(unresolved))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--l10n-root", type=Path, required=True)
    parser.add_argument("--vm-root", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path,
        default=Path(__file__).resolve().parents[1] / "scratch_official_zh_tw.json",
    )
    args = parser.parse_args()

    block_messages = read_json(args.l10n_root / "editor" / "blocks" / "zh-tw.json")
    extension_messages = read_json(args.l10n_root / "editor" / "extensions" / "zh-tw.json")
    core, core_unresolved = collect_core(args.vm_root, block_messages)
    extensions, extension_unresolved = collect_extensions(args.vm_root, extension_messages)

    opcodes = {**core, **extensions}
    # Scratch 曾使用 speech2text 作為儲存檔 prefix；與目前 VM 的 speech 相容。
    for opcode, entry in list(opcodes.items()):
        if opcode.startswith("speech_"):
            opcodes["speech2text_" + opcode.removeprefix("speech_")] = dict(entry)
    for opcode, template in INTERNAL_TEMPLATES.items():
        opcodes[opcode] = {
            "template": template,
            "message_id": None,
            "source": "Scratch project.json internal input block",
        }

    payload = {
        "metadata": {
            "locale": "zh-tw",
            "sources": {
                "scratch_l10n_commit": git_revision(args.l10n_root),
                "scratch_vm_commit": git_revision(args.vm_root),
                "blocks": "scratch-l10n/editor/blocks/zh-tw.json",
                "extensions": "scratch-l10n/editor/extensions/zh-tw.json",
            },
            "generated_by": "tools/sync_official_scratch_zh_tw.py",
        },
        "opcodes": dict(sorted(opcodes.items())),
        "coverage": {
            "official_vm_opcodes": len(core) + len(extensions),
            "unresolved_official_vm_opcodes": sorted(core_unresolved + extension_unresolved),
            "internal_project_json_opcodes": sorted(INTERNAL_TEMPLATES),
        },
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if payload["coverage"]["unresolved_official_vm_opcodes"]:
        raise SystemExit("官方 opcode 尚未完整對照：" + ", ".join(payload["coverage"]["unresolved_official_vm_opcodes"]))


if __name__ == "__main__":
    main()
