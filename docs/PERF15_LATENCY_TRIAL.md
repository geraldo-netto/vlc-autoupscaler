# PERF-15 latency-first trial

The user selected B (latency-first tuning on this machine) and D (one adaptive
tuning experiment). This is a bounded processing-only study. Production
defaults, launcher, audio handling, geometry and zero-copy policy stay unchanged.

## Decision rules declared before measurement

Use the existing animation, motion and live-action decoded clips on the
Ryzen 9 7945HX. Animation/motion use 1280x720 output; live action uses
1920x1080. These geometries obey the production 4x cap. All cases keep
12 scaler workers and Spline36 so scaler tile boundaries stay identical.
The fixed reference uses the automatic USM budgets (8 at 720p, 12 at 1080p),
default sharpness cutoff 3500, 20% USM, scaler pinning and zero-copy.

Compare five treatments: a duplicate reference control, fixed four-worker
USM, USM restricted to physical cores 0--7, existing adaptive USM and one
experimental adaptive revision. Each treatment has its own adjacent reference
run, with order randomized before execution. Three repetitions of 2,700 frames
at 30 fps include startup, probing, trials and retirement. The 600-frame source
sequences repeat; this tests 90-second sessions, not uninterrupted multi-hour
content or decode-to-screen latency. No timed run overlaps another benchmark,
build, analyzer or playback. No driver power or system scheduling setting changes.

Run separate all-frame pixel controls before timing. Hash every visible plane
for all 600 source frames; force the revised controller through trial worker
counts in unit tests. Hashing is disabled during timing to avoid perturbing
subsequent frames. Sources, inputs, binaries and commands are recorded.

Promotion requires at least 10% lower processing p99 on an intended workload,
with no greater than 5% mean, p95, p99 or process-CPU regression on any validation
workload. Every repeat must meet the limits; the p99 improvement must exceed
the largest relative p99 difference between duplicate-reference controls on
that workload. This conservative rule rejects unstable or inconclusive results;
three repetitions do not establish a population confidence interval.
Pixels must match in all controls. No second candidate revision or endless
retesting follows a failure in this study.

Futility stopping is declared in advance: all candidates complete the first
repetition on all three clips. A candidate violating any 5% guard is rejected
and receives no further repetitions. Duplicate-reference controls always finish
all three repetitions. A candidate cannot recover eligibility by selective
retesting; missing later pairs are explicitly marked as skipped after rejection.

The adaptive revision searches worker counts near the incumbent (half to
twice its size), requires a 10% p99 improvement against both neighboring
baselines with mean/p95 within 5%, and waits at least 1,800 settled frames
before drift-triggered exploration. Periodic rechecking remains enabled.
Allocation failures, output ownership and fallback use the existing adaptive
pool implementation. CPU cost is guarded by external measurements.

The result closes the bounded proposal by retaining a validated opt-in preset
or recording the tested policies as rejected. It makes no universal default,
multi-hour stability, energy or screen-latency claim.

## Pilot results

The pilot completed 44 timed runs (22 matched pairs), with 23 remaining
planned pairs skipped under the predeclared futility rule. Source, input and
binary hashes remained unchanged. All four candidate policies failed the
original guard, so none qualified. Nine duplicate-reference pairs completed
all three repetitions. Their largest absolute p99 differences were 64.7%
(animation), 14.3% (motion), and 32.8% (live action). Three pilot repeats do not
establish statistical confidence or prove every observed difference causal.

Each percentage below compares a candidate with its own adjacent reference;
negative means less processing time or process CPU. These are individual
observations, including every failed comparison, without outlier removal.

| Clip | Treatment | Repeat | Mean | p95 | p99 | Process CPU |
|---|---|---|---|---|---|---|
| animation | adaptive | 1 | +3.5% | +12.3% | +20.1% | +7.5% |
| live-action-540 | adaptive | 1 | -4.7% | -14.0% | -2.9% | -8.3% |
| motion | adaptive | 1 | +21.3% | +94.6% | +79.2% | +6.4% |
| animation | duplicate | 1 | +9.2% | +22.4% | +16.7% | -5.8% |
| animation | duplicate | 2 | +34.9% | +125.1% | +64.7% | +0.1% |
| animation | duplicate | 3 | -4.3% | -24.3% | -17.9% | +6.5% |
| live-action-540 | duplicate | 1 | +5.9% | +26.0% | +32.8% | +5.2% |
| live-action-540 | duplicate | 2 | -8.8% | -25.1% | -25.9% | -0.9% |
| live-action-540 | duplicate | 3 | -7.8% | -27.9% | -23.2% | -5.9% |
| motion | duplicate | 1 | -7.5% | -23.0% | -0.9% | -3.1% |
| motion | duplicate | 2 | -11.5% | -39.2% | -11.0% | -5.4% |
| motion | duplicate | 3 | +8.2% | +32.3% | +14.3% | +2.8% |
| animation | fixed4 | 1 | +5.6% | -6.8% | -16.3% | +1.7% |
| live-action-540 | fixed4 | 1 | +18.7% | +38.7% | +28.1% | -13.2% |
| motion | fixed4 | 1 | +31.7% | +120.5% | +24.4% | -9.5% |
| animation | latency | 1 | +3.7% | -5.3% | +30.7% | +8.3% |
| live-action-540 | latency | 1 | +3.7% | +4.5% | +10.9% | +3.6% |
| motion | latency | 1 | -0.9% | +24.2% | +3.0% | -5.1% |
| animation | local | 1 | -12.9% | -33.3% | -20.4% | -15.6% |
| live-action-540 | local | 1 | +4.7% | -6.1% | -2.3% | -14.1% |
| motion | local | 1 | -8.2% | -26.6% | -7.7% | -7.1% |
| motion | local | 2 | +11.3% | +82.3% | +57.2% | -11.3% |

Local USM placement reduced process CPU in its four observed pairs by
7.1% to 15.6%, but motion p99 changed from a 7.7% gain to a 57.2% regression
on repetition. This is a candidate for further measurement, not a validated
latency preset. Fixed four-worker USM saved CPU on motion/live action while
regressing their mean and tail processing times. The new adaptive controller
had higher p99 in every pilot workload pair; reduced exploration alone did
not establish lower total processing latency.

## Validation and evidence

Separate pixel controls completed 18 captures: one reference plus five
variants on each of three clips. All 15 matched comparisons had identical
per-frame visible-plane hashes across all 600 source frames. Forced-worker
unit tests also exercised the experimental controller's dispatched counts,
fallback and retirement paths.

The seven-case experimental-policy suite was added first and produced four
failures against the legacy-observer alias; all seven passed after the new
policy was implemented. This establishes new-policy behavior, not a claim
that the original policy was a behavioral bug. Existing tuner, adaptive and
both pipeline suites passed. The full warning-as-error suite, ASan/UBSan,
cppcheck, complexity, hardening, visibility and documentation checks passed
before timed captures; targeted Clang 18 TSan passed all four experimental
pipeline cases.

The later OBS-21 diagnostic regression reproduced two incorrect skip labels:
a later pair in the same repetition and an invalid adaptive outcome were
both described as an earlier-repetition 5% failure. The permanent normal-suite
test failed before the diagnostic-only fix and passed afterward. Original
raw skip labels remain archived literally; capture order and pilot verdicts
were unaffected.

[Archived evidence](benchmarks/perf15-latency/README.md) includes raw traces,
commands, JSON outcomes, plans, skipped jobs, source/input/binary manifests,
the exact measured sources and binaries, the original protocol, and validation
logs. Sources changed after the pilot for this diagnostic and follow-up tooling;
the archive preserves the original measured versions.

## User-requested statistical follow-up

After the pilot began, the user clarified that gains greater than 5% should
qualify for review instead of requiring 10%; the 5% regression guard remains.
The user then requested at least 100 repeated tests. This supersedes the
pilot's no-further-retesting scope for a separate confirmation study, without
rewriting its original rules or pooling its results into confirmation data.

The [confirmation protocol](PERF15_CONFIRMATION.md) declares run-level paired
estimates, correlation checks and multiplicity-adjusted uncertainty before
new measurements. The experimental controller's internal 10% acceptance rule
is unchanged. Production defaults, launcher and audio handling are unchanged.
Neither benchmark-only USM placement nor the experimental controller is
advertised as a shipped playback preset. The user subsequently bounded the
measurement step to [ten pairs per option and clip](PERF15_TEN_PAIRS.md), reusing
completed evidence. Measurement and analysis are complete at that final scope:
local placement saves processing CPU with worse latency, and the experimental
controller establishes no latency gain above 5%. Neither is promoted.
