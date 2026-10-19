"""Frozen 210-cell analytical closeout; no solver, training, scheduler or network."""

import argparse
import csv
import io
import itertools
import json
import math
import statistics as stats
from collections import Counter
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pr86_wave67 as flow

q = flow.q
f0 = flow.reviewed.audit.old.f0
DEST = q.ROOT / "docs/evidence/pr86/final-210"
PRIOR = flow.reviewed.DEST
SHA = "a3a219799291d2471a9329eda922aca2ac34b29a2dfa77dd63ec1dfe2351ebe7"
SOURCE = "fff8215f57fd51bc6ea471e0999a5c28e095c284"
PLAN = "9f8d29dabb4c5742d49a7db05a6f873b0e92b936b2b93c0c9c24bccb8ae29c64"
PREFIX_MANIFEST = "9ea394e540495239b4812596f21ac458587ccf22165314b26e4735586eb8dda4"
PREP = q.ROOT / "docs/evidence/pr86/job3521/preparation_costs.csv"
PREP_SHA = "b96ca95143d1e5003416577dee29f989105482f8e5da83c3ead00fb5f4b9c680"
CAPS = (1, 2, 4, 8, 16)
COMPARISONS = (("M1", "M0"), ("M2", "M0"), ("M2", "M1"))
METRICS = (
    "solver_seconds",
    "scoped_cold_cost_scenario_seconds",
    "scoped_amortized_cost_scenario_seconds",
    "allocated_cold_scenario_seconds",
    "allocated_amortized_scenario_seconds",
)


def read_csv(raw):
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
    numbers = {
        "solver_seconds",
        "gap_fraction",
        "primal",
        "dual",
        "supervised_attempt_seconds",
        "scoped_preparation_seconds",
        "scoped_cold_cost_scenario_seconds",
        "scoped_amortized_cost_scenario_seconds",
        "sampled_cgroup_peak_bytes",
    }
    for row in rows:
        for key in ("threads", "seed", "method_order_position"):
            row[key] = int(row[key])
        for key in numbers:
            row[key] = float(row[key])
            q.require(math.isfinite(row[key]), "finite_metric")
        q.require(row["right_censored"] in ("True", "False"), "censor_boolean")
        row["right_censored"] = row["right_censored"] == "True"
    return rows


def review(raw):
    # Pin the historical source/plan/receipt. Never rebuild dependency pins from
    # the later analysis tree; the original validator passed on the frozen tree.
    q.require(q.digest(raw) == SHA, "final_return_hash")
    wave = q.first.executor.existing.review.flow.meta.strict_json(raw)
    frozen = wave["plan"]
    q.require(frozen["source_commit"] == SOURCE, "historical_source")
    q.require(wave["plan_sha256"] == q.digest(q.encoded(frozen)) == PLAN, "final_plan")
    proposal, cells = q.first.executor.proposal.build()
    q.require(len(frozen["groups"]) == 3, "final_three_groups")
    for group, expected in zip(frozen["groups"], proposal["groups"][67:70]):
        q.require(group["group"] == expected, "original_manifest_group")
        q.require(
            group["cells"]
            == [c for c in cells if c["group_id"] == expected["group_id"]],
            "original_manifest_cells",
        )
    policy = SimpleNamespace(protocol=flow.POLICY.protocol, plan=lambda _: frozen)
    q.require(
        q.validate_return(raw, policy)["ready_for_independent_review"], "incomplete"
    )
    q.require(
        [r["accounting"]["job_id"] for r in wave["returns"]]
        == ["3662", "3663", "3664"],
        "final_jobs",
    )
    manifest_raw = q.read(PRIOR / "manifest.json")
    q.require(q.digest(manifest_raw) == PREFIX_MANIFEST, "reviewed_prefix_manifest")
    manifest = json.loads(manifest_raw)
    for name, digest in manifest["outputs"].items():
        q.require(q.digest(q.read(PRIOR / name)) == digest, "prefix_asset_hash")
    inventory = json.loads(q.read(PRIOR / "campaign_inventory.json"))
    q.require(
        frozen["first_review"] == {k: inventory[k] for k in frozen["first_review"]},
        "prefix_review_identity",
    )
    rows = read_csv(q.read(PRIOR / "campaign_results.csv"))
    q.require(len(rows) == 201, "reviewed_prefix201")
    added = f0.rows_from_returns(
        wave["returns"], dict.fromkeys(("3662", "3663", "3664"), SHA)
    )
    for row in added:
        row["numerical_scope"] = (
            "M12_tolerance_sensitive_no_exact_optimality_or_certified_speedup"
        )
    rows += added
    q.require(
        len(rows) == len({r["cell_id"] for r in rows}) == 210, "complete210_unique"
    )
    q.require(
        [r["cell_id"] for r in rows] == [c["cell_id"] for c in cells],
        "ordered_manifest210",
    )
    q.require(
        Counter(r["method"] for r in rows) == {"M0": 70, "M1": 70, "M2": 70},
        "method_counts",
    )
    q.require(
        Counter(r["threads"] for r in rows) == {1: 90, 2: 30, 4: 30, 8: 30, 16: 30},
        "cap_counts",
    )
    q.require(
        Counter(r["seed"] for r in rows) == {42: 150, 43: 30, 44: 30}, "seed_counts"
    )
    return rows, inventory, wave


@lru_cache(maxsize=None)
def bootstrap_indices(n):
    q.require(2 <= n <= 6, "bootstrap_parent_count")
    return tuple(itertools.product(range(n), repeat=n))


def paired_summary(logs):
    """Exact empirical parent bootstrap; exploratory model-based sensitivity."""
    q.require(
        2 <= len(logs) <= 6 and all(math.isfinite(v) for v in logs), "paired_logs"
    )
    n = len(logs)
    distribution = sorted(
        sum(logs[i] for i in index) / n for index in bootstrap_indices(n)
    )

    def quantile(p):
        position = p * (len(distribution) - 1)
        lo, hi = math.floor(position), math.ceil(position)
        return distribution[lo] + (distribution[hi] - distribution[lo]) * (
            position - lo
        )

    loo = [math.exp((sum(logs) - v) / (n - 1)) for v in logs]
    return {
        "parents": n,
        "geometric_mean_ratio": math.exp(stats.mean(logs)),
        "bootstrap_percentile_lower_95": math.exp(quantile(0.025)),
        "bootstrap_percentile_upper_95": math.exp(quantile(0.975)),
        "bootstrap_ordered_resamples": n**n,
        "leave_one_parent_out_min": min(loo),
        "leave_one_parent_out_max": max(loo),
        "lower_ratio_parents": sum(v < 0 for v in logs),
        "interpretation": "exploratory_pointwise_exchangeable_parent_model_not_population_coverage",
    }


def annotate_costs(rows):
    # These add an existing full-observed-preparation allocation SCENARIO; they
    # are not new cold-job measurements or measured campaign resource totals.
    preparation_raw = q.read(PREP)
    q.require(q.digest(preparation_raw) == PREP_SHA, "frozen_preparation_costs")
    costs = {
        r["alias"]: r for r in csv.DictReader(io.StringIO(preparation_raw.decode()))
    }
    result = []
    for original in rows:
        row = dict(original)
        method = row["method"]
        cost = costs[row["alias"]]
        for suffix, source in (
            ("cold", "allocated_preparation_scenario_seconds"),
            ("amortized", "allocated_scenario_per_seven_uses_seconds"),
        ):
            preparation = 0.0 if method == "M0" else float(cost[f"{method}_{source}"])
            row[f"allocated_{suffix}_scenario_seconds"] = (
                row["supervised_attempt_seconds"] + preparation
            )
        result.append(row)
    return result


def analyses(rows):
    enriched = annotate_costs(rows)
    easy = sorted(
        {r["alias"] for r in rows if r["alias"].startswith("F")},
        key=lambda s: int(s[1:]),
    )
    aliases = list(dict.fromkeys(r["alias"] for r in rows))
    index = {(r["alias"], r["threads"], r["seed"], r["method"]): r for r in enriched}
    paired, parent_effects, repeats, quality, scaling, gaps = [], [], [], [], [], []
    for cap in CAPS:
        for numerator, denominator in COMPARISONS:
            for metric in METRICS:
                logs = []
                for alias in easy:
                    a, b = (index[alias, cap, 42, m] for m in (numerator, denominator))
                    q.require(
                        not a["right_censored"] and not b["right_censored"],
                        "uncensored_easy_pair",
                    )
                    effect = math.log(a[metric] / b[metric])
                    logs.append(effect)
                    parent_effects.append(
                        dict(
                            parent_alias=alias,
                            threads=cap,
                            seed=42,
                            numerator=numerator,
                            denominator=denominator,
                            metric=metric,
                            ratio=math.exp(effect),
                            log_ratio=effect,
                        )
                    )
                paired.append(
                    dict(
                        threads=cap,
                        seed_scope="seed42",
                        numerator=numerator,
                        denominator=denominator,
                        metric=metric,
                        **paired_summary(logs),
                    )
                )
    for numerator, denominator in COMPARISONS:
        for metric in METRICS:
            logs = []
            for alias in easy:
                effects = [
                    math.log(
                        index[alias, 1, seed, numerator][metric]
                        / index[alias, 1, seed, denominator][metric]
                    )
                    for seed in (42, 43, 44)
                ]
                logs.append(stats.mean(effects))
                repeats.append(
                    dict(
                        parent_alias=alias,
                        numerator=numerator,
                        denominator=denominator,
                        metric=metric,
                        threads=1,
                        seeds=3,
                        geometric_mean_ratio=math.exp(stats.mean(effects)),
                        min_seed_ratio=math.exp(min(effects)),
                        max_seed_ratio=math.exp(max(effects)),
                    )
                )
            paired.append(
                dict(
                    threads=1,
                    seed_scope="parent_mean_log_over_seeds42_43_44",
                    numerator=numerator,
                    denominator=denominator,
                    metric=metric,
                    **paired_summary(logs),
                )
            )
    for alias in aliases:
        for method in ("M0", "M1", "M2"):
            selected = [
                r for r in enriched if r["alias"] == alias and r["method"] == method
            ]
            quality.append(
                dict(
                    parent_alias=alias,
                    method=method,
                    runs=len(selected),
                    reported_target_met=sum(
                        not r["right_censored"] and r["gap_fraction"] <= 1e-4
                        for r in selected
                    ),
                    time_censored=sum(r["right_censored"] for r in selected),
                    terminal_gap_percent_median=stats.median(
                        r["gap_fraction"] * 100 for r in selected
                    ),
                    terminal_gap_percent_min=min(
                        r["gap_fraction"] * 100 for r in selected
                    ),
                    terminal_gap_percent_max=max(
                        r["gap_fraction"] * 100 for r in selected
                    ),
                    max_sampled_cgroup_gib=max(
                        r["sampled_cgroup_peak_bytes"] for r in selected
                    )
                    / 2**30,
                    numerical_scope=selected[0]["numerical_scope"],
                )
            )
        for cap, seed in [(c, 42) for c in CAPS] + [(1, s) for s in (43, 44)]:
            for numerator, denominator in COMPARISONS:
                a, b = (index[alias, cap, seed, m] for m in (numerator, denominator))
                gaps.append(
                    dict(
                        parent_alias=alias,
                        threads=cap,
                        seed=seed,
                        numerator=numerator,
                        denominator=denominator,
                        terminal_gap_difference_percentage_points=(
                            a["gap_fraction"] - b["gap_fraction"]
                        )
                        * 100,
                        numerator_censored=a["right_censored"],
                        denominator_censored=b["right_censored"],
                        numerical_scope=a["numerical_scope"],
                    )
                )
        if alias in easy:
            for cap in CAPS:
                for method in ("M0", "M1", "M2"):
                    speedup = (
                        index[alias, 1, 42, method]["solver_seconds"]
                        / index[alias, cap, 42, method]["solver_seconds"]
                    )
                    scaling.append(
                        dict(
                            parent_alias=alias,
                            threads=cap,
                            seed=42,
                            method=method,
                            own_one_thread_speedup=speedup,
                            own_one_thread_parallel_efficiency=speedup / cap,
                        )
                    )
    return {
        "cost_scenarios.csv": f0.csv_bytes(enriched),
        "paired_uncertainty.csv": f0.csv_bytes(paired),
        "paired_parent_effects.csv": f0.csv_bytes(parent_effects),
        "paired_seed_repeatability.csv": f0.csv_bytes(repeats),
        "parent_method_quality.csv": f0.csv_bytes(quality),
        "paired_terminal_gap.csv": f0.csv_bytes(gaps),
        "easy_cpu_scaling.csv": f0.csv_bytes(scaling),
    }


def slurm_seconds(value):
    """Parse the displayed Slurm duration; keep unavailable distinct from zero."""
    if value in (None, "", "Unknown", "N/A"):
        return None
    days, _, rest = str(value).rpartition("-")
    parts = [float(v) for v in rest.split(":")]
    q.require(
        1 <= len(parts) <= 3 and all(math.isfinite(v) and v >= 0 for v in parts),
        "accounting_duration",
    )
    return (int(days) * 86400 if days else 0) + sum(
        v * 60**i for i, v in enumerate(reversed(parts))
    )


def detailed_sources(rows):
    wanted = {r["receipt_sha256"] for r in rows}
    sources = {}
    for path in (q.ROOT / "docs/evidence/pr86").rglob("public_return.json"):
        raw = q.read(path)
        digest = q.digest(raw)
        if digest in wanted:
            sources[digest] = json.loads(raw)
    q.require(set(sources) == wanted, "all_campaign_receipts_present")
    index = {r["cell_id"]: r for r in rows}
    details, accounting, jobs = [], [], {}
    for digest, value in sources.items():
        returns = value["returns"] if "returns" in value else [value]
        for returned in returns:
            job = returned["accounting"]["job_id"]
            q.require(job not in jobs, "unique_accounted_job")
            job_rows = returned["accounting"]["rows"]
            jobs[job] = next(r for r in job_rows if r["JobID"] == job)
            for record in job_rows:
                accounting.append(
                    dict(
                        job_id=job,
                        accounting_record=record["JobID"],
                        state=record["State"],
                        exit_code=record["ExitCode"],
                        elapsed_seconds=record["ElapsedRaw"],
                        allocated_logical_cpus=record["AllocCPUS"],
                        requested_memory_raw=record["ReqMem"],
                        max_rss_raw=record["MaxRSS"],
                        total_cpu_raw=record["TotalCPU"],
                        total_cpu_seconds=slurm_seconds(record["TotalCPU"]),
                        receipt_sha256=digest,
                    )
                )
            for i, cell in enumerate(returned["plan"]["cells"]):
                child = f0.member(returned, f"run/attempt-{i}/child.json")
                result = child["result"]
                row = index[cell["cell_id"]]
                q.require(
                    row["receipt_sha256"] == digest
                    and row["child_sha256"]
                    == returned["members"][f"run/attempt-{i}/child.json"]["sha256"],
                    "detail_source_link",
                )
                solve = result["solve"]
                times = solve["first_observed_gap_times_seconds"]
                details.append(
                    dict(
                        cell_id=cell["cell_id"],
                        parent_alias=cell["alias"],
                        method=cell["method"],
                        threads=cell["threads"],
                        seed=cell["seed"],
                        effective_objective_sense=result["effective_objective_sense"],
                        model_sha256=result["mip_sha256"],
                        parameter_sha256=result["parameter_sha256"],
                        solver_version=result["solver_version"],
                        python_version=result["python_version"],
                        status_code=solve["solve_status_code"],
                        node_count=solve["node_count"],
                        first_observed_feasible_seconds=solve[
                            "first_observed_feasible_seconds"
                        ],
                        first_observed_gap_1_percent_seconds=times.get("0.01"),
                        first_observed_gap_5_percent_seconds=times.get("0.05"),
                        first_observed_gap_6_percent_seconds=times.get("0.06"),
                        first_observed_gap_10_percent_seconds=times.get("0.1"),
                        terminal_target_fraction=result["parameters"]["MIPGap"],
                        terminal_runtime_seconds=solve["solver_runtime_seconds"],
                        original_scientific_reporting_eligible=result[
                            "scientific_reporting_eligible"
                        ],
                        child_sha256=row["child_sha256"],
                        receipt_sha256=digest,
                    )
                )
    q.require(len(jobs) == 70 and len(details) == 210, "detailed_coverage")
    details.sort(key=lambda r: list(index).index(r["cell_id"]))
    accounting.sort(key=lambda r: (int(r["job_id"]), r["accounting_record"]))
    totals = dict(
        scheduler_job_elapsed_sum_seconds=sum(r["ElapsedRaw"] for r in jobs.values()),
        scheduler_job_total_cpu_sum_seconds=sum(
            slurm_seconds(r["TotalCPU"]) for r in jobs.values()
        ),
        scheduler_jobs_counted_once=70,
        scheduler_totals_include_main_jobs_only_not_root_or_gpu_preparation=True,
        observed_shared_node_contention_qualified=False,
    )
    return {
        "solve_details.csv": f0.csv_bytes(details),
        "scheduler_accounting.csv": f0.csv_bytes(accounting),
    }, totals


def publish(directory):
    rows, before, wave = review(q.read(DEST / "public_return.json"))
    scope = []
    for label, aliases in (
        ("outside_M4_M12", {r["alias"] for r in rows} - {"M4", "M12"}),
        ("M4_sensitive", {"M4"}),
        ("M12_sensitive", {"M12"}),
    ):
        subset = [r for r in rows if r["alias"] in aliases]
        scope.append(
            dict(
                scope=label,
                cells=len(subset),
                reported_target_met=sum(
                    not r["right_censored"] and r["gap_fraction"] <= 1e-4
                    for r in subset
                ),
                time_censored=sum(r["right_censored"] for r in subset),
            )
        )
    records = []
    # The public final records extend only M12; use the original numeric screen.
    old_raw = q.read(flow.reviewed.audit.review.DEST / "public_return.json")
    q.require(q.digest(old_raw) == flow.reviewed.audit.SHA, "m12_original_wave_hash")
    old_wave = json.loads(old_raw)
    for source in (old_wave, wave):
        for returned in source["returns"]:
            for i, cell in enumerate(returned["plan"]["cells"]):
                result = f0.member(returned, f"run/attempt-{i}/child.json")["result"]
                if cell["alias"] == "M12":
                    records.append(
                        dict(
                            cell_id=cell["cell_id"],
                            parent=cell["parent"],
                            model_sha256=result["mip_sha256"],
                            mathematical_signature_sha256=result[
                                "mathematical_signature_sha256"
                            ],
                            model_fingerprint=result["model_fingerprint"],
                            primal=result["solve"]["primal"],
                            dual=result["solve"]["dual"],
                        )
                    )
    findings = flow.reviewed.audit.old.cross_run_findings(records)
    q.require(len(records) == 21 and len(findings) == 14, "final_m12_screen")
    report = dict(
        protocol_id="pr86_final210_metric_scoped_analytical_review_v1",
        input_final_sha256=SHA,
        input_prefix_manifest_sha256=PREFIX_MANIFEST,
        source_commit=SOURCE,
        source_plan_sha256=PLAN,
        completed_cells=210,
        completed_groups=70,
        remaining_cells=0,
        remaining_groups=0,
        historically_exposed_parents=10,
        scope_counts=scope,
        sum_solver_runtime_seconds=sum(r["solver_seconds"] for r in rows),
        max_solver_runtime_seconds=max(r["solver_seconds"] for r in rows),
        final_wave_scheduler_elapsed_sum_seconds=sum(
            r["accounting"]["rows"][0]["ElapsedRaw"] for r in wave["returns"]
        ),
        m12_cross_run_comparisons=14,
        m12_stored_vectors_previously_audited=6,
        new_private_rounded_vector_audits=0,
        author_decisions=before["author_decisions"],
        numeric_audits_sha256=before["numeric_audits_sha256"],
        uncertainty="exploratory_exact_empirical_parent_bootstrap_percentile_pointwise95_no_familywise_or_population_claim",
        timing_endpoint="terminal_solver_return_meeting_configured_target_not_exact_first_crossing",
        first_observed_callback_thresholds_are_not_terminal_target=True,
        terminal_quality_is_not_exact_common_horizon_quality=True,
        cold_and_amortized_costs_are_scoped_scenarios=True,
        whole_job_cold_cost_qualified=False,
        M4_M12_exact_optimality_or_certified_speedup=False,
        original_receipts_and_flags_unchanged=True,
        scientific_reporting_eligible=False,
        metric_specific_analytical_review_completed=True,
        optimization_runs_added=0,
        submissions_added=0,
        training_runs_added=0,
        further_dispatch_admitted=False,
    )
    detail_outputs, accounting_totals = detailed_sources(rows)
    report.update(accounting_totals)
    outputs = {
        "campaign_results.csv": f0.csv_bytes(rows),
        "review.json": q.encoded(report),
        "scope_and_censoring.csv": f0.csv_bytes(scope),
        "m12_cross_run_screen.json": q.encoded(findings),
        **analyses(rows),
        **detail_outputs,
    }
    outputs["manifest.json"] = q.encoded(
        dict(
            inputs=[SHA, PREFIX_MANIFEST, *before["numeric_audits_sha256"].values()],
            preparation_costs_sha256=q.digest(q.read(PREP)),
            outputs={k: q.digest(v) for k, v in outputs.items()},
        )
    )
    directory.mkdir(parents=True, exist_ok=True)
    for name, raw in outputs.items():
        path = directory / name
        if path.exists():
            q.require(q.read(path) == raw, "preserve_output")
        else:
            with path.open("xb") as stream:
                stream.write(raw)
    return report


def seal_assets(directory):
    payloads = {
        p.name: q.digest(q.read(p))
        for p in sorted(directory.iterdir())
        if p.is_file() and p.name != "publication_manifest.json"
    }
    sources = (
        "scripts/evidence/review_pr86_final.py",
        "scripts/evidence/plot_pr86_final.py",
        "tests/evidence/test_pr86_final.py",
    )
    raw = q.encoded(
        dict(
            protocol="pr86_final210_publication_asset_seal_v1",
            historical_source=SOURCE,
            final_return_sha256=SHA,
            payloads_sha256=payloads,
            source_sha256_lf={
                name: q.digest(q.read(q.ROOT / name).replace(b"\r\n", b"\n"))
                for name in sources
            },
        )
    )
    path = directory / "publication_manifest.json"
    if path.exists():
        q.require(q.read(path) == raw, "preserve_publication_seal")
    else:
        with path.open("xb") as handle:
            handle.write(raw)
    return {"publication_payloads": len(payloads), "source_files": len(sources)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEST)
    parser.add_argument("--seal", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            seal_assets(args.output) if args.seal else publish(args.output), indent=2
        )
    )
