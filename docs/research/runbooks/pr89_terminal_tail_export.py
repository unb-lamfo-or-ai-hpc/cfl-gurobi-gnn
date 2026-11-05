"""Export the six remaining PR89 terminal jobs; standard library only.

Run by the author in the existing tfm_env Bash session. The only new HPC
file is one private ZIP in the existing stage. No solver/campaign imports,
new directories, home writes, scheduler mutations or automatic polling.
"""
import csv
import datetime as dt
import hashlib
import io
import json
import os
import socket
import stat
import subprocess
import zipfile
from pathlib import Path

HEAD = "9ab7823c6886d19e9ec865141a1cd35b3c3c16e5"
TREE = "69ed16b9635c493161bf620727c9e0a0aee7a7dc"
CONTROLS = {
    "plan.json": "48fca37e2cc698f4d35e4850fdd48d8115b36d7f64b97438ded3b9e17dea3dd1",
    "preflight.json": "b31d5ac2e80a3ae76c3904e197851ce8b42c1bbc92a955212dc277c4cbb252c0",
    "authorization.json": "0fc7aee5c53639ca05edfb46ba8cec826f843dfe2597ebea780d4bcdbe68b47e",
}
MODEL = "c93c8862e4819d1a2b62e721d907afe07b79039d12b953cdb881525c7d251801"
ALL_JOBS = tuple(str(j) for j in range(3675, 3735))
JOBS = tuple(str(j) for j in range(3729, 3735))
FIELDS = ("JobID", "State", "ExitCode", "ElapsedRaw", "TotalCPU", "AllocCPUS", "ReqMem", "MaxRSS", "Start", "End")
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "NODE_FAIL", "OUT_OF_MEMORY",
            "PREEMPTED", "BOOT_FAIL", "DEADLINE", "REVOKED"}
OUT_NAME = "terminal-tail-jobs3729-3734.private.zip"
MIB = 2**20
MAX_TOTAL = 768 * MIB


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(MIB), b""):
            h.update(block)
    return h.hexdigest()


def scoped(path, stage):
    path, stage = Path(path), Path(stage).resolve(strict=True)
    require(not path.is_symlink(), "SYMLINK_LEAF")
    path = path.resolve(strict=True)
    require(path != stage and path.is_relative_to(stage), "PATH_OUTSIDE_STAGE")
    require(stat.S_ISREG(path.stat().st_mode), "REGULAR_FILE_REQUIRED")
    return path


def metadata(path):
    require(Path(path).stat().st_size <= 8 * MIB, "METADATA_SIZE_CAP")
    return json.loads(Path(path).read_text(encoding="utf-8"))


def accounting_rows(text):
    rows = []
    for row in csv.reader(io.StringIO(text), delimiter="|"):
        if not row or not row[0].strip():
            continue
        if len(row) == len(FIELDS) + 1 and row[-1] == "":
            row.pop()
        require(len(row) == len(FIELDS), "ACCOUNTING_FIELD_COUNT")
        value = {k: v.strip() for k, v in zip(FIELDS, row)}
        require(value["JobID"].split(".")[0] in ALL_JOBS, "UNREQUESTED_JOB")
        rows.append(value)
    jobs, active = [], []
    for job in ALL_JOBS:
        current = [r for r in rows if r["JobID"].split(".")[0] == job]
        roots = [r for r in current if r["JobID"] == job]
        require(len(roots) == 1, "MISSING_OR_AMBIGUOUS_ACCOUNTING_" + job)
        state = roots[0]["State"].split()[0].rstrip("+")
        if state not in TERMINAL:
            active.append(job + ":" + state)
        if job in JOBS:
            for step in current:
                step_state = step["State"].split()[0].rstrip("+")
                if step_state not in TERMINAL and step["JobID"] != job:
                    active.append(step["JobID"] + ":" + step_state)
        jobs.append({"job_id": job, "state": state, "rows": current})
    require(not active, "AGUARDE_ESTADOS_NAO_TERMINAIS=" + ",".join(active))
    return jobs


def export(stage, accounting, query_started_utc, query_finished_utc):
    stage = Path(stage).resolve(strict=True)
    out = stage / OUT_NAME
    require(not out.exists() and not out.is_symlink(), "OUTPUT_ALREADY_EXISTS_PRESERVE_AND_TRANSFER=" + str(out))
    jobs = accounting_rows(accounting)  # All gates precede archive creation.
    entries, missing = [], []

    def add(name, cap=8 * MIB, expected=None, optional=False):
        candidate = stage / name
        if optional and not candidate.exists() and not candidate.is_symlink():
            missing.append({"job_id": str(3675 + int(Path(name).parts[1])), "path": name})
            return None
        path = scoped(candidate, stage)
        size = path.stat().st_size
        require(size <= cap, "FILE_SIZE_CAP_" + name)
        before = digest(path)
        if expected is not None:
            require(before == expected, "SEALED_HASH_MISMATCH_" + name)
        entries.append((name, path, before, size))
        return path

    for name, expected in CONTROLS.items():
        add(name, expected=expected)
    plan = metadata(stage / "plan.json")
    require(plan["source_commit"] == HEAD and len(plan["cells"]) == 60, "PLAN_IDENTITY")
    mapping = []
    for index, job in enumerate(ALL_JOBS):
        cell = plan["cells"][index]
        name = f"runs/{index}/submission.json"
        sub = scoped(stage / name, stage)
        require(metadata(sub) == {"index": index, "job_id": job, "plan_sha256": CONTROLS["plan.json"]}, "SUBMISSION_BINDING_" + job)
        mapping.append({"index": index, "job_id": job, "cell": cell})
        if job in JOBS:
            require(cell["alias"] == "M12" and cell["model_sha256"] == MODEL
                    and cell["seed"] == 42 and cell["threads"] in (8, 16), "TAIL_CELL_SCOPE")
            add(name)
    artifact_seals = []
    for item in mapping:
        if item["job_id"] not in JOBS:
            continue
        index, job = item["index"], item["job_id"]
        prefix = f"runs/{index}/"
        paths = {}
        for name in ("child.json", "supervision.json", "checked.json", "costs.json", "held_profile.json",
                     "optimize.intent.json", "dispatch.started.json", "child.started.json"):
            paths[name] = add(prefix + name, optional=True)
        child = metadata(paths["child.json"]) if paths["child.json"] else None
        checked = metadata(paths["checked.json"]) if paths["checked.json"] else None
        if child is not None:
            require(child["cell"] == item["cell"] and child["plan_sha256"] == CONTROLS["plan.json"], "CHILD_IDENTITY_" + job)
        if checked is not None:
            require(checked["index"] == index and checked["plan_sha256"] == CONTROLS["plan.json"], "CHECKED_IDENTITY_" + job)
            for name, key in (("child.json", "child_sha256"), ("supervision.json", "supervision_sha256"), ("costs.json", "costs_sha256")):
                if paths[name] is not None:
                    require(digest(paths[name]) == checked[key], "NESTED_SEAL_" + job + "_" + name)
        log_seal = child.get("gurobi_log", {}).get("log_sha256") if child else None
        log = add(prefix + "gurobi.private.log", cap=32 * MIB, expected=log_seal, optional=True)
        solution = add(prefix + "solution.private.json.gz", cap=64 * MIB, optional=True)
        add(prefix + f"batch-{job}.private.out", cap=32 * MIB, optional=True)
        artifact_seals.append({"job_id": job, "closed_log_historical_seal_verified": bool(log and log_seal),
                               "solution_hash_scope": "observed_on_tail_collection_not_historical_seal" if solution else "absent"})
    require(sum(size for _, _, _, size in entries) <= MAX_TOTAL, "TOTAL_INPUT_SIZE_CAP")
    states = {j["job_id"]: j for j in jobs}
    non_success = [j for j in ALL_JOBS if states[j]["state"] != "COMPLETED" or
                   next(r for r in states[j]["rows"] if r["JobID"] == j)["ExitCode"] != "0:0"]
    generated = {
        "job-cell-map.json": encoded(mapping),
        "scheduler-snapshot.json": encoded({"query_started_utc": query_started_utc, "query_finished_utc": query_finished_utc,
                                            "query_scope": "all_sixty_campaign_jobs_and_reported_steps", "jobs": jobs}),
        "accounting.private.txt": accounting.encode(),
    }
    manifest = {
        "kind": "PR89_terminal_tail_private_export_v1", "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_commit": HEAD, "model_sha256": MODEL, "model_included": False,
        "model_reference_archive_sha256": "bf5f13a9d6e34de77312c10e613f8b677e7b2548eec97e2a3c03cb9cae4105c2",
        "previous_receipt_archives": [
            {"job_ids": [str(j) for j in range(3675, 3725)], "sha256": "111ca062008ff92896a22c8266050ba544f7ad5fb5c048c1d1b0a4539038d0ab"},
            {"job_ids": [str(j) for j in range(3725, 3729)], "sha256": "a43ed259666bf3f29306891192c061a54db157bd314561c23641aecd2066bae9"},
        ],
        "previous_archives_references_not_rehashed_here": True,
        "collected_job_ids": list(JOBS), "terminal_jobs": 6, "campaign_terminal_jobs_observed": 60,
        "non_success_accounting_job_ids": non_success, "missing_files": missing, "artifact_seals": artifact_seals,
        "private_archive_not_for_github": True, "nested_result_validation": "collection_identity_and_present_seals_only_pending_scientific_review",
        "optimization_calls_added": 0, "campaign_modified": False, "scientific_reporting_eligible": False,
        "final_campaign_return": False,
        "sha256": {n: h for n, _, h, _ in entries}, "sizes": {n: size for n, _, _, size in entries},
    }
    for name, raw in generated.items():
        manifest["sha256"][name] = hashlib.sha256(raw).hexdigest()
        manifest["sizes"][name] = len(raw)
    # Exclusive creation. Preserve a failed/partial ZIP; never overwrite it.
    with zipfile.ZipFile(out, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for name, path, expected, size in entries:
            require(path.stat().st_size == size and digest(path) == expected, "CHANGED_BEFORE_COPY_" + name)
            archive.write(path, name)
            require(path.stat().st_size == size and digest(path) == expected, "CHANGED_DURING_COPY_" + name)
        for name, raw in generated.items():
            archive.writestr(name, raw)
        archive.writestr("tail-manifest.json", encoded(manifest))
    with zipfile.ZipFile(out) as archive:
        require(set(archive.namelist()) == set(manifest["sha256"]) | {"tail-manifest.json"}, "ZIP_MEMBER_SET")
        for name, expected in manifest["sha256"].items():
            h = hashlib.sha256()
            with archive.open(name) as stream:
                for block in iter(lambda: stream.read(MIB), b""):
                    h.update(block)
            require(h.hexdigest() == expected, "ZIP_MEMBER_HASH_" + name)
    return out, manifest


def main():
    import pwd
    require(socket.gethostname().split(".")[0] == "dgx-dasci", "HOST_MISMATCH")
    require(pwd.getpwuid(os.getuid()).pw_name == "vrcelestino", "USER_MISMATCH")
    require(os.environ.get("CONDA_DEFAULT_ENV") == "tfm_env", "ENV_MISMATCH")
    stage = Path("/raid/vrcelestino/data/cfl-mvp2-evidence/pr89/cpu12h-9ab7823c6886").resolve(strict=True)
    require(stage == Path("/raid/vrcelestino/data") / "cfl-mvp2-evidence/pr89/cpu12h-9ab7823c6886", "STAGE_MISMATCH")
    for revision, expected in (("HEAD", HEAD), ("HEAD^{tree}", TREE)):
        result = subprocess.check_output(["git", "-C", str(stage / "source"), "rev-parse", revision], text=True, timeout=15).strip()
        require(result == expected, "SOURCE_IDENTITY")
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    accounting = subprocess.check_output(["sacct", "--noheader", "--parsable2", "--starttime=2026-10-01",
        "-j", ",".join(ALL_JOBS), "--format=" + ",".join("State%40" if k == "State" else k for k in FIELDS)], text=True, timeout=60)
    finished = dt.datetime.now(dt.timezone.utc).isoformat()
    out, manifest = export(stage, accounting, started, finished)
    print("ARQUIVO_HPC=" + str(out))
    print("SHA256=" + digest(out))
    print("JOBS_TERMINAIS=6")
    print("JOBS_COLETADOS=" + ",".join(JOBS))
    print("JOBS_CAMPANHA_TERMINAIS=60")
    print("ARQUIVOS_AUSENTES=" + str(len(manifest["missing_files"])))
    print("OTIMIZACOES_NOVAS=0")
    print("BYTES_ZIP=" + str(out.stat().st_size))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit("COLETA_ABORTADA=" + str(error) + "\nPreserve a saida e qualquer ZIP existente. Nao sobrescreva arquivos.")
