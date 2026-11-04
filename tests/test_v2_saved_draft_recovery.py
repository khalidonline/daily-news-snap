"""Offline recovery: exact saved writer bytes, narrow copy edits, no paid retry."""
import copy
import hashlib
import importlib
import json
import socket

import pytest

from publishing_v2.autopilot.policy import digest
from test_fixed_information_writer import draft
from test_v2_saved_research_recovery import NOW
from test_v2_uncertain_writer_recovery import data as uncertain_data


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(socket, 'socket', lambda *a, **k: pytest.fail('network forbidden'))


def encoded(value):
    text = json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + '\n'
    return {'text': text, 'sha256': hashlib.sha256(text.encode()).hexdigest()}


def fixture():
    previous, uncertain, selection, original, ledger = uncertain_data()
    for i, receipt in enumerate(previous['agent_receipts'], 1):
        receipt.update(stage=receipt['role'], request_attempt=i)
    baseline = copy.deepcopy(previous['recovery']['previous_state'])
    baseline['agent_receipts'] = copy.deepcopy(previous['agent_receipts'])
    baseline['sources'] = [{'id': 'article', 'url': 'https://example.org/article',
                            'text': 'exact evidence', 'retrieved_text_sha256': 'a' * 64}]
    previous['sources'] = copy.deepcopy(baseline['sources'])
    previous['recovery']['previous_state'] = baseline
    current = copy.deepcopy(previous)
    current['engine'] = 'latest'
    current['sources'][0]['retrieved_text_sha256'] = 'b' * 64
    current['source_drift'] = [{'source_id': 'article', 'previous_sha256': 'a' * 64,
                              'current_sha256': 'b' * 64}]
    current['recovery'] = {'request': uncertain, 'previous_state': previous}
    current['audit'].insert(2, {'event': 'uncertain_writer_recovery_authorized'})
    current['audit'][-2]['reason'] = 'fixed_information_text_does_not_fit: bullet: 3 lines exceeds 2'
    current['agent_receipts'].append({'role': 'fixed_information_writer',
        'stage': 'fixed_information_writer', 'request_attempt': 4, 'response_id': 'w4',
        'cost_micro_usd': 7, 'package_id': 'a', 'stop_reason': 'end_turn'})
    ledger['entries']['4'] = {'package_id': 'a', 'stage': 'fixed_information_writer',
        'bot': 'autopilot:fixed_information_writer', 'request_attempt': 4, 'status': 'settled',
        'charged_micro_usd': 7, 'run_id': '456', 'run_attempt': '1'}
    raw = draft()
    raw['cards'][0]['bullets'][0] = 'نصّ واضح'
    normalized = copy.deepcopy(raw)
    normalized['cards'][0]['bullets'][0] = 'نص واضح'
    raw_artifact = encoded(raw)
    artifacts = {'raw': raw_artifact, 'normalized': encoded(normalized),
        'context': encoded({'context_sha256': 'c' * 64, 'status': 'writer_saved',
                            'raw_sha256': raw_artifact['sha256']})}
    edited = copy.deepcopy(normalized)
    edited['cards'][0]['bullets'] = ['نص أقصر.']
    edited['cards'][0]['image_caption'] = 'قهوة'
    request = {'version': 1, 'kind': 'saved_draft', 'allow_saved_draft_review': True,
        'allow_source_text_drift_review': True, 'candidate_id': 'a', 'lane': 'daily',
        'original_run_id': 456, 'original_engine': 'latest',
        'expected_state_sha256': digest(current), 'selection_sha256': digest(selection),
        'original_selection_sha256': digest(original), 'artifacts': artifacts,
        'edited_draft': edited, 'edited_sha256': digest(edited),
        'retained_reservation': copy.deepcopy(uncertain['retained_reservation'])}
    return current, request, selection, original, ledger


def module():
    return importlib.import_module('publishing_v2.autopilot.saved_draft_recovery')


def recover(state, request, selection, original):
    return module().prepare_recovery(state, request, selection, original, now=NOW, engine='new')


def test_saved_edit_preserves_original_artifacts_history_and_unresolved_source_drift():
    state, request, selection, original, ledger = fixture()
    before = copy.deepcopy((state, request, ledger))
    out = recover(state, request, selection, original)
    assert out['status'] == 'working' and out['engine'] == 'new'
    assert out['recovery']['previous_state'] == state
    assert out['recovery']['request'] == request
    assert out['research'] == state['research']
    assert out['agent_receipts'] == state['agent_receipts']
    assert out['source_drift'] == state['source_drift']
    assert out['audit'][-1]['event'] == 'saved_draft_recovery_authorized'
    assert (state, request, ledger) == before
    assert module().verify_ledger(state, request, ledger, NOW) == 4
    assert module().research_source_baseline(state)[0]['retrieved_text_sha256'] == 'a' * 64
    with pytest.raises(ValueError):
        recover(out, request, selection, original)


def test_artifact_validation_returns_exact_text_and_explicit_edit_receipt():
    state, request, *_ = fixture()
    result = module().validate_artifacts(request, state['research'])
    assert result['artifacts'] == request['artifacts']
    assert result['raw']['cards'][0]['bullets'][0] == 'نصّ واضح'
    assert result['normalized']['cards'][0]['bullets'][0] == 'نص واضح'
    assert result['edited_draft'] == request['edited_draft']
    assert {c['path'] for c in result['changes']} == {
        'cards[0].bullets', 'cards[0].image_caption'}


@pytest.mark.parametrize('key', ['raw', 'context', 'normalized'])
def test_changed_artifact_bytes_rejected_even_if_valid_json(key):
    state, request, selection, original, _ = fixture()
    request['artifacts'][key]['text'] += ' '
    with pytest.raises(ValueError):
        recover(state, request, selection, original)


@pytest.mark.parametrize('mutation', [
    lambda r: r['artifacts'].__setitem__('context', encoded({'context_sha256': 'c' * 64,
        'status': 'writer_started', 'raw_sha256': r['artifacts']['raw']['sha256']})),
    lambda r: r['artifacts'].__setitem__('normalized', encoded(draft())),
    lambda r: r['edited_draft'].__setitem__('title', 'New title'),
    lambda r: r['edited_draft']['cards'][0].update(title='Other headline'),
    lambda r: r['edited_draft']['cards'][0].update(claim_ids=['c2']),
    lambda r: r['edited_draft']['cards'][0].update(image_query='tea cup'),
    lambda r: r['edited_draft']['cards'][0].update(kind='story'),
    lambda r: r['edited_draft']['cards'][0].update(bullets=[]),
    lambda r: r['edited_draft']['cards'][0].update(bullets=['point'] * 5),
    lambda r: r['edited_draft']['cards'][0].update(punch='bad\ntext'),
    lambda r: r['edited_draft']['cards'][0].update(image_caption='نصّ'),
    lambda r: r['edited_draft'].__setitem__('approved', True),
    lambda r: r['edited_draft']['cards'].append(copy.deepcopy(r['edited_draft']['cards'][0])),
    lambda r: r.update(allow_saved_draft_review=False),
    lambda r: r.update(allow_replacement_writer=True),
    lambda r: r.update(writing_limit_micro_usd=1100000),
])
def test_unknown_or_unapproved_edit_scope_rejected(mutation):
    state, request, selection, original, _ = fixture()
    mutation(request)
    # These cases exercise schema/scope checks, not the separate hash guard.
    request['edited_sha256'] = digest(request['edited_draft'])
    with pytest.raises(ValueError):
        recover(state, request, selection, original)


@pytest.mark.parametrize('change', [
    {'status': 'working'}, {'mode': 'live'}, {'information_package': {}},
    {'package': {}}, {'text_approval': {}}, {'review': {}},
    {'expires_at': '2026-11-03T00:00:00+00:00'}, {'agent_receipts': []},
    {'candidate_id': 'changed'}, {'research': {}},
])
def test_only_exact_unapproved_fit_hold_can_resume(change):
    state, request, selection, original, _ = fixture()
    state.update(change)
    request['expected_state_sha256'] = digest(state)
    with pytest.raises(ValueError):
        recover(state, request, selection, original)


def test_changed_state_selection_and_nonfit_failure_rejected():
    state, request, selection, original, _ = fixture()
    state['reason'] = 'changed'
    with pytest.raises(ValueError): recover(state, request, selection, original)
    state, request, selection, original, _ = fixture()
    selection['choice']['id'] = 'different'
    with pytest.raises(ValueError): recover(state, request, selection, original)
    state, request, selection, original, _ = fixture()
    state['audit'][-2]['reason'] = 'RuntimeError'
    request['expected_state_sha256'] = digest(state)
    with pytest.raises(ValueError): recover(state, request, selection, original)


@pytest.mark.parametrize('mutation', [
    lambda l: l['entries']['reservation'].update(status='settled'),
    lambda l: l['entries']['reservation'].update(charged_micro_usd=0),
    lambda l: l['entries']['4'].update(status='reserved'),
    lambda l: l['entries']['4'].update(charged_micro_usd=999),
    lambda l: l['entries']['4'].update(stage='fixed_information_text_review'),
    lambda l: l['entries']['4'].update(run_id='other'),
    lambda l: l['entries'].pop('4'),
    lambda l: l['entries'].__setitem__('5', dict(l['entries']['4'], request_attempt=5)),
    lambda l: l.update(day='2026-11-05'),
])
def test_changed_ambiguous_or_additional_paid_attempt_blocks(mutation):
    state, request, _, _, ledger = fixture()
    mutation(ledger)
    with pytest.raises(ValueError): module().verify_ledger(state, request, ledger, NOW)


def test_recovery_rejects_changed_research_ancestry_and_retained_proof():
    state, request, selection, original, ledger = fixture()
    state['recovery']['previous_state']['research'] = {'claims': [{'id': 'changed'}]}
    request['expected_state_sha256'] = digest(state)
    with pytest.raises(ValueError): recover(state, request, selection, original)
    state, request, _, _, ledger = fixture()
    request['retained_reservation']['entry']['charged_micro_usd'] = 1
    with pytest.raises(ValueError): module().verify_ledger(state, request, ledger, NOW)


def test_edited_copy_is_bound_to_explicit_digest_not_renormalized():
    state, request, *_ = fixture()
    request['edited_draft']['cards'][0]['punch'] = 'ختام آخر.'
    with pytest.raises(ValueError, match='edited_draft_hash_mismatch'):
        module().validate_artifacts(request, state['research'])
    request['edited_sha256'] = digest(request['edited_draft'])
    module().validate_artifacts(request, state['research'])
    request['edited_draft']['cards'][0]['punch'] = 'نصّ'
    request['edited_sha256'] = digest(request['edited_draft'])
    with pytest.raises(ValueError, match='invalid_fixed_information_text'):
        module().validate_artifacts(request, state['research'])


def test_actual_fit_of_every_card_required_before_recovery():
    state, request, selection, original, _ = fixture()
    for key in ('raw', 'normalized'):
        data = json.loads(request['artifacts'][key]['text'])
        data['cards'].append(copy.deepcopy(data['cards'][0]))
        request['artifacts'][key] = encoded(data)
    request['artifacts']['context'] = encoded({'context_sha256': 'c' * 64,
        'status': 'writer_saved', 'raw_sha256': request['artifacts']['raw']['sha256']})
    request['edited_draft']['cards'].append(copy.deepcopy(request['edited_draft']['cards'][0]))
    request['edited_draft']['cards'][1]['bullets'] = ['نص طويل جدا لا يتسع داخل البطاقة. ' * 40]
    request['edited_sha256'] = digest(request['edited_draft'])
    with pytest.raises(ValueError, match='saved_draft_text_does_not_fit'):
        recover(state, request, selection, original)


def test_exact_artifact_keys_prevent_injected_files():
    state, request, *_ = fixture()
    request['artifacts']['../../other'] = encoded({})
    with pytest.raises(ValueError, match='exact_saved_draft_artifacts_required'):
        module().validate_artifacts(request, state['research'])
