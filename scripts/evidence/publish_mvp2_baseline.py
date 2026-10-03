"""Publish small allowlisted evidence summaries; never copy private binaries.

SPDX-License-Identifier: MIT
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile

from verify_mvp1_closure_receipts import verify, EXPECTED

PRIVATE = re.compile(r'(?i)/(?:home|raid)/|[a-z]:[/\\]|\\\\|(?:gh[opusr]_[a-z0-9]+)|(?:password|api_key|wlssecret)\s*[:=]')
JOBS = {'3307': 'mixed_39_training', '3361': 'easy_only_training',
        '3422': 'mixed_54_training_timeout', '3427': 'evaluation_recovery'}


def training_allocations(text):
    lines = text.splitlines()
    expected = 'JobID|JobName|State|ExitCode|ElapsedRaw|TotalCPU|AllocCPUS|AllocTRES|MaxRSS|ReqMem'
    if not lines or lines[0] != expected:
        raise ValueError('Slurm accounting schema is not supported')
    rows = []
    for line in lines[1:]:
        values = line.split('|')
        if values[0] not in JOBS:
            continue
        if len(values) != 10 or any(r['job_id'] == values[0] for r in rows):
            raise ValueError('Duplicate or malformed parent Slurm row')
        tres = dict(item.split('=', 1) for item in values[7].split(',') if '=' in item)
        gpu = tres.get('gres/gpu')
        rows.append({'job_id': values[0], 'phase': JOBS[values[0]], 'state': values[2],
                     'exit_code': values[3], 'elapsed_seconds': int(values[4]),
                     'reported_total_cpu_time': values[5], 'allocated_cpus': int(values[6]),
                     'allocated_gpus': int(gpu) if gpu is not None else None,
                     'requested_memory': values[9] or None,
                     'gpu_utilization': None, 'ddp_execution_verified': False})
    if {row['job_id'] for row in rows} != set(JOBS):
        raise ValueError('Expected historical training/evaluation allocations are missing')
    return sorted(rows, key=lambda row: int(row['job_id']))


def parent_coverage(inventory):
    cohort = set(inventory['cohort'])
    rows = []
    for difficulty in ('easy', 'medium', 'hard'):
        for number in range(30):
            parent = f'CFL_{difficulty}_instance_{number}'
            tables = [r for r in inventory['incumbent_tables'] if parent in r['parent_ids_from_path']]
            rows.append({'parent_id': parent, 'difficulty': difficulty,
                         'in_frozen_learning_cohort': parent in cohort,
                         'observed_incumbent_tables': len(tables),
                         'unique_feasible_incumbents': None,
                         'fit_validation_test_role': 'not_recovered_in_this_receipt'})
    return rows


def publication_payloads(verification, inventory, allocations):
    keys = ['scope', 'closure_package_sha256', 'local_receipt_files',
            'freeze_checksum_targets_verified', 'withheld_file_crosschecks_valid',
            'package_report_receipt_hash_valid', 'archive_parts', 'archive_groups',
            'archive_compressed_bytes', 'archive_payload_bytes', 'included_files',
            'all_source_member_hash_declarations_equal', 'large_archives_rehashed_locally',
            'large_archive_verification_source', 'upload_ready', 'zenodo_upload_performed',
            'scientific_reporting_eligible']
    closure = {key: verification[key] for key in keys}
    closure.update(schema_version=1, gate_status='passed',
                   policy_excluded_operational_paths=7, invalid_structured_files_retained=1,
                   publication_scope='allowlisted_summary_not_private_archive',
                   source_main_commit='c8297139aaeed78c7951c91379983c414b181860',
                   synchronized_develop_commit='534cc4f07be14c28ff1788352446af846d6458b3')
    incumbents = {'schema_version': 1, 'scope': 'artifact_observations_not_unique_solutions',
                  'source_receipts_sha256': EXPECTED, 'cohort_by_class': inventory['cohort_by_class'],
                  'cohort': inventory['cohort'],
                  'observations_by_path_solver': verification['incumbent_table_observations_by_path_solver'],
                  'complete_gurobi_54_parent_incumbent_total': None,
                  'complete_scip_54_parent_incumbent_total': None,
                  'counts_include_repeated_attempts_and_derived_models': True,
                  'missing_evidence_is_not_zero': True}
    hardware = {'schema_version': 1, 'scope': 'slurm_allocation_not_utilization',
                'source_receipts_sha256': EXPECTED, 'jobs': allocations,
                'training_quality_comparison_performed': False,
                'ddp_scaling_comparison_performed': False}
    coverage = {'schema_version': 1, 'scope': 'original_parent_inventory_not_run_ledger',
                'source_receipts_sha256': EXPECTED, 'parents': parent_coverage(inventory),
                'zero_tables_means_no_table_observed_not_no_incumbents': True,
                'label_admission_not_reconstructed_from_footer_counts': True}
    results = {'closure_verification.json': closure, 'incumbent_inventory.json': incumbents,
               'hardware_allocations.json': hardware, 'parent_coverage.json': coverage}
    encoded = {name: (json.dumps(value, indent=2, sort_keys=True) + '\n').encode('utf-8')
               for name, value in results.items()}
    if any(PRIVATE.search(value.decode('utf-8')) for value in encoded.values()):
        raise ValueError('Publication summaries contain a prohibited private marker')
    return encoded


def publish(package, output):
    if output.exists():
        raise ValueError('Preserve existing summaries; choose a fresh output directory')
    verification = verify(package)
    with tarfile.open(package, 'r:gz') as archive:
        inventory = json.load(archive.extractfile('computational-inventory/incumbent_inventory.json'))
        accounting = archive.extractfile('computational-inventory/slurm_accounting.txt').read().decode('utf-8')
    payloads = publication_payloads(verification, inventory, training_allocations(accounting))
    output.mkdir(parents=True)
    for name, payload in payloads.items():
        (output / name).write_bytes(payload)
    (output / 'SHA256SUMS.txt').write_text(''.join(
        hashlib.sha256(payload).hexdigest() + '  ' + name + '\n'
        for name, payload in sorted(payloads.items())), encoding='utf-8')
    print('MVP2_BASELINE_SUMMARIES_OK | files=4 | research_runs=0 | zenodo_upload=false')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    publish(args.receipts, args.output)
