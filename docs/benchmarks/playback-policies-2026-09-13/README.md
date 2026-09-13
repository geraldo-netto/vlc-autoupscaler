# Playback policy evidence

See the [report](../../PLAYBACK_POLICY_EXPERIMENTS.md) for methods, conclusions
and limits. All matrices ran sequentially on one host. The baseline commit
was `c0508e6` on `develop`, with the experimental changes in the working tree.

- `cpu`: 72 fixed-worker and USM-placement comparisons.
- `adaptive`: 12 fixed/adaptive 1080p comparisons; animation at this geometry
  is a direct-backend stress case beyond playback's 4x ratio cap.
- `adaptive-720`: six animation comparisons at production geometry and its
  automatic eight-worker USM budget.
- `gpu`: 72 direct-libvulkan cadence controls, telemetry and stage profiles.
- `native-playback`: 12 native/bridge playback comparisons with matched
  processing geometry and window size within each pair.
- `native-controls`: final real-VLC fullscreen, resize, subtitle, seek,
  native-volume and cleanup regression.

Each matrix retains `manifest.json` and `verified.json`. Numbered `.csv.gz`
files are the original per-frame traces; `.log.gz` files retain raw logs.
The GPU's `results.json.gz` includes full sensor samples. Compression is
lossless and uses a fixed gzip timestamp.

CPU and initial 1080p adaptive `results.json` retain the originally emitted
`trace_summary`, including the OBS-20 fixed-pool exploration misclassification.
Use `corrected-classification.json` for exploration counts. The correction
changes no timings. Trace `workers` means incumbent pool size, not every
transient trial's size. The two measured runner snapshots retain the exact
helper versions named by the earlier manifests; the current runner adds the
720p matrix and corrected classification.

GPU sensor clocks include idle intervals and firmware averaging. They are
not active-kernel clock measurements. Telemetry-free controls determine
the reported ranking; no driver power setting was changed.

After measurement, the GPU runner's summary helper was split to meet the
CCN limit. Sampling and timing code are unchanged. All 72 archived summaries
exactly match the refactored helper; `analysis-validation.json` records this
check and both source hashes. The measured manifest retains the original hash.

Native playback playlist counters are observed only for the native output.
The bridge's zero counters are not evidence of zero drops. No run measures
decode-to-screen latency. The subtitle PNG is a synthetic test fixture.

`publish.py` records how raw outputs were copied and compressed.
`sha256.json` covers the published files except itself.
The `validation` directory retains the final automated checks and the
complexity gate's failing and passing runs.
