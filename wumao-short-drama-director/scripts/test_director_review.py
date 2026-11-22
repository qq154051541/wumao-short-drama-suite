"""导演台审阅与生产看板回归测试，不调用 GPU。"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import director_server as server


class DirectorReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.patch = patch.object(server, "ROOT", self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.seg = self.root / "04_feed/segments/S02"
        self.seg.mkdir(parents=True)
        (self.seg / "prompt.txt").write_text("[00:00.000] first shot.\n[00:02.000] second shot.\n", encoding="utf-8")
        (self.seg / "continuity.json").write_text("{}", encoding="utf-8")
        (self.seg / "refs.json").write_text(json.dumps({"pictures": {}}), encoding="utf-8")

    def request(self, method, path, payload=None):
        h = object.__new__(server.Handler)
        h.path = path
        raw = json.dumps(payload or {}).encode()
        h.headers = {"Content-Length": str(len(raw))}
        h.rfile = io.BytesIO(raw)
        out = []
        h._json = lambda body, code=200: out.append((code, body))
        getattr(h, "do_" + method)()
        return out[0]

    def test_comment_resolve_approve_and_persist(self):
        review = server.get_review("S02")
        self.assertEqual(review["state"], "pending")
        note = self.request("POST", "/api/review/S02", {"action": "comment", "shot_id": review["shots"][0]["id"], "text": "改动作"})[1]["notes"][0]
        self.assertEqual(note["status"], "open")
        code, body = self.request("POST", "/api/review/S02", {"action": "approve", "fingerprint": review["fingerprint"]})
        self.assertEqual(code, 409)
        code, body = self.request("POST", "/api/review/S02", {"action": "resolve", "id": note["id"]})
        self.assertEqual(code, 200)
        self.assertEqual(self.request("POST", "/api/review/S02", {"action": "approve", "fingerprint": review["fingerprint"]})[1]["state"], "approved")
        self.assertTrue((self.root / "导演台数据/审阅记录.json").is_file())
        output = subprocess.check_output([
            sys.executable, "-B", "-c",
            "import json, sys, director_server as s; from pathlib import Path; "
            "s.ROOT = Path(sys.argv[1]); print(json.dumps(s.get_review('S02')))", str(self.root),
        ], env={**os.environ, "PYTHONPATH": str(Path(server.__file__).parent)}, timeout=15)
        restarted = json.loads(output)
        self.assertEqual(restarted["state"], "approved")
        self.assertEqual(restarted["notes"][0]["status"], "resolved")

    def test_same_name_image_change_and_path_boundary(self):
        image = self.root / "anchor.png"
        image.write_bytes(b"version1")
        refs = self.seg / "refs.json"
        refs.write_text(json.dumps({"pictures": {"Picture 1": {"file": "anchor.png"}}}), encoding="utf-8")
        _, review = self.request("GET", "/api/review/S02")
        self.assertEqual(self.request("POST", "/api/review/S02", {"action": "approve", "fingerprint": review["fingerprint"]})[0], 200)
        image.write_bytes(b"version2")
        self.assertEqual(self.request("GET", "/api/review/S02")[1]["state"], "stale")
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "anchor.png"
            external.write_bytes(b"private1")
            for rel in (str(external), f"../{external.parent.name}/anchor.png"):
                refs.write_text(json.dumps({"pictures": {"Picture 1": {"file": rel}}}), encoding="utf-8")
                before = self.request("GET", "/api/review/S02")[1]["fingerprint"]
                external.write_bytes(external.read_bytes() + b"x")
                self.assertEqual(self.request("GET", "/api/review/S02")[1]["fingerprint"], before)
        self.assertEqual(self.request("GET", "/api/review/%2e%2e/S02")[0], 400)

    def test_request_changes_and_draft_save(self):
        prompt = self.seg / "prompt.txt"
        before = prompt.read_bytes()
        _, review = self.request("GET", "/api/review/S02")
        code, updated = self.request("POST", "/api/review/S02", {"action": "request_changes", "fingerprint": review["fingerprint"]})
        self.assertEqual((code, updated["state"]), (200, "changes_requested"))
        code, result = self.request("POST", "/api/continuity/S02", {"compile": False, "ledger": {"segment": "S02", "prompt_sha256": "old"}})
        self.assertEqual(code, 200, result)
        self.assertEqual(prompt.read_bytes(), before)
        self.assertEqual(json.loads((self.seg / "continuity.json").read_bytes()), {"segment": "S02"})
        self.assertEqual(self.request("GET", "/api/review/S02")[1]["state"], "stale")

    def test_conflict_and_orphan(self):
        review = server.get_review("S02")
        code, body = self.request("POST", "/api/review/S02", {"action": "approve", "fingerprint": "bad"})
        self.assertEqual(code, 409)
        self.assertEqual(self.request("POST", "/api/review/S02", {"action": "approve", "fingerprint": review["fingerprint"]})[1]["state"], "approved")
        (self.seg / "prompt.txt").write_text("[00:00.000] changed.\n", encoding="utf-8")
        self.assertEqual(server.get_review("S02")["state"], "stale")
        (self.seg / "prompt.txt").write_text("[00:00.000] first shot.\n[00:02.000] second shot.\n", encoding="utf-8")
        note = self.request("POST", "/api/review/S02", {"action": "comment", "shot_id": review["shots"][1]["id"], "text": "待办"})[1]["notes"][0]
        (self.seg / "prompt.txt").write_text("[00:00.000] first shot.\n", encoding="utf-8")
        current = server.get_review("S02")
        self.assertTrue(current["notes"][0]["orphaned"])
        self.assertEqual(current["state"], "stale")
        self.assertEqual(current["notes"][0]["id"], note["id"])
        server.save_json("_tmp/seg_map.json", {"E01": [2]})
        self.assertEqual(server.build_production()["summary"]["open_notes"], 1)
        self.assertEqual(self.request("POST", "/api/review/S02", {"action": "comment",
            "shot_id": current["shots"][0]["id"], "text": "旧页提交", "fingerprint": review["fingerprint"]})[0], 409)
        self.assertEqual(self.request("POST", "/api/review/S02", {
            "action": "approve", "fingerprint": current["fingerprint"],
        })[0], 409)

    def test_path_boundary_and_h3_shots_rejected_without_write(self):
        h = object.__new__(server.Handler)
        self.assertIsNone(h._safe("../outside"))
        prompt = self.seg / "prompt.txt"
        before = prompt.read_bytes()
        shots = server.parse_shots(before.decode())
        code, result = self.request("POST", "/api/segment/S02/save_shots", {"shots": shots})
        self.assertEqual(code, 200)
        self.assertTrue(result["unchanged"])
        self.assertEqual(prompt.read_bytes(), before)
        shots[0]["shot"] = "Changed shot"
        self.assertEqual(self.request("POST", "/api/segment/S02/save_shots", {"shots": shots})[0], 200)
        self.assertIn(b"Changed shot", prompt.read_bytes())
        (self.seg / "prompt.txt").write_text("overall_soundscape: test\n", encoding="utf-8")
        code, _ = self.request("POST", "/api/segment/S02/save_shots", {"shots": [{"time": "0", "shot": "x"}]})
        self.assertEqual(code, 400)
        self.assertEqual((self.seg / "prompt.txt").read_text(encoding="utf-8"), "overall_soundscape: test\n")

    def test_production_shape(self):
        server.save_json("_tmp/seg_map.json", {"E01": [2]})
        server.save_status({"S02": {"1": "ok"}})
        clip = self.root / "clips/raw/local-runner/s02-040mp.mp4"
        clip.parent.mkdir(parents=True)
        clip.touch()
        with patch.object(server, "ensure_shot_frames", side_effect=AssertionError("不得抽帧")):
            code, result = self.request("GET", "/api/production")
        self.assertEqual(code, 200)
        self.assertEqual(result["segments"], [{"segment": "S02", "episode": "E01", "review_state": "pending",
                                               "open_notes": 0, "has_clip": True, "shot_count": 2}])
        self.assertEqual(result["summary"]["pending"], 1)


if __name__ == "__main__":
    unittest.main()
