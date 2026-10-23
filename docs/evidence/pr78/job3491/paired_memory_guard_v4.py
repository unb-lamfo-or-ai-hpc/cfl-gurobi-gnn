"""Qualification-only scoped-mount gate with sanitized failure diagnostics.

No executor integration, cgroup writes, retries or change to numerical limits.
"""
import errno
import re
from pathlib import PurePosixPath

import paired_memory_guard_v3 as prior

original = prior.original
POLICY = dict(prior.POLICY)
job_chain = prior.job_chain
require = prior.require


class MemoryObservationError(ValueError):
    def __init__(self, diagnostic):
        super().__init__('memory_observation_failed')
        self.diagnostic = diagnostic


def failure(stage, exc, depth=None):
    # No exception messages, paths, arbitrary type names or traceback text.
    kind = next((name for cls, name in (
        (FileNotFoundError, 'FileNotFoundError'),
        (PermissionError, 'PermissionError'),
        (OSError, 'OSError'), (UnicodeError, 'UnicodeError'),
        (ValueError, 'ValueError'),
    ) if isinstance(exc, cls)), 'other')
    number = getattr(exc, 'errno', None)
    return {'stage': stage, 'exception_type': kind,
            'errno': number if number in {errno.ENOENT, errno.EACCES, errno.EIO, errno.EPERM} else None,
            'depth_from_leaf': depth, 'private_text_included': False}


def scoped_mount_signature(membership, mounts, job):
    """Re-resolve memory controller; retain every mount that can mask its reads."""
    version, leaf, _, _ = prior.resolve_cgroup(membership, mounts, job)
    leaf = PurePosixPath(leaf)
    anchor = next(p for p in (leaf, *leaf.parents)
                  if re.fullmatch(r'job[_-]' + job + r'(?:\.scope)?', p.name))
    selected = []
    for line in mounts.splitlines():
        left, sep, right = line.partition(' - ')
        fields, fs = left.split(), right.split()
        require(bool(sep) and len(fields) >= 6 and len(fs) >= 3)
        target_text = re.sub(r'\\(040|011|012|134)',
                             lambda m: chr(int(m.group(1), 8)), fields[4])
        require('\\' not in target_text)
        target = PurePosixPath(target_text)
        require(target.is_absolute() and '..' not in target.parts)
        # Ancestors can replace the controller mount; descendants can shadow
        # usage/limit/hierarchy files at ANY level between task and job.
        if anchor.is_relative_to(target) or target.is_relative_to(anchor):
            selected.append(line)
    require(bool(selected) and len(selected) == len(set(selected)))
    return version, str(leaf), tuple(sorted(selected))


class MemoryGate(prior.MemoryGate):
    def __init__(self, job, pid=None):
        self.last_failure = None
        self._mount_signature = None
        try:
            super().__init__(job, pid)
        except MemoryObservationError:
            raise
        except Exception as exc:
            self.last_failure = failure('initial_policy_or_resolution', exc)
            raise MemoryObservationError(self.last_failure) from None

    def checked(self, stage, fn, depth=None):
        try:
            return fn()
        except MemoryObservationError:
            raise
        except Exception as exc:
            self.last_failure = failure(stage, exc, depth)
            raise MemoryObservationError(self.last_failure) from None

    def read_limits(self):
        values = []
        for depth, path in enumerate(self.chain):
            self.checked('path_identity', lambda: require(path.resolve(strict=True) == path), depth)
            if self.version == 'v1':
                self.checked('hierarchy', lambda: require(original.numeric(path / 'memory.use_hierarchy') == 1), depth)
            raw = self.checked('limit_read', lambda: original.bounded_text(path / self.limit_name).strip(), depth)
            if self.version == 'v2' and raw == 'max':
                values.append(None)
            else:
                self.checked('limit_parse', lambda: require(re.fullmatch(r'[0-9]{1,20}', raw) is not None), depth)
                values.append(int(raw))
        return tuple(values)

    def sample(self):
        membership = self.checked('membership_read', lambda: original.bounded_text(f'/proc/{self.pid}/cgroup'))
        self.checked('membership_changed', lambda: require(membership == self.membership))
        if self._mount_signature is None:
            self._mount_signature = self.checked('mount_baseline', lambda: scoped_mount_signature(self.membership, self.mounts, self.job))
        mounts = self.checked('mount_read', lambda: original.bounded_text(f'/proc/{self.pid}/mountinfo'))
        signature = self.checked('mount_resolution', lambda: scoped_mount_signature(membership, mounts, self.job))
        self.checked('memory_mount_changed', lambda: require(signature == self._mount_signature))
        limits = self.read_limits()
        self.checked('limit_changed', lambda: require(limits == self.limits))
        return max(self.checked('usage_read_or_parse', lambda p=p: original.numeric(p / self.usage_name), depth)
                   for depth, p in enumerate(self.chain))

    def public(self):
        result = super().public()
        result['memory_gate_protocol'] = 'job_scoped_hierarchical_ram_v2_candidate'
        result['mount_validation_scope'] = 'memory_controller_and_job_path_covering_mounts'
        result['sanitized_failure_diagnostics'] = True
        return result
