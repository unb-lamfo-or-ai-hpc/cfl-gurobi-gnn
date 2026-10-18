# Jobs3645–3650 — 18 October 2026

Original `public_return.json` SHA256:
`4088a2d464ec1d1874b249b7aeed0e720a55bf36e35dfb329d859fb853b709d7`.
Source `34e470752988ec938605ae22dcaab6b4a03b4395`; plan
`05685508e7dd657993028fa5948dc1453145f0bb8d3915a9b4eec9c354c2ba17`.
Original bytes and false eligibility flags remain unchanged.

`review_pr86_wave61.py` regenerates `review.json`, the cumulative 201-row CSV,
four CPU gap/memory SVGs and the output manifest offline. See
[what/how/why and execution boundary](../../../research/pr86-wave61-numeric-review.md).
201 collected cells are not 201 independent parents or certified optima:
168 previous/non-M4/M12 scoped observations,21 M4-sensitive observations,
12 M12 observations awaiting numerical qualification. The final nine solves
are not released by these artifacts. M4's prior limitation remains intact.

```text
python -B scripts/evidence/review_pr86_wave61.py --output docs/evidence/pr86/jobs3645-3650
python -B -m unittest discover -s tests/evidence -p test_pr86_wave61_review_numeric.py -v
```
