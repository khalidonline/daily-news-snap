"""Versioned owner feedback; changes invalidate earlier engine approval."""
from urllib.parse import urlsplit
import re

EDITORIAL_FEEDBACK = (
    {'subject': 'Rejection recovery',
     'reason': ('A review rejection is not a stop condition. Repair the existing package first using saved '
                'research/evidence/images when possible. If the angle itself remains weak, replace the candidate '
                'and continue within the shared budget until a publishable package exists. Stop only for a real '
                'budget, source, rights, safety, or delivery blocker.')},
    {'subject': 'Generic heritage angle',
     'reason': ('Owner rejects packages whose value is mainly that a subject is part of Saudi heritage, '
                'has a special place, or is being introduced to a new generation. A current trigger must '
                'lead to a concrete memorable fact and a documented story worth sharing; otherwise reject '
                'the angle before publication.')},
    {'subject': 'Horse package 2026-09-25',
     'rejected_candidate_id': 'owner-approved-horse-20260925',
     'reason': ('Owner rejected the generic horse-heritage angle as too shallow. Do not reuse this angle; '
                'future horse coverage needs a specific distinctive fact and stronger story progression.')},
    {'subject': 'Owner Snapchat style',
     'reason': ('Use casual Saudi wording and a clear Snapchat story progression. '
                'Avoid academic/history-article framing, heavy prose, repeated names, '
                'and formal words such as لاحقاً، معروفاً، قدراً. Start from what the '
                'viewer is likely seeing/hearing now, then explain simply, then tell '
                'a connected story worth sharing.')},
    {'subject': 'Music and artists',
     'reason': ('Owner does not want packages about singers, musicians, songs, albums, '
                'music awards or concerts. Reject these before paid research or writing.')},
    {'subject': 'Ostrich reintroduction',
     'rejected_candidate_id': 'b63aca74ca2db59c',
     'rejected_article': ('www.alyaum.com', '/articles/6683301'),
     'reason': 'Owner rejected this trigger and the species-statistics story as weak and not in current public conversation.'},
    {'subject': 'Date palm',
     'rejected_candidate_id': 'local-c80cb7e19b06',
     'reason': 'Owner rejected the timeless species/fruit-facts package; do not recycle it as a story.'},
)


MUSIC_ARTIST_TERMS = (
    'مغني', 'مغنية', 'فنان', 'فنانة', 'مطرب', 'مطربة', 'أغنية', 'اغنية',
    'ألبوم', 'البوم', 'حفلة موسيقية', 'حفل موسيقي', 'موسيقى', 'موسيقي',
    'singer', 'musician', 'song', 'album', 'music award', 'concert',
)

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

