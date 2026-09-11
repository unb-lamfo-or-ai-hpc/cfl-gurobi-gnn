"""Run one targeted Gurobi label repair; never submit the deferred 90-parent campaign."""
import argparse
from pathlib import Path
from cfl_gnn.pipelines.confirmation_campaign import execute_repair_task

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign_dir", type=Path, required=True)
    parser.add_argument("--source_dir", type=Path, required=True)
    parser.add_argument("--run_root", type=Path, required=True)
    parser.add_argument("--task_index", type=int, required=True)
    args = parser.parse_args()
    result = execute_repair_task(**vars(args))
    print(f"[INFO] parent={result['source_instance_id']} | eligible={result['label_eligible']}")
    return 0 if result["label_eligible"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
