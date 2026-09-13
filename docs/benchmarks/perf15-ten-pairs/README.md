# PERF-15 completed ten-pair evidence

The [final report](../../PERF15_TEN_PAIRS.md) records the outcome: local USM
placement saves processing CPU but increases p99, and experimental adaptive
tuning establishes no latency gain above 5%. Defaults remain unchanged.

This archive contains the 15-pair continuation. Combine it with the 51 complete
pairs in the [stopped-batch archive](../perf15-reduced/README.md): ten pairs per
B/D option and clip, plus two duplicate-control pairs per clip. The unfinished
pair in the stopped batch is excluded, with its files retained.

- `captures.tar.gz`: all continuation captures, commands, traces, outcomes and
  completed plans, preserved before later Python reporting changes.
- `measured-sources.tar.gz`: exact sources and profiling executables checked
  against the continuation manifest before archival; YUV inputs are identified
  by hash and reused from the existing clip set, not included in this archive.
- `manifest.json`, plans, paired results and `verified.json`: frozen capture
  provenance, original-group references and completed measurement counts.
- `protocol.md`: the ten-pair protocol frozen before continuation captures;
  later results are in the linked final report.
- `analysis.json`, `results.md`, `paired-variation.svg` and `.png`: final
  statistics and chronological paired changes. `local` means B (local USM),
  `latency` means D (adaptive experiment), and `duplicate` means controls.
  CPU refers to per-frame processing CPU time, not whole-player CPU usage.
  Controls have two pairs per clip and descriptive estimates only.
- `trace-verification.json`, `trace-diagnostics.json`: independent validation
  of all 132 completed traces and exploratory slow-tail stage diagnostics.
  These derived files were produced after capture archival.
- `analysis-sources.tar.gz`: repaired replay package (revision 2), containing
  the original post-measurement analysis files plus the omitted
  `scripts/bench_playback_policies.py` from `measured-sources.tar.gz`.
  Original members are unchanged; this deliberately differs from the measured
  source snapshot and does not include later generic-runner fixes.
- `analysis-sources-v1.tar.gz`: unchanged original analysis package, retained
  for provenance. It omits a transitive import and cannot replay by itself.
- `analyze_ten_pairs.py`, `plot_ten_pairs.py`, `verify_ten_pairs.py`,
  `ten_pairs_extension.py`, `archive_ten_pairs.py`: readable copies of bounded
  capture, archival, verification and analysis helpers.
- `validation/`: pre-continuation full-suite log, budget/OBS-22 red and green
  regression logs, complexity, raw-trace verification and final report checks.
- `sha256.json`: hashes of every archive file except the hash index itself.

Source commit remains `0f6cee0`; measured and analysis changes were uncommitted.
Historical manifests are not rewritten to match later documentation or Python
fixes. The earlier pilot's pixel comparisons and sanitizer results are in the
[pilot archive](../perf15-latency/README.md).

BUILD-46 repaired only the replay package dependency closure. No capture,
measurement manifest, measured source, executable or reported statistic changed.
The permanent normal-suite archive test extracts the package into an empty
directory and checks imports with no checkout on Python's search path.

## Reproduce analysis without playback

Use a separate empty directory. Extract the stopped `captures.tar.gz` under
`build/perf15/confirmation` and this archive's `captures.tar.gz` under
`build/perf15/ten-pairs`. Extract `analysis-sources.tar.gz` at that directory's
root; it contains `scripts/` dependencies and `build/perf15/` helpers. Python
requires SciPy (the measured analysis version is recorded in `analysis.json`)
and matplotlib for the optional plot. Then run:

```bash
python3 build/perf15/verify_ten_pairs.py
python3 build/perf15/analyze_ten_pairs.py build/perf15/confirmation build/perf15/ten-pairs rebuilt-analysis
python3 build/perf15/plot_ten_pairs.py rebuilt-analysis/analysis.json rebuilt-analysis/paired-variation
```

These commands read saved evidence and launch no video processes. The output
directory must not already exist. Binary/source integrity during measurement
is recorded separately by the capture manifests and verification records.
