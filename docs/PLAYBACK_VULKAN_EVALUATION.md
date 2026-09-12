# Playback and Vulkan follow-up — 12 September 2026

The output permission fix is implemented. Performance defaults remain unchanged.
The disputed NJIT classifier accuracy claim is rejected as a design dependency;
its training/validation contradiction has not been scientifically resolved.
This follow-up implements user choices 1a, 2a and 4a, and tests choice 3 within
its video-only scope: no VLC patches, audio DSP, or additional player handling.

## Output permission contract

`src/autoupscale.c` now checks `b_allow_fmt_out_change` before allocating plugin
state or opening a backend. A fixed output must already match the configured
planned target's chroma, coded/visible width and height, and zero crop offsets.
Otherwise Open declines the request without changing output format, callbacks,
plugin state or the owner-controlled permission flag. Permitted changes retain
the configured target.

The permanent `test_output_permission` in
`tests/test_autoupscale_lifecycle.c` covers nine requested formats under both
permission values. Eight forbidden changes failed before the fix; the same
regression passes afterward. Existing lifecycle fixtures now explicitly grant
format changes, matching their intended use.

Actual VLC 3.0.20 playback logs show the plugin producing 1280x720 from 320x180.
Direct playback subsequently inserts a 1280x720-to-320x180 converter; the
transcode-display path instead configures its encoder and final visible video
at 1280x720. Respecting the plugin API does not control VLC's later converters.

## Audio command checks

The plugin processes video only. The launcher already omits audio re-encoding.
VLC still needs ordinary audio decoding/output and volume control to play sound.

The CLI matrix used a generated 16-second MPEG-4/PCM clip, real X11 video
output, a temporary private PulseAudio null sink, and RC volume values
256, 64 and 128. No system default sink was changed. All runs set:

```sh
--audio-filter= --audio-visual=none --no-audio-time-stretch --audio-replay-gain-mode=none
```

These disable optional effects, replay gain and pitch-preserving rate changes.
They do not disable ordinary audio playback. Disabling time stretching also
means altered playback speed can change pitch. VLC's
[normal-rate time-stretch fast path](https://github.com/videolan/vlc/blob/3.0.20/modules/audio_filter/scaletempo.c#L563)
returns the input block directly; removing it does not establish a meaningful
CPU saving at normal speed.

| CLI path | Observed stream volume at RC 256 / 64 / 128 | Final visible video |
|---|---|---|
| `--video-filter=autoupscale` | 100% / 25% / 50% | 320x180 after VLC downscaling |
| Video-only `#transcode{...}:display` with audio passthrough | 50% / 50% / 50% | 1280x720 |
| Same sout plus `--no-sout-audio` | No audio stream | 1280x720 |

Percentages are the output stream's PulseAudio volume, not linear sample gain.
The private stream inherited its initial 50% level and ignored subsequent RC
changes. The monitor recording returned silence even for the direct positive
control, so those recordings are excluded: this matrix establishes stream
control behavior, not an acoustic loudness measurement.

The source explains both failures:
[`display.c`](https://github.com/videolan/vlc/blob/3.0.20/modules/stream_out/display.c#L102)
allocates a private input resource, whereas
[playlist volume](https://github.com/videolan/vlc/blob/3.0.20/src/playlist/aout.c#L43)
uses the playlist resource.
[`es_out.c`](https://github.com/videolan/vlc/blob/3.0.20/src/input/es_out.c#L1751)
deselects audio when sout audio is disabled. Removing audio effects cannot
change resource ownership. REL-16 remains blocked under the current scope.

A command to try without optional audio effects, retaining the enlarged sout
video, is:

```sh
vlc --no-one-instance --avcodec-hw=none --audio-filter= --audio-visual=none --no-audio-time-stretch --audio-replay-gain-mode=none --autoupscale-target=2 --autoupscale-algo=3 --autoupscale-usm=20 --sout='#transcode{vcodec=h264,vb=10000,venc=x264{preset=ultrafast,tune=zerolatency},vfilter=autoupscale}:display' -- path/to/video.mp4
```

Live volume still requires the existing system mixer workaround. No new audio
or control handling is added to the project.

## Controlled VLC playback

**Attribution correction (BUILD-42):** these historical runs did not verify
which AutoUpscale binary VLC selected. `VLC_PLUGIN_PATH` adds a recursive
search to the installed plugin tree. A later reproduction loaded the current
build, two nested scan-build variants and the installed plugin; its behavior
did not match the requested current build. Preserve the numbers below as
historical observations, but do not use them to accept current-code defaults.
An isolated, unmodified VLC runtime and a runtime mapping check are required
for replacement measurements. The standalone backend benchmarks do not load
VLC plugins and are unaffected by this selection problem.

Paired pinning-on/off runs use actual VLC decode, upscale, USM, H.264 encoding,
decoding and X11 display. Two locally encoded public-sample excerpts cover
320x180 animation and 960x540 live action, both 30 fps. Each clip runs three
pairs in on/off, off/on, on/off order. Settings retain the 1080p preset,
Spline36, 20% USM, default worker policy and default sharpness gate. The
observe-only content advisory is disabled for both variants. The existing 4x
linear cap produces 1280x720 for the animation; live action reaches 1920x1080.
Clips contain no
audio, so these runs measure the video path and cannot quantify audio savings.

Each process runs about 15 seconds. CPU measurements span seconds 3–15 to
exclude startup; one-second samples, load averages, temperatures, plugin and
input hashes, exact commands and output-format diagnostics are retained.
These are process CPU measurements, not per-frame filter latency.

| Clip / actual output | Pinned median CPU | Unpinned median CPU |
|---|---:|---:|
| Animation / 1280x720 | 31.83% | 32.75% |
| Live action / 1920x1080 | 76.00% | 81.50% |

CPU percentages use one core as 100%. Pinning consumes less CPU in all six
pairs. Their ambiguous plugin selection prevents attributing that difference
to the current build, or accepting current pinning from these runs.

VLC's RC counters remain zero for this private transcode-display resource,
despite active display and output-format diagnostics. Zero counters are not
zero dropped frames. Reliable presentation tails still require instrumentation
that observes the actual private vout. Baseline acceptance is limited to the
evidence below. PERF-15 retains the unresolved measurement requirements;
these runs do not establish multiple-host behavior.

### Evidence required for baseline acceptance

The user accepts the baseline only where evidence supports it. Acceptance
does not make every current setting a validated performance winner. Keep
existing runtime defaults while separating supported retention decisions
from unproven policy choices:

| Decision | Recorded evidence | Scope of acceptance |
|---|---|---|
| Retain pinning provisionally | Standalone backend measurements remain available; historical VLC playback attribution is withdrawn under BUILD-42. | Repeated playback with one verified plugin is required before extending the evidence to current VLC behavior. |
| Retain zero-copy | The earlier native-cadence, matching-grid comparison gives 277.01 versus 357.27 us/frame with direct versus copied access. Compared final-frame hashes match; permanent pixel regressions cover the tested executor paths. | Supports direct access in the measured configurations; does not prove equivalence after changing graph grids or a GPU path. |
| Treat 8/12/16-worker presets as the reference configuration | The earlier 8/12-worker means nearly tie, with a CPU/tail tradeoff; short and longer motion runs favor different counts. | Preset optimality is not accepted. Defaults remain unchanged while alternatives are investigated. |
| Keep adaptive and GPU replacements experimental | The default-profile adaptive comparison differs by only 0.3%; the tested GPU roundtrip reduces CPU but increases wall time and omits USM/equivalence validation. | Neither experiment establishes a replacement for the current pipeline. |

The [earlier per-frame evidence](DECISION_EXPERIMENTS.md#presets-pinning-and-zero-copy)
also retains the 227.12 versus 368.79 us/frame repeated-control discrepancy.
That discrepancy is not resolved by accepting the baseline. The current
sharpness cutoff is likewise not validated for grainy or heavily compressed
material by these clips; no threshold tuning follows from their results.

Future performance claims must identify the tested input, host, output
geometry, algorithm, worker configuration and measurement boundary. Compare
matched workloads in repeated alternating order; retain raw samples and
report CPU, processing mean and tails separately. Require pixel-equivalence
checks for changes intended to preserve output, investigate control drift
and tail regressions, and validate the measurement itself before claiming
presentation improvements. Broader claims require broader evidence.

The user selected optional plugin processing metrics (2A), direct libvulkan
experiments (3), and a single-output video-splitter prototype (4A). These
choices are settled. Defaults remain fixed; measurements determine adoption.
Private sout presentation counters remain unavailable; plugin processing
metrics do not claim to measure display drops or presentation latency.

## Vulkan feasibility

Both real GPUs enumerate and run Vulkan through RADV/Mesa 26.2.2:
Radeon 610M and RX 6600 XT advertise device API 1.4.354. The loader advertises
instance API 1.3.275. The software llvmpipe device is excluded.

The first explicit FFmpeg `hwupload`/hardware-frame experiment failed on the
RX 6600 XT with `VK_ERROR_DEVICE_LOST`. `scale_vulkan` on the 610M failed shader
compilation with an out-of-range array index. The working experiment instead
lets libplacebo upload and download CPU frames itself. These failures concern
the installed FFmpeg 6.1.1 path, not proof that the GPUs lack Vulkan support.
No driver, operating system or VLC patch was applied.

The comparison uses FFmpeg 6.1.1 with zimg 3.0.5 and libplacebo 6.338.2, the
same 600 packed I420 frames at 960x540, and 12 FFmpeg filter threads. Each
output/backend has three runs in alternating order. The table gives medians:
wall time divided by 600, and total process CPU time divided by 600. Startup,
shader creation, file input, transfers and teardown are included. No decoder,
encoder, display or USM runs in this comparison. The final 18-run batch ran after the audio and VLC playback experiments,
without concurrent agent benchmarks or builds. An earlier overlapping batch
was excluded from this table.

| Output | Backend | Wall ms/frame | CPU ms/frame |
|---|---|---:|---:|
| 1080p | CPU zscale/Spline36 | 0.326 | 1.265 |
| 1080p | RX 6600 XT/libplacebo Spline36 | 1.443 | 0.966 |
| 1080p | Radeon 610M/libplacebo Spline36 | 9.478 | 1.138 |
| 4K | CPU zscale/Spline36 | 0.691 | 3.537 |
| 4K | RX 6600 XT/libplacebo Spline36 | 3.271 | 1.264 |
| 4K | Radeon 610M/libplacebo Spline36 | 37.019 | 1.712 |

All 18 runs finish successfully with 600 output frames. These are batch
throughput averages, not isolated shader timings or frame-latency percentiles.
The discrete GPU reduces CPU consumption but takes about four to five times the wall
time in this tested route. Integrated-GPU 4K throughput falls below 30 fps in this experiment.
Spline36 names do not guarantee matching pixels: color processing, rounding
and chroma handling differ. Image equivalence and the production USM path
remain unvalidated, so these results cannot justify replacing the backend.

The practical first prototype would be an opt-in backend using persistent
Vulkan resources, bounded buffers and GPU scaling plus the current luma USM
semantics, followed by download into the existing output picture. It fits the
current CPU-picture interface but includes transfers. At 60 fps, packed I420
960x540 upload plus output download alone moves about 233 MB/s for 1080p or
793 MB/s for 4K, before padding and display uploads.

A path keeping decoded frames, scaling, USM and display entirely on the GPU
could avoid those roundtrips. That is an architectural inference, not a tested
speedup. The current `scaler_ctx_t` interface accepts CPU picture planes and
declines opaque GPU surfaces. Vulkan
[external memory and synchronization](https://docs.vulkan.org/guide/latest/extensions/external.html)
require compatible handles, ownership and fences/semaphores at both ends;
Vulkan support alone cannot make the current VLC pipeline zero-copy.

Recommendation: retain the CPU backend and existing zero-copy settings.
Consider a separate optional GPU prototype only if CPU reduction is worth
investigating despite current latency results. Require equivalent scaling/USM
output, bounded lifetime/failure tests, and paired end-to-end CPU and tail
measurements before enabling it by default. No GPU backend is shipped here.

## Direct libvulkan experiments and current playback evidence

User choices 2A, 3 and 4A are implemented as optional processing metrics,
direct-library GPU experiments, and a video-only display prototype. Production
quality, worker counts, zero-copy settings and launcher defaults are unchanged.

### Corrected playback attribution

`scripts/playback_runtime.py` copies the unmodified installed `libvlccore`
into a private test runtime, links stock plugins individually, and includes
exactly one requested AutoUpscale binary. It excludes installed and nested
AutoUpscale copies. Each measured process verifies its runtime mappings;
the permanent `test_playback_runtime.py` rejects duplicate, missing and deleted
plugin mappings. System files and installed plugins are unchanged.

Twelve replacement VLC runs repeat the same clips, settings, alternating
pinning order and seconds 3–15 sampling interval as the historical experiment.
All runs exit successfully and identify the requested binary. Median process
CPU, with one core equal to 100%, is:

| Clip | Pinning on | Pinning off |
|---|---:|---:|
| Animation, 1280x720 output | 32.52% | 32.85% |
| Live action, 1920x1080 output | 73.79% | 67.46% |

Pinning lowers CPU in two animation pairs and increases it in every live-action
pair. These results replace the unsupported blanket playback benefit. They
do not prove a universal replacement policy; defaults remain reference settings
while PERF-15 retains the mixed evidence and worker-preset questions. Standalone
matching-grid zero-copy equivalence and timing evidence remains valid.

### Direct GPU measurements

`tests/experiment_vulkan.c` calls libvulkan directly. Its persistent buffers,
descriptor sets, pipelines, command buffers and fences perform host upload,
GPU compute, readback and a CPU-visible output copy. Host allocations prefer
cached coherent memory. The scaler benchmark links the project's zimg backend
for comparison; the sharpening benchmark links its actual CPU worker pool.
Neither Vulkan benchmark links FFmpeg or libplacebo.

The experiment is bounded to 4K pixels, software I420 for scaling, and packed
8-bit luma for sharpening. It does not change the production geometry policy.
`test_vulkan_limits` permanently covers the guard that prevents oversized
single-dispatch requests; its excessive-size tests failed before the guard.

The matrix runs three alternating CPU/GPU pairs per stage, resolution and GPU.
Scaling uses one decoded 960x540 live-action frame, 20 warmup iterations and
120 unpaced measured iterations, comparing 12 pinned zimg workers with a direct
Spline36 compute shader. Sharpening uses deterministic luma, the same warmup
and sample counts, 30-fps pacing, and 12/16 CPU workers for 1080p/4K. These are
stage microbenchmarks. Startup and shader compilation are excluded; Vulkan
measurements include upload, dispatch, completion wait, readback and output
copy. Scaling starts with contiguous I420, so packing VLC's strided input is
not timed. This original matrix measures separate stages. The later latency report adds
combined microbenchmarks; neither matrix measures GPU-backed VLC playback.

| Stage/output | GPU | CPU path wall ms | Vulkan wall ms | Process CPU ms (CPU / Vulkan) |
|---|---|---:|---:|---:|
| scale / 1080p | RX 6600 XT | 0.131 | 1.039 | 1.374 / 0.140 |
| scale / 1080p | 610M | 0.133 | 11.517 | 1.345 / 0.286 |
| scale / 2160p | RX 6600 XT | 0.349 | 3.742 | 3.881 / 0.539 |
| scale / 2160p | 610M | 0.350 | 44.972 | 3.897 / 1.585 |
| usm / 1080p | RX 6600 XT | 0.247 | 0.933 | 2.111 / 0.165 |
| usm / 1080p | 610M | 0.144 | 2.903 | 1.001 / 0.191 |
| usm / 2160p | RX 6600 XT | 0.406 | 3.367 | 4.487 / 0.888 |
| usm / 2160p | 610M | 0.537 | 8.455 | 5.581 / 1.231 |

The direct path succeeds on both GPUs, bypassing the external FFmpeg
hardware-frame failures. Lower process CPU comes with higher per-frame latency
in these implementations. This measures these kernels and transfer strategy;
it does not establish a hardware limit or the performance of a future GPU
resident pipeline.

Sharpening is byte-identical to the CPU reference across random, flat and
high-contrast inputs, eight sharpening amounts including clamp boundaries,
and tiny/odd through 4K geometry. Twelve further runs on both GPUs pass with
the Khronos validation layer and synchronization validation enabled. Those
instrumented timings are not used for performance claims.

The Spline36 prototype is not byte-equivalent to zimg. The recorded per-plane
maximum error and RMSE must be reviewed before any quality-equivalence claim;
the later latency report directly measures tiled/untiled zimg differences and
compares the GPU kernels with an independent global reference. The constant-image property passes. Neither
speed nor equivalent quality currently justifies replacing the CPU scaler.

Build the optional tools with Vulkan headers/loader and the shaderc runtime
available, in addition to the VLC/zimg SDKs already used by the CPU benchmark:

```sh
make BUILD=build-gpu build-vulkan-bench
build-gpu/bench_vulkan build-gpu/vulkan_usm.spv 0 1920 1080 12 120 33333 gpu
build-gpu/bench_vulkan_scale build-gpu/vulkan_spline36.spv 0 2 gpu live-action-540.yuv
```

Device indices are enumerated per process; results identify the actual GPU
name and reject CPU Vulkan devices. `VULKAN_CFLAGS` and `VULKAN_LIBS` can point
to an isolated SDK/runtime. Timings, commands and file hashes are retained in
the direct experiment evidence below.

### Display prototype

`make display-prototype` builds the optional `autoupscale-display` video splitter.
It reuses the existing upscaler through VLC's filter chain and declares one
enlarged output. It adds no audio DSP or player controller. Normal-suite
ASan/UBSan tests cover output format, timestamps, input ownership, allocation
failure and cleanup.

Isolated playback confirms 320x180 to 1280x720 output, native volume commands
changing the stream to 100/25/50%, seeking to 10 and 1 seconds, visible subtitles,
nonzero frame counters, and removal of its window at exit. The sout control
comparison remains at 50% stream volume for all three commands. Subtitle
screenshots were inspected; OCR alone was unreliable on the colored fixture.

Live fullscreen is not validated: bounded adapter probes leave the child window
unchanged or temporarily unobservable, while normal playback enters fullscreen
and restores its original window. VLC's splitter wrapper rejects display control
requests and owns separate child displays. REL-16 retains this integration
requirement. The prototype is not the launcher default and requires an input
eligible for upscaling; no bypass or general GUI support is claimed.

### Implemented latency experiments

The subsequent [latency experiments](VULKAN_LATENCY_EXPERIMENTS.md) implement
GPU timestamps, separable scaling, precomputed coefficients, specialized
pipelines, shared GPU scaling/sharpening, mapped buffers and a no-readback
measurement mode. They retain both winners and losing candidates, compare
paced sequences with unpaced controls, and keep defaults unchanged. The
no-readback experiment does not present a frame through VLC.

### Direct experiment evidence

The original direct-library measurements and corrected playback controls are
retained as [the 48-run matrix](benchmarks/direct-vulkan-2026-09-12/matrix.json),
[the 12 verified playback runs](benchmarks/direct-vulkan-2026-09-12/playback.json),
[display/audio controls](benchmarks/direct-vulkan-2026-09-12/controls.json),
[standalone GPU validation](benchmarks/direct-vulkan-2026-09-12/validation.json),
and [baseline provenance](benchmarks/direct-vulkan-2026-09-12/environment.json).
The environment file labels the earlier FFmpeg snapshot separately; its
historical hashes do not identify the direct-library binaries. Optimized
measurements have their own manifest in the latency report.

## Historical reproducible evidence

The recorded commands and observations are retained as
[VLC playback samples](benchmarks/playback-vulkan-2026-09-12/playback.json),
[audio stream controls](benchmarks/playback-vulkan-2026-09-12/audio-controls.json),
[Vulkan timings](benchmarks/playback-vulkan-2026-09-12/vulkan.json),
[successful and failing GPU smoke logs](benchmarks/playback-vulkan-2026-09-12/vulkan-smokes.json),
and [versions and hashes](benchmarks/playback-vulkan-2026-09-12/environment.json).
The raw excerpts and their source URLs are described in
[the earlier experiment's reproduction steps](DECISION_EXPERIMENTS.md#reproduction).
VLC clips were encoded from those packed 30-fps I420 files using
`ffmpeg -f rawvideo -pixel_format yuv420p -video_size WIDTHxHEIGHT -framerate 30 -i INPUT.yuv -c:v mpeg4 -q:v 4 OUTPUT.mkv`.
Paths in recorded commands identify the local capture workspace; substitute
your own checkout and input paths when reproducing.

## Validation

`make -j4 BUILD=build-perf10 EXTRA_CFLAGS=-Werror check plugin check-hardening check-visibility`
passes, including the permanent lifecycle regression under ASan/UBSan.
`make BUILD=build-perf10 analyze` passes Lizard (CCN <= 10), cppcheck,
ShellCheck, Actionlint, Markdown and offline link checks. The existing nested
Make jobserver warning remains tracked as BUILD-40; no new compiler warning
is introduced. REL-21 is removed from the unresolved ledger.
