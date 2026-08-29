import shutil
import tempfile
import unittest
from pathlib import Path

import topic_snapchat


class TopicWorkflowImagePolicyTests(unittest.TestCase):
    def test_topic_brief_prioritizes_relevant_curated_artifacts_over_reuse_rest(self):
        workflow = Path('.github/workflows/topic.yml').read_text(encoding='utf-8')
        self.assertIn('LIBRARY_REUSE_DAYS: "0"', workflow)

    def test_curated_sama_artifact_is_directly_relevant_to_sama_topic(self):
        wrapped = topic_snapchat._direct_relevance_only(lambda photo, context: 'neutral')
        verdict = wrapped(
            Path('assets/sama-history-hq.jpg'),
            'ساما البنك المركزي السعودي سعر الفائدة والتمويل في السعودية',
        )
        self.assertEqual(verdict, 'yes')

    def test_copied_hero_still_recognizes_curated_sama_artifact(self):
        wrapped = topic_snapchat._direct_relevance_only(lambda photo, context: 'neutral')
        with tempfile.TemporaryDirectory() as td:
            hero = Path(td) / 'hero.jpg'
            shutil.copyfile('assets/sama-history-hq.jpg', hero)
            verdict = wrapped(
                hero,
                'ساما البنك المركزي السعودي سعر الفائدة والتمويل في السعودية',
            )
        self.assertEqual(verdict, 'yes')

    def test_unrelated_curated_artifact_still_rejects_neutral_match(self):
        wrapped = topic_snapchat._direct_relevance_only(lambda photo, context: 'neutral')
        verdict = wrapped(
            Path('assets/old-riyadh-souq.jpg'),
            'ساما البنك المركزي السعودي سعر الفائدة والتمويل في السعودية',
        )
        self.assertEqual(verdict, 'no')


if __name__ == '__main__':
    unittest.main()
