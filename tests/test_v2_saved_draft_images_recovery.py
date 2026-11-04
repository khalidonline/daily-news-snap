"""One explicit image-plan repair after a settled but unretained text review."""
import copy
import socket

import pytest

from publishing_v2.autopilot import saved_draft_recovery as recovery
from publishing_v2.autopilot.policy import digest
from test_v2_saved_draft_recovery import fixture as draft_fixture
from test_v2_saved_research_recovery import NOW


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(socket, 'socket', lambda *a, **k: pytest.fail('network forbidden'))


def fixture():
    old, prior_request, original, _, ledger = draft_fixture()
    original['image_plan'] = [{'asset_id': str(i), 'purpose': 'subject image'} for i in range(3)]
    old['free_selection'] = copy.deepcopy(original)
    prior_request.update(expected_state_sha256=digest(old),
        selection_sha256=digest(original), original_selection_sha256=digest(original))
    current = copy.deepcopy(old)
    current['engine'] = 'reviewed-engine'
    current['recovery'] = {'request': copy.deepcopy(prior_request), 'previous_state': copy.deepcopy(old)}
    current['audit'].insert(-3, {'event': 'saved_draft_recovery_authorized'})
    current['audit'][-2]['reason'] = 'fixed_information_caption_rights_compatible_source_unavailable'
    current['agent_receipts'].append({'role': 'fixed_information_text_review',
        'stage': 'fixed_information_text_review', 'request_attempt': 5, 'response_id': 'review5',
        'cost_micro_usd': 61478, 'package_id': 'a', 'stop_reason': 'end_turn'})
    ledger['entries']['5'] = {'package_id': 'a', 'stage': 'fixed_information_text_review',
        'bot': 'autopilot:fixed_information_text_review', 'request_attempt': 5,
        'status': 'settled', 'charged_micro_usd': 61478, 'run_id': '789', 'run_attempt': '1'}
    selection = copy.deepcopy(original)
    selection['image_plan'] = [{'asset_id': str(i), 'purpose': 'compatible subject image'} for i in range(3, 6)]
    request = copy.deepcopy(prior_request)
    request.pop('allow_saved_draft_review')
    request.update(kind='saved_draft_images', allow_saved_draft_image_review=True,
        original_engine=current['engine'], original_run_id=789,
        expected_state_sha256=digest(current), selection_sha256=digest(selection))
    return current, request, selection, original, ledger


def prepare(state, request, selection, original):
    return recovery.prepare_recovery(state, request, selection, original, now=NOW, engine='new')


def test_image_only_continuation_preserves_copy_receipts_original_sources_and_budget():
    state, request, selection, original, ledger = fixture()
    before = copy.deepcopy((state, request, ledger))
    result = prepare(state, request, selection, original)
    assert result['status'] == 'working'
    assert result['recovery']['previous_state'] == state
    assert result['recovery']['request'] == request
    assert result['agent_receipts'] == state['agent_receipts']
    assert result['audit'][-1]['event'] == 'saved_draft_image_recovery_authorized'
    assert result['source_drift'] == state['source_drift']
    assert recovery.research_source_baseline(state, request)[0]['retrieved_text_sha256'] == 'a' * 64
    assert recovery.verify_ledger(state, request, ledger, NOW) == 5
    assert (state, request, ledger) == before
    assert 'text_approval' not in result
    with pytest.raises(ValueError): prepare(result, request, selection, original)


@pytest.mark.parametrize('mutation', [
    lambda r, s: r['edited_draft']['cards'][0].update(punch='Different closing'),
    lambda r, s: r['artifacts']['raw'].update(text=r['artifacts']['raw']['text'] + ' '),
    lambda r, s: s['choice'].update(id='different'),
    lambda r, s: s.update(source={'url': 'https://example.org/different'}),
    lambda r, s: s.update(story=[]),
    lambda r, s: s.update(timing={'eligible': True}),
    lambda r, s: s.update(image_plan=[]),
    lambda r, s: r.update(allow_saved_draft_image_review=False),
    lambda r, s: r.update(allow_replacement_writer=True),
])
def test_only_new_image_plan_is_permitted_even_with_recomputed_hashes(mutation):
    state, request, selection, original, _ = fixture()
    mutation(request, selection)
    request['selection_sha256'] = digest(selection)
    request['edited_sha256'] = digest(request['edited_draft'])
    with pytest.raises(ValueError): prepare(state, request, selection, original)


def test_unchanged_image_plan_and_unbound_old_selection_cannot_retry_review():
    state, request, selection, original, _ = fixture()
    request['selection_sha256'] = digest(original)
    with pytest.raises(ValueError): prepare(state, request, original, original)
    state, request, selection, original, _ = fixture()
    original['choice']['id'] = 'changed'
    request['original_selection_sha256'] = digest(original)
    with pytest.raises(ValueError): prepare(state, request, selection, original)


@pytest.mark.parametrize('change', [
    {'reason': 'another_failure'}, {'status': 'working'}, {'text_approval': {}},
    {'information_package': {}}, {'package': {}}, {'paths': []},
])
def test_exact_held_postreview_phase_only(change):
    state, request, selection, original, _ = fixture()
    state.update(change)
    request['expected_state_sha256'] = digest(state)
    with pytest.raises(ValueError): prepare(state, request, selection, original)


@pytest.mark.parametrize('reason', ['fixed_information_text_does_not_fit: bullet',
                                 'RuntimeError', 'incomplete_fixed_visual_selection'])
def test_other_failure_stages_cannot_spend_a_second_review(reason):
    state, request, selection, original, _ = fixture()
    state['audit'][-2]['reason'] = reason
    request['expected_state_sha256'] = digest(state)
    with pytest.raises(ValueError): prepare(state, request, selection, original)


@pytest.mark.parametrize('mutation', [
    lambda ledger: ledger['entries']['5'].update(status='reserved'),
    lambda ledger: ledger['entries']['5'].update(charged_micro_usd=0),
    lambda ledger: ledger['entries']['5'].update(stage='visual'),
    lambda ledger: ledger['entries']['5'].update(run_id='different'),
    lambda ledger: ledger['entries']['4'].update(run_id='789'),
    lambda ledger: ledger['entries']['reservation'].update(status='settled'),
    lambda ledger: ledger['entries'].__setitem__('6', dict(ledger['entries']['5'], request_attempt=6)),
])
def test_receipt_and_ledger_proof_must_preserve_all_five_attempts(mutation):
    state, request, _, _, ledger = fixture()
    mutation(ledger)
    with pytest.raises(ValueError): recovery.verify_ledger(state, request, ledger, NOW)


def test_old_request_binding_cannot_be_rewritten_to_authorize_new_copy():
    state, request, selection, original, _ = fixture()
    state['recovery']['request']['edited_draft']['cards'][0]['punch'] = 'changed'
    request['expected_state_sha256'] = digest(state)
    with pytest.raises(ValueError): prepare(state, request, selection, original)


def test_image_recovery_is_single_use_even_if_a_later_hold_has_the_same_reason():
    state, request, selection, original, _ = fixture()
    state['audit'].insert(-3, {'event': 'saved_draft_image_recovery_authorized'})
    request['expected_state_sha256'] = digest(state)
    with pytest.raises(ValueError): prepare(state, request, selection, original)


def test_artifact_reformatting_cannot_change_previously_reviewed_inputs():
    import hashlib
    state, request, selection, original, _ = fixture()
    artifact = request['artifacts']['normalized']
    artifact['text'] += ' '
    artifact['sha256'] = hashlib.sha256(artifact['text'].encode()).hexdigest()
    # Individually valid JSON and SHA, but not the original request's exact bytes.
    with pytest.raises(ValueError, match='previously_reviewed_copy_changed'):
        prepare(state, request, selection, original)


def test_image_continuation_needs_exact_settled_review_receipt_not_just_writer_history():
    state, request, selection, original, _ = fixture()
    state['agent_receipts'] = state['agent_receipts'][:3]
    request['expected_state_sha256'] = digest(state)
    with pytest.raises(ValueError): prepare(state, request, selection, original)


def test_ancestor_state_cannot_be_replaced_while_current_digest_is_recomputed():
    state, request, selection, original, _ = fixture()
    state['recovery']['previous_state']['research'] = {'claims': [{'id': 'c1', 'fact': 'changed'}]}
    request['expected_state_sha256'] = digest(state)
    with pytest.raises(ValueError, match='ancestry_changed'):
        prepare(state, request, selection, original)
