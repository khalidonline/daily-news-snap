"""Offline regression for raw copy retention and bounded, unapproved text repair."""
import copy
import hashlib
import json
import socket
import pytest
from test_fixed_information_writer import draft
from publishing_v2.autopilot import fixed_information as fixed
from publishing_v2.autopilot import fixed_preparation as preparation


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(socket, 'socket', lambda *a, **k: pytest.fail('network forbidden'))


def context():
    return {'as_of': '2026-11-04T00:00:00+03:00', 'lane': 'daily',
            'candidate': {'id': 'fixture'}, 'research': {'claims': [{'id': 'c1', 'fact': 'نصّ الدليل'}]},
            'verified_timing': {'eligible': True}, 'original_sources': {'text': 'نصّ المصدر'}}


@pytest.mark.parametrize('key,value,code,category', [
    ('punch', 'نصّ', 'U+0651', 'Mn'),
    ('image_caption', 'caption\u200f', 'U+200F', 'Cf'),
    ('title', 'title\nSECRET', 'U+000A', 'Cc'),
])
def test_field_diagnostics_never_echo_content(key, value, code, category):
    raw = draft(); raw['cards'][0][key] = value
    with pytest.raises(ValueError) as error:
        fixed.validate_draft(raw, context()['research'])
    assert f'cards[0].{key}' in str(error.value)
    assert code in str(error.value) and category in str(error.value)
    assert value not in str(error.value) and 'SECRET' not in str(error.value)


def test_normalization_only_removes_vowel_marks_and_preserves_evidence_and_letters():
    raw = draft(); raw['cards'][0]['bullets'] = ['نصّ واضح، 2026… أشياء كثيرة!']
    original = copy.deepcopy(raw)
    normalized, changes = fixed.normalize_unapproved_draft(raw)
    assert normalized['cards'][0]['bullets'] == ['نص واضح، 2026… أشياء كثيرة!']
    assert raw == original
    assert normalized['cards'][0]['claim_ids'] == raw['cards'][0]['claim_ids']
    assert changes == [{'path': 'cards[0].bullets[0]', 'index': 2, 'codepoint': 'U+0651',
                        'category': 'Mn', 'action': 'remove_arabic_vowel_mark'}]
    fixed.validate_draft(normalized, context()['research'])


@pytest.mark.parametrize('value', ['نص\u200f', '', 42, 'ا\u0654'])
def test_unsafe_text_not_silently_removed(value):
    raw = draft(); raw['cards'][0]['punch'] = value
    normalized, changes = fixed.normalize_unapproved_draft(raw)
    assert normalized == raw and changes == []
    with pytest.raises(ValueError): fixed.validate_draft(normalized, context()['research'])


class Agent:
    def __init__(self, raw): self.raw = raw; self.calls = []
    def run(self, role, data):
        self.calls.append(role)
        assert role == 'fixed_information_writer'
        return copy.deepcopy(self.raw)


def test_raw_persisted_before_schema_failure_and_reused_without_paid_writer(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    raw = draft(); raw['unexpected'] = 'private raw output'
    agent = Agent(raw); prepare = preparation.FixedInformationPreparer(agent, object())
    for _ in range(2):
        with pytest.raises(ValueError, match='unexpected_fixed_draft_fields'):
            prepare(context(), 'out')
    assert agent.calls == ['fixed_information_writer']
    assert json.loads((tmp_path/'out/fixed-writer-raw.json').read_text()) == raw
    receipt = json.loads((tmp_path/'out/fixed-writer-repair.json').read_text())
    assert receipt['status'] == 'rejected'
    assert receipt['publish_authorized'] is False and receipt['preview_allowed'] is False
    assert 'private raw output' not in json.dumps(receipt)


def test_normalized_and_hash_receipt_persist_before_actual_fit_and_review(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    raw = draft(); raw['cards'][0]['bullets'][0] = 'نصّ واضح'
    before = context(); agent = Agent(raw)
    def fit(candidate):
        assert candidate['bullets'][0] == 'نص واضح'
        out = tmp_path/'out'
        receipt = json.loads((out/'fixed-writer-repair.json').read_text())
        assert receipt['status'] == 'validated'
        for label in ('raw', 'normalized'):
            data = (out/f'fixed-writer-{label}.json').read_bytes()
            assert receipt[f'{label}_sha256'] == hashlib.sha256(data).hexdigest()
        return {'fit': False, 'violations': ['synthetic fail']}
    monkeypatch.setattr(preparation, 'prepare_text', fit)
    prepare = preparation.FixedInformationPreparer(agent, object())
    with pytest.raises(ValueError, match='does_not_fit'): prepare(before, 'out')
    assert before == context()
    assert agent.calls == ['fixed_information_writer']


def test_existing_raw_mismatch_or_missing_binding_never_triggers_writer(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path); out = tmp_path/'out'; out.mkdir()
    (out/'fixed-writer-raw.json').write_text(json.dumps(draft()))
    agent = Agent(draft())
    with pytest.raises(ValueError, match='fixed_writer_recovery'):
        preparation.FixedInformationPreparer(agent, object())(context(), 'out')
    assert agent.calls == []


def test_normalized_copy_still_requires_real_fit_and_independent_review(tmp_path, monkeypatch):
    from publishing_v2.editorial_production import TextRejected
    monkeypatch.chdir(tmp_path)
    raw = draft(); raw['cards'][0]['bullets'][0] = 'نصّ واضح'
    class RejectingReviewer(Agent):
        def run(self, role, data):
            if role == 'fixed_information_text_review':
                self.calls.append(role)
                assert data['cards'][0]['bullets'][0] == 'نص واضح'
                assert data['research'] == context()['research']
                assert data['original_sources'] == context()['original_sources']
                assert 'text_approval' not in data
                return {'checks': {}, 'reason': 'unsupported fact'}
            return super().run(role, data)
    agent = RejectingReviewer(raw)
    # Catalog compatibility is free preflight; paid visual work still follows review.
    from types import SimpleNamespace
    renderer = SimpleNamespace(image_catalog=lambda package: [{'asset_id':'fixture','license':'CC0'}])
    with pytest.raises(TextRejected):
        preparation.FixedInformationPreparer(agent, renderer)(context(), 'out')
    assert agent.calls == ['fixed_information_writer', 'fixed_information_text_review']
    assert not (tmp_path/'approved').exists()


@pytest.mark.parametrize('mutation', ['raw', 'context', 'intent'])
def test_changed_or_uncertain_saved_response_cannot_cause_another_writer(tmp_path, monkeypatch, mutation):
    monkeypatch.chdir(tmp_path)
    raw = draft(); raw['cards'][0]['punch'] = 'bad\ntext'
    agent = Agent(raw); prepare = preparation.FixedInformationPreparer(agent, object())
    with pytest.raises(ValueError): prepare(context(), 'out')
    original_bytes = (tmp_path/'out/fixed-writer-raw.json').read_bytes()
    if mutation == 'raw':
        (tmp_path/'out/fixed-writer-raw.json').write_text('{}')
    elif mutation == 'context':
        binding = context(); binding['research']['claims'][0]['fact'] = 'changed'
    else:
        (tmp_path/'out/fixed-writer-raw.json').unlink()
    with pytest.raises(ValueError, match='fixed_writer_recovery'):
        prepare(binding if mutation == 'context' else context(), 'out')
    assert agent.calls == ['fixed_information_writer']
    if mutation == 'context':
        assert (tmp_path/'out/fixed-writer-raw.json').read_bytes() == original_bytes


@pytest.mark.parametrize('raw', [None, [], 'not a JSON object'])
def test_nonobject_response_retained_without_coercion(tmp_path, monkeypatch, raw):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match='unexpected_fixed_draft_fields'):
        preparation.FixedInformationPreparer(Agent(raw), object())(context(), 'out')
    assert json.loads((tmp_path/'out/fixed-writer-raw.json').read_text()) == raw
