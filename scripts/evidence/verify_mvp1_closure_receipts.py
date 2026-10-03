"""Verify small closure receipts without extracting or loading research binaries.

SPDX-License-Identifier: MIT
"""
from pathlib import Path, PurePosixPath
import argparse
import collections
import hashlib
import json
import tarfile

if not __debug__:
    raise RuntimeError('Receipt verification requires Python assertion checks enabled')

EXPECTED = 'f5cc52a20f69ebae0af8aecff5ac7c2981de85118d09a4d5406c3877a4cef156'


def checksum_lines(payload):
    rows = {}
    for line in payload.decode('utf-8').splitlines():
        digest, name = line.split('  ', 1)
        assert len(digest) == 64 and all(c in '0123456789abcdef' for c in digest)
        assert name not in rows
        rows[name] = digest
    return rows


def verify(package):
    assert hashlib.sha256(package.read_bytes()).hexdigest() == EXPECTED
    payloads = {}
    with tarfile.open(package, 'r:gz') as archive:
        names = set()
        for member in archive:
            name = PurePosixPath(member.name)
            assert not name.is_absolute() and '..' not in name.parts
            assert '\\' not in member.name and ':' not in member.name
            assert member.name not in names and (member.isfile() or member.isdir())
            names.add(member.name)
            if member.isfile():
                assert member.size <= 10_000_000
                payloads[member.name] = archive.extractfile(member).read()
    expected_files = {
        'FREEZE_SHA256SUMS.txt', 'computational-inventory/SHA256SUMS.txt',
        'computational-inventory/incumbent_inventory.json',
        'computational-inventory/incumbent_table_inventory.csv',
        'computational-inventory/slurm_accounting.txt',
        'evidence/package_report.json', 'evidence/archive_verification.json',
        'evidence/text_preflight.json', 'evidence/upload/SHA256SUMS.txt',
        'evidence/upload/withheld_files.json',
    }
    assert set(payloads) == expected_files
    hashed = set()
    for sums, prefix in [('FREEZE_SHA256SUMS.txt', ''),
                         ('computational-inventory/SHA256SUMS.txt', 'computational-inventory/')]:
        for name, digest in checksum_lines(payloads[sums]).items():
            target = prefix + name
            assert hashlib.sha256(payloads[target]).hexdigest() == digest
            hashed.add(target)
    load = lambda name: json.loads(payloads[name])
    report = load('evidence/package_report.json')
    receipt = load('evidence/archive_verification.json')
    withheld = load('evidence/upload/withheld_files.json')['files']
    inventory = load('computational-inventory/incumbent_inventory.json')
    assert receipt['package_report_sha256'] == hashlib.sha256(payloads['evidence/package_report.json']).hexdigest()
    assert receipt['archive_and_member_hashes_valid'] and receipt['private_archive']
    assert not receipt['upload_performed'] and not receipt['scientific_reporting_eligible']
    assert report['private_archive'] and report['archival_coverage_complete_for_discovered_files']
    assert not report['upload_ready'] and not report['source_files_modified']
    assert not report['publication_authorized'] and not report['upload_performed']
    assert len(withheld) == report['withheld_entries'] == 7
    assert all(r['reason'] == 'private_operational_directory_or_symlink' and
               'source_sha256' not in r for r in withheld)
    expected_exclusions = {
        'analysis/pr58_validation_guidance/tools',
        'analysis/pr58_validation_guidance/bootstrap',
        'analysis/pr60_scientific_evidence/bootstrap',
        'analysis/pr57_54/tools',
        'analysis/pr59_heldout_guidance/bootstrap',
        'analysis/pr61_documentation/bootstrap',
        'intermediate/gurobi_expansion_campaign/pr54_20260915T152610Z/.pr57-remaining-medium-queue',
    }
    assert {r['relative_path'] for r in withheld} == expected_exclusions
    withheld_hash = hashlib.sha256(payloads['evidence/upload/withheld_files.json']).hexdigest()
    assert report['sidecar_sha256']['withheld_files.json'] == withheld_hash
    upload_sums = checksum_lines(payloads['evidence/upload/SHA256SUMS.txt'])
    assert upload_sums['withheld_files.json'] == withheld_hash
    assert upload_sums['package_report.json'] == receipt['package_report_sha256']
    members = {}
    for part in report['packages']:
        assert upload_sums[part['file']] == part['sha256']
        for row in part['members']:
            path = row['relative_path']
            assert path not in members
            assert PurePosixPath(path).parts[0] in {'analysis','intermediate','bipartite_graphs','models','embeddings'}
            assert '..' not in PurePosixPath(path).parts and not PurePosixPath(path).is_absolute()
            assert row['archive'] == part['file']
            assert row['source_sha256'] == row['public_sha256'] and not row['transformed']
            members[path] = row
    assert len(members) == report['included_files'] == 8790
    assert report['transformed_text_files'] == 0
    invalid = report['invalid_structured_artifacts']
    assert invalid == load('evidence/text_preflight.json')['issues']
    assert all(row['relative_path'] in members for row in invalid)
    for row in inventory['incumbent_tables'] + inventory['reported_counters']:
        assert members[row['relative_path']]['source_sha256'] == row['sha256']
    assert len(inventory['cohort']) == len(set(inventory['cohort'])) == 54
    assert inventory['cohort_by_class'] == {'easy': 30, 'medium': 24}
    observed = collections.defaultdict(lambda: {'tables': 0, 'footer_rows': 0, 'unknown_row_counts': 0, 'parent_ids': set(), 'file_hashes': set()})
    for row in inventory['incumbent_tables']:
        parts = PurePosixPath(row['relative_path']).parts
        solver = 'gurobi' if 'gurobi' in parts else 'scip' if 'scip' in parts or 'scip_parent_solutions' in parts else 'unattributed'
        group = observed[solver]
        group['tables'] += 1
        if row['parquet_rows'] is None:
            group['unknown_row_counts'] += 1
        else:
            group['footer_rows'] += row['parquet_rows']
        group['parent_ids'].update(row['parent_ids_from_path'])
        group['file_hashes'].add(row['sha256'])
    for group in observed.values():
        group['parent_ids'] = sorted(group['parent_ids'])
        group['distinct_file_hashes'] = len(group.pop('file_hashes'))
    return {
        'gate_status': 'passed', 'scope': 'private_archival_receipt_integrity_not_scientific_certification',
        'closure_package_sha256': EXPECTED, 'local_receipt_files': len(payloads),
        'freeze_checksum_targets_verified': len(hashed),
        'withheld_file_crosschecks_valid': True, 'package_report_receipt_hash_valid': True,
        'archive_parts': len(report['packages']),
        'archive_groups': dict(collections.Counter(p['group'] for p in report['packages'])),
        'archive_compressed_bytes': sum(p['bytes'] for p in report['packages']),
        'archive_payload_bytes': sum(p['payload_bytes'] for p in report['packages']),
        'included_files': len(members), 'all_source_member_hash_declarations_equal': True,
        'large_archives_rehashed_locally': False, 'large_archive_verification_source': 'HPC_verification_receipt',
        'policy_exclusions': withheld, 'invalid_structured_artifacts_retained': invalid,
        'incumbent_table_observations_by_path_solver': dict(observed),
        'incumbent_rows_are_unique_feasible_solution_counts': False,
        'complete_gurobi_54_parent_incumbent_total': inventory['complete_gurobi_54_parent_incumbent_total'],
        'complete_scip_54_parent_incumbent_total': inventory['complete_scip_54_parent_incumbent_total'],
        'upload_ready': False, 'zenodo_upload_performed': False, 'scientific_reporting_eligible': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.package)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['policy_exclusions','incumbent_table_observations_by_path_solver']}, indent=2))
