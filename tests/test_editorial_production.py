import copy, tempfile, unittest
from pathlib import Path
from importlib.util import find_spec

class ProductionTests(unittest.TestCase):
    def test_general_feedback_does_not_crash_unrelated_candidate(self):
        from publishing_v2.autopilot.feedback import rejected_trigger
        self.assertFalse(rejected_trigger({'id':'fresh-shop','title':'shop','url':'https://example.com/a'}))

    def test_failed_text_review_never_reaches_design(self):
        self.assertIsNotNone(find_spec('publishing_v2.editorial_production'))
        from publishing_v2.editorial_production import approve_text, require_text_approval
        p={'title':'subject','cards':[{'kind':'info','title':'fact','body':'body'}], 'sources':[{'text':'source'}]}
        class Agent:
            def run(self,*args,**kwargs): return {'checks':{'timely':False},'repair_indices':[0],'reason':'stale'}
        with self.assertRaises(ValueError): approve_text(p,Agent())
        with self.assertRaises(ValueError): require_text_approval(p)

    def test_approval_is_bound_to_text_and_sources_not_image(self):
        self.assertIsNotNone(find_spec('publishing_v2.editorial_production'))
        from publishing_v2.editorial_production import approve_text,require_text_approval,TEXT_CHECKS
        p={'title':'subject','cards':[{'kind':'info','title':'fact','body':'body'}], 'sources':[{'text':'source'}]}
        class Agent:
            def run(self,*args,**kwargs): return {'checks':dict.fromkeys(TEXT_CHECKS,True),'repair_indices':[],'reason':'verified'}
        approve_text(p,Agent()); p['cards'][0]['image']={'asset_id':'new'};require_text_approval(p)
        p['cards'][0]['body']='changed'
        with self.assertRaises(ValueError): require_text_approval(p)

    def test_patch_cannot_change_unaffected_cards_or_count(self):
        self.assertIsNotNone(find_spec('publishing_v2.editorial_production'))
        from publishing_v2.editorial_production import apply_card_patches
        old={'title':'a','cards':[{'body':'one'},{'body':'two'}]}; snapshot=copy.deepcopy(old)
        revised=apply_card_patches(old,{'patches':[{'index':1,'card':{'body':'fixed'}}]},[1])
        self.assertEqual(revised['cards'][0],old['cards'][0]);self.assertEqual(old,snapshot)
        self.assertEqual(revised['cards'][1]['body'],'fixed')
        with self.assertRaises(ValueError): apply_card_patches(old,{'patches':[{'index':0,'card':{}}]},[1])

    def test_only_changed_card_needs_render_and_tampering_invalidates_cache(self):
        self.assertIsNotNone(find_spec('publishing_v2.editorial_production'))
        from publishing_v2.editorial_production import CardArtifacts
        with tempfile.TemporaryDirectory() as d:
            cache=CardArtifacts(Path(d),'renderer-v1'); paths=[]
            for i in range(2):
                p=Path(d)/f'{i}.jpg';p.write_bytes(bytes([i]));paths.append(p);cache.record(i,{'body':str(i)},p)
            self.assertTrue(cache.reuse(0,{'body':'0'},paths[0]))
            self.assertFalse(cache.reuse(1,{'body':'changed'},paths[1]))
            paths[0].write_bytes(b'tampered');self.assertFalse(cache.reuse(0,{'body':'0'},paths[0]))


class PipelineIntegrationTests(unittest.TestCase):
    def test_rejected_text_is_fixed_before_first_design(self):
        import test_v2_autopilot as f
        from publishing_v2.editorial_production import TEXT_CHECKS
        fixture=f.PipelineTests();fixture.setUp();self.addCleanup(fixture.temp.cleanup)
        original=fixture.agent.run; reviews=[];rendered=[]
        def run(role,data,images=()):
            if role=='text_review':
                fixture.agent.calls.append(role);reviews.append(copy.deepcopy(data))
                good=len(reviews)>1
                return {'checks':dict.fromkeys(TEXT_CHECKS,good),'repair_indices':[] if good else [1],'reason':'Fix second card'}
            if role=='card_repair':
                fixture.agent.calls.append(role);c=copy.deepcopy(data['draft']['cards'][1]);c['body']='قصة واضحة بعد التعديل'
                return {'patches':[{'index':1,'card':c}]}
            return original(role,data,images)
        fixture.agent.run=run;p=fixture.pipeline()
        def render(package,folder):
            self.assertEqual(len(reviews),2)
            rendered.append(copy.deepcopy(package));return fixture.render(package,folder)
        p.render=render;result=p.run('daily','shadow')
        self.assertEqual(result['status'],'shadow_passed')
        self.assertEqual(len(rendered),1);self.assertEqual(fixture.agent.calls.count('writer'),1)
        self.assertEqual(rendered[0]['cards'][0],f.draft()['cards'][0])
        self.assertEqual(rendered[0]['cards'][2],f.draft()['cards'][2])
        events=[r['event'] for r in result['audit']]
        self.assertLess(events.index('text_approved'),events.index('review_passed'))

if __name__=='__main__':unittest.main()

