"""Deterministic constraints. Model output cannot grant authority."""
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo
from .feedback import rejected_trigger
from .sources import attention_source

RIYADH = ZoneInfo('Asia/Riyadh')
REVIEW_CHECKS = ('factual', 'timely', 'saudi_language', 'broad_appeal',
                 'current_attention', 'feedback_respected',
                 'story_coherent', 'documented_story', 'distinct_value',
                 'snapchat_pull', 'owner_quality',
                 'visual_variety', 'story_numbering', 'visual_identity', 'safe_routine')


def validate_editor_binding(candidate):
    """Bind editor evidence to one discovered source; not a semantic fact check."""
    edit = candidate['editorial']
    if edit.get('source_title') != candidate.get('title'):
        raise ValueError('editor_source_title_mismatch')
    subjects, evidence = edit.get('subjects'), edit.get('subject_evidence')
    if (not isinstance(subjects, list) or not 1 <= len(subjects) <= 2
            or any(not isinstance(s, str) or not s.strip() for s in subjects)
            or len(set(subjects)) != len(subjects)
            or not isinstance(evidence, list) or len(evidence) != len(subjects)):
        raise ValueError('editor_subject_evidence_required')
    normalize = lambda value: ' '.join(value.split())
    source_parts = [normalize(candidate.get(key, '')) for key in ('title', 'summary')]
    seen = set()
    for row in evidence:
        if (not isinstance(row, dict) or not isinstance(row.get('subject'), str)
                or row['subject'] not in subjects or row['subject'] in seen):
            raise ValueError('editor_subject_evidence_mismatch')
        seen.add(row['subject'])
        quote, mention = row.get('quote'), row.get('mention')
        if not isinstance(quote, str) or not 12 <= len(quote.strip()) <= 1000:
            raise ValueError('editor_subject_quote_required')
        quote = normalize(quote)
        if not any(quote in part for part in source_parts):
            raise ValueError('editor_subject_quote_not_in_source')
        if not isinstance(mention, str) or not 3 <= len(mention.strip()) <= 150:
            raise ValueError('editor_subject_mention_required')
        mention = normalize(mention)
        # Presentation may translate or shorten the name. Only source evidence
        # is checked literally; semantic alignment belongs to source review.
        if mention not in quote:
            raise ValueError('editor_subject_mention_not_grounded')


def story_counter(index, total):
    return f'{index} من {total}'.translate(str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩'))


def validate_image_variety(cards):
    editorial = [c for c in cards if c.get('kind') != 'credits']
    for key in ('asset_id', 'sha256', 'origin_key'):
        values = [c.get('image', {}).get(key) for c in editorial]
        values = [v for v in values if v]
        if any(values.count(value) > 2 for value in set(values)):
            raise ValueError('duplicate_source_image: one photo may appear on at most two editorial cards')
    # The owner accepts a repeated subject illustration between Info and Story
    # only when needed, but the Story itself must visually move forward.
    stories = [c for c in editorial if c.get('kind') == 'story']
    for key in ('asset_id', 'sha256', 'origin_key'):
        values = [c.get('image', {}).get(key) for c in stories]
        values = [v for v in values if v]
        if len(values) != len(set(values)):
            raise ValueError('duplicate_story_image: story cards require distinct source photos')


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


def validate_timing(data, sources, now):
    """Fail closed on the original article before expensive downstream work."""
    if not isinstance(data, dict) or data.get('eligible') is not True:
        raise ValueError('ineligible_or_uncertain_event_time')
    if data.get('timing_basis') not in {'event', 'report'}:
        raise ValueError('unsupported_timing_basis')
    value = data.get('event_date')
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('missing_event_date')
    event = datetime.fromisoformat(value).date()
    today = now.astimezone(RIYADH).date()
    if not today - timedelta(days=1) <= event <= today + timedelta(days=1):
        raise ValueError('event_outside_window')
    quote = text(data.get('event_quote'), 500)
    source = next((s for s in sources if s['id'] == data.get('event_source_id')), {})
    if len(quote) < 8 or quote not in source.get('text', ''):
        raise ValueError('unsupported_event_time')
    text(data.get('reason'), 500)


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


def literal_numbers(value):
    """Compare written numbers only; this is not semantic fact verification."""
    normalized = ''.join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in value)
    normalized = normalized.replace('٫', '.').replace('٬', ',')
    return set(re.findall(r'\d+(?:[.,]\d+)*', normalized))


def prune_unsupported_number_claims(data, sources):
    """Drop only claims whose written numbers are not grounded in their quote.

    The original strict validator remains unchanged and still rejects any
    unsupported numeric claim that survives this deterministic projection.
    """
    if not isinstance(data, dict) or not isinstance(data.get('claims'), list):
        return data, []
    by_id = {source['id']: source for source in sources}
    kept, dropped = [], []
    for claim in data['claims']:
        if not isinstance(claim, dict):
            kept.append(claim)
            continue
        fact, quote, source_id = claim.get('fact'), claim.get('quote'), claim.get('source_id')
        if not isinstance(fact, str) or not isinstance(quote, str) or source_id not in by_id:
            kept.append(claim)
            continue
        if literal_numbers(fact).issubset(literal_numbers(quote)):
            kept.append(claim)
        else:
            dropped.append(claim.get('id'))
    if dropped and len(kept) < 3:
        raise ValueError('insufficient_supported_claims_after_prune')
    return dict(data, claims=kept), [ident for ident in dropped if isinstance(ident, str)]


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
        if not literal_numbers(claim['fact']).issubset(literal_numbers(quote)):
            raise ValueError('unsupported_claim_number')
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
        if set(card) - {'image_caption'} != {'kind', 'title', 'body', 'punch', 'claim_ids', 'image_query'}:
            raise ValueError('unexpected_card_fields')
        text(card.get('title'), 85); text(card.get('body'), 320)
        if not isinstance(card.get('punch'), str) or len(card['punch']) > 100:
            raise ValueError('invalid_closing')
        if 'image_caption' in card:
            if card['kind'] != 'story':
                raise ValueError('photo_caption_story_only')
            text(card['image_caption'], 50)
        text(card.get('image_query'), 180)
        ids = card.get('claim_ids')
        if not isinstance(ids, list) or not ids or any(i not in known for i in ids):
            raise ValueError('unsupported_card_claim')


    # Narrow pre-render guard for the observed model-code-heavy draft. This is
    # not a general readability score: dates and repeated subject names are fine.
    visible = ' '.join(card.get(key, '') for card in cards
                       for key in ('title', 'body', 'punch', 'image_caption'))
    identifiers = {token.upper() for token in re.findall(
        r'[A-Za-z][A-Za-z0-9]*(?:[-–‑][A-Za-z0-9]+)*', visible)
        if any(ch.isdigit() for ch in token)}
    if len(identifiers) > 3:
        raise ValueError('technical_identifier_overload: keep at most three distinct '
                         'model codes; replace nonessential codes with plain roles, '
                         'not transliterations; retain the supported story and claims')

    # Almarai has no arrow glyphs: the owner's arrow-aside style drew as boxes.
    if re.search('[\u2190-\u21ff\u27f0-\u27ff\u2b00-\u2b0f]', visible):
        raise ValueError('unsupported_arrow_symbol: write the side note as a plain short sentence')

    formal = ('لاحقاً', 'لاحقا', 'معروفاً', 'معروفا', 'قدراً', 'قدرا')
    if any(word in visible for word in formal):
        raise ValueError('owner_style_violation: use casual Saudi wording, not formal Arabic')


def validate_review(review, count):
    # Internal evidence audit, not public card copy. Accommodate the bounded
    # reviewer response without paying to rewrite otherwise valid cards.
    text(review.get('reason'), 100_000)
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
