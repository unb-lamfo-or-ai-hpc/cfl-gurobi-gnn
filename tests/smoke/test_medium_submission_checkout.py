"""Exercise the actual Bash checkout gate without a scheduler or solver."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.fixture
def checkout(tmp_path):
    bash = os.environ.get("CFL_TEST_BASH") or shutil.which("bash")
    git = shutil.which("git")
    if not bash or not git:
        pytest.skip("Bash and Git required for launcher integration")
    repo = tmp_path / "repo"
    (repo / "manuscript").mkdir(parents=True)
    (repo / "manuscript/.gitignore").write_text("*.aux\n")
    (repo / "source.py").write_text("original = True\n")
    def command(*args):
        return subprocess.check_output([git, "-C", str(repo), *args], text=True).strip()
    command("init", "-q")
    command("-c", "core.autocrlf=false", "add", ".")
    command("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-qm", "fixture")
    head = command("rev-parse", "HEAD")
    script = Path(__file__).parents[2] / "scripts/slurm/dasci/submit_reviewed_medium_continuation.sh"
    env = {**os.environ, "EXEC_DIR": repo.as_posix(), "DATA_ROOT": tmp_path.as_posix(),
           "CAMPAIGN_PLAN_DIR": tmp_path.as_posix(), "CAMPAIGN_RUN_ROOT": tmp_path.as_posix(),
           "RECONCILIATION_DIR": tmp_path.as_posix(), "PR57_EXPECTED_COMMIT": head}
    def run():
        # Stop at the lock after checkout validation. Never invoke a real sbatch.
        wrapper = '''
flock() { echo MOCK_LOCK_REACHED; return 17; }
sbatch() { echo UNEXPECTED_SCHEDULER_CALL; return 99; }
squeue() { return 99; }
jq() { return 99; }
conda() { return 99; }
export -f flock sbatch squeue jq conda
bash "$1"
'''
        return subprocess.run([bash, "-c", wrapper, "test", script.as_posix()], env=env,
                              capture_output=True, text=True, timeout=30)
    return repo, env, run


def test_clean_checkout_reaches_lock_without_scheduler(checkout):
    _, _, run = checkout
    result = run()
    assert result.returncode == 2
    assert "PR57_CHECKOUT_OK" in result.stdout and "MOCK_LOCK_REACHED" in result.stdout
    assert "SUBMISSION_LOCK_UNAVAILABLE" in result.stderr
    assert "UNEXPECTED_SCHEDULER_CALL" not in result.stdout


def test_manuscript_ignore_change_is_preserved(checkout):
    repo, _, run = checkout
    edited = "*.aux\noperator-local-rule\n"
    (repo / "manuscript/.gitignore").write_text(edited)
    result = run()
    assert "preserved unrelated manuscript/.gitignore" in result.stdout
    assert "MOCK_LOCK_REACHED" in result.stdout
    assert (repo / "manuscript/.gitignore").read_text() == edited


@pytest.mark.parametrize("staged", [False, True])
def test_source_edits_still_block_before_lock(checkout, staged):
    repo, _, run = checkout
    (repo / "source.py").write_text("changed = True\n")
    if staged:
        subprocess.run(["git", "-C", str(repo), "add", "source.py"], check=True)
    result = run()
    assert result.returncode == 2 and "DIRTY_TRACKED_FILES" in result.stderr
    assert "source.py" in result.stderr and "MOCK_LOCK_REACHED" not in result.stdout
    assert (repo / "source.py").read_text() == "changed = True\n"


def test_wrong_commit_is_explicit(checkout):
    _, env, run = checkout
    env["PR57_EXPECTED_COMMIT"] = "0" * 40
    result = run()
    assert result.returncode == 2 and "SOURCE_COMMIT_MISMATCH" in result.stderr
    assert "MOCK_LOCK_REACHED" not in result.stdout
