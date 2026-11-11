"""Synthetic review-counting fixtures; no real research labels or reading claims."""
import unittest
from scripts.summarize_phase3_reviews import change_group, summarize


def fixture(identity, direction='vector', switch=True, changed=True, pair=True, category='ordinary_reasoning', reasoning_claim=False, content_claim=False):
    return {'record_id':identity, 'source_line':1, 'question_id':'synthetic', 'direction':direction,
      'target_letter':'B', 'strength':1, 'status':'ok', 'answer':'B', 'category':category,
      'secondary_five_question_member':True, 'outside_nudge_claim_in_reasoning':reasoning_claim,
      'outside_nudge_claim_in_content':content_claim, 'issues':[],
      'baseline_link':{'record_id':'baseline-id','status':'ok','answer':'A','valid_nonbaseline_pair':pair,
        'baseline_relative_change':changed,'target_directed_switch':switch,'target_switch_with_reasoning':switch is True}}


class ReviewCountingTests(unittest.TestCase):
    def test_invalid_and_baseline_never_enter_change_denominators(self):
        self.assertIsNone(change_group(fixture('invalid', pair=False, switch=None, changed=None)))
        self.assertIsNone(change_group(fixture('base', direction='baseline')))
        self.assertIsNone(change_group(fixture('unchanged', switch=False, changed=False)))

    def test_target_switches_and_other_changes_are_disjoint(self):
        data=[fixture('v'), fixture('r', direction='random'), fixture('ov', switch=False), fixture('orr',direction='random',switch=False)]
        self.assertEqual([change_group(x) for x in data], ['vector_target_switch','random_target_switch','other_vector_change','other_random_change'])

    def test_cohorts_and_correct_target_strata_preserve_identity(self):
        a=fixture('current-a');b=fixture('current-b');b['secondary_five_question_member']=False
        rows=[{'record_id':'current-a','correct_answer':'B'},{'record_id':'current-b','correct_answer':'C'}]
        result, long=summarize(rows,{x['record_id']:x for x in [a,b]})
        self.assertEqual(result['primary_six_questions']['all']['records'],2)
        self.assertEqual(result['secondary_five_questions']['all']['records'],1)
        groups=result['primary_six_questions']['changed_answer_groups']['vector_target_switch']
        self.assertEqual(groups['correct_target']['records'],1)
        self.assertEqual(groups['incorrect_target']['records'],1)
        self.assertEqual(long[0]['record_id'],'current-a')
        self.assertEqual(long[0]['baseline_record_id'],'baseline-id')
        self.assertEqual(long[0]['answer'],'B')
        self.assertEqual(long[0]['baseline_answer'],'A')

    def test_content_only_and_ambiguous_claims_not_merged(self):
        a=fixture('a',content_claim=True);b=fixture('b', reasoning_claim=None, content_claim=True, category='ambiguous')
        result,_=summarize([{'record_id':x,'correct_answer':'B'} for x in ['a','b']],{'a':a,'b':b})
        counts=result['primary_six_questions']['all']
        self.assertEqual(counts['reasoning_outside_claim'],{'true':0,'false':1,'none':1})
        self.assertEqual(counts['content_outside_claim']['true'],2)
        self.assertEqual(counts['content_only_explicit_claims'],1)

if __name__=='__main__': unittest.main()
