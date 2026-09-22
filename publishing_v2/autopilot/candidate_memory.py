"""Bounded rejection history for unchanged feed items across scheduled runs."""
import hashlib
import json


class CandidateMemory:
    def __init__(self, store, now):
        self.store, self.now = store, now
        self.rows = store.read().get('rejections', {})

    @staticmethod
    def key(candidate):
        # Feed timestamps and IDs may refresh without any new reporting.
        content = [candidate.get(key, '') for key in ('url', 'title', 'summary')]
        return hashlib.sha256(json.dumps(content, ensure_ascii=False).encode()).hexdigest()

    def reason(self, candidate, engine):
        row = self.rows.get(self.key(candidate), {})
        if self.now().timestamp() - row.get('at', 0) >= 86400:
            return None
        # Implementation fixes can repair binding/retrieval failures immediately.
        if row.get('engine') != engine and row.get('reason') not in {
                'sensitive_or_uncertain_topic', 'invalid_claims', 'event_outside_window'}:
            return None
        return row.get('reason')

    def record(self, candidate, reason, engine):
        # Network, budget and infrastructure failures must never blacklist news.
        if reason in {'RuntimeError', 'OSError', 'agent_input_too_large'}:
            return
        self.rows[self.key(candidate)] = {'candidate_id': candidate['id'],
            'source_title': candidate['title'], 'reason': reason,
            'engine': engine, 'at': self.now().timestamp()}
        self.rows = dict(sorted(self.rows.items(), key=lambda item: item[1]['at'], reverse=True)[:500])
        self.store.save({'version': 1, 'rejections': self.rows})
