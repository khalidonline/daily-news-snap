import tempfile
import unittest
from pathlib import Path

import topic_snapchat


class TopicWorkflowImagePolicyTests(unittest.TestCase):
    def test_topic_brief_prioritizes_relevant_curated_artifacts_over_reuse_rest(self):
        workflow = Path('.github/workflows/topic.yml').read_text(encoding='utf-8')
        self.assertIn('LIBRARY_REUSE_DAYS: "0"', workflow)

    def test_sama_provenance_survives_finance_copy_that_omits_sama_name(self):
        wrapped = topic_snapchat._direct_relevance_only(lambda photo, context: 'neutral')
        with tempfile.TemporaryDirectory() as td:
            candidate = Path(td) / 'hero.auto-local.jpg'
            candidate.write_bytes(b'candidate-image')
            Path(str(candidate) + '.exempt').write_text(
                'local:sama-history-hq.jpg', encoding='utf-8'
            )
            verdict = wrapped(
                candidate,
                '16 سبتمبر: موعد قرار الفائدة القادم\n'
                'التمويل المتغير يعتمد على المؤشر المرجعي وهامش البنك.\n'
                'التسعير المحلي لا يعتمد على قرار واحد.',
            )
        self.assertEqual(verdict, 'yes')

    def test_curated_sama_artifact_is_directly_relevant_to_sama_topic(self):
        wrapped = topic_snapchat._direct_relevance_only(lambda photo, context: 'neutral')
        verdict = wrapped(
            Path('sama-history-hq.jpg'),
            'ساما البنك المركزي السعودي سعر الفائدة والتمويل في السعودية',
        )
        self.assertEqual(verdict, 'yes')

    def test_copied_sama_artifact_keeps_provenance_and_overrides_wrong_no(self):
        wrapped = topic_snapchat._direct_relevance_only(lambda photo, context: 'no')
        with tempfile.TemporaryDirectory() as td:
            candidate = Path(td) / 'hero.auto-local.jpg'
            candidate.write_bytes(b'candidate-image')
            Path(str(candidate) + '.exempt').write_text(
                'local:sama-history-hq.jpg', encoding='utf-8'
            )
            verdict = wrapped(
                candidate,
                'Saudi Central Bank SAMA headquarters Riyadh\nساما',
            )
        self.assertEqual(verdict, 'yes')

    def test_unrelated_copied_artifact_still_respects_visual_no(self):
        wrapped = topic_snapchat._direct_relevance_only(lambda photo, context: 'no')
        with tempfile.TemporaryDirectory() as td:
            candidate = Path(td) / 'hero.auto-local.jpg'
            candidate.write_bytes(b'unrelated-image')
            Path(str(candidate) + '.exempt').write_text(
                'local:old-riyadh-souq.jpg', encoding='utf-8'
            )
            verdict = wrapped(
                candidate,
                'Saudi Central Bank SAMA headquarters Riyadh\nساما',
            )
        self.assertEqual(verdict, 'no')

    def test_unrelated_curated_artifact_still_rejects_neutral_match(self):
        wrapped = topic_snapchat._direct_relevance_only(lambda photo, context: 'neutral')
        verdict = wrapped(
            Path('old-riyadh-souq.jpg'),
            'ساما البنك المركزي السعودي سعر الفائدة والتمويل في السعودية',
        )
        self.assertEqual(verdict, 'no')

    def test_generated_topic_prompt_forbids_visible_text_and_fake_signage(self):
        seen = {}

        def fake_fetcher(prompt, out_path):
            seen['prompt'] = prompt
            Path(out_path).write_bytes(b'image')
            Path(str(out_path) + '.generated').write_text('ai', encoding='utf-8')
            return Path(out_path), 'AI generated'

        wrapped = topic_snapchat._topic_generated_photo(
            fake_fetcher, cleaner=lambda photo: (True, '')
        )
        result = wrapped('Saudi interest rate policy and banking', Path('hero.jpg'))

        self.assertEqual(result[0], Path('hero.jpg'))
        prompt = seen['prompt'].lower()
        for rule in (
            'no visible text',
            'no arabic or english words',
            'no names',
            'no labels',
            'no signs',
            'no logos',
            'no institution names',
            'no fake official signage',
        ):
            self.assertIn(rule, prompt)

    def test_generated_topic_photo_is_blocked_when_second_visual_gate_finds_text(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'hero.jpg'

            def fake_fetcher(prompt, out_path):
                Path(out_path).write_bytes(b'image-with-text')
                Path(str(out_path) + '.generated').write_text('ai', encoding='utf-8')
                return Path(out_path), 'AI generated'

            wrapped = topic_snapchat._topic_generated_photo(
                fake_fetcher,
                cleaner=lambda photo: (False, 'visible Arabic text and signage'),
            )
            self.assertEqual(wrapped('Saudi finance scene', out), (None, None))
            self.assertFalse(out.exists())
            self.assertFalse(Path(str(out) + '.generated').exists())


if __name__ == '__main__':
    unittest.main()
