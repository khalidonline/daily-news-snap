import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from publishing_v2.autopilot import policy, sources


class FactualGroundingTests(unittest.TestCase):
    def validate(self, fact, quote):
        data = {'sensitive': False, 'claims': [dict(id='c1', fact=fact, quote=quote, source_id='s')]}
        policy.validate_research(data, [{'id': 's', 'text': quote}], 'evergreen', datetime.now(timezone.utc))

    def test_year_from_neighboring_text_is_not_supported(self):
        with self.assertRaisesRegex(ValueError, 'unsupported_claim_number'):
            self.validate('أصبحت إجازة في 2007 وأول احتفال في 2015',
                          'In 2007 the national day became an official holiday.')

    def test_arabic_digits_match_original_numbers(self):
        self.validate('صدر القرار عام ١٩٣٢', 'The decree was issued in 1932.')

    def test_supported_year_is_not_a_substring_of_another_number(self):
        with self.assertRaisesRegex(ValueError, 'unsupported_claim_number'):
            self.validate('كان العدد 32', 'The decree was issued in 1932.')

    def test_official_references_are_bounded_deduplicated_and_allowlisted(self):
        urls = ['https://evil.example/a', 'https://www.spa.gov.sa/a',
                'https://www.spa.gov.sa/a', 'https://saudipedia.com/b',
                'https://www.mofa.gov.sa/c', 'https://www.spa.gov.sa/d']
        with patch.object(sources, 'fetch', return_value=b'<article>Official historical evidence.</article>') as fetch:
            rows = sources.official_references([{'reference_urls': urls}])
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r['source_type'] == 'official_reference' for r in rows))
        self.assertEqual(rows[0]['text'], 'Official historical evidence.')

    def test_failed_reference_does_not_invent_evidence(self):
        with patch.object(sources, 'fetch', side_effect=OSError('offline')):
            self.assertEqual(sources.official_references([
                {'reference_urls': ['https://www.spa.gov.sa/a']}]), [])

    def test_research_delivers_official_text_to_researcher(self):
        candidate = {'editorial': {'subjects': ['Saudi National Day'],
                                  'research_query': 'Saudi National Day'}}
        wiki_row = {'id': 'w1', 'source_type': 'encyclopedia', 'title': 'Saudi National Day', 'text': 'Historical context.',
                    'url': 'https://en.wikipedia.org/?curid=1',
                    'reference_urls': ['https://www.spa.gov.sa/a']}
        with patch.object(sources.Sources, 'attention', return_value=[]), \
             patch.object(sources, 'wiki', return_value=[wiki_row]), \
             patch.object(sources, 'fetch', return_value=b'<p>Official decree evidence.</p>'):
            rows = sources.Sources().research(candidate)
        self.assertEqual(rows[-1]['text'], 'Official decree evidence.')
        self.assertTrue(all('reference_urls' not in r for r in rows))
