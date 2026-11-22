"""P12 回归：真实子进程、跨段判据、编译输入边界。"""
import ast
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import validate_prompt as vp
import compile_feed as compiler
import sd_core


class ScopeRegressionTests(unittest.TestCase):
    def state(self):
        state = sd_core.default_project_state()
        state['receipt']['asset_book'] = 'P2-测试夹具资产.md'
        base = state['segments'][0]
        state['segments'] = [copy.deepcopy(base) for _ in range(5)]
        for i, seg in enumerate(state['segments'], 1):
            seg.update(seg_id=f'SEG-{i:02d}', bridge='硬切跳，同场连续性待核验')
            seg['shots'][0]['spec'] = '全景 · 35mm · 略仰 · 缓拉'
        return state

    def test_digest_save_and_production_changes(self):
        state = self.state()
        digest = sd_core.input_digest(state, 'SEG-03')
        state['workflow'] = {'input_digest': digest, 'checks': '通过'}
        self.assertEqual(digest, sd_core.input_digest(state, 'SEG-03'))
        self.assertEqual(sd_core.workflow_summary(state, 'SEG-03')['checks'], '通过')
        self.assertNotEqual(digest, sd_core.input_digest(state, 'SEG-02:SEG-04'))
        state['segments'][2]['shots'][0]['action'] += '停步'
        self.assertNotEqual(digest, sd_core.input_digest(state, 'SEG-03'))

    def test_legacy_mode_and_conflict(self):
        state = self.state()
        del state['locks']['asset_mode']
        state['material_mode'] = 'M0'
        self.assertIn('素材形态：M0', compiler.compile_project_to_feed(state, 'SEG-03'))
        state['locks']['asset_mode'] = 'M1'
        with self.assertRaisesRegex(ValueError, '冲突'):
            compiler.compile_project_to_feed(state, 'SEG-03')
        with self.assertRaisesRegex(ValueError, '冲突'):
            sd_core.verify_feed_against_state('', state)

    def test_summary_missing_receipt_locks_bridge_digest(self):
        state = self.state()
        state['receipt'] = {}
        state['workflow'] = {'checks': '通过'}
        del state['locks']['aspect']
        del state['segments'][2]['bridge']
        result = sd_core.workflow_summary(state, 'SEG-03')
        self.assertEqual(result['scope']['selected_ids'], ['SEG-03'])
        self.assertEqual(result['checks'], '需复核')
        self.assertTrue(any('aspect' in item for item in result['blocked_by']))
        self.assertTrue(any('bridge' in item for item in result['blocked_by']))
        self.assertTrue(any('未提供' in item for item in result['unverified']))
        self.assertTrue(result['next_action'])
        restored = self.state()
        restored['receipt'] = {}
        text = compiler.compile_project_to_feed(restored, 'SEG-03')
        self.assertIn('激活外挂：未提供/未核验', text)
        self.assertNotIn('资产另册：', text)

    def test_scope_metadata_board_and_body(self):
        import build_board_lite as board
        state = self.state()
        for selector, count, first in [('SEG-03', 1, 3), ('SEG-02:SEG-04', 3, 2)]:
            text = compiler.compile_project_to_feed(state, selector)
            data = board.parse_md(text)
            self.assertEqual(len(data['segments']), count)
            self.assertEqual(data['scope']['project_total'], 5)
            self.assertEqual(data['scope']['selector'], selector)
            self.assertEqual(data['segments'][0]['original_index'], first)
            self.assertEqual(data['segments'][0]['seg_id'], f'SEG-{first:02d}')
            self.assertIn('workflow', data)
        self.assertNotIn('sd-feed-metadata:', compiler.compile_project_to_feed(state))

    def test_verifier_segment_isolation(self):
        state = self.state()
        state['segments'][1]['camera_combo_80'] = '不存在的机位'
        text = compiler.compile_project_to_feed(state, 'SEG-03')
        self.assertFalse(any('SEG-02' in item for item in sd_core.verify_feed_against_state(text, state)[1]))
        state['segments'][2]['camera_combo_80'] = '独有机位'
        text = compiler.compile_project_to_feed(state, 'SEG-02:SEG-04')
        text = text.replace('【时间轴分镜】', '【时间轴分镜】独有机位', 1)
        self.assertTrue(any('SEG-03' in item for item in sd_core.verify_feed_against_state(text, state)[1]))

    def test_cli_compile_validate_board(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            state_path = root / 'state.json'
            state_path.write_text(json.dumps(self.state(), ensure_ascii=False), encoding='utf-8')
            for selector in ('SEG-03', 'SEG-02:SEG-04'):
                feed = root / (selector.replace(':', '_') + '.md')
                commands = [('compile_feed.py', '--state', state_path, '--segments', selector, '--out', feed),
                            ('validate_prompt.py', feed, '--state', state_path, '--segments', selector, '--model', '2.5', '--allow-warn'),
                            (str(HERE.parent.parent / 'sd-feed-engine/scripts/gate_check.py'), feed, '--state', state_path, '--segments', selector, '--model', '2.5', '--aspect', '16:9'),
                            ('build_board_lite.py', feed, '--state', state_path, '--out', root / 'board.html')]
                for script, *args in commands:
                    result = subprocess.run([sys.executable, str(HERE / script), *map(str, args)],
                                            capture_output=True, text=True, encoding='utf-8',
                                            env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1'})
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class P12Tests(unittest.TestCase):
    def cli(self, script, *args):
        r = subprocess.run([sys.executable, str(HERE / script), *map(str, args)],
                           capture_output=True, text=True, encoding='utf-8',
                           env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1'}, timeout=120)
        return r

    def state(self):
        state = sd_core.default_project_state()
        state['receipt']['asset_book'] = 'P2-资产提示词.md'
        other = copy.deepcopy(state['segments'][0])
        other.update(seg_id='段2', bridge='承接上段末镜；示例同场，真实尾帧待生成后核验。')
        other['shots'][0]['spec'] = '全景 · 35mm · 略仰 · 缓拉'
        state['segments'].append(other)
        return state

    def test_real_segment_range_contract(self):
        state = self.state()
        state['segments'][0]['seg_id'] = 'seg_01'
        state['segments'][1]['seg_id'] = 'seg_02'
        self.assertEqual(sd_core.resolve_segments(state['segments'], 'seg_02'), [1])
        self.assertEqual(sd_core.resolve_segments(state['segments'], 'seg_01:seg_02'), [0, 1])
        for selector in ['seg_02:seg_01', 'seg_01,seg_02', 'missing']:
            with self.assertRaises(ValueError):
                sd_core.resolve_segments(state['segments'], selector)
        state['locks']['material_mode'] = 'M0'
        with self.assertRaisesRegex(ValueError, '冲突'):
            compiler.compile_project_to_feed(state)

    def test_codes(self):
        for label in ['', '[段2] ', '[投喂单元 2/3] ', '[EP01][来源][单元乙] ', '[x]' * 8]:
            self.assertEqual(vp._warn_code(label + 'C20c 描述'), 'C20c')
        self.assertEqual(vp._warn_code('普通说明引用 C20c'), '')
        self.assertEqual(vp._warn_code('[高危实拍必崩阻断] C20c 描述'), '')

    def test_state_restore(self):
        old = vp.__dict__.pop('_BY_SEG', None)
        try:
            for exists, value in [(False, None), (True, True), (True, False)]:
                if exists:
                    vp._BY_SEG = value
                else:
                    vp.__dict__.pop('_BY_SEG', None)
                for failed in [False, True]:
                    with patch.object(vp, 'validate', side_effect=ValueError('测试异常') if failed else None,
                                      return_value=([], [], {})):
                        if failed:
                            with self.assertRaises(RuntimeError):
                                vp.cross_segment_alerts('', '2.5', 'new', '1', 'auto', 'auto')
                        else:
                            vp.cross_segment_alerts('', '2.5', 'new', '1', 'auto', 'auto')
                    self.assertEqual('_BY_SEG' in vp.__dict__, exists)
                    if exists:
                        self.assertIs(vp._BY_SEG, value)
        finally:
            vp.__dict__.pop('_BY_SEG', None)
            if old is not None:
                vp._BY_SEG = old

    def test_bridge_and_locks(self):
        state = self.state()
        state['segments'][1].pop('bridge')
        with self.assertRaisesRegex(ValueError, 'bridge'):
            compiler.compile_project_to_feed(state)
        for key in ['model', 'aspect', 'seam']:
            state = self.state()
            state['locks'].pop(key)
            with self.assertRaises(ValueError):
                compiler.compile_project_to_feed(state)
        for seam in ['1', '2', '3', '4']:
            state = self.state()
            state['locks'].update(seam=seam, model='2.0', aspect='9:16')
            state['segments'][1]['bridge'] = '硬切跳到另一场景，声音按上游分镜。'
            text = compiler.compile_project_to_feed(state)
            self.assertIn('9:16 竖屏', text)
            self.assertIn('模型锁：2.0', text)
            self.assertNotIn('同场同轴不换场', text)
            if seam != '1':
                self.assertNotIn('第 13.5 秒起运动收束', text)

    def test_c40_scope(self):
        text = ('【画幅风格】16:9\n【场景资产】教室\n【核心人物】@甲\n'
                '【站位声明】@甲（手头事务：翻书）\n【时间轴分镜】\n'
                '00:00-00:03 [镜头1] 中景 · 平视 · 固定。周围人群围观。声音：无。台词：无。\n'
                '【音效】无\n【强制禁止项】禁止其他人围观\n')
        issues, warns, _ = vp.validate(text, '2.5', 'new')
        vp.finalize_checks(text, issues, warns)
        self.assertTrue(any('C40b' in w for w in warns))
        good = text.replace('周围人群围观。', '周围人群低头翻书。')
        issues, warns, _ = vp.validate(good, '2.5', 'new')
        vp.finalize_checks(good, issues, warns)
        self.assertFalse(any('C40b' in w for w in warns))

    def test_real_cli_formats_and_e2e(self):
        with tempfile.TemporaryDirectory(prefix='P12 中文路径 ') as td:
            root = Path(td)
            state = self.state()
            src = root / '输入 state.json'
            dst = root / '投喂 feed.md'
            src.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
            r = self.cli('compile_feed.py', '--state', src, '--out', dst)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            text = dst.read_text(encoding='utf-8')
            r = self.cli('validate_prompt.py', dst, '--model', '2.5')
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn('[+] PASSED', r.stdout)
            self.assertNotIn('[!] WARN:', r.stdout)
            for fmt in ['original', 'plain', 'heading', 'colon']:
                bad = text.replace('画面主体：', '画面主体：端坐如钟，')
                if fmt == 'plain':
                    bad = re.sub(r'^## .*\n|^```[^\n]*\n', '', bad, flags=re.M)
                elif fmt == 'heading':
                    bad = re.sub(r'## 【投喂单元 (\d+)/2[^\n]*', r'## 段\1', bad)
                elif fmt == 'colon':
                    bad = re.sub(r'(\[镜头\d+\]) ', r'\1：', bad)
                dst.write_text(bad, encoding='utf-8')
                r = self.cli('validate_prompt.py', dst, '--model', '2.5')
                self.assertEqual(r.returncode, 1, (fmt, r.stdout, r.stderr))
                self.assertGreaterEqual(r.stdout.count('[高危实拍必崩阻断]'), 2, (fmt, r.stdout))
            src.write_text('{}', encoding='utf-8')
            r = self.cli('compile_feed.py', '--state', src)
            self.assertNotEqual(r.returncode, 0)

    def test_five_cross_codes_real_cli(self):
        # 复用既有真实正反例输入，但独立启动 CLI，避免只模拟返回告警。
        source = Path(vp.__file__).read_text(encoding='utf-8')
        tree = ast.parse(source)
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_self_test')
        env = {}
        for node in fn.body:
            if isinstance(node, ast.Assign):
                try:
                    val = eval(compile(ast.Expression(node.value), '<样例>', 'eval'), {'__builtins__': {}}, env)
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            env[target.id] = val
                except Exception:
                    pass
        samples = {
            'C11b': env['_t_c11b_multi'],
            'C17d': env['_seg1'] + '\n' + env['_seg2_drift'],
            'C17e': env['_e_seg1'] + '\n' + env['_e_seg2_new'],
        }
        # 另两条选取自测中送入 validate 的字面/变量表达式。
        samples['C26f'] = (env['_e_seg1'].replace('@SCN-修表铺', '@SCN-修表铺；@PRP-怀表（参考图3）')
                            + '\n' + env['_e_seg2_new'].replace('甲看着乙。', '甲看着怀表。'))
        for code in ['C18m']:
            for node in fn.body:
                if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                    continue
                call = node.value
                if not isinstance(call.func, ast.Name) or call.func.id != 'validate' or not call.args:
                    continue
                try:
                    sample = eval(compile(ast.Expression(call.args[0]), '<样例>', 'eval'), {'__builtins__': {}}, env)
                    if isinstance(sample, str) and sample.count('【画幅风格】') >= 2:
                        alerts = vp.cross_segment_alerts(sample, '2.5', 'new', '1', 'auto', 'auto')
                        if any(vp._warn_code(w) == code for w in alerts):
                            samples[code] = sample
                            break
                except Exception:
                    pass
        self.assertEqual(set(samples), set(vp._CROSS_SEG_CODES))
        with tempfile.TemporaryDirectory() as td:
            for code, sample in samples.items():
                p = Path(td) / (code + '.md')
                p.write_text(sample, encoding='utf-8')
                r = self.cli('validate_prompt.py', p, '--model', '2.5')
                self.assertIn(r.returncode, (0, 1), r.stderr)
                self.assertRegex(r.stdout, r'(?:WARN:|FAIL:).*' + code)


if __name__ == '__main__':
    unittest.main()
