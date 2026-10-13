"""Six held, then serial afterok jobs: the next frozen F0 groups, no retry."""

import argparse
import copy
import json
import os
import re
import time
from pathlib import Path

import pr86_main_first_group as first

require, read, parsed, write = first.require, first.read, first.parsed, first.write
encoded, digest = first.encoded, first.digest
ROOT, BASE = first.ROOT, first.BASE
PROTOCOL = "pr86_six_serial_f0_groups_v1"
FIRST_SHA = "dd1a553b453289b23dbed3d52bd4bd7e0ac93eb2b4283597b788e406fcab6825"
FIRST_COMMIT = "5c1c174ca0f5d643ca02c6bd289e289a649dba15"
FIRST_PLAN = "c2244c55beca91881e2fdfc2cfd57a1dad2e00f41b6b207ae1baea64bfb06a99"
CLAIM = BASE / "main-comparison-f0-remaining-six.claim"
RECEIPT = ROOT / "docs/evidence/pr86/job3522/public_return.json"


def review_first(raw):
    """Pinned historical bytes, not an old manifest rebuilt on newer source."""
    require(digest(raw) == FIRST_SHA, "job3522_original_hash")
    value = first.executor.existing.review.flow.meta.strict_json(raw)
    frozen = value["plan"]
    require(
        frozen["source_commit"] == FIRST_COMMIT
        and value["plan_sha256"] == FIRST_PLAN
        and frozen["group"]["group_id"] == first.GROUP
        and value["accounting"]["job_id"] == "3522",
        "job3522_identity",
    )
    require(first.validate_return(raw, expected_plan=frozen), "job3522_incomplete")
    return {
        "job_id": "3522",
        "return_sha256": FIRST_SHA,
        "completed_main_calls": 3,
        "implementation_first_group_review_passed": True,
        "scientific_reporting_eligible": False,
    }


def plan(commit):
    baseline = first.plan(commit)
    original, cells = first.executor.proposal.build()
    groups = original["groups"][1:7]
    require(
        len(groups) == 6 and all(g["parent"] == "CFL_easy_instance_0" for g in groups),
        "frozen_prefix",
    )
    plans = []
    for group in groups:
        value = copy.deepcopy(baseline)
        value["group"] = group
        value["cells"] = [c for c in cells if c["group_id"] == group["group_id"]]
        plans.append(value)
    return {
        "protocol_id": PROTOCOL,
        "source_commit": commit,
        "first_review": review_first(read(RECEIPT)),
        "groups": plans,
        "maximum_submissions": 6,
        "maximum_optimization_calls": 18,
        "maximum_serial_reservation_seconds": 86400,
        "maximum_physical_core_hours": 128,
        "maximum_solver_seconds": 64800,
        "campaign_completed_calls_before_this_wave": 3,
        "campaign_calls_ceiling": 210,
        "automatic_retry": False,
        "scientific_reporting_eligible": False,
        "dispatch_after_this_wave": False,
    }


def load(stage, policy=None):
    value = parsed(stage / "plan.json")
    planner = plan if policy is None else policy.plan
    prefix = "six-f0-" if policy is None else policy.prefix
    require(value == planner(first.roots.head()), "source_plan_changed")
    require(stage.resolve() == BASE / (prefix + value["source_commit"][:12]), "stage")
    require(not (ROOT / "gurobi.env").exists(), "unexpected_parameter_file")
    return value


def installed_first():
    return review_first(
        read(BASE / ("main-first-" + FIRST_COMMIT[:12]) / "public_return.json")
    )


def prepare(stage):
    first.roots.accounting.host()
    frozen = plan(first.roots.head())
    require(
        stage.resolve() == BASE / ("six-f0-" + frozen["source_commit"][:12]), "stage"
    )
    require(installed_first() == frozen["first_review"], "installed_review")
    first.private_inputs(frozen["groups"][0])
    return {"plan_sha256": write(stage / "plan.json", frozen), "submissions_added": 0}


def group_stage(stage, index):
    require(type(index) is int and 0 <= index < 6, "group_index")
    return stage / f"group-{index}"


def profile(text, job, threads, previous):
    fields = first.held_profile(text, job, threads)
    dependency = first.site.selected_fields(text, {"Dependency"}).get("Dependency")
    if previous is None:
        require(dependency in (None, "(null)", "None"), "unexpected_dependency")
    else:
        require(
            dependency in (f"afterok:{previous}", f"afterok:{previous}(unfulfilled)"),
            "serial_dependency",
        )
    return {"resources": fields, "dependency": dependency}


def submit(stage, approved_sha, policy=None):
    first.roots.accounting.host()
    require(os.environ.get("CONDA_DEFAULT_ENV") == "tfm_env", "environment")
    frozen = load(stage, policy)
    require(digest(read(stage / "plan.json")) == approved_sha, "approved_plan_sha")
    reviewer = installed_first if policy is None else policy.installed_review
    require(reviewer() == frozen["first_review"], "installed_review")
    claim = CLAIM if policy is None else policy.claim
    private = {}
    for group in frozen["groups"]:
        parent = group["group"]["parent"]
        if parent not in private:
            private[parent] = first.private_inputs(group)
    claim.mkdir(exist_ok=False)
    write(claim / "claim.json", {"plan_sha256": approved_sha, "stage": str(stage)})
    write(
        stage / "approval.json",
        {
            "plan_sha256": approved_sha,
            "explicit_user_authorization": True,
            "maximum_submissions": 6,
            "maximum_optimization_calls": 18,
            "included_in_210": True,
            "automatic_retry": False,
        },
    )
    # Every admission is checked before the first scheduler mutation.
    for i, group in enumerate(frozen["groups"]):
        folder = group_stage(stage, i)
        folder.mkdir(exist_ok=False)
        write(folder / "plan.json", group)
        write(folder / "approval.json", first.approval(group))
        mip, starts = private[group["group"]["parent"]]
        first.bundles(group, folder, mip, starts)
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("SBATCH_", "SLURM_", "SRUN_"))
        and k not in ("PYTHONHOME", "PYTHONPATH")
    }
    env.update(
        PR86_SOURCE=str(ROOT), PR86_STAGE=str(stage), PR86_PYTHON=os.sys.executable
    )
    jobs = []
    for i, group in enumerate(frozen["groups"]):
        folder = group_stage(stage, i)
        previous = jobs[-1] if jobs else None
        threads = group["group"]["threads"]
        write(folder / "submission.intent.json", {"index": i, "previous_job": previous})
        args = [
            "sbatch",
            "--parsable",
            "--hold",
            "--partition=batch",
            "--nodes=1-1",
            "--ntasks=1",
            f"--cpus-per-task={threads}",
            "--hint=nomultithread",
            "--mem=64G",
            "--time=04:00:00",
            "--no-requeue",
            "--kill-on-invalid-dep=yes",
            f"--job-name=cfl_pr86_{group['group']['group_id'].split('-')[0].lower()}_{i}",
            "--chdir=" + str(ROOT),
            "--output=" + str(folder / "job-%j.private.out"),
            "--error=" + str(folder / "job-%j.private.err"),
        ]
        if previous:
            args.append("--dependency=afterok:" + previous)
        args += [
            str(
                ROOT
                / "scripts/evidence"
                / ("operate_pr86_six_jobs.sh" if policy is None else policy.operator)
            ),
            "batch",
            str(i),
        ]
        job = first.roots.accounting.command(args, env=env, timeout=30).strip()
        require(
            re.fullmatch(r"[0-9]{1,20}", job) and job not in jobs,
            "ambiguous_sbatch_preserve_claim",
        )
        write(
            folder / "submission.json",
            {"job_id": job, "plan_sha256": digest(encoded(group))},
        )
        held = profile(
            first.roots.accounting.command(
                ["scontrol", "show", "job", job, "--oneliner"]
            ),
            job,
            threads,
            previous,
        )
        write(folder / "held_profile.json", held)
        jobs.append(job)
    write(stage / "chain.json", {"plan_sha256": approved_sha, "job_ids": jobs})
    # Release tail first: the root cannot start before all six jobs are recorded.
    for i in reversed(range(6)):
        folder = group_stage(stage, i)
        write(folder / "release.intent.json", {"job_id": jobs[i]})
        first.roots.accounting.command(["scontrol", "release", jobs[i]])
        write(folder / "released.json", {"job_id": jobs[i]})
    return {
        "job_ids": jobs,
        "submission": "six_serial_jobs_released",
        "automatic_retry": False,
    }


def admitted(stage, frozen, policy=None):
    sha = digest(encoded(frozen))
    require(
        parsed((CLAIM if policy is None else policy.claim) / "claim.json")
        == {"plan_sha256": sha, "stage": str(stage)},
        "campaign_claim",
    )
    require(
        parsed(stage / "approval.json")
        == {
            "plan_sha256": sha,
            "explicit_user_authorization": True,
            "maximum_submissions": 6,
            "maximum_optimization_calls": 18,
            "included_in_210": True,
            "automatic_retry": False,
        },
        "campaign_approval",
    )
    chain = parsed(stage / "chain.json")
    jobs = chain["job_ids"]
    require(
        chain["plan_sha256"] == sha
        and len(jobs) == 6
        and len(set(jobs)) == 6
        and all(re.fullmatch(r"[0-9]{1,20}", j) for j in jobs),
        "chain",
    )
    for i, group in enumerate(frozen["groups"]):
        folder = group_stage(stage, i)
        require(parsed(folder / "plan.json") == group, "group_plan")
        require(
            parsed(folder / "approval.json") == first.approval(group), "group_approval"
        )
        require(
            parsed(folder / "submission.json")
            == {"job_id": jobs[i], "plan_sha256": digest(encoded(group))},
            "submission",
        )
        held = parsed(folder / "held_profile.json")
        text = " ".join(k + "=" + v for k, v in held["resources"].items())
        if held["dependency"] is not None:
            text += " Dependency=" + held["dependency"]
        require(
            profile(
                text, jobs[i], group["group"]["threads"], jobs[i - 1] if i else None
            )
            == held,
            "held_record",
        )
        require(
            parsed(folder / "release.intent.json") == {"job_id": jobs[i]},
            "release_intent",
        )
    return jobs


def checked(stage, frozen, index, jobs):
    folder = group_stage(stage, index)
    members = first.export_members(folder)
    require(
        first.validate_members(frozen["groups"][index], members, jobs[index]),
        "artifact_gate",
    )
    return {
        "job_id": jobs[index],
        "group_plan_sha256": digest(encoded(frozen["groups"][index])),
        "members_sha256": {k: v["sha256"] for k, v in members.items()},
        "artifact_gate_passed": True,
        "scientific_reporting_eligible": False,
    }


def run(stage, index, policy=None):
    frozen = load(stage, policy)
    jobs = admitted(stage, frozen, policy)
    folder = group_stage(stage, index)
    require(os.environ.get("SLURM_JOB_ID") == jobs[index], "allocated_job")
    # afterok supplies scheduler completion; this separate gate supplies evidence validity.
    if index:
        require(
            parsed(group_stage(stage, index - 1) / "checked.json")
            == checked(stage, frozen, index - 1, jobs),
            "predecessor_gate",
        )
    first.executor.allocation(frozen["groups"][index]["group"]["threads"])
    requests = parsed(folder / "requests.json")
    require(
        len(requests) == 3
        and [r["file"] for r in requests] == [f"bundle-{i}.json" for i in range(3)],
        "requests",
    )
    for cell, ref in zip(frozen["groups"][index]["cells"], requests):
        bundle = first.executor.load_bundle(
            folder / "admission" / ref["file"], ref["sha256"]
        )
        require(
            bundle["cell"] == cell
            and bundle["context"] == frozen["groups"][index]["context"],
            "allocated_group_binding",
        )
    started = time.monotonic()
    try:
        result = first.executor.run_group(
            [(folder / "admission" / r["file"], r["sha256"]) for r in requests],
            folder / "run",
        )
    finally:
        write(
            folder / "batch.json",
            {
                "job_id": jobs[index],
                "observed_group_dispatch_seconds": time.monotonic() - started,
                "excludes": [
                    "pre_dispatch_validation",
                    "batch_receipt_write",
                    "queueing",
                ],
                "scientific_reporting_eligible": False,
            },
        )
    if not result["complete"]:
        return 2
    write(folder / "checked.json", checked(stage, frozen, index, jobs))
    return 0


def status(stage, policy=None):
    load(stage, policy)
    records = []
    for i in range(6):
        folder = group_stage(stage, i)
        records.append(
            first.roots.status(folder)
            if (folder / "submission.json").exists()
            else {"index": i, "state": "not_recorded", "terminal": False}
        )
    return {"jobs": records, "terminal": all(r["terminal"] for r in records)}


def validate_return(raw, policy=None):
    value = first.executor.existing.review.flow.meta.strict_json(raw)
    require(
        set(value)
        == {
            "protocol_id",
            "plan",
            "plan_sha256",
            "returns",
            "launch",
            "scientific_reporting_eligible",
            "raw_logs_included",
        },
        "queue_return_schema",
    )
    frozen = value["plan"]
    require(
        value["protocol_id"] == (PROTOCOL if policy is None else policy.protocol)
        and frozen == (plan if policy is None else policy.plan)(frozen["source_commit"])
        and value["plan_sha256"] == digest(encoded(frozen)),
        "queue_return_plan",
    )
    require(
        value["raw_logs_included"] is False
        and value["scientific_reporting_eligible"] is False,
        "queue_return_scope",
    )
    require(len(value["returns"]) == 6, "six_returns")
    require(len(value["launch"]) == 6, "six_launch_records")
    ready, ids = [], []
    for group, returned in zip(frozen["groups"], value["returns"]):
        ids.append(returned["accounting"]["job_id"])
        ready.append(first.validate_return(encoded(returned), expected_plan=group))
    require(len(set(ids)) == 6, "duplicate_jobs")
    for i, launch in enumerate(value["launch"]):
        require(
            set(launch) == {"job_id", "held_profile"} and launch["job_id"] == ids[i],
            "launch_identity",
        )
        held = launch["held_profile"]
        text = " ".join(k + "=" + v for k, v in held["resources"].items())
        if held["dependency"] is not None:
            text += " Dependency=" + held["dependency"]
        require(
            profile(
                text,
                ids[i],
                frozen["groups"][i]["group"]["threads"],
                ids[i - 1] if i else None,
            )
            == held,
            "launch_dependency_resources",
        )
    return {
        "complete_groups": sum(ready),
        "groups": 6,
        "ready_for_independent_review": all(ready),
        "dispatch_after_this_wave": False,
    }


def collect(stage, policy=None):
    frozen = load(stage, policy)
    admitted(stage, frozen, policy)
    states = status(stage, policy)
    require(states["terminal"], "not_terminal_no_wait")
    value = {
        "protocol_id": PROTOCOL if policy is None else policy.protocol,
        "plan": frozen,
        "plan_sha256": digest(encoded(frozen)),
        "returns": [
            first.public_value(group_stage(stage, i), group, states["jobs"][i])
            for i, group in enumerate(frozen["groups"])
        ],
        "launch": [
            {
                "job_id": states["jobs"][i]["job_id"],
                "held_profile": parsed(group_stage(stage, i) / "held_profile.json"),
            }
            for i in range(6)
        ],
        "scientific_reporting_eligible": False,
        "raw_logs_included": False,
    }
    reviewed = validate_return(encoded(value), policy)
    output = stage / "public_return.json"
    if output.exists():
        require(read(output) == encoded(value), "preserve_return")
    else:
        write(output, value)
    return {**reviewed, "return_sha256": digest(read(output)), "output": str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("prepare", "submit", "run", "status", "collect", "review")
    )
    parser.add_argument("--stage", type=Path)
    parser.add_argument("--approved-plan-sha256")
    parser.add_argument("--index", type=int)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    if args.action == "review":
        result = validate_return(read(args.receipt))
    elif args.action == "run":
        return run(args.stage, args.index)
    elif args.action == "submit":
        result = submit(args.stage, args.approved_plan_sha256)
    else:
        result = {"prepare": prepare, "status": status, "collect": collect}[
            args.action
        ](args.stage)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
