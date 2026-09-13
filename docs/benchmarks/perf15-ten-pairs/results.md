# PERF-15 ten-pair numerical results

Measurement complete: 10 matched pairs per B/D option and clip.
60 candidate pairs plus six retained control pairs; 132 paired executions.
The unfinished pair is excluded and retained in the original archive.

Changes use geometric means of paired ratios. Negative means less time or CPU.
Intervals below are conditional family-adjusted paired-log t intervals.
Block sensitivities, all ratios and chronological groups are in analysis.json.

| Clip | Treatment | Mean | p95 | p99 | CPU |
|---|---|---|---|---|---|
| animation | duplicate | -12.1% | -28.2% | -23.5% | -0.3% |
| animation | latency | -5.6% | -7.4% | -7.0% | -1.1% |
| animation | local | +7.4% | +26.6% | +17.0% | -14.4% |
| live-action-540 | duplicate | +1.9% | +18.7% | +8.7% | -1.3% |
| live-action-540 | latency | -3.4% | -8.3% | -2.8% | +1.8% |
| live-action-540 | local | +10.0% | +19.7% | +18.7% | -15.7% |
| motion | duplicate | +12.4% | +36.6% | +11.9% | +6.6% |
| motion | latency | -0.2% | +1.0% | +1.9% | +4.4% |
| motion | local | +3.7% | +25.8% | +13.5% | -14.2% |

| Clip | Treatment | Metric | Change | Conditional interval | Guard failures |
|---|---|---|---|---|---|
| animation | latency | frame_mean | -5.6% | [-16.3%, +6.4%] | 2/10 |
| animation | latency | frame_p95 | -7.4% | [-25.0%, +14.3%] | 1/10 |
| animation | latency | frame_p99 | -7.0% | [-22.3%, +11.3%] | 1/10 |
| animation | latency | processing_cpu_mean | -1.1% | [-7.6%, +5.8%] | 1/10 |
| animation | local | frame_mean | +7.4% | [-19.6%, +43.3%] | 4/10 |
| animation | local | frame_p95 | +26.6% | [-25.2%, +114.3%] | 8/10 |
| animation | local | frame_p99 | +17.0% | [-3.5%, +41.8%] | 7/10 |
| animation | local | processing_cpu_mean | -14.4% | [-22.1%, -6.0%] | 0/10 |
| live-action-540 | latency | frame_mean | -3.4% | [-16.3%, +11.6%] | 2/10 |
| live-action-540 | latency | frame_p95 | -8.3% | [-34.7%, +28.8%] | 3/10 |
| live-action-540 | latency | frame_p99 | -2.8% | [-19.6%, +17.4%] | 4/10 |
| live-action-540 | latency | processing_cpu_mean | +1.8% | [-8.0%, +12.6%] | 2/10 |
| live-action-540 | local | frame_mean | +10.0% | [-5.4%, +27.8%] | 8/10 |
| live-action-540 | local | frame_p95 | +19.7% | [-15.3%, +69.2%] | 8/10 |
| live-action-540 | local | frame_p99 | +18.7% | [+2.0%, +38.1%] | 9/10 |
| live-action-540 | local | processing_cpu_mean | -15.7% | [-23.1%, -7.5%] | 0/10 |
| motion | latency | frame_mean | -0.2% | [-17.7%, +21.0%] | 3/10 |
| motion | latency | frame_p95 | +1.0% | [-32.1%, +50.2%] | 5/10 |
| motion | latency | frame_p99 | +1.9% | [-12.5%, +18.7%] | 5/10 |
| motion | latency | processing_cpu_mean | +4.4% | [-13.5%, +26.0%] | 4/10 |
| motion | local | frame_mean | +3.7% | [-4.6%, +12.7%] | 3/10 |
| motion | local | frame_p95 | +25.8% | [-8.4%, +72.6%] | 9/10 |
| motion | local | frame_p99 | +13.5% | [+1.6%, +26.9%] | 8/10 |
| motion | local | processing_cpu_mean | -14.2% | [-21.5%, -6.1%] | 0/10 |
