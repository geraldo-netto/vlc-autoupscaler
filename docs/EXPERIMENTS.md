# Experiment support boundary

Production retains its current CPU scaling path, fused USM, worker policy,
zero-copy/fallback handling and default-off adaptive/metrics options. The
[completed PERF-15 study](PERF15_TEN_PAIRS.md) supports retaining defaults
against the tested B/D candidates under the latency guard. It does not prove
that this implementation wins every CPU, latency, quality or energy comparison.

## Active tools and retained references

| Component | Support policy | Build or use |
|---|---|---|
| General CPU benchmarks and profiling | Maintain for diagnosis and future comparisons | `make build-bench build-profile` |
| Native vout prototype | Retain opt-in; software I420 limitations still apply | `make native-vout-prototype` |
| Direct Vulkan prototype and correctness suite | Retain isolated; no production GPU backend or quality-equivalent replacement claimed | `make build-vulkan-bench test-vulkan` with the documented SDK |
| Public adaptive-USM and processing metrics options | Maintain default-off behavior and permanent tests | Normal plugin build |
| B placement, zero-copy and thread controls | Retain explicit measurement controls | Profiling command/environment recorded by the dedicated runners |

Native output demonstrated lower whole-player CPU cost than the encode/decode
bridge in short trials. Vulkan demonstrated CPU/latency tradeoffs. Those are
reasons to preserve useful references, not to promote either to the default.
See [playback results](PLAYBACK_POLICY_EXPERIMENTS.md) and
[Vulkan results](VULKAN_LATENCY_EXPERIMENTS.md) for boundaries and reproduction.

## Frozen experiments

These implementations are retained for historical replay and regression
coverage. They receive correctness fixes when needed; adoption or further
performance tuning requires a new, explicit experiment scope.

| Reference | Files | Disposition |
|---|---|---|
| Splitter display adapter | `tests/experiment_display.c` | Superseded by native vout; not a recommended playback path |
| Shared/independent executor gates | `tests/experiment_executor.h`, profiling wrappers | Frozen opt-in modes; general profiling uses the original executor |
| PERF-15 D controller | `tests/latency_tuner.h`, latency profiler | No established qualifying gain; excluded from general `build-profile` |
| Flat-skip kernel | `USM_POOL_FLAT_SKIP` in `src/usm_pool.c` | Changes pixels; compile-time disabled in production and excluded from general `build-bench` |

Explicit reference builds:

```sh
make build-frozen-experiments       # splitter, flat-skip and D; requires VLC/zimg SDKs
make build-profile-experiments      # only D's profiling binary
make display-prototype             # historical splitter target remains replayable
make bench-flatskip                 # explicit historical flat-skip comparison
```

For a fresh PERF-15 capture, explicitly build both profiler variants with
`make build-profile build-profile-experiments`. Existing source/binary/measurement
archives remain available for exact historical replay.

Every permanent regression stays in `make test`/`make check`, including frozen
controller, executor, display and profiling cases. CI explicitly compiles frozen
reference binaries without running performance studies. Code remains at its
existing test paths to preserve those fixtures and historical commands.

The small shared tuner observation helper and disabled flat-skip branch are
retained in place: copying production internals into frozen fixtures would add
duplication without a demonstrated playback gain. General build targets no
longer compile their standalone experiment binaries automatically. No public
option, production fallback or diagnostic was removed.

The VLC chain-limit patch under `patches/` is unsupported historical evidence.
Current playback workflows use unmodified VLC and no project audio processing.
