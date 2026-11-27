"""Render author creation/transfer/discovery commands inside a dedicated project."""

import re
import shlex
from pathlib import PurePosixPath

from ..contract import require
from ..journal import durable_json, file_sha256
from .layout import DEFAULT_EXECUTION_ROOT, DIRECTORY_NAME


def write_handoff(output, prepared, *, root=DEFAULT_EXECUTION_ROOT):
    project = PurePosixPath(root)
    require(
        project.is_absolute()
        and project.name == DIRECTORY_NAME
        and ".." not in project.parts
        and re.fullmatch(r"/[A-Za-z0-9_./-]+", str(project)),
        "Dedicated ASCII Linux project root required",
    )
    short = prepared["source_commit"][:12]
    incoming = project / "incoming" / short
    run = project / "runs" / short
    archive = incoming / "s2-production-qualification.tar"
    name = f"run-s2-discovery-{short}.sh"
    create = "\n".join(
        [
            "umask 077",
            f"production_project={shlex.quote(str(project))}",
            'for production_directory in "$production_project" "$production_project/incoming" "$production_project/runs"; do',
            '  if [ -L "$production_directory" ]; then printf "%s\\n" "Preserve existing links; creation aborted." >&2; exit 1; fi',
            "done",
            'mkdir -p -- "$production_project/incoming" "$production_project/runs"',
            f'mkdir -m 700 -- "$production_project/incoming/{short}"',
        ]
    )
    lines = [
        "#!/bin/bash",
        "set -euo pipefail",
        "umask 077",
        f"production_project={shlex.quote(str(project))}",
        f"production_incoming={shlex.quote(str(incoming))}",
        f"production_run={shlex.quote(str(run))}",
        f"production_archive={shlex.quote(str(archive))}",
        'for production_directory in "$production_project" "$production_project/incoming" "$production_incoming" "$production_project/runs"; do',
        '  if [ -L "$production_directory" ] || [ ! -d "$production_directory" ]; then printf "%s\\n" "Dedicated project directories unavailable; preserve them." >&2; exit 1; fi',
        "done",
        'production_script_directory=$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)',
        'production_expected_directory=$(cd -P -- "$production_incoming" && pwd)',
        'if [ "$production_script_directory" != "$production_expected_directory" ]; then printf "%s\\n" "Run the transferred script from its dedicated incoming directory." >&2; exit 1; fi',
        'cd -- "$production_incoming"',
        f"printf '%s  %s\\n' '{prepared['archive_sha256']}' \"$production_archive\" | sha256sum --check --status",
        'mkdir -m 700 -- "$production_run"',
        'mkdir -m 700 -- "$production_run/bundle"',
        'cd -- "$production_run"',
        'tar --extract --file="$production_archive" --directory="$production_run/bundle" --no-same-owner --no-same-permissions',
        "GRB_LICENSE_FILE=/home/vrrcelestino/cfl-gurobi-gnn/secrets/gurobi.lic \\",
        "  /home/vrrcelestino/venv313_g14/bin/python -B \\",
        '  "$production_run/bundle/scripts/mvp3/qualify_production.py" \\',
        f'  --bundle "$production_run/bundle" --manifest-sha256 {prepared["manifest_sha256"]} \\',
        '  --execution-root "$production_project" \\',
        '  discover --output "$production_run/discovery" \\',
        "  --license-file /home/vrrcelestino/cfl-gurobi-gnn/secrets/gurobi.lic \\",
        "  --installed-repo /home/vrrcelestino/cfl-gurobi-gnn \\",
        "  --data-root /home/Projeto_LAMFO_LAPPS/data/CFL",
        "",
    ]
    script = output / name
    with script.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines))
    creation = output / "create-execution-directory.sh"
    with creation.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("#!/bin/bash\nset -euo pipefail\n" + create + "\n")
    receipt = {
        "execution_root": str(project),
        "incoming_directory": str(incoming),
        "run_directory": str(run),
        "remote_archive": str(archive),
        "remote_launcher": str(incoming / name),
        "create_directory_command": "bash <<'MVP3_CREATE_DIRECTORY'\nset -euo pipefail\n"
        + create
        + "\nMVP3_CREATE_DIRECTORY",
        "author_discovery_command": shlex.join(["bash", str(incoming / name)]),
        "return_file": str(run / "discovery/discovery.json"),
        "launcher_sha256": file_sha256(script),
        "creation_script_sha256": file_sha256(creation),
        "remote_directory_created_by_agent": False,
        "author_commands_executed": False,
        "native_calls": 0,
        "HPC_access": False,
    }
    durable_json(output / "handoff.json", receipt)
    return receipt
