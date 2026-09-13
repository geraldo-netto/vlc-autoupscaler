# Direct Vulkan latency experiments

These optional benchmarks test how far direct libvulkan scaling and sharpening
can reduce processing cost on this host. They do not change the production
backend, worker policy, quality defaults, zero-copy settings or VLC launcher.
No audio processing or VLC patch is introduced.

The subsequent [playback policy experiments](PLAYBACK_POLICY_EXPERIMENTS.md)
extend CPU placement, adaptive playback and native window integration coverage.

The experiment compares several implementations, rather than treating a single
GPU timing as a hardware limit. It retains the original direct-library baseline
in [the playback report](PLAYBACK_VULKAN_EVALUATION.md#direct-gpu-measurements).

## Implemented candidates

| Candidate | Implementation | Cost being tested |
|---|---|---|
| Naive | Original 6x6 Spline36 kernel | Baseline repeated sampling |
| Separable | Six horizontal taps into a float buffer, then six vertical taps | Fewer samples per output pixel |
| Lookup | Normalized coefficients and reflected indices computed once | Repeated polynomial and coordinate work |
| Direct | Coherent cached host buffers read/written by the GPU | Removes explicit DMA staging copies; GPU memory traffic still exists |
| Combined | Scaling and exact luma USM in one command submission | One upload/readback pair for both stages |
| Fused | Vertical scaling and USM share a 64x4 pixel workgroup tile with halos | Removes the full scaled intermediate and a dispatch |
| Resident | Completes GPU work without downloading output | Measures the cost of retaining GPU output; does not present it |

The final shader build enables shaderc's performance optimization and specializes
geometry and pass selection when creating each pipeline. Sharpening amount remains
a push constant. This makes invariant branches and dimensions available to the
GPU compiler without rebuilding shaders for each frame. Resources and commands
persist between frames; each call waits for its own completion. There is no queue
of multiple frames in flight.

The fused kernel preserves byte rounding between scaling and sharpening. It
sharpens luma only and copies the scaled chroma values. Widths not divisible by
eight use the separate USM pass, avoiding packed-word writes across row boundaries.
The prototype accepts even software-I420 dimensions up to the existing 4K pixel
budget. It does not impose a new production memory or geometry policy.

## Measurement method

The host is a Ryzen 9 7945HX with an RX 6600 XT and Radeon 610M, using Mesa
26.2.2 and Vulkan loader 1.3.275. Results identify the device name; enumeration
indices are local to each process. Neither benchmark links FFmpeg or libplacebo.

The CPU comparison invokes the actual zimg backend with 12 pinned workers,
source and destination zero-copy, and Spline36. Combined runs then use the
actual in-place USM pool, with 12 workers at 1080p and 16 at 4K, amount 51 in
Q8 (20%). USM is forced on every frame here; production content gating is not
part of this benchmark.

Each run has 20 warmup frames and 120 measured frames. Three repeated orders
alternate forward/reverse/forward. Unpaced runs reuse the first decoded
960x540 I420 frame. Paced runs cycle through 32 consecutive decoded frames
at 30 fps; they include the GPU's stride-to-packed input copy in the timed
processing call. Reading the file and populating the simulated VLC input
picture are outside timing for both backends. Output geometry is 1920x1080
or 3840x2160. Startup, compilation, decoding, encoding, display conversion,
compositing and presentation are excluded.

Wall timing includes upload memcpy, submission, completion wait, readback and
output memcpy where the candidate uses them. Process CPU includes all benchmark
threads. Resident variants omit readback and output memcpy and are reported
separately. Their smaller number is not a VLC playback result.

The runner executes sequentially without overlapping builds, analyzers or other
agent benchmarks. It records commands, raw output, host load and hashes, then
checks that benchmark, shaders, sources and decoded input stayed unchanged.
The desktop remains active, so these are repeated measurements on one host,
not controlled laboratory or cross-machine guarantees.

## Results

The 160-run matrix contains 144 timing-disabled runs and 16 stage profiles.
Tables report the median of three run means; tail columns are medians of the
three per-run percentiles, not a pooled percentile. All runs completed and
the manifest check passed.

### Scaling only, unpaced

| GPU / output | CPU ms | Naive GPU ms | Separable GPU ms | Lookup + direct GPU ms | Reduction from naive |
|---|---:|---:|---:|---:|---:|
| RX 6600 XT / 1080p | 0.140 | 1.085 | 0.725 | 0.573 | 47.2% |
| RX 6600 XT / 2160p | 0.358 | 3.918 | 2.426 | 2.167 | 44.7% |
| 610M / 1080p | 0.132 | 13.946 | 6.353 | 3.600 | 74.2% |
| 610M / 2160p | 0.368 | 49.553 | 20.715 | 14.364 | 71.0% |

The optimized kernels substantially reduce GPU time in these unpaced controls.
The CPU still has the lowest mean scaling time. This does not establish a
quality-equivalent replacement or a universal GPU limit.

### Scaling plus USM, RX 6600 XT, unpaced

| Output | CPU ms | Separable + USM ms | Lookup + direct ms | Lookup + fused + direct ms | Fused, no readback ms |
|---|---:|---:|---:|---:|---:|
| 1080p | 0.326 | 0.844 | 0.651 | 0.566 | 0.449 |
| 2160p | 0.835 | 2.771 | 2.232 | 1.915 | 1.234 |

Fusion improves the complete unpaced GPU call by about one third versus the
separable three-pass version. The no-readback column is a GPU-completion
experiment: it excludes the cost and behavior of making a displayed frame.

### Scaling plus USM, 32-frame sequence paced at 30 fps

| GPU / output | Backend | Mean ms | p95 ms | p99 ms | Process CPU ms/frame |
|---|---|---:|---:|---:|---:|
| RX 6600 XT / 1080p | CPU | 0.561 | 1.254 | 2.493 | 3.193 |
| RX 6600 XT / 1080p | GPU lookup + direct | 1.310 | 1.586 | 1.816 | 0.259 |
| RX 6600 XT / 2160p | CPU | 1.162 | 1.420 | 2.929 | 10.198 |
| RX 6600 XT / 2160p | GPU lookup + direct | 4.104 | 4.718 | 4.977 | 1.009 |
| 610M / 1080p | CPU | 0.530 | 1.088 | 2.585 | 4.051 |
| 610M / 1080p | GPU lookup + direct | 7.180 | 8.900 | 10.258 | 0.313 |
| 610M / 2160p | CPU | 1.171 | 1.430 | 2.189 | 9.890 |
| 610M / 2160p | GPU lookup + direct | 18.202 | 23.026 | 24.891 | 1.395 |

CPU has the lowest **mean** processing latency in this matrix. The discrete
GPU uses about 90–92% less process CPU time. At 1080p its median p99 is also
lower than the CPU control, while its mean and p95 are higher. Do not reduce
this tradeoff to a claim that one backend wins every latency measure.

The fused discrete-GPU variant reverses its unpaced ranking: paced means are
1.539 ms at 1080p and 5.041 ms at 4K, versus 1.310 and 4.104 ms without fusion.
The no-readback fused variant is 1.384/4.331 ms. It is neither the fastest
paced candidate nor evidence of a working zero-copy display.

Eight additional instrumented controls separate single-frame/32-frame input
from unpaced/30-fps operation. With one repeated frame, the fused final GPU
pass grows from about 305 to 908 microseconds when paced; the corresponding
separate vertical and USM passes grow from 111 + 247 to 340 + 343 microseconds.
The 32-frame sequence shows the same compute-stage reversal. Frame changes
alone do not explain it. Power/frequency and scheduling remain possible causes;
these experiments do not isolate them or change power policy.

### CPU worker-count follow-up

A separate 24-run paced sweep repeats 4/8/12/16 scaler workers at both
resolutions. The USM pool stays at 12 workers for 1080p and 16 for 4K.
All use the same 32-frame sequence. Changing scaler workers can change graph
seams; these are policy candidates, not equivalent-pixel substitutions.

| Output | Scaler workers | Mean ms | p95 ms | p99 ms | Process CPU ms/frame |
|---|---:|---:|---:|---:|---:|
| 1080p | 4 | 0.789 | 0.862 | 2.045 | 3.665 |
| 1080p | 8 | 0.542 | 0.594 | 1.569 | 3.281 |
| 1080p | 12 | 0.539 | 0.634 | 2.728 | 3.687 |
| 1080p | 16 | 0.510 | 0.612 | 1.593 | 4.784 |
| 2160p | 4 | 1.898 | 2.151 | 2.495 | 10.527 |
| 2160p | 8 | 1.266 | 1.418 | 1.916 | 8.852 |
| 2160p | 12 | 1.094 | 1.342 | 1.741 | 9.633 |
| 2160p | 16 | 1.210 | 1.474 | 2.823 | 12.459 |

At 1080p, eight workers retain almost the same mean as 12 while reducing
process CPU and the measured tail. Sixteen workers slightly lower the mean
but consume more CPU. At 4K, 12 workers give the lowest mean and tails in this
sweep; 16 regress both. These results strengthen the case for workload-specific
measurement, not a universal increase in thread count. The one-clip, one-host
scope and graph-quality differences keep PERF-15 open to further evidence;
production defaults remain unchanged.

## Stage timing

Optional host clocks and a persistent Vulkan timestamp query pool report host
copies, submit/wait, GPU upload, each compute pass and download. Timestamp
conversion respects the queue family's valid-bit count and device timestamp
period, including unsigned rollover. Unsupported timestamp queues reject the
instrumented request. CPU/GPU timings are different clock domains: only elapsed
intervals are compared. Barriers and synchronization can contribute to adjacent
stage intervals; the intervals are not pure hardware-engine occupancy.

Performance ranking uses timing-disabled calls. Additional instrumented runs
attribute costs and expose the measurement overhead; they are not substituted
for the repeated controls. The implementation follows the Vulkan
[timestamp contract](https://docs.vulkan.org/refpages/latest/refpages/source/vkCmdWriteTimestamp.html).

## Pixel correctness and limits

The permanent optional GPU suite runs both GPUs, eight combinations of staging,
lookup and fusion, six small geometries including partial tiles and chroma
boundaries, plus 4K identity on both devices. Each case uses constant, random
and high-contrast input with eight sharpening amounts, including clamp limits.
Separable scaling stays within one code value of an independent double-precision
Spline36 reference. Combined/fused USM must match CPU USM on the same GPU-scaled
pixels byte for byte, including unchanged chroma. Fused-ineligible widths exercise
the separate-pass fallback. Normal `make check` also retains pure geometry and
timestamp arithmetic tests without requiring a GPU.

This does **not** establish byte equivalence with the production tiled zimg
backend. Directly comparing one and 12 zimg workers on the same decoded frame
finds luma maximum delta 63 and RMSE 2.760926; chroma maxima are 8 and 13. The
existing smooth-fixture seam test is retained, but its former claim that only
noise could produce large differences is removed (REL-22). No perception or
quality ranking follows from these differences. CPU/GPU latency tables compare
implementations with this explicit quality caveat.

## Validation

The normal ASan/UBSan suite, warning-clean build, Lizard CCN <=10, cppcheck,
plugin visibility/hardening and documentation checks pass. The GPU suite also
passes with ASan, UBSan, leak detection, Khronos validation and synchronization
validation enabled. Standalone luma USM is checked from tiny/odd through 4K
geometry on both GPUs. Shader tests and instrumented validation runs are not
used as performance evidence.

An unrestricted loader-only reproducer reports 512 bytes in two driver
allocations after enumerating devices and destroying the instance. Selecting
only the Radeon ICD and retaining its library for process lifetime avoids
unloading those allocation roots. The full GPU suite then passes leak detection
without suppressing allocations or disabling sanitizers (BUILD-44). This is a
host-specific test setup, not a production setting or a fix to Mesa.

```sh
make BUILD=build-gpu build-vulkan-bench
make BUILD=build-gpu build-gpu/test_vulkan_pipeline
VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/radeon_icd.json \
LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libasan.so.8:/usr/lib/x86_64-linux-gnu/libvulkan_radeon.so \
VK_INSTANCE_LAYERS=VK_LAYER_KHRONOS_validation \
VK_LAYER_ENABLES=VK_VALIDATION_FEATURE_ENABLE_SYNCHRONIZATION_VALIDATION_EXT \
build-gpu/test_vulkan_pipeline build-gpu/vulkan_separable.spv \
  build-gpu/vulkan_usm.spv build-gpu/vulkan_fused.spv
```

Use the corresponding ICD, driver and ASan paths for the tested installation.
The local validation-layer package was extracted into the ignored build tree;
its `VK_LAYER_PATH` and `LD_LIBRARY_PATH` must be supplied when using that copy.
No system driver, loader or layer was installed or replaced.

## Reproduction

The optional build requires Vulkan headers/loader and the shaderc runtime in
addition to the project's VLC/zimg SDKs. On this checkout, the isolated header
and runtime overrides were:

```sh
make BUILD=build-perf10 EXTRA_CFLAGS=-Werror \
  VULKAN_CFLAGS=-Ibuild/decision-review/direct-vulkan/Vulkan-Headers-1.3.275/include \
  VULKAN_LIBS=-l:libvulkan.so.1 build-vulkan-bench
python3 scripts/bench_vulkan_matrix.py build-perf10 \
  build/decision-review/clips/live-action-540.yuv \
  build/decision-review/direct-vulkan/new-measurement
```

The runner requires a new evidence directory and at least 32 decoded frames.
The source excerpt and public download URL are documented in the
[earlier reproduction steps](DECISION_EXPERIMENTS.md#reproduction). The benchmark
itself uses direct libvulkan; file decoding is fixture preparation.

For one candidate:

```sh
build-perf10/bench_vulkan_scale build-perf10/vulkan_separable.spv 0 2 gpu \
  build/decision-review/clips/live-action-540.yuv \
  lookup-fused-direct build-perf10/vulkan_usm.spv 0 33333 12 32
```

Arguments after the clip are variant, USM shader or `-` for scaling only,
timestamp switch, pacing period in microseconds, optional CPU worker count,
and optional sequence length (1–32). CPU mode uses the same command with
`cpu` in place of `gpu`. Supply `vulkan_spline36.spv` for `naive`; other variants
use `vulkan_separable.spv`, with `vulkan_fused.spv` beside it for fused runs.

## What removing readback requires in VLC

The installed VLC 3.0 headers expose CPU planes and several decoder-specific
opaque formats; this project's scaler dispatch consumes software pictures.
The installed video outputs do not offer a consumer for this prototype's
Vulkan storage buffer. Merely omitting readback would leave the current VLC
output picture unwritten.

The supported video-only integration point is a new
[`vout_display_t` module](https://raw.githubusercontent.com/videolan/vlc/3.0.20/include/vlc_vout_display.h):
it can prepare GPU work and present the result while VLC retains audio, timing
and window ownership. Such a module must implement compatible GPU image output,
presentation, resizing, crop/aspect handling, subtitles, resource ownership and
recovery. This is a feasible integration direction, not implemented playback.
VLC's stock OpenGL path has an
[internal converter interface](https://raw.githubusercontent.com/videolan/vlc/3.0.20/modules/video_output/opengl/converter.h),
which is not a drop-in public Vulkan-buffer interface. Cross-API use also needs
compatible [external memory and synchronization](https://docs.vulkan.org/guide/latest/extensions/external.html).

Keep native-display integration distinct from kernel improvements. The earlier
splitter prototype still has the fullscreen limitation tracked as REL-16.
Increasing frames in flight can increase visible latency, as the Vulkan
[frames-in-flight tutorial](https://docs.vulkan.org/tutorial/latest/03_Drawing_a_triangle/03_Drawing/03_Frames_in_flight.html)
explains. This experiment keeps one submitted frame outstanding.

## Final copy-contract check

After recording the main matrix, Clang's analyzer treated the readback switch
as potentially changing across submission: true at the null-output check,
false at the eventual copy. The synchronous path never makes that transition.
A local null check now makes the copy contract explicit. Permanent GPU tests
cover rejecting null output with readback enabled, accepting it when disabled,
and restoring byte-identical output after re-enabling readback (BUILD-45).
Clang analysis and the full GPU sanitizer/validation suite pass.

The main matrix's manifest intentionally identifies the measured pre-guard
build. Its [backend source snapshot](benchmarks/vulkan-latency-2026-09-13/experiment_vulkan-measured.c)
is retained; shader and algorithm code did not change for this final guard.
A separate 12-run comparison alternates old/current binaries at 1080p and 4K,
using the best paced GPU candidate and the same 32-frame sequence.

Median old/current means are 1.292/1.313 ms at 1080p and 4.072/4.067 ms at
4K. The results retain the same latency tradeoff; they do not show a new
optimization from the defensive guard. The
[current-build comparison and hashes](benchmarks/vulkan-latency-2026-09-13/guard-ab.json)
and [final GPU checks](benchmarks/vulkan-latency-2026-09-13/guard-gpu-validation.log)
identify the version left in the working tree.

## Retained evidence

The final/control set comprises 160 matrix runs, eight pacing-attribution runs
and 24 CPU-worker runs, plus 12 final copy-contract comparisons (204 total). See the [matrix](benchmarks/vulkan-latency-2026-09-13/matrix.json),
[immutable-input manifest](benchmarks/vulkan-latency-2026-09-13/manifest.json),
[verification](benchmarks/vulkan-latency-2026-09-13/verified.json),
[pacing attribution](benchmarks/vulkan-latency-2026-09-13/pace-attribution.json),
[CPU worker sweep](benchmarks/vulkan-latency-2026-09-13/cpu-paced-workers.json),
[CPU grid quality comparison](benchmarks/vulkan-latency-2026-09-13/cpu-grid-quality.json),
and [GPU sanitizer/validation output](benchmarks/vulkan-latency-2026-09-13/optimized-gpu-validation.log).
The original baseline has separate provenance; it was saved before rebuilding
the experiment. No benchmark binaries or media are committed.
