"""Record existing runtime; no version gate, installation or synthetic job."""

import importlib.metadata
import platform
import re
from pathlib import Path

PACKAGES = (
    "torch",
    "torchvision",
    "torchaudio",
    "torch-geometric",
    "numpy",
    "scipy",
    "gurobipy",
    "packaging",
    "torch-scatter",
    "torch-sparse",
    "torch-cluster",
    "pyg-lib",
)


def versions():
    result = {}
    for name in PACKAGES:
        try:
            value = importlib.metadata.version(name)
            result[name] = (
                value
                if re.fullmatch(r"[A-Za-z0-9.+_-]{1,100}", value)
                else "redacted_nonstandard_version"
            )
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


def observe():
    driver = None
    try:
        text = Path("/proc/driver/nvidia/version").read_text()
        match = re.search(r"Kernel Module\s+(\d+\.\d+(?:\.\d+)?)", text)
        driver = match.group(1) if match else None
    except OSError:
        pass
    return {
        "python": platform.python_version(),
        "packages": versions(),
        "machine": platform.machine(),
        "libc": list(platform.libc_ver()),
        "nvidia_driver_procfs": driver,
        "packages_modified": False,
        "minimum_torch_version_gate": False,
    }
