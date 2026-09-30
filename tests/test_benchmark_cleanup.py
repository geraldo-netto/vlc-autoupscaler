"""ERR-9 / RES-3: benchmark diagnostics and child retirement survive failures."""
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import bench_gpu_pacing as gpu
import bench_native_playback as playback
import test_native_vout_runtime as native
import os
import json
import bench_playback_policies as policies
import bench_vulkan_matrix as matrix
import profile_project as profile


class GpuCaptureTests(unittest.TestCase):
    def test_err9_stderr_larger_than_pipe_completes(self):
        command = [sys.executable, '-c',
                   "import sys; sys.stderr.write('x'*1048576); print('finished')"]
        clock = time.monotonic
        started = clock()
        with tempfile.TemporaryDirectory() as root:
            log = Path(root) / 'capture.log'
            with patch.object(gpu.time, 'monotonic', side_effect=lambda: (clock()-started)*30):
                rc, errors, samples = gpu.collect(command, {}, log, False)
            self.assertEqual(rc, 0)
            self.assertEqual(errors, 'x'*1048576)
            self.assertEqual(log.read_text(), 'finished\n')
            self.assertEqual(log.with_suffix('.stderr').read_text(), errors)
            self.assertEqual(samples, [])

    def test_err9_timeout_reaps_child_and_keeps_logs(self):
        children = []
        popen = subprocess.Popen

        def launch(*args, **kwargs):
            child = popen(*args, **kwargs)
            children.append(child)
            return child

        with tempfile.TemporaryDirectory() as root:
            log = Path(root) / 'capture.log'
            with patch.object(gpu.subprocess, 'Popen', side_effect=launch), \
                    patch.object(gpu.time, 'monotonic', side_effect=[0, 91]):
                with self.assertRaisesRegex(TimeoutError, 'GPU benchmark timed out'):
                    gpu.collect([sys.executable, '-c', 'import time; time.sleep(30)'], {}, log, False)
            self.assertIsNotNone(children[0].returncode)
            self.assertTrue(log.exists())
            self.assertTrue(log.with_suffix('.stderr').exists())


class PlaybackCleanupTests(unittest.TestCase):
    def cleanup_child(self, child):
        if child.poll() is None:
            child.kill()
        child.wait()
        child.stdin.close()
        child.stdout.close()

    def child(self, script):
        child = subprocess.Popen([sys.executable, '-c', script], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, text=True)
        self.addCleanup(self.cleanup_child, child)
        return child

    def test_res3_closed_stdin_live_child_is_reaped(self):
        child = self.child("import os,time; os.close(0); print('ready',flush=True); time.sleep(30)")
        self.assertEqual(child.stdout.readline(), 'ready\n')
        with self.assertRaises(BrokenPipeError):
            playback.stop(child)
        self.assertIsNotNone(child.returncode)

    def test_res3_normal_quit(self):
        child = self.child("import sys; assert sys.stdin.readline() == 'quit\\n'")
        self.assertEqual(playback.stop(child), 0)

    def test_res3_exit_during_send_is_reaped(self):
        child = self.child("import sys; sys.stdin.readline()")

        def exit_during_send(player, _command):
            player.kill()
            raise BrokenPipeError('exited during send')

        with patch.object(playback, 'send', side_effect=exit_during_send):
            with self.assertRaises(BrokenPipeError):
                playback.stop(child)
        self.assertIsNotNone(child.returncode)

    def test_res3_timeout_kills_and_reaps(self):
        child = Mock()
        child.poll.return_value = None
        child.wait.side_effect = [subprocess.TimeoutExpired('vlc', 10), -9]
        with self.assertRaises(subprocess.TimeoutExpired):
            playback.stop(child)
        child.kill.assert_called_once_with()
        self.assertEqual(child.wait.call_count, 2)

    def test_res3_capture_preserves_measurement_error(self):
        with tempfile.TemporaryDirectory() as root:
            args = SimpleNamespace(output=Path(root), build=Path(root))
            with patch.object(playback, 'command', return_value=['unused']), \
                    patch.object(playback.subprocess, 'Popen'), \
                    patch.object(playback, 'measure', side_effect=ValueError('measurement failed')), \
                    patch.object(playback, 'stop', side_effect=BrokenPipeError('cleanup failed')):
                with self.assertRaisesRegex(ValueError, 'measurement failed') as caught:
                    playback.capture(args, {}, 'clip', 'native', 0, 0)
                self.assertIsInstance(caught.exception.__cause__, BrokenPipeError)


class NativeCleanupTests(unittest.TestCase):
    def capture(self, child, control_error=None):
        with tempfile.TemporaryDirectory() as root:
            args = SimpleNamespace(output=Path(root), build=Path(root), clip=Path('clip'))
            child.pid = os.getpid()
            with patch.object(native.subprocess, 'Popen', return_value=child), \
                    patch.object(native.time, 'sleep'), \
                    patch.object(native, 'verify_plugin_maps'), \
                    patch.object(native, 'controls', return_value={}, side_effect=control_error), \
                    patch.object(native, 'window_state', return_value={}):
                return native.playback(args, {}, 'title')

    def test_rev9_broken_pipe_reaps_and_closes(self):
        child = Mock()
        child.poll.return_value = None
        child.stdin.write.side_effect = BrokenPipeError('quit failed')
        with self.assertRaises(BrokenPipeError):
            self.capture(child)
        child.kill.assert_called_once_with()
        child.wait.assert_called_once_with()
        child.stdin.close.assert_called_once_with()

    def test_rev9_hung_quit_reaps_and_closes(self):
        child = Mock()
        child.poll.return_value = None
        child.wait.side_effect = [subprocess.TimeoutExpired('vlc', 10), -9]
        with self.assertRaises(subprocess.TimeoutExpired):
            self.capture(child)
        child.kill.assert_called_once_with()
        self.assertEqual(child.wait.call_count, 2)
        child.stdin.close.assert_called_once_with()

    def test_rev9_preserves_control_error_when_cleanup_fails(self):
        child = Mock()
        child.poll.return_value = None
        child.stdin.write.side_effect = BrokenPipeError('quit failed')
        with self.assertRaisesRegex(ValueError, 'controls failed') as caught:
            self.capture(child, ValueError('controls failed'))
        self.assertIsInstance(caught.exception.__cause__, BrokenPipeError)
        child.wait.assert_called_once_with()
        child.stdin.close.assert_called_once_with()

    def test_rev9_success_closes_without_kill(self):
        child = Mock(returncode=0)
        child.poll.return_value = None
        self.assertEqual(self.capture(child)['returncode'], 0)
        child.stdin.write.assert_called_once_with('quit\n')
        child.wait.assert_called_once_with(timeout=10)
        child.kill.assert_not_called()
        child.stdin.close.assert_called_once_with()


class CapturePreservationTests(unittest.TestCase):
    def run_capture(self, runner, root):
        args = SimpleNamespace(output=root, build=Path('build'), clips=Path('clips'), frames=8)
        if runner == 'policies':
            return policies.capture(args, policies.jobs('cpu')[0], 0, 0)
        if runner == 'matrix':
            return matrix.capture(args.build, Path('clip'), next(matrix.jobs()), output=root)
        case = profile.pipeline_case('review', 4, 4, 1280, 720)
        return profile.run_case(case, args, {'all': [0]}, 0, 0)

    def test_rev14_failed_attempts_preserve_raw_evidence(self):
        failures = [subprocess.CompletedProcess([], 0, '{broken', 'useful diagnostic'),
                    subprocess.CompletedProcess([], 3, 'partial', 'useful diagnostic'),
                    subprocess.TimeoutExpired('benchmark', 90, output=b'partial', stderr=b'useful diagnostic'),
                    OSError('launch failed')]
        for runner in ('policies', 'matrix', 'profile'):
            for failure in failures:
                with self.subTest(runner=runner, failure=failure), tempfile.TemporaryDirectory() as root:
                    result = failure if isinstance(failure, subprocess.CompletedProcess) else None
                    error = failure if isinstance(failure, BaseException) else None
                    with patch.object(subprocess, 'run', return_value=result, side_effect=error):
                        with self.assertRaises(RuntimeError):
                            self.run_capture(runner, Path(root))
                    saved = json.loads((Path(root) / '0.attempt.json').read_text())
                    self.assertTrue(saved['command'])
                    self.assertTrue(saved['failure'])
                    self.assertIn('returncode', saved)
                    if not isinstance(failure, OSError):
                        self.assertEqual(saved['stderr'], 'useful diagnostic')
                        self.assertTrue(saved['stdout'])


if __name__ == '__main__':
    unittest.main()
