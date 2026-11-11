"""Synthetic failure tests for the offline audit; no model or network access."""
from copy import deepcopy
import base64
import gzip
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
    ORIGINAL_COMMIT, CHECKPOINT_COMMIT, audit_second_checkpoint, snapshot_payloads)


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


class SecondCheckpointTests(unittest.TestCase):
    def fixture(self, directory):
        project = Path(directory)
        root = project/'artifacts/pilot-20-phase3-v1'
        checkpoint = project/'artifacts/pilot-20-phase3-checkpoint-0430'
        second = project/'artifacts/pilot-20-phase3-checkpoint-1110'
        metadata = project/'artifacts/pilot-20-phase3-resume-notebook-SYNTHETIC'
        for path in [root, checkpoint, second, metadata, project/'docs']:path.mkdir(parents=True)
        rows = []
        for i in range(198):
            start = (datetime(2026,11,10,4,0,tzinfo=timezone.utc)+timedelta(minutes=i) if i<8 else
                     datetime(2026,11,10,10,40,tzinfo=timezone.utc)+timedelta(minutes=i-8) if i<28 else
                     datetime(2026,11,11,1,0,tzinfo=timezone.utc)+timedelta(minutes=i-28))
            rows.append(dict(record_id=f'SYNTHETIC-ONLY-{i}',question_id=f'q{i//33}',started_at=start.isoformat(),
                             finished_at=(start+timedelta(seconds=30)).isoformat()))
        encode = lambda selected: ''.join(json.dumps(row)+'\n' for row in selected).encode()
        raw8,raw28,raw198=encode(rows[:8]),encode(rows[:28]),encode(rows)
        names=['manifest.json','plan.json','runtime.json','steering.jsonl','vector_metadata.json','vectors.npz','execution.log']
        payloads={}
        for folder in [checkpoint,root]:
            for name in names:
                raw=raw8 if name=='steering.jsonl' and folder==checkpoint else raw28 if name=='steering.jsonl' else ('SYNTHETIC '+name).encode()
                payloads[str((folder/name).relative_to(project))]=raw
        payloads[str((checkpoint/'checkpoint-provenance.json').relative_to(project))]=b'SYNTHETIC checkpoint provenance'
        runtime_name='runtime-resume-SYNTHETIC-first.json'
        payloads[str((root/runtime_name).relative_to(project))]=b'SYNTHETIC first L4 runtime'
        for name in ['setup.json','resume-execution.log']:
            payloads[str((metadata/name).relative_to(project))]=('SYNTHETIC old L4 '+name).encode()
        for name in ['PHASE3_L4_RESUME_ADDENDUM.md','phase3-l4-resume-addendum.json']:
            payloads['docs/'+name]=('SYNTHETIC '+name).encode()
        self.assertEqual(len(payloads),20)
        packed={}
        for name,raw in payloads.items():
            (project/name).write_bytes(raw)
            compressed=gzip.compress(raw,mtime=0)
            packed[name]=dict(encoding='gzip+base64',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                compressed_bytes=len(compressed),compressed_sha256=hashlib.sha256(compressed).hexdigest(),
                base64=base64.b64encode(compressed).decode())
        (root/'steering.jsonl').write_bytes(raw198)
        snapshot=dict(schema='phase3-recovery-snapshot-v1',retained_records=28,original_retained_records=8,
            complete_verified=False,captured_at_utc='2026-11-10T11:10:25+00:00',files=packed)
        acquisition=dict(files={name:item['sha256'] for name,item in packed.items()},retained_records=28,
            complete_verified=False,snapshot_captured_at_utc=snapshot['captured_at_utc'],
            acquired_at_utc='2026-11-11T00:36:17+00:00')
        (second/'steering.jsonl').write_bytes(raw28)
        (second/'snapshot.json').write_text(json.dumps(snapshot))
        (second/'acquisition-provenance.json').write_text(json.dumps(acquisition))
        hashes={name:hashlib.sha256((second/name).read_bytes()).hexdigest()
                for name in ['steering.jsonl','snapshot.json','acquisition-provenance.json']}
        original=dict(captured_at='2026-11-10T03:50:00+00:00',gpu_name='Tesla T4')
        resumed=[(runtime_name,dict(captured_at='2026-11-10T10:39:00+00:00',gpu_name='NVIDIA L4')),
                 ('runtime-resume-SYNTHETIC-second.json',dict(captured_at='2026-11-11T00:59:00+00:00',gpu_name='NVIDIA L4'))]
        lineage=audit_runtime_lineage(rows,original,resumed,'2026-11-10T04:28:00+00:00')
        return project,root,checkpoint,second,metadata,rows,lineage,hashes,snapshot,acquisition

    def test_both_prefixes_all20_payloads_and_8_20_170_lineage_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            project,root,old,new,metadata,rows,lineage,hashes,snapshot,acquisition=self.fixture(directory)
            self.assertEqual([segment['retained_records'] for segment in lineage['segments']],[20,170])
            with patch('scripts.audit_phase3_artifacts.SECOND_CHECKPOINT_HASHES',hashes):
                result,observed=audit_second_checkpoint(root,old,new,rows,lineage,[metadata],project)
            self.assertTrue(result['all20_snapshot_payloads_verified'])
            self.assertTrue(result['exact28_row_byte_prefix_unchanged'])
            self.assertEqual(result['retained_segment_counts'],dict(original_t4=8,first_l4=20,later_l4=170))
            self.assertEqual(len(result['preserved_payloads']),20)
            self.assertIn(metadata/'resume-execution.log',observed)
            self.assertIn('both interruptions',result['historical_attempts'])

    def test_changed28_prefix_old_setup_log_runtime_or_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            project,root,old,new,metadata,rows,lineage,hashes,snapshot,acquisition=self.fixture(directory)
            with patch('scripts.audit_phase3_artifacts.SECOND_CHECKPOINT_HASHES',hashes):
                for path in [root/'steering.jsonl',metadata/'setup.json',metadata/'resume-execution.log',
                             root/'runtime-resume-SYNTHETIC-first.json',new/'snapshot.json']:
                    saved=path.read_bytes();path.write_bytes(b'CHANGED '+saved)
                    with self.subTest(path=path.name):
                        with self.assertRaises(ValueError):audit_second_checkpoint(root,old,new,rows,lineage,[metadata],project)
                    path.write_bytes(saved)
                old_log=metadata/'resume-execution.log';saved=old_log.read_bytes()
                old_log.write_bytes(saved+b'\nSYNTHETIC appended new-session output')
                with self.assertRaisesRegex(ValueError,'Preserved snapshot payload changed'):
                    audit_second_checkpoint(root,old,new,rows,lineage,[metadata],project)
                old_log.write_bytes(saved)
                with self.assertRaisesRegex(ValueError,'metadata directory'):
                    audit_second_checkpoint(root,old,new,rows,lineage,[],project)
                bad=deepcopy(lineage);bad['segments'][0]['record_ids'].append(rows[28]['record_id'])
                with self.assertRaisesRegex(ValueError,'exactly the preserved 20'):
                    audit_second_checkpoint(root,old,new,rows,bad,[metadata],project)

    def test_payload_encoding_hash_and_acquisition_inventory_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            *_,snapshot,acquisition=self.fixture(directory)
            first=next(iter(snapshot['files']))
            for field,value in [('compressed_sha256','0'*64),('sha256','0'*64),('encoding','unknown')]:
                bad=deepcopy(snapshot);bad['files'][first][field]=value
                with self.subTest(field=field):
                    with self.assertRaises(ValueError):snapshot_payloads(bad,acquisition)
            bad_acquisition=deepcopy(acquisition);bad_acquisition['files'].pop(first)
            with self.assertRaisesRegex(ValueError,'inventory differs'):snapshot_payloads(snapshot,bad_acquisition)



if __name__ == '__main__':
    unittest.main()
