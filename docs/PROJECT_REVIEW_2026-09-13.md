# Project review and experimental code retirement

Initial review: `develop` at `c67d685` on 2026-09-13. The review itself changed
only documentation. The subsequently requested fixes are recorded in
[Resolution](#resolution); findings and reproductions below describe the
reviewed revision, not the repaired checkout.

Recommendation: keep the production baseline and selectively freeze superseded
experiment drivers. The data does **not** establish superiority over every
alternative. Most experimental code is outside the production plugin, so
deleting it has no demonstrated playback performance benefit.

## Scope and method

Inventoried production sources, tests and stubs, fuzz corpora, scripts, Makefile,
CI/configuration, documentation and the retained patch. Excluded working
build/cache directories, generated objects, bytecode and Git internals from
the source scan. Published benchmark archives are evidence, not disposable
cache; checked the relevant reports and replayed final PERF-15 trace validation.

The inventory includes 29 production files, 25 script files, 133 test/helper/stub
files and 132 corpus seeds. Manual review concentrated on production ownership,
arithmetic, geometry/format validation, fallback, pool publication/retirement,
adaptive state, metrics, experimental boundaries and benchmark provenance.
Automated analysis covered the repository's configured source/test/script scope.
This is not a claim of manually checking every corpus byte or every historical
capture, or of testing every platform and video format.

Verification outputs were created under `/tmp/vlc-autoupscaler-review-20260913`
and separate `/tmp/vlc-review-*` paths. Existing local lint executables and the
documented Vulkan header SDK were used as dependencies, not scanned as project
source. No playback performance study was repeated during this review.

## Findings recorded in TODO

Ten entries were added to the [ledger](../TODO.md), with exact sources,
resolution conditions and required permanent regression coverage. Completed
entries are removed from that ledger; this table preserves the review context:

| ID | Finding | Practical implication |
|---|---|---|
| BUILD-46 | Analysis archive omits an imported Python module | Documented empty-directory replay fails before analysis starts |
| OBS-23 | Generic analysis/resume trusts derived pair data | Edited ratios or missing captures can pass those validation boundaries |
| OBS-24 | General profiler inherits unrecorded input controls | The same recorded command can process different source geometry |
| ERR-3 | Timeout exits before saving a capture row | Failed attempts lose structured command/environment/output diagnostics |
| BUILD-47 | USM TSan cannot start reliably on this host | USM/adaptive race-detector coverage remains unverified in this review |
| REL-24 | Old decision report presents resolved status as current | Readers can mistake completed bounded decisions for outstanding blockers |
| REL-25 | Current usage guide still recommends a VLC patch | Guidance conflicts with the user's no-VLC-patches scope |
| REL-26 | Stale worker, USM and module descriptions | Comments/help misdescribe current policy, implementation and preset scope |
| PERF-16 | Universal-superiority premise exceeds the evidence | It cannot justify deleting every alternative |
| ARCH-15 | Superseded experiment drivers remain active tooling | Selective isolation can reduce maintenance and clarify supported paths |

`blocked` follows the project's rule for unresolved contradictions, plus the
external TSan obstacle. It does not mean every entry needs a user decision.
The four behavioral tooling defects are directly fixable with permanent tests
added first, demonstrated failing, then passing. Documentation findings require
correction without artificial behavioral tests. ARCH-15 is open maintenance work.

No new production security, UB, ownership or concurrency defect was confirmed.
Passing checks and bounded review do not prove those classes are absent.

### Reproductions and evidence integrity

**BUILD-46:** extract only
`docs/benchmarks/perf15-ten-pairs/analysis-sources.tar.gz` into an empty directory;
run `python3 build/perf15/analyze_ten_pairs.py --help` there with repository
directories absent from `PYTHONPATH`. It exits 1 with
`ModuleNotFoundError: No module named 'bench_playback_policies'`.
The archive includes `bench_perf15.py`, whose import requires that omitted file.

**OBS-23:** copy only the final archive's `verified.json`, `pairs.json` and
`plan.json` into a temporary directory. Change the first
`ratios.frame_p99` from `1.0232249509606797` to `0.01`.
`perf15_statistics.checked_pairs(directory)` accepts it without raw captures.
A separate resume fixture with an empty `results.json`, its correct hash,
and a `pair.json` claiming ratio `0.01` is accepted by `collect_pair` and
`verify_evidence`. Hashing raw files alone does not validate their interpretation.
The final archived verifier performs additional checks; do not confuse it with
the weaker generic entry points.

**OBS-24:** call `profile_project.run_case` for
`pipeline_case('review', 4, 4, 1280, 720)` with eight frames and all allowed CPUs.
Compare a clean `UP_PROFILE_*` environment with
`UP_PROFILE_WIDTH=320 UP_PROFILE_HEIGHT=180`. The recorded command is identical;
output hash changes from `78444727a6ea1325` to `6924aa0f7550d137`.
Neither source dimensions nor input provenance are recorded in the result.
With `UP_PROFILE_ZEROCOPY=0 UP_PROFILE_ADAPTIVE=1`, the clean baseline's
`zerocopy=1, adaptive_outcome=fixed` becomes `0, searching`; those resulting
mode fields are visible, but their inherited controls are not recorded.
These eight-frame probes demonstrate behavior, not performance differences.

**ERR-3:** inject `subprocess.TimeoutExpired` at `bench_perf15.subprocess.run`
while invoking `checked_capture`, supplying partial stdout and stderr.
The exception propagates; the results list has zero rows and the fresh output
directory has no files. Existing successful captures are not deleted.

The real PERF-15 data passed fresh verification: all **43 files** listed by
the stopped/final archive SHA-256 indexes matched. After supplying the omitted
module through the current checkout's `scripts` import path, the archived
`verify_ten_pairs.py` accepted all **66 pairs, 132 executions and 356,400 frames**.
Raw summaries, pair ratios, outcome flags and disabled timed pixel hashing
matched. Only temporary extracted copies were used. This workaround confirms
the data checks; it does not repair the archive's self-containment defect.

## What the performance data supports

| Comparison | Observed result | Valid conclusion and limit |
|---|---|---|
| PERF-15 B, local USM placement | 14–16% less processing CPU; 13–19% worse p99 | Reviewable CPU saving, rejected under the retained latency guard |
| PERF-15 D, experimental adaptive tuning | Animation p99 point estimate improves 7%; intervals cross no change on all clips | No established gain above 5%; keep defaults |
| Native output versus encode/decode bridge | 78.1–79.7% less VLC process CPU | Useful prototype; three short repeats on two video-only clips, not display-latency proof |
| RX 6600 XT, paced 1080p scale plus USM | GPU CPU time 0.259 versus 3.193 ms/frame; p99 1.816 versus 2.493 ms; mean 1.310 versus 0.561 ms | Lower CPU cost and p99, higher mean/p95 in that bounded matrix; scaling pixels differ |

Sources: [final PERF-15 analysis](PERF15_TEN_PAIRS.md),
[matched native playback comparison](PLAYBACK_POLICY_EXPERIMENTS.md#matched-playback-cpu-comparison),
and [direct Vulkan measurements](VULKAN_LATENCY_EXPERIMENTS.md).
CPU percentages in the playback study refer to one logical core; the GPU
table reports processing CPU time per frame. Neither measures energy.

The ten-pair study is complete at the user's selected scope. Broad intervals,
two duplicate controls per clip and visible control variation limit inference;
they do not require reopening the run budget. These short tests also do not
establish behavior throughout a three- or four-hour playback session.

## Experimental code retirement

The freshly linked `libautoupscale_plugin.so` directly needs `libvlccore`,
`libswscale`, `libzimg` and `libc`. It contains no experimental Vulkan,
display-adapter, alternate-executor or latency-controller entry points.
`tests/profile_zimg.c` and `tests/profile_usm.c` inject experimental behavior
into profiling builds; that is not the production build path.

| Component and files | Recommendation | Implication |
|---|---|---|
| Persistent pools, fused USM, CPU policy and zero-copy in `src/` | Keep | These are the current implementation and tested optimizations |
| `scaler_swscale.c` and zimg scratch/copy paths | Keep | Swscale covers formats/no-zimg builds and fallback; copies cover alignment and tiled output constraints |
| `pipeline_metrics.h` and production metrics wiring | Keep, default off | Useful real-player diagnostics; no evidence that deleting them materially improves playback |
| `usm_adaptive.h`, `worker_tuner.h`, public adaptive-USM option | Keep, default off | Existing opt-in public behavior; D is a different controller, not evidence for deleting this option |
| `tests/latency_tuner.h`, latency profiler target | Freeze as experimental reference | D failed promotion; avoid more active tuning by default. Its 67-line policy is a small removal target |
| `up_tuner_observe_with` in `src/worker_tuner.h` | Consider isolating its experiment seam with D | Production passes the legacy handler; optimized plugin has no standalone seam symbol, so no speedup is established |
| `tests/experiment_executor.h`, alternate executor profiling drivers | Freeze/isolate superseded candidates | Reduces live experiment choices; keep the generic profiler, useful pinning/zero-copy controls and production pool implementation |
| `tests/experiment_display.c`, `display-prototype` target | Best retirement candidate | Superseded splitter has inferior window/fullscreen integration; preserve its permanent regression fixtures |
| `tests/experiment_vout.c`, native runtime validation | Retain opt-in | CPU saving and native volume/window controls justify keeping it; adoption still needs broader format/presentation validation |
| Vulkan implementation, shaders and correctness tests | Retain an isolated reference | Direct Vulkan answered the user's question and exposes CPU/latency tradeoffs; no production GPU backend exists to remove |
| `USM_POOL_FLAT_SKIP` and `bench-flatskip` | Candidate for moving out of production source | Disabled at compile time; changes pixels when enabled. Removal would simplify source, with no default-runtime gain |
| Benchmark capture, statistics, raw archives and regression tests | Keep; repair findings first | Needed to challenge conclusions, reproduce evidence and prevent old bugs returning |

Freezing means ending active adoption/tuning work and clearly separating replay
or test fixtures from supported entry points. It does not mean removing,
skipping or weakening permanent regressions. Any later retirement must preserve
those tests in the normal suite, even where frozen implementation fixtures are
needed. This requirement limits how much code/test maintenance deletion saves.

Avoid reverting entire experimental commits: they also contain genuine fixes,
diagnostics, pixel-equivalence checks, input validation and failure handling.
`pipeline_metrics.h` also uses the worker tuner's scoring helper, so deleting
`worker_tuner.h` would break retained functionality. Deleting public adaptive,
algorithm, worker or zero-copy options would change supported behavior.

Suggested order: repair archive/provenance/error reporting; correct current
documentation; then isolate the superseded splitter and benchmark-only choices.
Reassess whether D's small seam is worth changing after that. No new performance
claim should be attached to this maintenance cleanup without measuring an actual
production binary difference.

## Validation

- Fresh `make -j4 BUILD=/tmp/vlc-autoupscaler-review-20260913 EXTRA_CFLAGS=-Werror
  check plugin check-hardening check-visibility`: passed, including the normal
  ASan/UBSan suite and ABI/ISA checks.
- `make analyze`: passed lizard's CCN gate, shellcheck, actionlint, Markdown/link
  checks and cppcheck's configured 76-file scope. Cppcheck excludes the real VLC
  lifecycle TU; that scope was supplemented by compiled lifecycle tests and
  Clang analysis of the actual production plugin.
- `make test-zimg fuzz-smoke`: passed, including randomized scaler seams and
  cross-SIMD byte-equivalence checks.
- `make scan-build SCAN_BUILD=scan-build-18 SCAN_CC=clang-18`: passed both single
  and multiversion production builds; no analyzer reports.
- Vulkan correctness suite: passed on both enumerated hardware devices with
  ASan/UBSan, leak detection and synchronization validation. Used the documented
  Vulkan header override and loader library, selected the Radeon ICD, and kept
  the Radeon library loaded with `LD_PRELOAD`, with `libasan` first. No project
  leak suppression or disabled sanitizer was used.
- ASan/UBSan USM/adaptive stress and zimg TSan invariants passed. The aggregate
  `make stress stress-zimg` command exited 2 because USM TSan aborted at startup.
  Both USM/adaptive TSan binaries still failed with address randomization
  disabled and non-PIE builds. An empty TSan program reproduced exit 66 and
  `FATAL: ThreadSanitizer: unexpected memory mapping`. BUILD-47 records the
  remaining validation gap; this is not a project race report.
- Final PERF-15 archive hashes and all-frame verifier passed with the explicit
  import-path workaround described above. The new review and TODO also passed
  direct Markdown/link validation and `git diff --check`.

No new live VLC playback, multi-hour soak, power measurement or cross-platform
performance comparison was performed. Existing playback evidence is identified
as historical and bounded rather than presented as newly reproduced here.

## Resolution

The follow-up implements the review's bounded conclusion: retain defaults
against the tested candidates under the latency guard. The
[support boundary](EXPERIMENTS.md) classifies active tools and frozen references;
general benchmark/profile builds exclude standalone flat-skip and D binaries,
while explicit reference builds and every permanent regression remain available.
The small shared observation helper and disabled flat-skip branch stay in place
to avoid duplicating production internals solely for historical fixtures.

- BUILD-46: the repaired archive adds the exact omitted dependency from the
  measured-source archive. The original analysis package is preserved as
  `analysis-sources-v1.tar.gz`; measurements, manifests and reported statistics
  are unchanged. The archive-only import regression failed before and passed
  after repair.
- OBS-23: both resume and analysis validate required file hashes, saved/planned
  identities, capture order, all raw frame summaries, metric ratios and outcome
  flags. Regressions cover missing/edited captures, removed hashes, edited
  summaries, false ratios/outcomes and mismatched capture jobs. Valid failed
  performance guards remain analyzable; their data is never discarded.
- OBS-24: general profiling clears inherited controls and records explicit
  generated-input settings. Raw-input experiments use dedicated runners with
  input provenance. The environment-contamination regression passed after
  failing on the original runner.
- ERR-3: timeout records retain command, environment, duration and available
  stdout/stderr before capture fails. The incomplete pair stays unreplayable
  without manual inspection; the normal-suite regression covers retention and
  analysis rejection.
- REL-24/25/26: current guidance identifies superseded status, uses unmodified
  VLC, and accurately describes AUTO policies, fused USM, source references and
  explicit presets. The patch remains unsupported historical evidence.
- BUILD-47: Clang 18 passed the unchanged USM/adaptive and zimg stress suites
  under ASan/UBSan and TSan. USM passed all 29 configurations; adaptive passed
  6,400 changing frames with byte-identical output. The documented fresh-build
  command changes the test compiler/runtime, with no suppression or skipped test.

New behavioral regressions are part of `make test` and `make check`:
`tests/test_perf15_archive.py`, `tests/test_perf15_evidence.py` and
`tests/test_profile_project.py`. Existing confirmation assertions remain intact;
their synthetic capture fixture now contains valid raw evidence so it can pass
the stricter verification boundary.

Post-fix validation passed `make check plugin check-hardening check-visibility`,
general/frozen builds, and `make analyze`. Both the new strict validator and
the self-contained archived verifier accepted all 66 historical pairs, 132
executions and 356,400 frames. Every original analysis-archive member remained
byte-identical; exactly one measured dependency was added. A real eight-frame
profiler control produced identical pixels and recorded settings with and without
the contaminating input/policy environment. Resolved entries were removed from
`TODO.md`; no defaults, public options or permanent regressions were removed.
