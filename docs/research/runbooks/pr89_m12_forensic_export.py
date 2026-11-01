"""Copy closed PR89 artifacts for offline arithmetic; stdlib only, no solver.

Invoked by the author in the existing HPC session. It never imports campaign
operators, decompresses solution vectors, or changes existing inputs/outputs.
The private archive is NOT intended for GitHub or journal distribution.
"""
import datetime as dt
import hashlib
import json
import os
import socket
import stat
import subprocess
import uuid
import zipfile
from pathlib import Path

HEAD = "9ab7823c6886d19e9ec865141a1cd35b3c3c16e5"
TREE = "69ed16b9635c493161bf620727c9e0a0aee7a7dc"
PLAN = "48fca37e2cc698f4d35e4850fdd48d8115b36d7f64b97438ded3b9e17dea3dd1"
PREFLIGHT = "b31d5ac2e80a3ae76c3904e197851ce8b42c1bbc92a955212dc277c4cbb252c0"
AUTH = "0fc7aee5c53639ca05edfb46ba8cec826f843dfe2597ebea780d4bcdbe68b47e"
MODEL = "c93c8862e4819d1a2b62e721d907afe07b79039d12b953cdb881525c7d251801"
PARENT = "CFL_medium_instance_12"
CELLS = {
    50: ("3725", "d1705c90f7c7c1d1c350a201a1199ca506caff4c3e89deb966fe3cb6608dc09b"),
    51: ("3726", "ecefa1c2c925041ad703649fbb38359d65c231dcfe8c025e0b2de5c79b32f65a"),
    52: ("3727", "4c708a4c980a4269d5aea8e96bb419614cd382bde4541b7ac868e33bdbdb177e"),
    53: ("3728", "d23c4faefcaa89e66dfd5e69ff52ebac2cf98457fb2d04273219d51501f3f4b5"),
}
MIB = 2**20
MAX_FILE = 512 * MIB
MAX_TOTAL = 768 * MIB


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def scoped(path, root):
    root = Path(root).resolve(strict=True)
    path = Path(path)
    require(not path.is_symlink(), "symlink_leaf")
    path = path.resolve(strict=True)
    require(path.is_relative_to(root) and path != root, "path_outside_data_scope")
    require(stat.S_ISREG(path.stat().st_mode), "regular_file_required")
    return path


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(MIB), b""):
            h.update(block)
    return h.hexdigest()


def parsed(path):
    require(Path(path).stat().st_size <= 8 * MIB, "metadata_size_cap")
    return json.loads(Path(path).read_text(encoding="utf-8"))


def closed_job_states(text):
    rows = [line.rstrip("|").split("|") for line in text.splitlines() if line.strip()]
    require(len(rows) == 4 and {r[0] for r in rows} == {v[0] for v in CELLS.values()}, "accounting_job_set")
    require(all(len(r) == 3 and r[1:] == ["COMPLETED", "0:0"] for r in rows), "four_completed_jobs_required")
    return rows


def copy_closed_files(stage, data_root, accounting):
    """No directory creation; output must be a new ZIP in the existing stage."""
    stage, data_root = Path(stage).resolve(strict=True), Path(data_root).resolve(strict=True)
    require(stage.is_dir() and stage.is_relative_to(data_root), "existing_data_stage")
    closed_job_states(accounting)
    entries = []

    def add(name, path, expected=None, cap=MAX_FILE):
        path = scoped(path, data_root)
        require(0 <= path.stat().st_size <= cap, "file_size_cap:" + name)
        h = digest(path)
        if expected is not None:
            require(h == expected, "sealed_file_hash:" + name)
        entries.append((name, path, h, path.stat().st_size))
        return path

    add("plan.json", stage / "plan.json", PLAN, 8 * MIB)
    add("preflight.json", stage / "preflight.json", PREFLIGHT, 8 * MIB)
    add("authorization.json", stage / "authorization.json", AUTH, 8 * MIB)
    plan = parsed(stage / "plan.json")
    require(plan["source_commit"] == HEAD and len(plan["cells"]) == 60, "frozen_plan")
    binding = data_root / "cfl-mvp2-evidence/pr86/bindings-46802675ff99/prepared/private/input_paths.json"
    paths = parsed(scoped(binding, data_root))
    matches = [p for p in paths if p["parent"] == PARENT]
    require(len(matches) == 1, "unique_bound_parent")
    original_model = Path(matches[0]["mip_path"])
    model_suffix = "".join(original_model.suffixes).lower()
    require(model_suffix in (".lp", ".mps", ".lp.gz", ".mps.gz"), "known_model_file_format")
    add("model.private" + model_suffix, original_model, MODEL)
    for index, (job, child_sha) in CELLS.items():
        folder = stage / "runs" / str(index)
        prefix = "runs/" + str(index) + "/"
        add(prefix + "child.json", folder / "child.json", child_sha, 8 * MIB)
        child = parsed(folder / "child.json")
        require(child["cell"] == plan["cells"][index] and child["cell"]["model_sha256"] == MODEL, "child_cell_binding")
        require(child["plan_sha256"] == PLAN, "child_plan_binding")
        require(child["result"]["optimization_calls"] == 1, "original_single_call")
        add(prefix + "submission.json", folder / "submission.json", cap=8 * MIB)
        require(parsed(folder / "submission.json") == {"index": index, "job_id": job, "plan_sha256": PLAN}, "submitted_job_identity")
        add(prefix + "checked.json", folder / "checked.json", cap=8 * MIB)
        checked = parsed(folder / "checked.json")
        require(checked["complete"] is True and checked["child_sha256"] == child_sha and checked["index"] == index and checked["plan_sha256"] == PLAN, "terminal_child_seal")
        for name, key in (("supervision.json", "supervision_sha256"), ("costs.json", "costs_sha256")):
            add(prefix + name, folder / name, checked[key], 8 * MIB)
        add(prefix + "solution.private.json.gz", folder / "solution.private.json.gz", cap=64 * MIB)
        add(prefix + "gurobi.private.log", folder / "gurobi.private.log", child["gurobi_log"]["log_sha256"], 32 * MIB)
        add(prefix + "optimize.intent.json", folder / "optimize.intent.json", cap=8 * MIB)
        add(prefix + "held_profile.json", folder / "held_profile.json", cap=8 * MIB)
    require(sum(size for _, _, _, size in entries) <= MAX_TOTAL, "total_read_cap")
    out = stage / ("forensics-m12-3725-3728-" + uuid.uuid4().hex + ".private.zip")
    manifest = {
        "protocol": "pr89_closed_m12_forensics_v1",
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_commit": HEAD, "model_sha256": MODEL, "job_ids": [x[0] for x in CELLS.values()],
        "original_model_file_suffix": model_suffix,
        "sha256": {n: h for n, _, h, _ in entries},
        "sizes": {n: size for n, _, _, size in entries},
        "solution_hash_scope": "observed_on_forensic_collection_not_historical_solution_seal",
        "optimization_calls_added": 0, "campaign_modified": False,
        "scientific_reporting_eligible": False, "private_not_for_publication": True,
    }
    # Exclusive creation preserves all prior archives. Any failed archive stays
    # in place as a partial export; never retry by overwriting it.
    with zipfile.ZipFile(out, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for name, path, expected, size in entries:
            require(digest(path) == expected and path.stat().st_size == size, "changed_before_copy")
            archive.write(path, name)
            require(digest(path) == expected and path.stat().st_size == size, "changed_during_copy")
        archive.writestr("accounting.txt", accounting)
        manifest["sha256"]["accounting.txt"] = hashlib.sha256(accounting.encode()).hexdigest()
        archive.writestr("forensic-manifest.json", json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    # Verify copied bytes, not just original pre/post hashes.
    with zipfile.ZipFile(out) as archive:
        for name, expected in manifest["sha256"].items():
            with archive.open(name) as stream:
                h = hashlib.sha256()
                for block in iter(lambda: stream.read(MIB), b""):
                    h.update(block)
            require(h.hexdigest() == expected, "archive_member_hash")
    return out, manifest


def main():
    data = Path("/raid/vrcelestino/data").resolve(strict=True)
    stage = data / "cfl-mvp2-evidence/pr89/cpu12h-9ab7823c6886"
    require(socket.gethostname().split(".")[0] == "dgx-dasci", "host")
    import pwd
    require(pwd.getpwuid(os.getuid()).pw_name == "vrcelestino", "user")
    require(os.environ.get("CONDA_DEFAULT_ENV") == "tfm_env", "environment")
    for revision, expected in (("HEAD", HEAD), ("HEAD^{tree}", TREE)):
        value = subprocess.check_output(["git", "-C", str(stage / "source"), "rev-parse", revision], text=True, timeout=15).strip()
        require(value == expected, "source_identity")
    accounting = subprocess.check_output([
        "sacct", "-X", "-n", "-P", "-j", "3725,3726,3727,3728",
        "--format=JobIDRaw,State,ExitCode",
    ], text=True, timeout=45)
    out, manifest = copy_closed_files(stage, data, accounting)
    print("ARQUIVO_HPC=" + str(out))
    print("SHA256=" + digest(out))
    print("JOBS_COLETADOS=" + ",".join(manifest["job_ids"]))
    print("OTIMIZACOES_NOVAS=0")
    print("BYTES_ZIP=" + str(out.stat().st_size))


if __name__ == "__main__":
    main()
