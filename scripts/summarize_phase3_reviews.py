#!/usr/bin/env python3
"""Count validated AI annotations; no labels, reading attestations or inference created.

This does not validate or replace the separately recorded second-reader process.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from scripts.review_phase3_traces import load_prepared, validate_review_files, sha, require

CATEGORIES = ('ordinary_reasoning', 'explicit_outside_nudge_claim', 'incoherent', 'ambiguous', 'empty')
CHANGE_GROUPS = ('vector_target_switch', 'random_target_switch', 'other_vector_change', 'other_random_change')


def change_group(review):
    link = review['baseline_link']
    if not link['valid_nonbaseline_pair'] or review['direction'] not in ('vector', 'random'):
        return None
    if link['target_directed_switch'] is True:
        return review['direction'] + '_target_switch'
    if link['baseline_relative_change'] is True and link['target_directed_switch'] is False:
        return 'other_' + review['direction'] + '_change'
    return None


def counts(selected):
    return {'records': len(selected),
            'categories': {category: sum(r['category'] == category for r in selected) for category in CATEGORIES},
            'issues_nonexclusive': dict(sorted(Counter(issue for r in selected for issue in r['issues']).items())),
            'reasoning_outside_claim': {str(flag).lower(): sum(r['outside_nudge_claim_in_reasoning'] is flag for r in selected) for flag in (True, False, None)},
            'content_outside_claim': {str(flag).lower(): sum(r['outside_nudge_claim_in_content'] is flag for r in selected) for flag in (True, False, None)},
            'content_only_explicit_claims': sum(r['outside_nudge_claim_in_content'] is True and r['outside_nudge_claim_in_reasoning'] is False for r in selected),
            'record_ids': [r['record_id'] for r in selected]}


def summarize(rows, reviews):
    by_id = {row['record_id']: row for row in rows}
    ordered = [reviews[row['record_id']] for row in rows]
    result = {}
    for cohort, selected in [('primary_six_questions', ordered),
                             ('secondary_five_questions', [r for r in ordered if r['secondary_five_question_member']])]:
        changed = {}
        for group in CHANGE_GROUPS:
            members = [r for r in selected if change_group(r) == group]
            changed[group] = {'all': counts(members)}
            for name, correct in [('correct_target', True), ('incorrect_target', False)]:
                changed[group][name] = counts([r for r in members if
                    (r['target_letter'] == by_id[r['record_id']]['correct_answer']) is correct])
        result[cohort] = {'all': counts(selected),
                         'by_direction': {d: counts([r for r in selected if r['direction'] == d]) for d in ('baseline', 'vector', 'random')},
                         'changed_answer_groups': changed}
    long_rows = []
    for review in ordered:
        source = by_id[review['record_id']]
        target = review['target_letter']
        long_rows.append({**{key: review[key] for key in ('record_id', 'source_line', 'question_id', 'direction', 'target_letter', 'strength', 'status', 'answer', 'category', 'secondary_five_question_member', 'outside_nudge_claim_in_reasoning', 'outside_nudge_claim_in_content')},
            'correct_answer': source['correct_answer'],
            'target_stratum': 'baseline' if target is None else ('correct_target' if target == source['correct_answer'] else 'incorrect_target'),
            'change_group': change_group(review),
            **{key: review['baseline_link'][key] for key in ('valid_nonbaseline_pair', 'baseline_relative_change', 'target_directed_switch', 'target_switch_with_reasoning')},
            'baseline_status': review['baseline_link']['status'],
            'baseline_answer': review['baseline_link']['answer'],
            'baseline_record_id': review['baseline_link']['record_id'],
            'issues': ';'.join(review['issues'])})
    return result, long_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--review', type=Path, action='append', required=True)
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    require(not args.out_dir.exists(), 'Use a new summary directory; do not overwrite evidence')
    require(not args.out_dir.resolve().is_relative_to((PROJECT/'artifacts').resolve()), 'Summary belongs outside raw artifacts')
    manifest, seal, rows, validator = load_prepared(args.manifest)
    reviews, files, missing, reread = validate_review_files(args.review, manifest, seal, rows, validator)
    summary, long_rows = summarize(rows, reviews)
    result = {'schema': 'phase3-ai-descriptive-counts-v1', 'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'source_sha256': manifest['source']['sha256'], 'protocol_sha256': manifest['protocol']['sha256'],
        'partition_manifest_sha256': seal, 'review_files': files, 'summary_code_sha256': sha(Path(__file__)),
        'cohorts': summary, 'primary_annotation_coverage_complete': True,
        'second_pass_status': 'See separately source-bound context-check/adjudication evidence; not certified by this counting tool.',
        'human_labels_created': 0, 'inference_or_judge_calls': 0,
        'limitations': ['Unblinded AI descriptive annotations, not validated faithfulness or human accuracy.',
          'Full-read attestations and structural checks do not independently prove comprehension.',
          'Change groups use baseline/current pair validity, not baseline/vector/random triple validity.',
          'Empty reasoning is not an acknowledgment failure; content-only claims remain separate.',
          'Repeated conditions and overlapping cohorts are not independent replications.']}
    args.out_dir.mkdir(parents=True)
    (args.out_dir/'summary.json').write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
    with (args.out_dir/'record_summary.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(long_rows[0]));writer.writeheader();writer.writerows(long_rows)
    lines = ['# Descriptive AI review counts', '', 'Counts of source-bound annotations; no human labels or validated faithfulness score.', '']
    for cohort, data in summary.items():
        lines += ['## '+cohort.replace('_', ' '), '', '| Category | All | Baseline | Vector | Random |', '|---|---:|---:|---:|---:|']
        for category in CATEGORIES:
            vals = [data['all']['categories'][category]]+[data['by_direction'][d]['categories'][category] for d in ('baseline', 'vector', 'random')]
            lines.append('| '+category+' | '+' | '.join(map(str, vals))+' |')
        lines += ['', '| Category | Vector target switches | Random target switches | Other vector changes | Other random changes |', '|---|---:|---:|---:|---:|']
        groups=data['changed_answer_groups']
        lines.append('| Eligible records | '+' | '.join(str(groups[g]['all']['records']) for g in CHANGE_GROUPS)+' |')
        for category in CATEGORIES:
            lines.append('| '+category+' | '+' | '.join(str(groups[g]['all']['categories'][category]) for g in CHANGE_GROUPS)+' |')
        lines += ['', 'All quality flags, claim-channel counts, correct/incorrect-target strata, denominators and record IDs are in `summary.json`; `record_summary.csv` preserves every record.', '']
    lines += ['The separate context-check record must accompany these primary-annotation counts. This script does not establish second-reader completion or adjudicate semantic disagreements.', '']
    (args.out_dir/'REPORT.md').write_text('\n'.join(lines))
    for item in files:
        require(sha(PROJECT/item['path']) == item['sha256'], 'Review changed while counting')
    (args.out_dir/'checksums.sha256').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in sorted(args.out_dir.iterdir())))
    print(f'Summarized {len(reviews)} validated AI annotations; no semantic labels created.')

if __name__ == '__main__':
    main()
