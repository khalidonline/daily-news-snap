"""Fixed-preview is a preparation state, never legacy approval or publication."""
import copy
from pathlib import Path
import pytest
from test_v2_autopilot import FakeAgent, FakeSources, MemoryStore, NOW
from publishing_v2.autopilot.pipeline import Pipeline


def test_fixed_preparation_is_invoked_after_research_and_is_terminal(tmp_path):
    calls=[];store=MemoryStore();agent=FakeAgent()
    def fixed_prepare(context,output):
        assert context['research']['claims']
        assert context['verified_timing']['eligible'] is True
        calls.append(copy.deepcopy(context))
        return {'status':'DRAFT_REQUIRES_REVIEW','package':'approved/synthetic-fixed',
                'preview_allowed':False,'publish_authorized':False}
    def forbidden(*args,**kwargs): pytest.fail('legacy renderer or publisher invoked')
    pipeline=Pipeline(agent=agent,sources=FakeSources(),render=forbidden,store=store,
                      publish=forbidden,output=tmp_path,now=lambda:NOW,fixed_prepare=fixed_prepare)
    result=pipeline.run('daily','fixed-preview')
    assert result['status']=='awaiting_information_review'
    assert result['information_package']['preview_allowed'] is False
    assert 'writer' not in agent.calls and 'reviewer' not in agent.calls
    before=copy.deepcopy(agent.calls)
    assert pipeline.run('daily','fixed-preview')==result
    assert agent.calls==before and len(calls)==1
    with pytest.raises(ValueError): pipeline.run('daily','live',rollout_verified=True)


def test_fixed_mode_requires_callback_before_work(tmp_path):
    pipeline=Pipeline(agent=FakeAgent(),sources=FakeSources(),render=lambda *a:None,
                      store=MemoryStore(),publish=lambda *a:None,output=tmp_path,now=lambda:NOW)
    with pytest.raises(ValueError,match='fixed'):
        pipeline.run('daily','fixed-preview')


def test_actual_preparer_uses_fixed_writer_and_stops_before_preview(tmp_path,monkeypatch):
    import hashlib,io,json,socket
    from PIL import Image
    from publishing_v2.editorial_production import TEXT_CHECKS
    import importlib.util
    assert importlib.util.find_spec('publishing_v2.autopilot.fixed_preparation'), 'fixed preparer missing'
    from publishing_v2.autopilot import fixed_preparation as fixed
    root=Path(__file__).resolve().parents[1]
    monkeypatch.chdir(tmp_path);(tmp_path/'publishing_v2').mkdir()
    (tmp_path/'publishing_v2/design-settings.json').write_bytes((root/'publishing_v2/design-settings.json').read_bytes())
    monkeypatch.setattr(socket,'socket',lambda *a,**kw:pytest.fail('network forbidden'))
    buffer=io.BytesIO();Image.new('RGB',(1200,800),'blue').save(buffer,'JPEG');raw=buffer.getvalue()
    image={'asset_id':'synthetic','license':'CC0','sha256':hashlib.sha256(raw).hexdigest()}
    class Agent(FakeAgent):
        def run(self,role,data,images=()):
            if role=='fixed_information_writer':
                self.calls.append(role)
                return {'title':'خبر محلي','cards':[{'kind':'info','title':'خبر اليوم',
                        'bullets':['معلومة واضحة وقريبة من الناس'], 'punch':'هنا الخلاصة',
                        'claim_ids':['c1'],'image_query':'Jeddah','image_caption':'صورة تجريبية'}]}
            if role=='fixed_information_text_review':
                self.calls.append(role)
                return {'checks':dict.fromkeys(TEXT_CHECKS,True),'repair_indices':[],
                        'reason':'Synthetic offline source review'}
            if role=='visual':
                self.calls.append(role)
                return {'image_ids':['synthetic'],'reason':'Synthetic selection'}
            return super().run(role,data,images)
    class Renderer:
        def image_catalog(self,package): return [image]
        def __call__(self,*a): pytest.fail('legacy rendering forbidden')
    monkeypatch.setattr(fixed,'download_image',lambda *a,**kw:raw)
    agent=Agent();renderer=Renderer();store=MemoryStore()
    prepare=fixed.FixedInformationPreparer(agent,renderer)
    pipeline=Pipeline(agent=agent,sources=FakeSources(),render=renderer,store=store,
                      publish=lambda *a:pytest.fail('publishing forbidden'),output=tmp_path/'out',
                      now=lambda:NOW,fixed_prepare=prepare)
    result=pipeline.run('daily','fixed-preview')
    assert result['status']=='awaiting_information_review',result
    p=tmp_path/result['information_package']['package']
    assert (p/'card-00.png').exists()
    assert json.loads((p/'manifest.json').read_text())['approved'] is False
    assert json.loads((p/'archive-approval.json').read_text())['approved'] is False
    assert agent.calls.count('fixed_information_writer')==1
    assert 'writer' not in agent.calls and 'reviewer' not in agent.calls
    assert not (p/'prepared.json').exists()
    assert not (p/'preview-receipt.json').exists()
    calls=list(agent.calls)
    assert pipeline.run('daily','fixed-preview')==result
    assert calls==agent.calls

    # Exercise actual CLI wiring, not just the injected Pipeline callback.
    # Use a distinct lane so the existing draft is not regenerated.
    from types import SimpleNamespace
    from publishing_v2.autopilot import runtime,published_memory,candidate_memory
    journals={}
    def journal(name): return journals.setdefault(name,MemoryStore())
    monkeypatch.setenv('GITHUB_REPOSITORY','khalidonline/daily-news-snap')
    monkeypatch.setenv('GITHUB_REF','refs/heads/main')
    monkeypatch.setattr(runtime,'GitHubJournal',journal)
    monkeypatch.setattr(runtime,'GitHubStore',lambda *a:None)
    monkeypatch.setattr(runtime,'Ledger',lambda *a,**kw:SimpleNamespace(limit_micro_usd=None))
    agent.receipts=[]
    monkeypatch.setattr(runtime,'Agents',lambda **kw:agent)
    monkeypatch.setattr(runtime,'Sources',lambda **kw:FakeSources())
    monkeypatch.setattr(runtime,'Renderer',lambda *a:renderer)
    monkeypatch.setattr(runtime,'datetime',SimpleNamespace(now=lambda *a:NOW))
    monkeypatch.setattr(published_memory,'PublishedMemory',lambda *a:SimpleNamespace(
        import_manual=lambda *a:None,reason=lambda *a:None))
    monkeypatch.setattr(candidate_memory,'CandidateMemory',lambda *a:SimpleNamespace(
        reason=lambda *a:None,record=lambda *a:None))
    monkeypatch.setattr('sys.argv',['runtime','--mode','fixed-preview','--lane','local','--output','runtime-out'])
    assert runtime.main()==0
    assert journals['autopilot-readiness'].read()=={}
    assert 'autopilot-ready-inventory' not in journals
    summary=json.loads((tmp_path/'runtime-out/summary.json').read_text())
    assert summary['results'][0]['status']=='awaiting_information_review'


def test_production_runtime_exposes_fixed_mode_and_separate_agent_prompts(monkeypatch,capsys):
    from publishing_v2.autopilot import runtime,agents,fixed_information
    assert agents.PROMPTS['fixed_information_writer']==fixed_information.WRITER_PROMPT
    assert agents.PROMPTS['fixed_information_text_review']==fixed_information.TEXT_REVIEW_PROMPT
    monkeypatch.setattr('sys.argv',['runtime','--help'])
    with pytest.raises(SystemExit) as e: runtime.main()
    assert e.value.code==0
    assert 'fixed-preview' in capsys.readouterr().out
