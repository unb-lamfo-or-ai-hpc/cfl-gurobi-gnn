# PR80 job 3500: runtime blocked before numerical admission

## What happened and what it means

The operator reports job **3500**, `COMPLETED`, exit `0:0`, elapsed
4 seconds. The independently rehashed downloaded `numeric.json` is:

`3f45d352751746d502e02a23a6b62d786622df5d0dab58042e016cac9ac25a18`

Its auditor implementation SHA256 is
`70f26f232215503477dcc71841a8d3e5da399f32fb666076072a8b1272a56101`,
from executable source `13bcc3ef50f894c117af2565eec8b4e071aa3144`.
The source artifact receipt remains
`e0b51fce0ad3e207c1f0a72b1b5678c89974f8fe856a1918a7b189b0ae981681`.

There are **zero numerically qualified parents, one runtime-blocked parent,
and 53 unattempted parents**. This is not 54 failed mathematical checks.
`CFL_easy_instance_0` stopped with:

```json
{
  "state": "unqualified",
  "stage": "restricted_graph_load",
  "reason": "restricted_loader_requires_torch_2_6",
  "exception_type": "AuditStop"
}
```

The source checks the installed `torch.__version__` major/minor against
`(2, 6)` before calling `torch.load`. This receipt establishes failure of
that version gate, but does **not** record the exact installed version.
The first graph was not deserialized by this auditor; its model was not
read for numerical comparison. No optimization or training was performed.
The collector then stopped instead of repeating the same runtime failure
for another 53 parents. Its recorded elapsed time is approximately 3.27 s.

`COMPLETED/0:0` means the collection process successfully wrote its result;
it does not mean `numeric_checks_passed=true`. Both cohort gates and
`training_admitted` remain false. Job accounting is operator-supplied;
the downloaded receipt was checked locally without a new scheduler query.

## Why the loader gate must remain

PyTorch's official advisory [GHSA-53q9-r3pm-6pq6](https://github.com/pytorch/pytorch/security/advisories/GHSA-53q9-r3pm-6pq6)
reports a `weights_only=True` deserialization vulnerability affecting
versions through 2.5.1, patched in 2.6.0. Do not remove the minimum-version
check or use `weights_only=False`. Passing that minimum alone is not a
blanket security or compatibility certification for any later version.

The operational mistake was submitting the bounded numerical job without
first checking the installed runtime against the loader requirement.
Offline/CI tests were not evidence of installed PyTorch/PyG compatibility.
The receipt should also report allowlisted runtime versions on failure,
not only on successful parents.

## Immediate CLI: inventory only, no new job

Run this once in Bash on **dgx-dasci** and return the JSON. This uses only
Python's standard-library package metadata; it does not import PyTorch,
PyG or Gurobi, load a model/graph, invoke Slurm, access the license, install
anything or write files. No password or path inventory is requested.

```bash
conda activate tfm_env
python3 -B - <<'PY'
import importlib.metadata as metadata
import json
import platform
import re
import sys

if platform.node().split('.')[0] != 'dgx-dasci':
    raise SystemExit('WRONG_HOST_NO_ACTION')

versions = {}
for name in ('torch', 'torch-geometric', 'numpy', 'scipy', 'gurobipy', 'packaging'):
    try:
        value = metadata.version(name)
        versions[name] = value if re.fullmatch(r'[A-Za-z0-9.+_-]{1,100}', value) else 'redacted_nonstandard_version'
    except metadata.PackageNotFoundError:
        versions[name] = None

print(json.dumps({
    'protocol_id': 'pr80_job3500_runtime_metadata_v1',
    'historical_job_id': '3500',
    'python': '.'.join(map(str, sys.version_info[:3])),
    'machine': platform.machine(),
    'libc': list(platform.libc_ver()),
    'package_versions': versions,
    'metadata_only_not_import_compatibility_proof': True,
    'historical_environment_identity_proven': False,
    'graph_loads': 0,
    'optimization_runs_added': 0,
    'submissions_added': 0,
    'scheduler_queries': 0,
    'training_admitted': False,
}, indent=2, sort_keys=True))
PY
```

## Continuation and exit conditions

1. Preserve job 3500's source, output and receipt unchanged. Do not rerun
   its submission block or delete its stage.
2. Inspect the inventory above before choosing a compatible package set.
   Prefer a separate CPU-only audit environment under the evidence tree,
   preserving `tfm_env`, rather than upgrading the historical environment.
   Installation commands and versions are not authorized by this document.
3. Prepare and test a pre-submission compatibility check and failure-version
   reporting. Distinguish package metadata, successful imports, restricted
   graph loading and full numerical admission; none implies the next.
4. After a compatible environment is demonstrated, provide one explicit,
   bounded continuation in a fresh stage, with exact source and dependency
   versions recorded. No automatic resubmission, unsafe loader fallback,
   optimization, training or change of sample/split/labels is permitted.
5. Only a numerically qualified installed return plus independent review
   can close C1 and unlock the next E0 gates in the
   [current contract](mvp2-contract-20261008.md). E0, PR80 readiness and merge
   remain pending; this diagnosis does not promote scientific evidence.

This is a runtime-admission problem, not a reason to regenerate datasets,
repeat Sprint B solver runs, change hyperparameters or redesign the sprints.
