"""Synthetic failure tests for the offline audit; no model or network access."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scripts.audit_phase3_artifacts import (audit_prefix, audit_runtime_lineage, audit_token_text,
    audit_vectors, check_immutable, load_cached_tokenizer, ordered_ids, runtime_changes, audit_hardware_addendum,
    ORIGINAL_COMMIT, CHECKPOINT_COMMIT)


class FakeTokenizer:
    def encode(self, text, add_special_tokens):
        return [151667 if text == '<think>' else 151668]

    def apply_chat_template(self, messages, **kwargs):
        assert kwargs == dict(tokenize=True, add_generation_prompt=True, enable_thinking=True, return_dict=False)
        return [1, 2]

    def decode(self, ids, skip_special_tokens):
        assert skip_special_tokens is True
        values = {100: 'Thought', 101: 'Answer: (A)', 102: 'Answer: (B)', 103: '  ', 104: 'Preamble', 151935: 'Padded'}
        return ''.join(values.get(token, '') for token in ids)


def trace():
    return dict(record_id='synthetic-trace', messages=[dict(role='user', content='synthetic fixture')],
                prompt_token_ids=[1, 2], generated_token_ids=[151667, 100, 151668, 103, 101, 103, 151645],
                reasoning='Thought', content='Answer: (A)', answer='A')


class TokenTextTests(unittest.TestCase):
    def test_exact_adapter_boundaries_and_unclosed_reasoning(self):
        first = trace()
        second = dict(first, record_id='synthetic-unclosed', generated_token_ids=[100, 151935],
                      reasoning='ThoughtPadded', content='')
        result = audit_token_text([first], [first, second], FakeTokenizer())
        self.assertEqual((result['source_prompt_records'], result['exact_trace_decodes']), (1, 2))
        self.assertEqual(result['distinct_prompt_tokenizations'], 1)
        preamble = dict(first, generated_token_ids=[104, *first['generated_token_ids']])
        result = audit_token_text([first], [preamble], FakeTokenizer())
        self.assertEqual(result['substantive_preamble_discarded_by_frozen_adapter_ids'], ['synthetic-trace'])

    def test_text_mutation_and_source_prompt_mismatch_are_rejected(self):
        first = trace()
        for changed in [dict(first, content='Answer: (B)', answer='B'), dict(first, reasoning='Rewritten reasoning')]:
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(ValueError, 'text differs'):
                    audit_token_text([first], [changed], FakeTokenizer())
        with self.assertRaisesRegex(ValueError, 'prompt tokens differ'):
            audit_token_text([dict(first, prompt_token_ids=[1, 3])], [first], FakeTokenizer())

    def test_oov_and_premature_eos_are_rejected(self):
        first = trace()
        for generated in [[151936, 151645], [151667, 151643, 100, 151668, 101, 151645]]:
            with self.subTest(generated=generated):
                with self.assertRaises(ValueError):
                    audit_token_text([first], [dict(first, generated_token_ids=generated)], FakeTokenizer())

    def test_missing_cache_never_falls_back_to_tokenizer_download(self):
        with patch('huggingface_hub.try_to_load_from_cache', return_value=None), \
             patch('transformers.AutoTokenizer.from_pretrained') as loader:
            with self.assertRaisesRegex(ValueError, 'no download fallback'):
                load_cached_tokenizer()
            loader.assert_not_called()


class PrefixTests(unittest.TestCase):
    def test_exact_prefix_order_and_complete_newline_required(self):
        ids = [f'synthetic-{i:03}' for i in range(198)]
        lines = [(json.dumps({'record_id': name, 'synthetic': True}) + '\n').encode() for name in ids]
        original, retained = b''.join(lines[:8]), b''.join(lines)
        self.assertEqual(len(audit_prefix(original, retained, ids)), 198)
        bad = list(lines); bad[8], bad[9] = bad[9], bad[8]
        for changed in [b''.join(bad), retained[:-1], b' ' + retained]:
            with self.subTest(changed=changed[:20]):
                with self.assertRaises(ValueError):audit_prefix(original, changed, ids)

    def test_ordered_grid_has_198_unique_positions(self):
        manifest = {'strengths': [0, 1, 2, 4, 8], 'test_question_ids': [f'q{i}' for i in range(6)]}
        ids = ordered_ids(manifest)
        self.assertEqual(len(ids), 198)
        self.assertEqual(len(set(ids)), 198)
        self.assertNotEqual(ids, ordered_ids(dict(manifest, test_question_ids=list(reversed(manifest['test_question_ids'])))))

    def test_immutable_file_change_rejected(self):
        names = ['manifest.json', 'plan.json', 'runtime.json', 'steering.jsonl', 'vector_metadata.json', 'vectors.npz', 'execution.log']
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); checkpoint = base/'checkpoint'; root = base/'root'
            checkpoint.mkdir();root.mkdir()
            hashes = {}
            for name in names:
                raw = ('Synthetic fixture ' + name).encode()
                for folder in [checkpoint, root]:(folder/name).write_bytes(raw)
                hashes[name] = hashlib.sha256(raw).hexdigest()
            (checkpoint/'checkpoint-provenance.json').write_text(json.dumps(
                dict(files_sha256=hashes, retained_records=8, complete=False,
                     captured_at_utc='2026-11-10T04:28:37.649111+00:00')))
            with patch('scripts.audit_phase3_artifacts.CHECKPOINT_HASHES', hashes), \
                 patch('scripts.audit_phase3_artifacts.CHECKPOINT_PROVENANCE_SHA256',
                       hashlib.sha256((checkpoint/'checkpoint-provenance.json').read_bytes()).hexdigest()):
                check_immutable(root, checkpoint)
                saved_provenance = (checkpoint/'checkpoint-provenance.json').read_bytes()
                altered = json.loads(saved_provenance);altered['captured_at_utc']='2026-11-10T05:00:00+00:00'
                (checkpoint/'checkpoint-provenance.json').write_text(json.dumps(altered))
                with self.assertRaisesRegex(ValueError, 'provenance bytes differ'):
                    check_immutable(root, checkpoint)
                (checkpoint/'checkpoint-provenance.json').write_bytes(saved_provenance)
                (root/'vectors.npz').write_bytes(b'changed synthetic bytes')
                with self.assertRaisesRegex(ValueError, 'Immutable resumed artifact differs'):
                    check_immutable(root, checkpoint)


class VectorTests(unittest.TestCase):
    def test_finite_norm_matched_seeded_controls_and_direction_mutation(self):
        rng = np.random.default_rng(42)
        arrays, norms, targets = {}, {}, {}
        for i, letter in enumerate('ABCD'):
            vector = np.linspace(.1 + i, 1 + i, 2048).astype('float32')
            norm = float(np.linalg.norm(vector)); norms[letter] = norm
            draw = rng.standard_normal(vector.shape).astype('float32')
            arrays['vector_'+letter], arrays['random_'+letter] = vector, draw*norm/np.linalg.norm(draw)
            for j in range(5 if letter == 'C' else 3):targets[f'{letter}{j}'] = letter
        counts = dict(A=3, B=3, C=5, D=3)
        plan = dict(seed=42, assigned_targets=targets, train_question_ids=list(targets), train_target_counts=counts)
        metadata = dict(training_questions_per_letter=counts, vector_norms=norms)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'synthetic-vectors.npz';np.savez(path, **arrays)
            result = audit_vectors(path, metadata, plan)
            self.assertEqual(len(result['arrays']), 4)
            arrays['random_A'] = -arrays['random_A'];np.savez(path, **arrays)
            with self.assertRaisesRegex(ValueError, 'Random direction differs'):
                audit_vectors(path, metadata, plan)
            arrays['vector_B'][0] = np.nan;np.savez(path, **arrays)
            with self.assertRaises(ValueError):audit_vectors(path, metadata, plan)


class LineageTests(unittest.TestCase):
    def fixture(self):
        original = dict(captured_at='2026-11-10T04:12:00+00:00')
        checkpoint = '2026-11-10T04:28:37.649111+00:00'
        resumed = [('runtime-resume-zero.json', dict(captured_at='2026-11-10T09:50:00+00:00')),
                   ('runtime-resume-real.json', dict(captured_at='2026-11-10T10:00:00+00:00'))]
        rows = []
        for i in range(198):
            start = datetime(2026, 11, 10, 4, 13, tzinfo=timezone.utc) + timedelta(minutes=i) if i < 8 else \
                    datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc) + timedelta(minutes=i-8)
            rows.append(dict(record_id=f'synthetic-{i}', started_at=start.isoformat(),
                             finished_at=(start+timedelta(seconds=30)).isoformat()))
        return rows, original, resumed, checkpoint

    def test_original_resumed_and_zero_row_segments_are_distinguished(self):
        rows, original, resumed, checkpoint = self.fixture()
        result = audit_runtime_lineage(rows, original, resumed, checkpoint)
        self.assertEqual((result['original_retained_records'], result['resumed_retained_records']), (8, 190))
        self.assertEqual([x['retained_records'] for x in result['segments']], [0, 190])
        self.assertIsNone(result['historical_total_attempts'])
        self.assertIn('Inferred', result['attribution'])

    def test_gpu_and_critical_distribution_changes_remain_explicit(self):
        old = dict(gpu_name='Tesla T4', installed_packages=['numpy==1.26.4', 'numpy==2.2.6', 'transformers==5.0.0rc3'])
        new = dict(gpu_name='NVIDIA L4', installed_packages=['numpy==2.2.6', 'transformers==5.0.1'])
        changes = runtime_changes(old, new)
        self.assertEqual(changes['gpu_name']['resumed'], 'NVIDIA L4')
        self.assertEqual(changes['critical_package_distributions']['original']['numpy'], ['1.26.4', '2.2.6'])
        rows, original, resumed, checkpoint = self.fixture()
        original.update(old)
        for _, runtime in resumed:runtime.update(new)
        for i, row in enumerate(rows):row['question_id'] = f'q{i//33}'
        lineage = audit_runtime_lineage(rows, original, resumed, checkpoint)
        self.assertEqual(lineage['questions_spanning_gpu_names'], ['q0'])
        self.assertEqual(lineage['question_gpu_names']['q0'], ['NVIDIA L4', 'Tesla T4'])

    def test_l4_declaration_precedes_resume_and_preserves_primary_with_exact_secondary(self):
        rows, original, resumed, checkpoint = self.fixture()
        original['gpu_name'] = 'Tesla T4'
        for _, runtime in resumed:runtime['gpu_name'] = 'NVIDIA L4'
        for i, row in enumerate(rows):row['question_id'] = f'q{i//33}'
        lineage = audit_runtime_lineage(rows, original, resumed, checkpoint)
        manifest = {'test_question_ids': [f'q{i}' for i in range(6)]}
        declaration = dict(allowed_resume_gpu='L4', frozen_at_utc='2026-11-10T09:55:00+00:00',
            primary_test_question_ids=manifest['test_question_ids'], mixed_question_id='q0',
            secondary_exclude_question_ids=['q0'], secondary_test_question_ids=[f'q{i}' for i in range(1,6)],
            primary_retained_grid_outcomes=198, secondary_retained_grid_outcomes=165,
            original_retained_records=8, planned_resumed_records=190,
            scientific_commit=ORIGINAL_COMMIT, checkpoint_commit=CHECKPOINT_COMMIT,
            human_validation=False, outcome_based_selection=False)
        result = audit_hardware_addendum(declaration, rows, manifest, lineage)
        self.assertEqual((result['primary_retained_outcomes'], result['secondary_retained_outcomes']), (198, 165))
        for change in [dict(frozen_at_utc='2026-11-10T10:01:00+00:00'),
                       dict(secondary_exclude_question_ids=['q1']), dict(primary_test_question_ids=['q0']),
                       dict(secondary_retained_grid_outcomes=198)]:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):audit_hardware_addendum(dict(declaration, **change), rows, manifest, lineage)

    def test_missing_late_or_straddled_runtime_and_overlapping_rows_fail(self):
        rows, original, resumed, checkpoint = self.fixture()
        cases = [([], rows), ([('runtime-late.json', dict(captured_at='2026-11-10T10:00:15+00:00'))], rows)]
        overlap = deepcopy(rows);overlap[9]['started_at'] = overlap[8]['started_at']
        cases.append((resumed, overlap))
        straddled = resumed + [('runtime-midrow.json', dict(captured_at='2026-11-10T10:00:15+00:00'))]
        cases.append((straddled, rows))
        for runtime, selected in cases:
            with self.subTest(runtime=runtime):
                with self.assertRaises(ValueError):audit_runtime_lineage(selected, original, runtime, checkpoint)


if __name__ == '__main__':
    unittest.main()
