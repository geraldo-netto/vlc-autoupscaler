"""REV-30: current and historical profiler activity evidence stays verifiable."""
import csv
import json
import random
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import bench_perf15 as bench
import bench_perf15_confirm as confirm
import perf15_evidence as evidence
import perf15_statistics as stats
from perf15_fixture import fake_pair, write_capture


def read_trace(path):
    with path.open() as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames, list(reader)


def write_trace(path, fields, rows):
    with path.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def current_trace(path, adaptive, outcome):
    fields, rows = read_trace(path)
    for row in rows:
        active = adaptive and outcome != 'disabled' and row['skipped'] == '0'
        if outcome == 'fallback' and int(row['frame']) >= 59:
            active = False
        row['adaptive_active'] = str(int(active))
    return fields + ['adaptive_active'], rows


def current_pair(args, **job):
    pair = fake_pair(args, **job)
    path = args.output / 'results.json'
    records = json.loads(path.read_text())
    for record in records:
        trace = args.output / record['trace']
        adaptive = record['job']['adaptive']
        fields, rows = current_trace(trace, adaptive, record['result']['adaptive_outcome'])
        write_trace(trace, fields, rows)
        record['summary'] = bench.trace_summary(trace, adaptive)
    bench.save(path, records)
    return pair


class ActivityEvidenceTests(unittest.TestCase):
    def test_rev30_current_pairs_capture_resume_and_analyze(self):
        for treatment in ('adaptive', 'latency'):
            with self.subTest(treatment=treatment), tempfile.TemporaryDirectory() as root:
                args = SimpleNamespace(output=Path(root), build=Path('unused'), clips=Path('unused'))
                job = dict(clip='animation', treatment=treatment, repeat=0, order=['baseline', treatment])
                with patch.object(bench, 'pair', side_effect=current_pair):
                    row = confirm.collect_pair(args, job, 0)
                for name, data in [('plan.json', [job]), ('pairs.json', [row]),
                                   ('verified.json', dict(hashes_unchanged=True, pairs=1))]:
                    bench.save(args.output / name, data)
                self.assertEqual(confirm.collect_pair(args, job, 0), row)
                self.assertEqual(stats.checked_pairs(args.output), [row])

    def capture(self, directory, treatment, outcome, current=True):
        record = write_capture(directory, 'animation', treatment, 0, 1.0, outcome)
        path = directory / record['trace']
        if current:
            fields, rows = current_trace(path, record['job']['adaptive'], outcome)
            write_trace(path, fields, rows)
        record['summary'] = bench.trace_summary(path, record['job']['adaptive'])
        return record, path

    def test_rev30_current_and_historical_outcomes(self):
        cases = [('local', 'fixed'), ('local', 'sharpness-bypass')]
        cases += [(treatment, outcome) for treatment in ('adaptive', 'latency')
                  for outcome in ('searching', 'settled', 'fallback', 'disabled', 'sharpness-bypass')]
        for current in (False, True):
            for treatment, outcome in cases:
                with self.subTest(current=current, treatment=treatment, outcome=outcome), \
                        tempfile.TemporaryDirectory() as root:
                    record, path = self.capture(Path(root), treatment, outcome, current)
                    self.assertEqual(evidence.verify_trace(record, path), dict.fromkeys(bench.METRICS, 1.0))

    def reject_edit(self, treatment, outcome, edit, message='activity'):
        with tempfile.TemporaryDirectory() as root:
            record, path = self.capture(Path(root), treatment, outcome)
            fields, rows = read_trace(path)
            edit(rows)
            write_trace(path, fields, rows)
            record['summary'] = bench.trace_summary(path, record['job']['adaptive'])
            with self.assertRaisesRegex(ValueError, message):
                evidence.verify_trace(record, path)

    def test_rev30_rejects_noncanonical_activity_values(self):
        values = ['', '00', '01', '+1', '-0', '1.0', 'true', ' 1', '1 ', 'nan', None]
        values += [str(value) for value in range(-4, 5) if value not in (0, 1)]
        values += [str(random.Random(seed).randrange(2, 2**64)) for seed in range(32)]
        for value in values:
            with self.subTest(value=value):
                self.reject_edit('adaptive', 'searching',
                                 lambda rows: rows[0].update(adaptive_active=value))

    def test_rev30_rejects_activity_conflicting_with_mode_or_outcome(self):
        cases = [('local', 'fixed', 0, '1'), ('latency', 'disabled', 0, '1'),
                 ('latency', 'sharpness-bypass', 59, '1'),
                 ('latency', 'fallback', -1, '1'),
                 ('latency', 'searching', -1, '0'), ('adaptive', 'settled', -1, '0')]
        for treatment, outcome, frame, value in cases:
            with self.subTest(treatment=treatment, outcome=outcome, frame=frame):
                self.reject_edit(treatment, outcome,
                                 lambda rows: rows[frame].update(adaptive_active=value))

    def test_rev30_stopped_activity_cannot_restart_or_change_state(self):
        self.reject_edit('adaptive', 'searching', lambda rows: rows[10].update(adaptive_active='0'))
        self.reject_edit('adaptive', 'fallback', lambda rows: rows[60].update(phase='1'))
        self.reject_edit('adaptive', 'fallback', lambda rows: rows[60].update(changed='1'))

    def test_rev30_stopped_tuner_can_retain_settled_phase(self):
        with tempfile.TemporaryDirectory() as root:
            record, path = self.capture(Path(root), 'latency', 'settled')
            fields, rows = read_trace(path)
            for row in rows[100:]:
                row['adaptive_active'] = '0'
            write_trace(path, fields, rows)
            record['result']['adaptive_outcome'] = 'fallback'
            record['summary'] = bench.trace_summary(path, True)
            self.assertEqual(record['summary']['settled_frames'], 34)
            self.assertEqual(evidence.verify_trace(record, path)['frame_mean'], 1.0)

    def test_rev30_unknown_or_incomplete_schemas_still_fail(self):
        with tempfile.TemporaryDirectory() as root:
            _, path = self.capture(Path(root), 'local', 'fixed')
            fields, rows = read_trace(path)
            for header in (fields + ['unknown'], fields[::-1], fields[:-2]):
                with self.subTest(header=header):
                    path.write_text(','.join(header) + '\n')
                    with self.assertRaisesRegex(ValueError, 'schema'):
                        evidence.trace_rows(path)
            rows[0].pop('adaptive_active')
            write_trace(path, fields, rows)
            with self.assertRaisesRegex(ValueError, 'activity'):
                evidence.trace_rows(path)


class ProtocolBoundaryTests(unittest.TestCase):
    def test_rev30_evidence_paths_reject_traversal_and_symlinks(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            (directory / 'alias').symlink_to(directory / 'trace.csv')
            for name in (None, '', '.', '..', '../trace.csv', '/tmp/trace.csv', 'alias'):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    evidence.child(directory, name)

    def test_rev30_invocation_shape_and_pair_index_stay_strict(self):
        for command in (None, [], ['profile'] * 10, ['profile'] * 12, [0] * 11):
            with self.subTest(command=command), self.assertRaises(ValueError):
                evidence.check_command(command)
        for row in (dict(index=1, directory='pair-0000'), dict(index=0, directory='pair-0001')):
            with self.subTest(row=row), self.assertRaises(ValueError):
                evidence.verify_identity(row, None, 0)

    def test_rev30_historical_traces_keep_transition_guards(self):
        cases = [('1', '1', '0', '0', True), ('0', '2', '0', '0', True),
                 ('0', '0', '1', '0', True), ('0', '1', '0', '0', False)]
        for first, last, before, after, adaptive in cases:
            rows = [dict(phase=first, skipped=before, changed='0'),
                    dict(phase=last, skipped=after, changed='0')]
            with self.subTest(case=(first, last, before, after, adaptive)), self.assertRaises(ValueError):
                evidence.verify_trace_transitions(rows, adaptive)

    def test_rev30_historical_terminal_state_keeps_consistency_guards(self):
        cases = [('settled', '1', 1), ('disabled', '1', 0), ('searching', '0', 1)]
        for outcome, phase, settled in cases:
            result = dict(adaptive_outcome=outcome, first_settled_frame=settled)
            rows = [dict(phase=phase, changed='0')]
            with self.subTest(outcome=outcome), self.assertRaises(ValueError):
                evidence.verify_terminal_state(result, rows)


if __name__ == '__main__':
    unittest.main()
