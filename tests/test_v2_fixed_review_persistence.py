"""Offline fixtures for durable real text review before any visual selection."""
import copy
import hashlib
import json
import socket

import pytest

from test_fixed_information_writer import draft
from test_v2_fixed_draft_recovery import context
from publishing_v2.autopilot import fixed_preparation as preparation
from publishing_v2.autopilot import fixed_information
from publishing_v2.autopilot.policy import digest
from publishing_v2.editorial_production import TEXT_CHECKS, TextRejected


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(socket, 'socket', lambda *a, **k: pytest.fail('network forbidden'))


def passing_review():
    return {'checks': dict.fromkeys(TEXT_CHECKS, True), 'repair_indices': [],
            'reason': 'Synthetic offline independent review'}


class Agent:
    def __init__(self, review=None, review_error=None, before_visual=None):
        self.review = passing_review() if review is None else review
        self.review_error = review_error
        self.before_visual = before_visual
        self.calls = []

    def run(self, role, data):
        self.calls.append(role)
        if role == 'fixed_information_writer':
            return draft()
        if role == 'fixed_information_text_review':
            assert data['original_sources'] == context()['original_sources']
            assert 'text_approval' not in data
            if self.review_error:
                raise self.review_error
            return copy.deepcopy(self.review)
        assert role == 'visual'
        if self.before_visual:
            self.before_visual()
        raise ValueError('synthetic_visual_failure')


class Renderer:
    def __init__(self, rows=None):
        self.rows = [{'asset_id': 'compatible', 'license': 'CC0'}] if rows is None else rows

    def image_catalog(self, package):
        return copy.deepcopy(self.rows)


@pytest.mark.parametrize('catalog', [[], [
    {'asset_id': 'requires_credit', 'license': 'CC BY 4.0', 'attribution_required': True},
]])
def test_incompatible_catalog_stops_before_paid_independent_review(tmp_path, catalog):
    agent = Agent()
    with pytest.raises(ValueError, match='caption_rights_compatible_source_unavailable'):
        preparation.FixedInformationPreparer(agent, Renderer(catalog))(context(), 'out')
    assert agent.calls == ['fixed_information_writer']
    assert not list((tmp_path / 'out').glob('fixed-text-*.json'))


def test_actual_approved_package_is_hash_bound_and_durable_before_visual(tmp_path):
    original = context()
    def inspect_saved():
        out = tmp_path / 'out'
        saved_raw = (out / 'fixed-text-reviewed.json').read_bytes()
        response_raw = (out / 'fixed-text-review-response.json').read_bytes()
        saved = json.loads(saved_raw)
        binding = json.loads((out / 'fixed-text-review-context.json').read_bytes())
        fixed_information.require_text_approval(saved)
        assert saved['text_approval']['review'] == passing_review()
        assert json.loads(response_raw) == passing_review()
        assert saved['cards'] == draft()['cards']
        assert binding['context_sha256'] == digest(original)
        assert binding['input_sha256'] == saved['text_approval']['input_sha256']
        assert binding['review_response_sha256'] == hashlib.sha256(response_raw).hexdigest()
        assert binding['reviewed_package_sha256'] == hashlib.sha256(saved_raw).hexdigest()
        assert binding['status'] == 'text_review_approved'
        assert binding['approved'] is False
        assert binding['publish_authorized'] is False and binding['preview_allowed'] is False
    agent = Agent(before_visual=inspect_saved)
    with pytest.raises(ValueError, match='synthetic_visual_failure'):
        preparation.FixedInformationPreparer(agent, Renderer())(original, 'out')
    inspect_saved()
    assert original == context()
    assert agent.calls == ['fixed_information_writer', 'fixed_information_text_review', 'visual']
    assert not (tmp_path / 'approved').exists()


@pytest.mark.parametrize('response', [
    {'checks': {}, 'repair_indices': [0], 'reason': 'Unsupported assertion'},
    ['malformed', 'response'],
])
def test_rejected_response_preserved_exactly_without_approval(tmp_path, response):
    agent = Agent(review=response)
    prep = preparation.FixedInformationPreparer(agent, Renderer())
    with pytest.raises(TextRejected):
        prep(context(), 'out')
    out = tmp_path / 'out'
    response_raw = (out / 'fixed-text-review-response.json').read_bytes()
    assert json.loads(response_raw) == response
    binding = json.loads((out / 'fixed-text-review-context.json').read_bytes())
    assert binding['status'] == 'text_review_rejected'
    assert binding['review_response_sha256'] == hashlib.sha256(response_raw).hexdigest()
    assert not (out / 'fixed-text-reviewed.json').exists()
    with pytest.raises(ValueError, match='fixed_text_review'):
        prep(context(), 'out')
    assert agent.calls == ['fixed_information_writer', 'fixed_information_text_review']


def test_uncertain_review_call_retains_intent_and_cannot_be_retried(tmp_path):
    agent = Agent(review_error=TimeoutError('synthetic uncertain provider outcome'))
    prep = preparation.FixedInformationPreparer(agent, Renderer())
    with pytest.raises(TimeoutError):
        prep(context(), 'out')
    out = tmp_path / 'out'
    binding = json.loads((out / 'fixed-text-review-context.json').read_bytes())
    assert binding['status'] == 'review_started'
    assert binding['context_sha256'] == digest(context())
    assert not (out / 'fixed-text-reviewed.json').exists()
    with pytest.raises(ValueError, match='fixed_text_review'):
        prep(context(), 'out')
    assert agent.calls == ['fixed_information_writer', 'fixed_information_text_review']


@pytest.mark.parametrize('name', [
    'fixed-text-review-context.json', 'fixed-text-review-response.json', 'fixed-text-reviewed.json',
])
@pytest.mark.parametrize('symlink', [False, True])
def test_any_prior_or_unsafe_review_artifact_blocks_all_paid_calls(tmp_path, name, symlink):
    out = tmp_path / 'out'
    out.mkdir()
    target = out / name
    if symlink:
        original = tmp_path / 'original'
        original.write_text('retained bytes')
        target.symlink_to(original)
    else:
        target.write_text('retained bytes')
    agent = Agent()
    with pytest.raises(ValueError, match='fixed_text_review'):
        preparation.FixedInformationPreparer(agent, Renderer())(context(), 'out')
    assert agent.calls == []
    assert target.read_text() == 'retained bytes'


def test_visual_failure_retry_cannot_repeat_review_or_replace_artifacts(tmp_path):
    agent = Agent()
    prep = preparation.FixedInformationPreparer(agent, Renderer())
    with pytest.raises(ValueError, match='synthetic_visual_failure'):
        prep(context(), 'out')
    out = tmp_path / 'out'
    before = {path.name: path.read_bytes() for path in out.iterdir()}
    changed = context()
    changed['original_sources']['text'] = 'Changed evidence'
    for fresh in (context(), changed):
        with pytest.raises(ValueError, match='fixed_text_review'):
            prep(fresh, 'out')
    assert {path.name: path.read_bytes() for path in out.iterdir()} == before
    assert agent.calls == ['fixed_information_writer', 'fixed_information_text_review', 'visual']


@pytest.mark.parametrize('name,status', [
    ('fixed-text-review-response.json', 'review_started'),
    ('fixed-text-reviewed.json', 'review_response_saved'),
])
def test_interrupted_atomic_result_install_cannot_trigger_retry(tmp_path, monkeypatch, name, status):
    original_link = preparation.os.link
    def interrupted_link(source, destination):
        if destination.name == name:
            raise OSError('synthetic failed install')
        return original_link(source, destination)
    monkeypatch.setattr(preparation.os, 'link', interrupted_link)
    agent = Agent()
    prep = preparation.FixedInformationPreparer(agent, Renderer())
    with pytest.raises(OSError, match='synthetic failed install'):
        prep(context(), 'out')
    out = tmp_path / 'out'
    binding = json.loads((out / 'fixed-text-review-context.json').read_bytes())
    assert binding['status'] == status
    assert not (out / name).exists()
    assert not list(out.glob('.pending-fixed-text-*'))
    if status == 'review_response_saved':
        assert json.loads((out / 'fixed-text-review-response.json').read_bytes()) == passing_review()
    with pytest.raises(ValueError, match='fixed_text_review'):
        prep(context(), 'out')
    assert agent.calls == ['fixed_information_writer', 'fixed_information_text_review']


def test_concurrent_review_intent_is_not_overwritten_or_called(tmp_path, monkeypatch):
    original_link = preparation.os.link
    def competing_link(source, destination):
        if destination.name == 'fixed-text-review-context.json':
            destination.write_text('competing durable intent')
        return original_link(source, destination)
    monkeypatch.setattr(preparation.os, 'link', competing_link)
    agent = Agent()
    with pytest.raises(ValueError, match='fixed_text_review'):
        preparation.FixedInformationPreparer(agent, Renderer())(context(), 'out')
    out = tmp_path / 'out'
    assert (out / 'fixed-text-review-context.json').read_text() == 'competing durable intent'
    assert not list(out.glob('.pending-fixed-text-*'))
    assert agent.calls == ['fixed_information_writer']


def test_preflight_returns_exact_review_and_visual_payloads_without_calls_or_writes(tmp_path):
    agent = Agent()
    prep = preparation.FixedInformationPreparer(agent, Renderer())
    result = prep.preflight(context(), draft())
    assert result['package']['cards'] == draft()['cards']
    assert 'original_sources' not in result['package']
    assert result['review_payload']['original_sources'] == context()['original_sources']
    assert result['review_payload']['cards'] == draft()['cards']
    assert result['visual_payload'] == {
        'cards': draft()['cards'], 'options': [{'asset_id': 'compatible', 'license': 'CC0'}],
        'fixed_images': [], 'repair': {},
    }
    assert result['catalog'] == result['visual_payload']['options']
    assert agent.calls == [] and list(tmp_path.iterdir()) == []


def test_preflight_catalog_is_reused_exactly_and_return_value_cannot_mutate_it(tmp_path):
    class ChangingRenderer(Renderer):
        def image_catalog(self, package):
            rows = super().image_catalog(package)
            self.rows = []
            return rows
    class CheckingAgent(Agent):
        def run(self, role, data):
            if role == 'visual':
                assert data['options'] == [{'asset_id': 'compatible', 'license': 'CC0'}]
                assert data['cards'] == draft()['cards']
            return super().run(role, data)
    agent = CheckingAgent()
    prep = preparation.FixedInformationPreparer(agent, ChangingRenderer())
    plan = prep.preflight(context(), draft())
    plan['catalog'].clear()
    plan['visual_payload']['options'].clear()
    plan['package']['cards'].clear()
    with pytest.raises(ValueError, match='synthetic_visual_failure'):
        prep(context(), 'out')
    assert agent.calls == ['fixed_information_writer', 'fixed_information_text_review', 'visual']


def test_changed_preflight_context_stops_before_any_paid_call(tmp_path):
    agent = Agent()
    prep = preparation.FixedInformationPreparer(agent, Renderer())
    prep.preflight(context(), draft())
    changed = context()
    changed['original_sources']['text'] = 'Different evidence'
    with pytest.raises(ValueError, match='fixed_preflight_binding_mismatch'):
        prep(changed, 'out')
    assert agent.calls == []
    assert not (tmp_path / 'out').exists()
