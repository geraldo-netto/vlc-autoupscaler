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


if __name__ == '__main__':
    unittest.main()
