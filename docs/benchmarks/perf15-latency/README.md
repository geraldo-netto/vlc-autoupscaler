# PERF-15 pilot evidence

The [report](../../PERF15_LATENCY_TRIAL.md) explains the pilot and the separate
100-repeat follow-up. These files preserve the original pilot, without pooling
later measurements or relabeling rejected candidates.

- `paced/`: 44 captures, 22 matched pairs, 23 skipped pairs, original decisions,
  randomized plan, manifests and verified completion; raw CSV traces use gzip.
- `pixels/`: 18 unpaced hash captures and 15 matching 600-frame comparisons.
- `protocol.md`: the exact pre-measurement protocol hashed by both groups.
- `measured-sources.tar.gz`: exact measured source files and both executable
  profiling binaries, with original relative paths from the manifests.
- `validation/`: warning-clean build, permanent red/green tests, full checks,
  complexity, sanitizers and diagnostic-fix logs. Follow-up-tool checks are
  labeled separately from the validation performed before pilot measurement.
- `sha256.json`: archive file hashes, excluding this hash index itself.

Source commit: `0f6cee0`; measured changes were uncommitted. The source archive
captures those changes independently of later working-tree edits. Input YUV
files are identified by hashes and reused from the existing decision-review
clip set; their source descriptions are in the earlier experiment reports.

The original skip labels say "earlier repetition" and "5% guard". OBS-21 later
corrected those diagnostics: the rejection may originate in an earlier pair
of the same nonzero repetition, or from an invalid adaptive outcome. Original
labels remain literal evidence. This correction did not change which pilot
pairs ran or which candidates failed.
