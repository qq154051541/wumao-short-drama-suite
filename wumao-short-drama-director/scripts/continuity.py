"""纯标准库连续性台账；仅验证文本事实，不声称核验成片。

公开 API：load_ledger(root, seg, shots=None)、validate_ledger(ledger,
prompt_text=None, previous=None)、compile_prompt(prompt, ledger)、
save_ledger(root, seg, ledger, prompt_text)。compile_prompt 不修改输入台账；
save_ledger 绑定最终提示词的 UTF-8 SHA256，返回保存路径，不创建父目录。

1.0 数据契约：schema、segment、scene、characters、objects、shots 必填。
characters: [{id, subject: "Subject X", name, role, rank(可选), opening}]
objects: [{id, ...}]；opening/closing 及有效状态字段为 presence(bool)、
anchor_object(道具 id)、side、posture、facing，可选有限数值 x/y。
shots: [{id, start, end, lead_subject, states: {人物id: 部分状态},
         dialogue: [{speaker, text, mode, listener(可选), reaction_subjects(可选)}],
         transitions: [{character, from: {变更字段: 原值},
                        to: {变更字段: 新值}, action: 非空动作}]}]
引用允许人物 id、唯一 subject 或 name。states 逐人继承；空 states 合法。
mode 为 on_screen/off_screen/voiceover；无对白须显式给 dialogue: []。
transitions 的 from/to 键集合必须一致，覆盖真实状态变更，禁止空转变。
同 scene 的 previous 须为完整有效台账；其末镜有效状态承接本段 opening，
可选 closing 为声明的最终状态，必须与推导结果相符。缺失未知值不推测。
时间码兼容 range 与行首 [MM:SS.mmm]；single 中间 end 取下一镜 start，
最后 end 使用对应台账 end（提示词没有独立末时长证据）。对白 text 为不含
「」的逐句原文，精确比较字符和顺序。编译保留 <d> 开标签与 [Chinese]，
多句拆为逐句标签；无显式绑定时只验证文本，不猜说话人。
evidence 的 dialogue_text_verified/speaker_binding_verified 区分两类文本证据。
"""

import copy
import hashlib
import json
import math
from pathlib import Path
import re

SCHEMA = "wumao-continuity/1.0"
STATE_FIELDS = ("presence", "anchor_object", "side", "posture", "facing")
MOTION_FIELDS = STATE_FIELDS + ("x", "y")
POSTURES = {"standing", "seated", "crouching", "lying"}
SIDES = {"left", "right", "center", "左", "右", "中"}
FACINGS = {"N", "NE", "E", "SE", "S", "SW", "W", "NW",
           "north", "northeast", "east", "southeast", "south", "southwest",
           "west", "northwest", "北", "东北", "东", "东南", "南", "西南", "西", "西北"}
BLOCK = re.compile(r"\[Continuity\][^\r\n]*?\[/Continuity\]")
TIME = re.compile(
    r"(?<![\d:])(?:\[)?(?P<a>\d+(?::\d{2})?(?:\.\d+)?)\s*(?:s|秒)?"
    r"\s*[-–—~至]\s*(?P<b>\d+(?::\d{2})?(?:\.\d+)?)\s*(?:s|秒)?(?:\])?"
    r"(?=\s|\[|。|$)|^[ \t]*\[(?P<single>\d{2}:\d{2}\.\d+)\]", re.MULTILINE)
DIALOGUE = re.compile(r"(?P<open><d(?:\s+[^<>]*?)?>)(?P<body>.*?)</d>", re.DOTALL)
QUOTED = re.compile(r"「([^「」]*)」")
SPEAKER_ATTR = re.compile(r'''\bspeaker\s*=\s*["']([^"']+)["']''')
BINDING = re.compile(r"Dialogue speaker: <(Subject [A-Za-z0-9_-]+)>\.")


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and value.strip().lower() not in {
        "unknown", "null", "none", "?", "未知", "待定"}


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _seconds(value):
    if ":" in value:
        minutes, seconds = value.split(":")
        if float(seconds) >= 60:
            return None
        return int(minutes) * 60 + float(seconds)
    return float(value)


def _markers(prompt, shots=()):
    matches = list(TIME.finditer(prompt))
    result = []
    for i, match in enumerate(matches):
        if match.group("single") is not None:
            start = _seconds(match.group("single"))
            if i + 1 < len(matches):
                following = matches[i + 1]
                end = _seconds(following.group("single") or following.group("a"))
            else:
                shot = shots[i] if i < len(shots) else {}
                end = shot.get("end") if isinstance(shot, dict) else None
        else:
            start, end = _seconds(match.group("a")), _seconds(match.group("b"))
        result.append((match, (start, end)))
    return result


def _utterances(body):
    """返回逐句原文；中文引号之间仅允许空白，避免静默漏掉文字。"""
    prefix = "[Chinese]" if body.startswith("[Chinese]") else ""
    content = body[len(prefix):]
    quoted = list(QUOTED.finditer(content))
    if quoted:
        if QUOTED.sub("", content).strip():
            raise ValueError("中文对白引号外存在未绑定文字")
        return prefix, [m.group(1) for m in quoted], True
    if prefix or "「" in content or "」" in content:
        raise ValueError("中文对白必须使用完整的「...」")
    return "", [content], False


def _dialogue_check(prompt, marks, shots, aliases, chars, report):
    text_verified, binding_verified, total = True, True, 0
    first = marks[0][0].start() if marks else len(prompt)
    if re.search(r"</?d\b", prompt[:first]):
        report("DIALOGUE_OUTSIDE_SHOT", "dialogue.text", "镜头外存在对白")
        text_verified = False
    for index, (marker, _) in enumerate(marks):
        if index >= len(shots) or not isinstance(shots[index], dict):
            text_verified = binding_verified = False
            continue
        shot = shots[index]
        sid = shot.get("id", index)
        end = marks[index + 1][0].start() if index + 1 < len(marks) else len(prompt)
        body = prompt[marker.end():end]
        entries = shot.get("dialogue", [])
        if not isinstance(entries, list):
            entries = []
        actual, bound = [], []
        matches = list(DIALOGUE.finditer(body))
        remainder = DIALOGUE.sub("", body)
        if re.search(r"</?d\b", remainder):
            report("INVALID_DIALOGUE_TAG", "dialogue.text", "对白标签不完整", sid)
            text_verified = False
        last = 0
        for match in matches:
            try:
                _, texts, _ = _utterances(match.group("body"))
            except ValueError as exc:
                report("INVALID_DIALOGUE_TEXT", "dialogue.text", str(exc), sid)
                text_verified = False
                last = match.end()
                continue
            actual.extend(texts)
            attr = SPEAKER_ATTR.search(match.group("open"))
            gap = body[last:match.start()]
            adjacent = re.search(r"\[Continuity\]([^\r\n]*?)\[/Continuity\]$", gap)
            labels = BINDING.findall(adjacent.group(1)) if adjacent else []
            explicit = labels[0] if len(labels) == 1 else None
            attr_id = aliases.get(attr.group(1)) if attr else None
            explicit_id = aliases.get(explicit) if explicit else None
            for _ in texts:
                bound.append(explicit_id or attr_id)
            if len(texts) != 1 or (not attr and not explicit):
                binding_verified = False
            if (attr and attr_id not in chars) or (attr and explicit and attr_id != explicit_id):
                report("SPEAKER_BINDING_MISMATCH", "dialogue.speaker", "标签说话人与逐句英文绑定不一致", sid)
                binding_verified = False
            last = match.end()
        expected = [line.get("text") for line in entries if isinstance(line, dict)]
        total += len(expected)
        if actual != expected:
            report("DIALOGUE_TEXT_MISMATCH", "dialogue.text", "实际对白逐句文本、数量或顺序与台账不一致", sid)
            text_verified = False
        for actual_speaker, line in zip(bound, entries):
            if not isinstance(line, dict):
                continue
            if actual_speaker is None:
                binding_verified = False
            elif actual_speaker != (aliases.get(line.get("speaker")) if isinstance(line.get("speaker"), str) else None):
                report("SPEAKER_BINDING_MISMATCH", "dialogue.speaker", "实际逐句说话人绑定与台账不一致", sid)
                binding_verified = False
    return text_verified, binding_verified and text_verified, total


def _path(root, seg):
    if not _text(seg) or seg in {".", ".."} or any(c in seg for c in '/\\:'):
        raise ValueError("segment 必须是单一目录名")
    return Path(root) / "04_feed" / "segments" / seg / "continuity.json"


def load_ledger(root, seg, shots=None):
    """读取台账；shots 可提供预期镜头清单，仅核对、不补造台账事实。

    JSON 损坏、非对象或 segment 不匹配抛 ValueError；文件缺失返回 missing。
    预期 shots 的 start/end/id 存入内存专用 _expected_shots 供 validator 核对。
    """
    path = _path(root, seg)
    if not path.exists():
        return {"schema": SCHEMA, "segment": seg, "characters": [],
                "objects": [], "shots": [], "status": "missing"}
    ledger = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(ledger, dict):
        raise ValueError("连续性台账必须为 JSON 对象")
    if ledger.get("segment") != seg:
        raise ValueError("台账 segment 与目录不匹配")
    if shots is not None:
        ledger["_expected_shots"] = copy.deepcopy(shots)
    return ledger


def _analyse(ledger, prompt_text=None, previous=None):
    errors, warnings = [], []
    dialogue_evidence = {}

    def report(code, field, message, shot=None, character=None, warning=False):
        (warnings if warning else errors).append({"code": code, "shot": shot,
            "character": character, "field": field, "message": message})

    def result(states=None):
        return ({"status": "blocked" if errors else "review" if warnings else "pass",
                 "errors": errors, "warnings": warnings,
                 "evidence": {"text_only": True, "film_verified": False, **dialogue_evidence}}, states or {})

    if not isinstance(ledger, dict):
        report("INVALID_LEDGER", "ledger", "台账必须为对象")
        return result()
    if ledger.get("status") == "missing":
        report("MISSING_LEDGER", "status", "台账文件缺失，无法验证", warning=True)
        return result()
    if ledger.get("schema") != SCHEMA:
        report("INVALID_SCHEMA", "schema", "缺失或不支持的 schema")
    for field in ("segment", "scene"):
        if not _text(ledger.get(field)):
            report("MISSING_FIELD", field, "必须显式提供有效值")
    lists = {}
    for field in ("characters", "objects", "shots"):
        value = ledger.get(field)
        if not isinstance(value, list):
            report("INVALID_FIELD", field, "必须为数组")
            value = []
        lists[field] = value
    if not lists["characters"] or not lists["shots"]:
        report("MISSING_FIELD", "characters/shots", "人物和镜头清单不能为空")
    objects = set()
    for obj in lists["objects"]:
        oid = obj.get("id") if isinstance(obj, dict) else None
        if not _text(oid) or oid in objects:
            report("INVALID_OBJECT", "objects.id", "道具 id 缺失或重复")
        else:
            objects.add(oid)
    chars, aliases, seen = {}, {}, {key: set() for key in ("id", "subject", "name")}
    for char in lists["characters"]:
        if not isinstance(char, dict):
            report("INVALID_CHARACTER", "characters", "人物必须为对象")
            continue
        cid = char.get("id")
        for field in ("id", "subject", "name"):
            value = char.get(field)
            if not _text(value):
                report("MISSING_FIELD", field, "人物标识缺失", character=cid)
            elif value.casefold().strip() in seen[field]:
                report("DUPLICATE_" + field.upper(), field, "人物标识必须唯一", character=cid)
            else:
                seen[field].add(value.casefold().strip())
                if value in aliases and aliases[value] != cid:
                    report("AMBIGUOUS_REFERENCE", field, "人物引用跨字段歧义", character=cid)
                aliases[value] = cid
        subject = char.get("subject")
        if not isinstance(subject, str) or not re.fullmatch(r"Subject [A-Za-z0-9_-]+", subject) or re.search(
                r"\b(pair|group)\b", subject or "", re.I) or char.get("type", "individual") != "individual":
            report("INVALID_SUBJECT", "subject", "每个人物须绑定单一 Subject，拒绝 pair/group", character=cid)
        if not _text(char.get("role")):
            report("MISSING_FIELD", "role", "人物叙事角色不能为空", character=cid)
        if "rank" in char and not (_text(char["rank"]) or _number(char["rank"])):
            report("INVALID_RANK", "rank", "rank 不得为未知值", character=cid)
        if _text(cid):
            chars[cid] = char

    if errors:
        return result()

    def resolve(ref):
        return aliases.get(ref) if isinstance(ref, str) else None

    def state_check(state, cid, shot):
        for field in STATE_FIELDS:
            value = state.get(field)
            valid = (type(value) is bool if field == "presence" else
                     isinstance(value, str) and value in objects if field == "anchor_object" else
                     isinstance(value, str) and value in SIDES if field == "side" else
                     isinstance(value, str) and value in POSTURES if field == "posture" else
                     isinstance(value, str) and value in FACINGS)
            if not valid:
                report("INVALID_STATE", field, "状态缺失、未知或取值非法", shot, cid)
        for field in ("x", "y"):
            if field in state and not _number(state[field]):
                report("INVALID_STATE", field, "坐标须为有限数值", shot, cid)
        for field in ("role", "rank", "subject", "name", "id"):
            if field in state and state[field] != chars[cid].get(field):
                report("IDENTITY_DRIFT", field, "人物身份、主配角与 rank 不得随镜头变化", shot, cid)

    def overlap(states, shot):
        occupied = {}
        for cid, state in states.items():
            if state.get("presence") is not True:
                continue
            anchor, side = state.get("anchor_object"), state.get("side")
            if not isinstance(anchor, str) or not isinstance(side, str):
                continue
            side = {"左": "left", "右": "right", "中": "center"}.get(side, side)
            xy = tuple(state.get(k) for k in ("x", "y"))
            if any(v is not None and not _number(v) for v in xy):
                continue
            key = (anchor, side) + xy
            if key in occupied:
                report("OVERLAPPING_POSITION", "anchor_object/side/x/y",
                       "与人物 " + occupied[key] + " 占据同一锚点同侧同坐标", shot, cid)
            occupied[key] = cid

    states = {}
    for cid, char in chars.items():
        opening = char.get("opening")
        if not isinstance(opening, dict):
            report("MISSING_FIELD", "opening", "每个人物必须有独立开场状态", character=cid)
            opening = {}
        states[cid] = copy.deepcopy(opening)
        state_check(states[cid], cid, "opening")
    if previous is not None:
        if not isinstance(previous, dict) or not _text(previous.get("scene")):
            report("INVALID_PREVIOUS", "previous", "前段场景未知，不能推断是否同场景")
        elif previous["scene"] == ledger.get("scene"):
            prev_result, closing = _analyse(previous)
            if prev_result["status"] != "pass":
                report("INVALID_PREVIOUS", "previous", "同场景前段台账无有效 closing 状态")
            else:
                old_chars = {c["id"]: c for c in previous["characters"]}
                for cid, state in closing.items():
                    if cid not in states:
                        report("CROSS_SEGMENT_MISSING", "characters", "同场景前段人物不能无交代消失", character=cid)
                        continue
                    for field in ("subject", "name", "role", "rank"):
                        if chars[cid].get(field) != old_chars[cid].get(field):
                            report("IDENTITY_DRIFT", field, "跨段人物身份/rank 变化", character=cid)
                    for field in MOTION_FIELDS:
                        if states[cid].get(field) != state.get(field):
                            report("CROSS_SEGMENT_DRIFT", field, "开场未继承前段有效末态", character=cid)
                for cid in states.keys() - closing.keys():
                    if states[cid].get("presence") is not False:
                        report("CROSS_SEGMENT_ENTRY", "presence", "新增人物须从不在场状态经 transition 入场", character=cid)
    overlap(states, "opening")
    shot_ids, last_end = set(), None
    for index, shot in enumerate(lists["shots"]):
        if not isinstance(shot, dict):
            report("INVALID_SHOT", "shots", "镜头必须为对象", index)
            continue
        sid = shot.get("id", index)
        if not _text(shot.get("id")):
            report("INVALID_SHOT_ID", "id", "镜头 id 必须非空且唯一", index)
            sid = index
        elif sid in shot_ids:
            report("INVALID_SHOT_ID", "id", "镜头 id 必须非空且唯一", index)
        shot_ids.add(sid)
        start, end = shot.get("start"), shot.get("end")
        if not (_number(start) and _number(end) and 0 <= start < end):
            report("INVALID_TIME", "start/end", "须显式提供非负递增秒数", sid)
        else:
            if last_end is not None and start < last_end:
                report("INVALID_TIME", "start", "镜头时间不得倒退或重叠", sid)
            last_end = end
        lead = resolve(shot.get("lead_subject"))
        if lead not in chars:
            report("INVALID_LEAD", "lead_subject", "每镜必须且只能有一个合法视觉主体", sid)
        changes = shot.get("states")
        if not isinstance(changes, dict):
            report("MISSING_FIELD", "states", "须显式提供逐人状态对象，可为空以继承", sid)
            changes = {}
        target = copy.deepcopy(states)
        touched = set()
        for ref, patch in changes.items():
            cid = resolve(ref)
            if cid not in chars or not isinstance(patch, dict) or cid in touched:
                report("INVALID_STATE", "states", "状态引用非法、重复或不是对象", sid, ref)
                continue
            touched.add(cid)
            target[cid].update(copy.deepcopy(patch))
        transitions = shot.get("transitions", [])
        if not isinstance(transitions, list):
            report("INVALID_TRANSITION", "transitions", "transitions 必须为数组", sid)
            transitions = []
        covered = set()
        for transition in transitions:
            if not isinstance(transition, dict):
                report("INVALID_TRANSITION", "transitions", "transition 必须为对象", sid)
                continue
            cid = resolve(transition.get("character"))
            before, after = transition.get("from"), transition.get("to")
            if (cid not in chars or not isinstance(before, dict) or not isinstance(after, dict)
                    or not before or before.keys() != after.keys() or not _text(transition.get("action"))):
                report("INVALID_TRANSITION", "transitions", "须有合法 character、同字段 from/to 和 action", sid, cid)
                continue
            for field in before:
                if (field not in MOTION_FIELDS or field not in states[cid] or field not in target[cid]
                        or states[cid][field] != before[field] or target[cid][field] != after[field]
                        or before[field] == after[field] or (cid, field) in covered):
                    report("TRANSITION_MISMATCH", field, "from/to 必须精确匹配真实变更且不得重复", sid, cid)
                else:
                    covered.add((cid, field))
        for cid, state in target.items():
            state_check(state, cid, sid)
            for field in MOTION_FIELDS:
                if states[cid].get(field) != state.get(field) and (cid, field) not in covered:
                    report("MISSING_TRANSITION", field, "位置、姿态、朝向或出入场改变须有匹配动作", sid, cid)
        states = target
        overlap(states, sid)
        dialogue = shot.get("dialogue")
        if not isinstance(dialogue, list):
            report("MISSING_FIELD", "dialogue", "对白须为数组，无对白显式给空数组", sid)
            dialogue = []
        for line in dialogue:
            if not isinstance(line, dict):
                report("INVALID_DIALOGUE", "dialogue", "对白必须为对象", sid)
                continue
            if not _text(line.get("text")):
                report("MISSING_DIALOGUE_TEXT", "dialogue.text", "每条对白必须有明确的非空原文，不推测台词", sid)
            speaker = resolve(line.get("speaker"))
            if speaker not in chars:
                report("INVALID_SPEAKER", "speaker", "缺失或非法说话人", sid)
            mode = line.get("mode")
            if mode not in ("on_screen", "off_screen", "voiceover"):
                report("INVALID_DIALOGUE_MODE", "mode", "必须声明画内/画外/旁白", sid, speaker)
            if mode == "on_screen" and speaker in states and states[speaker].get("presence") is not True:
                report("SPEAKER_ABSENT", "presence", "画内说话人必须在场", sid, speaker)
            refs = []
            if "listener" in line:
                refs.append(line["listener"])
            reactions = line.get("reaction_subjects", [])
            if not isinstance(reactions, list):
                report("INVALID_LISTENER", "reaction_subjects", "反应人物必须为数组", sid)
            else:
                refs.extend(reactions)
            for ref in refs:
                cid = resolve(ref)
                if cid not in chars or cid == speaker:
                    report("INVALID_LISTENER", "listener/reaction_subjects", "听者和反应人物须合法且不含说话人", sid, cid)
        for field in ("role", "rank"):
            if field in shot:
                report("IDENTITY_DRIFT", field, "主配角/rank 属于人物，不得由镜头重定义", sid)
    for cid, char in chars.items():
        if "closing" in char:
            declared = char["closing"]
            if not isinstance(declared, dict) or any(
                    declared.get(k) != states[cid].get(k) for k in set(states[cid]) | set(declared)):
                report("CLOSING_MISMATCH", "closing", "声明末态与逐镜推导末态不一致", character=cid)
    expected = ledger.get("_expected_shots")
    if expected is not None:
        if not isinstance(expected, list) or len(expected) != len(lists["shots"]):
            report("SHOT_COUNT_MISMATCH", "shots", "台账与预期镜头数不一致")
        else:
            for actual, wanted in zip(lists["shots"], expected):
                if not isinstance(actual, dict) or not isinstance(wanted, dict) or any(
                        actual.get(k) != wanted.get(k) for k in ("start", "end")):
                    report("SHOT_TIME_MISMATCH", "shots", "台账与预期镜头时间不一致")
    if prompt_text is not None:
        if not isinstance(prompt_text, str):
            report("INVALID_PROMPT", "prompt_text", "提示词必须为字符串")
        else:
            marks = _markers(prompt_text, lists["shots"])
            if len(marks) != len(lists["shots"]):
                report("SHOT_COUNT_MISMATCH", "prompt_text", "提示词时间码数与台账镜头数不一致")
            else:
                for (_, times), shot in zip(marks, lists["shots"]):
                    if not isinstance(shot, dict) or times != (shot.get("start"), shot.get("end")):
                        report("SHOT_TIME_MISMATCH", "prompt_text", "提示词镜头时间码与台账不一致")
            text_ok, binding_ok, count = _dialogue_check(
                prompt_text, marks, lists["shots"], aliases, chars, report)
            dialogue_evidence.update(dialogue_text_verified=text_ok,
                                     speaker_binding_verified=binding_ok)
            if count and text_ok and not binding_ok:
                report("UNVERIFIED_SPEAKER_BINDING", "dialogue.speaker",
                       "对白文本一致，但尚无逐句说话人绑定证据", warning=True)
            digest = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
            if not ledger.get("prompt_sha256"):
                report("MISSING_PROMPT_HASH", "prompt_sha256", "提示词尚未绑定保存哈希", warning=True)
            elif ledger["prompt_sha256"] != digest:
                report("STALE_PROMPT", "prompt_sha256", "提示词已变更，台账哈希陈旧")
    return result(states)


def validate_ledger(ledger, prompt_text=None, previous=None):
    """返回 status/errors/warnings/evidence；不修改输入、不猜测缺失信息。"""
    return _analyse(ledger, prompt_text, previous)[0]


def compile_prompt(prompt, ledger):
    """按时间码注入英文行内块，返回 str；非法台账/时间码抛 ValueError。

    仅删除本模块单行 [Continuity]...[/Continuity] 块；逐句拆分 <d>，
    保留原开标签、语言标记和台词原文，并紧邻绑定台账 speaker。
    已有 prompt_sha256 不限制重新编译；保存后须重新绑定最终提示词。
    """
    if not isinstance(prompt, str):
        raise ValueError("prompt 必须为字符串")
    clean = BLOCK.sub("", prompt)
    candidate = copy.deepcopy(ledger)
    if not isinstance(candidate, dict) or candidate.get("status") == "missing":
        raise ValueError("缺少有效连续性台账")
    candidate.pop("prompt_sha256", None)
    verdict = validate_ledger(candidate, prompt)
    if verdict["status"] == "blocked":
        raise ValueError(json.dumps(verdict["errors"], ensure_ascii=False))
    aliases = {c[k]: c["id"] for c in ledger["characters"] for k in ("id", "subject", "name")}
    chars = {c["id"]: c for c in ledger["characters"]}
    states = {cid: copy.deepcopy(c["opening"]) for cid, c in chars.items()}

    def subject(ref):
        return "<" + chars[aliases[ref]]["subject"] + ">"

    inserts = []
    markers = _markers(clean, ledger["shots"])
    for index, ((match, _), shot) in enumerate(zip(markers, ledger["shots"])):
        for ref, patch in shot["states"].items():
            states[aliases[ref]].update(patch)
        sentences = ["Internal direction only; do not render these labels as visible text.",
                     "Visual focus: " + subject(shot["lead_subject"]) + "."]
        for cid, state in states.items():
            sentences.append("State of " + subject(cid) + ": " + "; ".join(
                k.replace("_", " ") + "=" + str(state[k]).lower() if isinstance(state[k], bool)
                else k.replace("_", " ") + "=" + str(state[k])
                for k in MOTION_FIELDS if k in state) + ".")
        for t in shot.get("transitions", []):
            sentences.append("Movement of " + subject(t["character"]) + ": " + t["action"] + ".")
        block = "[Continuity] " + " ".join(sentences) + " [/Continuity]"
        if "\n" in block or "\r" in block or block.count("[Continuity]") != 1 or block.count("[/Continuity]") != 1:
            raise ValueError("台账文本不得包含换行或保留的连续性块标记")
        shot_end = markers[index + 1][0].start() if index + 1 < len(markers) else len(clean)
        region = clean[match.end():shot_end]
        entry_index = 0
        for dialogue_match in DIALOGUE.finditer(region):
            prefix, texts, quoted = _utterances(dialogue_match.group("body"))
            replacement = []
            for text in texts:
                entry = shot["dialogue"][entry_index]
                entry_index += 1
                directions = ["Dialogue speaker: " + subject(entry["speaker"]) + ".",
                              "Voice placement: " + entry["mode"].replace("_", " ") + ".",
                              "The following utterance is spoken only by this subject; do not render direction labels as visible text."]
                if "listener" in entry:
                    directions.append("Listener: " + subject(entry["listener"]) + ".")
                if entry.get("reaction_subjects"):
                    directions.append("Reaction subjects: " + ", ".join(subject(r) for r in entry["reaction_subjects"]) + ".")
                instruction = "[Continuity] " + " ".join(directions) + " [/Continuity]"
                utterance = prefix + ("「" + text + "」" if quoted else text)
                replacement.append(instruction + dialogue_match.group("open") + utterance + "</d>")
            inserts.append((match.end() + dialogue_match.start(),
                            match.end() + dialogue_match.end(), "".join(replacement)))
        inserts.append((match.end(), match.end(), block))
    for start, end, replacement in sorted(inserts, key=lambda item: (item[0], item[1]), reverse=True):
        clean = clean[:start] + replacement + clean[end:]
    return clean


def save_ledger(root, seg, ledger, prompt_text):
    """绑定最终提示词哈希后保存，返回 Path；不修改输入或创建父目录。

    保存前严格验证；缺失事实、时间不匹配均抛 ValueError。外部传入的同场景
    previous 应由调用者先使用 validate_ledger(..., previous=...) 验证。
    """
    path = _path(root, seg)
    if not path.parent.is_dir():
        raise FileNotFoundError("台账父目录不存在：" + str(path.parent))
    candidate = copy.deepcopy(ledger)
    if not isinstance(candidate, dict) or candidate.get("segment") != seg or not isinstance(prompt_text, str):
        raise ValueError("台账 segment 或 prompt_text 非法")
    candidate["prompt_sha256"] = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    verdict = validate_ledger(candidate, prompt_text)
    if verdict["status"] != "pass":
        raise ValueError(json.dumps(verdict, ensure_ascii=False))
    candidate.pop("_expected_shots", None)
    path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
