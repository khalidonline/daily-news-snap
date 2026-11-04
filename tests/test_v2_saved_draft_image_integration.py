"""Image-plan-only continuation: free catalog and complete budget preflight."""
import copy
import json
import socket
from types import SimpleNamespace

import pytest

from publishing_v2.autopilot.policy import digest


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(socket, 'socket', lambda *a, **k: pytest.fail('network forbidden'))


@pytest.mark.parametrize('role', ['fixed_information_text_review', 'visual'])
def test_stage_estimate_matches_real_reservation_without_consuming_review_or_ledger(role):
    from test_v2_saved_draft_integration import agent_fixture
    agent, store, calls = agent_fixture()
    estimate = agent.estimate_stage(role, {'fixture': 'exact payload'})
    assert estimate > 0
    assert store.row is None and calls == [] and agent.receipts == []
    assert not hasattr(agent, '_saved_draft_review_attempts')
    assert agent.run(role, {'fixture': 'exact payload'}) == {}
    entry = next(iter(store.row['entries'].values()))
    assert entry['reserved_micro_usd'] == estimate
    assert len(calls) == 1


@pytest.fixture
def image_pipeline(tmp_path, monkeypatch):
    import hashlib
    import io
    from pathlib import Path
    from PIL import Image
    from daily_budget import Ledger, day_key
    from publishing_v2.autopilot.agents import Agents
    from publishing_v2.autopilot import fixed_preparation
    from publishing_v2.editorial_production import TEXT_CHECKS
    from test_v2_autopilot_adapters import Store
    from test_v2_saved_draft_integration import pipeline_fixture
    from test_v2_saved_draft_images_recovery import fixture
    case, pipeline, baseline, _, _ = pipeline_fixture()
    old, request, _, _, history = fixture()
    original = copy.deepcopy(pipeline.free_selection)
    selection = copy.deepcopy(original)
    selection['image_plan'] = [{'asset_id': str(i), 'purpose': 'compatible subject image'} for i in range(3, 6)]
    day = day_key(pipeline.now())
    ancestor = old
    while ancestor:
        for key in ('candidate', 'candidate_id', 'research', 'sources', 'free_selection',
                    'timing', 'started_at', 'expires_at'):
            ancestor[key] = copy.deepcopy(baseline[key])
        historical_request = ancestor.get('recovery', {}).get('request', {})
        if 'retained_reservation' in historical_request:
            historical_request['retained_reservation']['day'] = day
        ancestor = ancestor.get('recovery', {}).get('previous_state')
    old.pop('source_drift', None)
    old['recovery']['request'].update(
        expected_state_sha256=digest(old['recovery']['previous_state']),
        selection_sha256=digest(original), original_selection_sha256=digest(original))
    request['retained_reservation']['day'] = day
    request.update(expected_state_sha256=digest(old), selection_sha256=digest(selection),
                   original_selection_sha256=digest(original))
    pipeline.store.save(old)
    pipeline.free_selection = selection
    pipeline.saved_research_recovery = (request, original)
    history.update(day=day, limit_micro_usd=None)
    store = Store(); store.row = copy.deepcopy(history)
    ledger = Ledger(store, now=pipeline.now, limit_micro_usd=None)
    roles = []
    def transport(method, url, headers, payload):
        role = ledger.context['stage']; roles.append(role)
        data = json.loads(payload['messages'][0]['content'][-1]['text'])
        if role == 'fixed_information_text_review':
            assert data['cards'] == request['edited_draft']['cards']
            result = {'checks': dict(dict.fromkeys(TEXT_CHECKS, True), source_drift_resolved=True),
                      'repair_indices': [], 'reason': 'Offline actual review response'}
        elif role == 'visual':
            assert {row['asset_id'] for row in data['options']} == {'3', '4', '5'}
            result = {'image_ids': ['3']}
        else: pytest.fail('unexpected generation role: ' + role)
        return {'status_code': 200, 'body': {'id': 'fixture-' + role, 'stop_reason': 'end_turn',
                'usage': {'input_tokens': 10, 'output_tokens': 10},
                'content': [{'type': 'text', 'text': json.dumps(result)}]}}
    pipeline.agent = Agents(env={'ANTHROPIC_API_KEY': 'offline', 'PACKAGE_ID': 'a'},
                            ledger=ledger, transport=transport)
    buffer = io.BytesIO(); Image.new('RGB', (1200, 800), 'blue').save(buffer, 'JPEG')
    image_bytes = buffer.getvalue()
    catalog = [{'asset_id': str(i), 'license': 'CC0',
                'sha256': hashlib.sha256(image_bytes).hexdigest()} for i in range(3, 6)]
    class Renderer:
        def screen_visuals(self, candidate):
            candidate['visual_feasibility'] = [{'asset_id': str(i)} for i in range(3, 6)]
            return True
        def image_catalog(self, package): return copy.deepcopy(catalog)
    pipeline.render = Renderer()
    pipeline.fixed_prepare = fixed_preparation.FixedInformationPreparer(pipeline.agent, pipeline.render)
    settings = (Path.cwd() / 'publishing_v2/design-settings.json').read_bytes()
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'publishing_v2').mkdir()
    (tmp_path / 'publishing_v2/design-settings.json').write_bytes(settings)
    monkeypatch.setattr(fixed_preparation, 'download_image', lambda *a, **k: image_bytes)
    pipeline.output = tmp_path / 'out'
    try:
        yield SimpleNamespace(pipeline=pipeline, old=old, request=request, store=store,
                              history=copy.deepcopy(history), roles=roles, catalog=catalog, case=case)
    finally:
        case.doCleanups()


def test_image_recovery_preflights_real_catalog_and_combined_budget_before_review(image_pipeline):
    f = image_pipeline; p = f.pipeline
    result = p.run('daily', 'fixed-preview')
    assert result['status'] == 'awaiting_information_review', result
    assert result['recovery']['previous_state'] == f.old
    assert p.agent.request_attempt_offset == 5
    assert [r['request_attempt'] for r in p.agent.receipts] == [6, 7]
    assert f.roles == ['fixed_information_text_review', 'visual']
    proof = result['recovery']['review_budget_preflight']
    assert proof['maximum_micro_usd'] > 0
    assert proof['charged_micro_usd'] == 61478 and proof['limit_micro_usd'] == 500000
    assert proof['maximum_micro_usd'] + proof['charged_micro_usd'] <= proof['limit_micro_usd']
    for ident, row in f.history['entries'].items():
        assert f.store.row['entries'][ident] == row
    assert not hasattr(p.agent.ledger, 'package_writing_authorization')
    assert result['information_package']['publish_authorized'] is False
    assert result['information_package']['preview_allowed'] is False
    assert f.case.sent == []


def test_empty_compatible_catalog_leaves_hold_and_ledger_untouched(image_pipeline):
    f = image_pipeline; f.catalog.clear()
    with pytest.raises(ValueError, match='caption_rights_compatible_source_unavailable'):
        f.pipeline.run('daily', 'fixed-preview')
    assert f.pipeline.store.read() == f.old and f.store.row == f.history
    assert f.roles == [] and not f.pipeline.output.exists()


def test_full_review_and_visual_maximum_must_fit_remaining_review_allowance(image_pipeline):
    from daily_budget import BudgetBlocked
    f = image_pipeline; p = f.pipeline
    p.agent.env.update(AUTOPILOT_FIXED_INFORMATION_TEXT_REVIEW_MODEL='claude-opus-5',
                       AUTOPILOT_VISUAL_MODEL='claude-opus-5')
    original = p.sources.research
    def large_sources(*args):
        rows = copy.deepcopy(original(*args)); rows[0]['text'] += ' background context' * 1200
        return rows
    p.sources.research = large_sources
    with pytest.raises(BudgetBlocked) as blocked:
        p.run('daily', 'fixed-preview')
    assert blocked.value.diagnostic['code'] == 'package_stage_limit'
    assert blocked.value.diagnostic['charged_micro_usd'] == 61478
    assert p.store.read() == f.old and f.store.row == f.history and f.roles == []
    assert not p.output.exists()


def test_runtime_loads_image_only_recovery_and_reaches_guarded_review(image_pipeline, tmp_path, monkeypatch):
    import base64
    from daily_budget import day_key
    from publishing_v2.autopilot import runtime, fixed_preparation, published_memory, candidate_memory
    from test_v2_autopilot import MemoryStore
    f = image_pipeline; p = f.pipeline
    selection_path = tmp_path / 'editorial/selected/new.json'
    selection_path.parent.mkdir(parents=True)
    selection_path.write_text(json.dumps(p.free_selection))
    f.request.update(original_head_sha='a' * 40, original_selection_path='editorial/selected/old.json')
    request_path = tmp_path / 'editorial/recovery/request.json'
    request_path.parent.mkdir(); request_path.write_text(json.dumps(f.request))
    def call(path):
        if path == '/actions/runs/789':
            return {'head_sha': 'a' * 40, 'event': 'workflow_dispatch', 'status': 'completed',
                    'conclusion': 'failure', 'path': '.github/workflows/publishing-v2-fixed-preview.yml',
                    'repository': {'full_name': 'khalidonline/daily-news-snap'}}
        assert path == '/contents/editorial/selected/old.json?ref=' + 'a' * 40
        return {'content': base64.b64encode(json.dumps(f.old['free_selection']).encode()).decode()}
    p.store.call = call
    slot = f'autopilot-{day_key(p.now())}-daily-fixed-preview'
    journals = {slot: p.store}
    def journal(name): return journals.setdefault(name, MemoryStore())
    monkeypatch.setenv('GITHUB_REPOSITORY', 'khalidonline/daily-news-snap')
    monkeypatch.setenv('GITHUB_REF', 'refs/heads/main')
    monkeypatch.setattr(runtime, 'GitHubJournal', journal)
    monkeypatch.setattr(runtime, 'GitHubStore', lambda *a: None)
    monkeypatch.setattr(runtime, 'Ledger', lambda *a, **kw: p.agent.ledger)
    monkeypatch.setattr(runtime, 'Agents', lambda **kw: p.agent)
    monkeypatch.setattr(runtime, 'Sources', lambda **kw: p.sources)
    monkeypatch.setattr(runtime, 'Renderer', lambda *a: p.render)
    monkeypatch.setattr(runtime, 'datetime', SimpleNamespace(now=lambda *a: p.now()))
    monkeypatch.setattr(runtime, 'engine_id', lambda: 'runtime-new')
    monkeypatch.setattr(fixed_preparation, 'FixedInformationPreparer', lambda *a: p.fixed_prepare)
    monkeypatch.setattr(published_memory, 'PublishedMemory', lambda *a: SimpleNamespace(
        import_manual=lambda *a: None, reason=lambda *a: None))
    monkeypatch.setattr(candidate_memory, 'CandidateMemory', lambda *a: SimpleNamespace(
        reason=lambda *a: None, record=lambda *a: None))
    monkeypatch.setattr('sys.argv', ['runtime', '--mode', 'fixed-preview', '--lane', 'daily',
        '--selection', str(selection_path), '--recover-held', str(request_path), '--output', 'runtime-out'])
    assert runtime.main() == 0
    result = json.loads((tmp_path / 'runtime-out/daily.json').read_text())
    assert result['status'] == 'awaiting_information_review'
    assert result['recovery']['previous_state'] == f.old
    assert [r['request_attempt'] for r in p.agent.receipts] == [6, 7]
    assert f.roles == ['fixed_information_text_review', 'visual']
    assert journals['autopilot-readiness'].read() == {}
    assert 'autopilot-ready-inventory' not in journals
