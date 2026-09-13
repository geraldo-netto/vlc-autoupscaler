# Playback policy and native display experiments

This follow-up tests the remaining CPU placement, adaptive sharpening, GPU
cadence and native display questions from the [Vulkan latency report](VULKAN_LATENCY_EXPERIMENTS.md).
Production defaults and the installed launcher remain unchanged. No VLC source
patch, audio processor or additional player is introduced.

## CPU method

The host is the same Ryzen 9 7945HX, with 32 allowed logical CPUs. Physical
cores 0--7 share one L3; physical cores 8--15 share another. The 72-run CPU
matrix uses three shuffled repetitions, 240 frames per run, paced at 30 fps.
It covers animation, motion and live action at 1080p, plus live action at 4K.
The public sample provenance remains in the [earlier playback report](PLAYBACK_VULKAN_EVALUATION.md).

These direct-backend tests select output geometry explicitly. Their 320x180
to 1080p rows are stress cases beyond playback's existing 4x ratio cap, which
would produce 720p. The 540p-to-1080p/4K cases fit that cap. Separate 720p
adaptive controls below exercise the production geometry and automatic
eight-worker USM budget for the animation input.

The actual zimg Spline36 backend uses source and destination zero-copy. USM
amount is 51 in Q8 (20%). The production sharpness cutoff, 3500, applies after
the first 60 source frames. None of these clips triggered that cutoff.

Unlike the earlier warm steady-state microbenchmarks, these runs include lazy
worker startup and probe work. Context setup and loading decoded input are
outside frame timing. Each sample also records process CPU around processing;
the older aggregate `cpu_us` includes file reads and pacing overhead. All
workers in the process contribute to process CPU. Timings exclude presentation.

USM placement is a benchmark-only hook. It restricts only USM worker threads
to an explicit CPU range and verifies each applied mask. The scaler retains
its existing pinning. With eight scaler workers, cores 0--7 are the local
range and 8--15 are the remote range. The coordinator remains scheduler-managed.
This experiment changes placement, not an isolated cache characteristic.

No benchmark overlaps another benchmark, build, analyzer or playback test.
Source, binary and input hashes are checked before and after each matrix.
The desktop remains active. Results establish behavior on this host and these
inputs, not a universal policy.

## CPU results

Tables show the median of three run means or percentiles, in microseconds.
Percentiles are not pooled across repetitions.

| Input / output | Scaler / USM workers | USM placement | Mean | p95 | p99 | Process CPU/frame |
|---|---|---|---:|---:|---:|---:|
| Animation / 1080p | 8 / 8 | Scheduler | 523.4 | 897.2 | 1589.2 | 2206.8 |
| Animation / 1080p | 8 / 8 | Cores 0--7 | 446.2 | 854.6 | 2068.4 | 1933.7 |
| Motion / 1080p | 8 / 8 | Scheduler | 446.7 | 483.1 | 2162.8 | 2154.1 |
| Motion / 1080p | 8 / 8 | Cores 0--7 | 454.7 | 983.6 | 2088.6 | 1960.2 |
| Live action / 1080p | 8 / 8 | Scheduler | 605.4 | 1126.8 | 2437.0 | 2556.6 |
| Live action / 1080p | 8 / 8 | Cores 0--7 | 520.0 | 741.3 | 1753.1 | 2218.6 |
| Live action / 4K | 8 / 16 | Scheduler | 1419.5 | 1801.8 | 3219.2 | 9837.7 |
| Live action / 4K | 12 / 16 | Scheduler | 1254.6 | 1734.5 | 2392.9 | 9790.6 |
| Live action / 4K | 16 / 16 | Scheduler | 1260.7 | 1610.3 | 3072.3 | 12387.8 |

Local placement with eight USM workers lowers process CPU for all three
1080p clips. It improves both mean and tails for live action, but animation
p99 and motion p95 regress. At 12 USM workers, local placement also lowers
CPU, while motion mean rises from 486.8 to 609.0 microseconds. These results
do not support enabling a universal locality policy.

With eight scaler and 12 USM workers, putting USM on the remote range gives
mean times of 712.8/712.9/766.6 microseconds for animation/motion/live action,
versus 491.6/486.8/528.4 with scheduler placement. Deliberately separating
these stages across L3 domains is not supported by these measurements.

At 4K, 12 scaler workers use about 21% less process CPU than 16, with nearly
the same mean and lower p99; p95 favors 16. Worker-count changes can alter
zimg tile seams, so this remains a quality-sensitive policy choice. Placement
comparisons retain the same tile geometry. Their final visible-picture hashes
match, and permanent tests also compare output across USM trial counts.

## Adaptive sharpening

Twelve additional runs compare the fixed automatic 12-worker USM pool with
opt-in adaptation at 1080p. Each run contains 2,048 paced frames (about 68
seconds), including lazy startup, trial setup and retirement, probe work and
accepted policy changes. The same 600-frame decoded clips loop during each
run. Scaler geometry stays fixed at 12 workers, and final picture hashes match
between fixed and adaptive runs.

| Input | USM policy | Mean us | p95 us | p99 us | Process CPU us/frame |
|---|---|---:|---:|---:|---:|
| Animation | Fixed | 482.9 | 772.1 | 2570.1 | 3033.6 |
| Animation | Adaptive | 519.1 | 1100.5 | 2310.6 | 3294.7 |
| Live action | Fixed | 534.3 | 1011.7 | 2355.5 | 3173.1 |
| Live action | Adaptive | 558.3 | 1121.8 | 2259.0 | 3249.9 |

The median means and p95 do not favor adaptation. Paired mean differences are
+23.4%, +7.5%, -5.3% for animation and +11.8%, -2.6%, -7.0% for live action;
a negative value favors adaptation. This variability prevents a stable winner
claim. Adaptive p99 is lower in the median table, at higher median CPU cost.

Every adaptive run reached its first settled state between frame 1258 and
1580, then returned to exploration before the run ended. Four runs accepted
no worker-count change. The final animation repetition accepted one change
and ended with 16 incumbent workers; the final live-action repetition accepted
three changes and also ended with 16. Those acceptance frames took 564--610
microseconds including pool retirement. No fallback or sharpness bypass
occurred in these runs; permanent tests exercise both paths.

The controller's existing mean/tail acceptance rule remains unchanged. This
experiment does not justify enabling adaptation by default or claiming a
stable learned policy. Trace `workers` records the incumbent pool; it does
not identify every transient trial pool. The recorded phase distinguishes
base, trial, confirmation and settled intervals.

An initial summary parser mislabeled fixed-pool frames as exploration because
the inactive tuner has phase zero. OBS-20 fixes classification using the
explicit adaptive-mode flag. The original timings and traces remain intact;
the measured runner snapshot and corrected summaries preserve that distinction.

Six further 2,048-frame runs use animation's actual production geometry,
1280x720, and its automatic eight-worker USM budget:

| USM policy | Mean us | p95 us | p99 us | Process CPU us/frame |
|---|---:|---:|---:|---:|
| Fixed | 331.2 | 872.6 | 2581.9 | 1467.2 |
| Adaptive | 312.1 | 577.3 | 1908.4 | 1497.2 |

Adaptive mode improves mean and tails in all three matched repetitions here,
while median CPU rises about 2%. Its median mean is 5.8% lower. Nevertheless,
none of these runs accepted a worker-count change: each kept eight incumbent
workers, reached settlement around frames 1318--1378, and resumed exploration.
The improvement therefore cannot be attributed to a learned final worker
preset. Transient trials and scheduler/system effects remain entangled.
Together with the mixed 1080p results, this supports retaining the opt-in
experiment and unchanged defaults.

## GPU cadence and telemetry

The 72-run cadence matrix uses direct libvulkan on the RX 6600 XT, one repeated
960x540 decoded frame, 1080p output and combined Spline36/USM. It contains
60 timing-disabled comparisons with and without a telemetry reader, plus
12 stage-timestamp profiles. Three shuffled repetitions cover unpaced, 120,
60, 30 and 24 fps operation. Each run has 20 warmup and 120 measured frames.
Because this experiment holds the packed input constant, it excludes the
stride-packing work exercised by the earlier changing-frame GPU benchmark.

| Cadence | Separate passes, mean us | Fused passes, mean us |
|---|---:|---:|
| Unpaced | 585.0 | 536.1 |
| 120 fps | 1153.6 | 1400.2 |
| 60 fps | 1180.0 | 1442.5 |
| 30 fps | 1232.3 | 1481.1 |
| 24 fps | 1241.0 | 1475.8 |

These are the unmonitored controls. Across all cadence/variant cases, enabling
the reader changes median mean latency by -1.9% to +3.9%; it can perturb tails
more. Consequently, monitored runs supply attribution rather than the ranking.
The fused kernel wins only without pacing in this matrix.

GPU timestamps reproduce the earlier slowdown: the fused final pass grows
from 303.4 to 907.7 microseconds at 30 fps. Separate vertical scaling grows
from 110.5 to 335.8 microseconds and USM from 245.0 to 343.2. Host upload and
readback also grow, but most additional time is inside submission/completion
and the GPU stage intervals, which include their synchronization boundaries.

The reader polls the [AMD hwmon/sysfs interfaces](https://docs.kernel.org/gpu/amdgpu/thermal.html)
at 10 ms intervals and keeps only samples between the benchmark's recorded
measurement bounds. For the separate path, the median reported clock changes
from 2412.5 MHz unpaced to 19 MHz at 30 fps, and reported power from 22.5 to
6 W. The fused path reports 2279 to 24 MHz and 24.5 to 5 W. These sensor
intervals include idle gaps and firmware averaging; those tiny paced clock
values are **not measurements of the clock while a kernel executes**.

The data are consistent with cadence-dependent power/clock behavior and
exclude input-frame changes as the sole explanation. They do not isolate
active clock, memory-state transitions or scheduling as the cause. The
driver's `auto` policy was read and verified unchanged; no clock, power cap,
voltage or system scheduling setting was written. Reported power is not a
whole-machine energy measurement. A locked-clock experiment would be a
separate intervention, not a justified default change from these results.

## Native video output

`tests/experiment_vout.c` implements an opt-in `vout display` module. It opens
the existing upscaling filter with output-format changes allowed, then supplies
enlarged pictures directly from the stock OpenGL output pool. Input pictures
remain borrowed during preparation and are released on display. The module
does not encode video or create another player.

The child output requests its window through the parent VLC display's public
window callbacks from the [VLC display API](https://github.com/videolan/vlc/blob/3.0.20/include/vlc_vout_display.h).
This keeps fullscreen and window ownership with VLC, resolving
the splitter prototype's observed fullscreen limitation. Stock OpenGL handles
presentation and subtitle composition. This is a CPU upscaler feeding OpenGL;
it is not a Vulkan backend or a GPU-resident playback path.

An isolated, unmodified VLC 3.0.20 runtime verified 320x180 to 1280x720
processing, fullscreen and restore, explicit window resizing, visible subtitles,
seeking to 10 seconds and back to 1 second, native volume at 100/25/50 percent,
and window cleanup. The final short control reported 270 displayed frames and zero
lost frames. Those counters do not establish display latency or guarantee
zero drops over other workloads.

The prototype accepts eligible, normally oriented software I420 sources without
an initial crop offset. Unsupported inputs can use VLC's explicit output-module
fallback list, `--vout=autoupscale-vout,gl`. The launcher is not replaced.
General format coverage and end-to-end presentation latency remain separate
adoption questions. Vulkan output still requires a compatible presentation
path and validation of its different scaling pixels.

### Matched playback CPU comparison

Twelve real-VLC runs compare this native path with the existing
`transcode{...vfilter=autoupscale}:display` bridge. Both use the same encoded
input, Spline36, USM amount, pinning policy, metrics setting and stock OpenGL
presentation. Each owned window is resized to 1280x720 before sampling.
Process CPU is sampled from seconds 3--15; three shuffled repetitions run
sequentially. The isolated runtime verifies the exact plugin selection.

| Input | Actual processing output | Bridge CPU, % of one core | Native CPU, % of one core | Reduction |
|---|---|---:|---:|---:|
| Animation, 320x180 | 1280x720 | 28.67 | 5.83 | 79.7% |
| Live action, 960x540 | 2560x1440 | 92.50 | 20.25 | 78.1% |

The explicitly requested preset is 1440p (`target=3`); the existing ratio
cap limits the 180p input to 720p. Geometry matches between paths within each
pair. These media fixtures contain video only; separate audio/video controls
above verify native volume. CPU percentages include all VLC threads and use
one logical core as 100%, not the entire 32-thread host.

The native path avoids the bridge's additional H.264 encoding and decoding.
Every native run reports positive displayed-frame counts and zero lost frames
over this short interval. The bridge's playlist counters remain zero and
unobserved for its private display; they are not evidence of zero drops.
This comparison establishes lower process CPU, not a measured reduction in
decode-to-screen latency or pixel equivalence after the bridge's lossy encode.

## Reproduction and regression coverage

```sh
make BUILD=build/policies EXTRA_CFLAGS=-Werror build-profile native-vout-prototype
python3 scripts/bench_playback_policies.py build/policies decoded-clips results-cpu
python3 scripts/bench_playback_policies.py build/policies decoded-clips results-adaptive --phase adaptive
python3 scripts/bench_playback_policies.py build/policies decoded-clips results-adaptive-720 --phase adaptive-720
python3 scripts/bench_native_playback.py build/policies encoded-clips results-native
```

The CPU runner expects `animation.yuv`, `motion.yuv` and `live-action-540.yuv`,
with 320x180 geometry for the first two and 960x540 for the last. The playback
runner expects the corresponding animation and live-action MKV inputs.
Every output directory must be new. No media download or transcoder is part
of these runners.

Build the Vulkan benchmarks with the SDK/runtime options in the
[Vulkan report](VULKAN_LATENCY_EXPERIMENTS.md#reproduction), then run:

```sh
python3 scripts/bench_gpu_pacing.py build/policies decoded-clips/live-action-540.yuv results-gpu
```

The cadence runner uses Vulkan device index 0 and defaults to DRM `card1`
for telemetry on this host; `--device` selects another DRM sysfs device path.
Check that both refer to the same GPU before interpreting telemetry elsewhere.

The normal test suite retains regression coverage for benchmark sharpness-gate
retirement (REL-23), adaptive output/fallback behavior, verified USM placement,
native display ownership, window/event/control routing and failure cleanup.
The previous benchmark kept the USM pool after sharpness bypass; the new
regression failed before the harness was corrected to retire it as playback does.

The optional real-desktop regression requires VLC, X11, `wmctrl`, `xwininfo`,
`xprop`, ImageMagick `import`, Tesseract and PulseAudio-compatible `pactl`:

```sh
make BUILD=build/policies test-native-vout-runtime \
    NATIVE_TEST_CLIP=/path/to/low-resolution-audio-video.mkv \
    NATIVE_TEST_OUTPUT=build/policies/new-runtime-result
```

It uses a private null audio sink and checks only its own VLC stream. The
fixture requests a black subtitle background so OCR can verify rendered text
against colorful video. No audio or display preference is changed globally.

## Evidence and validation

The [evidence archive](benchmarks/playback-policies-2026-09-13/README.md) retains
174 benchmark runs: 72 CPU policy controls, 18 adaptive comparisons, 72 GPU
cadence controls and 12 real playback comparisons. Raw timings, per-frame
traces, commands, hashes, telemetry and GUI results remain available.

- [CPU results](benchmarks/playback-policies-2026-09-13/cpu/results.json)
- [1080p adaptive results](benchmarks/playback-policies-2026-09-13/adaptive/results.json)
- [720p adaptive results](benchmarks/playback-policies-2026-09-13/adaptive-720/results.json)
- [GPU results and telemetry](benchmarks/playback-policies-2026-09-13/gpu/results.json.gz)
- [Matched native playback](benchmarks/playback-policies-2026-09-13/native-playback/results.json)
- [Native controls](benchmarks/playback-policies-2026-09-13/native-controls/result.json)

The normal automated suite passes with ASan/UBSan and `-Werror`. Clang TSan
passes the new profile/adaptive/affinity tests. Clang static analysis reports
no native-vout findings; cppcheck, shell/workflow/Markdown checks, plugin
hardening and visibility checks pass. Lizard enforces CCN at most 10.

The permanent complexity gate now includes `scripts/`. It rejected the GPU
telemetry summary at CCN 11 before the helper was split. This post-measurement
refactor changes no sampling or timing code; all 72 archived summaries match
exactly. [Analysis validation](benchmarks/playback-policies-2026-09-13/analysis-validation.json)
records the measured and final source hashes.

BUILD-40 now retains Make jobserver descriptors through recursive shell
fixtures; its regression reproduced the warning before the recipe fix.
The obsolete lifecycle mutation shims were removed without changing runtime
behavior. SDK callback types remain unchanged: narrow cppcheck metadata
documents its incompatible const suggestions rather than casting function
pointers. No new production tuning policy was selected.
