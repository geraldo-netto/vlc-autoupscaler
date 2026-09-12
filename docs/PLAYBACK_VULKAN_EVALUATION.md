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
that observes the actual private vout. PERF-15 remains blocked for an optimal
policy claim; these runs do not change defaults or establish multiple-host
behavior.

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

## Reproducible evidence

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
