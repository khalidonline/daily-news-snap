import copy
import hashlib
import json
import pytest
from test_fixed_information_writer import draft
from test_v2_fixed_draft_recovery import context
from publishing_v2.autopilot import fixed_preparation as preparation


def validated():
    raw=draft(); normalized=copy.deepcopy(raw); edited=copy.deepcopy(raw)
    edited['cards'][0]['punch']='خلاصة قصيرة'
    artifacts={k:{'text':json.dumps(v,ensure_ascii=True)+'\n'} for k,v in
        [('raw',raw),('normalized',normalized),('context',{'context_sha256':'a'*64})]}
    for row in artifacts.values(): row['sha256']=hashlib.sha256(row['text'].encode()).hexdigest()
    return {'raw':raw,'normalized':normalized,'edited_draft':edited,'artifacts':artifacts,
            'changes':[{'path':'cards[0].punch','before':raw['cards'][0]['punch'],'after':'خلاصة قصيرة'}]}


def test_preserves_original_bindings_separately_and_never_calls_writer(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    data=validated()
    monkeypatch.setattr(preparation,'validate_saved_draft',lambda request,research:copy.deepcopy(data),raising=False)
    request={'kind':'saved_draft'}
    result=preparation._persisted_editorial_draft(request,context(),tmp_path/'out')
    assert result==data['edited_draft']
    for key,row in data['artifacts'].items():
        assert (tmp_path/f'out/fixed-writer-{key}.json').read_bytes()==row['text'].encode()
    audit=json.loads((tmp_path/'out/fixed-editorial-repair.json').read_text())
    assert audit['fresh_context_sha256']!=json.loads(data['artifacts']['context']['text'])['context_sha256']
    assert audit['approved'] is False and audit['preview_allowed'] is False
    assert audit['publish_authorized'] is False
    assert audit['changes']==data['changes']
    assert preparation._persisted_editorial_draft(request,context(),tmp_path/'out')==result


@pytest.mark.parametrize('symlink',[False,True])
def test_existing_changed_or_symlink_artifact_fails_closed(tmp_path,monkeypatch,symlink):
    monkeypatch.chdir(tmp_path);data=validated()
    monkeypatch.setattr(preparation,'validate_saved_draft',lambda *a:copy.deepcopy(data),raising=False)
    out=tmp_path/'out';out.mkdir()
    if symlink:
        target=tmp_path/'target';target.write_text(data['artifacts']['raw']['text'])
        (out/'fixed-writer-raw.json').symlink_to(target)
    else: (out/'fixed-writer-raw.json').write_text('changed')
    with pytest.raises(ValueError): preparation._persisted_editorial_draft({},context(),out)


def test_preparer_saved_route_still_fails_fit_before_review(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(preparation,'_persisted_editorial_draft',lambda *a:draft(),raising=False)
    monkeypatch.setattr(preparation,'prepare_text',lambda *a:{'fit':False,'violations':['synthetic']})
    class Agent:
        def run(self,*a,**k): pytest.fail('writer or reviewer before fit')
    prep=preparation.FixedInformationPreparer(Agent(),object())
    prep.saved_draft_recovery={'kind':'saved_draft'}
    with pytest.raises(ValueError,match='does_not_fit'): prep(context(),'out')


def test_saved_route_requires_fresh_independent_review_before_visual(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(preparation,'_persisted_editorial_draft',lambda *a:draft())
    monkeypatch.setattr(preparation,'prepare_text',lambda *a:{'fit':True})
    calls=[]
    def review(package,agent,sources):
        calls.append((package,sources))
        assert sources==context()['original_sources']
        assert package['cards']==draft()['cards']
        raise ValueError('independent_source_review_rejected')
    monkeypatch.setattr(preparation.fixed,'approve_text',review)
    class Forbidden:
        def run(self,*a,**k): pytest.fail('unexpected writer')
        def image_catalog(self,*a,**k): pytest.fail('visual before independent review')
    prep=preparation.FixedInformationPreparer(Forbidden(),Forbidden())
    prep.saved_draft_recovery={'kind':'saved_draft'}
    with pytest.raises(ValueError,match='independent_source_review_rejected'): prep(context(),'out')
    assert len(calls)==1
