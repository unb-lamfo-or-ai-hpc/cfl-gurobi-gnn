"""Check both real Bash gates and reproduce the historical EOL worktree fault."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).parents[2]


@pytest.fixture(params=["queue_remaining_medium_batches.sh", "submit_remaining_medium_task.sbs"])
def checkout(tmp_path, request):
    bash = os.environ.get("CFL_TEST_BASH") or shutil.which("bash")
    git = shutil.which("git")
    if not bash or not git:
        pytest.skip("Bash and Git required")
    repo = tmp_path / "repo"
    (repo / "manuscript").mkdir(parents=True)
    (repo / ".gitattributes").write_text("manuscript/** text eol=lf\n")
    (repo / "manuscript/.gitignore").write_bytes((ROOT / "manuscript/.gitignore").read_bytes())
    (repo / "source.py").write_text("original = True\n")

    def gitcmd(*args, input=None):
        return subprocess.check_output([git, "-C", str(repo), *args], input=input).decode().strip()

    gitcmd("init", "-q")
    gitcmd("config", "core.autocrlf", "false")
    gitcmd("config", "core.safecrlf", "false")
    gitcmd("add", ".")

    def commit():
        gitcmd("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
               "-c", "commit.gpgsign=false", "commit", "-qm", "fixture")
        return gitcmd("rev-parse", "HEAD")

    head = commit()
    license_path = tmp_path / "fixture.lic"
    license_path.write_text("fixture only; never used by a solver")
    env = {**os.environ, "EXEC_DIR": repo.as_posix(), "PR57_QUEUE_COMMIT": head,
           "GRB_LICENSE_FILE": license_path.as_posix(), "PREDECESSOR_AUDIT_JOB": "3369"}
    for name in ("DATA_ROOT", "CAMPAIGN_PLAN_DIR", "CAMPAIGN_RUN_ROOT", "REVIEWED_PREFLIGHT",
                 "PREDECESSOR_AUDIT_DIR", "MEDIUM_QUEUE_DIR"):
        env[name] = tmp_path.as_posix()
    script = ROOT / "scripts/slurm/dasci" / request.param

    def run():
        # Abort at the first post-checkout boundary. No real scheduler or solver.
        wrapper = '''
flock() { echo MOCK_BOUNDARY_REACHED; return 17; }
sbatch() { echo UNEXPECTED_EXECUTION; return 99; }
srun() { echo UNEXPECTED_EXECUTION; return 99; }
python3() { echo UNEXPECTED_EXECUTION; return 99; }
scontrol() { return 0; }
jq() { return 99; }
conda() { echo MOCK_BOUNDARY_REACHED >&2; return 17; }
export -f flock sbatch srun python3 scontrol jq conda
bash "$1"
'''
        return subprocess.run([bash, "-c", wrapper, "test", script.as_posix()],
                              env=env, capture_output=True, text=True, timeout=30)
    return repo, tmp_path, env, gitcmd, commit, run


def test_clean_checkout_reaches_boundary(checkout):
    result = checkout[-1]()
    assert "PR57_QUEUE_CHECKOUT_OK" in result.stdout
    assert "MOCK_BOUNDARY_REACHED" in result.stdout + result.stderr
    assert "UNEXPECTED_EXECUTION" not in result.stdout + result.stderr


@pytest.mark.parametrize("staged", [False, True])
def test_real_source_changes_remain_blocking(checkout, staged):
    repo, _, _, gitcmd, _, run = checkout
    edited = "original = False\n"
    (repo / "source.py").write_text(edited)
    if staged:
        gitcmd("add", "source.py")
    result = run()
    assert result.returncode == 2
    assert "DIRTY_TRACKED_FILES" in result.stderr and "source.py" in result.stderr
    assert "MOCK_BOUNDARY_REACHED" not in result.stdout + result.stderr
    assert (repo / "source.py").read_text() == edited


def test_manuscript_edits_are_not_silently_discarded_or_exempted(checkout):
    repo, _, _, _, _, run = checkout
    edited = "operator-specific-rule\n"
    (repo / "manuscript/.gitignore").write_text(edited)
    result = run()
    assert result.returncode == 2 and "manuscript/.gitignore" in result.stderr
    assert (repo / "manuscript/.gitignore").read_text() == edited


def test_wrong_sha_has_actionable_diagnostic(checkout):
    checkout[2]["PR57_QUEUE_COMMIT"] = "0" * 40
    result = checkout[-1]()
    assert result.returncode == 2 and "SOURCE_COMMIT_MISMATCH" in result.stderr
    assert "MOCK_BOUNDARY_REACHED" not in result.stdout + result.stderr


def test_mixed_blob_reproduces_dirty_fresh_worktree_and_lf_fixes_it(checkout):
    repo, temp, env, gitcmd, commit, run = checkout
    payload = (ROOT / "manuscript/.gitignore").read_bytes()
    assert b"\r" not in payload
    # Bypass clean filters to reproduce the historical mixed-EOL GitHub blob.
    mixed = payload.replace(b"\n", b"\r\n", 12)
    blob = gitcmd("hash-object", "-w", "--stdin", input=mixed)
    gitcmd("update-index", "--cacheinfo", "100644," + blob + ",manuscript/.gitignore")
    bad = commit()
    bad_tree = temp / "mixed-worktree"
    gitcmd("worktree", "add", "--detach", str(bad_tree), bad)
    env.update(EXEC_DIR=bad_tree.as_posix(), PR57_QUEUE_COMMIT=bad)
    result = run()
    assert result.returncode == 2 and "manuscript/.gitignore" in result.stderr
    clean_blob = gitcmd("hash-object", "-w", "--stdin", input=payload)
    gitcmd("update-index", "--cacheinfo", "100644," + clean_blob + ",manuscript/.gitignore")
    good = commit()
    good_tree = temp / "lf-worktree"
    gitcmd("worktree", "add", "--detach", str(good_tree), good)
    env.update(EXEC_DIR=good_tree.as_posix(), PR57_QUEUE_COMMIT=good)
    result = run()
    assert "PR57_QUEUE_CHECKOUT_OK" in result.stdout
    assert "MOCK_BOUNDARY_REACHED" in result.stdout + result.stderr
    assert "UNEXPECTED_EXECUTION" not in result.stdout + result.stderr
