"""Synthetic second-reader fixtures only; no real labels or full-read claims."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

from scripts.review_phase3_traces import read_lines, recheck_plan, sha, validate_workspace
from scripts.verify_phase3_context_checks import verify_partition, verify_context_checks
from tests import test_review_phase3_traces as synthetic_fixtures


class ContextPartitionTests(unittest.TestCase):
    def setUp(self):
        self.partition = {'partition_id': 'question-01', 'record_ids': ['ordinary', 'loop', 'unused']}
        self.manifest = {'source': {'sha256': 'a'*64}, 'protocol': {'sha256': 'b'*64},
                         'partitions': [self.partition], 'records': [{'record_id': r} for r in self.partition['record_ids']]}
        self.reviews = {rid: {'record_id': rid, 'review_state': 'complete', 'category': category,
            'status': status, 'issues': [], 'outside_nudge_claim_in_reasoning': False,
            'outside_nudge_claim_in_content': False, 'reviewer': {'id': 'synthetic-primary'},
            'reviewed_at_utc': '2026-01-01T01:00:00+00:00'}
            for rid, category, status in [('ordinary', 'ordinary_reasoning', 'ok'),
                ('loop', 'incoherent', 'truncated'), ('unused', 'ordinary_reasoning', 'invalid_answer')]}
        self.seal = 'c'*64
        self.primary = {'path': '/synthetic-primary.jsonl', 'sha256': 'd'*64}
        self.plan = recheck_plan(self.manifest, self.reviews)
        self.assignment = {'schema': 'phase3-ai-context-check-assignment-v1', 'partition_id': 'question-01',
            'created_at_utc': '2026-01-01T02:00:00Z', 'source_sha256': 'a'*64, 'protocol_sha256': 'b'*64,
            'partition_manifest_sha256': self.seal, 'primary_review_path': self.primary['path'],
            'primary_review_sha256': self.primary['sha256'], 'mandatory_ids': ['loop'],
            'spotcheck': self.plan['second_ai_spotchecks'][0], 'record_ids': ['ordinary', 'loop']}
        self.checks = [{'record_id': rid, 'source_sha256': 'a'*64, 'partition_manifest_sha256': self.seal,
            'primary_review_sha256': 'd'*64, 'reviewer_id': 'synthetic-second',
            'reviewed_at_utc': '2026-01-01T03:00:00Z', 'full_read': dict(messages=True, reasoning=True, content=True),
            'agrees_with_primary': True, 'observed_category': self.reviews[rid]['category'],
            'outside_nudge_claim_in_reasoning': False, 'outside_nudge_claim_in_content': False,
            'notes': 'Synthetic test attestation only.', 'suggested_changes': {}} for rid in ['ordinary', 'loop']]

    def verify(self):
        return verify_partition(self.assignment, self.checks, self.partition, self.manifest,
            self.seal, self.reviews, self.primary, self.plan, datetime(2026, 1, 2, tzinfo=timezone.utc))

    def test_final_selection_counts_overlapping_mandatory_and_spotcheck_once(self):
        result = self.verify()
        self.assertEqual((result['mandatory_records'], result['selected_records'], result['checked_records']), (1, 2, 2))
        self.assertEqual(result['spotcheck_roles'], 2)
        self.assertEqual(result['second_reviewer_ids'], ['synthetic-second'])
        self.assignment['record_ids'].append('unused')
        with self.assertRaisesRegex(ValueError, 'selection'): self.verify()

    def test_missing_duplicate_and_unexpected_ids_rejected(self):
        original = deepcopy(self.checks)
        for bad in [original[:1], original+[original[0]], original+[dict(original[0], record_id='unused')]]:
            with self.subTest(ids=[x['record_id'] for x in bad]):
                self.checks = bad
                with self.assertRaisesRegex(ValueError, 'record IDs'): self.verify()

    def test_wrong_hash_or_same_reader_rejected(self):
        for key in ('source_sha256', 'partition_manifest_sha256', 'primary_review_sha256'):
            with self.subTest(key=key):
                original = self.checks[0][key]; self.checks[0][key] = 'f'*64
                with self.assertRaisesRegex(ValueError, 'mismatch'): self.verify()
                self.checks[0][key] = original
        self.assignment['protocol_sha256'] = 'f'*64
        with self.assertRaisesRegex(ValueError, 'protocol_sha256'): self.verify()
        self.assignment['protocol_sha256'] = 'b'*64
        self.checks[0]['reviewer_id'] = 'synthetic-primary'
        with self.assertRaisesRegex(ValueError, 'Second reader'): self.verify()

    def test_false_or_integer_read_attestation_and_empty_notes_rejected(self):
        for value in (False, 1, None):
            self.checks[0]['full_read']['content'] = value
            with self.assertRaisesRegex(ValueError, 'full-read'): self.verify()
        self.checks[0]['full_read']['content'] = True
        self.checks[0]['notes'] = '  '
        with self.assertRaisesRegex(ValueError, 'nonempty'): self.verify()

    def test_pre_assignment_pre_primary_future_and_non_utc_times_rejected(self):
        for stamp in ('2026-01-01T01:30:00Z', '2026-01-01T00:30:00Z',
                      '2026-01-03T00:00:00Z', '2026-01-01T03:00:00', '2026-01-01T04:00:00+01:00'):
            with self.subTest(timestamp=stamp):
                self.checks[0]['reviewed_at_utc'] = stamp
                with self.assertRaises(ValueError): self.verify()
        self.checks[0]['reviewed_at_utc'] = '2026-01-01T03:00:00Z'
        self.reviews['ordinary']['reviewed_at_utc'] = '2026-01-01T04:00:00Z'
        with self.assertRaisesRegex(ValueError, 'timestamp'): self.verify()

    def test_inconsistent_agreement_rejected_including_null_claim_flags(self):
        for changes in ({'observed_category': 'ambiguous'}, {'outside_nudge_claim_in_reasoning': None},
                        {'outside_nudge_claim_in_content': True}, {'suggested_changes': {'issues': ['other']}}):
            saved = deepcopy(self.checks[0]);self.checks[0].update(changes)
            with self.assertRaisesRegex(ValueError, 'Agreement contradicts'): self.verify()
            self.checks[0] = saved

    def test_real_flagged_disagreement_is_preserved_not_adjudicated(self):
        self.checks[1].update(agrees_with_primary=False, observed_category='ambiguous',
            outside_nudge_claim_in_reasoning=None,
            notes='Synthetic disagreement: uncertain attribution in full context.',
            suggested_changes={'category': 'ambiguous', 'reason': 'Synthetic uncertainty.'})
        result = self.verify()
        self.assertEqual(result['unresolved_disagreements'], [self.checks[1]])
        self.assertEqual(self.reviews['loop']['category'], 'incoherent')


class CompleteContextWorkspaceTests(unittest.TestCase):
    def setUp(self):
        # Reuse only the existing synthetic fixture setup, not its test methods.
        self.fixture = synthetic_fixtures.PreparedWorkspaceTests(methodName='runTest')
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.paths = f.review_files()
        self.coverage_dir = f.base/'coverage'
        self.coverage = validate_workspace(f.manifest_path, self.paths, self.coverage_dir)
        self.coverage_path = self.coverage_dir/'coverage.json'
        reviews = {r['record_id']: r for p in self.paths for r in read_lines(p)}
        plan = recheck_plan(f.manifest, reviews)
        for partition, primary_file in zip(f.manifest['partitions'], self.coverage['review_files']):
            pid = partition['partition_id']; d = f.out/'second-pass'/pid;d.mkdir(parents=True)
            assignment = {'schema': 'phase3-ai-context-check-assignment-v1', 'partition_id': pid,
                'created_at_utc': datetime.now(timezone.utc).isoformat(),
                'source_sha256': f.manifest['source']['sha256'], 'protocol_sha256': f.manifest['protocol']['sha256'],
                'partition_manifest_sha256': f.manifest_sha, 'primary_review_path': primary_file['path'],
                'primary_review_sha256': primary_file['sha256'],
                'record_ids': [r for r in partition['record_ids'] if r in plan['combined_full_text_export_ids']],
                'mandatory_ids': [r for r in partition['record_ids'] if r in plan['mandatory_context_recheck_ids']],
                'spotcheck': next(x for x in plan['second_ai_spotchecks'] if x['partition_id'] == pid)}
            (d/'assignment.json').write_text(json.dumps(assignment)+'\n')
            checks = [dict(record_id=rid, source_sha256=assignment['source_sha256'],
                partition_manifest_sha256=f.manifest_sha, primary_review_sha256=primary_file['sha256'],
                reviewer_id='synthetic-second', reviewed_at_utc=datetime.now(timezone.utc).isoformat(),
                full_read=dict(messages=True, reasoning=True, content=True), agrees_with_primary=True,
                observed_category=reviews[rid]['category'], outside_nudge_claim_in_reasoning=False,
                outside_nudge_claim_in_content=False, notes='Synthetic fixture only, not actual reading.',
                suggested_changes={}) for rid in assignment['record_ids']]
            (d/'checks.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in checks))

    def test_complete_primary_required_and_disagreement_prevents_completion(self):
        f = self.fixture; out = f.base/'completion.json'
        result = verify_context_checks(f.out, self.coverage_path, out)
        self.assertTrue(result['full_review_process_complete'])
        self.assertEqual(result['complete_primary_reviews'], 198)
        self.assertEqual(result['primary_coverage']['sha256'], sha(self.coverage_path))
        with self.assertRaisesRegex(ValueError, 'fresh'): verify_context_checks(f.out, self.coverage_path, out)
        with self.assertRaisesRegex(ValueError, 'artifact'): verify_context_checks(f.out, self.coverage_path, f.root/'bad.json')
        checks_path = f.out/'second-pass/question-01/checks.jsonl'
        checks = read_lines(checks_path); checks[0].update(agrees_with_primary=False,
            notes='Synthetic issue disagreement; keep original category and preserve this concern.',
            suggested_changes={'issues': ['unsupported_reasoning'], 'reason': 'Synthetic issue concern.'})
        checks_path.write_text(''.join(json.dumps(x)+'\n' for x in checks))
        disputed = verify_context_checks(f.out, self.coverage_path, f.base/'disputed.json')
        self.assertFalse(disputed['full_review_process_complete'])
        self.assertTrue(disputed['second_reader_coverage_complete'])
        self.assertEqual(disputed['unresolved_disagreement_count'], 1)
        self.paths[-1].unlink()
        with self.assertRaisesRegex(ValueError, '198 complete'): verify_context_checks(f.out, self.coverage_path, f.base/'missing.json')

    def test_stale_primary_coverage_cannot_certify_current_checks(self):
        self.coverage['review_files'][0]['sha256'] = 'f'*64
        self.coverage_path.write_text(json.dumps(self.coverage)+'\n')
        out = self.fixture.base/'stale.json'
        with self.assertRaisesRegex(ValueError, 'stale'): verify_context_checks(self.fixture.out, self.coverage_path, out)
        self.assertFalse(out.exists())


if __name__ == '__main__': unittest.main()
