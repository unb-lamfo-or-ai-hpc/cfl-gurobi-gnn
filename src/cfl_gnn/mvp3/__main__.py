"""Read-only bundle/evidence validation, or exclusive deterministic bundle export."""

import argparse
import hashlib
import json
from pathlib import Path

from . import CONTRACT_VERSION
from .contract import (
    approved_contract,
    build_primary_plan,
    freeze_parents,
    load_bundle,
    load_json,
    summary,
    validate_catalogue,
)
from .records import validate_records
from .schema import evidence_schema


def export_bundle(catalogue, output):
    """Create a new directory; never overwrite a frozen artifact or input file."""
    validate_catalogue(catalogue)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    contract = approved_contract()
    parents = freeze_parents(catalogue)
    files = {
        "contract.json": contract,
        "input-catalogue.json": catalogue,
        "parent-manifest.json": parents,
        "primary-plan.json": build_primary_plan(parents, contract),
        "evidence.schema.json": evidence_schema(),
    }
    seal = {"schema_version": CONTRACT_VERSION, "files": {}}
    for name, value in files.items():
        raw = (
            json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        ).encode("utf-8")
        with (output / name).open("xb") as stream:
            stream.write(raw)
        seal["files"][name] = {
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    with (output / "bundle-manifest.json").open(
        "x", encoding="utf-8", newline="\n"
    ) as stream:
        json.dump(seal, stream, indent=2)
        stream.write("\n")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle", type=Path, required=True, help="Versioned contract directory"
    )
    parser.add_argument(
        "--records", type=Path, help="JSON array of observations, not planning slots"
    )
    parser.add_argument(
        "--export", type=Path, help="New directory for a byte-identical contract export"
    )
    args = parser.parse_args()
    bundle = load_bundle(args.bundle)
    result = summary(bundle)
    if args.records:
        records = load_json(args.records)
        if not isinstance(records, list):
            parser.error("--records must contain a JSON array")
        result["evidence"] = validate_records(records, bundle)
    if args.export:
        export_bundle(bundle["catalogue"], args.export)
        result["exported"] = str(args.export)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
