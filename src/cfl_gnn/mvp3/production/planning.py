"""Render exact allocation proposals; this module never calls sbatch."""

import re
import shlex
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..contract import digest, load_json, require
from ..journal import durable_json, file_sha256
from .policy import PROFILES, ascii_path, policy, token
from .release import verify_bundle


def make_plan(
    bundle,
    manifest_sha256,
    discovery_path,
    output,
    *,
    partition,
    account,
    qos,
    nodes,
    python,
    license_file,
    approval_reference,
):
    bundle, output, license_file = map(ascii_path, (bundle, output, license_file))
    python = ascii_path(python, resolve_links=False)
    manifest = verify_bundle(bundle, manifest_sha256)
    discovery = load_json(discovery_path)
    require(
        discovery["source_commit"] == manifest["source_commit"]
        and discovery["inventory"] is not None
        and not discovery["commands_failed"],
        "Complete exact-source discovery is required",
    )
    require(
        len(discovery["inventory"]["own_jobs"]) == 0,
        "Qualification proposal requires a closed own-job snapshot; inspect other activity first",
    )
    require(
        discovery["package_versions"].get("gurobipy") == "14.0.0"
        and discovery["license_file_exists"] is True,
        "Target Gurobi14 metadata/license path not admitted",
    )
    require(
        Path(discovery["python_executable"]).absolute() == python,
        "Probe interpreter differs from discovery",
    )
    require(
        Path(discovery["license_file_path"]) == license_file,
        "Probe license route differs from discovery",
    )
    for value in (partition, account, qos):
        token(value)
    partition_rows = discovery["inventory"]["partitions"]
    require(
        any(
            row["PartitionName"] == partition and row.get("State") == "UP"
            for row in partition_rows
        ),
        "Partition was not observed UP",
    )
    associations = discovery["inventory"]["own_associations"]
    require(
        any(
            row["account"] == account
            and row["partition"] in ("", partition)
            and qos in row["qos"].split(",")
            for row in associations
        ),
        "Account/QOS pair not explicitly observed in own association; do not guess inherited access",
    )
    require(set(nodes) == set(PROFILES), "Exactly two profile candidates are required")
    observed = {row["NodeName"]: row for row in discovery["inventory"]["nodes"]}
    for profile, node in nodes.items():
        token(node)
        require(
            node in discovery["inventory"]["candidate_nodes"][profile],
            "Node is not an observed profile candidate",
        )
        require(
            partition in observed[node].get("Partitions", "").split(","),
            "Candidate node is outside the selected partition",
        )
    require(
        isinstance(approval_reference, str) and approval_reference.strip(),
        "Prospective author CLI approval reference required",
    )
    identifier = uuid.uuid4().hex
    plan = {
        "schema_version": policy()["schema_version"],
        "qualification_id": identifier,
        "source_commit": manifest["source_commit"],
        "bundle": str(bundle),
        "manifest_sha256": manifest_sha256,
        "discovery_sha256": file_sha256(discovery_path),
        "discovery_utc": discovery["created_utc"],
        "policy": policy(),
        "partition": partition,
        "account": account,
        "qos": qos,
        "python": str(python),
        "python_prefix": discovery["python_prefix"],
        "license_file": str(license_file),
        "approval_reference": approval_reference,
        "slots": {
            profile: {
                "node": node,
                "attempt": f"prod-{identifier}-{profile}",
                "output": str(output / profile),
            }
            for profile, node in nodes.items()
        },
        "scientific_release": False,
        "native_calls_released_by_preparation": 0,
        "other_Gurobi_sessions": "author_must_confirm_none_before_submission_not_machine_proven",
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    output.mkdir(parents=True, exist_ok=False)
    plan_path = output / "plan.json"
    checksum = durable_json(plan_path, plan)
    scripts = {}
    for profile, slot in plan["slots"].items():
        path = output / f"{profile}.sbs"
        args = [
            str(python),
            "-B",
            str(bundle / "scripts/mvp3/qualify_production.py"),
            "--bundle",
            str(bundle),
            "--manifest-sha256",
            manifest_sha256,
            "worker",
            "--plan",
            str(plan_path),
            "--plan-sha256",
            checksum,
            "--profile",
            profile,
        ]
        text = "\n".join(
            [
                "#!/bin/bash",
                f"#SBATCH --job-name=cfl-prod-qual-{identifier[:8]}-{profile}",
                "#SBATCH --nodes=1",
                "#SBATCH --ntasks=1",
                "#SBATCH --cpus-per-task=64",
                "#SBATCH --threads-per-core=2",
                "#SBATCH --exclusive",
                f"#SBATCH --mem={PROFILES[profile]['memory_GiB']}G",
                "#SBATCH --time=00:05:00",
                "#SBATCH --no-requeue",
                f"#SBATCH --partition={partition}",
                f"#SBATCH --account={account}",
                f"#SBATCH --qos={qos}",
                f"#SBATCH --nodelist={slot['node']}",
                f"#SBATCH --output={output}/{profile}.%j.out",
                f"#SBATCH --error={output}/{profile}.%j.err",
                "set -euo pipefail",
                "umask 077",
                f"export GRB_LICENSE_FILE={shlex.quote(str(license_file))}",
                "exec srun --nodes=1 --ntasks=1 --cpus-per-task=64 --threads-per-core=2 --cpu-bind=threads "
                + shlex.join(args),
                "",
            ]
        )
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        scripts[profile] = {
            "script_sha256": file_sha256(path),
            "test_only_command": shlex.join(["sbatch", "--test-only", str(path)]),
            "prospective_submission_command": shlex.join(
                ["sbatch", "--parsable", str(path)]
            ),
            "submission_requires_specific_author_release": True,
        }
    result = {
        "plan_sha256": checksum,
        "plan_identity_sha256": digest(plan),
        "scripts": scripts,
        "jobs_submitted": 0,
        "native_calls": 0,
        "review_required": True,
        "maximum_total_technical_calls_if_separately_released": 2,
        "capacity_request_is_not_a_memory_stress_test": True,
    }
    durable_json(output / "proposal.json", result)
    return result


def load_plan(path, checksum, manifest, *, bundle=None, manifest_sha256=None):
    require(
        re.fullmatch(r"[0-9a-f]{64}", checksum) is not None
        and file_sha256(path) == checksum,
        "Plan bytes changed",
    )
    plan = load_json(path)
    require(
        plan["source_commit"] == manifest["source_commit"]
        and plan["policy"] == policy()
        and plan["scientific_release"] is False,
        "Plan/source/policy mismatch",
    )
    require(
        set(plan["slots"]) == set(PROFILES), "Changed qualification slot population"
    )
    if bundle is not None:
        require(
            Path(plan["bundle"]).resolve() == Path(bundle).resolve()
            and plan["manifest_sha256"] == manifest_sha256,
            "Worker bundle differs from reviewed plan",
        )
    outputs = []
    for profile, slot in plan["slots"].items():
        token(slot["node"])
        require(
            slot["attempt"] == f"prod-{plan['qualification_id']}-{profile}",
            "Changed slot identity",
        )
        outputs.append(ascii_path(slot["output"]))
    require(
        len(set(outputs)) == 2
        and all(not p.is_relative_to(Path(plan["bundle"]).resolve()) for p in outputs),
        "Output collides with source/other slot",
    )
    for value in (plan["partition"], plan["account"], plan["qos"]):
        token(value)
    return plan
