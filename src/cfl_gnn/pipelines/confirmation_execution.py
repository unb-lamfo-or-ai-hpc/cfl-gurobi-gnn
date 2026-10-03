"""Recover a frozen confirmation cohort without relaxing label admission.

Historical files are read-only. Published plans contain relative paths and hashes,
never workstation paths. A label gate does not certify graph or training readiness.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import pickle
from pathlib import Path

from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.pipelines.confirmation_campaign import COHORT
from cfl_gnn.training.gasse_reconnected import canonical_sha256, write_json
from cfl_gnn.validation.mathematical import audit_gurobi_solution, common_gap

PLAN = "confirmation_execution_plan.json"
REPORT = "confirmation_source_report.json"
INVENTORY_KEYS = ("schema_version", "cohort", "seed", "epochs", "objective_sense",
                  "rotation", "maximum_label_mip_gap_relative", "rescue_budgets_seconds",
                  "parent_manifest_sha256", "records")


def error_reason(error):
    """Expose actionable diagnostics without leaking filenames or credentials."""
    message = str(error)
    if isinstance(error, ValueError) and message and all(ch.isalnum() or ch in " -;" for ch in message):
        return message[:180]
    return "artifact unreadable or schema invalid"


def read_json(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def safe_path(root, relative):
    root = Path(root).resolve()
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("invalid relative artifact path")
    part = Path(relative)
    if part.is_absolute() or ":" in relative or ".." in part.parts:
        raise ValueError("unsafe artifact path")
    path = (root / part).resolve()
    if not path.is_relative_to(root):
        raise ValueError("artifact escaped its root")
    return path


def checked(root, descriptor):
    path = safe_path(root, descriptor["relative_path"])
    if not path.is_file() or sha256_file(path) != descriptor["sha256"]:
        raise ValueError("artifact missing or changed since planning")
    return path


def descriptor(root, path):
    path, root = Path(path).resolve(), Path(root).resolve()
    return {"relative_path": path.relative_to(root).as_posix(), "sha256": sha256_file(path)}


def validate_plan(plan):
    payload = {k: v for k, v in plan.items() if k != "contract_sha256"}
    if canonical_sha256(payload) != plan.get("contract_sha256"):
        raise ValueError("execution plan contract mismatch")
    if ([t["source_instance_id"] for t in plan["tasks"]] != list(COHORT)
            or plan["objective_sense"] != "MINIMIZE" or plan["seed"] != 42
            or plan["maximum_label_mip_gap_relative"] != .1 or plan["epochs"] != 100
            or plan["repair_budgets_seconds"] != [3600, 14400]):
        raise ValueError("frozen cohort or admission policy changed")
    if plan["implementation_sha256"] != implementation_hashes():
        raise ValueError("implementation changed; use a new campaign plan")


def implementation_hashes():
    from cfl_gnn.validation import mathematical
    from cfl_gnn.pipelines import parent_collection_task
    return {"confirmation_execution": sha256_file(Path(__file__)),
            "independent_validation": sha256_file(Path(mathematical.__file__)),
            "parent_collection_task": sha256_file(Path(parent_collection_task.__file__))}


def prepare(*, inventory_path, data_root, output_dir):
    """Index existing original-parent Gurobi solutions; do not deserialize graphs."""
    data, output = Path(data_root).resolve(), Path(output_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("use a new campaign directory; historical outputs are immutable")
    inventory = read_json(inventory_path)
    if (canonical_sha256({k: inventory[k] for k in INVENTORY_KEYS}) != inventory["contract_sha256"]
            or inventory["cohort"] != list(COHORT)
            or [r["source_instance_id"] for r in inventory["records"]] != list(COHORT)
            or inventory["maximum_label_mip_gap_relative"] != .1
            or inventory["seed"] != 42 or inventory["objective_sense"] != "MINIMIZE"
            or inventory["epochs"] != 100 or inventory["rotation"] != 0):
        raise ValueError("inventory is not the frozen confirmation contract")
    from cfl_gnn.paths import PROJECT_ROOT
    from cfl_gnn.splits.instance_folds import read_manifest, role_for_fold
    manifest = PROJECT_ROOT / "configs/splits/cfl_90_seed42_folds.csv"
    if sha256_file(manifest) != inventory["parent_manifest_sha256"]:
        raise ValueError("canonical split changed")
    folds = {e.source_instance_id: e for e in read_manifest(manifest)}
    report_index = {identity: [] for identity in COHORT}
    rejected_reports = []
    intermediate = data / "intermediate"
    if intermediate.is_dir():
        for path in sorted(intermediate.rglob("gurobi_parent_solve_report.json")):
            try:
                report = read_json(path)
                identity = report.get("parent", {}).get("source_instance_id")
                if identity in report_index:
                    report_index[identity].append(descriptor(data, path))
            except (ValueError, OSError, TypeError):
                rejected_reports.append(path.name)
    tasks = []
    for index, row in enumerate(inventory["records"]):
        identity = row["source_instance_id"]
        entry = folds[identity]
        if row["fold"] != entry.fold or row["role"] != role_for_fold(entry.fold, 0):
            raise ValueError("inventory role differs from canonical split")
        graph = safe_path(data / "bipartite_graphs/instance_baseline_smoke", row["graph_relative_path"])
        sidecar = graph.with_suffix(".provenance.json")
        if sha256_file(graph) != row["graph_sha256"] or sha256_file(sidecar) != row["provenance_sha256"]:
            raise ValueError("frozen graph or provenance hash mismatch")
        category = identity.rsplit("_", 1)[0]
        mip = data / "raw/MILPBench/CFL" / category / "LP" / f"{identity}.lp.gz"
        provenance = read_json(sidecar)
        mip_descriptor = descriptor(data, mip)
        if provenance["structure_provenance"]["raw_instance_sha256"] != mip_descriptor["sha256"]:
            raise ValueError("legacy label is linked to another original MIP")
        legacy_dir = data / "intermediate_lps" / category / identity
        files = {}
        for name in ("original_features.pickle.gz", "metadata.json", "solutions.pickle.gz", "incumbents.parquet"):
            path = legacy_dir / name
            if path.is_file():
                files[name] = descriptor(data, path)
        tasks.append({"task_index": index, "source_instance_id": identity,
                      "difficulty": row["difficulty"], "fold": entry.fold, "role": row["role"],
                      "mip": mip_descriptor, "graph": descriptor(data, graph),
                      "provenance": descriptor(data, sidecar), "legacy_files": files,
                      "existing_parent_reports": report_index[identity]})
    payload = {"schema_version": 1, "inventory_sha256": sha256_file(inventory_path),
               "inventory_contract_sha256": inventory["contract_sha256"], "tasks": tasks,
               "seed": 42, "objective_sense": "MINIMIZE", "epochs": 100,
               "maximum_label_mip_gap_relative": .1, "repair_budgets_seconds": [3600, 14400],
               "development_only": True, "scientific_reporting_eligible": False,
               "unreadable_discovery_report_count": len(rejected_reports),
               "implementation_sha256": implementation_hashes()}
    # Both budgets cover the identical 42-task ordering, but are executed only
    # after compatible sources fail independent admission for that parent.
    from cfl_gnn.pipelines.parent_population import (
        write_parent_collection_plan, DEFAULT_CAMPAIGN_CONFIG, DEFAULT_EXPERIMENT_CONFIG)
    for budget in payload["repair_budgets_seconds"]:
        write_parent_collection_plan(base_source_dir=data / "raw/MILPBench/CFL",
            output_dir=output / f"repair_{budget}s", parent_manifest_path=manifest,
            campaign_config_path=DEFAULT_CAMPAIGN_CONFIG, experiment_config_path=DEFAULT_EXPERIMENT_CONFIG,
            instances=list(COHORT), time_limit=budget, overwrite=False)
    payload["repair_plans"] = {str(budget): descriptor(output, output / f"repair_{budget}s/parent_collection_plan.json")
                               for budget in payload["repair_budgets_seconds"]}
    plan = {**payload, "contract_sha256": canonical_sha256(payload)}
    write_json(output / PLAN, plan)
    return plan


class LegacyUnpickler(pickle.Unpickler):
    """Compatibility for trusted, hash-verified project artifacts only."""
    def find_class(self, module, name):
        if module == "__main__" and name in ("ModelFeatures", "VariableFeatures", "ConstraintFeatures"):
            from cfl_gnn.artifacts import schemas
            return getattr(schemas, name)
        return super().find_class(module, name)


def legacy_order_matches(model, raw):
    """Verify historical float32 column/row identity against the original model.

The old writer stored edges as variable, constraint. Equality is checked at
the writer's actual precision; solution feasibility is checked in float64.
"""
    import numpy as np
    from scipy.sparse import coo_matrix
    vs, cs = model.getVars(), model.getConstrs()
    vf, cf, mf = raw["variable_features"], raw["constraint_features"], raw["model_features"]
    if mf.obj_sense != 1 or mf.num_vars != len(vs) or mf.num_constrs != len(cs):
        return False
    pairs = ((vf.types, [v.VType for v in vs]), (cf.senses, [c.Sense for c in cs]))
    if any(not np.array_equal(a, b) for a, b in pairs):
        return False
    pairs = ((vf.lower_bounds, [v.LB for v in vs]), (vf.upper_bounds, [v.UB for v in vs]),
             (vf.obj_coeffs, [v.Obj for v in vs]), (cf.rhs_values, [c.RHS for c in cs]))
    if any(not np.array_equal(np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)) for a, b in pairs):
        return False
    edges = np.asarray(raw["edge_indices"])
    old = coo_matrix((np.asarray(raw["edge_features"], dtype=np.float32), (edges[1], edges[0])),
                     shape=(len(cs), len(vs))).tocsr()
    current = model.getA().astype(np.float32).tocsr()
    return bool((old != current).nnz == 0 and float(mf.obj_offset) == float(model.ObjCon))


def eligible_gap(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= .1


def named_candidate(model, data, task, report_descriptor):
    path = checked(data, report_descriptor)
    report = read_json(path)
    parent = report.get("parent", {})
    if (parent.get("source_instance_id") != task["source_instance_id"]
            or parent.get("sha256") != task["mip"]["sha256"]):
        raise ValueError("parent identity mismatch")
    if report.get("gate_status") not in {"passed", "inconclusive"} or report.get("eligibility", {}).get("label_eligible") is not True:
        return None
    artifact = report.get("artifacts", {}).get("solution", {})
    solution_path = checked(path.parent, {"relative_path": artifact["file_name"], "sha256": artifact["sha256"]})
    with gzip.open(solution_path, "rt", encoding="utf-8") as stream:
        solution = json.load(stream)
    if (solution.get("solution_source") != "independent_gurobi_optimization"
            or str(solution.get("effective_objective_sense", "")).lower() != "minimize"):
        raise ValueError("solution source or objective policy mismatch")
    gap = solution.get("mip_gap_relative")
    if not eligible_gap(gap):
        return None
    records = solution["variables"]
    named = {v["name"]: float(v["value"]) for v in records}
    if len(named) != len(records):
        raise ValueError("duplicate variable name")
    audit = audit_gurobi_solution(model, named, solution["solution_objective"])
    if not audit["valid"]:
        raise ValueError("independent mathematical validation failed")
    bound = solution.get("best_bound")
    bound_gap = common_gap(audit["recomputed_objective"], bound)
    if not eligible_gap(bound_gap) or not math.isclose(gap, bound_gap, rel_tol=1e-5, abs_tol=1e-8):
        raise ValueError("terminal gap is inconsistent with primal and dual bounds")
    if bound > audit["recomputed_objective"] + 1e-6:
        raise ValueError("minimization dual bound exceeds the primal objective")
    return {"named": named, "audit": audit, "mip_gap_relative": gap,
            "execution_time_seconds": solution.get("execution_time_seconds"),
            "origin": "hash_verified_original_parent_report", "source_artifact": descriptor(data, solution_path),
            "source_report": report_descriptor,
            "time_regions": solution.get("time_regions"),
            "time_semantics": "recorded_solver_wall_time_not_current_audit_duration"}


def legacy_candidate(model, data, task):
    """Import only the frozen selected record, never graph.y or a pool-wide gap."""
    sidecar = read_json(checked(data, task["provenance"]))
    label = sidecar["label_provenance"]
    if not eligible_gap(label.get("mip_gap")):
        return None
    files = task["legacy_files"]
    feature_path = checked(data, files["original_features.pickle.gz"])
    if files["original_features.pickle.gz"]["sha256"] != sidecar["structure_provenance"]["feature_artifact_sha256"]:
        raise ValueError("legacy feature provenance mismatch")
    with gzip.open(feature_path, "rb") as stream:
        raw = LegacyUnpickler(stream).load()
    if not legacy_order_matches(model, raw):
        raise ValueError("legacy positional variable identity not established")
    metadata = read_json(checked(data, files["metadata.json"]))
    if files["metadata.json"]["sha256"] != sidecar["collection_provenance"]["artifact_sha256"]:
        raise ValueError("legacy metadata provenance mismatch")
    if metadata.get("instance") != task["source_instance_id"] or metadata.get("objective_sense_override") != "MINIMIZE":
        raise ValueError("legacy parent or objective policy mismatch")
    artifact = label["artifact"]
    selected_path = checked(data, files[artifact])
    if files[artifact]["sha256"] != label["artifact_sha256"]:
        raise ValueError("legacy label artifact mismatch")
    index = int(label["source_index"])
    if index < 0:
        raise ValueError("invalid selected record index")
    if artifact == "solutions.pickle.gz":
        with gzip.open(selected_path, "rb") as stream:
            record = LegacyUnpickler(stream).load()["solution_pool"][index]
        # A terminal pool gap belongs to the best solution, not every pool row.
        if not math.isclose(float(record["objective"]), float(metadata["best_objective"]), rel_tol=1e-8, abs_tol=1e-8):
            raise ValueError("pool record cannot inherit the best solution gap")
        gap = metadata["mip_gap"]
    elif artifact == "incumbents.parquet":
        import pyarrow.parquet as pq
        offset, record = 0, None
        for batch in pq.ParquetFile(selected_path).iter_batches(batch_size=8):
            if offset + batch.num_rows > index:
                record = batch.slice(index-offset, 1).to_pylist()[0]
                break
            offset += batch.num_rows
        if record is None:
            raise ValueError("incumbent index missing")
        gap = common_gap(float(record["objective"]), float(record["bound"]))
        if float(record["bound"]) > float(record["objective"]) + 1e-6:
            raise ValueError("incumbent dual bound exceeds primal objective")
    else:
        raise ValueError("unsupported legacy label artifact")
    if not eligible_gap(gap):
        return None
    if not math.isclose(float(record["objective"]), float(label["objective"]), rel_tol=1e-8, abs_tol=1e-8):
        raise ValueError("selected objective provenance mismatch")
    names, vector = [v.VarName for v in model.getVars()], record["solution_vector"]
    if len(names) != len(vector):
        raise ValueError("legacy vector length mismatch")
    named = dict(zip(names, map(float, vector)))
    audit = audit_gurobi_solution(model, named, float(record["objective"]))
    if not audit["valid"]:
        raise ValueError("legacy label failed independent original-MIP validation")
    runtime = metadata.get("runtime")
    return {"named": named, "audit": audit, "mip_gap_relative": gap,
            "execution_time_seconds": runtime, "origin": "independently_audited_legacy_record",
            "source_artifact": files[artifact], "source_index": index,
            "time_regions": None, "missing_time_regions_reason": "not_recorded_in_legacy_run",
            "time_semantics": "terminal_legacy_runtime_not_incumbent_epoch",
            "legacy_gap_semantics": "best_pool_terminal_gap" if artifact == "solutions.pickle.gz" else "callback_primal_dual_gap"}


def choose(candidates):
    accepted = [c for c in candidates if c is not None]
    return min(accepted, key=lambda c: (c["audit"]["recomputed_objective"], c["mip_gap_relative"],
                                      c["source_artifact"]["sha256"])) if accepted else None


def execute(*, campaign_dir, data_root, task_index, repair=False):
    """Audit each source before reuse; optionally solve only an unadmitted parent."""
    import gurobipy as gp
    from gurobipy import GRB
    campaign, data = Path(campaign_dir).resolve(), Path(data_root).resolve()
    plan = read_json(campaign / PLAN)
    validate_plan(plan)
    if not 0 <= task_index < len(plan["tasks"]):
        raise ValueError("task index is outside frozen 42-parent inventory")
    task = plan["tasks"][task_index]
    mip = checked(data, task["mip"])
    checked(data, task["graph"])
    checked(data, task["provenance"])
    output = campaign / "labels" / task["source_instance_id"]
    if (output / REPORT).exists():
        previous = read_json(output / REPORT)
        if (previous.get("campaign_contract_sha256") == plan["contract_sha256"]
                and previous.get("label_eligible") is True):
            checked(output, previous["solution"])
            # Reaudit named values against the original MIP below; not a gate-only resume.
    else:
        previous = None
    errors, sources, repair_outcomes = [], [], []
    with gp.Env(empty=True) as env:
        env.setParam("OutputFlag", 0)
        env.start()
        with gp.read(str(mip), env=env) as model:
            model.ModelSense = GRB.MINIMIZE
            model.update()
            if previous is not None and previous.get("label_eligible") is True:
                if previous.get("campaign_contract_sha256") != plan["contract_sha256"]:
                    raise ValueError("existing result belongs to another campaign")
                path = checked(output, previous["solution"])
                selection = previous["selected"]
                source_root = campaign if selection.get("source_root_alias") == "campaign" else data
                checked(source_root, selection["source_artifact"])
                if "source_report" in selection:
                    checked(source_root, selection["source_report"])
                if selection["origin"] == "independently_audited_legacy_record":
                    for name in ("metadata.json", "original_features.pickle.gz"):
                        checked(data, task["legacy_files"][name])
                with gzip.open(path, "rt", encoding="utf-8") as stream:
                    payload = json.load(stream)
                audit = audit_gurobi_solution(model, {v["name"]: v["value"] for v in payload["variables"]}, payload["solution_objective"])
                if not audit["valid"] or not eligible_gap(payload["mip_gap_relative"]):
                    raise ValueError("completed label failed mathematical revalidation")
                return previous
            for source in task["existing_parent_reports"]:
                try:
                    sources.append(named_candidate(model, data, task, source))
                except (ValueError, OSError, KeyError, TypeError) as error:
                    errors.append({"kind": "existing_parent_report", "sha256": source["sha256"], "error_type": type(error).__name__, "reason": error_reason(error)})
            try:
                sources.append(legacy_candidate(model, data, task))
            except (ValueError, OSError, KeyError, TypeError, IndexError, pickle.UnpicklingError) as error:
                errors.append({"kind": "legacy_record", "error_type": type(error).__name__, "reason": error_reason(error)})
            selected = choose(sources)
            if selected is None and repair:
                from cfl_gnn.pipelines.parent_collection_task import execute_parent_collection_task
                from cfl_gnn.pipelines.parent_solutions import report_name
                run_root = campaign / "repair_runs"
                for budget in plan["repair_budgets_seconds"]:
                    plan_dir = campaign / f"repair_{budget}s"
                    repair_plan = read_json(checked(campaign, plan["repair_plans"][str(budget)]))
                    tasks = [t for t in repair_plan["tasks"] if t["solver"] == "gurobi"]
                    match = next(t for t in tasks if t["source_instance_id"] == task["source_instance_id"])
                    execute_parent_collection_task(plan_dir=plan_dir, solver="gurobi", task_index=match["solver_task_index"],
                        base_source_dir=data / "raw/MILPBench/CFL", run_root=run_root, resume=True, overwrite=False)
                    path = safe_path(run_root, match["run_dir_relative_path"]) / report_name("gurobi")
                    # Repair roots may be outside DATA_ROOT. Rebase this task's
                    # source descriptor without introducing absolute publication paths.
                    try:
                        candidate = named_candidate(model, campaign, task, descriptor(campaign, path))
                    except (ValueError, OSError, KeyError, TypeError) as error:
                        errors.append({"kind": "repair_report", "budget_seconds": budget, "error_type": type(error).__name__, "reason": error_reason(error)})
                        candidate = None
                    repair_outcomes.append({"budget_seconds": budget, "report_sha256": sha256_file(path),
                                            "label_eligible": candidate is not None})
                    if candidate is not None:
                        candidate["source_root_alias"] = "campaign"
                        selected = candidate
                        break
    result = {"schema_version": 1, "campaign_contract_sha256": plan["contract_sha256"],
              "source_instance_id": task["source_instance_id"], "fold": task["fold"], "role": task["role"],
              "mip_sha256": task["mip"]["sha256"], "source_errors": errors, "repair_outcomes": repair_outcomes,
              "gate_status": "passed" if selected else "inconclusive", "label_eligible": selected is not None,
              "training_ready": False, "development_only": True, "scientific_reporting_eligible": False}
    if selected:
        named = selected.pop("named")
        result["selected"] = selected
        payload = {"source_instance_id": task["source_instance_id"], "source_mip_sha256": task["mip"]["sha256"],
                   "solution_source": "independently_audited_gurobi_confirmation_label",
                   "effective_objective_sense": "MINIMIZE", "solution_objective": selected["audit"]["recomputed_objective"],
                   "mip_gap_relative": selected["mip_gap_relative"], "execution_time_seconds": selected["execution_time_seconds"],
                   "mathematical_audit": selected["audit"], "variables": [{"name": n, "value": v} for n, v in sorted(named.items())]}
        output.mkdir(parents=True, exist_ok=True)
        path = output / "confirmation_solution.json.gz"
        with gzip.open(path.with_suffix(".tmp"), "wt", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, allow_nan=False)
        path.with_suffix(".tmp").replace(path)
        result["solution"] = descriptor(output, path)
    if (output / REPORT).is_file():
        old = output / REPORT
        archive = output / f"previous_{sha256_file(old)}.json"
        if not archive.exists():
            archive.write_bytes(old.read_bytes())
    write_json(output / REPORT, result)
    return result


def aggregate(campaign_dir):
    campaign = Path(campaign_dir).resolve()
    plan = read_json(campaign / PLAN)
    validate_plan(plan)
    rows, index = [], []
    for task in plan["tasks"]:
        root = campaign / "labels" / task["source_instance_id"]
        status = {"source_instance_id": task["source_instance_id"], "role": task["role"], "label_eligible": False}
        try:
            report = read_json(root / REPORT)
            if (report["campaign_contract_sha256"] != plan["contract_sha256"] or report["source_instance_id"] != task["source_instance_id"]
                    or report["mip_sha256"] != task["mip"]["sha256"] or report["role"] != task["role"] or report["fold"] != task["fold"]):
                raise ValueError("task identity mismatch")
            if report["label_eligible"]:
                path = checked(root, report["solution"])
                with gzip.open(path, "rt", encoding="utf-8") as stream:
                    payload = json.load(stream)
                if (not eligible_gap(payload["mip_gap_relative"]) or payload["mathematical_audit"]["valid"] is not True
                        or payload["source_mip_sha256"] != task["mip"]["sha256"]):
                    raise ValueError("solution admission invalid")
                status.update(label_eligible=True, mip_gap_relative=payload["mip_gap_relative"],
                              execution_time_seconds=payload["execution_time_seconds"])
                index.append({**status, "fold": task["fold"], "solution": descriptor(campaign, path),
                              "mip": task["mip"], "report": descriptor(campaign, root / REPORT)})
        except (OSError, ValueError, KeyError, TypeError) as error:
            status["error_type"] = type(error).__name__
            status["reason"] = error_reason(error)
        rows.append(status)
    ready = len(index) == 42
    result = {"schema_version": 1, "campaign_contract_sha256": plan["contract_sha256"],
              "gate_status": "passed" if ready else "incomplete", "planned_parents": 42,
              "independently_admissible_parents": len(index), "records": rows,
              "label_inventory_ready": ready, "training_ready": False,
              "next_gate": "strict_gurobi_graph_consolidation" if ready else "review_unadmitted_parent_sources",
              "development_only": True, "scientific_reporting_eligible": False}
    path = campaign / "confirmation_label_index.jsonl"
    path.write_text("".join(json.dumps(row, sort_keys=True, allow_nan=False)+"\n" for row in index), encoding="utf-8")
    result["label_index"] = descriptor(campaign, path)
    write_json(campaign / "confirmation_execution_report.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--inventory", type=Path, required=True)
    p.add_argument("--data_root", type=Path, required=True)
    p.add_argument("--campaign_dir", type=Path, required=True)
    p = commands.add_parser("task")
    p.add_argument("--campaign_dir", type=Path, required=True)
    p.add_argument("--data_root", type=Path, required=True)
    p.add_argument("--task_index", type=int, required=True)
    p.add_argument("--repair", action="store_true")
    p = commands.add_parser("aggregate")
    p.add_argument("--campaign_dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare(inventory_path=args.inventory, data_root=args.data_root, output_dir=args.campaign_dir)
            print(f"[INFO] contract={result['contract_sha256']} | tasks=42 | seed=42 | MINIMIZE")
        elif args.command == "task":
            result = execute(campaign_dir=args.campaign_dir, data_root=args.data_root, task_index=args.task_index, repair=args.repair)
            print(f"[INFO] parent={result['source_instance_id']} | gate={result['gate_status']} | training_ready=false")
        else:
            result = aggregate(args.campaign_dir)
            print(f"[INFO] admitted={result['independently_admissible_parents']}/42 | training_ready=false")
            return 0 if result["label_inventory_ready"] else 1
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"[ERROR] confirmation {args.command} failed: {type(error).__name__}: {error_reason(error)}")
        return 2
