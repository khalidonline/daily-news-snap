import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from publishing_v2.autopilot.published_memory import PublishedMemory
import test_v2_autopilot as fixtures


class PublishedMemoryTests(unittest.TestCase):
    def test_confirmed_publication_survives_restart_without_extending_expiry(self):
        now = fixtures.NOW
        store = fixtures.MemoryStore()
        candidate = {'url': 'https://example.com/a?utm=x', 'editorial': {'subjects': ['Mbappé', 'مبابي']}}
        receipt = {'identity': 'one', 'status': 'POSTED', 'post_ids': ['post']}
        memory = PublishedMemory(store, lambda: now)
        memory.record(candidate, dict(receipt, status='PENDING'))
        self.assertEqual(memory.rows, {})
        memory.record(candidate, receipt)
        now += timedelta(hours=23)
        memory = PublishedMemory(store, lambda: now)
        memory.record(candidate, receipt)
        for title in ['مبابي يسجل هدفا', 'Mbappé scores again']:
            self.assertIsNotNone(memory.reason({'title': title, 'url': 'https://other.com'}))
        self.assertIsNotNone(memory.reason({'title': 'Different', 'url': candidate['url']}))
        now += timedelta(hours=1)
        self.assertIsNone(memory.reason(candidate))

    def test_real_manual_manifests_require_complete_delivery_and_disambiguate_ceer(self):
        now = datetime(2026, 9, 22, 12, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            journals = {}
            for topic in ['ceer', 'mbappe']:
                source = Path('approved') / (topic + '-20260922') / 'manifest.json'
                data = json.loads(source.read_text())
                target = root / topic
                target.mkdir()
                (target / 'manifest.json').write_text(json.dumps(data))
                identity = hashlib.sha256(('executivesaudi:' + ':'.join(m['sha256'] for m in data['media'])).encode()).hexdigest()
                journal = fixtures.MemoryStore()
                count = sum(m['kind'] != 'credits' for m in data['media'])
                journal.data = {str(i): {'status': 'POSTED', 'post_id': str(i)} for i in range(1, count + 1)}
                journals[identity] = journal
            memory = PublishedMemory(fixtures.MemoryStore(), lambda: now)
            # A single pending card makes the whole package ineligible for memory.
            for journal in journals.values():
                journal.data['1']['status'] = 'SENDING'
            memory.import_manual(root, journals.__getitem__)
            self.assertEqual(memory.rows, {})
            for journal in journals.values():
                journal.data['1']['status'] = 'POSTED'
            memory.import_manual(root, journals.__getitem__)
            self.assertEqual(len(memory.rows), 2)
            for title in ['شركة سير تكشف سياراتها', 'Ceer unveils EXOBOT', 'مبابي يسجل', 'Mbappé scores']:
                self.assertIsNotNone(memory.reason({'title': title}))
            self.assertIsNone(memory.reason({'title': 'حركة سير المركبات في الرياض'}))
            now += timedelta(hours=24)
            memory.import_manual(root, journals.__getitem__)
            self.assertIsNone(memory.reason({'title': 'شركة سير تكشف سياراتها'}))


class PipelinePublishedTests(unittest.TestCase):
    setUp = fixtures.PipelineTests.setUp
    pipeline = fixtures.PipelineTests.pipeline
    render = fixtures.PipelineTests.render
    publish = fixtures.PipelineTests.publish

    def test_publications_are_excluded_before_any_paid_role(self):
        pipeline = self.pipeline()
        memory = PublishedMemory(fixtures.MemoryStore(), lambda: fixtures.NOW)
        for candidate in pipeline.sources.discover('daily', fixtures.NOW):
            memory.remember(candidate['id'], [candidate['url']], [], fixtures.NOW.timestamp())
        pipeline.published_memory = memory
        result = pipeline.run('daily', 'shadow')
        self.assertEqual(result['status'], 'held')
        self.assertEqual(self.agent.calls, [])
        self.assertEqual(len(result['eligibility_rejections']), 2)
