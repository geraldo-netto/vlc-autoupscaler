# TODO — full-project audit findings

## security

| id | status | effort | description | notes |
|---|---|---|---|---|

## undefined behavior

| id | status | effort | description | notes |
|---|---|---|---|---|

## memory management

| id | status | effort | description | notes |
|---|---|---|---|---|

## performance

| id | status | effort | description | notes |
|---|---|---|---|---|
| PERF-11 | open | M | Measure opt-in adaptive USM on paced decoded video. | `tests/bench_adaptive.c` deliberately keeps USM active on synthetic noise. [BENCHMARKS.md](docs/BENCHMARKS.md#adaptive-usm) now documents the matching `--autoupscale-usm-sharp-threshold=0` override and reports the actual algorithm/pinning/outcome. The [decoded-video matrix](docs/DECISION_EXPERIMENTS.md) exercises the default 3500 cutoff with fixed USM pools. Extend that paced harness to adaptive USM, retaining explicit fallback outcomes, exploration/retirement costs and mean/tail/CPU comparisons; fixed-pool video results do not establish adaptive playback gains. |
| PERF-13 | open | M | Compare bounded USM affinity and stage-to-stage locality policies on representative paced input. | With the same 8x1 zimg grid and 12 USM workers at 1080p, five-run median means are 278.9 us on eight physical cores sharing one L3 versus 404.3 us across four physical cores in each of two L3 domains; the local placement also wins at USM counts 4/8/16/32. [Raw results and limits](docs/PROFILING.md) retain the identical-grid hashes and actual CPU masks. This changes whole-process placement and does not isolate cache effects from scheduler/coordinator/frequency effects. Compare a benchmark-only USM placement policy with the existing scheduler-managed pool before introducing production topology discovery, preserving pixels and measuring mean/tails/CPU on multiple hosts; no universal affinity policy is established. |
| PERF-15 | blocked | M | Establish stable paced controls before changing presets or declaring pinning optimal. | Continuous-loop preset gains conflicted with earlier 60-fps regressions. The [102 decoded-video runs](docs/DECISION_EXPERIMENTS.md#results) now cover default sharpness gating, 30/60-fps cadence, CPU/tails, one-minute repeats and paired follow-ups. Identical 720p animation controls still give 227.12 versus 368.79 us/frame across three-run groups; native-cadence 8/12-worker means nearly tie, and pinning has mixed tail results. This also retains the repeated-control contradiction first recorded as PERF-16. User requires defaults unchanged during metric research. Unblock a best-policy claim with reproducible paired ordering and representative end-to-end playback across clips/hosts; retain existing presets and pinning meanwhile. |


## scalability

| id | status | effort | description | notes |
|---|---|---|---|---|
| SCAL-10 | blocked | M | Resolve the ML paper's conflicting evaluation claims before using them to justify a trained controller. | [NJIT §3.2](https://arxiv.org/pdf/2312.11790) evaluates the neural model on the training data, whereas §4 attributes accuracy to validation data. Unblock with reproducible data, code and an independent held-out split plus end-to-end control measurements. [Primary-code review](docs/BENCHMARKS.md#bbr-research-and-transfer-limits) resolves the BBRv1 loss interpretation: Linux v6.8 uses loss in recovery, probe termination and policer estimation. User choice 4b authorizes experiments and metric collection only; default control behavior stays unchanged. |

## concurrency

| id | status | effort | description | notes |
|---|---|---|---|---|

## code complexity

| id | status | effort | description | notes |
|---|---|---|---|---|

## code duplication

| id | status | effort | description | notes |
|---|---|---|---|---|

## architecture/modularity/SOLID

| id | status | effort | description | notes |
|---|---|---|---|---|

## decoupling

| id | status | effort | description | notes |
|---|---|---|---|---|

## business/design patterns/DDD

| id | status | effort | description | notes |
|---|---|---|---|---|

## reliability/correctness

| id | status | effort | description | notes |
|---|---|---|---|---|
| REL-16 | blocked | M | Restore live VLC volume controls for the transcode-display profile; displayed control changes conflict with the unchanged audible stream. | User choice 8 excludes audio-processing work; the launcher now passes audio through without requesting re-encoding. Confirmed control-ownership limitation for the Nemo profile, not an upscaler DSP defect: [VLC 3.0.20 display.c:102,150](https://github.com/videolan/vlc/blob/3.0.20/modules/stream_out/display.c#L102) gives its decoder a private resource; [playlist/aout.c:43-46,65-74](https://github.com/videolan/vlc/blob/3.0.20/src/playlist/aout.c#L43) controls the playlist resource instead. The earlier CLI matrix reproduced unchanged audio under RC volume changes; core/audio-filter gain at 0.25 attenuated it by 12 dB. Unblock by choosing requirements: system mixer plus documented fixed `--gain` is a workaround; a normal receiving VLC process restores the correct ownership but live piping adds process/lifecycle work and loses ordinary file seeking (pre-transcoding preserves seeking at storage/startup cost); a VLC control-routing patch can preserve native controls, one process, and seeking but needs maintained integration and lifetime/feedback tests. Direct playback avoids private audio ownership, but preserving enlarged video then needs separate VLC vout integration. Changing `--aout`, volume step, or disabling sout audio does not repair ownership. |

## portability/standards conformance

| id | status | effort | description | notes |
|---|---|---|---|---|

## error handling

| id | status | effort | description | notes |
|---|---|---|---|---|

## resource management

| id | status | effort | description | notes |
|---|---|---|---|---|

## API/ABI stability

| id | status | effort | description | notes |
|---|---|---|---|---|

## build/toolchain hygiene

| id | status | effort | description | notes |
|---|---|---|---|---|
| BUILD-40 | open | S | Preserve or deliberately clear GNU Make jobserver state in shell regression fixtures. | `make -j4 check` reports jobserver-unavailable warnings from nested Make invocations in the install/benchmark shell tests. Mark recursive recipes appropriately or sanitize inherited jobserver flags for isolated fixtures; verify parallel checks without these warnings. |

## observability

| id | status | effort | description | notes |
|---|---|---|---|---|


## wiring gaps

| id | status | effort | description | notes |
|---|---|---|---|---|

## unused functions/methods

| id | status | effort | description | notes |
|---|---|---|---|---|
| UNUSED-6 | open | S | Remove obsolete variable-mutation shims from the lifecycle VLC stub. | `tests/lifecycle_stubs/vlc_common.h:10-12,19-43` declares `lifecycle_var_create/destroy/set_integer` and defines forwarding helpers/macros for `var_Create`, `var_Destroy`, and `var_SetInteger`, but repository-wide searches find no consumers or implementations. Only the inheritance shim is used by the current lifecycle code. |

## Audit picks deliberately rejected

Recorded so future full-project rescans do not repeatedly promote the same
non-findings:

- **SCAL-1a--SCAL-1d, cgroup CPU-aware worker sizing:** rejected. The existing
  affinity-aware count, 12-worker automatic cap, and explicit user override
  handle the supported desktop workload; robust v1/v2/hybrid cgroup discovery
  would add proc/sysfs parsing and failure policy with no measured need.
- **SCAL-2a--SCAL-2d, cgroup memory-aware AUTO target selection:** rejected.
  AUTO deliberately does not inspect host or cgroup RAM: user configuration
  selects quality, and allocation failures follow the established graceful
  failure path. A memory-derived target would violate that runtime policy; no
  memory-pressure regression was reproduced within the bounded worker setup.
- **SCAL-3b--SCAL-3d, topology-aware pin ordering:** rejected. Pinning the
  existing allowed-CPU order is byte-equivalent and improved the measured host;
  sibling/NUMA discovery would be Linux-specific policy without a demonstrated
  production contention benefit.
- **SCAL-P1d, dynamic work queues:** rejected. Completion skew occurs even with
  no partitioned work, identifying scheduler wake delay rather than unequal
  tile cost; a queue would add synchronization and failure paths without a
  measured problem it can solve.
- **REL-17, distinct AutoUpscale launcher icon:** rejected. The entry is
  intentionally a visibly named VLC launch profile, keeps VLC's icon to identify
  the actual player, and uses a separate desktop ID without changing stock VLC
  or MIME defaults. A custom icon would add packaging and maintenance for a
  cosmetic ambiguity that the `VLC (AutoUpscale)` name already distinguishes.
- Adding a CI threshold for in-place USM halo snapshots: the paired alias-mode
  benchmark found no consistent in-place regression on the measured host, and
  cache/write differences prevent the comparison from isolating copy cost.
- Moving USM halo snapshots into workers: PERF-P1a found no repeatable
  bottleneck, so an extra readiness phase would add synchronization risk
  without measured benefit.
- Defining a max-ISA dispatch policy: repeated Ryzen 9 7945HX matrices found
  AVX-512 faster than AVX2 in 17 of 18 medians and effectively tied in the
  other; widest-supported dispatch remains the evidence-backed policy.
- Adding a load-time max-ISA override: no wider-ISA regression was confirmed,
  while single-baseline builds already provide a diagnostic workaround.
- Adding a zimg resource budget: measured 1--16-worker 720p runs stayed below
  9 MiB process RSS; lazy startup rose from about 3 ms to 13 ms but is a
  bounded one-time cost, not evidence for reducing steady-state parallelism.
- Applying a zimg resource-derived worker cap: the measured resource budget
  did not cross a material threshold, so no cap value has a valid basis.
- Sharing zimg graphs or temporary buffers: the prerequisite worker cap was
  rejected, and measured memory remains bounded without concurrency coupling.
- Splitting one worker budget between sequential zimg and USM pools: combined
  pipeline RSS stayed below 8 MiB, while dividing the measured 12-worker knee
  would reduce each stage's available parallelism without lowering frame work.
- Adding a backend-neutral worker job descriptor: the independent-pool
  measurements found no material resource pressure requiring lifecycle reuse.
- Sharing one persistent worker lifecycle between zimg and USM: its job
  descriptor prerequisite was rejected, and the lifecycle/failure coupling
  would be disproportionate to the measured sub-8-MiB combined footprint.
- Adding weighted static partitions for worker skew: the no-work completion
  benchmark reproduced skew, identifying wake/scheduling delay rather than
  unequal stripe cost; changing geometry cannot make late workers start sooner.
- Integrating weighted static partitions: the prototype prerequisite was
  rejected because measured completion skew exists without partitioned work.
- Replacing condition broadcast with tree wake: after the 12-worker cap, the
  measured pipeline still gained about 28 us/frame from 8 to 12 workers while
  the empty-dispatch cost was about 17 us; current wake remains net-positive
  without adding another failure-sensitive synchronization topology.
- Integrating an alternate wake strategy: no prototype beat broadcast, so
  there is no winning strategy to place behind the shared pool gate.
- Changing the zimg automatic stripe minimum from 16 to 24: on the tiny
  64x64-to-128x128, eight-worker I420 case, 16 keeps copy and source-direct
  paths at an 8x1 grid, while 24 changes them to 5x1 and 4x2 respectively.
  Their independent graph phases differ in 20,515 visible bytes (maximum delta
  255 on noise); source-direct and full-zero-copy remain byte-identical. A
  current five-pair, interleaved 600-frame pipeline sample also made 24 slower
  (median 150.44 versus 141.39 us/frame), so neither quality nor performance
  supports changing the default.
- Unifying `worker_copy_in_stripe` / `worker_copy_out_stripe` /
  `worker_copy_out_tile`: their direction and offset invariants differ; a generic
  helper would require a wide parameter surface.
- Adding a pool-wide cleanup hook solely because `prepare` is a pool callback:
  shared allocations are explicitly owner-owned and both owners release them;
  permanent-failure paths now initiate retirement immediately.
- Treating `lazy_done` / `lazy_failed` as an atomicity defect: VLC's video-filter
  callback contract serializes the lifecycle; revisit only if that contract
  changes.
- Removing per-worker boundary-row re-blur: the small duplicate computation is
  the invariant that permits barrier-free, race-free in-place USM.
- Adding alignment assumptions to USM vector loops: valid row alignment depends
  on width/stride, and prior measurements found no actionable gain over
  unaligned moves.
- Treating zimg temporary-buffer alignment as an overflow seam: zimg 3.0.5 uses
  checked internal size arithmetic, graph dimensions are capped at 32768, and
  returned x86 temporary sizes are already 64-byte aligned; the value cannot
  approach `SIZE_MAX - 63` on a reachable production graph.
- **ARCH-R1, full Rust rewrite:** rejected for the current implementation. The
  VLC 3 descriptor, picture-plane access, zimg/libswscale calls, CPU-feature
  dispatch, affinity, and persistent worker publication would retain a material
  `unsafe` FFI/concurrency surface, while replacing a mature 6.5k-line
  production implementation inside a 22k-line source-and-test system. The
  2026-08-20 evaluation found no open UB, memory-management, or concurrency
  defect and re-ran `make check plugin check-hardening check-visibility
  BUILD=build-rust-eval EXTRA_CFLAGS=-Werror` successfully. Revisit only for a
  measured hot-path win, recurring C safety defects, a Rust-first maintainer
  base, or a broader portability goal; use a small differential-tested kernel
  prototype before considering migration.
