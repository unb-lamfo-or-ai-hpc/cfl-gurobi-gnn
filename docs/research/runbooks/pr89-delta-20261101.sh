# Copy into the author's existing Bash session; PR89_STAGE must name the existing stage.
# Reads frozen identities and terminal receipts; creates one new archive in that stage.
python3 -B - "${PR89_STAGE:?Set PR89_STAGE to the existing campaign directory}" <<'PY'
import csv, datetime as dt, getpass, hashlib, io, json, os
import socket, subprocess, sys, zipfile
from pathlib import Path

S = Path(sys.argv[1]).resolve(strict=True)
OUT = S / "partial-results-delta-20261101-jobs3725-3728.zip"
HEAD = "9ab7823c6886d19e9ec865141a1cd35b3c3c16e5"
TREE = "69ed16b9635c493161bf620727c9e0a0aee7a7dc"
JOBS = ("3725", "3726", "3727", "3728")
BASE_ZIP_SHA = "111ca062008ff92896a22c8266050ba544f7ad5fb5c048c1d1b0a4539038d0ab"

def require(ok, message):
    if not ok:
        raise SystemExit(message)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def command(args):
    return subprocess.check_output(args, text=True)

def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()

def read_fixed(name):
    path = S / name
    require(path.resolve().is_relative_to(S) and not path.is_symlink(), "UNSAFE_PATH_" + name)
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
            "FILE_CHANGED_DURING_READ_" + name)
    return raw

require(socket.gethostname().split(".")[0] == "dgx-dasci", "HOST_MISMATCH")
require(getpass.getuser() == "vrcelestino", "USER_MISMATCH")
require(os.environ.get("CONDA_DEFAULT_ENV") == "tfm_env", "ENV_MISMATCH")
require(S.is_relative_to(Path("/raid")) and S.name == "cpu12h-9ab7823c6886", "STAGE_MISMATCH")
require(not OUT.exists() and not OUT.is_symlink(), "OUTPUT_ALREADY_EXISTS_PRESERVE_AND_REUSE")
require(command(["git", "-C", str(S/"source"), "rev-parse", "HEAD"]).strip() == HEAD, "HEAD_MISMATCH")
require(command(["git", "-C", str(S/"source"), "rev-parse", "HEAD^{tree}"]).strip() == TREE, "TREE_MISMATCH")
payload = {}
for name, expected in {
    "plan.json": "48fca37e2cc698f4d35e4850fdd48d8115b36d7f64b97438ded3b9e17dea3dd1",
    "preflight.json": "b31d5ac2e80a3ae76c3904e197851ce8b42c1bbc92a955212dc277c4cbb252c0",
    "authorization.json": "0fc7aee5c53639ca05edfb46ba8cec826f843dfe2597ebea780d4bcdbe68b47e"
}.items():
    raw = read_fixed(name)
    require(sha(raw) == expected, name + "_HASH_MISMATCH")
    payload[name] = raw
plan = json.loads(payload["plan.json"])
require(plan["source_commit"] == HEAD and len(plan["cells"]) == 60, "PLAN_IDENTITY")
mapping = []
for job in JOBS:
    i = int(job) - 3675
    raw = read_fixed("runs/" + str(i) + "/submission.json")
    sub = json.loads(raw)
    require(sub["index"] == i and str(sub["job_id"]) == job
            and sub["plan_sha256"] == sha(payload["plan.json"]), "SUBMISSION_BINDING_" + job)
    mapping.append({"index": i, "job_id": job, "cell": plan["cells"][i]})
fields = ["JobID", "State", "ExitCode", "ElapsedRaw", "TotalCPU", "AllocCPUS", "ReqMem", "MaxRSS", "Start", "End"]
started = dt.datetime.now(dt.timezone.utc).isoformat()
text = command(["sacct", "--noheader", "--parsable2", "--starttime=2026-10-01",
                "-j", ",".join(JOBS), "--format=" + ",".join("State%40" if k == "State" else k for k in fields)])
rows = [dict(zip(fields, r)) for r in csv.reader(io.StringIO(text), delimiter="|") if r and r[0].strip()]
terminal = {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "NODE_FAIL", "OUT_OF_MEMORY",
            "PREEMPTED", "BOOT_FAIL", "DEADLINE", "REVOKED"}
missing, states = [], []
for item in mapping:
    job, i = item["job_id"], item["index"]
    accounting = [r for r in rows if r["JobID"].split(".")[0] == job]
    root = [r for r in accounting if r["JobID"] == job]
    require(len(root) == 1, "MISSING_OR_AMBIGUOUS_ACCOUNTING_" + job)
    state = root[0]["State"].strip().split()[0].rstrip("+")
    require(state in terminal, "REQUESTED_JOB_NOT_TERMINAL_" + job + "_" + state)
    states.append({"job_id": job, "state": state, "rows": accounting})
    for name in ("submission.json", "child.json", "supervision.json", "checked.json", "costs.json"):
        rel = "runs/" + str(i) + "/" + name
        if (S/rel).is_file():
            payload[rel] = read_fixed(rel)
        else:
            missing.append({"job_id": job, "path": rel})
payload["job-cell-map.json"] = encode(mapping)
payload["scheduler-snapshot.json"] = encode({"query_started_utc": started,
    "query_finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "jobs": states,
    "query_scope": "requested_four_jobs_only"})
manifest = {"kind": "PR89_partial_diagnostic_delta_export_v1", "source_commit": HEAD,
    "baseline_archive_sha256": BASE_ZIP_SHA, "baseline_received_job_ids": [str(j) for j in range(3675, 3725)],
    "collected_job_ids": list(JOBS), "terminal_jobs": len(JOBS), "submitted_jobs": 60,
    "missing_files": missing, "raw_logs_included": False,
    "nested_result_validation": "pending_offline_review", "scientific_reporting_eligible": False,
    "final_campaign_return": False, "sha256": {k: sha(v) for k, v in sorted(payload.items())}}
payload["partial-manifest.json"] = encode(manifest)
with zipfile.ZipFile(OUT, "x", compression=zipfile.ZIP_DEFLATED) as archive:
    for name, raw in sorted(payload.items()):
        archive.writestr(name, raw)
print("ARQUIVO_HPC=" + str(OUT))
print("SHA256=" + sha(OUT.read_bytes()))
print("JOBS_TERMINAIS=" + str(len(JOBS)))
print("JOBS_COLETADOS=" + ",".join(JOBS))
print("ARQUIVOS_AUSENTES=" + str(len(missing)))
PY
