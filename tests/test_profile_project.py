"""OBS-24: named profile cases cannot inherit hidden input/policy changes."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import profile_project as profile


class EnvironmentTests(unittest.TestCase):
    def test_obs24_inherited_controls_are_scrubbed_and_effective_controls_recorded(self):
        controls = dict(INPUT='/unexpected.yuv', WIDTH='320', HEIGHT='180', EXECUTOR='2',
                        ACTIVE='1', ZEROCOPY='0', ADAPTIVE='1', WARMUP='0',
                        SHARP_THRESHOLD='1', USM_CPU_FIRST='99', USM_CPU_COUNT='1', VERIFY_PIXELS='1')
        inherited = {'UP_PROFILE_' + key: value for key, value in controls.items()}
        inherited['UP_PROFILE_FUTURE_CONTROL'] = 'unexpected'
        case = profile.pipeline_case('review', 4, 4, 1280, 720)
        args = SimpleNamespace(build=Path('unused'), frames=8)
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
