# PERF-15 ten-pair measurement and analysis

## Final measurement scope

The user clarified that the original request meant 100 executions total, then
explicitly selected ten matched pairs per option and clip. Ten pairs across
B (local USM placement), D (experimental adaptive tuning), and three clips means
60 candidate pairs or 120 candidate/reference executions. Six completed
control pairs add 12 executions. No additional controls are requested.

The original batch was stopped with 51 complete pairs: 45 candidate pairs
and six control pairs. An unfinished pair contains one completed reference
and an interrupted candidate; retain both records separately and exclude that
pair from comparisons. The continuation completes only the 15 missing pairs
from the original seeded plan's first ten repetitions. It does not rerun or
discard any completed pair. The measurement step ends at ten candidate pairs
per option/clip and proceeds to analysis, without further automatic repetitions.

Original source, binary, input and completed-pair hashes were verified after
stopping. Original raw data, protocol and measured sources are preserved in
the [retained evidence](benchmarks/perf15-reduced/README.md). The continuation
records its own manifest and the original manifest/pair hashes, and checks that
all timed C sources, executables and input clips still match. The Python budget
handling was corrected separately: default 100 means total executions;
`--repeats 10` explicitly requests ten pairs per candidate/clip plus controls.

All capture settings remain unchanged: separate 90-second processes, 30 fps,
existing clips, production-compatible geometry, fixed scaler workers, default
sharpness, and zero-copy. Each new pair keeps its preplanned randomized order
and an adjacent reference. No other benchmarks, builds or analyzers overlap.
The user-directed pause between groups remains visible in capture timestamps.

## Analysis declared before the remaining captures

Keep all complete pairs and every observed regression. Report geometric mean
of candidate/reference run ratios, median, range, each individual ratio, and
the number of pairs exceeding the 5% regression guard. Report absolute p99
processing times and process CPU alongside percentages. Gains strictly above
5% are reviewable; an observed gain does not automatically qualify a policy.

For each candidate/workload/metric, report a paired-log-ratio t interval with
nine degrees of freedom: both individual 95% intervals and Bonferroni-adjusted
intervals across all 24 candidate/workload/metric comparisons. These intervals
are conditional on independent, normally distributed log differences. They
are not assurances that the desktop workload meets those assumptions.

As dependence sensitivity checks, also report circular block-bootstrap
percentile intervals with lengths two and five, 100,000 resamples, and the
same family adjustment. Ten pairs provide few blocks; these are exploratory
sensitivity estimates, not a guarantee of population coverage. Show the
chronological paired values and original-versus-continuation groups. Do not
choose whichever method produces the most favorable result.

The two duplicate-control pairs per clip support descriptive variation only;
do not invent control confidence intervals or treat frames as independent
experimental repetitions. Old 100-pair eligibility and 25-pair/lag-20 screening
rules do not apply to this explicitly reduced study. Regressions, noisy controls
and method disagreement constrain conclusions rather than triggering more runs.
No default changes or preset promotion follow automatically.

## Interpretation limits

Processing-only, short-session results do not establish decode-to-screen
latency, uninterrupted multi-hour playback, energy savings, or generalization
to all video formats. The new adaptive policy is compared with a fixed reference;
this does not establish that it beats the legacy adaptive policy. Pixel-control
results remain those verified against the unchanged profiling binaries.

The paired calculation follows
[NIST's analysis of paired observations](https://www.itl.nist.gov/div898/handbook/prc/section3/prc311.htm).
The dependence limitation follows
[NIST's discussion of autocorrelated measurements](https://www.nist.gov/publications/calculation-uncertainty-mean-autocorrelated-measurements).
The reduced sample budget, interval sensitivity choices, and review criteria
are this experiment's declared choices.
