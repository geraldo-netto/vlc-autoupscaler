"""OBS-24: named profile cases cannot inherit hidden input/policy changes."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import profile_project as profile


class EnvironmentTests(unittest.TestCase):
    def test_rev24_repetitions_keep_distinct_raw_attempts(self):
        for kind in ('pipeline', 'empty'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as root:
                args = SimpleNamespace(build=Path('unused'), frames=8, output=Path(root))
                case = dict(profile.pipeline_case('review', 4, 4, 1280, 720),
                            kind=kind, workers=4)
                captures = [subprocess.CompletedProcess([], 0,
                            json.dumps(dict(frame_mean=repeat, samples=[[repeat] * 9])),
                            f'diagnostic-{repeat}') for repeat in range(2)]
                with patch.object(profile.subprocess, 'run', side_effect=captures):
                    summaries = [profile.run_case(case, args, {'all': [0]}, repeat, 0)
                                 for repeat in range(2)]
                self.assertEqual(len(list(Path(root).glob('*.attempt.json'))), 2)
                for repeat, summary in enumerate(summaries):
                    saved = json.loads((Path(root) / summary['attempt_file']).read_text())
                    self.assertEqual(saved['repetition'], repeat)
                    self.assertEqual(saved['order'], summary['order'])
                    self.assertEqual(saved['case'], case)
                    self.assertEqual(saved['attempt_file'], summary['attempt_file'])
                    self.assertEqual(saved['stdout'], captures[repeat].stdout)
                    self.assertEqual(saved['stderr'], captures[repeat].stderr)

    def test_obs24_inherited_controls_are_scrubbed_and_effective_controls_recorded(self):
        controls = dict(INPUT='/unexpected.yuv', WIDTH='320', HEIGHT='180', EXECUTOR='2',
                        ACTIVE='1', ZEROCOPY='0', ADAPTIVE='1', WARMUP='0',
                        SHARP_THRESHOLD='1', USM_CPU_FIRST='99', USM_CPU_COUNT='1', VERIFY_PIXELS='1')
        inherited = {'UP_PROFILE_' + key: value for key, value in controls.items()}
        inherited['UP_PROFILE_FUTURE_CONTROL'] = 'unexpected'
        case = profile.pipeline_case('review', 4, 4, 1280, 720)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        args = SimpleNamespace(build=Path('unused'), frames=8, output=Path(temporary.name))
        completed = subprocess.CompletedProcess([], 0, stdout=json.dumps({}))
        with patch.dict(os.environ, inherited), patch.object(profile.subprocess, 'run', return_value=completed) as run:
            result = profile.run_case(case, args, {'all': [0]}, 0, 0)
        actual = run.call_args.kwargs['env']
        self.assertNotIn('UP_PROFILE_INPUT', actual)
        self.assertNotIn('UP_PROFILE_FUTURE_CONTROL', actual)
        self.assertEqual(actual['UP_PROFILE_WIDTH'], '640')
        self.assertEqual(actual['UP_PROFILE_HEIGHT'], '360')
        self.assertEqual(actual['UP_PROFILE_ADAPTIVE'], '0')
        self.assertEqual(actual['UP_PROFILE_ZEROCOPY'], '1')
        self.assertEqual(result['environment'], {key: value for key, value in actual.items()
                                                if key.startswith('UP_PROFILE_')})
        self.assertEqual(result['input'], dict(kind='generated', width=640, height=360, content=1))


if __name__ == '__main__':
    unittest.main()
