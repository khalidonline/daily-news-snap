"""Deterministic constraints. Model output cannot grant authority."""
import hashlib
import json
from datetime import datetime, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo
from .feedback import rejected_trigger
from .sources import attention_source

RIYADH = ZoneInfo('Asia/Riyadh')
REVIEW_CHECKS = ('factual', 'timely', 'saudi_language', 'broad_appeal',
                 'current_attention', 'feedback_respected',
                 'story_coherent', 'documented_story', 'distinct_value',
                 'visual_variety', 'story_numbering', 'visual_identity', 'safe_routine')


def story_counter(index, total):
    return f'{index} من {total}'.translate(str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩'))


def validate_image_variety(cards):
    editorial = [c for c in cards if c.get('kind') != 'credits']
    for key in ('asset_id', 'sha256', 'origin_key'):
        values = [c.get('image', {}).get(key) for c in editorial]
        values = [v for v in values if v]
        if len(values) != len(set(values)):
            raise ValueError('duplicate_source_image: choose different relevant photos or fewer cards')


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def text(value, maximum=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError('invalid_text')
    return value


def expiry(now):
    return datetime.combine(now.astimezone(RIYADH).date() + timedelta(days=2),
                            time.min, RIYADH).isoformat()


def validate_attention(candidate, now):
    if rejected_trigger(candidate):
        raise ValueError('owner_rejected_trigger')
    published = candidate.get('published_at')
    if not isinstance(published, str) or not candidate.get('url'):
        raise ValueError('missing_attention_source')
    stamp = datetime.fromisoformat(published)
    if stamp.tzinfo is None or not now - timedelta(days=1) <= stamp <= now:
        raise ValueError('attention_outside_window')


def reporting_time(data, sources, candidate, lane):
    """Fresh verified reporting may trigger a story without dating its history."""
    if data.get('event_date') is not None:
        return data
    article = next((s for s in sources if attention_source(s, candidate)), None)
    published = candidate.get('published_at')
    if not article or not isinstance(published, str):
        return data
    stamp = datetime.fromisoformat(published)
    if stamp.tzinfo is None:
        raise ValueError('undated_reporting_source')
    quote = 'Reported at ' + published
    source = {'id': 'verified-feed-time', 'url': candidate['url'], 'text': quote,
              'source_type': 'retrieved_feed_metadata'}
    sources.append(source)
    return dict(data, event_date=stamp.astimezone(RIYADH).date().isoformat(),
                event_quote=quote, event_source_id=source['id'], timing_basis='report_date',
                timing_note='Current reporting is the trigger. Do not claim the underlying event happened today.')


def validate_research(data, sources, lane, now):
    by_id = {s['id']: s for s in sources}
    claims = data.get('claims', [])
    if not 1 <= len(claims) <= 16 or len({c['id'] for c in claims}) != len(claims):
        raise ValueError('invalid_claims')
    for claim in claims:
        text(claim['id'], 80); text(claim['fact'], 500)
        quote = text(claim['quote'], 1000)
        if len(quote) < 12 or quote not in by_id.get(claim['source_id'], {}).get('text', ''):
            raise ValueError('unsupported_quote')
    if data.get('sensitive') is not False:
        raise ValueError('sensitive_or_uncertain_topic')
    if lane in {'daily', 'local'}:
        event_text = data.get('event_date')
        if not isinstance(event_text, str):
            raise ValueError('missing_event_date')
        event = datetime.fromisoformat(event_text).date()
        today = now.astimezone(RIYADH).date()
        if not today - timedelta(days=1) <= event <= today + timedelta(days=1):
            raise ValueError('event_outside_window')
        quote = text(data['event_quote'], 500)
        if len(quote) < 8 or quote not in by_id.get(data['event_source_id'], {}).get('text', ''):
            raise ValueError('unsupported_event_time')


def evidence_snapshot(data, sources):
    """Persist supporting excerpts and provenance, not full copied articles."""
    quotes = {}
    for claim in data['claims']:
        quotes.setdefault(claim['source_id'], []).append(claim['quote'])
    if data.get('event_source_id') and data.get('event_quote'):
        quotes.setdefault(data['event_source_id'], []).append(data['event_quote'])
    rows = []
    for source in sources:
        excerpts = list(dict.fromkeys(quotes.get(source['id'], [])))
        body = '\n'.join(excerpts)
        if len(body.split()) > 200:
            raise ValueError('source_excerpt_limit')
        if body:
            snapshot = {'id': source['id'], 'url': source['url'], 'text': body,
                        'retrieved_text_sha256': hashlib.sha256(source['text'].encode()).hexdigest()}
            if source.get('source_type') == 'publisher_feed':
                snapshot.update({key: source[key] for key in ('source_type', 'feed_url', 'published_at')})
            rows.append(snapshot)
    return rows


def validate_draft(data, research):
    if set(data) != {'title', 'cards'}:
        raise ValueError('unexpected_draft_fields')
    text(data.get('title'), 100)
    cards = data.get('cards', [])
    if not 3 <= len(cards) <= 7 or [c.get('kind') for c in cards] != ['info'] + ['story'] * (len(cards) - 1):
        raise ValueError('info_and_two_to_six_story_cards_required')
    known = {c['id'] for c in research['claims']}
    for card in cards:
        if set(card) != {'kind', 'title', 'body', 'punch', 'claim_ids', 'image_query'}:
            raise ValueError('unexpected_card_fields')
        text(card.get('title'), 85); text(card.get('body'), 320)
        if not isinstance(card.get('punch'), str) or len(card['punch']) > 100:
            raise ValueError('invalid_closing')
        text(card.get('image_query'), 180)
        ids = card.get('claim_ids')
        if not isinstance(ids, list) or not ids or any(i not in known for i in ids):
            raise ValueError('unsupported_card_claim')


def validate_review(review, count):
    text(review.get('reason'), 2000)
    checks = review.get('checks', {})
    if any(checks.get(k) is not True for k in REVIEW_CHECKS):
        raise ValueError('editorial_review_rejected')
    rows = review.get('card_checks', [])
    if len(rows) != count or any(r.get('readable') is not True or r.get('relevant') is not True for r in rows):
        raise ValueError('visual_review_rejected')


def seal(package, paths):
    return {'package_sha256': digest(package),
            'media_sha256': [hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths]}


def verify_seal(package, paths, approval, now):
    if now.tzinfo is None:
        raise ValueError('timezone_required')
    expires = datetime.fromisoformat(package['expires_at'])
    if expires.tzinfo is None or now >= expires:
        raise ValueError('package_expired')
    if not paths or approval != seal(package, paths):
        raise ValueError('approved_package_changed')
