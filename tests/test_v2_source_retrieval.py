import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from publishing_v2.autopilot.sources import wiki, Sources, WIKI_TEXT_LIMIT


def response(text='Verified history'):
    return json.dumps({'query':{'pages':{'1':{'pageid':1,'title':'Cole Palmer','extract':text}}}}).encode()


class SourceRetrievalTests(unittest.TestCase):
    def test_search_recovery_requests_each_bounded_candidate_extract(self):
        def api(url):
            params=parse_qs(urlsplit(url).query)
            if 'titles' in params:
                return b'{"query":{"pages":{"-1":{"missing":""}}}}'
            if params.get('list') == ['search']:
                return b'{"query":{"search":[{"pageid":1},{"pageid":2}]}}'
            count=int(params.get('exlimit',['1'])[0])
            return json.dumps({'query':{'pages':{str(i):{'pageid':i,
                'title':'Subject '+str(i),'extract':'Verified context'} for i in range(1,count+1)}}}).encode()
        with patch('publishing_v2.autopilot.sources.fetch',side_effect=api):
            rows=wiki('Subject')
        self.assertEqual([r['title'] for r in rows],['Subject 1','Subject 2'])

    def test_full_history_is_retrieved_then_bounded_locally(self):
        full = 'Introduction. ' * 100 + 'Documented turning point. ' * 1200
        def api(url):
            params=parse_qs(urlsplit(url).query)
            return response(full[:1200] if 'exchars' in params else full)
        with patch('publishing_v2.autopilot.sources.fetch',side_effect=api):
            rows=wiki('Cole Palmer')
        self.assertEqual(rows[0]['text'],full[:WIKI_TEXT_LIMIT])
        self.assertIn('Documented turning point.', rows[0]['text'])

    def test_temporary_transport_failure_is_retried_once(self):
        with patch('publishing_v2.autopilot.sources.fetch',side_effect=[URLError('temporary'),response()]) as fetch, \
             patch('publishing_v2.autopilot.sources.time.sleep'):
            rows=wiki('Cole Palmer')
        self.assertEqual(rows[0]['title'],'Cole Palmer')
        self.assertEqual(fetch.call_count,2)

    def test_api_errors_are_not_misreported_as_no_subject(self):
        with patch('publishing_v2.autopilot.sources.fetch',return_value=b'{"error":{"code":"badvalue"}}'):
            with self.assertRaisesRegex(ValueError,'encyclopedia_api_error:badvalue'):
                wiki('Cole Palmer')

    def test_permanent_http_denial_is_not_retried(self):
        with patch('publishing_v2.autopilot.sources.fetch',side_effect=HTTPError('https://en.wikipedia.org',403,'Forbidden',{},None)) as fetch:
            with self.assertRaises(HTTPError):wiki('Cole Palmer')
        self.assertEqual(fetch.call_count,1)

    def test_repeated_failure_is_bounded_and_persisted_as_retrieval_failure(self):
        candidate={'editorial':{'subjects':['Cole Palmer'],'research_query':'Cole Palmer'}}
        with patch('publishing_v2.autopilot.sources.fetch',side_effect=URLError('temporary')) as fetch, \
             patch('publishing_v2.autopilot.sources.time.sleep'):
            with self.assertRaisesRegex(ValueError,'unresolved_editorial_subject'):
                Sources().research(candidate)
        self.assertEqual(fetch.call_count,2)
        self.assertEqual(candidate['subject_resolution'][0]['status'],'retrieval_failed')
        self.assertEqual(candidate['subject_resolution'][0]['error_type'],'URLError')
