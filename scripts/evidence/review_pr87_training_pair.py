"""Offline, scoped review of jobs3673/3674; no torch, training or scheduler."""

import argparse
import csv
import io
import json
import math
from pathlib import Path

import pr87_contract as c
import pr87_workflow as workflow

SHA = "909f6ce85dfdd9541e1624f8774bb099f27752e21408270f695e81aba7d576ab"
SOURCE = "a2fef6040c71cbbf63c29e9f712e868ba7bfa42b"
AUTH = "74df18d2da3711598528864932ab3336ca13af92701374e126e7a0fa260953b5"
DECISION = "https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/pull/87#issuecomment-6292612875"
DEST = c.REPO / "docs/evidence/pr87/jobs3673-3674"
METRICS = ("precision", "recall", "f1_score", "pr_auc", "brier")
GIB = 1024**3


def encoded(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def finite(value, code, minimum=0):
    c.require(
        type(value) in (int, float) and math.isfinite(value) and value >= minimum,
        code,
    )
    return value


def close(a, b, code):
    c.require(math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-9), code)


def mean(values):
    return math.fsum(values) / len(values)


def alias(parent):
    _, difficulty, _, number = parent.split("_")
    return ("F" if difficulty == "easy" else "M") + number


def cpu_seconds(text):
    parts = text.split(":")
    c.require(1 <= len(parts) <= 3, "cpu_time_format")
    value = 0.0
    for part in parts:
        value = value * 60 + float(part)
    return finite(value, "cpu_time")


def audit(value):
    workflow.review(value)
    c.require(value["ready_for_independent_review"] is True, "complete_receipt")
    c.require(value["plan"]["source_commit"] == SOURCE, "released_source")
    c.require(value["approval"]["authorization_sha256"] == AUTH, "replacement_auth")
    c.require(
        value["approval"]["decision_reference"] == DECISION, "replacement_decision"
    )
    prior = c.read(c.REPO / "docs/evidence/pr87/job3671/public_return.json")
    c.require(
        value["approval"]["bindings_sha256"] == prior["approval"]["bindings_sha256"],
        "reused_input_bindings",
    )
    summaries, timings, quality, aggregates, history, ranks = [], [], [], [], [], []
    for index, (result, supervisor, job) in enumerate(
        zip(value["results"], value["supervisors"], value["accounting"]["jobs"])
    ):
        world = (1, 4)[index]
        job_id = ("3673", "3674")[index]
        c.require(result["job_id"] == job["job_id"] == job_id, "replacement_job_ids")
        c.require(result["world_size"] == world, "world")
        arm = "serial1" if index == 0 else "ddp4"
        observed = next(r for r in job["rows"] if r["JobID"] == job_id)
        batch = next(r for r in job["rows"] if r["JobID"] == job_id + ".batch")
        elapsed = finite(observed["ElapsedRaw"], "elapsed", 1)
        c.require(elapsed <= 43200, "wall_budget")
        c.require(observed["ReqMem"] == "128G", "requested_memory")
        c.require(
            batch["State"] == "COMPLETED" and batch["ExitCode"] == "0:0", "batch_exit"
        )
        c.require(batch["MaxRSS"].endswith("K"), "rss_unit")
        rss = int(batch["MaxRSS"][:-1]) * 1024
        epochs = result["history"]
        best = min(epochs, key=lambda row: row["validation_loss"])
        c.require(best["epoch"] == result["best_epoch"], "validation_selected_epoch")
        close(
            best["validation_loss"],
            result["best_validation_loss"],
            "validation_selected_loss",
        )
        close(
            math.fsum(
                finite(r["training_seconds"], "epoch_time", 1e-12) for r in epochs
            ),
            result["training_loop_seconds"],
            "epoch_time_sum",
        )
        prep = finite(result["preparation_seconds"], "preparation_time")
        loop = result["training_loop_seconds"]
        region = result["training_validation_checkpoint_seconds"]
        process = result["process_wall_seconds"]
        supervised = finite(supervisor["supervisor_wall_seconds"], "supervisor_time", 1)
        c.require(
            0 < loop <= region < process <= supervised <= elapsed + 2,
            "nested_timing_scopes",
        )
        c.require(prep + region <= process, "preparation_timing_scope")
        # The frozen trainer records pos_weight after rounding it to float32.
        c.require(
            math.isclose(
                result["training_negative_targets"]
                / result["training_positive_targets"],
                result["pos_weight"],
                rel_tol=1e-7,
            ),
            "positive_weight_float32",
        )
        c.require(
            result["prenorm"]["training_graphs"] == 34
            and result["prenorm"]["validation_or_test_used"] is False,
            "train_only_fit",
        )
        c.require(
            result["runtime"]["packages_modified"] is False, "unchanged_environment"
        )
        c.require("V100" in result["gpu_type"], "gpu_model")
        resources = result["rank_resources"]
        c.require(
            len(resources) == world
            and {r["rank"] for r in resources} == set(range(world)),
            "rank_coverage",
        )
        all_cpus = []
        for rank in resources:
            cpus = rank["affinity"]["logical_cpu_ids"]
            c.require(
                rank["affinity"]["physical_cores"] == 4
                and len(cpus) == len(set(cpus)) == 4,
                "rank_physical_affinity",
            )
            all_cpus.extend(cpus)
            allocated = finite(rank["gpu_peak_allocated_bytes"], "gpu_allocated", 1)
            reserved = finite(rank["gpu_peak_reserved_bytes"], "gpu_reserved", 1)
            c.require(allocated <= reserved <= 32 * GIB, "device_allocator_scope")
            ranks.append(
                {
                    "arm": arm,
                    "job_id": job_id,
                    "rank": rank["rank"],
                    "reported_physical_cores": 4,
                    "gpu_allocated_peak_gib": allocated / GIB,
                    "gpu_reserved_peak_gib": reserved / GIB,
                }
            )
        c.require(len(set(all_cpus)) == 4 * world, "disjoint_rank_affinity")
        peak = finite(supervisor["sampled_cgroup_peak_bytes"], "host_peak", 1)
        c.require(
            supervisor["kernel_ram_limit_bytes"] == 128 * GIB
            and supervisor["host_memory_stop_bytes"] == 112 * GIB
            and peak < 112 * GIB,
            "memory_limits",
        )
        telemetry = supervisor["gpu_telemetry"]
        c.require(
            telemetry["interval_seconds"] == 5 and telemetry["samples"] > 0,
            "telemetry_sampling",
        )
        util = telemetry["gpu_utilization_mean_percent"]
        mem = telemetry["gpu_sampled_max_memory_mib"]
        power = telemetry["gpu_sampled_mean_power_watts"]
        c.require(len(util) == len(mem) == len(power) == world, "telemetry_devices")
        c.require(
            all(0 <= finite(x, "utilization") <= 100 for x in util), "utilization_range"
        )
        c.require(
            all(0 < finite(x, "gpu_sampled_memory") <= 32768 for x in mem),
            "sampled_gpu_memory",
        )
        c.require(
            all(finite(x, "sampled_power") > 0 for x in power), "sampled_power_range"
        )
        for rank, utilization, memory, watts in zip(ranks[-world:], util, mem, power):
            rank.update(
                {
                    "gpu_utilization_sample_mean_pct": utilization,
                    "device_memory_sample_max_mib": memory,
                    "device_power_sample_mean_w": watts,
                }
            )
        summaries.append(
            {
                "arm": arm,
                "job_id": job_id,
                "gpus": world,
                "physical_cores_reported": 4 * world,
                "slurm_alloc_cpus": observed["AllocCPUS"],
                "epochs": 100,
                "updates": 3400,
                "global_draws": 13600,
                "preparation_seconds": prep,
                "training_loop_seconds": loop,
                "training_validation_checkpoint_seconds": region,
                "process_wall_seconds": process,
                "supervisor_wall_seconds": supervised,
                "job_elapsed_seconds": elapsed,
                "allocated_gpu_hours": world * elapsed / 3600,
                "physical_core_allocation_hours": world * 4 * elapsed / 3600,
                "slurm_total_cpu_seconds": cpu_seconds(observed["TotalCPU"]),
                "cpu_seconds_per_alloc_logical_elapsed": cpu_seconds(
                    observed["TotalCPU"]
                )
                / (observed["AllocCPUS"] * elapsed),
                "sampled_cgroup_peak_gib": peak / GIB,
                "slurm_batch_maxrss_gib": rss / GIB,
                "gpu_sample_utilization_mean_pct": mean(util),
                "gpu_samples": telemetry["samples"],
                "gpu_missing_queries": telemetry["missing_queries"],
                "selected_epoch": result["best_epoch"],
                "selected_validation_loss": result["best_validation_loss"],
                "selected_threshold": result["selected_threshold"],
                "terminal_threshold": result["terminal_threshold"],
                "loop_global_draws_per_second": 13600 / loop,
                "loop_updates_per_second": 3400 / loop,
            }
        )
        for row in epochs:
            history.append({"arm": arm, "job_id": job_id, **row})
        for which in ("selected", "terminal"):
            rows = result["test"][which]
            for row in rows:
                finite(row["brier"], "brier")
                c.require(row["brier"] <= 1, "brier_range")
                quality.append(
                    {
                        "arm": arm,
                        "checkpoint": which,
                        "job_id": job_id,
                        "alias": alias(row["parent"]),
                        "difficulty": row["parent"].split("_")[1],
                        **row,
                    }
                )
            for scope in ("all", "easy", "medium"):
                chosen = [
                    r
                    for r in rows
                    if scope == "all" or r["parent"].split("_")[1] == scope
                ]
                aggregates.append(
                    {
                        "arm": arm,
                        "checkpoint": which,
                        "scope": scope,
                        "averaging": "parent_macro",
                        "parents": len(chosen),
                        **{k: mean([r[k] for r in chosen]) for k in METRICS},
                    }
                )
            pooled = result["test_pooled"][which]
            close(
                math.fsum(r["n_targets"] * r["brier"] for r in rows)
                / pooled["n_targets"],
                pooled["brier"],
                "pooled_brier",
            )
            aggregates.append(
                {
                    "arm": arm,
                    "checkpoint": which,
                    "scope": "all",
                    "averaging": "pooled_binary",
                    "parents": 10,
                    **{k: pooled[k] for k in METRICS},
                }
            )
    a, b = summaries
    reference_counts = {}
    for row in quality:
        counts = (row["n_targets"], row["n_positive"])
        c.require(
            reference_counts.setdefault(row["parent"], counts) == counts,
            "paired_reference_counts",
        )
    c.require(
        value["results"][0]["runtime"] == value["results"][1]["runtime"], "runtime_pair"
    )
    for key in (
        "training_positive_targets",
        "training_negative_targets",
        "torch_cuda_build",
        "nccl_version",
        "gpu_type",
    ):
        c.require(
            value["results"][0][key] == value["results"][1][key],
            "paired_input_environment",
        )
    for field in (
        "training_loop_seconds",
        "training_validation_checkpoint_seconds",
        "process_wall_seconds",
        "supervisor_wall_seconds",
        "job_elapsed_seconds",
    ):
        ratio = a[field] / b[field]
        timings.append(
            {
                "scope": field,
                "serial_seconds": a[field],
                "ddp4_seconds": b[field],
                "speedup": ratio,
                "parallel_efficiency": ratio / 4,
                "wall_reduction_fraction": 1 - b[field] / a[field],
            }
        )
    deltas = []
    for metric in ("f1_score", "pr_auc"):
        for which in ("selected", "terminal"):
            serial = {
                r["parent"]: r
                for r in quality
                if r["arm"] == "serial1" and r["checkpoint"] == which
            }
            ddp = {
                r["parent"]: r
                for r in quality
                if r["arm"] == "ddp4" and r["checkpoint"] == which
            }
            for parent in serial:
                delta = ddp[parent][metric] - serial[parent][metric]
                deltas.append(
                    {
                        "checkpoint": which,
                        "metric": metric,
                        "parent": parent,
                        "alias": alias(parent),
                        "difficulty": parent.split("_")[1],
                        "serial": serial[parent][metric],
                        "ddp4": ddp[parent][metric],
                        "ddp4_minus_serial": delta,
                    }
                )
    selected = {
        k: mean(
            [
                r["ddp4_minus_serial"]
                for r in deltas
                if r["checkpoint"] == "selected" and r["metric"] == k
            ]
        )
        for k in ("f1_score", "pr_auc")
    }
    assessment = {
        "review_protocol": "pr87_completed_pair_scoped_review_v1",
        "source_return_sha256": SHA,
        "execution_source_commit": SOURCE,
        "authorization_sha256": AUTH,
        "technical_pair_complete": True,
        "matched_learning_work_reconciled": True,
        "scope": "single_seed42_serial_then_ddp4_case_with_scaled_cpu_resources",
        "selected_macro_ddp4_minus_serial": selected,
        "selected_f1_parents_lower": sum(
            r["ddp4_minus_serial"] < 0
            for r in deltas
            if r["checkpoint"] == "selected" and r["metric"] == "f1_score"
        ),
        "descriptive_loss_margin_absolute": 0.02,
        "f1_loss_exceeds_margin": selected["f1_score"] < -0.02,
        "pr_auc_loss_exceeds_margin": selected["pr_auc"] < -0.02,
        "quality_preservation_supported": False,
        "statistical_noninferiority_claimed": False,
        "training_seed_uncertainty_estimated": False,
        "independent_generalization_claimed": False,
        "raw_receipt_scientific_flag_unchanged": value["scientific_reporting_eligible"]
        is False,
        "qualified_descriptive_scopes": [
            "matched_recorded_work",
            "recorded_timing_scopes",
            "resource_accounting_with_scope_limits",
            "recorded_predictive_case_metrics",
        ],
        "independent_probability_rescoring_performed": False,
        "cause_of_trajectory_divergence_proven": False,
        "allocated_gpu_hours_pair": math.fsum(
            r["allocated_gpu_hours"] for r in summaries
        ),
        "additional_jobs_authorized": False,
        "submissions_added": 0,
        "training_runs_added": 0,
        "optimization_runs_added": 0,
        "automatic_retry": False,
    }
    return {
        "summary": summaries,
        "timings": timings,
        "quality": quality,
        "aggregates": aggregates,
        "history": history,
        "ranks": ranks,
        "deltas": deltas,
        "assessment": assessment,
    }


def products(raw):
    c.require(c.sha(raw) == SHA, "training_return_hash")
    result = audit(json.loads(raw))
    output = {"public_return.json": raw, "review.json": encoded(result["assessment"])}
    for key in (
        "summary",
        "timings",
        "quality",
        "aggregates",
        "history",
        "ranks",
        "deltas",
    ):
        output[key + ".csv"] = csv_bytes(result[key])
    output["manifest.json"] = encoded(
        {
            "source_return_sha256": SHA,
            "execution_source_commit": SOURCE,
            "generator": "scripts/evidence/review_pr87_training_pair.py",
            "outputs": {name: c.sha(content) for name, content in output.items()},
            "submissions_added": 0,
            "training_runs_added": 0,
        }
    )
    return output


def save(output, directory):
    directory.mkdir(parents=True, exist_ok=True)
    for name, raw in output.items():
        path = directory / name
        if path.exists():
            c.require(path.read_bytes() == raw, "preserve_existing_analysis")
        else:
            with path.open("xb") as stream:
                stream.write(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEST)
    args = parser.parse_args()
    output = products(args.receipt.read_bytes())
    save(output, args.output)
    print(output["review.json"].decode())


if __name__ == "__main__":
    main()
