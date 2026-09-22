"""Recent confirmed publications exclude repeated subjects before paid selection."""
import hashlib
import json
import re
from datetime import datetime, timedelta


def normalized(value):
    return ' '.join(re.findall(r'\w+', str(value).casefold()))


class PublishedMemory:
    def __init__(self, store, now):
        self.store, self.now = store, now
        self.rows = store.read().get('publications', {})

    def remember(self, identity, urls, aliases, at):
        if identity in self.rows:
            return
        self.rows[identity] = {'urls': urls, 'aliases': aliases, 'at': at}
        self.rows = dict(sorted(self.rows.items(), key=lambda pair: pair[1]['at'], reverse=True)[:200])
        self.store.save({'version': 1, 'publications': self.rows})

    def reason(self, candidate):
        title = ' ' + normalized(candidate.get('title', '')) + ' '
        url = candidate.get('url', '').split('?')[0]
        for row in self.rows.values():
            if not 0 <= self.now().timestamp() - row['at'] < 86400:
                continue
            if url and url in row['urls']:
                return 'already_published_recently'
            for alias in row['aliases']:
                if normalized(alias) and ' ' + normalized(alias) + ' ' in title:
                    return 'already_published_recently'
        return None

    def record(self, candidate, receipt):
        if receipt.get('status') != 'POSTED' or not receipt.get('post_ids'):
            return
        aliases = [row['name'] for row in candidate.get('resolved_subjects', []) if row.get('name')]
        edit = candidate.get('editorial', {})
        aliases += edit.get('subjects', [])
        self.remember(receipt['identity'], [candidate['url'].split('?')[0]],
                      list(dict.fromkeys(aliases)), self.now().timestamp())

    def import_manual(self, root, journal_factory):
        """Approval alone cannot suppress news; require real delivery receipts."""
        for path in sorted(root.glob('*/manifest.json')):
            data = json.loads(path.read_text())
            aliases = data.get('topic_aliases', [])
            if not aliases or data.get('approved') is not True:
                continue
            expiry = datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00'))
            # Manual approvals expire at midnight; retain only the current day's
            # package and yesterday's until its 24-hour suppression elapses.
            if not self.now() - timedelta(days=1) < expiry <= self.now() + timedelta(days=1):
                continue
            hashes = [m['sha256'] for m in data['media']]
            identity = hashlib.sha256(('executivesaudi:' + ':'.join(hashes)).encode()).hexdigest()
            if identity in self.rows:
                continue
            receipt = journal_factory(identity).read()
            count = sum(m['kind'] != 'credits' for m in data['media'])
            if not count or any(receipt.get(str(i), {}).get('status') != 'POSTED'
                                or not receipt.get(str(i), {}).get('post_id') for i in range(1, count+1)):
                continue
            urls = [s['url'].split('?')[0] for s in data.get('sources', []) if s.get('url')]
            self.remember(identity, urls, aliases, self.now().timestamp())
