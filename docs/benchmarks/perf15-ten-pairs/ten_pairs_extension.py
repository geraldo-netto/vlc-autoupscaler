"""Complete the user-selected ten-pair matrix using verified existing pairs."""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path.cwd()/'scripts'))
import bench_perf15 as bench
import bench_perf15_confirm as confirm


def manifest(args):
    value = bench.manifest(args)
    extras = [Path(__file__), args.protocol, args.original/'manifest.json',
              args.original/'pairs.json', args.original/'stopped-verification.json']
    value['continuation'] = {str(path): bench.digest(path) for path in extras}
    return value


def verify_compatible(args, current):
    prior = json.loads((args.original/'manifest.json').read_text())
    for name, expected in prior['hashes'].items():
        file = Path(name)
        if file.suffix in ('.c', '.h', '.yuv') or file.name.startswith('profile_pipeline'):
            if current['hashes'].get(name) != expected:
                raise RuntimeError('timed code, binary or input changed since retained captures')
    verified = json.loads((args.original/'stopped-verification.json').read_text())
    if not verified['hashes_unchanged']:
        raise RuntimeError('original partial evidence is unverified')


def run(args):
    current = manifest(args)
    verify_compatible(args, current)
    original = json.loads((args.original/'pairs.json').read_text())
    confirm.verify_evidence(SimpleNamespace(output=args.original), original)
    plan = confirm.plan(10, ['local', 'latency'], 20260916)
    pending = confirm.pending_jobs(plan, original)
    args.output.mkdir(parents=True, exist_ok=False)
    bench.save(args.output/'manifest.json', current)
    bench.save(args.output/'complete-plan.json', plan)
    bench.save(args.output/'plan.json', pending)
    rows = []
    for index, job in enumerate(pending):
        rows.append(confirm.collect_pair(args, job, index))
        bench.save(args.output/'pairs.json', rows)
        print('additional pairs',len(rows),'/',len(pending),flush=True)
    confirm.verify_evidence(args, rows)
    if manifest(args) != current:
        raise RuntimeError('continuation sources changed during capture')
    combined = [dict(row, source='original') for row in original]
    combined += [dict(row, source='extension') for row in rows]
    confirm.pending_jobs(plan, combined)
    bench.save(args.output/'combined-pairs.json', combined)
    bench.save(args.output/'verified.json', dict(hashes_unchanged=True, measurement_complete=True,
                                                paired_executions=2*len(combined), pairs=len(combined),
                                                candidate_pairs=60, control_pairs=6))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('build','clips','original','output','protocol'):
        parser.add_argument(name, type=Path)
    run(parser.parse_args())


if __name__ == '__main__':
    main()
