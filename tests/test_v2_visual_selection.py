import unittest
from publishing_v2.autopilot.runtime import Renderer
import test_v2_autopilot as fixtures


class DistinctVisualTests(unittest.TestCase):
    def test_same_bytes_or_origin_cannot_count_as_different_options(self):
        class Source:
            def subject_images(self, query, subject):
                return [dict(asset_id=ident, title='Jeddah', license='CC0',
                             sha256=sha, origin_key=origin) for ident, sha, origin in [
                    ('a', 'same-bytes', 'photo1'), ('b', 'same-bytes', 'photo2'),
                    ('c', 'resized-bytes', 'photo1'), ('d', 'different', 'photo3')]]
        rows = Renderer(None, Source()).plan_visuals({'resolved_subjects':[{'name':'Jeddah'}]})
        self.assertEqual([row['asset_id'] for row in rows], ['a', 'd'])

    def test_duplicate_photo_across_two_subject_searches_counts_once(self):
        class Source:
            def subject_images(self, query, subject):
                return [dict(asset_id=subject, title='Jeddah Riyadh', license='CC0',
                             sha256='same-photo', origin_key='shared-photo')]
        rows = Renderer(None, Source()).plan_visuals({
            'resolved_subjects':[{'name':'Jeddah'}, {'name':'Riyadh'}]})
        self.assertEqual(len(rows), 1)


class VisualSelectionTests(unittest.TestCase):
    setUp = fixtures.PipelineTests.setUp
    pipeline = fixtures.PipelineTests.pipeline
    render = fixtures.PipelineTests.render
    publish = fixtures.PipelineTests.publish

    def test_only_image_qualified_candidate_is_selected_and_paid_researched(self):
        pipeline = self.pipeline()
        options = [{'asset_id':str(i)} for i in range(3)]
        def render(package, output): return self.render(package, output)
        render.plan_visuals = lambda candidate: options[:1] if candidate['id'] == 'a' else options
        pipeline.render = render
        original, researched = self.agent.run, []
        def run(role, data, images=()):
            if role == 'researcher': researched.append(data['candidate']['id'])
            return original(role, data, images)
        self.agent.run = run
        result = pipeline.run('daily', 'shadow')
        self.assertEqual(result['status'], 'shadow_passed')
        self.assertEqual(researched, ['b'])
        selected = [row for row in result['audit'] if row['event'] == 'selected']
        self.assertEqual([row.get('candidate_id') for row in selected], ['b'])
        self.assertEqual(result['visual_preflight'], {'candidate_id':'b',
                         'asset_ids':['0','1','2'], 'distinct_count':3})

