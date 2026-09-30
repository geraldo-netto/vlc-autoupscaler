"""REV-25: native playback acceptance survives optimized Python."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


def valid_result():
    window = {'geometry': 'Width: 1280\nHeight: 720\n', 'state': ''}
    return dict(returncode=0, native_geometry=['native'],
                fullscreen={'1': dict(window, state='_NET_WM_STATE_FULLSCREEN')},
                resized={'1': window}, restored={'1': window}, after_exit={},
                subtitle='AUTOUPSCALE', time_responses=['10', '1'], displayed=['12'],
                volume=[dict(percentages=[[value, value]]) for value in ('100%', '25%', '50%')])


def invalid_results():
    replacements = dict(returncode=1, native_geometry=[], fullscreen={}, restored={},
                        resized={}, after_exit={'1': {}}, subtitle='',
                        time_responses=['1', '10'], displayed=[], volume=[])
    rows = [dict(valid_result(), **{key: value}) for key, value in replacements.items()]
    for field, state in [('fullscreen', ''), ('restored', '_NET_WM_STATE_FULLSCREEN')]:
        row = valid_result()
        row[field]['1']['state'] = state
        rows.append(row)
    return rows


def invalid_volume_results():
    rows = []
    for volumes in ([], [[]], [['0%']], [['100%', '0%']]):
        row = valid_result()
        row['volume'][0]['percentages'] = volumes
        rows.append(row)
    for count in (1, 2, 4):
        row = valid_result()
        row['volume'] = [copy.deepcopy(row['volume'][0]) for _ in range(count)]
        rows.append(row)
    return rows


class NativeValidationTests(unittest.TestCase):
    def validate_in_subprocess(self, row, optimized):
        command = [sys.executable, *(['-O'] if optimized else []), '-c',
                   'import json,sys; sys.path.insert(0,sys.argv[1]); '
                   'from test_native_vout_runtime import validate; '
                   'validate(json.load(sys.stdin)); print("PASS")',
                   str(Path(__file__).resolve().parent)]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        env.pop('PYTHONOPTIMIZE', None)
        return subprocess.run(command, input=json.dumps(row), text=True,
                              capture_output=True, env=env, timeout=10)

    def test_rev25_valid_result_passes_in_both_modes(self):
        for optimized in (False, True):
            result = self.validate_in_subprocess(valid_result(), optimized)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, 'PASS\n')

    def test_rev25_each_missing_acceptance_condition_fails(self):
        for index, row in enumerate(invalid_results() + invalid_volume_results()):
            for optimized in (False, True):
                with self.subTest(index=index, optimized=optimized):
                    result = self.validate_in_subprocess(row, optimized)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn('PASS', result.stdout)

    def test_rev25_invalid_presentation_and_window_boundaries(self):
        for value in ('0', '-1', 'not-a-count', str(-(2**63))):
            row = valid_result()
            row['displayed'] = [value]
            for optimized in (False, True):
                self.assertNotEqual(self.validate_in_subprocess(row, optimized).returncode, 0)
        row = valid_result()
        row['restored'] = {'1': {'geometry': 'Width: 1279\nHeight: 720\n', 'state': ''}}
        for optimized in (False, True):
            self.assertNotEqual(self.validate_in_subprocess(row, optimized).returncode, 0)


if __name__ == '__main__':
    unittest.main()
