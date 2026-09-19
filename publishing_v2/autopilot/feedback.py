"""Versioned owner feedback; changes invalidate earlier engine approval."""
from urllib.parse import urlsplit

EDITORIAL_FEEDBACK = (
    {'subject': 'Ostrich reintroduction',
     'rejected_candidate_id': 'b63aca74ca2db59c',
     'rejected_article': ('www.alyaum.com', '/articles/6683301'),
     'reason': 'Owner rejected this trigger and the species-statistics story as weak and not in current public conversation.'},
    {'subject': 'Date palm',
     'rejected_candidate_id': 'local-c80cb7e19b06',
     'reason': 'Owner rejected the timeless species/fruit-facts package; do not recycle it as a story.'},
)


def rejected_trigger(candidate):
    parsed = urlsplit(candidate.get('url', ''))
    for row in EDITORIAL_FEEDBACK:
        if candidate.get('id') == row['rejected_candidate_id']:
            return True
        host, path = row.get('rejected_article', (None, None))
        if host == parsed.hostname and (parsed.path == path or parsed.path.startswith(path + '/')):
            return True
    return False
