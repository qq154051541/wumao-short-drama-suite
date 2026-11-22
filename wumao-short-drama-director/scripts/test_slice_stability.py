"""完整章节分页、真实覆盖与 CLI 兼容性回归。"""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import slice_context as slicer


class SliceStabilityTests(unittest.TestCase):
    def test_complete_chapters_and_lossless_pages(self):
        raw = ['# 文档', '前言', '## 第一章', *['正文'] * 80,
               '### 子节', '子节正文', '## 第二章', '末行']
        pages = slicer.chapter_pages(raw, 10)
        self.assertEqual(pages, [(0, 2), (2, 85), (85, 87)])
        self.assertEqual([line for start, end in pages for line in raw[start:end]], raw)

    def test_fences_and_frontmatter_do_not_split(self):
        raw = ['---', 'name: 示例', '---', '# 标题', '## 第一章',
               '```markdown', '## 假标题', '```', '~~~', '## 另一个假标题',
               '~~~', '| 表 |', '|---|', '| 值 |', '## 第二章', '结束']
        self.assertEqual(slicer.chapter_pages(raw, 1), [(0, 4), (4, 14), (14, 16)])

    def test_no_heading_and_empty_file(self):
        self.assertEqual(slicer.chapter_pages(['内容'] * 99, 1), [(0, 99)])
        self.assertEqual(slicer.chapter_pages([], 40), [])

    def test_multiple_top_level_chapters(self):
        self.assertEqual(slicer.chapter_pages(['# 甲', '甲正文', '# 乙', '乙正文'], 1),
                         [(0, 2), (2, 4)])

    def test_coverage_missing_and_non_cumulative(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, 'fixture.md').write_text('# 标题\n前言\n## 章一\n甲\n## 章二\n乙\n', encoding='utf-8')
            with patch.object(slicer, 'SUITE_DIR', root), patch.object(
                    slicer, 'resolve_files', return_value=['fixture.md', 'missing.md']):
                first = slicer.build_slice('P3', max_lines_per_file=2)
                second = slicer.build_slice('P3', max_lines_per_file=2, page=2)
                self.assertIn('coverage=2/6 行；本页范围=L1-L2', first)
                self.assertIn('未加载=L3-L6', first)
                self.assertIn('未加载=L1-L2、L5-L6', second)
                self.assertIn('；缺失；未加载=全文', first)
                self.assertIn('--page 2', first)
                self.assertNotIn('> 已读子库：', first)
                self.assertNotIn('乙', second)
                with self.assertRaises(ValueError):
                    slicer.build_slice('P3', page=99)

    def test_source_and_previs_resolution(self):
        for source in ('3', '4'):
            for stage in ('P0', 'P1'):
                files = slicer.resolve_files(stage, source=source, previs=True)
                self.assertIn('sd-recon-engine/references/intel-card.md', files)
                self.assertIn('sd-storyboard-engine/references/p45-previs-storyboard.md', files)
                self.assertEqual(len(files), len(set(files)))
        self.assertFalse(any('sd-recon-engine' in p for p in slicer.resolve_files('P0')))
        self.assertFalse(any('p45-previs' in p for p in slicer.resolve_files('P3')))

    def test_required_stage_gaps_and_adaptation(self):
        required = {
            'P3': ['sd-storyboard-engine/references/scene-space-adaptation.md',
                   'sd-storyboard-engine/references/segment-linkage.md',
                   'wumao-short-drama-director/references/blooper-prevention-playbook.md'],
            'P4': ['sd-feed-engine/references/engineering-language-cleanup.md',
                   'wumao-short-drama-director/references/blooper-prevention-playbook.md',
                   'wumao-short-drama-director/references/asset-delivery-modes.md',
                   'sd-storyboard-engine/references/p45-previs-storyboard.md'],
            'P5': ['wumao-short-drama-director/references/asset-delivery-modes.md'],
        }
        for stage, paths in required.items():
            for path in paths:
                self.assertIn(path, slicer.resolve_files(stage))
        novel = 'wumao-short-drama-director/references/novel-to-shortdrama-adaptation.md'
        self.assertIn(novel, slicer.resolve_files('P1', source='2'))
        for source in ('1', '3', '4'):
            self.assertNotIn(novel, slicer.resolve_files('P1', source=source))

    def test_r2_r3_core_libraries(self):
        r2 = slicer.resolve_files('P3', combat='R2')
        for name in ('combat-iron-laws', 'combat-construction', 'eight-sentence-masters',
                     'combat-rhythm-and-load-guardrails', 'impact-frame-and-banlist',
                     'vfx-rendering-mandate'):
            self.assertIn(f'sd-combat-engine/references/{name}.md', r2)
        r3_names = ('core-combat-laws', 'camera-specs-15modes', 'close-quarters-engine',
                    'xuanhuan-elements-vfx', 'grand-scale-domains', 'arsenal-moves-library',
                    'arsenal-parameter-library', 'character-scene-presets', 'epic-battlefield-protocols')
        for stage in ('P3', 'P4'):
            paths = slicer.resolve_files(stage, combat='R3')
            for name in r3_names:
                self.assertIn(f'sd-xuanhuan-engine/references/{name}.md', paths)
            self.assertFalse(any('sd-real-engine/' in path for path in paths))
        self.assertFalse(any('sd-xuanhuan-engine/' in path for path in slicer.resolve_files('P2', 'R3')))

    def test_model_contract_and_unknown_model(self):
        for model in ('2.0', '2.5'):
            for stage in ('P0', 'P3', 'P4'):
                self.assertIn('wumao-short-drama-director/references/model-adapters.md',
                              slicer.resolve_files(stage, model=model))
            out = slicer.build_slice('P3', model=model)
            self.assertIn(f'Seedance {model} 版本契约', out)
        for invalid in ('h3', '3.0', ''):
            with self.assertRaisesRegex(ValueError, '仅核准'):
                slicer.resolve_files('P4', model=invalid)
        with self.assertRaises(ValueError):
            slicer.resolve_files('P9')

    def test_explicit_content_conditions_and_continuation(self):
        for trigger, (stages, paths) in slicer.TRIGGER_FILES.items():
            stage = stages[0]
            baseline = slicer.resolve_files(stage)
            selected = slicer.resolve_files(stage, triggers=[trigger, trigger])
            for path in paths:
                self.assertNotIn(path, baseline)
                self.assertIn(path, selected)
            self.assertEqual(len(selected), len(set(selected)))
            with self.assertRaises(ValueError):
                slicer.resolve_files('P0', triggers=[trigger])
        with self.assertRaises(ValueError):
            slicer.resolve_files('P3', triggers=['unknown'])
        out = slicer.build_slice('P3', triggers=['crowd', 'voiceover'], max_lines_per_file=1)
        self.assertIn('内容 crowd 触发', out)
        self.assertIn('--trigger crowd --trigger voiceover --page 2', out)
        self.assertNotIn('> 已读子库：', out)
        for mode in ('M0', 'M1', 'M2'):
            self.assertIn(f'素材形态：{mode}', slicer.build_slice('P4', mode=mode))

    def test_trigger_cli(self):
        result = self.cli('--stage', 'P4', '--model', '2.0', '--trigger', 'dialogue',
                          '--trigger', 'quality', '--lines', '1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('dialogue-speed-check.md', result.stdout)
        self.assertIn('prompt-quality-enhancement.md', result.stdout)
        self.assertIn('--trigger dialogue --trigger quality --page 2', result.stdout)
        self.assertEqual(self.cli('--stage', 'P0', '--trigger', 'dialogue').returncode, 2)
        self.assertEqual(self.cli('--model', 'h3').returncode, 2)

    def test_all_real_files_are_lossless(self):
        files = set()
        for stage in slicer.STAGE_FILES:
            for combat in ('none', 'R1', 'R2', 'R3'):
                for model in ('2.0', '2.5'):
                    for source in ('1', '2', '3', '4'):
                        triggers = [key for key, (stages, _) in slicer.TRIGGER_FILES.items() if stage in stages]
                        files.update(slicer.resolve_files(stage, combat, model, source, True, triggers))
        for rel in sorted(files):
            with self.subTest(file=rel):
                raw = Path(slicer.SUITE_DIR, rel).read_text(encoding='utf-8').splitlines()
                pages = slicer.chapter_pages(raw, 40)
                self.assertEqual([line for start, end in pages for line in raw[start:end]], raw)
                for left, right in zip(pages, pages[1:]):
                    self.assertEqual(left[1], right[0])

    def cli(self, *args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
        return subprocess.run([sys.executable, slicer.__file__, *args],
                              capture_output=True, text=True, encoding='utf-8', env=env)

    def test_cli_source_previs_and_continuation(self):
        result = self.cli('--stage', 'P1', '--source', '3', '--previs', '--page', '2')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('sd-recon-engine/references/intel-card.md', result.stdout)
        self.assertIn('p45-previs-storyboard.md', result.stdout)
        self.assertIn('--source 3 --lines 40 --previs --page 3', result.stdout)

    def test_estimate_compatibility(self):
        result = self.cli('--estimate', '--stage', 'P0', '--source', '4', '--previs', '--episodes', '10')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('预算报账', result.stdout)
        self.assertIn('按结构切', result.stdout)
        self.assertIn('当前页输出估算', result.stdout)
        self.assertIn('预算报账', slicer.build_estimate('P3', 'none', '2.5', 'M1', 40, 1, 0))

    def test_invalid_cli_parameters(self):
        for args in [('--page', '0'), ('--lines', '-1'), ('--page', '999999'),
                     ('--episodes', '0'), ('--chars-per-episode', '-1')]:
            with self.subTest(args=args):
                self.assertEqual(self.cli(*args).returncode, 2)

    def test_self_test_compatibility(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(slicer.self_test(), 0)
        result = self.cli('--self-test')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PASSED', result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
