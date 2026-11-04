import copy
from datetime import datetime,timezone
import pytest
from publishing_v2.autopilot.policy import digest

NOW=datetime(2026,11,4,13,tzinfo=timezone.utc)


def fixture():
    selection={'version':1,'lane':'daily','candidate_id':'a','choice':{'id':'a'},'source':{'url':'https://www.bbc.com/news/a'}}
    state={'version':1,'engine':'old','lane':'daily','mode':'fixed-preview','status':'held',
           'reason':'no_package_passed_review','started_at':'2026-11-04T12:00:00+00:00',
           'expires_at':'2026-11-05T00:00:00+00:00','candidate_id':'a','candidate':{'id':'a'},
           'research':{'claims':[{'id':'c1'}]},'sources':[{'id':'article'}],
           'free_selection':copy.deepcopy(selection),'timing':{'eligible':True},
           'agent_receipts':[{'role':'researcher','response_id':'r','package_id':'a','cost_micro_usd':5,'stop_reason':'end_turn'},
                             {'role':'fixed_information_writer','response_id':'w','package_id':'a','cost_micro_usd':3,'stop_reason':'end_turn'}],
           'audit':[{'event':'started'},{'event':'researched'},
                    {'event':'candidate_rejected','candidate_id':'a','reason':'invalid_fixed_information_text'},
                    {'event':'exhausted_candidates','reason':'no_package_passed_review'}]}
    request={'version':1,'kind':'saved_research','allow_replacement_writer':True,'lane':'daily','candidate_id':'a',
             'expected_state_sha256':digest(state),'original_engine':'old',
             'selection_sha256':digest(selection),'original_selection_sha256':digest(selection)}
    return state,request,selection,copy.deepcopy(selection)


def recover(*args):
    from publishing_v2.autopilot.saved_research_recovery import prepare_recovery
    return prepare_recovery(*args,now=NOW,engine='new')


def test_exact_research_and_receipts_preserved_with_one_use_only():
    old,req,selection,original=fixture();out=recover(old,req,selection,original)
    assert out['research']==old['research'] and out['agent_receipts']==old['agent_receipts']
    assert out['recovery']['previous_state']==old
    assert out['audit'][-1]['event']=='saved_research_recovery_authorized'
    assert old['status']=='held' and out['status']=='working'
    with pytest.raises(ValueError):recover(out,req,selection,original)


@pytest.mark.parametrize('change',[
 {'status':'working'},{'mode':'live'},{'information_package':{}},{'working_draft':{}},
 {'research':{}},{'sources':[]},{'candidate_id':'b'},
 {'agent_receipts':[]},{'agent_receipts':[{'role':'researcher'},{'role':'fixed_information_writer'}]},
 {'expires_at':'2026-11-03T00:00:00+00:00'},
 {'audit':[{'event':'researched'},{'event':'candidate_rejected','reason':'review_rejected'}, {'event':'exhausted_candidates'}]},
])
def test_wrong_ambiguous_or_completed_states_rejected(change):
    old,req,selection,original=fixture();old.update(change);req['expected_state_sha256']=digest(old)
    with pytest.raises(ValueError):recover(old,req,selection,original)


def test_no_new_writer_without_explicit_request_and_same_selection():
    old,req,selection,original=fixture();req['allow_replacement_writer']=False
    with pytest.raises(ValueError):recover(old,req,selection,original)
    old,req,selection,original=fixture();selection['choice']={'id':'b'};req['selection_sha256']=digest(selection)
    with pytest.raises(ValueError):recover(old,req,selection,original)


def pipeline_fixture():
    from test_v2_cost_controls import FreeSelectionTests
    from test_v2_autopilot import research,evidence
    from publishing_v2.autopilot.policy import evidence_snapshot
    case=FreeSelectionTests();case.setUp();p=case.make_pipeline()
    candidate=p.sources.discover('daily',p.now())[0]
    p.free_selection['source']={'url':candidate['url']}
    p.sources.resolve_selection=lambda *args:copy.deepcopy(candidate)
    old,req,_,_=fixture();old.update(candidate_id='a',candidate=copy.deepcopy(candidate),
        research=research(),sources=evidence_snapshot(research(),evidence()),
        free_selection=copy.deepcopy(p.free_selection),timing=copy.deepcopy(p.free_selection['timing']),
        started_at=p.now().isoformat(),expires_at='2026-09-18T00:00:00+00:00')
    req.update(expected_state_sha256=digest(old),selection_sha256=digest(p.free_selection),
               original_selection_sha256=digest(p.free_selection))
    p.store.save(old);p.saved_research_recovery=(req,copy.deepcopy(p.free_selection))
    seen=[]
    p.fixed_prepare=lambda context,output:(seen.append(copy.deepcopy(context)) or {'preview_allowed':False,'publish_authorized':False})
    return case,p,old,seen


def test_pipeline_reuses_saved_research_without_paid_research_and_never_repeats():
    case,p,old,seen=pipeline_fixture()
    try:
        result=p.run('daily','fixed-preview')
        assert result['status']=='awaiting_information_review',result
        assert case.agent.calls==[]
        assert seen[0]['research']==old['research']
        assert result['agent_receipts']==old['agent_receipts']
        assert case.agent.request_attempt_offset==2
        with pytest.raises(ValueError):p.run('daily','fixed-preview')
        assert len(seen)==1
    finally:case.doCleanups()


def test_changed_live_evidence_does_not_consume_paid_hold():
    case,p,old,seen=pipeline_fixture()
    try:
        p.sources.research=lambda *args:[{'id':'s1','url':'https://www.bbc.com/news/a','source_type':'news_article','text':'Changed evidence'}]
        with pytest.raises(ValueError):p.run('daily','fixed-preview')
        assert p.store.read()==old and case.agent.calls==[] and seen==[]
    finally:case.doCleanups()


def test_replacement_writer_keeps_attempt_sequence_and_is_one_provider_call():
    from test_v2_autopilot_adapters import Store
    from daily_budget import Ledger
    from publishing_v2.autopilot.agents import Agents,InvalidAgentResponse
    calls=[];store=Store();ledger=Ledger(store,now=lambda:NOW)
    def transport(*args):
        calls.append(args)
        return {'status_code':200,'body':{'id':'new-writer','stop_reason':'end_turn',
                'usage':{'input_tokens':10,'output_tokens':10},'content':[{'type':'text','text':'{bad json'}]}}
    agent=Agents(env={'ANTHROPIC_API_KEY':'offline','PACKAGE_ID':'a'},ledger=ledger,transport=transport)
    agent.request_attempt_offset=2;agent.fixed_writer_recovery_once=True
    with pytest.raises(InvalidAgentResponse):agent.run('fixed_information_writer',{})
    assert len(calls)==1
    assert agent.receipts[0]['request_attempt']==3
    assert next(iter(store.row['entries'].values()))['request_attempt']==3


def test_saved_research_to_preserved_normalized_fitted_reviewed_fixed_card(tmp_path,monkeypatch):
    import hashlib,io,json
    from pathlib import Path
    from PIL import Image
    from publishing_v2.autopilot import fixed_preparation as fixed
    from publishing_v2.editorial_production import TEXT_CHECKS
    case,p,old,seen=pipeline_fixture()
    root=Path.cwd()
    try:
        monkeypatch.chdir(tmp_path);(tmp_path/'publishing_v2').mkdir()
        (tmp_path/'publishing_v2/design-settings.json').write_bytes((root/'publishing_v2/design-settings.json').read_bytes())
        p.output=tmp_path/'output'
        buffer=io.BytesIO();Image.new('RGB',(1200,800),'blue').save(buffer,'JPEG');raw=buffer.getvalue()
        image={'asset_id':'0','license':'CC0','sha256':hashlib.sha256(raw).hexdigest()}
        def run(role,data,images=()):
            case.agent.calls.append(role)
            if role=='fixed_information_writer':
                return {'title':'خبر محلي','cards':[{'kind':'info','title':'خبر اليوم',
                        'bullets':['مَعلومة واضحة وقريبة من الناس'],'punch':'هنا الخلاصة',
                        'claim_ids':['c1'],'image_query':'Jeddah','image_caption':'صورة تجريبية'}]}
            if role=='fixed_information_text_review':
                assert data['cards'][0]['bullets'][0]=='معلومة واضحة وقريبة من الناس'
                return {'checks':dict.fromkeys(TEXT_CHECKS,True),'repair_indices':[],'reason':'fixture'}
            if role=='visual':return {'image_ids':['0']}
            pytest.fail('Unexpected role, especially paid researcher: '+role)
        case.agent.run=run
        class Renderer:
            def screen_visuals(self,candidate):
                candidate['visual_feasibility']=[{'asset_id':str(i)} for i in range(3)];return True
            def image_catalog(self,package):return [image]
        renderer=Renderer();p.render=renderer;p.fixed_prepare=fixed.FixedInformationPreparer(case.agent,renderer)
        monkeypatch.setattr(fixed,'download_image',lambda *args,**kw:raw)
        result=p.run('daily','fixed-preview')
        assert result['status']=='awaiting_information_review',result
        package=tmp_path/result['information_package']['package']
        assert (package/'card-00.png').is_file()
        assert json.loads((package/'manifest.json').read_text())['approved'] is False
        assert json.loads((package/'archive-approval.json').read_text())['approved'] is False
        saved=json.loads((p.output/'a/fixed/fixed-writer-raw.json').read_text())
        assert saved['cards'][0]['bullets'][0].startswith('مَ')
        assert case.agent.calls==['fixed_information_writer','fixed_information_text_review','visual']
        with pytest.raises(ValueError):p.run('daily','fixed-preview')
        assert len(case.agent.calls)==3
    finally:case.doCleanups()


def test_preflight_diagnostic_is_safe_and_not_an_authorization(tmp_path):
    from publishing_v2.autopilot.saved_research_recovery import write_preflight_failure
    import json
    write_preflight_failure(tmp_path,'daily',ValueError('planned_image_not_retrieved'))
    row=json.loads((tmp_path/'recovery-preflight.json').read_text())
    assert row['reason']=='planned_image_not_retrieved'
    assert row['preview_allowed'] is False and row['publish_authorized'] is False
    write_preflight_failure(tmp_path,'daily',ValueError('selected_source_not_in_publisher_feed'))
    assert json.loads((tmp_path/'recovery-preflight.json').read_text())['reason']=='selected_source_not_in_publisher_feed'
    write_preflight_failure(tmp_path,'daily',ValueError('untrusted private text'))
    assert 'untrusted private text' not in (tmp_path/'recovery-preflight.json').read_text()
    assert json.loads((tmp_path/'recovery-preflight.json').read_text())['reason']=='preflight_failed'


def test_source_body_drift_requires_opt_in_and_exact_support():
    from publishing_v2.autopilot.saved_research_recovery import verify_evidence
    old=[{'id':'a','url':'https://example.org/a','text':'Exact quote','retrieved_text_sha256':'a'*64}]
    new=copy.deepcopy(old);new[0]['retrieved_text_sha256']='b'*64
    with pytest.raises(ValueError,match='opt_in'):verify_evidence(old,new,{})
    drift=verify_evidence(old,new,{'allow_source_text_drift_review':True})
    assert drift==[{'source_id':'a','previous_sha256':'a'*64,'current_sha256':'b'*64}]
    for key in ('id','url','text'):
        changed=copy.deepcopy(new);changed[0][key]+=' changed'
        with pytest.raises(ValueError,match='evidence_changed'):
            verify_evidence(old,changed,{'allow_source_text_drift_review':True})


def test_source_drift_requires_explicit_independent_review_check():
    from publishing_v2.autopilot import fixed_information as fixed
    from publishing_v2.editorial_production import TEXT_CHECKS,TextRejected
    import hashlib
    package={'title':'خبر','cards':[{'kind':'info','title':'خبر','bullets':['خبر واضح'],'punch':'خلاصة',
        'claim_ids':['c1'],'image_query':'falcon','image_caption':'صقر'}],
        'research':{'claims':[{'id':'c1'}]},'sources':[{'id':'a','retrieved_text_sha256':hashlib.sha256(b'fresh').hexdigest()}],
        'source_drift':[{'source_id':'a','previous_sha256':'a'*64,'current_sha256':hashlib.sha256(b'fresh').hexdigest()}]}
    class Agent:
        def run(self,role,data):
            assert data['source_drift']==package['source_drift']
            return {'checks':dict.fromkeys(TEXT_CHECKS,True),'repair_indices':[],'reason':'fresh review'}
    with pytest.raises(TextRejected):fixed.approve_text(package,Agent(),[{'id':'a','text':'fresh'}])
    class Reviewed(Agent):
        def run(self,role,data):
            r=super().run(role,data);r['checks']['source_drift_resolved']=True;return r
    fixed.approve_text(package,Reviewed(),[{'id':'a','text':'fresh'}]);fixed.require_text_approval(package)
    package['source_drift'][0]['current_sha256']='c'*64
    with pytest.raises(ValueError):fixed.require_text_approval(package)


def test_pipeline_records_full_source_drift_and_passes_current_text_to_review():
    case,p,old,seen=pipeline_fixture()
    try:
        original=p.sources.research
        def changed(*args):
            rows=copy.deepcopy(original(*args))
            rows[0]['text']+=' Additional unrelated page text.'
            return rows
        p.sources.research=changed
        p.saved_research_recovery[0]['allow_source_text_drift_review']=True
        result=p.run('daily','fixed-preview')
        assert result['status']=='awaiting_information_review',result
        assert result['source_drift'] and seen[0]['source_drift']==result['source_drift']
        assert 'Additional unrelated' in seen[0]['original_sources'][0]['text']
        assert result['recovery']['previous_state']==old
        assert case.agent.calls==[]
    finally:case.doCleanups()
