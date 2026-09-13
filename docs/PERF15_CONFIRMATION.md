# PERF-15 statistical confirmation protocol

The user replaced the scope below with [ten pairs per option and clip](PERF15_TEN_PAIRS.md).
That bounded measurement and analysis are complete; the linked report contains
the final results and disposition.
The 1,320-execution plan was stopped; its exact original protocol is archived
with the [retained evidence](benchmarks/perf15-reduced/README.md). This document
keeps the original design for provenance, not as the current execution budget.

This follow-up was requested after seeing the pilot. The user lowered the
review threshold from 10% to gains strictly greater than 5%, retained the 5%
regression guard, and requested at least 100 repeats. Pilot evidence remains
separate. It is not pooled into confirmation estimates or relabeled as passing.

## Sampling

The main study uses 100 matched pairs
per workload for local USM placement (B) and experimental adaptive tuning (D),
compared with the fixed automatic USM reference. The three existing clips,
90-second captures, 30 fps pacing, output geometry, pixels, binaries and
worker settings are identical to the pilot. Each pair is two separate process
invocations. Frame samples within a process are not independent repetitions.

Candidate selection is explicit: local placement and the new adaptive policy
are the two main proposals. Fixed-four-worker and legacy-adaptive measurements
remain pilot results, without new statistical claims. A comparison of the new
adaptive policy with the fixed reference does not prove it beats legacy adaptive.

A seeded plan shuffles workload/treatment pairs within each repetition and
randomizes baseline/candidate order within each pair. A duplicate-reference
pair for each workload appears every fifth repetition (20 controls per clip).
This totals 660 pairs, 1,320 runs and about 33 hours. Capture all prescribed
candidate pairs even after metric failures. Stop only
for process/capture failure or changed sources; retain partial evidence.
No outlier exclusion, favorable-pair replacement or significance-based stopping.

Do not run builds, analyzers, other benchmarks or analysis during captures.
Keep desktop and host scheduling/power settings unchanged. Record command,
environment, wall-clock pair times, load averages, raw traces, process output,
source/input/binary hashes and per-pair evidence hashes. Resume only after
complete pairs with the same source/input/plan manifest. Incomplete captures
need explicit investigation and remain recorded rather than overwritten.

## Estimates and decisions

For each candidate, workload and metric, summarize all matched ratios
(candidate/reference): geometric mean, median, range, chronological quarter
estimates and count of individual ratios exceeding 1.05. Primary latency
endpoint is each run's full-capture processing p99; secondary metrics are
processing mean, p95 and process CPU mean. A p99 of all pooled frames is a
different quantity and will not replace run-level paired estimates.

Use a circular block bootstrap of chronological paired log ratios, 100,000
resamples per block length. Report lengths 1, 5, 10 and 20 and the envelope of
their confidence intervals. Length 1 is an independence sensitivity comparison;
the larger lengths preserve local dependence. Use Bonferroni-adjusted,
two-sided percentile intervals over every planned candidate/workload/metric
estimate plus duplicate-control estimates. Report lag correlations and
chronological segments. These are approximate intervals under a stationary,
weakly dependent run sequence, not guaranteed confidence under arbitrary
host drift. Mark results inconclusive if 25-pair chronological segments include
both a ratio below 0.95 and one above 1, or if absolute lag-20 correlation exceeds
2/sqrt(number of pairs). These conservative screening rules do not prove
stationarity when passed. Do not select a favorable block length after seeing outcomes.

A statistically supported gain above 5% needs the whole adjusted interval
below 0.95. Flag such gains in any measured metric for user review. This does
not automatically qualify a latency policy. Qualification retains the original
per-pair 5% regression guard on every validation workload and requires a p99
gain on at least one workload, matching pixels, valid adaptive outcomes and
complete planned repeats. Also show aggregate uncertainty relative to 1.05;
statistical average gains cannot hide observed per-run guard failures.
Duplicate controls diagnose measurement variation; a baseline control whose
adjusted interval excludes 1 makes corresponding candidate claims inconclusive.

The new adaptive policy's internal 10% acceptance threshold remains unchanged:
this follow-up lowers the external review threshold, not measured controller
code. No default or runtime policy changes follow automatically.

## Limits and statistical references

Repeated 90-second processes do not establish uninterrupted three- or four-hour
playback behavior. Results concern processing of these clips on this host;
they do not measure decode-to-screen latency, energy, or all video formats.
The controller's 64-frame internal p99 score is its maximum sample; the external
2,700-frame p99 is a ranked full-run percentile. Nearby worker searches can
miss distant optima. CPU placement is USM-only; scaler workers still span the
original pinned set.

The need to account for dependent measurements follows
[NIST's discussion of uncertainty under autocorrelation](https://www.nist.gov/publications/calculation-uncertainty-mean-autocorrelated-measurements).
Block resampling follows the approach described in the
[R boot time-series documentation](https://stat.ethz.ch/R-manual/R-devel/library/boot/html/tsboot.html).
Block sizes, multiplicity adjustment and review criteria above are this
experiment's declared choices, not claims that those sources guarantee this
study's coverage or power.
