"""Author-operated stages. Preparation never implicitly executes another stage."""

import argparse
import json
import os
from pathlib import Path

from ..contract import require
from .collection import collect
from .inventory import discover
from .planning import load_plan, make_plan
from .release import prepare, verify_bundle
from .worker import probe, worker


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle")
    parser.add_argument("--manifest-sha256")
    sub = parser.add_subparsers(dest="mode", required=True)
    build = sub.add_parser(
        "prepare",
        help="Windows/local offline source packaging; no native or HPC action",
    )
    for name in (
        "repository",
        "output",
        "source-commit",
        "ci-receipt",
        "local-license-file",
    ):
        build.add_argument(f"--{name}", required=True)
    scan = sub.add_parser(
        "discover",
        help="Author Linux read-only inventory; no Env/start/optimize/sbatch",
    )
    for name in ("output", "license-file", "installed-repo", "data-root"):
        scan.add_argument(f"--{name}", required=True)
    plan_parser = sub.add_parser("plan", help="Render proposals only, never submit")
    for name in (
        "discovery",
        "output",
        "partition",
        "account",
        "qos",
        "intel-256",
        "intel-512",
        "python",
        "license-file",
        "approval-reference",
    ):
        plan_parser.add_argument(f"--{name}", required=True)
    for name in ("worker", "probe", "collect"):
        command = sub.add_parser(
            name,
            help="Separate concrete author release required"
            if name != "collect"
            else "Read-only closed-job reconciliation",
        )
        command.add_argument("--plan", required=True)
        command.add_argument("--plan-sha256", required=True)
        if name == "collect":
            command.add_argument("--output", required=True)
        else:
            command.add_argument(
                "--profile", required=True, choices=("intel-256", "intel-512")
            )
    args = parser.parse_args(argv)
    try:
        if os.name == "posix":
            os.umask(0o077)
        if args.mode == "prepare":
            result = prepare(
                args.repository,
                args.output,
                args.source_commit,
                args.ci_receipt,
                args.local_license_file,
            )
        else:
            require(
                args.bundle and args.manifest_sha256,
                "Pinned portable source bundle required",
            )
            manifest = verify_bundle(args.bundle, args.manifest_sha256)
            if args.mode == "discover":
                result = discover(
                    args.output,
                    manifest["source_commit"],
                    license_file=args.license_file,
                    installed_repo=args.installed_repo,
                    data_root=args.data_root,
                    catalogue_path=Path(args.bundle)
                    / "configs/mvp3/v1/input-catalogue.json",
                )
            elif args.mode == "plan":
                result = make_plan(
                    args.bundle,
                    args.manifest_sha256,
                    args.discovery,
                    args.output,
                    partition=args.partition,
                    account=args.account,
                    qos=args.qos,
                    nodes={"intel-256": args.intel_256, "intel-512": args.intel_512},
                    python=args.python,
                    license_file=args.license_file,
                    approval_reference=args.approval_reference,
                )
            elif args.mode == "worker":
                result = worker(
                    args.bundle,
                    manifest,
                    args.manifest_sha256,
                    args.plan,
                    args.plan_sha256,
                    args.profile,
                )
            else:
                plan = load_plan(
                    args.plan,
                    args.plan_sha256,
                    manifest,
                    bundle=args.bundle,
                    manifest_sha256=args.manifest_sha256,
                )
                result = (
                    probe(plan, args.profile, manifest["source_commit"])
                    if args.mode == "probe"
                    else collect(plan, args.output)
                )
        print(
            json.dumps(
                {
                    "stage": args.mode,
                    "source_commit": result.get("source_commit"),
                    "stage_returned": True,
                    "scientific_release": False,
                }
            )
        )
        if args.mode == "discover":
            return 1 if result["commands_failed"] else 0
        if args.mode == "collect":
            return 0 if result["two_production_envelopes_technically_qualified"] else 1
        return 0
    except Exception as error:
        print(f"MVP3_PRODUCTION_STAGE_FAILED:{type(error).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
