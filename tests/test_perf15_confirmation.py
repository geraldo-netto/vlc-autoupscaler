#!/usr/bin/env python3
"""PERF-15: repeat counts, evidence retention and run-level uncertainty."""
import json
from contextlib import redirect_stdout
from io import StringIO
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import bench_perf15_confirm as confirm
import perf15_statistics as stats


def fixture_args(directory):
    return SimpleNamespace(output=Path(directory), repeats=100,
                           treatments=['local', 'latency'], seed=20260916)


def fake_pair(args, **job):
    job.pop('rows')
    (args.output/'0.csv').write_text('frame,total\n0,1\n')
    return dict(**job, valid_outcomes=False, ratios={'frame_p99': 1.2})


class CaptureTests(unittest.TestCase):
    def test_perf15_default_caps_total_executions_at_100(self):
        self.assertEqual(self.simulated_cli(), 50)

    def test_explicit_ten_repeats_is_120_candidate_executions_plus_12_controls(self):
        self.assertEqual(self.simulated_cli('--repeats', '10'), 66)

    def test_explicit_budget_includes_controls_and_cannot_split_pairs(self):
        self.assertEqual(self.simulated_cli('--executions', '12'), 6)
        with self.assertRaises(SystemExit):
            self.simulated_cli('--executions', '101')

    def test_ten_pair_extension_reuses_51_pairs_and_adds_only_15(self):
        jobs = confirm.plan(10, ['local', 'latency'], 20260916)
        remaining = confirm.pending_jobs(jobs, jobs[:51])
        self.assertEqual(len(remaining), 15)
        self.assertFalse(any(row['treatment'] == 'duplicate' for row in remaining))
        self.assertEqual(jobs[:51]+remaining, jobs)

    def test_extension_rejects_wrong_order_or_excess_evidence(self):
        jobs = confirm.plan(10, ['local', 'latency'], 20260916)
        with self.assertRaises(ValueError):
            confirm.pending_jobs(jobs, list(reversed(jobs[:2])))
        with self.assertRaises(ValueError):
            confirm.pending_jobs(jobs[:2], jobs[:3])

    def simulated_cli(self, *options):
        with tempfile.TemporaryDirectory() as directory:
            argv = ['bench_perf15_confirm.py', 'build', 'clips', directory, 'protocol', *options]
            with patch.object(sys, 'argv', argv), redirect_stdout(StringIO()), \
                    patch.object(confirm, 'initialize', return_value={}), \
                    patch.object(confirm, 'manifest', return_value={}), \
                    patch.object(confirm, 'collect_pair', return_value={}) as capture, \
                    patch.object(confirm, 'save'), patch.object(confirm, 'verify_evidence'):
                confirm.main()
            return capture.call_count

    def test_full_plan_has_100_pairs_per_candidate_and_clip(self):
        jobs = confirm.plan(100, ['local', 'latency'], 20260916)
        self.assertEqual(len(jobs), 660)
        for clip in confirm.bench.CLIPS:
            self.check_plan_clip(jobs, clip)
        self.assertEqual(jobs, confirm.plan(100, ['local', 'latency'], 20260916))
        self.assertNotEqual(jobs, confirm.plan(100, ['local', 'latency'], 20260917))

    def check_plan_clip(self, jobs, clip):
        for treatment in ('local', 'latency', 'duplicate'):
            subset = [row for row in jobs if (row['clip'], row['treatment']) == (clip, treatment)]
            count = 20 if treatment == 'duplicate' else 100
            self.assertEqual(len(subset), count)
            self.assertEqual(len({row['repeat'] for row in subset}), count)
            self.assertEqual({tuple(row['order']) for row in subset},
                             {('baseline', treatment), (treatment, 'baseline')})

    def test_resume_retains_failed_metrics_and_does_not_repeat_completed_pairs(self):
        with tempfile.TemporaryDirectory() as directory:
            args = fixture_args(directory)
            args.build, args.clips = Path('unused-build'), Path('unused-clips')
            jobs = confirm.plan(1, ['local'], 1)[:2]
            with patch.object(confirm, 'plan', return_value=jobs), \
                    patch.object(confirm, 'manifest', return_value={'fixed': True}), \
                    patch.object(confirm.bench, 'pair', side_effect=fake_pair) as capture:
                confirm.compare(args)
                first = (args.output/'pairs.json').read_bytes()
                confirm.compare(args)
                self.assertEqual(capture.call_count, 2)
                self.assertEqual((args.output/'pairs.json').read_bytes(), first)
                self.assertTrue(all(row['ratios']['frame_p99'] == 1.2 for row in json.loads(first)))
                self.assertTrue(json.loads((args.output/'verified.json').read_text())['hashes_unchanged'])

    def test_incomplete_pair_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            args = fixture_args(directory)
            partial = args.output/'pair-0000'
            partial.mkdir()
            trace = partial/'0.csv'
            trace.write_text('partial evidence')
            with self.assertRaisesRegex(RuntimeError, 'incomplete pair'):
                confirm.collect_pair(args, {}, 0)
            self.assertEqual(trace.read_text(), 'partial evidence')

    def test_resume_rejects_changed_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            args = fixture_args(directory)
            confirm.save(args.output/'manifest.json', {'fixed': True})
            with patch.object(confirm, 'manifest', return_value={'fixed': False}), \
                    self.assertRaisesRegex(RuntimeError, 'cannot resume'):
                confirm.initialize(args, [])

    def test_evidence_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            args = fixture_args(directory)
            args.build, args.clips = Path('unused-build'), Path('unused-clips')
            job = confirm.plan(1, ['local'], 1)[0]
            with patch.object(confirm.bench, 'pair', side_effect=fake_pair):
                result = confirm.collect_pair(args, job, 0)
            (args.output/result['directory']/'0.csv').write_text('modified')
            with self.assertRaisesRegex(RuntimeError, 'evidence changed'):
                confirm.verify_evidence(args, [result])


class StatisticsTests(unittest.TestCase):
    def test_constant_ratios_produce_exact_interval(self):
        row = stats.estimate([.9]*100, 36, samples=100)
        self.assertAlmostEqual(row['ratio'], .9)
        self.assertEqual(row['pairs'], 100)
        for bound in row['interval']:
            self.assertAlmostEqual(bound, .9)
        self.assertEqual(row['individual_guard_failures'], 0)

    def test_multiplicity_widens_interval(self):
        values = [.8, .9, 1, 1.1, 1.2]*20
        raw = stats.estimate(values, 1, samples=500)
        adjusted = stats.estimate(values, 36, samples=500)
        self.assertLessEqual(adjusted['interval'][0], raw['interval'][0])
        self.assertGreaterEqual(adjusted['interval'][1], raw['interval'][1])
        self.assertEqual(adjusted['individual_guard_failures'], 40)

    def test_blocks_preserve_clustered_variation(self):
        values = stats.log_values([.7]*50 + [1.3]*50)
        independent = stats.interval(values, 1, 1000, 5, .05)
        blocked = stats.interval(values, 10, 1000, 5, .05)
        self.assertGreater(blocked[1]-blocked[0], 2*(independent[1]-independent[0]))
        self.assertGreater(stats.serial_correlation(values, 1), .9)

    def test_reciprocal_pairs_use_log_scale(self):
        row = stats.estimate([.5, 2]*50, 1, samples=100)
        self.assertAlmostEqual(row['ratio'], 1)
        self.assertEqual(row['pairs'], 100)

    def test_invalid_and_insufficient_values_do_not_claim_intervals(self):
        for values in ([], [0], [-1], [math.nan], [math.inf]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                stats.estimate(values, 1, samples=100)
        row = stats.estimate([.9]*3, 1, samples=100)
        self.assertIsNone(row['interval'])

    def test_obs22_short_study_retains_guard_diagnostics(self):
        value = stats.estimate([.9]*9+[1.2], 24, samples=100)
        self.assertIsNone(value['interval'])
        self.assertEqual(value['individual_guard_failures'], 1)
        row = dict(clip='motion', treatment='local', pairs=10, valid_outcomes=True,
                   metrics={key: dict(value) for key in confirm.bench.METRICS})
        review = stats.candidate_review([row], 'local', {'motion': True})
        self.assertFalse(review['individual_guards_pass'])
        self.assertFalse(review['qualifies'])

    def test_obs22_missing_controls_prevent_promotion_without_exception(self):
        value = dict(interval=[.8, .9], individual_guard_failures=0, pairs=100)
        row = dict(clip='motion', treatment='local', pairs=100, valid_outcomes=True,
                   metrics={key: dict(value) for key in confirm.bench.METRICS})
        review = stats.candidate_review([row], 'local', {})
        self.assertFalse(review['valid_outcomes_and_controls'])
        self.assertFalse(review['qualifies'])

    def test_review_requires_more_than_five_percent_gain(self):
        self.assertFalse(stats.gain_supported({'interval': [.90, .95]}))
        self.assertTrue(stats.gain_supported({'interval': [.90, .949]}))
        self.assertFalse(stats.gain_supported({'interval': [.80, 1.1]}))

    def test_average_gain_cannot_hide_failed_guard_or_capture(self):
        value = dict(interval=[.90, .94], individual_guard_failures=0, pairs=100)
        row = dict(clip='motion', treatment='local', pairs=100, valid_outcomes=True,
                   metrics={key: dict(value) for key in confirm.bench.METRICS})
        self.assertTrue(stats.candidate_review([row], 'local', {'motion': True})['qualifies'])
        row['metrics']['frame_mean']['individual_guard_failures'] = 1
        self.assertFalse(stats.candidate_review([row], 'local', {'motion': True})['qualifies'])
        row['metrics']['frame_mean']['individual_guard_failures'] = 0
        row['valid_outcomes'] = False
        self.assertFalse(stats.candidate_review([row], 'local', {'motion': True})['qualifies'])
        row['valid_outcomes'] = True
        self.assertFalse(stats.candidate_review([row], 'local', {'motion': False})['qualifies'])

    def test_duplicate_control_bias_is_not_accepted(self):
        centered = dict(metrics={'frame_p99': {'interval': [.9, 1.1]}})
        biased = dict(metrics={'frame_p99': {'interval': [.8, .9]}})
        self.assertTrue(stats.control_consistent(centered))
        self.assertFalse(stats.control_consistent(biased))

    def test_drift_and_persistent_dependence_require_review(self):
        value = dict(pairs=100, chronological_quarter_ratios=[.8, .8, 1.02, 1.02],
                     serial_correlation={'20': .6})
        self.assertEqual(len(stats.stability_flags(value)), 2)


if __name__ == '__main__':
    unittest.main()
