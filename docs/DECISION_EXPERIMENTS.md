# Decision experiments, 12 September 2026

These experiments evaluate the selected alternatives without changing production
worker presets, pinning, zero-copy, graph geometry or the default-off adaptive
mode. The mean/tail controller update affects the existing opt-in USM tuner.
The launcher separately stops requesting audio re-encoding; the plugin processes
video only. An AC3 input retained AC3 audio through a real VLC transcode run.
VLC still decodes audio for playback, and the private transcode-display output's
volume-control limitation remains.

## Method and scope

Host: Ryzen 9 7945HX, 32 allowed logical CPUs. Builds use `-Werror`, zimg at
`-O2 -g -march=native`, and USM plus profiling driver at `-O3 -g -march=native`.
Timed binaries have no sanitizers. The separate normal test suite uses ASan and
UBSan. These backend experiments exclude video decoding, display, encoding and
VLC picture allocation. Process CPU includes raw-frame staging and pacing;
the reported frame latency begins after staging.

Paced comparisons use Spline36, I420, 20% USM, 128 unpaced warmup frames and
240 measured frames at a 16,667-us period. Three repetitions are shuffled with
seed 20260912. Input is predecoded packed I420, with every visible row copied
into an aligned picture before timing. The first 60 source frames pass through
the same metrics and 3500 sharpness cutoff used by production. These tests
exercise that decision, but retain the idle USM pool if sharpening is skipped;
they do not measure production's pool-destruction cost.

The source clips contain 600 frames at 30 fps. Replaying successive frames at
60 fps is a pacing stress test at twice the source timeline rate. It is not a
claim about native-cadence, complete VLC playback. Long runs repeat the same
20-second source segment for 3,600 measured frames (about one minute). This
tests sustained scheduling and thermal drift, not the content evolution of an
entire movie. Per-frame cost depends on dimensions, content, sharpening and
pacing; duration also affects startup, adaptation and temperature.

Inputs come from Blender's public films:

- [Big Buck Bunny 320x180 archive](https://download.blender.org/peach/bigbuckbunny_movies/BigBuckBunny_320x180.mp4.zip),
  20 seconds starting at 60 seconds (`animation`) and 240 seconds (`motion`).
- [Tears of Steel 720p](https://download.blender.org/demo/movies/ToS/tears_of_steel_720p.mov),
  20 seconds starting at 120 seconds, downsampled to 320x180 (`live-action`)
  and 960x540 (`live-action-540`).

The 320x180 sources produce 1280x720; the 960x540 source produces 3840x2160.
Both respect the plugin's four-times geometry cap. The small clip set and one
host cannot prove the best setting for every low-resolution video.

## Reproduction

Download and unzip the animation archive into a local clip directory. Generate
raw inputs with FFmpeg; use the corresponding input, timestamp and geometry
for each clip listed above:

```sh
ffmpeg -ss 60 -i BigBuckBunny_320x180.mp4 -t 20 \
  -vf fps=30 -an -pix_fmt yuv420p -f rawvideo animation.yuv
ffmpeg -ss 120 -i tears_of_steel_720p.mov -t 20 \
  -vf scale=960:540,fps=30 -an -pix_fmt yuv420p -f rawvideo live-action-540.yuv
make BUILD=build-perf10 EXTRA_CFLAGS=-Werror build-profile build-perf10/bench_adaptive
python3 scripts/bench_decisions.py build-perf10 /path/to/clips /path/to/new-results
python3 scripts/bench_decisions.py build-perf10 /path/to/clips /path/to/new-results --followup
```

The output directory must be new. Each JSON record retains the command,
experimental environment, stage means, p95/p99, process CPU, RSS, context
switches and final output hash. Per-frame CSVs retain latency samples.
The continuous adaptive matrix has three repeats of fixed 12 versus adaptive
USM for Lanczos/Spline36 and pinning off/on, 4096 frames each. Its synthetic
noise deliberately forces USM on; CSV includes the actual profile and outcome.

The follow-up pairs four animation settings at native 30-fps cadence, three
repeats, then compares the original and independent gates at 32 workers in
five neighboring randomized pairs at 60 fps. It uses seed 20260913 and appends
to the initial result directory. Pairing reduces separation in time between
controls; it cannot eliminate scheduler or thermal variation.

## Fixed-grid and notification prototypes

`tests/experiment_executor.h` implements static cyclic assignment of immutable
graph cells to active workers. Every cell retains its graph and scratch;
there is no dynamic task queue. Benchmark mode 1 uses the existing shared gate;
mode 2 gives each worker its own gate and completion counter. Both invoke the
same production pixel kernels. The original pool's threads remain parked in
both prototypes, so their resource use and startup are not production designs.
They are stopped only after replacement workers have joined.

The public profiling command remains compatible. Experimental settings are
explicit environment variables, validated before initialization:

| Variable | Meaning |
|---|---|
| `UP_PROFILE_INPUT` | Packed I420 input path; an incomplete or empty file fails |
| `UP_PROFILE_WIDTH`, `UP_PROFILE_HEIGHT` | Even source dimensions; default half the output |
| `UP_PROFILE_SHARP_THRESHOLD` | Source gate cutoff; default 0 in the profiling tool, 3500 in these video experiments |
| `UP_PROFILE_EXECUTOR` | 0 original, 1 experimental shared gate, 2 independent worker gates |
| `UP_PROFILE_ACTIVE` | Active zimg executors over the unchanged graph grid; 0 uses the grid count |
| `UP_PROFILE_ZEROCOPY` | 1 source/destination direct paths, 0 both copy paths |

Experimental dispatch requires tracing detail 0. Its scheduler-trace fields
are unavailable and remain zero; process CPU and frame/stage timings remain
measured. Fixed-grid comparisons retain a 12-cell zimg grid while using 4, 8
or 12 executors. Notification comparisons use matching 12/12 or 32/32
zimg/USM counts. Pinning calls use the existing placement hook.

Permanent tests cover changing active counts, exactly-once cell ownership,
partial thread creation, bounded completion failure, joins before releasing
storage, idempotent shutdown, packed input validation and per-pixel equality
of the combined scaler/USM output. Runtime adaptation of the production zimg
pool is not enabled by these experiments.

## Cache attribution and research

[The authenticated attribution](PROFILING.md#follow-up-12-september-2026)
identifies true sharing on the completion counter. It justifies measuring
notification alternatives; it does not predict a speedup.

[Primary BBR code review](BENCHMARKS.md#bbr-research-and-transfer-limits)
resolves the blanket claim that BBRv1 ignores loss. The ML paper's training
versus validation contradiction remains unresolved externally. User follow-up
choice 2a rejects that accuracy claim as a design dependency (SCAL-10), so
measurement research can proceed without it. No model is trained and no
production metric threshold is tuned from these clips.

## Results

The artifacts retain [all 102 paced runs](benchmarks/decisions-2026-09-12/paced.jsonl),
[per-frame samples](benchmarks/decisions-2026-09-12/frame-samples.json.gz),
[group summaries](benchmarks/decisions-2026-09-12/summary.csv),
[24 adaptive runs](benchmarks/decisions-2026-09-12/adaptive.csv) and
[environment/input hashes](benchmarks/decisions-2026-09-12/environment.json).
The compressed frame file is a JSON object mapping the recorded CSV filenames
to their contents. Tables below show medians of run statistics in microseconds;
they are not pooled percentiles or confidence intervals. CPU is process CPU
per measured frame.

### Notification at 32 workers

Five paired repeats at 60 fps, matching 32-cell grids and output hashes:

| Executor | Mean | p95 | p99 | CPU/frame |
|---|---:|---:|---:|---:|
| Original shared gate | 389.60 | 528.87 | 1553.35 | 5005.2 |
| Independent worker gates | 332.92 | 421.70 | 999.22 | 4108.2 |

Independent gates reduce the median run mean by 14.6% and CPU/frame by 17.9%.
All five paired means improve, but the last pair's p99 worsens from 434.79 to
1016.50 us. At 12 workers, the initial three-repeat comparison is essentially
tied (276.83 versus 274.53 us). Keep production's existing gate: the useful
high-count signal warrants further experimentation, not a default change or a
claim of regression-free tails. The experimental shared-gate control is also
retained so the parked original threads are visible in both prototype designs.

### Fixed graph grid

Live-action 720p, unchanged 12-cell zimg grid, 12 USM workers, three repeats:

| Gate | Active zimg workers | Mean | p95 | p99 | CPU/frame |
|---|---:|---:|---:|---:|---:|
| Shared | 4 | 343.97 | 363.76 | 701.31 | 1455.0 |
| Shared | 8 | 397.42 | 629.28 | 2295.41 | 1913.6 |
| Shared | 12 | 260.38 | 308.40 | 1679.20 | 1687.9 |
| Independent | 4 | 329.28 | 428.41 | 889.57 | 1479.1 |
| Independent | 8 | 320.77 | 542.51 | 1382.72 | 1452.0 |
| Independent | 12 | 251.22 | 338.19 | 952.30 | 1930.6 |

Scheduling fewer workers preserves pixels but does not beat 12 workers on mean
latency here. Some settings trade lower CPU or tails for a slower mean. The
tested fixed-grid foundation remains available for research; integrating
adaptive zimg into production has no demonstrated benefit from these samples.

### Presets, pinning and zero-copy

Paired native 30-fps animation runs, three repeats, fixed 12-cell zimg grid:

| USM workers | Pinning | Zero-copy | Mean | p95 | p99 | CPU/frame |
|---:|---|---|---:|---:|---:|---:|
| 8 | On | On | 278.44 | 378.34 | 1429.92 | 1673.1 |
| 12 | On | On | 277.01 | 353.45 | 553.58 | 1780.6 |
| 12 | Off | On | 310.14 | 491.18 | 511.21 | 2561.1 |
| 12 | On | Off | 357.27 | 971.69 | 2257.63 | 2008.9 |

The 8/12-worker means nearly tie; eight uses less CPU while twelve has better
tails in this sample. Pinning helps mean and CPU but has a slightly worse p99.
Zero-copy helps all these aggregate measures. At 4K in the initial matrix,
copying takes 1433.11 versus 1125.14 us with zero-copy, with worse tails and
more CPU; pinning means nearly tie while pinned tails improve. These paired
and 4K results support retaining zero-copy and the existing pinning default.
They do not prove that pinning is always best.

The initial matrix exposes substantial control variation: identical animation
12/12 pinned zero-copy settings yield 227.12 us in the preset group and 368.79
us in the pin/copy group. Consequently, individual group rankings cannot be
treated as stable tuning evidence. The 4K preset comparison is 1053.61 us with
12 USM workers versus 1090.00 with 16; the latter also costs more CPU. The two
one-minute motion runs give 349.02 us with eight versus 327.76 with twelve,
while eight uses less CPU (1723.7 versus 1832.0 us/frame). Short-run motion
means had favored eight. Preserve the current 8/12/16 presets while gathering
stronger playback evidence; TODO PERF-15 retains this unresolved variation.

All comparable final-frame hashes match, including copy/direct paths where
the grid remains unchanged. Full per-pixel tests additionally cover both
experimental gates and scheduling over row and column grids. Initial probe
Laplacian means are 325 (animation), 291 (motion), 435 (small live action) and
63 (540p live action): all below 3500, so sharpening remains active. This set
does not validate the cutoff for grainy or heavily compressed material.

### Adaptive profile matrix

Continuous synthetic runs, three repeats, fixed 12 versus adaptive USM:

| Algorithm | Pinning | Fixed mean | Adaptive mean |
|---|---|---:|---:|
| Lanczos | Off | 291.01 | 298.54 |
| Lanczos | On | 258.32 | 256.85 |
| Spline36 | Off | 293.03 | 292.83 |
| Spline36 | On | 255.11 | 254.46 |

The intended Spline36/pinned profile shows only a 0.3% difference, not an
established gain. Two of twelve adaptive runs remain searching at frame 4096;
none falls back. The historical 10.4% result in BENCHMARKS.md used an older
controller, Lanczos without pinning and an eight-CPU affinity limit. It does
not establish a benefit for this current default profile or for paced video.

## Selected alternatives and remaining decisions

| Choice | Result |
|---|---|
| 1a | Mean improvement plus p95/p99 guards; permanent tuner regression cases |
| 2a | Authenticated CPU/IBS attribution, capture failure regression tests |
| 3a | Paced source clips, CPU/tail comparisons and one-minute runs; presets retained |
| 4b | Primary-code research and metric collection; no trained model or default tuning |
| 5b | Fixed-grid executor prototype, changing active counts, ownership and pixel tests |
| 6a | Backend fallback documentation names the production owner |
| 7a | Shared versus independent notification/completion prototypes and paired measurements |
| 8 | Plugin is video-only; launcher no longer requests audio re-encoding; volume ownership remains unresolved |
| 9, superseded by follow-up 4a | Output-format permission enforced with permanent regression coverage |
| 10b | CI runs the canonical built fuzzer list, including plane-buffer mutation fuzzing |
| 11a | Coverage union documented and complementary-binary fixture added |
| 12 | Zero-copy implementation retained; measurements and same-grid limitation documented |
| 13a | Pinning comments corrected and on/off behavior measured; universal optimality unproven |
| 14b | Scratch diagnostics report source, shared destination, tiles, graph temporary bytes and total |
| 15b | Algorithm/pinning/outcome CSV fields, failure regression coverage and all four profiles measured |

The [playback/Vulkan follow-up](PLAYBACK_VULKAN_EVALUATION.md) implements the
new output permission decision, rejects the ML accuracy claim as a design
dependency, and tests stock VLC commands without optional audio effects.
Performance defaults remain unchanged. Stable policy evidence (PERF-15) and
the native-volume/enlarged-display conflict (REL-16) remain unresolved.

## Validation

`make check plugin check-hardening check-visibility` passes with `-Werror` and
ASan/UBSan. `make analyze` covers the whole source/test tree with Lizard
(CCN <= 10), cppcheck, ShellCheck, Actionlint, Markdown checks and offline
fragment/link checks. Clang 18 Static Analyzer reports no bugs in the single
and multiversion plugin builds. Clang 18 TSan passes the executor lifecycle
and combined scaler/USM pixel suites; this host's GCC TSan runtime aborts on
an unexpected memory mapping, so it is not counted as a passing run.

The canonical runner executes the plane-buffer libFuzzer for its full 30-second
budget: 625,244 inputs, no finding. Its permanent fixture also checks that every
target in Make's canonical list is executed and special corpus/budget settings
are retained. This local pass does not claim that a remote CI job was run.

Permanent tests were first observed failing for the confirmed tuner, capture,
audio-launcher, scratch-accounting, benchmark-profile and output-error defects,
then passing after their fixes. The output-error regression checks a successful
baseline and rejects closed stdout for both adaptive and pipeline benchmarks;
the final flush is now checked before reporting success. All experiments here
captured complete, parseable output before that final error-path correction.
