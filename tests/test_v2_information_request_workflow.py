import json
import subprocess
import os
import sys
from pathlib import Path
import pytest
import yaml
from test_v2_information_request import authorized, preview, draft, base_draft, remote, NOW, module, commit

ROOT=Path(__file__).resolve().parents[1]

def test_workflow_registration_is_explicit_and_preserves_recovery():
    w=yaml.safe_load((ROOT/'.github/workflows/publish-approved-package.yml').read_text())
    events=w.get('on',w.get(True))
    assert events.get('push')=={'branches':['main'],'paths':['.github/information-publish-request.json']}
    assert 'workflow_dispatch' in events
    assert w['concurrency']=={'group':'executivesaudi-approved-api','cancel-in-progress':False}
    checkout=w['jobs']['publish']['steps'][0]
    assert checkout['with']['ref']=='${{ github.sha }}'
    assert checkout['with']['fetch-depth']==0
    assert not (ROOT/'.github/information-publish-request.json').exists()

def event(root,before):
    return {'ref':'refs/heads/main','before':before,'after':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
            'repository':{'full_name':'khalidonline/daily-news-snap'},'deleted':False,'forced':False}

def test_multi_commit_push_resolves_exact_request(authorized):
    root,r=authorized;m=module()
    before=subprocess.check_output(['git','rev-parse','HEAD~1'],cwd=root,text=True).strip()
    (root/'readme.txt').write_text('unrelated followup');commit(root)
    assert m.resolve_push(root,event(root,before),NOW)==root/'approved/radio-school-20261031'

def test_cli_executes_resolver_in_real_process(authorized):
    root,r=authorized
    before=subprocess.check_output(['git','rev-parse','HEAD~1'],cwd=root,text=True).strip()
    p=root/'event.json';p.write_text(json.dumps(event(root,before)))
    result=subprocess.run([sys.executable,'-m','publishing_v2.information_request','resolve-push','--event',str(p)],
                          cwd=root,env={**os.environ,'PYTHONPATH':str(ROOT)},capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='package=radio-school-20261031'

@pytest.mark.parametrize('fault',['ordinary','wrong_head','wrong_branch','forced','zero_before','deleted','modified_worktree'])
def test_invalid_push_never_resolves_publication(authorized,fault):
    root,r=authorized;m=module()
    before=subprocess.check_output(['git','rev-parse','HEAD~1'],cwd=root,text=True).strip()
    e=event(root,before)
    if fault=='ordinary':
        e['before']=e['after'];(root/'readme.txt').write_text('ordinary');commit(root);e['after']=event(root,e['before'])['after']
    elif fault=='wrong_head':e['after']='a'*40
    elif fault=='wrong_branch':e['ref']='refs/heads/other'
    elif fault=='forced':e['forced']=True
    elif fault=='zero_before':e['before']='0'*40
    elif fault=='deleted':e['deleted']=True
    else:(root/m.REQUEST_PATH).write_text('{}')
    with pytest.raises((ValueError,subprocess.CalledProcessError)):
        m.resolve_push(root,e,NOW)

def test_cli_rejects_bad_event_without_provider(authorized,tmp_path,monkeypatch):
    root,_=authorized;m=module();p=root/'event.json';p.write_text('{}')
    monkeypatch.setattr('sys.argv',['information_request','resolve-push','--event',str(p)])
    with pytest.raises(ValueError):m.main()
