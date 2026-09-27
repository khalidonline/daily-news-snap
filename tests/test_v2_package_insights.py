import unittest
from datetime import datetime, timezone
from publishing_v2.autopilot.package_insights import package_report, measure_performance, inventory_entry

NOW = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)

class PackageInsightsTests(unittest.TestCase):
    def state(self):
        return {'status':'published','started_at':'2026-09-28T08:00:00+00:00',
                'candidate_id':'c1','package':{'title':'عنوان', 'cards':[{'kind':'info'},{'kind':'story'}]},
                'approval':{'package_sha256':'abc','media_sha256':['a','b']},
                'receipt':{'status':'POSTED','post_ids':['p1','p2']},
                'agent_receipts':[{'response_id':'r1','role':'writer','cost_micro_usd':120},
                                  {'response_id':'r1','role':'writer','cost_micro_usd':120},
                                  {'response_id':'r2','role':'card_repair','cost_micro_usd':30}],
                'audit':[], 'expires_at':'2026-09-29T12:00:00+00:00'}

    def test_report_counts_settled_receipts_once_and_does_not_invent_views(self):
        report = package_report(self.state(), 'slot', NOW)
        self.assertEqual(report['settled_cost_micro_usd'],150)
        self.assertEqual(report['cost_by_stage'],{'writer':120,'card_repair':30})
        self.assertEqual(report['repair_calls'],1)
        self.assertEqual(report['performance']['status'],'unavailable')

    def test_metrics_require_matching_post_order_and_window(self):
        data={'source':'Snapchat Insights export','observed_at':NOW.isoformat(),
              'window_start':'2026-09-28T08:00:00+00:00', 'window_end':NOW.isoformat(),
              'cards':[{'post_id':'p1','views':100},{'post_id':'p2','views':65}]}
        report=measure_performance(self.state(),data,NOW)
        self.assertEqual(report['completion_ratio'],.65)
        self.assertEqual(report['sample_age_hours'],4)
        data['cards'].reverse()
        with self.assertRaises(ValueError): measure_performance(self.state(),data,NOW)

    def test_zero_views_and_expired_inventory(self):
        s=self.state(); s['status']='shadow_passed'
        self.assertEqual(inventory_entry(s,'slot',NOW)['status'],'reviewed_requires_revalidation')
        s['expires_at']='2026-09-27T12:00:00+00:00'
        self.assertEqual(inventory_entry(s,'slot',NOW)['status'],'expired')
        s['status']='delivery_pending'
        self.assertEqual(inventory_entry(s,'slot',NOW)['status'],'reconciliation_required')
        s['status']='published'
        self.assertEqual(inventory_entry(s,'slot',NOW)['status'],'published')

class CardSearchTests(unittest.TestCase):
    def test_each_card_queries_its_own_scene_first(self):
        from publishing_v2.autopilot.runtime import Renderer
        class Source:
            recovery = False
            def __init__(self): self.queries=[]
            def images(self, query): self.queries.append(query); return []
        src=Source(); renderer=Renderer(None,src)
        cards=[{'kind':'info','image_query':'airport shop'}, {'kind':'story','image_query':'old bookstall'}]
        package={'cards':cards, 'candidate':{'title':'WHSmith', 'card_image_plan':[
            {'purpose':'المطار', 'queries':['WHSmith airport 1990']},
            {'purpose':'البداية', 'queries':['WHSmith Euston 1848','كشك يوستن']}]}}
        renderer.image_options(cards[1],package)
        self.assertEqual(src.queries[:2],['WHSmith Euston 1848','كشك يوستن'])
        self.assertNotIn('WHSmith airport 1990',src.queries)

    def test_recovery_keeps_entity_separate_from_historical_query(self):
        from publishing_v2.autopilot.runtime import Renderer
        class Source:
            recovery = True
            def __init__(self): self.calls=[]
            def subject_images(self, query, subject): self.calls.append((query,subject)); return []
        src=Source()
        card={'kind':'story','image_query':'old shop'}
        Renderer(None,src).image_options(card,{'cards':[card], 'candidate':{
            'title':'WHSmith', 'resolved_subject':{'name':'WHSmith'},
            'card_image_plan':[{'queries':['WHSmith Euston 1848']}]
        }})
        self.assertEqual(src.calls[0],('WHSmith Euston 1848','WHSmith'))
