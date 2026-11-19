"""Build 22 source/Start bindings from reviewed preparations; no scientific calls."""

import argparse
from pathlib import Path

import mvp2_concurrent_mip as campaign
import pr94_evaluation_workflow as old
import pr98_hard_inputs as inputs
import pr98_hard_preparation as hard

OLD = inputs.EVIDENCE / "pr94-evaluation-81c829b66f6d"
OLD_PLAN = "92ac169c5ccb69962628dc0b91aab6afff183538da87f14e3ebf080b8cfe53fb"


def assemble(stage, hard_stage, hard_sha):
    need = inputs.require
    need(inputs.digest(OLD / "plan.json") == OLD_PLAN, "PR94_plan")
    plan = inputs.read(OLD / "plan.json")
    private_path = OLD / "inputs.private.json"
    need(inputs.digest(private_path) == plan["private_inputs_sha256"], "PR94_private")
    public = plan["bindings"]
    private = inputs.read(private_path)
    old.verify_inputs(public, private)
    need(
        inputs.digest(hard_stage / "hard-preparation-return.json") == hard_sha,
        "hard_return_hash",
    )
    returned = inputs.read(hard_stage / "hard-preparation-return.json")
    need(returned["ready_for_review"] is True, "hard_return_not_qualified")
    hard_plan = inputs.read(hard_stage / "plan.json")
    need(
        returned["plan_sha256"] == inputs.digest(hard_stage / "plan.json")
        and hard_plan["budget"] == hard.BUDGET,
        "hard_plan",
    )
    need(
        inputs.digest(hard_stage / "inputs.private.json")
        == hard_plan["private_inputs_sha256"],
        "hard_private_inputs",
    )
    need(
        returned["source_commit"] == hard_plan["source_commit"]
        and set(returned["rows"]) == set(hard.ALL)
        and returned["root_intents"] == returned["forward_intents"] == 5,
        "hard_return_lineage",
    )
    models = inputs.read(hard_stage / "inputs.private.json")["models"]
    bindings = {}
    parents = {r["instance"]: r["parent"] for r in campaign.matrix()}
    for alias, parent in parents.items():
        if alias.startswith("H"):
            row = returned["rows"][alias]["receipt"]
            paths = {
                "model": models[alias]["model"],
                "root": str(
                    hard_stage / "run" / alias / "preparation/root.private.json.gz"
                ),
                "graph": str(
                    hard_stage / "run" / alias / "preparation/graph.private.pt"
                ),
                "predictions": str(
                    hard_stage / "run" / alias / "preparation/predictions.private.json"
                ),
                "starts": str(
                    hard_stage / "run" / alias / "preparation/starts.private.json"
                ),
            }
        else:
            row = public[parent]
            paths = private["parents"][parent]
        need(
            row["parent"] == parent and row["checkpoint_sha256"] == inputs.CHECKPOINT,
            "parent",
        )
        for name, key in (
            ("model", "model_sha256"),
            ("root", "root_sha256"),
            ("graph", "graph_sha256"),
            ("predictions", "prediction_sha256"),
            ("starts", "private_starts_sha256"),
        ):
            path = inputs.data_file(Path(paths[name]), inputs.DATA)
            need(inputs.digest(path) == row[key], "artifact_" + name)
        review_path = stage / "binding-receipts" / (alias + ".json")
        review_path.parent.mkdir(exist_ok=True)
        inputs.write_once(review_path, row)
        item = {
            **row,
            **paths,
            "reviewed_preparation": str(review_path),
            "reviewed_preparation_sha256": inputs.digest(review_path),
        }
        campaign.inspect_input(item, parent)
        bindings[alias] = item
    checkpoint = inputs.data_file(Path(private["checkpoint_path"]), inputs.DATA)
    need(inputs.digest(checkpoint) == inputs.CHECKPOINT, "checkpoint")
    path = stage / "input-bindings.private.json"
    inputs.write_once(path, bindings)
    inputs.write_once(
        stage / "preparation-review.json",
        {
            "hard_return_sha256": hard_sha,
            "hard_plan_sha256": returned["plan_sha256"],
            "PR94_plan_sha256": OLD_PLAN,
            "inputs_sha256": inputs.digest(path),
            "interpretation": "artifact_byte_and_lineage_checks_not_scientific_result_promotion",
        },
    )
    return bindings


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage", type=Path)
    p.add_argument("hard_stage", type=Path)
    p.add_argument("accepted_hard_return_sha256")
    a = p.parse_args()
    stage = campaign.site_stage(a.stage)
    need = inputs.require
    hard_stage = a.hard_stage.resolve(strict=True)
    need(
        hard_stage.parent == inputs.EVIDENCE.resolve()
        and hard_stage.name.startswith("pr98-hard.")
        and not a.hard_stage.is_symlink(),
        "hard_stage",
    )
    value = assemble(stage, hard_stage, a.accepted_hard_return_sha256)
    campaign.freeze(stage, value)
    print("PR98_INSTANCES_BOUND=" + str(len(value)))


if __name__ == "__main__":
    main()
