"""OBS-23 / ERR-3: validate saved evidence and retain failed attempts."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import bench_perf15 as bench
import bench_perf15_confirm as confirm
import perf15_statistics as stats
from perf15_fixture import fake_pair


def study(directory):
    args = SimpleNamespace(output=directory, build=Path('unused'), clips=Path('unused'))
    job = dict(clip='animation', treatment='local', repeat=0, order=['baseline', 'local'])
    with patch.object(bench, 'pair', side_effect=fake_pair):
        row = confirm.collect_pair(args, job, 0)
    for name, data in [('plan.json', [job]), ('pairs.json', [row]),
                       ('verified.json', dict(hashes_unchanged=True, pairs=1))]:
        bench.save(directory / name, data)
    return args, job, row


def edit_pair(directory, row):
    bench.save(directory / 'pairs.json', [row])
    bench.save(directory / row['directory'] / 'pair.json', row)


def corrupt(directory, row, change):
    pair = directory / row['directory']
    if change == 'missing':
        (pair / '0.csv').unlink()
    elif change == 'trace':
        (pair / '0.csv').write_text('changed')
    elif change == 'ratio':
        row['ratios']['frame_p99'] = .01
    elif change == 'outcome':
        row['valid_outcomes'] = True
    elif change == 'identity':
        row['clip'] = 'motion'
    elif change == 'hashes':
        row['hashes'] = {}
    edit_pair(directory, row)


class EvidenceTests(unittest.TestCase):
    def test_obs23_valid_guard_failure_is_retained(self):
        with tempfile.TemporaryDirectory() as root:
            args, job, row = study(Path(root))
            self.assertEqual(stats.checked_pairs(args.output), [row])
            self.assertEqual(confirm.collect_pair(args, job, 0), row)
            self.assertFalse(row['valid_outcomes'])

    def test_obs23_analysis_rejects_missing_or_edited_evidence(self):
        for change in ('missing', 'trace', 'ratio', 'outcome', 'identity', 'hashes'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as root:
                args, _, row = study(Path(root))
                corrupt(args.output, row, change)
                with self.assertRaises((ValueError, RuntimeError, OSError)):
                    stats.analyze(args.output, samples=10)

    def test_obs23_resume_rejects_missing_or_edited_evidence(self):
        for change in ('missing', 'trace', 'ratio', 'outcome', 'identity', 'hashes'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as root:
                args, job, row = study(Path(root))
                corrupt(args.output, row, change)
                with self.assertRaises((ValueError, RuntimeError, OSError)):
                    confirm.collect_pair(args, job, 0)

    def test_obs23_rehashing_a_false_summary_does_not_validate_it(self):
        with tempfile.TemporaryDirectory() as root:
            args, job, row = study(Path(root))
            path = args.output / row['directory'] / 'results.json'
            records = json.loads(path.read_text())
            records[1]['result']['frame_p99'] = .01
            bench.save(path, records)
            row['ratios']['frame_p99'] = .01
            row['hashes']['results.json'] = bench.digest(path)
            edit_pair(args.output, row)
            with self.assertRaises((ValueError, RuntimeError)):
                stats.checked_pairs(args.output)
            with self.assertRaises((ValueError, RuntimeError)):
                confirm.collect_pair(args, job, 0)

    def test_obs23_capture_job_must_match_pair_identity(self):
        with tempfile.TemporaryDirectory() as root:
            args, job, row = study(Path(root))
            path = args.output / row['directory'] / 'results.json'
            records = json.loads(path.read_text())
            records[1]['job']['clip'] = 'motion'
            bench.save(path, records)
            row['hashes']['results.json'] = bench.digest(path)
            edit_pair(args.output, row)
            with self.assertRaises((ValueError, RuntimeError)):
                stats.checked_pairs(args.output)
            with self.assertRaises((ValueError, RuntimeError)):
                confirm.collect_pair(args, job, 0)


class TimeoutTests(unittest.TestCase):
    def test_err3_timeout_retains_diagnostics_and_cannot_be_resumed(self):
        with tempfile.TemporaryDirectory() as root:
            args = SimpleNamespace(output=Path(root), build=Path('unused'), clips=Path('unused'))
            job = dict(clip='animation', treatment='local', repeat=0, order=['baseline', 'local'])
            timeout = subprocess.TimeoutExpired('profile_pipeline', 150,
                                                output=b'partial\xff', stderr=b'diagnostic')
            with patch.object(bench.subprocess, 'run', side_effect=timeout), redirect_stdout(StringIO()):
                with self.assertRaises(RuntimeError):
                    confirm.collect_pair(args, job, 0)
            directory = args.output / 'pair-0000'
            rows = json.loads((directory / 'results.json').read_text())
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['failure'], 'timeout')
            self.assertEqual(rows[0]['timeout_seconds'], 150)
            self.assertEqual(rows[0]['stderr'], 'diagnostic')
            self.assertIn('partial', rows[0]['stdout'])
            self.assertTrue(rows[0]['command'])
            self.assertEqual(rows[0]['environment']['UP_PROFILE_ADAPTIVE'], '0')
            self.assertNotEqual(rows[0]['returncode'], 0)
            self.assertFalse((directory / 'pair.json').exists())
            with self.assertRaisesRegex(RuntimeError, 'incomplete pair'):
                confirm.collect_pair(args, job, 0)
            bench.save(args.output / 'plan.json', [job])
            bench.save(args.output / 'pairs.json', [])
            bench.save(args.output / 'verified.json', dict(hashes_unchanged=True))
            with self.assertRaises((ValueError, RuntimeError)):
                stats.analyze(args.output, samples=10)


class CaptureFailureTests(unittest.TestCase):
    def check_incomplete(self, args, job):
        self.assertFalse((args.output / 'pair-0000' / 'pair.json').exists())
        with self.assertRaisesRegex(RuntimeError, 'incomplete pair'):
            confirm.collect_pair(args, job, 0)
        bench.save(args.output / 'plan.json', [job])
        bench.save(args.output / 'pairs.json', [])
        bench.save(args.output / 'verified.json', dict(hashes_unchanged=True))
        with self.assertRaises((ValueError, RuntimeError)):
            stats.analyze(args.output, samples=10)

    def failed_capture(self, root, kind):
        args = SimpleNamespace(output=Path(root), build=Path('unused'), clips=Path('unused'))
        job = dict(clip='animation', treatment='local', repeat=0, order=['baseline', 'local'])
        stdout = 'invalid JSON' if kind == 'json' else json.dumps(
            dict.fromkeys(bench.METRICS, 1.0) | {'adaptive_outcome': 'fixed'})

        def execute(*_args, **_kwargs):
            if kind == 'launch':
                raise FileNotFoundError(2, 'missing profiler', 'unused/profile_pipeline')
            if kind == 'trace':
                (args.output / 'pair-0000' / '0.csv').write_text('selected_workers\ninvalid\n')
            return subprocess.CompletedProcess([], 0, stdout, 'capture diagnostic')

        with patch.object(bench.subprocess, 'run', side_effect=execute), redirect_stdout(StringIO()):
            with self.assertRaises(RuntimeError):
                confirm.collect_pair(args, job, 0)
        rows = json.loads((args.output / 'pair-0000' / 'results.json').read_text())
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['command'])
        self.assertEqual(rows[0]['environment']['UP_PROFILE_ADAPTIVE'], '0')
        self.assertTrue(rows[0]['error'])
        self.check_incomplete(args, job)
        return rows[0], stdout

    def test_err4_launch_failure_retains_attempt(self):
        with tempfile.TemporaryDirectory() as root:
            row, _ = self.failed_capture(root, 'launch')
            self.assertEqual(row['failure'], 'launch')
            self.assertNotEqual(row['returncode'], 0)
            self.assertIn('missing profiler', row['error'])

    def test_err4_output_failures_retain_process_diagnostics(self):
        for kind in ('json', 'missing-trace', 'trace'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as root:
                row, stdout = self.failed_capture(root, kind)
                self.assertEqual(row['failure'], 'output-parse')
                self.assertEqual(row['returncode'], 0)
                self.assertEqual(row['stdout'], stdout)
                self.assertEqual(row['stderr'], 'capture diagnostic')

    def test_err4_raw_output_is_saved_before_parsing(self):
        with tempfile.TemporaryDirectory() as root:
            args = SimpleNamespace(output=Path(root), build=Path('unused'), clips=Path('unused'))
            result = dict.fromkeys(bench.METRICS, 1.0) | {'adaptive_outcome': 'fixed'}
            process = subprocess.CompletedProcess([], 0, json.dumps(result), 'diagnostic')

            def summary(*_args):
                raw = json.loads((args.output / 'results.json').read_text())[0]
                self.assertEqual(raw['stdout'], process.stdout)
                self.assertEqual(raw['stderr'], process.stderr)
                return {}

            with patch.object(bench.subprocess, 'run', return_value=process), \
                    patch.object(bench, 'trace_summary', side_effect=summary), redirect_stdout(StringIO()):
                row = bench.checked_capture(args, bench.settings('animation', 'baseline'), [])
            self.assertEqual(row['result'], result)


if __name__ == '__main__':
    unittest.main()
