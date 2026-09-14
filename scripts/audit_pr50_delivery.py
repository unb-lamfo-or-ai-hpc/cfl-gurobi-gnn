"""Audit a bounded evidence ZIP without deserializing models or executing jobs.

The output certifies consistency of supplied evidence only. Graphs, checkpoints,
predictions and omitted curve files cannot be independently validated here.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import zipfile


def classification(counts):
    tp, tn, fp, fn = (int(counts[k]) for k in ('tp', 'tn', 'fp', 'fn'))
    return {'accuracy': (tp + tn) / (tp + tn + fp + fn),
            'precision': tp / (tp + fp) if tp + fp else 0.0,
            'recall': tp / (tp + fn) if tp + fn else 0.0,
            'f1_score': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0}


def audit(path):
    failures = []
    def check(condition, name):
        if not condition:
            failures.append(name)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(PurePosixPath(n).is_absolute() or '..' in PurePosixPath(n).parts or '\\' in n or ':' in n for n in names):
            raise ValueError('Unsafe or duplicate ZIP members')
        if sum(x.file_size for x in archive.infolist()) > 200 * 1024**2:
            raise ValueError('Evidence archive exceeds 200 MiB')
        payload = {name: archive.read(name) for name in names}
    read = lambda n: json.loads(payload[n])
    rows = lambda n: list(csv.DictReader(io.StringIO(payload[n].decode('utf-8'))))
    digest = lambda n: hashlib.sha256(payload[n]).hexdigest()
    manifest = read('MANIFEST.json')
    included = [x for x in manifest['files'] if x['status'] == 'included']
    for entry in included:
        name = entry['file']
        check(name in payload and digest(name) == entry['packaged_sha256'], 'packaged_hash:' + name)
        check(len(payload[name]) == entry['bytes'], 'packaged_size:' + name)
        if not entry['sanitized']:
            check(entry['original_sha256'] == entry['packaged_sha256'], 'original_hash:' + name)
    sensitive = re.compile(r'/raid/|/home/|(?<![\w])[A-Za-z]:[\\/]|WLSSecret|LicenseID|gurobi\.lic')
    for name, content in payload.items():
        check(not sensitive.search(content.decode('utf-8')), 'private_content:' + name)
    revision = read('revision/confirmation_cohort_revision.json')
    graph = read('dataset/confirmation_graph_report.json')
    plan = read('training/gasse_training_plan.json')
    training = read('training/gasse_training_report.json')
    evaluation_plan = read('training/evaluation/gasse_evaluation_plan.json')
    evaluation = read('training/evaluation/gasse_evaluation_report.json')
    history = rows('training/training_epoch_metrics.csv')
    parents = rows('training/evaluation/per_parent_metrics.csv')
    difficulty = rows('training/evaluation/per_difficulty_metrics.csv')
    records = plan['records']
    check(len(records) == len({r['sample_id'] for r in records}) == 39, 'unique_cohort')
    check(set(revision['cohort']) == {r['sample_id'] for r in records}, 'cohort_identity')
    check(dict(Counter(r['role'] for r in records)) == {'train': 23, 'validation': 8, 'test': 8}, 'partition_counts')
    check(all(r['label_solver'] == 'gurobi' and r['graph_authority'] == 'gurobi' and 0 <= r['label_mip_gap_relative'] <= .1 for r in records), 'label_admission')
    check(plan['graph_report_sha256'] == digest('dataset/confirmation_graph_report.json'), 'graph_report_link')
    check(plan['contract_sha256'] == training['training_contract_sha256'], 'training_contract')
    check(evaluation_plan['contract_sha256'] == evaluation['contract_sha256'], 'evaluation_contract')
    check(evaluation_plan['checkpoint_sha256'] == training['outputs']['checkpoint']['sha256'], 'checkpoint_receipt_link')
    check(training['selected_probability_threshold'] == evaluation['probability_threshold'] == evaluation_plan['probability_threshold'], 'threshold_link')
    check(training['threshold_source'] == evaluation['threshold_source'] == 'maximum_validation_f1', 'validation_threshold')
    check(training['checkpoint_selection'] == 'minimum_validation_weighted_bce', 'validation_checkpoint')
    check(training['test_graphs_loaded'] == 0 and training['prenorm_audit']['validation_or_test_used'] is False, 'training_test_isolation_receipt')
    check(evaluation['test_graphs_loaded'] == 8 and evaluation['test_partition_usage'] == 'held_out_evaluation_only', 'held_out_receipt')
    check([int(x['epoch']) for x in history] == list(range(1, 101)), 'full_epoch_sequence')
    check(all(math.isfinite(float(v)) for x in history for v in x.values()), 'finite_history')
    check(set(x['parent_instance_id'] for x in parents) == {r['sample_id'] for r in records if r['role'] == 'test'}, 'test_identities')
    aggregate = evaluation['aggregate_metrics']
    for key in ('tp', 'tn', 'fp', 'fn', 'n_targets', 'n_positive'):
        check(sum(int(x[key]) for x in parents) == aggregate[key] == sum(int(x[key]) for x in difficulty), 'metric_total:' + key)
    for row in parents + difficulty + [aggregate]:
        for key, value in classification(row).items():
            check(math.isclose(float(row[key]), value, abs_tol=1e-12), 'classification:' + key)
    for key in classification(aggregate):
        check(math.isclose(sum(float(x[key]) for x in parents) / 8, evaluation['parent_macro_classification'][key], abs_tol=1e-12), 'macro:' + key)
    for report, folder in ((training, 'training/'), (evaluation, 'training/evaluation/')):
        for name, receipt in report['outputs'].items():
            if folder + name in payload:
                check(receipt['sha256'] == digest(folder + name), 'output_link:' + name)
    for record in records:
        receipt_path = 'dataset/' + record['receipt']['relative_path']
        check(digest(receipt_path) == record['receipt']['sha256'], 'graph_receipt:' + record['sample_id'])
    for name in ('statistics', 'clustering'):
        report = read(f'dataset/analysis/{name}/graph_{name}_report.json')
        check(report['gate_status'] == 'passed' and report['summary']['graphs'] == 39, name + '_receipt')
        check(report['graph_manifest_sha256'] == digest('dataset/confirmation_graph_manifest.jsonl'), name + '_manifest')
        for n, output in report['outputs'].items():
            check(output['sha256'] == digest(f'dataset/analysis/{name}/{n}'), name + '_output_hash')
    check(graph['gate_status'] == training['gate_status'] == evaluation['gate_status'] == 'passed', 'supplied_stage_gates')
    check(revision['original_campaign_remains_incomplete'] is True, 'strict_42_failure_preserved')
    best = min(history, key=lambda x: float(x['validation_loss']))
    return {'schema_version': 1, 'scope': 'supplied_evidence_consistency_not_raw_artifact_reexecution',
            'archive_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'gate_status': 'failed' if failures else 'passed', 'failures': failures,
            'packaged_files_hash_verified': len(included),
            'withheld': [x['file'] for x in manifest['files'] if x['status'] != 'included'],
            'unverified_raw_artifacts': ['graphs', 'root_vectors', 'labels', 'checkpoint', 'predictions', 'full_roc_pr_curves'],
            'cohort': {'parents': 39, 'easy': 30, 'medium': 9, 'hard': 0, 'train': 23, 'validation': 8, 'test': 8},
            'training': {'epochs': len(history), 'best_validation_epoch_from_history': int(best['epoch']),
                         'best_validation_loss': float(best['validation_loss']), 'first_epoch': history[0], 'last_epoch': history[-1],
                         'checkpoint_sha256': training['outputs']['checkpoint']['sha256'],
                         'probability_threshold': evaluation['probability_threshold'], 'protocol': plan['protocol']},
            'evaluation': {k: evaluation[k] for k in ('aggregate_metrics', 'parent_macro_classification', 'score_diagnostics', 'baseline_diagnostics', 'roc_auc', 'precision_recall_auc')},
            'limitations': ['solver_admissibility_selection', 'three_medium_parents_excluded', 'one_seed', 'no_hard_parents',
                            'no_current_cohort_four_arm_comparison', 'no_current_cohort_native_solver_benchmark',
                            'uncalibrated_scores', 'graph_statistics_censoring_unknown', 'raw_artifacts_not_packaged'],
            'development_only': True, 'scientific_reporting_eligible': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit(args.archive)
    text = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8', newline='\n')
    print(text)
    raise SystemExit(bool(result['failures']))
