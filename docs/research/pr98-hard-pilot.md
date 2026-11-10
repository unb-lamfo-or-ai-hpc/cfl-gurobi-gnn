# PR98 hard input qualification and H25 technical pilot

## Evidence boundary

The six original identities are H0, H5, H10, H15, H20 and H25, with the benchmark names `CFL_hard_instance_0/5/10/15/20/25`. The existing CFL inventory places them outside the admitted label-quality sample. The pilot uses the same frozen CPU checkpoint, the existing class-aware G policy, the matched root-LP R policy and the existing root capture. The optimization model uses MINIMIZE and retains the original domains and constraints. No labels or PaScal solver Starts enter the new pipeline.

The PaScal handoff inventory (2026-10-26, evidence archive v2.0.0, source `fbbf7d7178e022ff8cf759d8fd7568359b583cf8`) supplies five compressed LP reference hashes. They describe exact gzip bytes. The H0 pickle task establishes a separate historical observation; it supplies no independent original LP digest. The official benchmark reference is [MILPBench](https://github.com/thuiar/MILPBench).

| Parent | Archived gzip bytes | PaScal gzip SHA-256 |
| --- | ---: | --- |
| H0 | — | Independent LP reference pending |
| H5 | 135846967 | `7f0b9a9d11ed28eae8ec295035c507e00477387114b510c984811131873d9454` |
| H10 | 135812992 | `af80d09064bd9ed9c497ef37b43afad7b3e4b7ea97c7a6553997d1b0075d32f8` |
| H15 | 135836613 | `4b4302ee25c63ae92d105087f33b614aa35acc08f300775390e5e4942655ec57` |
| H20 | 135823234 | `9f95036756be3ce65eb93a5ed6f629d168c0e45a504deca8308650ab29e6b4e1` |
| H25 | 135856517 | `d615e368236abf98cf8bc0a7deb1dddb50b764d263e099b7174a267b900c292c` |

Preflight uses exactly two canonical dataset layouts under the existing data root. It reports both digests and rejects conflicting decoded copies. Admission requires the decoded byte size and SHA-256 of the independently hashed LP. The gzip digest remains a provenance field. When multiple copies have identical decoded bytes, prefer an exact PaScal gzip match if present. Otherwise select the first canonical copy and bind its raw size and SHA-256 for pilot rechecks. The H0 observed digest is a fingerprint for comparison with an independently acquired original. The bounded LP envelope check is not an optimization or a full structural or feasibility audit. The preflight also checks the exact checkpoint bytes at the existing PR94 preparation binding without deserializing it. For safety, an input mismatch stops the pilot and an incomplete preflight does not authorize a second attempt.

### Independently checked local PaScal LP exports

The existing local uncompressed LP exports were read and hashed on 8 November 2026. Compare these values with the dgx-dasci decoded SHA-256 and size as a second byte check. The local pickle for H0 matches the historical pickle fingerprint `30877729a1449214f9f4e87cf4ebb26debbd6432b4c09f255d82198a887a5c49` and was not deserialized. H0 still requires an independent LP reference from the [official CFL_hard distribution](https://github.com/thuiar/MILPBench/blob/main/Benchmark%20Datasets/README.md#benchmark-datasets).

| Parent | Local LP bytes | Local LP SHA-256 |
| --- | ---: | --- |
| H5 | 425851766 | `9c4923a2c3da283aa079c06347aa1bf324e76be6e64bf29529a1890b82f95c6a` |
| H10 | 425778787 | `19e0f0a8262b09521cb911f32af054333986242e539532465fb81023fc7e191f` |
| H15 | 425597797 | `8e7c528a6b894512fa1a82c84036fb86146d90385977919684a1427372ba1ad5` |
| H20 | 425988486 | `26f0d26b6a9c6b68536664af45d6e7d9de816918c83234ea4816fd3d5dec5076` |
| H25 | 425712450 | `bf8661803fa708d1e829ffa44fd69d69e95b228572c12310ba6e43d7d934cb38` |

### Read-only dgx-dasci return on 10 November 2026

The [original preflight receipt](../evidence/pr98/preflight-20261110/hard-preflight-v1.json) has SHA-256 `30edf5b0b82f5a899a40c0c97be570495e4e4c925b2cf70d400d86cfac8f01e1`. The installed checkpoint matched. Five candidates (H5/H10/H15/H20/H25) matched the byte counts and SHA-256 digests of the independent uncompressed LP exports. Each gzip digest differed from its historical PaScal gzip digest. H0 was found and inventoried, with its independent LP reference still pending. The first version rejected H25 at the gzip gate. It made zero solver calls, inference calls and Slurm submissions.

Preserve that receipt and its stage. Install the new pinned commit into a separate isolated stage for the new preflight. It applies the decoded LP criterion and seals the exact selected files used on dgx-dasci. Its new receipt is required for pilot admission.

## Pilot and controls

H25 was fixed before the cluster inspection. It is the largest compressed workload among the five archived PaScal gzip files, a transparent way to pick one case. Compressed size does not establish the worst memory or runtime among the hard cases.

One held Slurm job is proposed with four physical cores, 64 GiB, one 32-GB V100 and a one-hour allocation. The explicit author CLI supplies the preflight digest and pilot decision reference. The adapter compares the observed environment with the recorded one (Python 3.10.20, Gurobi 13.0.1, Torch 2.1.2 CUDA 12.1 and existing dependencies). It verifies the held allocation before release. The watchdog samples cgroup memory and supervises process groups with fixed deadlines. It requires 80 GiB free for admission and preserves a global write-once submission claim. Resource changes require a separate decision.

- One capture of the first optimal root LP, using the existing 600-second solver cap, then one frozen V100 forward and two matched Starts. The adapter verifies root/model signature and variable order, checks graph serialization round trip, and records graph, prediction, checkpoint and Start seals. An abstention is preserved and stops the pilot before the six solves because it cannot exercise Start delivery.
- Six fresh CPU solver calls at up to 120 seconds each, with four physical cores, seed 42, and B/R/G under `ConcurrentMIP=1` and `2`. The worker hides the GPU for evaluation, checks effective parameters and unchanged model signatures, and audits any terminal incumbent. Terminal outcomes are technical diagnostics. Start messages and callback progress from the first concurrent racer do not identify the winner's path. These observations remain outside the scientific campaign.
- Any failed gate stops further pilot steps. No retry, solver tuning or submission of the 990-cell matrix follows automatically. The raw and partial outputs stay on the data filesystem. Only sanitized receipts are copied into the PR.

## Checkout integrity incident

The first dgx-dasci preflight stopped at `source_changed`, before the model and checkpoint inspection or either preflight receipt. A read-only diagnostic identified four CRLF files under `manuscript/tables`. Their archived blob bytes and the PR89 asset receipt are preserved. The attributes now disable line-ending conversion for those four paths only. The recovery reuses the isolated stage, checks that each affected worktree file has its original raw blob identity, checks that the index is unchanged, and advances to the pinned repair commit with a normal detached checkout. Keep the failed stage and diagnostics if any check diverges.

## CLI sequence

Install the exact reviewed commit into an isolated `pr98-hard.*` stage within the existing evidence directory on dgx-dasci. Run the following with the author's active `tfm_env`. `STAGE`, `COMMIT` and `PREFLIGHT_SHA` are reviewed concrete values. Never use a moving branch to replace that checkout.

1. `timeout 600 nice -n 10 python -I -B "$STAGE/source/scripts/evidence/pr98_hard_inputs.py" "$STAGE" "$COMMIT"`
2. Review the six dispositions and the checkpoint hash. After the separate decision for the concrete pilot budget: `python -B "$STAGE/source/scripts/evidence/pr98_hard_pilot.py" submit "$STAGE" "$PREFLIGHT_SHA" --decision "$AUTHOR_DECISION"`.
3. Once accounting is terminal: `python -B "$STAGE/source/scripts/evidence/pr98_hard_pilot.py" report "$STAGE" "$PREFLIGHT_SHA"`. Review the job and steps, sampled memory and guard stops, root/graph/prediction/Start seals, and both effective solver profiles. Preserve partial output and intents as diagnostics if the gate fails.

Review the pilot before admitting preparation of the other hard cases. Each remaining case requires its own verified original model, root, graph, prediction and Start receipt. Compare H0 to an independent original LP before admitting it. A complete matrix release also requires site resource review and explicit approval of the campaign budget.
