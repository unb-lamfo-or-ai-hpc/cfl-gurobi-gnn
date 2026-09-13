"""Regression checks for research documentation and preserved data links."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def test_mit_scope_preserves_external_rights():
    assert (ROOT / "LICENSE").read_text().startswith("MIT License")
    assert 'license = {file = "LICENSE"}' in (ROOT / "pyproject.toml").read_text()
    policy = (ROOT / "LICENSE_POLICY.md").read_text()
    assert "SPDX-License-Identifier: MIT" in policy
    assert "does not relicense MILPBench" in policy
    data = (ROOT / "data/LICENSE.md").read_text()
    assert "SPDX-License-Identifier: MIT" in data
    assert "not relicensed" in data

DATA_URLS = (
    "https://github.com/thuiar/MILPBench",
    "https://drive.google.com/file/d/1z6oNG1ja6CwlsRYViXIzBj0j8Ch6sxdt/view?usp=sharing",
    "https://drive.google.com/file/d/181Evo5Q6otZRq6EBeQXFcCYlC4kM8zaH/view?usp=sharing",
    "https://drive.google.com/file/d/13NS9YTTyNsiV6Dth3qsQ7lWWNQs4Pek0/view?usp=sharing",
)


def test_readme_preserves_milpbench_download_presentation():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    download = text.split("### Data Download", 1)[1]
    for url in DATA_URLS:
        assert url in download
    for label in ("CFL_easy", "CFL_medium", "CFL_hard"):
        assert f"* **{label}**:" in download


def test_readme_distinguishes_confirmation_from_historical_routes():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for required in (
        "42 original parents: 30 easy, 12 medium",
        "MINIMIZE",
        "zero-vector fallback",
        "100 epochs",
        "common eligible parent intersection",
        "not yet a complete runtime dependency specification",
    ):
        assert required in text
    legacy = (ROOT / "docs/pipeline.md").read_text(encoding="utf-8")
    assert "Historical scope" in legacy
    assert "All scripts are production-ready" not in legacy


def test_readme_and_current_guide_relative_links_resolve():
    # Do not traverse large generated datasets, model stores, or local environments.
    documents = [ROOT / "README.md", ROOT / "data/README.md"]
    for directory in ("configs", "docs", "notebooks", "sandbox", "scripts", "src", "tests", "tools"):
        documents.extend((ROOT / directory).rglob("README.md"))
    documents += [
        ROOT / "docs/architecture.md",
        ROOT / "docs/reproducibility.md",
        ROOT / "docs/documentation-review.md",
    ]
    checked = 0
    for path in documents:
        if any(part.startswith(".") for part in path.relative_to(ROOT).parts):
            continue
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)]+)\)", text):
            target = target.split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            assert (path.parent / target).resolve().exists(), (path, target)
            checked += 1
    assert checked >= 60


def test_translated_legacy_launchers_remain_lf_only():
    names = (
        "submit_step1_cfl_data_generator.sbs",
        "submit_step3_build_test_pyg.sbs",
        "submit_step4_stats_cluster_xray.sbs",
        "submit_step5_real_gnn_serial.sbs",
        "submit_step6_real_gnn_parallel.sbs",
        "submit_step7_miphints_generator.sbs",
        "submit_step8_gurobi_hpc.sbs",
        "submit_step9_evaluation.sbs",
        "submit_toy_gnn.sbs",
    )
    for name in names:
        payload = (ROOT / "scripts/slurm/dasci" / name).read_bytes()
        assert payload.startswith(b"#!/bin/bash\n")
        assert b"\r" not in payload
