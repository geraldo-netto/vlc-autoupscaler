# Findings fixes and performance validation

Baseline: `develop` at `32d0867`. Five findings were reproduced with permanent
tests before their fixes. All five are resolved; their rows were removed from
`TODO.md`. Production quality, worker selection, zero-copy and adaptive defaults
are unchanged.

| Finding | Fix | Permanent regression |
|---|---|---|
| UB-13 | Failed dispatch retirement waits for worker exit publication even when joins fail; borrowed pictures remain safe to release | `tests/test_frame_retirement.c`, compiled for real USM and zimg backends |
| ERR-9 | GPU benchmark stderr goes to a retained `.stderr` sidecar while the child runs | `tests/test_benchmark_cleanup.py`: 1 MiB stderr completes; timeout kills and reaps |
| RES-3 | Playback cleanup kills/reaps after quit-write failures, closes stdin and preserves the measurement exception | `tests/test_benchmark_cleanup.py`: live closed stdin, exit during send, quit, timeout and error preservation |
| BUILD-48 | Real-VLC profiling prerequisites and executions require both VLC and zimg SDKs | `tests/test_sdk_boundary.py`: all four dependency combinations; actual SDK-free suite also passes |
| OBS-28 | Evidence validation checks adaptive outcomes against requested mode, bypass state and measured sharpness | `tests/test_perf15_evidence.py`: contradictory outcomes rejected at resume and analysis; legitimate failures retained |

Both frame-retirement binaries failed their `safe` assertion before the fix,
then passed with the same held callbacks, timed completion failure and repeated
join failures. The test retains image storage until cleanup even on the failing
baseline. Existing quarantine/retry tests remain intact. Unreaped pool state
still stays quarantined when joining cannot succeed; frame storage no longer
depends on that join succeeding. Retirement may wait for a running callback;
it does not promise a hard execution deadline.

All regressions remain in `make test`. Tests needing real VLC/zimg headers run
when those SDKs are present; the USM retirement regression always runs.

## Performance checks

The new completion flag is initialized once at thread creation and published
once at thread exit, including cancellation. Only failed retirement polls it.
No per-frame atomic operation, allocation or syscall was added. On this x86-64
build, each thread record remains 64 bytes: the flag occupies existing padding.

The initial cleanup wrapper caused GCC to spill the worker pointer inside its
loop. The final implementation keeps cancellation registration outside that
loop using a compiler-guarded `noinline` helper. Assembly inspection confirms
that the extra loop stack loads disappear. The extracted, unrelocated machine
code bytes for `usm_pool_run_worker` and `zimg_pool_run` match the baseline
exactly; this does not assert identity of the whole binaries or their timing.

Two bounded batches each used ten balanced, randomly ordered pairs per case:
12-worker empty dispatch with 20,000 iterations, and 12-worker scaling plus USM
with 1,500 generated 640x360-to-1280x720 frames. The existing pipeline benchmark
uses Lanczos, 20% USM, direct access and scaler pinning. Ten additional pairs
ran the identical baseline empty-dispatch binary under both labels. Total:
100 executions, sequential, with no agent builds or analyzers overlapping them.
Host: Ryzen 9 7945HX, GCC 13.3.0, native ISA. These are synthetic throughput
checks, not a new representative-video or presentation-latency study.

| Comparison | Median paired time change | Paired range |
|---|---:|---:|
| Initial wrapper, empty dispatch | +13.92% | -24.67% to +28.02% |
| Initial wrapper, scaling + USM | -2.08% | -30.81% to +20.89% |
| Final wrapper, empty dispatch | +4.98% | -36.14% to +57.92% |
| Final wrapper, scaling + USM | +0.37% | -20.85% to +5.21% |
| Identical-baseline empty-dispatch controls | -6.13% | -15.85% to +42.99% |

Positive means slower. The final pipeline's separate run medians are 139.98
and 137.85 us/frame; their ratio differs from the median of paired ratios.
The duplicate controls expose substantial scheduler/host variation. Do not
interpret the final 4.98% as a proven sub-5% overhead bound, or the difference
between batches as an isolated measurement of the helper's benefit. These
results establish neither a repeatable speedup nor a statistically bounded
absence of regression. The unchanged kernel bytes and absence of new per-frame
synchronization support retaining the safety fix; universal optimality is
not established.

Raw [initial](benchmarks/worker-retirement-2026-09-13/initial-results.json),
[final](benchmarks/worker-retirement-2026-09-13/final-results.json) and
[control](benchmarks/worker-retirement-2026-09-13/controls-results.json) captures
include every execution and exact commands. The
[environment](benchmarks/worker-retirement-2026-09-13/environment.json),
[initial manifest](benchmarks/worker-retirement-2026-09-13/initial-manifest.json),
[final manifest](benchmarks/worker-retirement-2026-09-13/final-manifest.json),
[kernel hashes](benchmarks/worker-retirement-2026-09-13/kernel-code.json),
[measured headers](benchmarks/worker-retirement-2026-09-13/measured-headers.tar.gz)
and [file index](benchmarks/worker-retirement-2026-09-13/SHA256SUMS.json) preserve
provenance. Build the baseline revision and replace only its worker header with
the selected archived version to reproduce the benchmark implementation;
use each manifest's build command and capture arguments.

## Architecture priorities

1. **Native video output has the largest demonstrated opportunity.** The
   [existing prototype](PLAYBACK_POLICY_EXPERIMENTS.md#native-video-output)
   avoids the bridge's additional H.264 encode/decode. Its short, matched VLC
   comparisons used 78.1–79.7% less whole-player CPU on two clips. Broader input
   format/orientation/crop support and decode-to-screen validation are required
   before considering it for the launcher. These historical CPU savings are
   not measurements of this fix or guarantees for other videos.
2. **Diagnose the interval before USM before changing scheduling.** Existing
   [PERF-15 traces](PERF15_TEN_PAIRS.md#what-the-existing-traces-suggest-next)
   put 95.2% of reference-tail wall time before USM on average. That timer also
   includes probing and adaptive setup. Separating those intervals and
   correlating worker wakeups can distinguish computation from scheduler delay;
   a new queue or shared pool is not yet justified.
3. **Keep Vulkan experimental until a complete path wins.** GPU-resident
   decode, upscale and presentation could avoid transfer costs, but current
   CPU-picture interfaces require interoperability and lifetime changes. Existing
   [GPU measurements](VULKAN_LATENCY_EXPERIMENTS.md) do not establish a drop-in
   quality-preserving latency winner. No GPU backend or default policy is
   promoted by this cleanup.

## Verification

- Warning-as-error full suite, real zimg harness, ABI/ISA/visibility/hardening
  checks and fuzz smoke passed.
- ASan/UBSan and Clang 18 TSan stress passed: 29 USM configurations, 6,400
  changing adaptive frames and zimg invariants. Pixel-equivalence regressions
  remain intact.
- GCC and Clang production builds passed; Clang static analysis reported no
  bugs for single and multiversion builds. Lizard CCN stayed at or below 10.
- SDK-free `make test` passed with `VLC_CFLAGS= VLC_LIBS=` and zimg installed.
- All 66 complete historical PERF-15 pairs passed the stricter validator;
  failed adaptive outcomes remain valid, nonqualifying evidence.

No multi-hour playback, new GPU timing matrix or cross-platform performance
study was run. The existing baseline remains the supported choice against the
tested alternatives, with the limitations above.
