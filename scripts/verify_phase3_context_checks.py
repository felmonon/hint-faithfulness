#!/usr/bin/env python3
"""Verify source-bound second-reader attestations, without creating semantic labels.

This checks structure and coverage, not comprehension or human accuracy. Flagged
disagreements are preserved as unresolved; this tool never adjudicates them.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from scripts.review_phase3_traces import (load_prepared, validate_review_files,
    recheck_plan, read_object, read_lines, require, sha, utc, label_path, resolve_label)

DEFAULT_REVIEW_DIR = PROJECT/'results/pilot-20-phase3-v1/ai-review'
CATEGORIES = {'ordinary_reasoning', 'explicit_outside_nudge_claim', 'incoherent', 'ambiguous', 'empty'}
CHECK_FIELDS = {'record_id', 'source_sha256', 'partition_manifest_sha256',
    'primary_review_sha256', 'reviewer_id', 'reviewed_at_utc', 'full_read',
    'agrees_with_primary', 'observed_category', 'outside_nudge_claim_in_reasoning',
    'outside_nudge_claim_in_content', 'notes', 'suggested_changes'}


def verify_partition(assignment, checks, partition, manifest, seal, reviews, primary_file, plan, now):
    """Validate one partition against the freshly recomputed complete recheck plan."""
    pid = partition['partition_id']
    selected = [rid for rid in partition['record_ids'] if rid in plan['combined_full_text_export_ids']]
    mandatory = [rid for rid in partition['record_ids'] if rid in plan['mandatory_context_recheck_ids']]
    spot = next(item for item in plan['second_ai_spotchecks'] if item['partition_id'] == pid)
    require(assignment.get('schema') == 'phase3-ai-context-check-assignment-v1'
            and assignment.get('partition_id') == pid, 'Wrong context-check assignment identity')
    hashes = {'source_sha256': manifest['source']['sha256'], 'partition_manifest_sha256': seal,
              'protocol_sha256': manifest['protocol']['sha256'], 'primary_review_sha256': primary_file['sha256']}
    for key, value in hashes.items():
        require(assignment.get(key) == value, f'Assignment {key} mismatch: {pid}')
    require(resolve_label(assignment['primary_review_path']).resolve() == resolve_label(primary_file['path']).resolve(),
            'Assignment binds a different primary review path')
    require(assignment.get('record_ids') == selected and assignment.get('mandatory_ids') == mandatory
            and assignment.get('spotcheck') == spot, 'Assignment selection differs from final recheck plan')
    assigned_at = utc(assignment['created_at_utc'])
    require(assigned_at <= now, 'Assignment timestamp is in the future')
    ids = [item.get('record_id') for item in checks]
    require(len(ids) == len(set(ids)), 'Duplicate context-check record IDs')
    require(set(ids) == set(selected), 'Missing or unexpected context-check record IDs')
    unresolved = []
    for item in checks:
        rid = item['record_id']; primary = reviews[rid]
        require(CHECK_FIELDS <= item.keys() and set(item) <= CHECK_FIELDS | {'protocol_sha256'},
                'Unexpected or missing context-check fields')
        for key in ('source_sha256', 'partition_manifest_sha256', 'primary_review_sha256'):
            require(item[key] == hashes[key], f'Context-check {key} mismatch')
        if 'protocol_sha256' in item:
            require(item['protocol_sha256'] == hashes['protocol_sha256'], 'Context-check protocol hash mismatch')
        reviewer = item['reviewer_id']
        require(isinstance(reviewer, str) and bool(reviewer.strip()) and reviewer == reviewer.strip()
                and reviewer != primary['reviewer']['id'].strip(), 'Second reader must differ from actual primary reader')
        require(isinstance(item['full_read'], dict) and set(item['full_read']) == {'messages', 'reasoning', 'content'}
                and all(value is True for value in item['full_read'].values()), 'All three full-read attestations must be true')
        reviewed_at = utc(item['reviewed_at_utc'])
        require(max(assigned_at, utc(primary['reviewed_at_utc'])) <= reviewed_at <= now,
                'Context-check timestamp predates its primary/assignment or is in the future')
        require(isinstance(item['notes'], str) and bool(item['notes'].strip()), 'Context-check notes must be nonempty')
        require(type(item['agrees_with_primary']) is bool and isinstance(item['suggested_changes'], dict),
                'Agreement must be boolean and suggested_changes an object')
        require(item['observed_category'] in CATEGORIES, 'Unknown observed category')
        for key in ('outside_nudge_claim_in_reasoning', 'outside_nudge_claim_in_content'):
            require(item[key] is None or type(item[key]) is bool, 'Claim flags must be true, false or null')
        if item['agrees_with_primary']:
            require(item['observed_category'] == primary['category'] and not item['suggested_changes']
                    and all(item[key] is primary[key] for key in
                        ('outside_nudge_claim_in_reasoning', 'outside_nudge_claim_in_content')),
                    'Agreement contradicts primary category/flags or contains suggested changes')
        else:
            unresolved.append(item)
    spot_ids = [spot[key] for key in ('ordinary_record_id', 'invalid_or_truncated_record_id') if spot[key]]
    return {'partition_id': pid, 'mandatory_records': len(mandatory), 'selected_records': len(selected),
        'checked_records': len(checks), 'mandatory_checked_records': sum(rid in ids for rid in mandatory),
        'spotcheck_roles': len(spot_ids), 'unique_spotcheck_records': len(set(spot_ids)),
        'spotcheck': spot, 'record_ids': selected,
        'primary_reviewer_ids': sorted({reviews[rid]['reviewer']['id'] for rid in selected}),
        'second_reviewer_ids': sorted({item['reviewer_id'] for item in checks}),
        'unresolved_disagreements': unresolved}


def verify_context_checks(review_dir, coverage_path, out):
    review_dir, coverage_path, out = map(Path, (review_dir, coverage_path, out))
    require(not out.exists(), 'Choose a fresh output path; do not overwrite evidence')
    require(not out.resolve().is_relative_to((PROJECT/'artifacts').resolve()), 'Output belongs outside raw artifacts')
    manifest_path = review_dir/'partition-manifest.json'
    manifest, seal, rows, validator = load_prepared(manifest_path)
    require(not out.resolve().is_relative_to(resolve_label(manifest['source']['path']).parent.resolve()),
            'Output belongs outside the source artifact directory')
    reviews, files, _, _ = validate_review_files(sorted((review_dir/'reviews').glob('*.jsonl')),
                                               manifest, seal, rows, validator)
    require(len(reviews) == 198, 'Exactly 198 complete primary annotations are required')
    plan = recheck_plan(manifest, reviews)
    bound = {manifest_path: seal, Path(__file__): sha(Path(__file__))}
    for item in files + [manifest[key] for key in ('source', 'protocol', 'integrity_audit', 'human_label_sheet')]:
        bound[resolve_label(item['path'])] = item['sha256']

    def capture(path, reader):
        expected = sha(path); result = reader(path)
        require(sha(path) == expected, 'Context evidence changed while reading')
        bound[path] = expected
        return result

    coverage = capture(coverage_path, read_object)
    for key, value in {'source_sha256': manifest['source']['sha256'], 'protocol_sha256': manifest['protocol']['sha256'],
                       'partition_manifest_sha256': seal, 'expected_records': 198, 'submitted_reviews': 198,
                       'complete_primary_reviews': 198, 'complete_primary_coverage': True,
                       'missing_record_ids': [], 'needs_reread_record_ids': []}.items():
        require(coverage.get(key) == value, f'Final primary coverage mismatch: {key}')
    require(sorted(coverage['review_files'], key=lambda x: x['partition_id']) == sorted(files, key=lambda x: x['partition_id'])
            and coverage['second_pass'] == plan, 'Coverage is stale or binds different primary reviews/recheck work')
    partitions, all_checks = [], []
    by_partition = {item['partition_id']: item for item in files}
    now = datetime.now(timezone.utc)
    for partition in manifest['partitions']:
        directory = review_dir/'second-pass'/partition['partition_id']
        assignment_path, checks_path = directory/'assignment.json', directory/'checks.jsonl'
        assignment = capture(assignment_path, read_object)
        checks = capture(checks_path, read_lines)
        all_checks.extend(checks)
        report = verify_partition(assignment, checks, partition, manifest, seal, reviews,
                                  by_partition[partition['partition_id']], plan, now)
        report.update(assignment={'path': label_path(assignment_path), 'sha256': bound[assignment_path]},
                      checks={'path': label_path(checks_path), 'sha256': bound[checks_path]})
        partitions.append(report)
    disagreements = [item for part in partitions for item in part['unresolved_disagreements']]
    result = {'schema': 'phase3-ai-context-check-verification-v1', 'verified_at_utc': now.isoformat(),
        'source_sha256': manifest['source']['sha256'], 'protocol_sha256': manifest['protocol']['sha256'],
        'partition_manifest_sha256': seal, 'primary_review_files': files,
        'primary_coverage': {'path': label_path(coverage_path), 'sha256': bound[coverage_path]},
        'verification_code_sha256': bound[Path(__file__)], 'complete_primary_reviews': 198,
        'mandatory_records': len(plan['mandatory_context_recheck_ids']),
        'selected_records': len(plan['combined_full_text_export_ids']),
        'checked_records': sum(part['checked_records'] for part in partitions),
        'spotcheck_roles': sum(part['spotcheck_roles'] for part in partitions),
        'unique_spotcheck_records': sum(part['unique_spotcheck_records'] for part in partitions),
        'second_reviewer_record_counts': dict(sorted(Counter(item['reviewer_id'] for item in all_checks).items())),
        'partitions': partitions, 'unresolved_disagreement_count': len(disagreements),
        'unresolved_disagreement_record_ids': [item['record_id'] for item in disagreements],
        'second_reader_coverage_complete': True, 'full_review_process_complete': not disagreements,
        'human_labels_created': 0, 'inference_or_judge_calls': 0,
        'limits': ['Structural verification of reader attestations does not independently prove comprehension.',
                   'Unblinded AI context checks are not human accuracy or a validated faithfulness measure.',
                   'Different reader IDs do not establish different models or independent human judgment.',
                   'Disagreements remain unresolved here; no primary labels are changed or automatically adjudicated.']}
    for path, expected in bound.items():
        require(sha(path) == expected, f'Bound evidence changed during verification: {label_path(path)}')
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-dir', type=Path, default=DEFAULT_REVIEW_DIR)
    parser.add_argument('--coverage', type=Path, help='Defaults to REVIEW_DIR/coverage-v1/coverage.json')
    parser.add_argument('--out', type=Path, help='Fresh path; defaults to REVIEW_DIR/second-pass/completion.json')
    args = parser.parse_args()
    report = verify_context_checks(args.review_dir, args.coverage or args.review_dir/'coverage-v1/coverage.json',
                                   args.out or args.review_dir/'second-pass/completion.json')
    print(f"Verified {report['checked_records']} context checks; unresolved disagreements: {report['unresolved_disagreement_count']}. "
          'Reader comprehension is not independently certified.')


if __name__ == '__main__':
    main()
