"""Archive exact final 9 October packages as independent Saved Stories.
No uploads, production, paid models, reposts, deletions, or duration changes."""
import hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path
from daily_budget import GitHubStore, day_key
from publishing_v2.bundle_api import BundleError, GitHubJournal
from publishing_v2.saved_story_api import SavedClient, SavedJournal, now, save_story, validate_archive

BASE=Path('approved/saved-stories/daily-20261009')
ORDER=['ikea-20261009','shopping-cart-20261009','postal-20261009']
RESERVE=2

class StateFile(GitHubJournal):
    def __init__(self,path):
        super().__init__('archive-daily-20261009'); self.path='/contents/'+path

def prepare(approval, receipts, backlog):
    a=approval; current=datetime.now(timezone.utc)
    if (a.get('approved') is not True or a.get('account')!='executivesaudi'
        or a.get('scope')!='SAVED_STORY_ONLY' or not a.get('authorization')
        or not a.get('visual_review') or a.get('package') not in ORDER):
        raise ValueError('independent_archive_approval_required')
    start=datetime.fromisoformat(a['not_before'].replace('Z','+00:00'))
    expiry=datetime.fromisoformat(a['expires_at'].replace('Z','+00:00'))
    if start.tzinfo is None or expiry.tzinfo is None or not start<=current<expiry:
        raise ValueError('archive_approval_outside_window')
    entry=next((b for b in backlog if b.get('identity')==a['source_backlog_identity']),None)
    if not entry or entry.get('status') not in ('PENDING_SAVE_APPROVAL','PENDING_FINAL_COMPOSITION_REVIEW','POSTED'):
        raise ValueError('source_backlog_not_final')
    if len(a['sources'])>1:
        expected=[{'identity':s['identity'],'card':1,**({'receipt_key':s['receipt_key']} if s['receipt_key']!=s['identity'] else {})} for s in a['sources']]
        if entry.get('delivery_card_sources')!=expected:
            raise ValueError('final_composition_changed')
    elif entry['identity']!=a['sources'][0]['identity']:
        raise ValueError('source_identity_changed')
    rows=[];hashes=[]
    for s in a['sources']:
        manifest_raw=Path(s['manifest']).read_bytes()
        actual_manifest_sha=hashlib.sha256(manifest_raw).hexdigest()
        if actual_manifest_sha!=s['manifest_sha256']:
            raise ValueError('source_manifest_binding_changed: actual='+actual_manifest_sha+' expected='+s['manifest_sha256'])
        receipt=receipts[s['receipt_key']]
        if s['receipt_key']!=s['identity']:
            auth=receipt.get('authorization',{})
            if (auth.get('approved') is not True or auth.get('account')!='executivesaudi'
                or auth.get('content_identity')!=s['identity'] or auth.get('delivery_key')!=s['receipt_key']
                or not auth.get('owner_authorization') or len(rows)!=1
                or receipt.get('1',{}).get('content_identity')!=s['identity']
                or receipt.get('1',{}).get('ordered_after_post_id')!=rows[-1]['post_id']):
                raise ValueError('reorder_lineage_mismatch')
        child=dict(a,**s)
        try:
            _,_,part=validate_archive(child,receipt)
        except (BundleError,KeyError,OSError) as e:
            raise ValueError('source_validation_failed: '+str(e)) from None
        manifest=json.loads(manifest_raw)
        actual=[m['sha256'] for m in manifest['media']]
        if actual!=s['media_sha256']: raise ValueError('source_media_binding_changed')
        hashes+=actual;rows+=part
    identity=hashlib.sha256(('executivesaudi:'+':'.join(hashes)).encode()).hexdigest()
    if identity!=a['identity'] or hashes!=a['media_sha256'] or len(set(hashes))!=len(hashes):
        raise ValueError('archive_composition_identity_mismatch')
    if len({r['post_id'] for r in rows})!=len(rows) or len({r['upload_id'] for r in rows})!=len(rows):
        raise ValueError('duplicate_source_delivery')
    return identity,a['title'],rows

def check_live(c,rows):
    for r in rows:
        live=c.call('/post/'+r['post_id']); snap=(live.get('data') or {}).get('SNAPCHAT') or {}
        ext=(live.get('externalData') or {}).get('SNAPCHAT') or {}
        if (live.get('id')!=r['post_id'] or live.get('teamId')!=c.team or live.get('status')!='POSTED'
            or live.get('deletedAt') or snap.get('type')!='STORY' or snap.get('uploadIds')!=[r['upload_id']]
            or snap.get('storyDuration')!='ONE_WEEK' or not ext.get('id')
            or (r.get('snapchat_id') and ext['id']!=r['snapchat_id'])):
            raise BundleError('source_live_mismatch')

def check_budget():
    store=GitHubStore(os.environ['GITHUB_REPOSITORY'],os.environ['GITHUB_TOKEN']);checks=[]
    for day in sorted({'2026-10-09',day_key()}):
        _,row=store.read(day); charged=None
        if row is not None:
            if row.get('day')!=day or not isinstance(row.get('entries'),dict): raise BundleError('invalid_cost_ledger')
            values=[e.get('charged_micro_usd') for e in row['entries'].values()]
            if any(type(v) is not int or v<0 for v in values): raise BundleError('invalid_cost_entries')
            charged=sum(values)
            if charged>3_000_000: raise BundleError('daily_budget_exceeded')
        checks.append({'day':day,'ledger_present':row is not None,'recorded_micro_usd':charged})
    return checks

def main():
    c=SavedClient();c.check()
    audit=StateFile('saved-story-audits/daily-20261009.json')
    report=audit.read() or {'results':[],'held':[],'started_at':now()}
    report.update(budget_checks=check_budget(),paid_model_requests=0,paid_image_requests=0,uploads=0,reserve=RESERVE,missing_ledger_not_zero=True,run_url='https://github.com/'+os.environ['GITHUB_REPOSITORY']+'/actions/runs/'+os.environ['GITHUB_RUN_ID'])
    report['quota_before']=c.ensure_capacity(RESERVE);audit.save(report)
    print('PREFLIGHT '+json.dumps({k:report[k] for k in ('budget_checks','quota_before')},ensure_ascii=False),flush=True)
    for name in ORDER:
        path=BASE/(name+'.json');a=json.loads(path.read_text());source_state=StateFile('saved-story-backlog.json');backlog=source_state.read()
        try:
            receipts={s['receipt_key']:GitHubJournal(s['receipt_key']).read() for s in a['sources']}
            identity,title,rows=prepare(a,receipts,backlog['packages']);check_live(c,rows)
            uploads=[r['upload_id'] for r in rows];found=c.find(identity,title,uploads)
            if len(found)>1: raise BundleError('multiple_existing_saved_stories')
            journal=SavedJournal(identity);prior=journal.read()
            if prior and not prior.get('post_id') and not found: raise BundleError('ambiguous_saved_story_intent')
            check_budget()
            if not prior and not found: c.ensure_capacity(RESERVE+1)
            result=save_story(c,journal,identity,title,uploads)
            confirmed=c.confirm(result['post_id'],title,uploads)
            ext=(confirmed.get('externalData') or {}).get('SNAPCHAT') or {}
            ids=ext.get('mediaIds') or []
            if not ext.get('id') or len(ids)!=len(rows) or len(set(ids))!=len(ids):
                raise BundleError('saved_story_external_confirmation_incomplete')
            result.update(approval=str(path),package=name,scope='SAVED_STORY_ONLY',source_manifests=a['sources'],media_sha256=a['media_sha256'],run_url=report['run_url'])
            journal.save(result)
            source_state=StateFile('saved-story-backlog.json');backlog=source_state.read()
            entry=next(b for b in backlog['packages'] if b.get('identity')==a['source_backlog_identity'])
            entry.update(status='POSTED',archive_status='POSTED',saved_identity=identity,saved_story_id=ext['id'],saved_post_id=result['post_id'],saved_title=title,saved_receipt_path='saved-story-receipts/'+identity+'.json',saved_confirmed_at=now(),saved_card_count=len(rows),archive_approval=str(path))
            backlog['updated_at']=now();source_state.save(backlog)
            output={'package':name,'title':title,'status':'POSTED','saved_story_id':ext['id'],'post_id':result['post_id'],'cards':len(rows),'new':not prior and not found}
            report['results']=[r for r in report['results'] if r['package']!=name]+[output]
            report['held']=[r for r in report['held'] if r['package']!=name]
            audit.save(report);print('SAVED '+json.dumps(output,ensure_ascii=False),flush=True)
        except (BundleError,ValueError,KeyError,OSError) as e:
            held={'package':name,'reason':str(e),'checked_at':now()}
            report['held']=[r for r in report['held'] if r['package']!=name]+[held];audit.save(report)
            print('HELD '+json.dumps(held,ensure_ascii=False),flush=True)
            # Existing SENDING intent is preserved; nothing is retried here.
    report['quota_after']=c.ensure_capacity(RESERVE);report['completed_at']=now();audit.save(report)
    print('COMPLETE '+json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__': main()

