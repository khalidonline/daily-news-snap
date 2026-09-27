"""Free per-package evidence reports; inventory is never publication authority."""
from datetime import datetime


def _time(value):
    at = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if at.tzinfo is None:
        raise ValueError('timezone_required')
    return at


def inventory_entry(state, slot, now):
    status = state.get('status')
    if status in {'delivery_pending', 'publishing'}:
        disposition = 'reconciliation_required'
    elif status == 'published':
        disposition = 'published'
    elif status in {'shadow_passed', 'approved'} and state.get('approval'):
        expires = state.get('package', {}).get('expires_at') or state.get('expires_at')
        try:
            disposition = 'reviewed_requires_revalidation' if _time(expires) > now else 'expired'
        except (ValueError, TypeError, AttributeError):
            disposition = 'expiry_unknown'
    else:
        disposition = 'not_ready'
    return {'slot':slot, 'status':disposition, 'title':state.get('package', {}).get('title'),
            'candidate_id':state.get('candidate_id'), 'updated_at':now.isoformat(),
            'expires_at':state.get('package', {}).get('expires_at') or state.get('expires_at'),
            'package_sha256':state.get('approval', {}).get('package_sha256'),
            'source_state_status':status, 'publish_authorized':False}


def measure_performance(state, data, now):
    if data is None:
        return {'status':'unavailable'}
    receipt = state.get('receipt') or {}
    if state.get('status') != 'published' or receipt.get('status') != 'POSTED':
        raise ValueError('confirmed_publication_required')
    if not isinstance(data.get('source'), str) or not data['source'].strip():
        raise ValueError('measurement_source_required')
    observed, start, end = (_time(data[k]) for k in ('observed_at','window_start','window_end'))
    if not _time(state['started_at']) <= start < end <= observed <= now:
        raise ValueError('invalid_measurement_window')
    rows = data.get('cards', [])
    if not rows or [r.get('post_id') for r in rows] != receipt.get('post_ids'):
        raise ValueError('measurement_post_order_mismatch')
    views = [r.get('views') for r in rows]
    if any(type(v) is not int or v < 0 for v in views):
        raise ValueError('invalid_view_count')
    return {'status':'observed', 'source':data['source'], 'observed_at':observed.isoformat(),
            'window_start':start.isoformat(), 'window_end':end.isoformat(),
            'sample_age_hours':(end-start).total_seconds()/3600,
            'measurement_age_hours':(now-observed).total_seconds()/3600,
            'views':views, 'completion_ratio':views[-1]/views[0] if views[0] else None,
            'first_transition_ratio':views[1]/views[0] if len(views)>1 and views[0] else None,
            'note':'Descriptive ratios only; no causal claim or advertising benchmark.'}


def package_report(state, slot, now, metrics=None):
    stages, seen, repairs = {}, set(), 0
    for r in state.get('agent_receipts', []):
        identity = r.get('response_id')
        if not identity or identity in seen:
            continue
        seen.add(identity)
        role, cost = r.get('role', 'unknown'), r.get('cost_micro_usd')
        if type(cost) is not int or cost < 0:
            continue
        stages[role] = stages.get(role, 0) + cost
        repairs += role == 'card_repair'
    return {'version':1, 'slot':slot, 'at':now.isoformat(),
            'candidate_id':state.get('candidate_id'), 'title':state.get('package', {}).get('title'),
            'status':state.get('status'), 'reason':state.get('reason'),
            'selection_assessment':state.get('selection_assessment'),
            'cost_by_stage':stages, 'settled_cost_micro_usd':sum(stages.values()),
            'cost_scope':'Recorded settled receipts for this package state; daily ledger remains budget authority. Unknown reservations excluded.',
            'repair_calls':repairs, 'text_approval':state.get('text_approval'),
            'final_review':state.get('review'), 'approval':state.get('approval'),
            'receipt':state.get('receipt'),
            'inventory':inventory_entry(state,slot,now),
            'performance':measure_performance(state,metrics,now)}
