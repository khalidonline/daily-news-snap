"""Saved fit-failed drafts resume only independent review, never generation."""
import base64
import copy
import json
import socket
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from publishing_v2.autopilot.policy import digest

NOW = datetime(2026, 11, 4, 13, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(socket, 'socket', lambda *a, **k: pytest.fail('network forbidden'))


def test_loader_accepts_saved_draft_only_with_immutable_failed_run(tmp_path, monkeypatch):
    from publishing_v2.autopilot.zero_call_recovery import load_recovery
    monkeypatch.chdir(tmp_path)
    original = {'version': 1, 'lane': 'daily', 'candidate_id': 'a'}
    request = {'kind': 'saved_draft', 'lane': 'daily', 'original_run_id': 123,
               'original_head_sha': 'a' * 40,
               'original_selection_path': 'editorial/selected/test.json',
               'original_selection_sha256': digest(original)}
    path = tmp_path / 'editorial/recovery/request.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(request))
    class Journal:
        conclusion = 'failure'
        def call(self, path):
            if path == '/actions/runs/123':
                return {'head_sha': 'a' * 40, 'event': 'workflow_dispatch',
                        'status': 'completed', 'conclusion': self.conclusion,
                        'path': '.github/workflows/publishing-v2-fixed-preview.yml',
                        'repository': {'full_name': 'khalidonline/daily-news-snap'}}
            assert path == '/contents/editorial/selected/test.json?ref=' + 'a' * 40
            return {'content': base64.b64encode(json.dumps(original).encode()).decode()}
    journal = Journal()
    assert load_recovery(path, journal, mode='fixed-preview', lane='daily') == (request, original)
    journal.conclusion = 'success'
    with pytest.raises(ValueError, match='original_failed_preview_run_required'):
        load_recovery(path, journal, mode='fixed-preview', lane='daily')


def agent_fixture(text='{}'):
    from daily_budget import Ledger
    from publishing_v2.autopilot.agents import Agents
    from test_v2_autopilot_adapters import Store
    calls = []
    store = Store()
    ledger = Ledger(store, now=lambda: NOW)
    def transport(*args):
        calls.append(args)
        return {'status_code': 200, 'body': {'id': 'review-' + str(len(calls)),
                'stop_reason': 'end_turn', 'usage': {'input_tokens': 10, 'output_tokens': 10},
                'content': [{'type': 'text', 'text': text}]}}
    agent = Agents(env={'ANTHROPIC_API_KEY': 'offline', 'PACKAGE_ID': 'a'},
                   ledger=ledger, transport=transport)
    agent.saved_draft_recovery_only = True
    agent.request_attempt_offset = 4
    return agent, store, calls


@pytest.mark.parametrize('role', ['fixed_information_writer', 'researcher', 'writer',
                                  'card_repair', 'reviewer', 'image_check'])
def test_saved_draft_agent_rejects_every_nonreview_role_before_ledger_or_transport(role):
    agent, store, calls = agent_fixture()
    with pytest.raises(ValueError, match='saved_draft_review_roles_only'):
        agent.run(role, {})
    assert store.row is None
    assert calls == []


@pytest.mark.parametrize('role', ['fixed_information_text_review', 'visual'])
def test_saved_draft_review_has_one_provider_attempt_even_for_invalid_json(role):
    from publishing_v2.autopilot.agents import InvalidAgentResponse
    agent, store, calls = agent_fixture('{bad json')
    with pytest.raises(InvalidAgentResponse):
        agent.run(role, {})
    assert len(calls) == 1
    assert len(agent.receipts) == 1
    assert agent.receipts[0]['request_attempt'] == 5
    assert [row['request_attempt'] for row in store.row['entries'].values()] == [5]


def test_saved_draft_roles_are_each_single_use_in_one_process():
    agent, store, calls = agent_fixture()
    assert agent.run('fixed_information_text_review', {}) == {}
    assert agent.run('visual', {}) == {}
    for role in ('fixed_information_text_review', 'visual'):
        with pytest.raises(ValueError, match='saved_draft_review_already_attempted'):
            agent.run(role, {})
    assert len(calls) == 2
    assert sorted(row['request_attempt'] for row in store.row['entries'].values()) == [5, 6]
    assert not hasattr(agent.ledger, 'package_writing_authorization')


def pipeline_fixture():
    from daily_budget import day_key
    from test_v2_saved_research_recovery import pipeline_fixture as research_pipeline
    from test_v2_saved_draft_recovery import fixture
    case, pipeline, baseline, _ = research_pipeline()
    state, request, _, _, ledger = fixture()
    ancestor = state
    while ancestor:
        for key in ('candidate', 'candidate_id', 'research', 'sources', 'free_selection',
                    'timing', 'started_at', 'expires_at'):
            ancestor[key] = copy.deepcopy(baseline[key])
        ancestor = ancestor.get('recovery', {}).get('previous_state')
    state.pop('source_drift', None)
    request.update(expected_state_sha256=digest(state),
                   selection_sha256=digest(pipeline.free_selection),
                   original_selection_sha256=digest(pipeline.free_selection))
    day = day_key(pipeline.now())
    ledger['day'] = day
    request['retained_reservation']['day'] = day
    state['recovery']['request']['retained_reservation']['day'] = day
    request['expected_state_sha256'] = digest(state)
    pipeline.agent.ledger = SimpleNamespace(store=SimpleNamespace(
        read=lambda requested_day: ('sha', copy.deepcopy(ledger))))
    pipeline.saved_research_recovery = (request, copy.deepcopy(pipeline.free_selection))
    pipeline.store.save(state)
    class Prepare:
        def __init__(self): self.contexts = []
        def __call__(self, context, output):
            self.contexts.append(copy.deepcopy(context))
            return {'preview_allowed': False, 'publish_authorized': False}
    pipeline.fixed_prepare = Prepare()
    return case, pipeline, state, request, ledger


def test_saved_draft_pipeline_preserves_history_and_routes_only_review_once():
    case, pipeline, old, request, ledger = pipeline_fixture()
    before = copy.deepcopy(ledger)
    try:
        result = pipeline.run('daily', 'fixed-preview')
        assert result['status'] == 'awaiting_information_review', result
        assert result['recovery']['previous_state'] == old
        assert result['agent_receipts'] == old['agent_receipts']
        assert pipeline.agent.request_attempt_offset == 4
        assert pipeline.agent.saved_draft_recovery_only is True
        assert not getattr(pipeline.agent, 'fixed_writer_recovery_once', False)
        assert not hasattr(pipeline.agent.ledger, 'package_writing_authorization')
        assert pipeline.fixed_prepare.saved_draft_recovery == request
        assert pipeline.fixed_prepare.contexts[0]['research'] == old['research']
        assert ledger == before and case.agent.calls == [] and case.sent == []
        with pytest.raises(ValueError):
            pipeline.run('daily', 'fixed-preview')
        assert len(pipeline.fixed_prepare.contexts) == 1
    finally:
        case.doCleanups()


@pytest.mark.parametrize('failure,reason', [
    ('source', 'selected_source_unverified'),
    ('evidence', 'attention_article_not_retrieved'),
    ('image', 'insufficient_subject_visuals_before_recovery'),
    ('rejection', 'saved_research_candidate_no_longer_eligible'),
    ('ledger', 'saved_draft_settled_history_changed'),
    ('artifact', 'saved_draft_artifact_hash_mismatch'),
])
def test_saved_draft_preflight_failure_never_consumes_hold(failure, reason):
    case, pipeline, old, request, ledger = pipeline_fixture()
    try:
        if failure == 'source':
            pipeline.sources.resolve_selection = lambda *args: None
        elif failure == 'evidence':
            pipeline.sources.research = lambda *args: []
        elif failure == 'image':
            pipeline.render.screen_visuals = lambda *args: False
        elif failure == 'rejection':
            pipeline.published_memory = SimpleNamespace(reason=lambda *args: 'already_published')
        elif failure == 'ledger':
            ledger['entries']['4']['status'] = 'reserved'
        elif failure == 'artifact':
            request['artifacts']['raw']['text'] += ' '
        with pytest.raises(ValueError, match=reason):
            pipeline.run('daily', 'fixed-preview')
        assert pipeline.store.read() == old
        assert case.agent.calls == [] and case.sent == []
        assert pipeline.fixed_prepare.contexts == []
        assert not hasattr(pipeline.agent.ledger, 'package_writing_authorization')
    finally:
        case.doCleanups()


def test_saved_draft_cas_uncertainty_stops_before_review_or_generation():
    from publishing_v2.autopilot.pipeline import PersistenceError
    case, pipeline, old, _, _ = pipeline_fixture()
    try:
        def fail_save(*args): raise OSError('uncertain')
        pipeline.store.save = fail_save
        with pytest.raises(PersistenceError):
            pipeline.run('daily', 'fixed-preview')
        assert pipeline.store.read() == old
        assert pipeline.fixed_prepare.contexts == [] and case.agent.calls == []
    finally:
        case.doCleanups()


def test_saved_draft_keeps_original_research_drift_and_passes_fresh_full_source():
    case, pipeline, old, request, _ = pipeline_fixture()
    try:
        baseline_hash = old['sources'][0]['retrieved_text_sha256']
        old['sources'][0]['retrieved_text_sha256'] = 'b' * 64
        old['recovery']['previous_state']['sources'][0]['retrieved_text_sha256'] = 'b' * 64
        request['expected_state_sha256'] = digest(old)
        pipeline.store.save(old)
        original_research = pipeline.sources.research
        def fresh_sources(*args):
            rows = copy.deepcopy(original_research(*args))
            rows[0]['text'] += ' Newly fetched surrounding article context.'
            return rows
        pipeline.sources.research = fresh_sources
        result = pipeline.run('daily', 'fixed-preview')
        assert result['status'] == 'awaiting_information_review', result
        context = pipeline.fixed_prepare.contexts[0]
        assert context['source_drift'][0]['previous_sha256'] == baseline_hash
        assert context['source_drift'] == result['source_drift']
        assert context['original_sources'][0]['text'].endswith('Newly fetched surrounding article context.')
    finally:
        case.doCleanups()


def test_runtime_routes_saved_draft_to_recovery_review_without_generation(tmp_path, monkeypatch):
    from pathlib import Path
    from daily_budget import day_key
    from publishing_v2.autopilot import runtime, fixed_preparation, published_memory, candidate_memory
    from test_v2_autopilot import MemoryStore
    case, pipeline, old, request, _ = pipeline_fixture()
    try:
        settings = (Path.cwd() / 'publishing_v2/design-settings.json').read_bytes()
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'publishing_v2').mkdir()
        (tmp_path / 'publishing_v2/design-settings.json').write_bytes(settings)
        selection_path = tmp_path / 'editorial/selected/test.json'
        selection_path.parent.mkdir(parents=True)
        selection_path.write_text(json.dumps(pipeline.free_selection))
        request.update(original_head_sha='a' * 40, original_selection_path='editorial/selected/test.json')
        request_path = tmp_path / 'editorial/recovery/request.json'
        request_path.parent.mkdir()
        request_path.write_text(json.dumps(request))
        def call(path):
            if path == '/actions/runs/456':
                return {'head_sha': 'a' * 40, 'event': 'workflow_dispatch', 'status': 'completed',
                        'conclusion': 'failure', 'path': '.github/workflows/publishing-v2-fixed-preview.yml',
                        'repository': {'full_name': 'khalidonline/daily-news-snap'}}
            assert path == '/contents/editorial/selected/test.json?ref=' + 'a' * 40
            return {'content': base64.b64encode(json.dumps(pipeline.free_selection).encode()).decode()}
        pipeline.store.call = call
        slot = f'autopilot-{day_key(pipeline.now())}-daily-fixed-preview'
        journals = {slot: pipeline.store}
        def journal(name): return journals.setdefault(name, MemoryStore())
        monkeypatch.setenv('GITHUB_REPOSITORY', 'khalidonline/daily-news-snap')
        monkeypatch.setenv('GITHUB_REF', 'refs/heads/main')
        monkeypatch.setattr(runtime, 'GitHubJournal', journal)
        monkeypatch.setattr(runtime, 'GitHubStore', lambda *a: None)
        monkeypatch.setattr(runtime, 'Ledger', lambda *a, **kw: SimpleNamespace(limit_micro_usd=None))
        monkeypatch.setattr(runtime, 'Agents', lambda **kw: pipeline.agent)
        monkeypatch.setattr(runtime, 'Sources', lambda **kw: pipeline.sources)
        monkeypatch.setattr(runtime, 'Renderer', lambda *a: pipeline.render)
        monkeypatch.setattr(runtime, 'datetime', SimpleNamespace(now=lambda *a: pipeline.now()))
        monkeypatch.setattr(runtime, 'engine_id', lambda: 'runtime-new')
        monkeypatch.setattr(fixed_preparation, 'FixedInformationPreparer', lambda *a: pipeline.fixed_prepare)
        monkeypatch.setattr(published_memory, 'PublishedMemory', lambda *a: SimpleNamespace(
            import_manual=lambda *a: None, reason=lambda *a: None))
        monkeypatch.setattr(candidate_memory, 'CandidateMemory', lambda *a: SimpleNamespace(
            reason=lambda *a: None, record=lambda *a: None))
        pipeline.agent.receipts = []
        monkeypatch.setattr('sys.argv', ['runtime', '--mode', 'fixed-preview', '--lane', 'daily',
            '--selection', str(selection_path), '--recover-held', str(request_path), '--output', 'runtime-out'])
        assert runtime.main() == 0
        result = json.loads((tmp_path / 'runtime-out/daily.json').read_text())
        assert result['status'] == 'awaiting_information_review'
        assert result['recovery']['previous_state'] == old
        assert pipeline.agent.saved_draft_recovery_only is True
        assert pipeline.agent.request_attempt_offset == 4
        assert pipeline.fixed_prepare.saved_draft_recovery == request
        assert case.agent.calls == [] and case.sent == []
        assert journals['autopilot-readiness'].read() == {}
        assert 'autopilot-ready-inventory' not in journals
    finally:
        case.doCleanups()


@pytest.mark.parametrize('resolve_drift', [True, False])
def test_saved_draft_real_preparer_and_budgeted_review_enforce_fresh_source_resolution(
        tmp_path, monkeypatch, resolve_drift):
    import hashlib
    import io
    from pathlib import Path
    from PIL import Image
    from daily_budget import Ledger
    from publishing_v2.autopilot.agents import Agents
    from publishing_v2.autopilot import fixed_preparation
    from publishing_v2.editorial_production import TEXT_CHECKS
    from test_v2_autopilot_adapters import Store
    case, pipeline, old, request, history = pipeline_fixture()
    try:
        settings = (Path.cwd() / 'publishing_v2/design-settings.json').read_bytes()
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'publishing_v2').mkdir()
        (tmp_path / 'publishing_v2/design-settings.json').write_bytes(settings)
        pipeline.output = tmp_path / 'out'
        original_research = pipeline.sources.research
        def current_sources(*args):
            rows = copy.deepcopy(original_research(*args))
            rows[0]['text'] += ' Freshly retrieved full article context.'
            return rows
        pipeline.sources.research = current_sources
        store = Store()
        store.row = copy.deepcopy(history)
        store.row['limit_micro_usd'] = None
        before = copy.deepcopy(store.row['entries'])
        ledger = Ledger(store, now=pipeline.now, limit_micro_usd=None)
        roles = []
        def transport(method, url, headers, payload):
            role = ledger.context['stage']
            roles.append(role)
            data = json.loads(payload['messages'][0]['content'][-1]['text'])
            if role == 'fixed_information_text_review':
                assert data['cards'] == request['edited_draft']['cards']
                assert data['original_sources'][0]['text'].endswith('Freshly retrieved full article context.')
                assert data['source_drift'][0]['previous_sha256'] == old['sources'][0]['retrieved_text_sha256']
                checks = dict.fromkeys(TEXT_CHECKS, True)
                checks['source_drift_resolved'] = resolve_drift
                result = {'checks': checks, 'repair_indices': [], 'reason': 'Offline independent review fixture'}
            elif role == 'visual':
                result = {'image_ids': ['0']}
            else:
                pytest.fail('Unexpected generation role: ' + role)
            return {'status_code': 200, 'body': {'id': 'fixture-' + role, 'stop_reason': 'end_turn',
                    'usage': {'input_tokens': 10, 'output_tokens': 10},
                    'content': [{'type': 'text', 'text': json.dumps(result)}]}}
        pipeline.agent = Agents(env={'ANTHROPIC_API_KEY': 'offline', 'PACKAGE_ID': 'a'},
                                ledger=ledger, transport=transport)
        buffer = io.BytesIO()
        Image.new('RGB', (1200, 800), 'blue').save(buffer, 'JPEG')
        image_bytes = buffer.getvalue()
        image = {'asset_id': '0', 'license': 'CC0', 'sha256': hashlib.sha256(image_bytes).hexdigest()}
        screen = pipeline.render.screen_visuals
        class Renderer:
            screen_visuals = staticmethod(screen)
            def image_catalog(self, package): return [image]
        pipeline.render = Renderer()
        pipeline.fixed_prepare = fixed_preparation.FixedInformationPreparer(pipeline.agent, pipeline.render)
        monkeypatch.setattr(fixed_preparation, 'download_image', lambda *a, **k: image_bytes)
        result = pipeline.run('daily', 'fixed-preview')
        assert result['recovery']['previous_state'] == old
        for ident, entry in before.items():
            assert store.row['entries'][ident] == entry
        assert store.row['entries']['reservation']['status'] == 'reserved'
        assert not hasattr(ledger, 'package_writing_authorization')
        assert case.sent == []
        expected_roles = ['fixed_information_text_review', 'visual'] if resolve_drift else ['fixed_information_text_review']
        assert roles == expected_roles
        assert [r['request_attempt'] for r in pipeline.agent.receipts] == ([5, 6] if resolve_drift else [5])
        if not resolve_drift:
            assert result['status'] == 'held'
            assert 'information_package' not in result
            assert not (tmp_path / 'approved').exists()
            return
        assert result['status'] == 'awaiting_information_review', result
        handoff = result['information_package']
        assert handoff['publish_authorized'] is False and handoff['preview_allowed'] is False
        package = tmp_path / handoff['package']
        assert (package / 'card-00.png').is_file()
        assert json.loads((package / 'manifest.json').read_text())['approved'] is False
        assert json.loads((package / 'archive-approval.json').read_text())['approved'] is False
        assert not (package / 'prepared.json').exists()
        assert not (package / 'preview-receipt.json').exists()
        for key, artifact in request['artifacts'].items():
            assert (pipeline.output / f'a/fixed/fixed-writer-{key}.json').read_bytes() == artifact['text'].encode()
        edited = json.loads((pipeline.output / 'a/fixed/fixed-editorial-draft.json').read_text())
        assert edited == request['edited_draft']
    finally:
        case.doCleanups()
