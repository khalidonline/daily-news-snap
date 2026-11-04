"""Pure adapters for existing journals. No fetching, sending or state writes."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def timestamp(value, now):
    try:
        at = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return at if at.tzinfo is not None and at <= now else None
    except (ValueError, TypeError, AttributeError):
        return None


def mapping(value):
    return value if isinstance(value, dict) else {}


def evidence(envelope, now):
    envelope = mapping(envelope)
    at = timestamp(envelope.get('observed_at'), now)
    return {'observed_at': at.isoformat() if at else None,
            'source': envelope.get('source') if isinstance(envelope.get('source'), str) else None,
            'freshness': ('unknown' if at is None else
                          'current' if now - at <= timedelta(hours=1) else 'stale')}


def destination(envelope, kind, identity, expected, now):
    envelope = mapping(envelope)
    data = mapping(envelope.get('data'))
    result = {**evidence(envelope, now), 'status': 'unknown', 'post_ids': [], 'confirmed_at': None}
    if not data:
        return result
    result['status'] = 'unresolved'
    if kind == 'saved_story':
        rows = [data]
        valid = isinstance(identity, str) and bool(identity.strip()) and data.get('identity') == identity
    else:
        keys = {key for key in data if isinstance(key, str) and key.isdigit()}
        valid = type(expected) is int and 0 < expected <= 100
        valid = valid and keys == {str(i) for i in range(1, expected + 1)}
        rows = [mapping(data[key]) for key in sorted(keys)]
        valid = valid and not data.get('reconciliation')
        valid = valid and all(row.get('placement', 'STORY') == 'STORY' for row in rows)
        if '_group' in data:
            group = mapping(data['_group'])
            media_ids = [row.get('media_id') for row in rows]
            distinct_media = (all(isinstance(value, str) and value.strip() for value in media_ids)
                              and len(set(media_ids)) == len(rows))
            valid = (valid and distinct_media and isinstance(identity, str) and bool(identity.strip())
                     and group.get('identity') == identity and group.get('status') == 'POSTED'
                     and bool(group.get('post_id'))
                     and all(row.get('post_id') == group.get('post_id') and row.get('media_id') for row in rows))
        else:
            post_ids = [row.get('post_id') for row in rows]
            valid = (valid and all(isinstance(value, str) and value.strip() for value in post_ids)
                     and len(set(post_ids)) == len(rows))
    confirmed = [row for row in rows if row.get('status') == 'POSTED'
                 and isinstance(row.get('post_id'), str) and row['post_id'].strip()]
    result['post_ids'] = list(dict.fromkeys(row['post_id'] for row in confirmed))
    if valid and rows and len(confirmed) == len(rows):
        result['status'] = 'confirmed'
        times = [timestamp(row.get('confirmed_at'), now) for row in rows]
        if all(times):
            result['confirmed_at'] = max(times).isoformat()
    return result


def operational_report(snapshot, now):
    if now.tzinfo is None:
        raise ValueError('timezone_required')
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get('packages', []), list):
        raise ValueError('invalid_snapshot')
    packages = []
    for raw in snapshot.get('packages', []):
        row = mapping(raw)
        identity = row.get('package_id')
        packages.append({'package_id': identity, 'title': row.get('title'),
                         'status': row.get('status', 'unknown'),
                         'reason': row.get('reason'),
                         'story': destination(row.get('story'), 'story', identity, row.get('expected_story_cards'), now),
                         'saved_story': destination(row.get('saved_story'), 'saved_story', identity, None, now)})
    return {'version': 1, 'read_only': True, 'generated_at': now.isoformat(),
            'day': now.astimezone(ZoneInfo('Asia/Riyadh')).date().isoformat(),
            'timezone': 'Asia/Riyadh', 'packages': packages}


def render_operational(report):
    labels = {'confirmed': 'مؤكد في الإيصال', 'unresolved': 'غير محسوم', 'unknown': 'غير معلوم'}
    lines = [f"تقرير التشغيل | {report['day']} (الرياض)",
             f"أُعدّ: {report['generated_at']} | قراءة فقط"]
    for row in report['packages']:
        title = ' '.join(str(row.get('title') or row.get('package_id') or 'باقة').split())[:120]
        lines.append(f"{title} | حالة الباقة المسجلة: {row['status']}")
        for key, name in [('story', 'Story'), ('saved_story', 'Saved Story')]:
            item = row[key]
            freshness = {'stale': 'قراءة قديمة', 'current': 'قراءة حديثة', 'unknown': 'حداثة القراءة غير معلومة'}[item['freshness']]
            lines.append(f"{name}: {labels[item['status']]} | آخر قراءة موثقة: {item['observed_at'] or 'غير معلوم'}"
                         f" | وقت التأكيد: {item['confirmed_at'] or 'غير مسجل'} | {freshness}")
        if any(row[k]['status'] == 'unresolved' for k in ('story', 'saved_story')):
            lines.append('يلزم التحقق قبل إعادة المحاولة لتجنب التكرار.')
    if not report['packages']:
        lines.append('حالة الباقات: غير معلومة؛ لم تُرفق سجلات.')
    return '\n'.join(lines)
