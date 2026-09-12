import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from publishing_v2.evaluate import Ledger, run, validate_package, load_cases


def valid(case):
    facts = [(s['id'], f['id']) for s in case['sources'] for f in s['facts']]
    frames = [{'text': 'نص عربي للتقييم', 'claims': [{'source_id': s, 'fact_id': f}], 'image_query': 'documented subject'} for s, f in facts[:8]]
    return {'event_id': case['id'], 'historical_replay': True, 'info': {'title': 'معلومة', 'frames': frames[:1]}, 'topic': {'title': 'موضوع', 'frames': frames[1:2]}, 'story': {'title': 'قصة', 'frames': frames[2:8]}}

class EvaluationTests(unittest.TestCase):
    def test_offline_never_calls_provider_and_has_no_winner(self):
        with tempfile.TemporaryDirectory() as d, patch('publishing_v2.evaluate.check_access', side_effect=AssertionError), patch('publishing_v2.evaluate.generate', side_effect=AssertionError):
            report = run('offline', Path(d), env={})
            self.assertEqual(report['status'], 'offline_ready')
            self.assertIsNone(report['winner'])
            self.assertFalse(report['editorial_approved'])

    def test_missing_credentials_not_complete(self):
        with tempfile.TemporaryDirectory() as d:
            report = run('models', Path(d), env={}, allow_paid=True)
            self.assertEqual(report['status'], 'incomplete')
            self.assertTrue(all(x['status'] == 'missing_credentials' for x in report['results']))

    def test_paid_requires_explicit_flag(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError): run('models', Path(d), env={})

    def test_structural_validation(self):
        case = load_cases()[0]
        payload = valid(case)
        self.assertEqual(validate_package(payload, case), [])
        for mutate in [lambda p:p['story']['frames'].pop(), lambda p:p.update(event_id='wrong'), lambda p:p['topic']['frames'].__setitem__(0, p['info']['frames'][0]), lambda p:p['info']['frames'][0]['claims'][0].update(source_id='invented')]:
            broken = copy.deepcopy(payload); mutate(broken)
            self.assertTrue(validate_package(broken, case))
        for bad in [None, [], {}, {'event_id':case['id'], 'info':None}]:
            self.assertTrue(validate_package(bad,case))

    def test_ledger_does_not_reset_and_unknown_stays_reserved(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'spend.sqlite'
            a = Ledger(path)
            self.assertTrue(a.reserve('a', 9))
            b = Ledger(path)
            self.assertFalse(b.reserve('a', 1))
            self.assertFalse(b.reserve('b', 2))
            self.assertEqual(b.total(),9)
            with self.assertRaises(ValueError): b.settle('a', {'input_tokens':-1,'output_tokens':0},'openai')
            self.assertEqual(b.total(),9)

    def test_success_checkpoints_and_rerun_does_not_regenerate(self):
        with tempfile.TemporaryDirectory() as d:
            cases=load_cases()
            responses=[{'text':json.dumps(valid(c)), 'usage':{'input_tokens':100,'output_tokens':100}, 'response_id':'r', 'model':'gpt-6-astra','elapsed_ms':1} for c in cases]
            with patch('publishing_v2.evaluate.generate',side_effect=responses) as gen:
                report=run('models',Path(d),env={'OPENAI_API_KEY':'dummy'},allow_paid=True)
                self.assertEqual(gen.call_count,3)
                self.assertEqual(report['status'],'incomplete')
                self.assertEqual(len(list(Path(d).glob('*response.json'))),3)
                self.assertIsNone(report['winner'])
            with patch('publishing_v2.evaluate.generate',side_effect=AssertionError):
                run('models',Path(d),env={'OPENAI_API_KEY':'dummy'},allow_paid=True)

    def test_checkpoint_failure_stops_further_paid_calls(self):
        from publishing_v2.evaluate import _save
        def fail_response(path,value,env):
            if path.name.endswith('response.json'): raise OSError('disk full')
            return _save(path,value,env)
        with tempfile.TemporaryDirectory() as d, patch('publishing_v2.evaluate._save',side_effect=fail_response), patch('publishing_v2.evaluate.generate',return_value={'text':'{}','usage':{'input_tokens':1,'output_tokens':1}}) as gen:
            report=run('models',Path(d),env={'OPENAI_API_KEY':'dummy'},allow_paid=True)
            self.assertEqual(gen.call_count,1)
            self.assertEqual(report['results'][0]['status'],'checkpoint_failed_stop')

    def test_redaction_before_json_encoding(self):
        from publishing_v2.evaluate import _save
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'data.json'
            secret='key-with-"-and-\\-characters'
            _save(path,{'text':secret}, {'OPENAI_API_KEY':' '+secret+' '})
            self.assertEqual(json.loads(path.read_text())['text'],'[REDACTED]')

    def test_missing_provider_can_be_added_without_repeating_first(self):
        with tempfile.TemporaryDirectory() as d:
            cases=load_cases()
            responses=[{'text':json.dumps(valid(c)), 'usage':{'input_tokens':100,'output_tokens':100}, 'response_id':'r','model':'model','elapsed_ms':1} for c in cases]
            with patch('publishing_v2.evaluate.generate',side_effect=responses):
                run('models',Path(d),env={'OPENAI_API_KEY':'dummy'},allow_paid=True)
            with patch('publishing_v2.evaluate.generate',side_effect=responses) as gen:
                report=run('models',Path(d),env={'ANTHROPIC_API_KEY':'dummy'},allow_paid=True)
                self.assertEqual(gen.call_count,3)
                self.assertEqual(report['status'],'generated_awaiting_human_review')

    def test_failed_request_remains_reserved_and_safe(self):
        with tempfile.TemporaryDirectory() as d, patch('publishing_v2.evaluate.generate',side_effect=RuntimeError('secret-value')):
            report=run('models',Path(d),env={'OPENAI_API_KEY':'secret-value'},allow_paid=True)
            self.assertGreater(report['reserved_or_spent_usd'],0)
            self.assertNotIn('secret-value',(Path(d)/'report.json').read_text())

if __name__ == '__main__': unittest.main()
