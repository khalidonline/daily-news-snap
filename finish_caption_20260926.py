import copy,json,os
from datetime import datetime,timezone
from pathlib import Path
from daily_budget import Ledger,GitHubStore
from publishing_v2.bundle_api import GitHubJournal,BundleClient
from publishing_v2.autopilot.agents import Agents
from publishing_v2.autopilot.runtime import Renderer,engine_id,rollout_ready,shadow_record
from publishing_v2.autopilot import policy
from publishing_v2.editorial_production import approve_text
SLOT='autopilot-2026-09-26-daily-shadow-5771c0d01ff16a95'
root=Path('repair-output'); journal=GitHubJournal(SLOT);state=journal.read()
if state['status']!='held' or state['reason']!='editorial_review_rejected':raise ValueError('unexpected_state')
if any(x['event']=='caption_repair_started' for x in state['audit']):raise ValueError('already_attempted')
BundleClient().ensure_capacity(4)
package=json.loads((root/'package.json').read_text());old=json.loads((root/'review.json').read_text())
if old.get('repair_indices')!=[3]:raise ValueError('unexpected_repair_scope')
state['audit'].append({'event':'caption_repair_started','at':datetime.now(timezone.utc).isoformat()});journal.save(state)
agent=Agents(env=os.environ,ledger=Ledger(GitHubStore(os.environ['GITHUB_REPOSITORY'],os.environ.get('DAILY_BUDGET_GITHUB_TOKEN') or os.environ['GITHUB_TOKEN']),limit_micro_usd=3000000));agent.package_id=state['candidate']['id']
try:
    before=[(root/'cards'/f'card-{i:02d}.jpg').read_bytes() for i in range(3)]
    package['cards'][3]['image_caption']='سايمون أورديل، بطل اللعبة'
    approve_text(package,agent,package['sources'])
    paths=Renderer(None,None)(package,root/'cards')
    assert before==[p.read_bytes() for p in paths[:3]],'unaffected_cards_changed'
    (root/'package.json').write_text(json.dumps(package,ensure_ascii=False))
    seal=policy.seal(package,paths);data=dict(copy.deepcopy(package),original_sources=package['sources'])
    review=agent.run('reviewer',data,images=paths);review['input_sha256']=policy.digest(data)
    (root/'review.json').write_text(json.dumps(review,ensure_ascii=False));policy.validate_review(review,len(paths))
    policy.verify_seal(package,paths,seal,datetime.now(timezone.utc))
    state.update(status='shadow_passed',reason=None,package=package,review=review,approval=seal,paths=[str(p) for p in paths])
    ready=GitHubJournal('autopilot-readiness');rows=ready.read();rows['daily']=shadow_record(state,state['engine'],SLOT);ready.save(rows)
    state['delivery_hold']='ready_for_saved_delivery' if rollout_ready(rows,engine_id(),datetime.now(timezone.utc)) else 'readiness_blocked'
except Exception as error:state.update(status='held',reason=str(error));raise
finally:
    state['agent_receipts'].extend(agent.receipts);journal.save(state)
    (root/'result.json').write_text(json.dumps({'status':state['status'],'reason':state.get('reason'),'delivery_hold':state.get('delivery_hold'),'cost_micro_usd':sum(r['cost_micro_usd'] for r in agent.receipts),'confirmed_cards':0}))
