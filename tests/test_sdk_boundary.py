"""BUILD-48: optional real-VLC tests require both SDKs; stub tests always run."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class SdkBoundaryTests(unittest.TestCase):
    def check_configuration(self, vlc, zimg):
        root = Path(__file__).resolve().parent.parent
        enabled = bool(vlc and zimg)
        env = {key: value for key, value in os.environ.items()
               if key not in ('MAKEFLAGS', 'MFLAGS', 'MAKELEVEL')}
        with tempfile.TemporaryDirectory() as directory:
            build = Path(directory) / 'build'
            result = subprocess.run(
                ['make', '-n', '--no-print-directory', 'SHELL=/bin/true', 'IS_X86=',
                 'BUILD=' + str(build), 'VLC_CFLAGS=', 'VLC_LIBS=' + vlc,
                 'HAVE_ZIMG=' + zimg, 'test'], cwd=root, env=env,
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('-o ' + str(build / 'test_usm_pool'), result.stdout)
            for name in ('test_bench_adaptive', 'test_experiment_zimg', 'test_profile_input',
                         'test_profile_pipeline', 'test_profile_pipeline_latency'):
                self.assertEqual('-o ' + str(build / name) + ' ' in result.stdout,
                                 enabled, name)
            self.assertEqual('python3 tests/test_profile_scheduler.py' in result.stdout,
                             enabled)
            guards = [line.split('"')[1] for line in result.stdout.splitlines()
                      if line.startswith('if [ -n "') and 'test_profile_pipeline;' in line]
            self.assertEqual([bool(guard) for guard in guards], [enabled])

    def test_build48_dependency_matrix(self):
        for vlc, zimg in (('', '1'), ('-lvlccore', '1'), ('', ''), ('-lvlccore', '')):
            with self.subTest(vlc=vlc, zimg=zimg):
                self.check_configuration(vlc, zimg)


if __name__ == '__main__':
    unittest.main()
