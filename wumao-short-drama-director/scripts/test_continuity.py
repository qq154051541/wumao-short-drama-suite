"""运行：python -B -m unittest discover -s scripts -p test_continuity.py -v。"""
import copy
import hashlib
import json
import re
from pathlib import Path
import tempfile
import unittest

from continuity import (SCHEMA, compile_prompt, load_ledger, save_ledger,
                        validate_ledger)

PROMPT = '00:00-00:02 [镜头1] 固定。<d speaker="甲">你好</d>\n00:02-00:04 [镜头2] 反应。'


def fixture():
    def opening(side):
        return {"presence": True, "anchor_object": "table", "side": side,
                "posture": "standing", "facing": "N"}
    return {"schema": SCHEMA, "segment": "SEG-01", "scene": "room",
            "objects": [{"id": "table"}],
            "characters": [
                {"id": "a", "subject": "Subject A", "name": "甲", "role": "protagonist",
                 "rank": "primary", "opening": opening("left")},
                {"id": "b", "subject": "Subject B", "name": "乙", "role": "supporting",
                 "rank": "secondary", "opening": opening("right")}],
            "shots": [
                {"id": "S1", "start": 0, "end": 2, "lead_subject": "Subject A", "states": {},
                 "dialogue": [{"speaker": "a", "mode": "on_screen", "listener": "b",
                               "reaction_subjects": ["Subject B"], "text": "你好"}]},
                {"id": "S2", "start": 2, "end": 4, "lead_subject": "b", "states": {},
                 "dialogue": []}]}


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.ledger = fixture()

    def codes(self, ledger=None, **kwargs):
        verdict = validate_ledger(self.ledger if ledger is None else ledger, **kwargs)
        self.assertTrue(verdict["evidence"]["text_only"])
        self.assertFalse(verdict["evidence"]["film_verified"])
        for error in verdict["errors"] + verdict["warnings"]:
            self.assertEqual(set(error), {"code", "shot", "character", "field", "message"})
        return {e["code"] for e in verdict["errors"] + verdict["warnings"]}

    def test_valid_and_no_mutation(self):
        original = copy.deepcopy(self.ledger)
        self.assertEqual(validate_ledger(self.ledger)["status"], "pass")
        self.assertEqual(self.ledger, original)

    def test_missing_ledger(self):
        with tempfile.TemporaryDirectory() as root:
            missing = load_ledger(root, "SEG-01", shots=[{}])
            self.assertEqual(missing, {"schema": SCHEMA, "segment": "SEG-01",
                                      "characters": [], "objects": [], "shots": [], "status": "missing"})
            self.assertEqual(validate_ledger(missing)["status"], "review")

    def test_bad_speaker(self):
        line = self.ledger["shots"][0]["dialogue"][0]
        for value in (None, "stranger", ["a", "b"]):
            line["speaker"] = value
            self.assertIn("INVALID_SPEAKER", self.codes())

    def test_bad_listener_and_reaction(self):
        line = self.ledger["shots"][0]["dialogue"][0]
        for field, value in (("listener", "a"), ("listener", "nobody"),
                             ("reaction_subjects", ["a"]), ("reaction_subjects", ["nobody"]),
                             ("reaction_subjects", "b")):
            with self.subTest(field=field, value=value):
                ledger = fixture()
                ledger["shots"][0]["dialogue"][0][field] = value
                self.assertIn("INVALID_LISTENER", self.codes(ledger))

    def test_identity_rank_drift(self):
        for field, value in (("role", "supporting"), ("rank", "secondary"),
                             ("subject", "Subject B")):
            ledger = fixture()
            ledger["shots"][1]["states"] = {"a": {field: value}}
            self.assertIn("IDENTITY_DRIFT", self.codes(ledger))
        self.ledger["shots"][1]["rank"] = "primary"
        self.assertIn("IDENTITY_DRIFT", self.codes())

    def test_duplicate_identifiers(self):
        for field in ("id", "subject", "name"):
            ledger = fixture()
            ledger["characters"][1][field] = ledger["characters"][0][field]
            self.assertIn("DUPLICATE_" + field.upper(), self.codes(ledger))

    def test_pair_and_group_subject_rejected(self):
        for value in ("Subject A and Subject B", "Subject pair", "Subject group", ["Subject A"]):
            self.ledger["characters"][0]["subject"] = value
            self.assertIn("INVALID_SUBJECT", self.codes())

    def test_posture_drift(self):
        self.ledger["shots"][1]["states"] = {"a": {"posture": "seated"}}
        self.assertIn("MISSING_TRANSITION", self.codes())

    def test_legal_transition_and_independent_inheritance(self):
        self.ledger["shots"][0]["states"] = {"a": {"posture": "seated"}}
        self.ledger["shots"][0]["transitions"] = [{"character": "a",
            "from": {"posture": "standing"}, "to": {"posture": "seated"}, "action": "sits down"}]
        self.assertEqual(validate_ledger(self.ledger)["status"], "pass")
        compiled = compile_prompt(PROMPT, self.ledger)
        self.assertEqual(compiled.count("posture=seated"), 2)
        self.assertEqual(compiled.count("posture=standing"), 2)

    def test_transition_wrong_from_to_and_action(self):
        for patch in ({"from": {"posture": "lying"}}, {"to": {"posture": "lying"}},
                      {"action": ""}, {"from": {"side": "left"}}):
            ledger = fixture()
            ledger["shots"][1]["states"] = {"a": {"posture": "seated"}}
            transition = {"character": "a", "from": {"posture": "standing"},
                          "to": {"posture": "seated"}, "action": "sits"}
            transition.update(patch)
            ledger["shots"][1]["transitions"] = [transition]
            self.assertEqual(validate_ledger(ledger)["status"], "blocked")

    def test_presence_and_position_transition(self):
        for field, value in (("presence", False), ("side", "center"), ("anchor_object", "door"),
                             ("facing", "E"), ("x", 2), ("y", 3)):
            ledger = fixture()
            ledger["objects"].append({"id": "door"})
            ledger["characters"][0]["opening"].update(x=0, y=0)
            ledger["shots"][1]["states"] = {"a": {field: value}}
            self.assertIn("MISSING_TRANSITION", self.codes(ledger))
            ledger["shots"][1]["transitions"] = [{"character": "a", "from": {
                field: ledger["characters"][0]["opening"][field]}, "to": {field: value}, "action": "moves"}]
            self.assertEqual(validate_ledger(ledger)["status"], "pass")

    def test_off_screen_and_voiceover(self):
        self.ledger["characters"][0]["opening"]["presence"] = False
        self.assertIn("SPEAKER_ABSENT", self.codes())
        for mode in ("off_screen", "voiceover"):
            self.ledger["shots"][0]["dialogue"][0]["mode"] = mode
            self.assertEqual(validate_ledger(self.ledger)["status"], "pass")

    def test_missing_unknown_fields_cannot_pass(self):
        for field in ("presence", "anchor_object", "side", "posture", "facing"):
            for value in (None, "unknown"):
                ledger = fixture()
                ledger["characters"][0]["opening"][field] = value
                self.assertIn("INVALID_STATE", self.codes(ledger))
        for field in ("dialogue", "states", "lead_subject", "start", "end"):
            ledger = fixture()
            del ledger["shots"][0][field]
            self.assertEqual(validate_ledger(ledger)["status"], "blocked")
        self.ledger["characters"][0]["opening"]["presence"] = 1
        self.assertIn("INVALID_STATE", self.codes())

    def test_unique_lead(self):
        for value in (["a", "b"], "a,b", None):
            self.ledger["shots"][0]["lead_subject"] = value
            self.assertIn("INVALID_LEAD", self.codes())

    def test_overlap(self):
        self.ledger["characters"][1]["opening"]["side"] = "left"
        self.assertIn("OVERLAPPING_POSITION", self.codes())
        self.ledger["characters"][1]["opening"].update(x=1, y=0)
        self.ledger["characters"][0]["opening"].update(x=0, y=0)
        self.assertEqual(validate_ledger(self.ledger)["status"], "pass")

    def test_cross_segment_effective_closing(self):
        previous = fixture()
        previous["shots"][1]["states"] = {"a": {"posture": "seated"}}
        previous["shots"][1]["transitions"] = [{"character": "a", "from": {"posture": "standing"},
            "to": {"posture": "seated"}, "action": "sits"}]
        self.assertIn("CROSS_SEGMENT_DRIFT", self.codes(previous=previous))
        self.ledger["characters"][0]["opening"]["posture"] = "seated"
        self.assertEqual(validate_ledger(self.ledger, previous=previous)["status"], "pass")
        self.ledger["characters"][0]["rank"] = "secondary"
        self.assertIn("IDENTITY_DRIFT", self.codes(previous=previous))

    def test_invalid_previous_and_closing(self):
        previous = fixture()
        previous["characters"][0]["closing"] = {"posture": "lying"}
        self.assertIn("INVALID_PREVIOUS", self.codes(previous=previous))
        self.assertIn("CLOSING_MISMATCH", self.codes(previous))
        previous["scene"] = "another room"
        self.assertEqual(validate_ledger(self.ledger, previous=previous)["status"], "pass")

    def test_prompt_time_and_count(self):
        self.assertIn("SHOT_COUNT_MISMATCH", self.codes(prompt_text="00:00-00:02 一镜"))
        self.assertIn("SHOT_TIME_MISMATCH", self.codes(prompt_text=PROMPT.replace("00:04", "00:05")))
        for prompt in ("没有时间码", PROMPT.replace("00:04", "00:05")):
            with self.assertRaises(ValueError):
                compile_prompt(prompt, self.ledger)

    def test_compile_idempotent_and_preserves_dialogue(self):
        original = copy.deepcopy(self.ledger)
        compiled = compile_prompt(PROMPT, self.ledger)
        self.assertEqual(compiled, compile_prompt(compiled, self.ledger))
        self.assertEqual(self.ledger, original)
        self.assertEqual(compiled.count("[Continuity]"), 3)
        self.assertIn('Visual focus: <Subject A>.', compiled)
        self.assertIn('Dialogue speaker: <Subject A>.', compiled)
        self.assertIn('<d speaker="甲">你好</d>', compiled)
        self.assertIn("do not render these labels as visible text", compiled)
        self.ledger["shots"][0]["lead_subject"] = "b"
        changed = compile_prompt(compiled, self.ledger)
        self.assertIn("Visual focus: <Subject B>.", changed)
        self.assertEqual(changed.count("[Continuity]"), 3)

    def test_hash_stale(self):
        self.ledger["prompt_sha256"] = hashlib.sha256(PROMPT.encode("utf-8")).hexdigest()
        self.assertEqual(validate_ledger(self.ledger, PROMPT)["status"], "pass")
        self.assertIn("STALE_PROMPT", self.codes(prompt_text=PROMPT + "修改"))
        del self.ledger["prompt_sha256"]
        self.assertEqual(validate_ledger(self.ledger, PROMPT)["status"], "review")

    def test_save_load_hash_and_expected_shots(self):
        with tempfile.TemporaryDirectory() as root:
            parent = Path(root) / "04_feed" / "segments" / "SEG-01"
            parent.mkdir(parents=True)
            prompt = compile_prompt(PROMPT, self.ledger)
            path = save_ledger(root, "SEG-01", self.ledger, prompt)
            self.assertEqual(path.name, "continuity.json")
            loaded = load_ledger(root, "SEG-01", shots=self.ledger["shots"])
            self.assertEqual(validate_ledger(loaded, prompt)["status"], "pass")
            self.assertNotIn("prompt_sha256", self.ledger)
            self.assertIn("STALE_PROMPT", self.codes(loaded, prompt_text=prompt + "change"))
            loaded = load_ledger(root, "SEG-01", shots=[])
            self.assertIn("SHOT_COUNT_MISMATCH", self.codes(loaded))
            shots = copy.deepcopy(self.ledger["shots"])
            shots[0]["end"] = 1
            self.assertIn("SHOT_TIME_MISMATCH", self.codes(load_ledger(root, "SEG-01", shots)))

    def test_save_requires_parent_and_rejects_invalid(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(FileNotFoundError):
                save_ledger(root, "SEG-01", self.ledger, PROMPT)
            parent = Path(root) / "04_feed" / "segments" / "SEG-01"
            parent.mkdir(parents=True)
            with self.assertRaises(ValueError):
                save_ledger(root, "SEG-01", self.ledger, "没有镜头")
            self.assertFalse((parent / "continuity.json").exists())
        for seg in ("../bad", "..", "x/y", "C:\\bad"):
            with self.assertRaises(ValueError):
                load_ledger(".", seg)

    def test_load_corrupt_and_segment_mismatch(self):
        with tempfile.TemporaryDirectory() as root:
            parent = Path(root) / "04_feed" / "segments" / "SEG-01"
            parent.mkdir(parents=True)
            path = parent / "continuity.json"
            for text in ("{broken", "[]", json.dumps({"segment": "other"})):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_ledger(root, "SEG-01")

    def test_basic_malformed_input(self):
        for value in (None, [], {}, {"schema": SCHEMA, "characters": [None], "objects": [None], "shots": [None]}):
            self.assertEqual(validate_ledger(value)["status"], "blocked")

    def test_malformed_shot_id_and_nested_values(self):
        for field, value in (("id", []), ("id", {}), ("states", []),
                             ("transitions", [None]), ("dialogue", [None]),
                             ("start", True), ("end", float("nan"))):
            ledger = fixture()
            ledger["shots"][0][field] = value
            self.assertEqual(validate_ledger(ledger)["status"], "blocked")

    def test_save_checks_expected_shots_before_stripping_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            parent = Path(root) / "04_feed" / "segments" / "SEG-01"
            parent.mkdir(parents=True)
            self.ledger["_expected_shots"] = []
            with self.assertRaises(ValueError):
                save_ledger(root, "SEG-01", self.ledger, PROMPT)
            self.assertFalse((parent / "continuity.json").exists())

    def h3_fixture(self):
        ledger = fixture()
        ledger["shots"] = []
        lines = []
        for i in range(4):
            entries = [{"speaker": "a", "mode": "on_screen", "text": f"第{i + 1}句。"},
                       {"speaker": "b", "mode": "on_screen", "text": f"回答{i + 1}。"}]
            ledger["shots"].append({"id": f"S{i + 1}", "start": i * 3, "end": (i + 1) * 3,
                                    "lead_subject": "a", "states": {}, "dialogue": entries})
            dialogue = (f'<d>[Chinese]「{entries[0]["text"]}」「{entries[1]["text"]}」</d>' if i % 2 == 0 else
                        f'<d>[Chinese]「{entries[0]["text"]}」</d>动作。<d>[Chinese]「{entries[1]["text"]}」</d>')
            lines.append(f'[00:{i * 3:02d}.000] 中景。{dialogue}')
        return ledger, "\n".join(lines)

    def test_h3_four_single_markers_split_binding_and_idempotence(self):
        ledger, prompt = self.h3_fixture()
        before = validate_ledger(ledger, prompt)
        self.assertEqual(before["status"], "review")
        self.assertTrue(before["evidence"]["dialogue_text_verified"])
        self.assertFalse(before["evidence"]["speaker_binding_verified"])
        compiled = compile_prompt(prompt, ledger)
        self.assertEqual(compiled.count("<d>"), 8)
        self.assertEqual(compiled.count("Dialogue speaker: <Subject A>."), 4)
        self.assertEqual(compiled.count("Dialogue speaker: <Subject B>."), 4)
        self.assertEqual(compile_prompt(compiled, ledger), compiled)
        shot_re = re.compile(r"^\[(\d\d:\d\d\.\d+)\]\s*(.*)$")
        self.assertEqual([shot_re.match(line).group(1) for line in prompt.splitlines()],
                         [shot_re.match(line).group(1) for line in compiled.splitlines()])
        ledger["prompt_sha256"] = hashlib.sha256(compiled.encode()).hexdigest()
        after = validate_ledger(ledger, compiled)
        self.assertEqual(after["status"], "pass", after)
        self.assertTrue(after["evidence"]["speaker_binding_verified"])

    def test_h3_single_start_count_and_intermediate_end(self):
        ledger, prompt = self.h3_fixture()
        for bad, code in ((prompt.replace("00:03.000", "00:03.100"), "SHOT_TIME_MISMATCH"),
                          ("\n".join(prompt.splitlines()[:-1]), "SHOT_COUNT_MISMATCH"),
                          (prompt + "\n[00:12.000] 多一镜", "SHOT_COUNT_MISMATCH")):
            self.assertIn(code, self.codes(ledger, prompt_text=bad))
        ledger["shots"][0]["end"] = 2.5
        self.assertIn("SHOT_TIME_MISMATCH", self.codes(ledger, prompt_text=prompt))

    def test_dialogue_omission_replacement_and_order_blocked(self):
        ledger, prompt = self.h3_fixture()
        for bad in (prompt.replace("第1句。", "第1。"), prompt.replace("回答1。", "答复1。"),
                    prompt.replace("「第1句。」「回答1。」", "「回答1。」「第1句。」")):
            self.assertIn("DIALOGUE_TEXT_MISMATCH", self.codes(ledger, prompt_text=bad))
            with self.assertRaises(ValueError):
                compile_prompt(bad, ledger)
        compiled = compile_prompt(prompt, ledger)
        self.assertIn("DIALOGUE_TEXT_MISMATCH", self.codes(ledger, prompt_text=compiled.replace("第1句。", "第1。")))

    def test_real_four_shot_timing_and_chinese_dialogue(self):
        ledger = fixture()
        timings = [(0, 3.5), (3.5, 5.5), (5.5, 8), (8, 10)]
        ledger["shots"] = [{"id": f"S{i + 1}", "start": start, "end": end,
                            "lead_subject": "a", "states": {}, "dialogue": []}
                           for i, (start, end) in enumerate(timings)]
        ledger["shots"][2]["dialogue"] = [
            {"speaker": "a", "text": "三千。", "mode": "on_screen"},
            {"speaker": "a", "text": "我三年，就值这个价。", "mode": "on_screen"}]
        prompt = ('[00:00.000] 中景，电话。\n[00:03.500] 挂断电话。\n'
                  '[00:05.500] <d>[Chinese]「三千。」</d> 停顿。'
                  '<d>[Chinese]「我三年，就值这个价。」</d>\n[00:08.000] 定住。')
        compiled = compile_prompt(prompt, ledger)
        self.assertEqual(compiled, compile_prompt(compiled, ledger))
        self.assertTrue(validate_ledger(ledger, compiled)["evidence"]["speaker_binding_verified"])

    def test_missing_dialogue_text_fails(self):
        for text in (None, "", "unknown"):
            self.ledger["shots"][0]["dialogue"][0]["text"] = text
            self.assertIn("MISSING_DIALOGUE_TEXT", self.codes())
        del self.ledger["shots"][0]["dialogue"][0]["text"]
        self.assertIn("MISSING_DIALOGUE_TEXT", self.codes())

    def test_wrong_explicit_speaker_binding_blocks(self):
        ledger, prompt = self.h3_fixture()
        compiled = compile_prompt(prompt, ledger)
        wrong = compiled.replace("Dialogue speaker: <Subject A>.", "Dialogue speaker: <Subject B>.", 1)
        self.assertIn("SPEAKER_BINDING_MISMATCH", self.codes(ledger, prompt_text=wrong))
        with self.assertRaises(ValueError):
            compile_prompt(wrong, ledger)
        wrong_attr = PROMPT.replace('speaker="甲"', 'speaker="乙"')
        self.assertIn("SPEAKER_BINDING_MISMATCH", self.codes(prompt_text=wrong_attr))

    def test_mixed_single_and_range(self):
        ledger, prompt = self.h3_fixture()
        prompt = prompt.replace("[00:03.000]", "[00:03.000-00:06.000]")
        compiled = compile_prompt(prompt, ledger)
        self.assertEqual(compiled, compile_prompt(compiled, ledger))
        self.assertTrue(validate_ledger(ledger, compiled)["evidence"]["speaker_binding_verified"])

    def test_numeric_seconds_format(self):
        prompt = '[0-2s] 第一镜<d>你好</d>\n[2-4s] 第二镜'
        compiled = compile_prompt(prompt, self.ledger)
        self.assertEqual(compiled, compile_prompt(compiled, self.ledger))


if __name__ == "__main__":
    unittest.main()
