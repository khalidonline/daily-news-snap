"""One explicit review continuation of a retained, unapproved fixed draft.

This module is read-only: no writer, researcher, provider, ledger mutation,
approval, or filesystem operation. The normal runtime must recheck fresh
evidence and actual text fit before its journal CAS, then independently review.
"""
import copy
from datetime import datetime
import hashlib
import json
import re

from . import fixed_information as fixed
from .policy import digest


_EDITABLE = frozenset({'bullets', 'punch', 'image_caption'})
_FORBIDDEN_STATE = frozenset({'information_package', 'package', 'paths', 'approval',
    'receipt', 'working_draft', 'text_approval', 'review', 'delivery'})


def _sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def _request(request):
    flags = {'saved_draft': 'allow_saved_draft_review',
             'saved_draft_images': 'allow_saved_draft_image_review'}
    if (not isinstance(request, dict) or type(request.get('version')) is not int
            or request['version'] != 1 or request.get('kind') not in flags
            or request.get(flags[request['kind']]) is not True
            or {'allow_replacement_writer', 'allow_new_writer_with_retained_reservation',
                'writing_limit_micro_usd', 'package_writing_authorization'} & set(request)):
        raise ValueError('explicit_saved_draft_review_required')
    try:
        size = len(json.dumps(request, ensure_ascii=False, allow_nan=False).encode('utf-8'))
    except (TypeError, ValueError, UnicodeError):
        raise ValueError('invalid_saved_draft_request') from None
    if size > 64000:
        raise ValueError('saved_draft_request_too_large')


def _json(text):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError('duplicate_artifact_key')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('nonfinite_artifact_number')
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except (TypeError, ValueError):
        raise ValueError('invalid_saved_draft_artifact_json') from None


def validate_artifacts(request, research):
    """Bind original bytes separately from fresh evidence; allow narrow copy edits.

    edited_sha256 is policy.digest(edited_draft), the canonical JSON value
    digest. Artifact sha256 values instead bind each exact UTF-8 text file.
    """
    _request(request)
    artifacts = request.get('artifacts')
    if not isinstance(artifacts, dict) or set(artifacts) != {'raw', 'context', 'normalized'}:
        raise ValueError('exact_saved_draft_artifacts_required')
    parsed = {}
    for key, artifact in artifacts.items():
        if (not isinstance(artifact, dict) or set(artifact) != {'text', 'sha256'}
                or not isinstance(artifact['text'], str) or not _sha(artifact['sha256'])):
            raise ValueError('invalid_saved_draft_artifact')
        try:
            raw_bytes = artifact['text'].encode('utf-8')
        except UnicodeError:
            raise ValueError('invalid_saved_draft_artifact_encoding') from None
        if hashlib.sha256(raw_bytes).hexdigest() != artifact['sha256']:
            raise ValueError('saved_draft_artifact_hash_mismatch')
        parsed[key] = _json(artifact['text'])
    binding = parsed['context']
    if (not isinstance(binding, dict)
            or set(binding) != {'context_sha256', 'raw_sha256', 'status'}
            or binding['status'] != 'writer_saved' or not _sha(binding['context_sha256'])
            or binding['raw_sha256'] != artifacts['raw']['sha256']):
        raise ValueError('saved_draft_original_binding_mismatch')
    normalized, _ = fixed.normalize_unapproved_draft(parsed['raw'])
    if normalized != parsed['normalized']:
        raise ValueError('saved_draft_normalization_mismatch')
    fixed.validate_draft(normalized, research)
    edited = request.get('edited_draft')
    if not _sha(request.get('edited_sha256')) or digest(edited) != request['edited_sha256']:
        raise ValueError('edited_draft_hash_mismatch')
    fixed.validate_draft(edited, research)
    if edited['title'] != normalized['title'] or len(edited['cards']) != len(normalized['cards']):
        raise ValueError('saved_draft_edit_scope_changed')
    changes = []
    for i, (before, after) in enumerate(zip(normalized['cards'], edited['cards'])):
        for key in fixed.TEXT_FIELDS:
            if before[key] == after[key]:
                continue
            if key not in _EDITABLE:
                raise ValueError('saved_draft_edit_scope_changed')
            changes.append({'path': f'cards[{i}].{key}',
                            'before': copy.deepcopy(before[key]), 'after': copy.deepcopy(after[key])})
    if not changes:
        raise ValueError('saved_draft_editorial_edit_required')
    from publishing_v2.information_text_fit import prepare_text
    for index, card in enumerate(edited['cards']):
        fit = prepare_text(fixed.card_draft(card))
        if not fit['fit']:
            raise ValueError('saved_draft_text_does_not_fit: card=' + str(index))
    return {'raw': copy.deepcopy(parsed['raw']), 'normalized': copy.deepcopy(normalized),
            'edited_draft': copy.deepcopy(edited), 'artifacts': copy.deepcopy(artifacts),
            'changes': changes}


def _receipts(state, *, image_recovery=False):
    receipts = state.get('agent_receipts')
    expected = [('researcher', 1), ('fixed_information_writer', 2), ('fixed_information_writer', 4)]
    if image_recovery:
        expected.append(('fixed_information_text_review', 5))
    if not isinstance(receipts, list) or len(receipts) != len(expected):
        raise ValueError('exact_saved_draft_receipts_required')
    for row, (role, attempt) in zip(receipts, expected):
        if (not isinstance(row, dict) or row.get('role') != role or row.get('stage') != role
                or type(row.get('request_attempt')) is not int or row['request_attempt'] != attempt
                or row.get('package_id') != state.get('candidate_id')
                or not isinstance(row.get('response_id'), str) or not row['response_id']
                or row.get('stop_reason') != 'end_turn'
                or type(row.get('cost_micro_usd')) is not int or row['cost_micro_usd'] < 0):
            raise ValueError('exact_saved_draft_receipts_required')
    if len({row['response_id'] for row in receipts}) != len(expected):
        raise ValueError('exact_saved_draft_receipts_required')
    return receipts


def research_source_baseline(state, request=None):
    """Follow only the known recoveries to the original paid research bytes."""
    if not isinstance(state, dict):
        raise ValueError('saved_draft_research_ancestry_changed')
    if request and request.get('kind') == 'saved_draft_images':
        receipts = _receipts(state, image_recovery=True)
        parent = state.get('recovery', {})
        previous = parent.get('previous_state')
        if (parent.get('request', {}).get('kind') != 'saved_draft'
                or not isinstance(previous, dict) or previous.get('research') != state.get('research')
                or previous.get('candidate_id') != state.get('candidate_id')
                or previous.get('agent_receipts') != receipts[:3]
                or digest(previous) != parent['request'].get('expected_state_sha256')):
            raise ValueError('saved_draft_research_ancestry_changed')
        return research_source_baseline(previous)
    receipts = _receipts(state)
    research = state.get('research')
    if not isinstance(research, dict) or not research.get('claims'):
        raise ValueError('saved_draft_research_missing')
    current = state
    for expected_kind in ('uncertain_writer', 'saved_research'):
        recovery = current.get('recovery')
        if (not isinstance(recovery, dict)
                or recovery.get('request', {}).get('kind') != expected_kind):
            raise ValueError('saved_draft_research_ancestry_changed')
        previous = recovery.get('previous_state')
        if (not isinstance(previous, dict) or previous.get('research') != research
                or previous.get('candidate_id') != state.get('candidate_id')
                or previous.get('agent_receipts') != receipts[:2]
                or not isinstance(previous.get('sources'), list) or not previous['sources']):
            raise ValueError('saved_draft_research_ancestry_changed')
        current = previous
    sources = current['sources']
    if any(not isinstance(row, dict) or not _sha(row.get('retrieved_text_sha256')) for row in sources):
        raise ValueError('saved_draft_research_ancestry_changed')
    return copy.deepcopy(sources)


def prepare_recovery(state, request, selection, original_selection, *, now, engine):
    """Validate one exact fit/image hold without changing state or any allowance."""
    _request(request)
    images = request['kind'] == 'saved_draft_images'
    if not isinstance(state, dict) or digest(state) != request.get('expected_state_sha256'):
        raise ValueError('saved_draft_state_changed')
    if (_FORBIDDEN_STATE & set(state) or state.get('status') != 'held'
            or state.get('mode') != 'fixed-preview' or state.get('reason') != 'no_package_passed_review'
            or state.get('engine') != request.get('original_engine')
            or state.get('lane') not in {'daily', 'local'} or state['lane'] != request.get('lane')):
        raise ValueError('invalid_saved_draft_hold')
    try:
        expires = datetime.fromisoformat(state['expires_at'])
        if expires.tzinfo is None or now.tzinfo is None or expires <= now:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValueError('saved_draft_expired_or_invalid_time') from None
    audit = state.get('audit')
    if (not isinstance(audit, list) or len(audit) < 3
            or any(not isinstance(row, dict) for row in audit)
            or [row.get('event') for row in audit[-3:]] != ['researched', 'candidate_rejected', 'exhausted_candidates']
            or (audit[-2].get('reason') != 'fixed_information_caption_rights_compatible_source_unavailable'
                if images else not str(audit[-2].get('reason', '')).startswith('fixed_information_text_does_not_fit: '))
            or audit[-2].get('candidate_id') != state.get('candidate_id')
            or sum(row.get('event') == 'saved_research_recovery_authorized' for row in audit) != 1
            or sum(row.get('event') == 'uncertain_writer_recovery_authorized' for row in audit) != 1
            or sum(row.get('event') == 'saved_draft_recovery_authorized' for row in audit) != int(images)
            or any(row.get('event') == 'saved_draft_image_recovery_authorized' for row in audit)):
        raise ValueError('saved_draft_fit_failure_not_proven')
    _receipts(state, image_recovery=images)
    research_source_baseline(state, request)
    if (not isinstance(selection, dict) or not isinstance(original_selection, dict)
            or original_selection != state.get('free_selection')
            or (not images and selection != original_selection)
            or digest(selection) != request.get('selection_sha256')
            or digest(original_selection) != request.get('original_selection_sha256')
            or selection.get('candidate_id') != state.get('candidate_id')
            or selection.get('candidate_id') != request.get('candidate_id')
            or selection.get('lane') != state['lane'] or not isinstance(selection.get('source'), dict)):
        raise ValueError('saved_draft_selection_changed')
    if images:
        before, after = copy.deepcopy(original_selection), copy.deepcopy(selection)
        old_plan, new_plan = before.pop('image_plan', None), after.pop('image_plan', None)
        if (before != after or old_plan == new_plan or not isinstance(new_plan, list)
                or not 3 <= len(new_plan) <= 8
                or any(not isinstance(row, dict) or not isinstance(row.get('asset_id'), str)
                       or not row['asset_id'].strip() or not isinstance(row.get('purpose'), str)
                       or not row['purpose'].strip() for row in new_plan)):
            raise ValueError('saved_draft_only_image_plan_change_allowed')
        prior = state['recovery']['request']
        _request(prior)
        if any(request.get(key) != prior.get(key)
               for key in ('artifacts', 'edited_draft', 'edited_sha256')):
            raise ValueError('saved_draft_previously_reviewed_copy_changed')
        # This validates original artifact/copy integrity, not the missing review.
        validate_artifacts(prior, state['research'])
    validate_artifacts(request, state['research'])
    recovered = copy.deepcopy(state)
    recovered.update(status='working', reason=None, engine=engine,
        recovery={'request': copy.deepcopy(request), 'previous_state': copy.deepcopy(state)})
    recovered['audit'].append({'event': ('saved_draft_image_recovery_authorized' if images
                                      else 'saved_draft_recovery_authorized'), 'at': now.isoformat(),
        'previous_state_sha256': digest(state), 'request_sha256': digest(request)})
    return recovered


def verify_ledger(state, request, ledger, now):
    """Prove all prior attempts and unchanged reserved attempt 3, read-only."""
    from daily_budget import day_key
    _request(request)
    images = request['kind'] == 'saved_draft_images'
    receipts = _receipts(state, image_recovery=images)
    retained = request.get('retained_reservation')
    historical = state.get('recovery', {}).get('request', {}).get('retained_reservation')
    if not isinstance(retained, dict) or retained != historical:
        raise ValueError('saved_draft_retained_reservation_changed')
    original_writer_request = (state['recovery']['previous_state'].get('recovery', {}).get('request', {})
                               if images else state['recovery']['request'])
    entry = retained.get('entry')
    if (not isinstance(ledger, dict) or ledger.get('version') != 1
            or ledger.get('day') != day_key(now) or retained.get('day') != ledger['day']
            or not isinstance(ledger.get('entries'), dict) or not isinstance(entry, dict)
            or ledger['entries'].get(retained.get('id')) != entry
            or entry.get('status') != 'reserved' or entry.get('stage') != 'fixed_information_writer'
            or entry.get('bot') != 'autopilot:fixed_information_writer'
            or entry.get('package_id') != state.get('candidate_id')
            or type(entry.get('request_attempt')) is not int or entry['request_attempt'] != 3
            or original_writer_request.get('kind') != 'uncertain_writer'
            or entry.get('run_id') != str(original_writer_request.get('original_run_id'))
            or entry.get('run_attempt') != '1'
            or type(entry.get('reserved_micro_usd')) is not int or entry['reserved_micro_usd'] <= 0
            or entry.get('charged_micro_usd') != entry['reserved_micro_usd']):
        raise ValueError('saved_draft_retained_reservation_changed')
    rows = [row for row in ledger['entries'].values()
            if isinstance(row, dict) and row.get('package_id') == state.get('candidate_id')]
    attempts = [1, 2, 3, 4, 5] if images else [1, 2, 3, 4]
    if (len(rows) != len(attempts) or any(type(row.get('request_attempt')) is not int for row in rows)
            or sorted(row['request_attempt'] for row in rows) != attempts):
        raise ValueError('saved_draft_extra_or_missing_package_attempt')
    for receipt in receipts:
        row = next(row for row in rows if row['request_attempt'] == receipt['request_attempt'])
        if (row.get('stage') != receipt['role'] or row.get('status') != 'settled'
                or type(row.get('charged_micro_usd')) is not int
                or row['charged_micro_usd'] != receipt['cost_micro_usd']):
            raise ValueError('saved_draft_settled_history_changed')
        run = (state['recovery']['request'].get('original_run_id')
               if images and receipt['request_attempt'] == 4 else request.get('original_run_id'))
        if receipt['request_attempt'] >= 4 and (
                type(run) is not int or run <= 0
                or row.get('run_id') != str(run) or row.get('run_attempt') != '1'):
            raise ValueError('saved_draft_final_writer_run_changed')
    return attempts[-1]
