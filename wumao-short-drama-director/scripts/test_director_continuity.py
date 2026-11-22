"""导演台连续性接口回归；不调用生成器。"""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import continuity
import director_server as server
from test_continuity import fixture


class DirectorContinuityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root_patch = patch.object(server, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.directory = self.root / "04_feed/segments/S02"
        self.directory.mkdir(parents=True)
        # 参考图接线门是现行生产门：夹具必须提供真实存在的锚图与匹配槽位，
        # 否则所有用例都会被 MISSING_REFERENCE_SLOTS 阻断，掩盖连续性本身的断言。
        self.picture = self.root / "02_assets/characters/x.png"
        self.picture.parent.mkdir(parents=True)
        self.picture.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        (self.directory / "refs.json").write_text(json.dumps({
            "pictures": {"Picture 1": {"file": "02_assets/characters/x.png", "role": "角色锚图"}}
        }, ensure_ascii=False), encoding="utf-8")
        self.prompt = '[00:00.000] <Picture 1> (x.png) 固定。<d>[Chinese]「你好」</d>\n[00:02.000] 反应。'
        self.prompt_file = self.directory / "prompt.txt"
        self.prompt_file.write_text(self.prompt, encoding="utf-8")
        self.ledger = fixture()
        self.ledger["segment"] = "S02"
        self.save()

    def save(self):
        (self.directory / "continuity.json").write_text(json.dumps(self.ledger), encoding="utf-8")

    def post(self, ledger=None):
        handler = object.__new__(server.Handler)
        handler.path = "/api/continuity/S02"
        payload = json.dumps({"ledger": self.ledger if ledger is None else ledger, "compile": True}).encode()
        handler.headers = {"Content-Length": str(len(payload))}
        handler.rfile = io.BytesIO(payload)
        responses = []
        handler._json = lambda body, code=200: responses.append((code, body))
        handler.do_POST()
        return responses[0]

    def test_single_final_end_and_unbound_review(self):
        report = server.continuity_details("S02")["report"]
        self.assertEqual(report["status"], "review")
        self.assertFalse(report["errors"])
        self.assertTrue(report["evidence"]["dialogue_text_verified"])
        self.assertFalse(report["evidence"]["speaker_binding_verified"])

    def test_compile_unbound_then_pass(self):
        code, body = self.post()
        self.assertEqual(code, 200, body)
        self.assertEqual(body["report"]["status"], "pass")
        self.assertTrue(body["report"]["evidence"]["speaker_binding_verified"])
        self.assertEqual(server.continuity_details("S02")["report"]["status"], "pass")

    def test_explicit_invalid_or_missing_previous_blocks_read_and_compile(self):
        for previous in ("S01", "../S01", None, 1, ""):
            with self.subTest(previous=previous):
                self.ledger["previous_segment"] = previous
                self.save()
                self.assertEqual(server.continuity_details("S02")["report"]["status"], "blocked")
                self.assertEqual(self.post()[0], 400)
                self.assertEqual(self.prompt_file.read_text(encoding="utf-8"), self.prompt)

    def test_corrupt_or_invalid_previous_blocks(self):
        previous_dir = self.directory.parent / "S01"
        previous_dir.mkdir()
        self.ledger["previous_segment"] = "S01"
        self.save()
        for content in ("{", "[]", json.dumps({"segment": "S01", "scene": "elsewhere"})):
            (previous_dir / "continuity.json").write_text(content, encoding="utf-8")
            self.assertEqual(server.continuity_details("S02")["report"]["status"], "blocked")
            self.assertEqual(self.post()[0], 400)

    def test_valid_previous_compile_and_state_mismatch(self):
        previous = copy.deepcopy(self.ledger)
        previous["segment"] = "S01"
        previous_dir = self.directory.parent / "S01"
        previous_dir.mkdir()
        (previous_dir / "continuity.json").write_text(json.dumps(previous), encoding="utf-8")
        self.ledger["previous_segment"] = "S01"
        self.assertEqual(self.post()[0], 200)
        self.ledger["characters"][0]["opening"]["side"] = "center"
        self.assertEqual(self.post()[0], 400)

    def test_text_mismatch_and_other_warnings_never_compile(self):
        self.ledger["shots"][0]["dialogue"][0]["text"] = "不同"
        self.assertEqual(self.post()[0], 400)
        self.assertEqual(self.prompt_file.read_text(encoding="utf-8"), self.prompt)
        self.ledger = fixture()
        self.ledger["segment"] = "S02"
        original = continuity.validate_ledger
        def extra_warning(*args, **kwargs):
            result = original(*args, **kwargs)
            result["warnings"].append({"code": "OTHER_WARNING"})
            return result
        with patch.object(continuity, "validate_ledger", side_effect=extra_warning):
            self.assertEqual(self.post()[0], 400)

    def test_regen_requires_pass_and_binding_evidence(self):
        for report in ({"status": "review", "evidence": {"speaker_binding_verified": True}},
                       {"status": "pass", "evidence": {}},
                       {"status": "pass", "evidence": {"speaker_binding_verified": False}}):
            with patch.object(server, "continuity_details", return_value={"report": report}):
                with self.assertRaises(RuntimeError):
                    server.do_regen("S02")


if __name__ == "__main__":
    unittest.main()
