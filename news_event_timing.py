"""Source-backed relative dates, rechecked without a model call at delivery."""

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

KSA = timezone(timedelta(hours=3))
FIELDS = ('headline', 'summary', 'takeaway')
RELATIVE = re.compile(r'(?<!\w)(?P<prefix>[وف]?)(?P<word>غد[ًا]*|اليوم|tomorrow|today)(?!\w)', re.I)
ISO_DATE = re.compile(r'(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)')
ANNOUNCEMENT = re.compile(
    r'(?:أعلن|اعلن|تعلن|يعلن|أوضح|اوضح|قال|صرح|كشف|بيان|announc|said|reveal|statement)', re.I
)
UNRESOLVED_TIME = re.compile(
    r'(?:الأسبوع|الاسبوع|الشهر|العام|السنة)\s+(?:المقبل|القادم|الماضي|المقبلة|القادمة|الماضية)'
    r'|(?:next|last)\s+(?:week|month|year)|بعد\s+غد|قريباً|قريبا|\bsoon\b', re.I
)


def has_relative_date(story):
    return any(RELATIVE.search(str(story.get(k) or '')) for k in FIELDS)


def _day(value):
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timing evidence requires a source timezone')
    return parsed.astimezone(KSA).date()


def _verified_date(story):
    source = story.get('timing_source') or {}
    if not isinstance(source, dict):
        raise ValueError('invalid source timing evidence')
    quote = str(story.get('event_date_evidence') or '').strip()
    source_text = '\n'.join(str(source.get(k) or '') for k in ('title', 'summary'))
    # A bare 'today' can refer to an announcement, not the event being previewed.
    context = RELATIVE.sub('', ISO_DATE.sub('', quote)).strip()
    if len(context) < 4 or quote not in source_text:
        raise ValueError('missing source timing evidence')
    if (ANNOUNCEMENT.search(quote) and RELATIVE.search(quote)) or UNRESOLVED_TIME.search(source_text):
        raise ValueError('announcement or unresolved source timing evidence requires a neutral angle')
    try:
        event_day = date.fromisoformat(str(story.get('event_date') or ''))
        dates = {date.fromisoformat(v) for v in ISO_DATE.findall(quote)}
        relative = [m.group('word') for m in RELATIVE.finditer(quote)]
        if relative:
            # Publication is only an anchor for an explicit source-relative
            # date. It is never itself evidence of when an event happens.
            anchor = _day(source.get('published_at'))
            dates.update(anchor + timedelta(days=1 if word.lower().startswith(('غد', 'tomorrow')) else 0)
                         for word in relative)
        if dates != {event_day}:
            raise ValueError('ambiguous or contradictory timing evidence')
        # This small guard deliberately does not resolve multiple event dates.
        # A source containing announcement-day + event-day needs a neutral
        # angle instead of letting the model pick the wrong date fragment.
        source_dates = {date.fromisoformat(v) for v in ISO_DATE.findall(source_text)}
        source_relative = [m.group('word') for m in RELATIVE.finditer(source_text)]
        if source_relative:
            anchor = _day(source.get('published_at'))
            source_dates.update(anchor + timedelta(days=1 if word.lower().startswith(('غد', 'tomorrow')) else 0)
                                for word in source_relative)
        if source_dates != {event_day}:
            raise ValueError('ambiguous source timing evidence')
    except (TypeError, ValueError) as exc:
        raise ValueError('invalid source timing evidence') from exc
    return event_day


def _apply_corrections(story):
    """Apply reviewed errata only to the exact article and original wording."""
    path = Path(__file__).with_name('news_copy_corrections.json')
    corrections = json.loads(path.read_text(encoding='utf-8'))
    url = urlsplit(str(story.get('link') or ''))
    identity = url.netloc.removeprefix('www.') + url.path.rstrip('/')
    for correction in corrections:
        if identity == correction['article']:
            for field, edit in correction['fields'].items():
                if story.get(field) == edit['before']:
                    story[field] = edit['after']
    return story


def prepare_news_delivery(story, now=None):
    """Correct supported dates; refuse unsupported/expired preview claims.

    Ordinary date-neutral cards need no metadata. Recovery carries the exact
    source excerpt saved during selection, not a date inferred from its slot.
    """
    prepared = _apply_corrections(dict(story))
    if not has_relative_date(prepared) and not prepared.get('event_date'):
        return prepared
    words = {m.group('word').lower().startswith(('غد', 'tomorrow'))
             for k in FIELDS for m in RELATIVE.finditer(str(prepared.get(k) or ''))}
    if len(words) > 1:
        raise ValueError('multiple card dates need separate timing evidence')
    event_day = _verified_date(prepared)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('delivery time requires a timezone')
    delta = (event_day - now.astimezone(KSA).date()).days
    if delta < 0:
        # A scheduled date is not proof that the event actually took place.
        raise ValueError('expired News preview needs a fresh supported angle')
    for field in FIELDS:
        if field not in prepared:
            continue
        def replace(match):
            arabic = match.group('word').lower() not in ('today', 'tomorrow')
            prefix = match.group('prefix')
            if delta == 0:
                return prefix + ('اليوم' if arabic else 'today')
            if delta == 1:
                return prefix + ('غداً' if arabic else 'tomorrow')
            return prefix + ('بتاريخ ' if arabic else 'on ') + event_day.isoformat()
        prepared[field] = RELATIVE.sub(replace, str(prepared[field]))
    return prepared
