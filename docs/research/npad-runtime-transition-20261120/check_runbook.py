"""Synthetic runbook checks; never execute the shell or contact either HPC."""

import sys
from pathlib import Path
from unittest.mock import patch


def template_text():
    return (
        Path(__file__)
        .with_name("reconcile-npad.template.sh")
        .read_text(encoding="utf-8")
        .replace("__AGRO_BACKUP_BASENAME__", "pyproject.toml.before-g14-fixture")
    )


def check_plan():
    import ast
    import contextlib
    import io
    import json
    import re
    import sys
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    root = Path(__file__).resolve().parent
    s = template_text()

    def block(tag):
        return re.search(r"<<'" + tag + r"'\n([\s\S]*?)\n" + tag + r"\n", s)[1] + "\n"

    for tag in ("FREEZE", "META", "PLAN", "RECEIPT"):
        ast.parse(block(tag))
    inventory = re.search(r"-c '([^']+)'", s)[1]
    ast.parse(inventory)
    assert (
        "--require-hashes --no-deps" in s
        and '--constraint "$S/existing.constraints.txt"' in s
    )
    assert "pip sync" not in s and "--upgrade" not in s and "sbatch" not in s
    assert s.count(" pip install ") == 2
    for tag in ("FREEZE", "META", "PLAN", "RECEIPT"):
        tree = ast.parse(block(tag))
        imports = [
            n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
        ]
        for n in imports:
            names = (
                [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module]
            )
            assert not any(x in ("torch", "gurobipy", "torch_geometric") for x in names)
    code = compile(block("PLAN"), "plan", "exec")
    url = "https://download-r2.pytorch.org/whl/cu118/torch-2.7.1%2Bcu118-cp313-cp313-manylinux_2_28_x86_64.whl"
    digest = "a3f02b2795165eaf6dfe18c963519049a45a9c588488795cebc5015dac77ab46"
    for case in (
        "valid",
        "downgrade_numpy",
        "upgrade_scipy",
        "wrong_url",
        "conditional",
        "unversioned",
        "missing_direct",
        "duplicate",
        "unhashed_torch",
    ):
        with tempfile.TemporaryDirectory(prefix="add-only-check-", dir=root) as tmp:
            r = Path(tmp)
            before = [["numpy", "2.5.2"], ["scipy", "1.18.1"], ["gurobipy", "14.0.0"]]
            (r / "target-before.json").write_text(json.dumps(before))
            (r / "agro-metadata-after.json").write_text(
                json.dumps({"pydantic_version_for_plan": "2.13.4"})
            )
            lines = [
                "torch @ " + url + " \\",
                "    --hash=sha256:" + digest,
                "torch-geometric==2.7.0",
                "pyarrow==24.0.0",
                "scikit-learn==1.7.2",
                "tqdm==4.67.3",
                "numpy==2.5.2",
                "scipy==1.18.1",
            ]
            lines.insert(6, "pydantic==2.13.4")
            if case == "downgrade_numpy":
                lines[-2] = "numpy==2.1.3"
            if case == "upgrade_scipy":
                lines[-1] = "scipy==1.19.0"
            if case == "wrong_url":
                lines[0] = "torch @ https://example.invalid/torch.whl"
            if case == "conditional":
                lines[-1] = 'scipy==1.18.1; python_version>="3.0"'
            if case == "unversioned":
                lines[-1] = "scipy>=1.0"
            if case == "missing_direct":
                lines.remove("pyarrow==24.0.0")
            if case == "duplicate":
                lines.append("numpy==2.5.2")
            if case == "unhashed_torch":
                lines[1] = "    --hash=sha256:" + "0" * 64
            (r / "complete-additions.lock.txt").write_text("\n".join(lines) + "\n")
            passed = False
            with (
                patch.object(sys, "argv", ["plan", str(r)]),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                try:
                    exec(code, {"__name__": "__main__"})
                    passed = True
                except AssertionError:
                    pass
            assert passed == (case == "valid"), (case, passed)
            if passed:
                plan = json.loads((r / "add-only-plan.json").read_text())
                assert plan["expected_versions"]["numpy"] == "2.5.2"
                assert len(plan["additions"]) == 6
    print(
        json.dumps(
            {
                "add_only_plan_scenarios": 9,
                "passed": 9,
                "python_blocks_parsed": 4,
                "no_scientific_imports": True,
                "no_install_executed_in_verification": True,
            }
        )
    )


def check_metadata():
    import contextlib
    import io
    import json
    import re
    import tempfile
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import patch
    from urllib.parse import unquote as decode_uri

    root = Path(__file__).resolve().parent
    source = template_text()
    helper = re.search(r"<<'META'\n([\s\S]*?)\nMETA\n", source)[1]
    g = {"__name__": "unit"}
    exec(compile(helper, "helper", "exec"), g)
    g["unquote"] = lambda s: (
        decode_uri(s)[1:] if re.match(r"^/[A-Za-z]:/", decode_uri(s)) else decode_uri(s)
    )
    base = '[build-system]\nrequires=["setuptools>=77","wheel>=0.45"]\nbuild-backend="setuptools.build_meta"\n[project]\nname="model-agrologistic"\nversion="1.0"\nrequires-python=">=3.13,<3.14"\ndependencies=["gurobipy>=13.0.2,<14"]\n'

    def fixture(p, text=base):
        (p / "pyproject.toml.before-g14-fixture").write_text(text)
        (p / "pyproject.toml").write_text(
            "".join(
                re.sub(r"<\s*14(?![\d.])", "<15", line)
                if "gurobipy" in line.lower()
                else line
                for line in text.splitlines(keepends=True)
            )
        )

    def ver(n):
        return {"setuptools": "84.0.0", "wheel": "0.48.0"}[n]

    count = 0
    for case in (
        "valid",
        "source_delta",
        "backend",
        "wrong_name",
        "setup",
        "gurobi",
        "build_tool",
    ):
        with tempfile.TemporaryDirectory(prefix="source-policy-", dir=root) as tmp:
            p = Path(tmp)
            text = base
            if case == "backend":
                text = text.replace("setuptools.build_meta", "custom.backend")
            if case == "wrong_name":
                text = text.replace("model-agrologistic", "another-project")
            if case == "gurobi":
                text = text.replace("<14", "<13")
            fixture(p, text)
            if case == "source_delta":
                (p / "pyproject.toml").write_text(
                    (p / "pyproject.toml")
                    .read_text()
                    .replace('version="1.0"', 'version="9.0"')
                )
            if case == "setup":
                (p / "setup.py").write_text("import gurobipy\n")
            passed = False
            with patch(
                "importlib.metadata.version",
                side_effect=(lambda n: "1.0" if n == "setuptools" else ver(n))
                if case == "build_tool"
                else ver,
            ):
                try:
                    g["source_info"](p)
                    passed = True
                except AssertionError:
                    pass
            assert passed == (case == "valid"), (case, passed)
            count += 1
    for case in ("old_metadata", "already_current", "verify", "other_version_changed"):
        with tempfile.TemporaryDirectory(prefix="metadata-policy-", dir=root) as tmp:
            p = Path(tmp)
            fixture(p)
            g["PROJECT"] = p
            state = {
                "version": "1.0" if case == "already_current" else "0.9",
                "req": "gurobipy>=13.0.2,<15"
                if case == "already_current"
                else "gurobipy>=13.0.2,<14",
            }

            def dist(n):
                return SimpleNamespace(
                    version=state["version"],
                    requires=[state["req"]],
                    read_text=lambda name: json.dumps(
                        {"url": p.as_uri(), "dir_info": {"editable": True}}
                    ),
                )

            with (
                patch("importlib.metadata.version", side_effect=ver),
                patch("importlib.metadata.distribution", side_effect=dist),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                g["inspect"](p)
            assert json.loads((p / "agro-metadata-before.json").read_text())[
                "metadata_refresh_needed"
            ] == (case != "already_current")
            if case in ("verify", "other_version_changed"):
                values = [
                    ["model-agrologistic", "0.9"],
                    ["gurobipy", "14.0.0"],
                    ["numpy", "2.5.2"],
                    ["scipy", "1.18.1"],
                ]
                (p / "target-before-reconcile.json").write_text(json.dumps(values))
                state.update(version="1.0", req="gurobipy>=13.0.2,<15")
                actual = [
                    SimpleNamespace(
                        metadata={"Name": n},
                        version=(
                            "1.0"
                            if n == "model-agrologistic"
                            else "2.1.3"
                            if case == "other_version_changed" and n == "numpy"
                            else v
                        ),
                    )
                    for n, v in values
                ]
                passed = False
                with (
                    patch("importlib.metadata.version", side_effect=ver),
                    patch("importlib.metadata.distribution", side_effect=dist),
                    patch("importlib.metadata.distributions", return_value=actual),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    try:
                        g["verify"](p)
                        passed = True
                    except AssertionError:
                        pass
                assert passed == (case == "verify"), (case, passed)
            count += 1
    for case in (
        "healthy",
        "pydantic_missing",
        "unknown_dependency",
        "remaining_gurobi",
        "bad_exit",
    ):
        with tempfile.TemporaryDirectory(prefix="dependency-policy-", dir=root) as tmp:
            p = Path(tmp)
            (p / "agro-metadata-after.json").write_text(
                json.dumps({"pydantic_version_for_plan": "2.13.4"})
            )
            (p / "additions.in").write_text("")
            t = chr(96)
            text = (
                "The package "
                + t
                + "dash"
                + t
                + " requires "
                + t
                + "pydantic>=2.10"
                + t
                + ", but it's not installed\n"
            )
            if case == "unknown_dependency":
                text = "The package " + t + "other" + t + " requires missinglib\n"
            if case == "remaining_gurobi":
                text += (
                    "The package "
                    + t
                    + "model-agrologistic"
                    + t
                    + " requires an incompatible Gurobi\n"
                )
            (p / "dependency-check-before.txt").write_text(text)
            rc = 0 if case == "healthy" else 2 if case == "bad_exit" else 1
            passed = False
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    g["check_dependencies"](p, rc)
                    passed = True
                except AssertionError:
                    pass
            assert passed == (case in ("healthy", "pydantic_missing")), (case, passed)
            count += 1
    print(
        json.dumps(
            {
                "metadata_scenarios_passed": count,
                "source_pyproject_unmodified_by_helper": True,
                "actual_package_changes": 0,
                "actual_HPC_calls": 0,
            }
        )
    )


def check_gpu_templates():
    import ast
    import re

    directory = Path(__file__).resolve().parent
    submit = (directory / "gpu-runtime-submit.template.sh").read_text(encoding="utf-8")
    collect = (directory / "gpu-runtime-collect.template.sh").read_text(
        encoding="utf-8"
    )
    assert submit.count("sbatch --parsable") == 1
    assert (
        "--ntasks=1 --cpus-per-task=8 --mem=48G --gres=gpu:1 --time=00:15:00 --no-requeue"
        in submit
    )
    for text, tags in ((submit, ("ADMIT", "WORKER")), (collect, ("PY",))):
        for tag in tags:
            body = re.search(r"<<'" + tag + r"'\n([\s\S]*?)\n" + tag + r"\n", text)[1]
            ast.parse(body)
            if tag == "WORKER":
                calls = [
                    node
                    for node in ast.walk(ast.parse(body))
                    if isinstance(node, ast.Call)
                ]
                forbidden = {
                    "optimize",
                    "optimizeAsync",
                    "backward",
                    "step",
                    "fit",
                    "train",
                    "forward",
                }
                assert not any(
                    isinstance(node.func, ast.Attribute) and node.func.attr in forbidden
                    for node in calls
                )
                assert "weights_only=False" in body
                assert "ONE_ALLOCATED_CUDA_DEVICE_REQUIRED_NO_CPU_FALLBACK" in body
                assert "from_numpy" in body and ".numpy()" in body
                assert "import gurobipy" not in body
    assert "sbatch" not in collect and "scancel" not in collect
    print("NPAD_GPU_TEMPLATES_STATIC_CONTRACT=PASS_NO_EXECUTION")


if __name__ == "__main__":
    if sys.version_info < (3, 11):
        raise SystemExit("Synthetic metadata checks require tomllib: Python >=3.11")
    check_gpu_templates()
    check_plan()
    with patch.object(sys, "version_info", (3, 13, 15)):
        check_metadata()
    print("NPAD_RUNBOOK_SYNTHETIC_SCENARIOS=25")
