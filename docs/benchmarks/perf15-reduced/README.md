# PERF-15 retained evidence after the budget correction

The user replaced the original 100-pairs-per-case scope with ten matched pairs
per option and clip. See the [current protocol](../../PERF15_TEN_PAIRS.md).

`captures.tar.gz` preserves all stopped-batch files: 51 complete pairs, plus
one unfinished pair excluded from comparisons. `stopped-verification.json`
confirms unchanged source/input/binary hashes and verifies the completed plan
prefix without claiming that the original 660-pair matrix finished.

`measured-sources.tar.gz` contains exact measured sources and executables.
`original-protocol.md`, manifests, plans and paired results remain literal
historical evidence. Later budget corrections do not rewrite them. The
continuation adds only the 15 missing candidate pairs in a separate group.
That [continuation and analysis](../perf15-ten-pairs/README.md) are complete.
`sha256.json` indexes every file here except the hash index itself.
