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
| PERF-15 | blocked | M | Resolve mixed pinning, worker-preset and repeated-control evidence before claiming a better policy. | User accepts defaults only within demonstrated evidence; remaining settings are a reference, not proven winners. Standalone matching-grid direct/copy measurements support zero-copy. Corrected playback isolates the exact current plugin: animation median CPU is 32.52% pinned versus 32.85% unpinned, but live action is 73.79% versus 67.46%; the former blanket pinning benefit is withdrawn. The 8/12/16-worker presets remain unproven: short/long motion rankings differ and identical controls yielded 227.12 versus 368.79 us/frame. Optional processing metrics are implemented (choice 2A); private sout presentation remains unobserved. The [paced Vulkan/CPU follow-up](docs/VULKAN_LATENCY_EXPERIMENTS.md#cpu-worker-count-follow-up) finds eight scaler workers improve 1080p CPU/tails at nearly equal mean, while 12 beat 16 at 4K; one input/host and graph-seam differences still prevent a universal preset claim. Unblock stronger policy claims with stable matched repeats, CPU and processing tails, representative inputs and any presentation evidence the claim requires. Defaults remain unchanged during experiments. |

## scalability

| id | status | effort | description | notes |
|---|---|---|---|---|

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
| REL-16 | blocked | M | Validate native fullscreen/window integration before adopting the single-output upscaling adapter. | User choice 4A authorizes the video-only prototype and still excludes VLC patches, audio DSP and extra playback handling. `tests/experiment_display.c` preserves 1280x720 output, native volume 100/25/50 percent, seeking and visible subtitles; isolated tests and normal-suite ownership/failure regressions validate those paths. Live RC fullscreen leaves the child window at 1280x720, conflicting with the adoption requirement. VLC 3.0.20 `src/video_output/display.c:1369-1372` implements `SplitterControl` by rejecting every control request. Normal playback enters fullscreen and restores its window; adapter probes leave the child unchanged or temporarily absent. Resolve through a supported video-only API or explicit acceptance of this limitation before replacing the launcher. Prototype remains opt-in; source must be eligible for an upscale. |

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

- **BUILD-44, driver-unload allocations as project leaks:** a loader-only
  `vkCreateInstance`/`vkEnumeratePhysicalDevices`/`vkDestroyInstance` program
  reproduces 512 bytes in two external allocations. The full GPU suite passes
  ASan, UBSan, leak detection and Vulkan synchronization validation with the
  Radeon ICD selected and its library retained by `LD_PRELOAD`. This test-only
  setup avoids unloading the driver's allocation roots; no project leak
  suppression or disabled sanitizer is used. See the direct Vulkan report.


- **OBS-19, private sout presentation counters as a prerequisite for processing metrics:**
  user choice 2A accepts plugin processing metrics. Optional bounded stage/total
  latency and process CPU are implemented with permanent normal-suite tests.
  They do not measure presentation or prove zero dropped frames. The private
  sout counter limitation remains external; never interpret its zero counters
  as observed zero drops.

- **BUILD-41, FFmpeg hardware-frame interoperability as a project dependency:**
  rejected by the user's direct-libvulkan choice. Retain external failure logs
  as historical probe results; they do not block the direct Vulkan prototype
  or establish the performance of a project Vulkan backend.

- **SCAL-10, NJIT classifier accuracy as a controller design dependency:** rejected
  by user follow-up choice 2a. Paper §3.2 describes evaluation on training data;
  §4 calls it validation. This unresolved external claim supplies no evidence
  for this project. No trained controller or default metric change depends on
  it; continue reproducible playback measurements. Reconsider only with source
  data/code, an independent held-out split and measured control benefit.

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
