"""PERF-15 fixed-count randomized confirmation; preserve every capture."""
import argparse
import fcntl
import json
from pathlib import Path
import random
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, str(Path.cwd() / 'scripts'))
import bench_perf15 as bench
from perf15_evidence import validate_pair


def save(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    bench.save(temporary, data)
    temporary.replace(path)


def plan(repeats, treatments, seed):
    generator = random.Random(seed)
    jobs = []
    for repeat in range(repeats):
        names = list(treatments) + (['duplicate'] if repeat % 5 == 0 else [])
        cycle = [(clip, name) for clip in bench.CLIPS for name in names]
        generator.shuffle(cycle)
        for clip, treatment in cycle:
            order = ['baseline', treatment]
            generator.shuffle(order)
            jobs.append(dict(clip=clip, treatment=treatment, repeat=repeat, order=order))
    return jobs


def planned_jobs(args):
    if args.repeats is not None:
        return plan(args.repeats, args.treatments, args.seed)
    pairs = args.executions//2
    per_cycle = len(bench.CLIPS)*len(args.treatments)
    repeats = (pairs+per_cycle-1)//per_cycle
    return plan(repeats, args.treatments, args.seed)[:pairs]


def pending_jobs(jobs, completed):
    if len(completed) > len(jobs):
        raise ValueError('completed evidence exceeds requested plan')
    for job, row in zip(jobs, completed):
        if any(row[key] != value for key, value in job.items()):
            raise ValueError('completed evidence differs from the requested plan prefix')
    return jobs[len(completed):]


def manifest(args, jobs):
    value = bench.manifest(args)
    value['confirmation'] = dict(plan=jobs, protocol=bench.digest(args.protocol),
                                  runner=bench.digest(Path(__file__)),
                                  repetitions=args.repeats, seed=args.seed)
    return value


def initialize(args, jobs):
    current = manifest(args, jobs)
    path = args.output / 'manifest.json'
    if path.exists():
        if json.loads(path.read_text()) != current:
            raise RuntimeError('sources, inputs or plan changed; cannot resume')
    else:
        save(path, current)
        save(args.output / 'plan.json', jobs)
    return current


def collect_pair(args, job, index):
    directory = args.output / ('pair-%04d' % index)
    completed = directory / 'pair.json'
    if completed.exists():
        result = json.loads(completed.read_text())
        validate_pair(args.output, result, job, index)
        return result
    if directory.exists():
        raise RuntimeError('incomplete pair retained; inspect before starting a separate study')
    directory.mkdir()
    pair_args = SimpleNamespace(build=args.build, clips=args.clips, output=directory)
    rows = []
    started = time.time()
    result = bench.pair(pair_args, **job, rows=rows)
    result.update(index=index, directory=directory.name, started=started, finished=time.time())
    result['hashes'] = {path.name: bench.digest(path) for path in directory.iterdir() if path.is_file()}
    save(completed, result)
    validate_pair(args.output, result, job, index)
    return result


def verify_evidence(args, rows):
    for row in rows:
        validate_pair(args.output, row)


def compare(args):
    jobs = planned_jobs(args)
    before = initialize(args, jobs)
    rows = []
    for index, job in enumerate(jobs):
        rows.append(collect_pair(args, job, index))
        save(args.output / 'pairs.json', rows)
        print('completed', len(rows), '/', len(jobs), flush=True)
    verify_evidence(args, rows)
    if before != manifest(args, jobs):
        raise RuntimeError('measured sources or inputs changed; reject study')
    save(args.output / 'verified.json', dict(hashes_unchanged=True, pairs=len(rows)))


def validate_arguments(parser, args):
    if len(args.treatments) != len(set(args.treatments)):
        parser.error('require unique treatments')
    if args.repeats is not None:
        if args.repeats < 1:
            parser.error('repetitions must be positive')
    elif args.executions < 2 or args.executions % 2:
        parser.error('execution budget must be positive and even to keep complete pairs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'clips', 'output', 'protocol'):
        parser.add_argument(name, type=Path)
    budget = parser.add_mutually_exclusive_group()
    budget.add_argument('--executions', type=int, default=100,
                        help='total executions including references and controls (default: 100)')
    budget.add_argument('--repeats', type=int,
                        help='explicit matched pairs per candidate and clip; controls are additional')
    parser.add_argument('--seed', type=int, default=20260916)
    parser.add_argument('--treatments', nargs='+', choices=bench.TREATMENTS[1:],
                        default=['local', 'latency'])
    args = parser.parse_args()
    validate_arguments(parser, args)
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / '.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        compare(args)


if __name__ == '__main__':
    main()
