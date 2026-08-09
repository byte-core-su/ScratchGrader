import unittest
import sys
import types

from scratch_translation import official_catalog, project_opcode_coverage, render_official_block


def import_core_without_ai_client():
    """解析器測試不需要 Google SDK；開發機未安裝時以空模組載入。"""
    if "google.genai" not in sys.modules:
        google = types.ModuleType("google")
        genai = types.ModuleType("google.genai")
        genai.types = types.ModuleType("google.genai.types")
        google.genai = genai
        sys.modules["google"] = google
        sys.modules["google.genai"] = genai
        sys.modules["google.genai.types"] = genai.types
    import scratch_grader_core
    return scratch_grader_core


class OfficialTraditionalChineseMappingTests(unittest.TestCase):
    def test_official_vm_catalog_has_full_coverage(self):
        catalog = official_catalog()
        coverage = catalog["coverage"]
        self.assertGreaterEqual(coverage["official_vm_opcodes"], 200)
        self.assertEqual(coverage["unresolved_official_vm_opcodes"], [])
        self.assertEqual(len(catalog["metadata"]["sources"]["scratch_l10n_commit"]), 40)
        self.assertEqual(len(catalog["metadata"]["sources"]["scratch_vm_commit"]), 40)

    def test_every_official_catalog_opcode_has_official_zh_tw_source(self):
        catalog = official_catalog()
        official_entries = [
            entry for entry in catalog["opcodes"].values()
            if entry["source"].startswith("scratch-l10n/")
        ]
        self.assertEqual(len(official_entries), catalog["coverage"]["official_vm_opcodes"])
        self.assertTrue(all(entry["template"] for entry in official_entries))

    def test_representative_blocks_use_official_terms(self):
        self.assertEqual(render_official_block("motion_movesteps", [("STEPS", "10")]), "移動 10 點")
        self.assertEqual(render_official_block("event_whenflagclicked"), "當 綠旗 被點擊")
        self.assertEqual(render_official_block("music_playNoteForBeats", [("NOTE", "60"), ("BEATS", "0.5")]), "演奏音階 60 0.5 拍")
        self.assertEqual(render_official_block("text2speech_speakAndWait", [("WORDS", "你好")]), "唸出 你好")

    def test_project_coverage_reports_unmapped_opcode(self):
        project = {
            "targets": [{"blocks": {
                "a": {"opcode": "motion_movesteps"},
                "b": {"opcode": "thirdparty_doSomething"},
            }}]
        }
        coverage = project_opcode_coverage(project)
        self.assertEqual(coverage["total"], 2)
        self.assertEqual(coverage["mapped"], 1)
        self.assertEqual(coverage["unmapped_opcodes"], ["thirdparty_doSomething"])

    def test_parser_outputs_official_terms_not_raw_core_opcode(self):
        core = import_core_without_ai_client()
        blocks = {
            "start": {
                "opcode": "event_whenflagclicked", "next": "move",
                "fields": {}, "inputs": {},
            },
            "move": {
                "opcode": "motion_movesteps", "next": None, "fields": {},
                "inputs": {"STEPS": [1, [4, "10"]]},
            },
        }
        pseudo = core.parse_chain_recursive("start", 0, blocks)
        self.assertIn("當 綠旗 被點擊", pseudo)
        self.assertIn("移動 '10' 點", pseudo)
        self.assertNotIn("motion_movesteps", pseudo)


if __name__ == "__main__":
    unittest.main()
