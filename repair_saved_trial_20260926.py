"""One bounded repair of the saved, held Daily trial. No new package discovery."""
import copy, hashlib, json, os
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from daily_budget import Ledger, GitHubStore
from publishing_v2.bundle_api import GitHubJournal, BundleClient
from publishing_v2.autopilot.runtime import Renderer, engine_id, rollout_ready, shadow_record
from publishing_v2.autopilot.agents import Agents
from publishing_v2.autopilot.sources import Sources, plain
from publishing_v2.autopilot import policy
from publishing_v2.editorial_production import approve_text
from recover_held_reviewer import restore_sources, attach_saved_timing_evidence

SLOT='autopilot-2026-09-26-daily-shadow-5771c0d01ff16a95'
ROOT=Path('repair-output'); ROOT.mkdir(exist_ok=True)
journal=GitHubJournal(SLOT); state=journal.read()
if state.get('status')!='held' or state.get('reason') not in {'verified_factual_contradiction','saved_image_metadata_not_recovered:0','saved_image_metadata_not_recovered:2'}: raise ValueError('unexpected_saved_state')
if sum(x.get('event')=='bounded_repair_started' for x in state['audit'])>=3: raise ValueError('repair_already_attempted')
now=datetime.now(timezone.utc)
if datetime.fromisoformat(state['expires_at'])<=now: raise ValueError('saved_package_expired')
BundleClient().ensure_capacity(4)
state['audit'].append({'event':'bounded_repair_started','at':now.isoformat()});journal.save(state)
token=os.environ.get('DAILY_BUDGET_GITHUB_TOKEN') or os.environ['GITHUB_TOKEN']
ledger=Ledger(GitHubStore(os.environ['GITHUB_REPOSITORY'],token),limit_micro_usd=3000000)
agent=Agents(env=os.environ,ledger=ledger);agent.package_id=state['candidate']['id']
try:
    package=copy.deepcopy(state['repair_package'])
    from publishing_v2.editorial_production import require_text_approval
    require_text_approval(package)
    sources=package['sources']; research=package['research']; timing=package['verified_timing'];draft=copy.deepcopy(package)
    # Recover metadata by matching exact saved image bytes. Never repeat visual selection.
    source=Sources(recovery=True,publication_only=True)
    from publishing_v2.autopilot.sources import fetch
    url=state['candidate']['url']
    source.article_html[url]=fetch(url).decode()
    source.prime_images(state['candidate'],'Silent Hill')
    rows=source.subject_images('Silent Hill','Silent Hill')
    rows+=source.subject_images('Konami headquarters','Konami')
    from publishing_v2.public_images import download_image
    for row in source.primary_pools.get('Silent Hill',[]):
        try:
            raw=download_image(row); row['sha256']=hashlib.sha256(raw).hexdigest();rows.append(row)
        except Exception:pass
    saved=Path('saved/package/daily/9ac357b6ba7af3e5/current')
    for i,card in enumerate(package['cards']):
        raw=(saved/f'source-{i:02d}.jpg').read_bytes();sha=hashlib.sha256(raw).hexdigest()
        matches=[r for r in rows if r.get('sha256')==sha]
        if not matches:raise ValueError('saved_image_metadata_not_recovered:'+str(i))
        card['image']=copy.deepcopy(matches[0])
    state.update(repair_package=copy.deepcopy(package),research=research,timing=timing,text_approval=package['text_approval'])
    journal.save(state)
    paths=Renderer(agent,source)(package,ROOT/'cards')
    (ROOT/'package.json').write_text(json.dumps(package,ensure_ascii=False))
    snapshot=policy.seal(package,paths)
    review_input=dict(copy.deepcopy(package),original_sources=sources)
    review=agent.run('reviewer',review_input,images=paths);review['input_sha256']=policy.digest(review_input)
    (ROOT/'review.json').write_text(json.dumps(review,ensure_ascii=False))
    policy.validate_review(review,len(paths));policy.verify_seal(package,paths,snapshot,datetime.now(timezone.utc))
    state.update(status='shadow_passed',reason=None,package=package,paths=[str(p) for p in paths],approval=snapshot,review=review)
    state['audit'].append({'event':'bounded_repair_passed','at':datetime.now(timezone.utc).isoformat(),'corrected_cards':[0,1,2,3]})
    readiness=GitHubJournal('autopilot-readiness');ready=readiness.read();ready['daily']=shadow_record(state,state['engine'],SLOT);readiness.save(ready)
    state['delivery_hold']='readiness_blocked' if not rollout_ready(ready,engine_id(),datetime.now(timezone.utc)) else 'ready_for_saved_delivery'
except Exception as error:
    state.update(status='held',reason=str(error));raise
finally:
    state.setdefault('agent_receipts',[]).extend(agent.receipts);journal.save(state)
    (ROOT/'result.json').write_text(json.dumps({'status':state['status'],'reason':state.get('reason'),'delivery_hold':state.get('delivery_hold'),'cost_micro_usd':sum(x['cost_micro_usd'] for x in agent.receipts),'confirmed_cards':0},ensure_ascii=False))
