"""Versioned owner feedback; changes invalidate earlier engine approval."""
from .owner_memory import EDITORIAL_FEEDBACK, MUSIC_ARTIST_TERMS, MEMORY_RECORDS
from urllib.parse import urlsplit
import re




def rejected_category(candidate):
    haystack = ' '.join(str(candidate.get(k, '')) for k in ('title', 'summary')).lower()
    return any(term.lower() in haystack for term in MUSIC_ARTIST_TERMS)


def rejected_trigger(candidate):
    if rejected_category(candidate):
        return True
    parsed = urlsplit(candidate.get('url', ''))
    for row in EDITORIAL_FEEDBACK:
        if row.get('rejected_candidate_id') and candidate.get('id') == row['rejected_candidate_id']:
            return True
        host, path = row.get('rejected_article', (None, None))
        if host == parsed.hostname and (parsed.path == path or parsed.path.startswith(path + '/')):
            return True
    return False

