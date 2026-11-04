import copy
from datetime import datetime, timezone
import pytest
from publishing_v2.autopilot.policy import digest

NOW = datetime(2026,11,4,12,30,tzinfo=timezone.utc)


def fixture():
    old = {'version':1,'engine':'old','lane':'daily','mode':'fixed-preview','status':'held',
           'started_at':'2026-11-04T12:16:29+00:00','expires_at':'2026-11-06T00:00:00+03:00',
           'reason':'free_selection_not_in_current_pool','agent_receipts':[], 'pool':[],
           'audit':[{'event':'started'}, {'event':'pool'},
                    {'event':'stopped','reason':'free_selection_not_in_current_pool'}]}
    original = {'version':1,'lane':'daily','candidate_id':'abc','choice':{'id':'abc'}}
    current = dict(original, source={'url':'https://www.alyaum.com/articles/example'})
    request = {'version':1,'expected_state_sha256':digest(old), 'original_engine':'old',
               'original_run_id':123, 'original_head_sha':'a'*40,
               'original_selection_path':'editorial/selected/test.json',
               'original_selection_sha256':digest(original), 'selection_sha256':digest(current),
               'candidate_id':'abc','lane':'daily'}
    return old,request,current,original


def recover(*args):
    from publishing_v2.autopilot.zero_call_recovery import prepare_recovery
    return prepare_recovery(*args,now=NOW,engine='new')


def test_recovers_only_exact_zero_call_hold_preserving_snapshot():
    old,request,current,original=fixture()
    result=recover(old,request,current,original)
    assert result['status']=='working' and result['engine']=='new'
    assert result['recovery']['previous_state']==old
    assert result['audit'][:-1]==old['audit']
    assert result['audit'][-1]['event']=='zero_call_recovery_authorized'
    assert result['started_at']==old['started_at']
    assert old['status']=='held'
    with pytest.raises(ValueError): recover(result,request,current,original)


@pytest.mark.parametrize('change',[
    {'agent_receipts':[{'cost_micro_usd':0}]}, {'candidate_id':'abc'},
    {'status':'working'}, {'status':'awaiting_information_review'},
    {'reason':'generation_interrupted'}, {'mode':'live'}, {'engine':'other'},
    {'expires_at':'2026-11-04T00:00:00+00:00'}, {'information_package':{}},
    {'recovery':{}}, {'audit':[{'event':'started'},{'event':'candidate_considered'},{'event':'stopped'}]},
])
def test_rejects_paid_ambiguous_terminal_or_other_states_even_if_digest_matches(change):
    old,request,current,original=fixture();old.update(change);request['expected_state_sha256']=digest(old)
    with pytest.raises(ValueError): recover(old,request,current,original)


def test_rejects_state_or_original_selection_tampering():
    old,request,current,original=fixture()
    old['pool']=[{'id':'changed'}]
    with pytest.raises(ValueError):recover(old,request,current,original)
    old,request,current,original=fixture();current['choice']={'id':'different'};request['selection_sha256']=digest(current)
    with pytest.raises(ValueError):recover(old,request,current,original)
    old,request,current,original=fixture();original['candidate_id']='other'
    with pytest.raises(ValueError):recover(old,request,current,original)


def test_pipeline_resolves_pin_and_retains_all_prepaid_evidence_gates(tmp_path):
    from test_v2_cost_controls import FreeSelectionTests
    case=FreeSelectionTests();case.setUp()
    try:
        pipeline=case.make_pipeline();candidate=pipeline.sources.discover('daily',pipeline.now())[0]
        pipeline.free_selection['source']={'url':candidate['url']}
        pipeline.sources.resolve_selection=lambda *args:copy.deepcopy(candidate)
        pipeline.sources.discover=lambda *args:pytest.fail('volatile discovery must not select pinned source')
        pipeline.fixed_prepare=lambda *args:{'preview_allowed':False,'publish_authorized':False}
        result=pipeline.run('daily','fixed-preview')
        assert result['status']=='awaiting_information_review',result
        assert case.agent.calls==['researcher']
        assert result['selection_assessment']['status']=='evidence_passed'
    finally:case.doCleanups()


def test_pipeline_does_not_fallback_or_pay_when_pin_cannot_resolve(tmp_path):
    from test_v2_cost_controls import FreeSelectionTests
    case=FreeSelectionTests();case.setUp()
    try:
        pipeline=case.make_pipeline();pipeline.free_selection['source']={}
        def fail(*args):raise ValueError('selected_source_unverified')
        pipeline.sources.resolve_selection=fail
        pipeline.fixed_prepare=lambda *args:pytest.fail('must not prepare')
        result=pipeline.run('daily','fixed-preview')
        assert result['status']=='held' and result['reason']=='selected_source_unverified'
        assert case.agent.calls==[]
    finally:case.doCleanups()


def recovery_pipeline():
    from test_v2_cost_controls import FreeSelectionTests
    case=FreeSelectionTests();case.setUp();pipeline=case.make_pipeline()
    original=copy.deepcopy(pipeline.free_selection)
    candidate=pipeline.sources.discover('daily',pipeline.now())[0]
    pipeline.free_selection['source']={'url':candidate['url']}
    pipeline.sources.resolve_selection=lambda *args:copy.deepcopy(candidate)
    pipeline.fixed_prepare=lambda *args:{'preview_allowed':False,'publish_authorized':False}
    old,request,_,_=fixture()
    old.update(started_at=pipeline.now().isoformat(),expires_at='2026-09-18T00:00:00+00:00')
    request.update(expected_state_sha256=digest(old),candidate_id='a',
                   original_selection_sha256=digest(original),selection_sha256=digest(pipeline.free_selection))
    pipeline.store.save(old);pipeline.zero_call_recovery=(request,original)
    return case,pipeline,old


def test_recovery_runs_original_slot_once_and_preserves_no_publish_authority():
    case,pipeline,old=recovery_pipeline()
    try:
        result=pipeline.run('daily','fixed-preview')
        assert result['status']=='awaiting_information_review', result
        assert result['recovery']['previous_state']==old
        assert case.agent.calls==['researcher']
        with pytest.raises(ValueError):pipeline.run('daily','fixed-preview')
        assert case.agent.calls==['researcher']
    finally:case.doCleanups()


def test_recovery_persistence_uncertainty_stops_before_any_paid_work():
    from publishing_v2.autopilot.pipeline import PersistenceError
    case,pipeline,old=recovery_pipeline()
    try:
        pipeline.store.save=lambda *args:(_ for _ in ()).throw(OSError('uncertain'))
        with pytest.raises(PersistenceError):pipeline.run('daily','fixed-preview')
        assert case.agent.calls==[]
    finally:case.doCleanups()


def test_recovery_cli_rejects_other_modes_before_any_external_access(monkeypatch):
    from publishing_v2.autopilot import runtime
    monkeypatch.setattr('sys.argv',['runtime','--mode','shadow','--recover-zero-call-held','recovery.json'])
    with pytest.raises(ValueError,match='recovery_requires_fixed_preview'):runtime.main()


def test_recovery_loader_reads_only_immutable_original_run_and_brief(tmp_path,monkeypatch):
    import base64,json
    from publishing_v2.autopilot.zero_call_recovery import load_recovery
    old,request,current,original=fixture()
    monkeypatch.chdir(tmp_path);path=tmp_path/'editorial/recovery/request.json'
    path.parent.mkdir(parents=True);path.write_text(json.dumps(request))
    class Journal:
        def __init__(self):self.calls=[];self.head='a'*40
        def call(self,path):
            self.calls.append(path)
            if path=='/actions/runs/123':
                return {'head_sha':self.head,'event':'workflow_dispatch','status':'completed','conclusion':'failure',
                        'path':'.github/workflows/publishing-v2-fixed-preview.yml',
                        'repository':{'full_name':'khalidonline/daily-news-snap'}}
            assert path=='/contents/editorial/selected/test.json?ref='+'a'*40
            return {'content':base64.b64encode(json.dumps(original).encode()).decode()}
    journal=Journal()
    assert load_recovery(path,journal,mode='fixed-preview',lane='daily')==(request,original)
    assert len(journal.calls)==2
    journal.head='b'*40
    with pytest.raises(ValueError,match='original_failed_preview_run_required'):
        load_recovery(path,journal,mode='fixed-preview',lane='daily')
    assert len(journal.calls)==3
    request['original_selection_path']='../secrets.json';path.write_text(json.dumps(request))
    with pytest.raises(ValueError,match='invalid_recovery_source_identity'):
        load_recovery(path,journal,mode='fixed-preview',lane='daily')
    assert len(journal.calls)==3


def test_recovery_does_not_allow_replacing_existing_original_source_pin():
    old,request,current,original=fixture()
    original['source']={'url':'https://www.alyaum.com/articles/original'}
    request['original_selection_sha256']=digest(original)
    with pytest.raises(ValueError,match='original_source_changed'):recover(old,request,current,original)


def test_exact_failed_trial_recovery_request_matches_archived_state_and_original_commit():
    import json,subprocess,zipfile
    from pathlib import Path
    artifact=Path('/tmp/tawari-trial-diagnostics.zip')
    if not artifact.is_file():pytest.skip('local diagnostic artifact is not a repository fixture')
    request=json.loads(Path('editorial/recovery/tawari-20261104-zero-call.json').read_text())
    state=json.loads(zipfile.ZipFile(artifact).read('daily.json'))
    original=json.loads(subprocess.check_output(['git','show',request['original_head_sha']+':'+request['original_selection_path']]))
    selection=json.loads(Path(request['original_selection_path']).read_text())
    result=recover(state,request,selection,original)
    assert result['recovery']['previous_state']['agent_receipts']==[]


def test_missing_recovery_source_does_not_consume_original_zero_call_hold():
    case,pipeline,old=recovery_pipeline()
    try:
        def missing(*args):raise ValueError('selected_source_not_in_publisher_feed')
        pipeline.sources.resolve_selection=missing
        with pytest.raises(ValueError,match='selected_source_not_in_publisher_feed'):
            pipeline.run('daily','fixed-preview')
        assert pipeline.store.read()==old
        assert case.agent.calls==[]
    finally:case.doCleanups()
