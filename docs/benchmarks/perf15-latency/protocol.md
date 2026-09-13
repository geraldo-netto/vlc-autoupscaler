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
