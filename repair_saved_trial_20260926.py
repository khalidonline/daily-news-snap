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
if state.get('status')!='held' or state.get('reason')!='verified_factual_contradiction': raise ValueError('unexpected_saved_state')
if any(x.get('event')=='bounded_repair_started' for x in state['audit']): raise ValueError('repair_already_attempted')
now=datetime.now(timezone.utc)
if datetime.fromisoformat(state['expires_at'])<=now: raise ValueError('saved_package_expired')
BundleClient().ensure_capacity(4)
state['audit'].append({'event':'bounded_repair_started','at':now.isoformat()});journal.save(state)
token=os.environ.get('DAILY_BUDGET_GITHUB_TOKEN') or os.environ['GITHUB_TOKEN']
ledger=Ledger(GitHubStore(os.environ['GITHUB_REPOSITORY'],token),limit_micro_usd=3000000)
agent=Agents(env=os.environ,ledger=ledger);agent.package_id=state['candidate']['id']
try:
    sources=restore_sources(state['sources'])
    official='https://www.konami.com/games/eu/en/topics/19323/'
    with urlopen(Request(official,headers={'User-Agent':'DailyNewsSnap/2.0'}),timeout=30) as response:
        if response.geturl()!=official: raise ValueError('unexpected_source_redirect')
        body=plain(response.read(2000000).decode())
    if 'September 24, 2026' not in body:raise ValueError('release_date_unverified')
    sources.append({'id':'konami-release','url':official,'text':body,'retrieved_text_sha256':hashlib.sha256(body.encode()).hexdigest()})
    # The fresh BBC report is the trigger; the release date stays September 24.
    stamp=state['candidate']['published_at'];quote='Reported at '+stamp
    sources.append({'id':'report-time','url':state['candidate']['url'],'text':quote,'source_type':'retrieved_feed_metadata'})
    timing={'eligible':True,'timing_basis':'report','event_date':datetime.fromisoformat(stamp).astimezone(policy.RIYADH).date().isoformat(),'event_source_id':'report-time','event_quote':quote,'reason':'Fresh BBC review is the current trigger. Actual release: September 24, 2026, verified with KONAMI.'}
    policy.validate_attention(state['candidate'],now);policy.validate_timing(timing,sources,now)
    research=copy.deepcopy(state['research']);research.update({k:timing[k] for k in ('event_date','event_source_id','event_quote')})
    for c in research['claims']:
        if c['id']=='c7':c['fact']='الجزء الجديد من تطوير Screen Burn في غلاسكو، وأحداثه في جزيرة اسكتلندية خيالية.'
    draft=copy.deepcopy(state['draft'])
    edits=[
      ('سايلنت هيل.. وش قصتها؟','سايلنت هيل سلسلة ألعاب رعب من كونامي. في أول لعبة، تدخل بلدة غامضة مع هاري ماسون، أب يدور على بنته المفقودة. القصة تبدأ ببحثه عنها، ومنها تتعرف على أسرار البلدة.','بدأت القصة بأب يدور على بنته'),
      ('البداية كانت مع فريق داخل كونامي','من ١٩٩٩ إلى ٢٠٠٤، طوّر فريق Team Silent أول أربعة أجزاء من السلسلة. هذي كانت المرحلة الأولى، قبل ما ينتقل تطوير ألعاب جديدة لفرق ثانية.','بعدها، تغيّر الفريق اللي يصنع اللعبة'),
      ('استوديوهات جديدة كملت السلسلة','بين ٢٠٠٧ و٢٠١٢، طوّرت شركات غربية أربع ألعاب للسلسلة، منها Origins وHomecoming وDownpour. استمرت سايلنت هيل، لكن صار ورا كل تجربة فريق مختلف.','والجزء الجديد جاي من غلاسكو'),
      ('هالمرة القصة في جزيرة اسكتلندية','في Townfall، تلعب بشخصية سايمون أورديل، اللي يوصل لجزيرة سانت أميليا الغارقة بالضباب. طوّر اللعبة استوديو Screen Burn الاسكتلندي. هنا تشوف المكان من عيون الشخصية وتكتشف أسراره معها.','الجزء الجديد نزل يوم ٢٤ سبتمبر ٢٠٢٦')]
    for card,(title,body,punch) in zip(draft['cards'],edits):card.update(title=title,body=body,punch=punch)
    # Add precise publisher-backed facts used only in the corrected final card.
    claims=[('c9','الجزء الجديد نزل يوم ٢٤ سبتمبر ٢٠٢٦','September 24, 2026'),('c10','اللعبة تعرض أحداثها من منظور الشخصية','fully first-person perspective')]
    for ident,fact,needle in claims:
        start=body.find(needle) if False else sources[-2]['text'].find(needle)
        if start<0:raise ValueError('official_claim_missing')
        exact=sources[-2]['text'][max(0,start-30):start+len(needle)+40]
        research['claims'].append({'id':ident,'fact':fact,'source_id':'konami-release','quote':exact})
    draft['cards'][3]['claim_ids']+=['c9','c10']
    policy.validate_research(research,sources,'daily',now);policy.validate_draft(draft,research)
    package=dict(copy.deepcopy(draft),sources=sources,research=research,lane='daily',candidate=state['candidate'],verified_timing=timing,expires_at=state['expires_at'],as_of=state['started_at'])
    approve_text(package,agent,sources)
    # Recover metadata by matching exact saved image bytes. Never repeat visual selection.
    source=Sources(recovery=True,publication_only=True)
    source.prime_images(state['candidate'],'Silent Hill')
    rows=source.subject_images('Silent Hill','Silent Hill')
    saved=Path('saved/package/daily/9ac357b6ba7af3e5/current')
    for i,card in enumerate(package['cards']):
        raw=(saved/f'source-{i:02d}.jpg').read_bytes();sha=hashlib.sha256(raw).hexdigest()
        matches=[r for r in rows if r.get('sha256')==sha]
        if not matches:raise ValueError('saved_image_metadata_not_recovered:'+str(i))
        card['image']=copy.deepcopy(matches[0])
    state.update(draft=draft,research=research,timing=timing,text_approval=package['text_approval'])
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
