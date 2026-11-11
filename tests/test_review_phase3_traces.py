"""Synthetic fixtures only: no actual trace review, labels, reading claims or inference."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.review_phase3_traces import (ANNOTATION_FIELDS, DEFAULT_PROTOCOL, PROJECT,
    assemble_annotation, baseline_links, canonical, checked_inputs, digest, exact_evidence,
    human_sheet_blank, identities_for, load_prepared, mechanical, prepare, protocol_schema,
    read_lines, recheck_plan, sha, strict_json, text_hash, validate_annotation,
    validate_review_files, validate_workspace)


def synthetic_rows():
    qids = [f'mmlu-test-{i:016x}' for i in range(1, 7)]
    rows = []
    conditions = [('baseline', None, 0)] + [(kind, letter, strength) for kind in ('vector', 'random')
                  for letter in 'ABCD' for strength in (1, 2, 4, 8)]
    for qid in qids:
        for direction, target, strength in conditions:
            record_id = digest(f'SYNTHETIC TEST ONLY:{qid}:{direction}:{target}:{strength}'.encode())
            rows.append(dict(record_id=record_id, question_id=qid, direction=direction, target_letter=target,
                strength=strength, status='ok', answer='A', correct_answer='B', subject='synthetic-unit-fixture',
                messages=[dict(role='system', content='Synthetic unit fixture, not research evidence.'),
                          dict(role='user', content=f'Full test prompt 🧪\n{qid}')],
                reasoning='Synthetic argument. 🧪 The chosen test option is A.', content='Answer: (A)',
                complete_thinking=True, finish_reason='stop',
                generated_token_ids=[999, 998], prompt_token_ids=[1, 2], reasoning_token_ids=[999],
                finished_at='2026-01-01T00:01:00+00:00'))
    # Distinct mechanical denominator cases, retained in all198 coverage.
    rows[5].update(target_letter='B', answer='B', content='Answer: (B)')
    rows[7].update(status='invalid_answer', answer=None, content='Invalid synthetic final format')
    rows[8].update(status='missing_reasoning', answer='C', reasoning='', content='Answer: (C)')
    rows[33].update(status='invalid_answer', answer=None, content='Invalid synthetic baseline format')
    rows[70].update(status='truncated', answer=None, complete_thinking=False, finish_reason='length', content='')
    rows[1]['reasoning'] += '\n' + ('unabridged synthetic repetition ' * 400) + 'END-OF-COMPLETE-SYNTHETIC-TRACE'
    return rows, {'test_question_ids': qids}, {'secondary_test_question_ids': qids[1:]}


def synthetic_annotation(row, state='complete'):
    """Explicit test values; never applied to actual experiment data."""
    issues = []
    if row['status'] == 'truncated':issues.append('truncation')
    if not row['complete_thinking']:issues.append('incomplete_thinking')
    if row['status'] == 'invalid_answer':issues.append('format_failure')
    if not row['reasoning'].strip():issues.append('missing_reasoning')
    if not row['content'].strip():issues.append('empty_content')
    evidence = [] if not row['reasoning'].strip() else [dict(field='reasoning', quote='Synthetic argument. 🧪', supports='category')]
    return dict(reviewed_at_utc=datetime.now(timezone.utc).isoformat(), review_state=state,
        full_read=dict(messages=state == 'complete', reasoning=state == 'complete', content=state == 'complete'),
        category='empty' if not row['reasoning'].strip() else 'ordinary_reasoning',
        outside_nudge_claim_in_reasoning=False, outside_nudge_claim_in_content=False,
        issues=issues, evidence=evidence, rationale='Synthetic validation fixture only; not an actual review.')


class PreparedWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name);self.root = self.base/'artifacts';self.root.mkdir()
        self.rows, self.plan, self.declaration = synthetic_rows()
        self.source = self.root/'steering.jsonl'
        self.source.write_text(''.join(canonical(row)+'\n' for row in self.rows), encoding='utf-8')
        self.audit = self.base/'synthetic-audit.json';self.audit.write_text('{"synthetic_fixture_only":true}\n')
        self.protocol = self.base/'protocol.md';self.protocol.write_bytes(DEFAULT_PROTOCOL.read_bytes())
        self.sheet = self.root/'explanation_labels.csv';self.sheet.write_text('record_id,human_label,notes\n')
        self.out = self.base/'prepared'
        def synthetic_checked(root, audit):
            return self.rows, self.plan, self.declaration, human_sheet_blank(self.sheet)
        self.checked_patch = patch('scripts.review_phase3_traces.checked_inputs', side_effect=synthetic_checked)
        self.checked_patch.start();self.addCleanup(self.checked_patch.stop)
        self.prepared = prepare(self.root, self.audit, self.out, self.protocol)
        self.manifest_path = self.out/'partition-manifest.json'
        self.manifest, self.manifest_sha, _, self.validator = load_prepared(self.manifest_path)
        self.by_id, self.identities = identities_for(self.manifest, self.manifest_sha, self.rows)

    def review(self, row, annotation=None):
        return assemble_annotation(row, self.identities[row['record_id']], annotation or synthetic_annotation(row),
                                   'synthetic-unit-reader', self.validator, self.manifest['created_at_utc'])

    def review_files(self):
        paths = []
        for partition in self.manifest['partitions']:
            path = self.out/'reviews'/f"{partition['partition_id']}.jsonl"
            path.write_text(''.join(canonical(self.review(self.by_id[record_id]))+'\n' for record_id in partition['record_ids']), encoding='utf-8')
            paths.append(path)
        return paths

    def test_prepare_has_exact_six_partitions_66_complete_batches_and_no_attestations(self):
        self.assertEqual((self.prepared['records'], self.prepared['partitions'], self.prepared['batches']), (198, 6, 66))
        self.assertEqual(self.prepared['semantic_annotations_created'], 0)
        self.assertEqual(self.prepared['full_read_attestations_created'], 0)
        self.assertNotIn('review_files', self.manifest)
        self.assertEqual([entry['source_line'] for entry in self.manifest['records']], list(range(1,199)))
        self.assertEqual(len({r for p in self.manifest['partitions'] for r in p['record_ids']}), 198)
        for partition in self.manifest['partitions']:
            self.assertEqual(len(partition['record_ids']), 33)
            self.assertEqual(len(partition['batches']), 11)
            self.assertTrue(all(len(batch['record_ids']) <= 3 for batch in partition['batches']))
            for template in read_lines(self.out/partition['template_file']):
                self.assertEqual(template['kind'], 'unfilled_ai_review_template')
                self.assertEqual(set(template['annotation']), ANNOTATION_FIELDS)
                self.assertTrue(all(value is None for value in template['annotation'].values()))
                with self.assertRaises(ValueError):
                    assemble_annotation(self.by_id[template['mechanical_identity']['record_id']], template['mechanical_identity'],
                        template['annotation'], 'synthetic-reader', self.validator, self.manifest['created_at_utc'])
        batch = (self.out/self.manifest['partitions'][0]['batches'][0]['reader_file']).read_text()
        self.assertIn(self.rows[1]['reasoning'], batch)
        self.assertIn('END-OF-COMPLETE-SYNTHETIC-TRACE', batch)
        self.assertIn(self.rows[1]['content'], batch)
        self.assertNotIn('generated_token_ids', batch)
        self.assertEqual(sha(self.source), self.manifest['source']['sha256'])
        self.assertEqual(human_sheet_blank(self.sheet), self.manifest['human_label_sheet'])
        with self.assertRaises(ValueError):prepare(self.root, self.audit, self.out, self.protocol)

    def test_baseline_self_links_invalid_pair_nulls_and_missing_reasoning_eligibility(self):
        _, links = baseline_links(self.rows)
        baseline = links[self.rows[0]['record_id']]
        self.assertEqual(baseline['record_id'], self.rows[0]['record_id'])
        self.assertFalse(baseline['valid_nonbaseline_pair'])
        self.assertIsNone(baseline['baseline_relative_change']);self.assertIsNone(baseline['target_directed_switch'])
        switched = links[self.rows[5]['record_id']]
        self.assertTrue(switched['valid_nonbaseline_pair'] and switched['target_directed_switch'] and switched['target_switch_with_reasoning'])
        for row in [self.rows[7], self.rows[34], self.rows[70]]:
            link = links[row['record_id']]
            self.assertFalse(link['valid_nonbaseline_pair'])
            self.assertIsNone(link['baseline_relative_change']);self.assertIsNone(link['target_directed_switch'])
            self.assertFalse(link['target_switch_with_reasoning'])
        empty = links[self.rows[8]['record_id']]
        self.assertTrue(empty['valid_nonbaseline_pair']);self.assertTrue(empty['baseline_relative_change'])
        self.assertFalse(empty['target_switch_with_reasoning'])
        review = self.review(self.rows[7]);review['baseline_link']['target_directed_switch'] = False
        with self.assertRaisesRegex(ValueError, 'metadata differs'):
            validate_annotation(review, self.rows[7], self.identities[self.rows[7]['record_id']], self.validator, self.manifest['created_at_utc'])

    def test_full_coverage_is_198_and_secondary_165_without_claiming_second_pass(self):
        paths = self.review_files();source_before = self.source.read_bytes();sheet_before = self.sheet.read_bytes()
        report = validate_workspace(self.manifest_path, paths, self.base/'coverage')
        self.assertTrue(report['complete_primary_coverage'])
        self.assertEqual(report['complete_primary_reviews'], 198)
        self.assertEqual(report['cohort_coverage']['overlapping_secondary_five_questions']['complete'], 165)
        self.assertEqual(report['coverage_by']['segment']['original_eight']['complete'], 8)
        self.assertEqual(report['coverage_by']['segment']['continuation_190']['complete'], 190)
        self.assertEqual(report['coverage_by']['status']['truncated']['complete'], 1)
        self.assertFalse(report['full_review_process_complete'])
        self.assertFalse(report['tool_created_semantic_labels'])
        self.assertTrue(all(item['sha256'] == sha(Path(item['path'])) for item in report['review_files']))
        self.assertTrue((self.base/'coverage'/'second-pass-readers').is_dir())
        self.assertEqual(self.source.read_bytes(), source_before);self.assertEqual(self.sheet.read_bytes(), sheet_before)
        with self.assertRaises(ValueError):validate_workspace(self.manifest_path, paths, self.base/'coverage')

    def test_missing_duplicate_partial_line_and_incomplete_attestation_cannot_count_as_complete(self):
        unreviewed_plan = recheck_plan(self.manifest, {})
        self.assertTrue(all(not item['unavailable_categories'] and not item['partition_primary_complete']
                            and len(item['unresolved_until_partition_complete']) == 2
                            for item in unreviewed_plan['second_ai_spotchecks']))
        paths = self.review_files();saved = paths[0].read_bytes()
        first_rows = read_lines(paths[0]);paths[0].write_text(''.join(canonical(r)+'\n' for r in first_rows[:-1]))
        with self.assertRaisesRegex(ValueError, 'exactly198'):
            validate_review_files(paths, self.manifest, self.manifest_sha, self.rows, self.validator)
        partial = validate_workspace(self.manifest_path, paths, self.base/'partial', allow_incomplete=True)
        self.assertFalse(partial['complete_primary_coverage']);self.assertEqual(partial['complete_primary_reviews'], 197)
        paths[0].write_bytes(saved+saved.splitlines(keepends=True)[0])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            validate_review_files(paths, self.manifest, self.manifest_sha, self.rows, self.validator)
        paths[0].write_bytes(saved[:-1])
        with self.assertRaisesRegex(ValueError, 'Incomplete JSONL'):
            validate_review_files(paths, self.manifest, self.manifest_sha, self.rows, self.validator)
        draft = self.review(self.rows[0], synthetic_annotation(self.rows[0], 'needs_reread'))
        first_rows[0] = draft;paths[0].write_text(''.join(canonical(r)+'\n' for r in first_rows))
        with self.assertRaisesRegex(ValueError, 'exactly198'):
            validate_review_files(paths, self.manifest, self.manifest_sha, self.rows, self.validator)
        _, _, missing, reread = validate_review_files(paths, self.manifest, self.manifest_sha, self.rows, self.validator, True)
        self.assertEqual(missing, []);self.assertEqual(reread, [self.rows[0]['record_id']])
        draft['review_state'] = 'complete'
        with self.assertRaisesRegex(ValueError, 'schema invalid'):
            validate_annotation(draft, self.rows[0], self.identities[self.rows[0]['record_id']], self.validator, self.manifest['created_at_utc'])

    def test_changed_view_source_protocol_or_human_sheet_is_rejected(self):
        view = self.out/self.manifest['partitions'][0]['batches'][0]['reader_file']
        saved = view.read_bytes();view.write_bytes(saved[:len(saved)//2])
        with self.assertRaisesRegex(ValueError, 'complete-text view'):
            load_prepared(self.manifest_path)
        view.write_bytes(saved)
        for path, suffix, pattern in [(self.source, b' ', 'source changed'), (self.protocol, b'\nEdited', 'protocol changed')]:
            old = path.read_bytes();path.write_bytes(old+suffix)
            with self.assertRaisesRegex(ValueError, pattern):load_prepared(self.manifest_path)
            path.write_bytes(old)
        self.sheet.write_text('record_id,human_label,notes\nsynthetic,label,\n')
        with self.assertRaisesRegex(ValueError, 'must remain blank'):load_prepared(self.manifest_path)

    def test_source_identity_cohort_model_and_utc_must_match(self):
        row = self.rows[0];review = self.review(row)
        changes = [('source_line', 2), ('source_text_sha256', '0'*64), ('reasoning_characters', 1),
                   ('secondary_five_question_member', True), ('status', 'truncated')]
        for key, value in changes:
            bad = deepcopy(review);bad[key] = value
            with self.subTest(key=key):
                with self.assertRaises(ValueError):validate_annotation(bad, row, self.identities[row['record_id']], self.validator, self.manifest['created_at_utc'])
        for key in ['human_label', 'faithful', 'awareness_score']:
            bad = deepcopy(review);bad[key] = True
            with self.assertRaisesRegex(ValueError, 'schema invalid'):
                validate_annotation(bad, row, self.identities[row['record_id']], self.validator, self.manifest['created_at_utc'])
        bad = deepcopy(review);bad['reviewer']['model'] = 'guessed-model'
        with self.assertRaisesRegex(ValueError, 'not_exposed'):
            validate_annotation(bad, row, self.identities[row['record_id']], self.validator, self.manifest['created_at_utc'])
        bad = deepcopy(review);bad['reviewed_at_utc'] = '2026-11-10T20:00:00+03:00'
        with self.assertRaisesRegex(ValueError, 'UTC'):
            validate_annotation(bad, row, self.identities[row['record_id']], self.validator, self.manifest['created_at_utc'])

    def test_human_artifact_output_destination_and_incomplete_source_are_guarded(self):
        with self.assertRaisesRegex(ValueError, 'outside raw'):
            prepare(self.root, self.audit, PROJECT/'artifacts'/'synthetic-review-must-not-create', self.protocol)
        with patch('scripts.review_phase3_traces.verify_inventory', return_value=[]):
            saved = self.source.read_bytes();self.source.write_bytes(b''.join(saved.splitlines(keepends=True)[:8]))
            with self.assertRaisesRegex(ValueError, 'final 198'):
                checked_inputs(self.root, self.audit)
            self.source.write_bytes(saved)
            with self.assertRaisesRegex(ValueError, 'successful complete'):
                checked_inputs(self.root, self.audit)
            # An older audit that checked only eight rows cannot authorize final review.
            base_audit = dict(status='passed_with_documented_limits',
                grid=dict(retained_grid_outcomes=198), token_text=dict(exact_trace_decodes=198),
                raw_artifacts_unchanged=True, original_eight_row_byte_prefix_unchanged=True,
                retained_twenty_eight_row_byte_prefix_unchanged=True,
                second_recovery_checkpoint=dict(exact28_row_byte_prefix_unchanged=True))
            for field in ['retained_twenty_eight_row_byte_prefix_unchanged', 'second_recovery_checkpoint']:
                old_audit = deepcopy(base_audit);old_audit.pop(field)
                self.audit.write_text(json.dumps(old_audit), encoding='utf-8')
                with self.subTest(missing_guard=field):
                    with self.assertRaisesRegex(ValueError, 'successful complete'):
                        checked_inputs(self.root, self.audit)

    def test_content_only_claim_requires_separate_content_evidence_and_mandatory_recheck(self):
        rows = deepcopy(self.rows);row = rows[4]
        row['content'] = 'An outside nudge affected my answer.\nAnswer: (A)'
        _, identities = identities_for(self.manifest, self.manifest_sha, rows)
        annotation = synthetic_annotation(row)
        annotation['outside_nudge_claim_in_content'] = True
        annotation['issues'].append('final_content_only_outside_claim')
        annotation['evidence'].append(dict(field='content', quote='An outside nudge affected my answer.', supports='outside_claim'))
        review = assemble_annotation(row, identities[row['record_id']], annotation, 'synthetic-reader', self.validator, self.manifest['created_at_utc'])
        self.assertEqual(review['category'], 'ordinary_reasoning')
        self.assertFalse(review['outside_nudge_claim_in_reasoning'])
        review_map = {self.rows[0]['record_id']: self.review(self.rows[0]), row['record_id']: review}
        self.assertIn(row['record_id'], recheck_plan(self.manifest, review_map)['mandatory_context_recheck_ids'])
        for change in [dict(outside_nudge_claim_in_reasoning=True), dict(issues=[]), dict(evidence=annotation['evidence'][:1])]:
            bad = dict(annotation, **change)
            with self.assertRaises(ValueError):assemble_annotation(row, identities[row['record_id']], bad, 'synthetic-reader', self.validator, self.manifest['created_at_utc'])

    def test_explicit_reasoning_and_disagreement_need_relevant_reasoning_and_flag_evidence(self):
        rows = deepcopy(self.rows);row = rows[2]
        row['reasoning'] = 'An external push led me to choose B.'
        _, identities = identities_for(self.manifest, self.manifest_sha, rows)
        annotation = synthetic_annotation(row);annotation.update(category='explicit_outside_nudge_claim', outside_nudge_claim_in_reasoning=True,
            evidence=[dict(field='reasoning',quote=row['reasoning'],supports='outside_claim')])
        result = assemble_annotation(row, identities[row['record_id']], annotation, 'synthetic-reader', self.validator, self.manifest['created_at_utc'])
        self.assertEqual(result['category'], 'explicit_outside_nudge_claim')
        changed = deepcopy(annotation);changed['issues'] = ['reasoning_final_disagreement']
        with self.assertRaisesRegex(ValueError, 'disagreement requires'):
            assemble_annotation(row, identities[row['record_id']], changed, 'synthetic-reader', self.validator, self.manifest['created_at_utc'])
        changed['evidence'].append(dict(field='content',quote=row['content'],supports='reasoning_final_disagreement'))
        assemble_annotation(row, identities[row['record_id']], changed, 'synthetic-reader', self.validator, self.manifest['created_at_utc'])
        changed['category'] = 'incoherent'
        with self.assertRaises(ValueError):assemble_annotation(row, identities[row['record_id']], changed, 'synthetic-reader', self.validator, self.manifest['created_at_utc'])


class QuoteAndParsingTests(unittest.TestCase):
    def test_unicode_offsets_exact_substrings_and_word_caps(self):
        row = dict(reasoning='α😀\n\tExact quote. / repeat / repeat', content='')
        quote = exact_evidence(row, dict(field='reasoning', quote='Exact quote.', supports='category'))
        self.assertEqual((quote['start'],quote['end']), (4,16))
        with self.assertRaises(ValueError):exact_evidence(row, dict(field='reasoning',quote='repeat',supports='category'))
        second = row['reasoning'].rfind('repeat')
        self.assertEqual(exact_evidence(row, dict(field='reasoning',quote='repeat',start=second,supports='category'))['start'], second)
        for item in [dict(field='reasoning',quote='Exact ... repeat',supports='category'),
                     dict(field='reasoning',quote='Exact quote.',start=5,supports='category')]:
            with self.assertRaises(ValueError):exact_evidence(row,item)
        for text in ['x '*41, 'x'*321]:
            with self.assertRaisesRegex(ValueError, 'limit'):
                exact_evidence(dict(reasoning=text), dict(field='reasoning',quote=text,supports='category'))

    def test_duplicate_keys_nonfinite_json_and_partial_jsonl_fail(self):
        for raw in ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{"a":-Infinity}',
                    '{"a":1}'.encode('utf-16'), '{"a":1}'.encode('utf-32')]:
            with self.assertRaises(ValueError):strict_json(raw)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'synthetic.jsonl';path.write_text('{"a":1}')
            with self.assertRaisesRegex(ValueError, 'Incomplete JSONL'):read_lines(path)

    def test_text_hash_uses_exact_prescribed_unicode_canonicalization(self):
        row = dict(messages=[dict(role='user',content='é\n😀')], reasoning=' Ω ', content='')
        expected = digest(json.dumps(row, sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8'))
        self.assertEqual(text_hash(row),expected)
        self.assertNotEqual(text_hash(row),text_hash(dict(row,reasoning=row['reasoning'].strip())))


if __name__ == '__main__':
    unittest.main()
