# Sprint B: reviewed paired CPU pilot

Offline review of easy3489 and medium3494; interrupted3490 retained.

| Parent | Threads | Stop | Runtime s | Final gap % | First observed target s | Sampled cgroup GiB |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| easy | 1 | gap_target | 66.739 | 0.16521 | 66.739 | 0.251 |
| easy | 2 | gap_target | 55.242 | 0.64435 | 55.242 | 0.488 |
| easy | 4 | gap_target | 72.869 | 0.60566 | 72.864 | 0.720 |
| easy | 8 | gap_target | 67.370 | 0.64048 | 67.362 | 1.031 |
| easy | 16 | gap_target | 60.995 | 0.53831 | 60.987 | 1.256 |
| medium | 1 | gap_target | 1449.801 | 9.99932 | 1449.771 | 2.119 |
| medium | 2 | gap_target | 2411.949 | 9.99458 | 2411.949 | 4.871 |
| medium | 4 | time_limit | 3600.924 | 37.04368 | censored | 8.970 |
| medium | 8 | time_limit | 3600.452 | 59.19361 | censored | 17.142 |
| medium | 16 | time_limit | 3601.501 | 56.84084 | censored | 32.056 |

## Development profile

- easy: frontier [1, 2]; selected cap 1; target-reaching coverage 5/5.
- medium: frontier [1]; selected cap 1; target-reaching coverage 2/5.

Strict frontier: first observed target time, process CPU and sampled memory. Select the lowest cap on that frontier. This is an exploratory development choice, not a population-wide optimum.

## Allocation costs (counted once per job)

| Job | Elapsed s | Scheduler CPU s | Allocated logical CPU h | Requested physical-core h |
| --- | ---: | ---: | ---: | ---: |
| 3489 | 328 | 1177.649 | 2.916 | 1.458 |
| 3490 | 1640 | 12632.000 | 14.578 | 7.289 |
| 3494 | 14691 | 49212.000 | 130.587 | 65.293 |

Scope: jobs3489/3490/3494, not the entire historical diagnostic campaign. Full values, speedup eligibility and separate RSS scopes are in the accompanying JSON.

## Limits

- Two fitting parents, one seed, shared node; descriptive development comparison only.
- Easy target 1% and medium target 10%: never pool target times across parents.
- Sampled first observations are not true first crossings; sample counts/drops are retained.
- Successful early-stop gaps are not quality measured at a common 3600-second horizon.
- Time-limit arms are censored, not successful target times or missing-at-random observations.
- Worker RSS, sampled hierarchical cgroup RAM and Slurm step MaxRSS have different scopes.
- Unknown job3490 call count and failure cause remain unknown; all three allocation costs retained.
- Development profile selection is exploratory, not a predeclared held-out statistical conclusion.

Technical Sprint B acceptance is supported by these reviewed returns and the scoped development profile. Existing operational scientific-eligibility flags remain false. Final closure requires code review, exact-head CI and authorized merge; no new optimization or budget is implied.
