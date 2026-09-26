import copy,json,hashlib,os
from pathlib import Path
from datetime import datetime,timezone
from daily_budget import Ledger,GitHubStore
from publishing_v2.bundle_api import GitHubJournal
from publishing_v2.autopilot.runtime import engine_id,shadow_record
from publishing_v2.autopilot.agents import Agents
from publishing_v2.autopilot import policy
from publishing_v2.autopilot.feedback import rejected_trigger,EDITORIAL_FEEDBACK
from publishing_v2.editorial_production import approve_text
from recover_held_reviewer import restore_sources,attach_saved_timing_evidence
now=datetime.now(timezone.utc);source=GitHubJournal('autopilot-2026-09-25-local-live').read()
if source.get('status')!='published' or rejected_trigger(source['candidate']):raise ValueError('prior_package_not_eligible')
engine=engine_id();slot='autopilot-validation-2026-09-26-local-'+engine[:16];journal=GitHubJournal(slot)
if journal.read():raise ValueError('validation_already_attempted')
state={'status':'working','engine':engine,'lane':'local','mode':'shadow','started_at':now.isoformat(),'audit':[]};journal.save(state)
agent=Agents(env=os.environ,ledger=Ledger(GitHubStore(os.environ['GITHUB_REPOSITORY'],os.environ.get('DAILY_BUDGET_GITHUB_TOKEN') or os.environ['GITHUB_TOKEN']),limit_micro_usd=3000000));agent.package_id='validation:'+source['candidate']['id']
root=Path('validation-output');root.mkdir(exist_ok=True)
try:
    hashes={hashlib.sha256(p.read_bytes()).hexdigest():p for p in Path('local-saved').rglob('*.jpg')}
    paths=[hashes[h] for h in source['approval']['media_sha256']]
    package=copy.deepcopy(source['package']);policy.verify_seal(package,paths,source['approval'],now)
    originals=attach_saved_timing_evidence(restore_sources(source['sources']),source['timing'])
    policy.validate_attention(source['candidate'],now);policy.validate_timing(source['timing'],originals,now)
    policy.validate_research(source['research'],originals,'local',now)
    package['editorial_feedback']=EDITORIAL_FEEDBACK
    approve_text(package,agent,originals)
    data=dict(copy.deepcopy(package),original_sources=originals)
    review=agent.run('reviewer',data,images=paths);review['input_sha256']=policy.digest(data)
    (root/'review.json').write_text(json.dumps(review,ensure_ascii=False));policy.validate_review(review,len(paths))
    approval=policy.seal(package,paths);policy.verify_seal(package,paths,approval,datetime.now(timezone.utc))
    state.update(status='shadow_passed',package=package,review=review,approval=approval,source_validation_slot='autopilot-2026-09-25-local-live')
    ready=GitHubJournal('autopilot-readiness');rows=ready.read();rows['local']=shadow_record(state,engine,slot);ready.save(rows)
except Exception as error:state.update(status='held',reason=str(error));raise
finally:
    state['agent_receipts']=agent.receipts;journal.save(state);(root/'result.json').write_text(json.dumps({'status':state['status'],'reason':state.get('reason'),'cost_micro_usd':sum(x['cost_micro_usd'] for x in agent.receipts),'new_packages':0,'posts':0}))
