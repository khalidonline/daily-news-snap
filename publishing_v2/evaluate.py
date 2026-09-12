"""Isolated historical evaluation. No production imports or publishing calls."""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Mapping
from .providers import check_access, generate, search_getty

ROOT = Path(__file__).resolve().parents[1]
PRICES = {'openai': (10, 50), 'anthropic': (2, 10)}  # USD / million, 2026-09-12
MODELS = {'openai':'gpt-6-astra', 'anthropic':'claude-sonnet-5'}
MAX_OUTPUT = 6000
CAP_USD = 10


def load_cases():
    return json.loads((ROOT/'evaluation/event_packages.json').read_text())['cases']


def validate_package(payload, case):
    """References/shape only: never a factual, aesthetic or editorial approval."""
    errors = []
    if not isinstance(payload, dict): return ['package_not_object']
    if payload.get('event_id') != case['id']: errors.append('wrong_event')
    if payload.get('historical_replay') is not True: errors.append('replay_label_missing')
    allowed = {f['id']:s['id'] for s in case['sources'] for f in s['facts']}
    seen = set()
    for kind, count in [('info',1), ('topic',1), ('story',6)]:
        post = payload.get(kind)
        if not isinstance(post,dict):
            errors.append(f'{kind}:missing'); continue
        if not isinstance(post.get('title'),str) or not post['title'].strip(): errors.append(f'{kind}:title')
        frames = post.get('frames')
        if not isinstance(frames,list) or len(frames) != count:
            errors.append(f'{kind}:frame_count'); continue
        for frame in frames:
            if not isinstance(frame,dict):
                errors.append(f'{kind}:frame'); continue
            for field in ('text','image_query'):
                if not isinstance(frame.get(field),str) or not frame[field].strip(): errors.append(f'{kind}:{field}')
            claims = frame.get('claims')
            if not isinstance(claims,list) or not claims:
                errors.append(f'{kind}:claims'); continue
            for claim in claims:
                if not isinstance(claim,dict):
                    errors.append(f'{kind}:claim'); continue
                fact = claim.get('fact_id'); source = claim.get('source_id')
                if not isinstance(fact,str) or not isinstance(source,str) or allowed.get(fact) != source:
                    errors.append(f'{kind}:unknown_reference'); continue
                if fact in seen: errors.append(f'{kind}:repeated_fact')
                seen.add(fact)
    return errors


class Ledger:
    """Persistent conservative reservations; unknown calls are never refunded."""
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS spend (key TEXT PRIMARY KEY, amount INTEGER NOT NULL, state TEXT NOT NULL)')

    def connect(self): return sqlite3.connect(self.path, timeout=30)

    def total(self):
        with self.connect() as db: return db.execute('SELECT COALESCE(SUM(amount),0) FROM spend').fetchone()[0]/1_000_000

    def reserve(self, key, usd):
        import math
        if not isinstance(usd,(int,float)) or not math.isfinite(usd) or usd <= 0: raise ValueError('invalid reservation')
        amount = math.ceil(usd*1_000_000)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM spend WHERE key=?',(key,)).fetchone(): return False
            total = db.execute('SELECT COALESCE(SUM(amount),0) FROM spend').fetchone()[0]
            if total + amount > CAP_USD*1_000_000: return False
            db.execute('INSERT INTO spend VALUES (?,?,?)',(key,amount,'reserved'))
        return True

    def settle(self, key, usage, provider):
        if not isinstance(usage,dict): raise ValueError('invalid usage')
        for field in ('input_tokens','output_tokens'):
            if type(usage.get(field)) is not int or usage[field]<0: raise ValueError('invalid usage')
        # No caching requested; charge any reported cache reads/creation conservatively.
        extra = 0
        for field in ('cache_creation_input_tokens','cache_read_input_tokens'):
            value = usage.get(field,0)
            if type(value) is not int or value<0: raise ValueError('invalid cache usage')
            extra += value
        inp,out = PRICES[provider]
        amount = (usage['input_tokens']+extra)*inp + usage['output_tokens']*out
        with self.connect() as db:
            row=db.execute('SELECT amount FROM spend WHERE key=?',(key,)).fetchone()
            if row is None: raise ValueError('missing reservation')
            if amount>row[0]: raise ValueError('usage exceeded conservative bound; stop evaluation')
            db.execute('UPDATE spend SET amount=?,state=? WHERE key=?',(amount,'settled',key))


def _save(path, value, env):
    secrets = {form for name, secret in env.items()
               if any(word in name for word in ('KEY','TOKEN','SECRET'))
               for form in (secret,secret.strip()) if form}
    def scrub(item):
        if isinstance(item,str):
            for secret in sorted(secrets,key=len,reverse=True):
                item=item.replace(secret,'[REDACTED]')
            return item
        if isinstance(item,list): return [scrub(x) for x in item]
        if isinstance(item,dict): return {scrub(k):scrub(v) for k,v in item.items()}
        return item
    raw = json.dumps(scrub(value),ensure_ascii=False,indent=2)
    temp=path.with_suffix(path.suffix+'.tmp')
    with temp.open('w') as fh:
        fh.write(raw+'\n'); fh.flush(); os.fsync(fh.fileno())
    temp.replace(path)


def _prompt(case):
    return ('Historical editorial replay only. Write engaging concise Arabic Snapchat content as of replay_date. '
        'News is a trigger, never a separate post. Follow each format objective. Use ONLY the supplied facts; '
        'never invent dialogue, incidents, specifications or current claims. Each fact may appear only once. '
        'Return ONLY a JSON object with event_id, historical_replay:true, info, topic, story. Each post has title '
        'and frames. Info and Topic each have one frame; Story has six sequential true-story frames. '
        'Each frame has text, image_query for a real relevant photo, and nonempty claims array of '
        '{source_id,fact_id}. Cover every factual claim with a reference. Do not assert you found or licensed an image. '
        'No quality scores, no publishing instructions. Evidence package:\n'+json.dumps(case,ensure_ascii=False))


def run(mode, output:Path, *, env:Mapping[str,str], allow_paid=False):
    if mode not in {'offline','readiness','models','images'}: raise ValueError('unknown mode')
    if mode in {'models','images'} and not allow_paid: raise ValueError('Live evaluation requires --allow-paid')
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    # Prevent two processes sharing one run directory from racing receipts/reservations.
    with (output/'.evaluation.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return _run(mode,output,env,allow_paid)


def _run(mode,output,env,allow_paid):
    cases=load_cases()
    report={'mode':mode,'historical_replay':True,'winner':None,'editorial_approved':False,
            'visual_approved':False,'licensing_verified':False,'production_deployed':False,
            'results':[],'status':'incomplete'}
    if mode=='offline':
        report.update(status='offline_ready',case_ids=[c['id'] for c in cases],
            detail='Corpus loaded. No provider, image, rendering or delivery acceptance claimed.')
    elif mode=='readiness':
        report['results']=[check_access(p,env) for p in ['openai','anthropic','getty','reuters','gcp']]
        report['status']='access_report_only'
    elif mode=='images':
        for case in cases:
            row={'event_id':case['id'],'provider':'getty','status':'missing_credentials'}
            if env.get('GETTY_API_KEY','').strip():
                try:
                    row['candidates']=search_getty(case['image_query'],env=env)
                    row['status']='metadata_only' if row['candidates'] else 'no_candidates'
                except Exception: row['status']='request_failed'
            report['results'].append(row)
            _save(output/'report.json',report,env)
        report['detail']='Discovery only. Historical date/entity match, frame-level relevance, usable download rights, crops and final visuals require separate review.'
    else:
        ledger=Ledger(output/'spend.sqlite')
        stop=False
        for provider in MODELS:
            for case in cases:
                row={'provider':provider,'event_id':case['id'],'status':'missing_credentials'}
                credential='OPENAI_API_KEY' if provider=='openai' else 'ANTHROPIC_API_KEY'
                prompt=_prompt(case)
                prompt_bytes=len(prompt.encode('utf-8'))
                key=hashlib.sha256((MODELS[provider]+prompt).encode()).hexdigest()
                response_path=output/f'{provider}-{case["id"]}-{key[:12]}-response.json'
                row['response_file']=response_path.name
                response=None
                if stop:
                    row['status']='stopped_after_persistence_or_usage_error'
                elif response_path.exists():
                    try:
                        response=json.loads(response_path.read_text())
                        row['reused_checkpoint']=True
                    except Exception:
                        row['status']='checkpoint_invalid_stop'; stop=True
                elif env.get(credential,'').strip():
                    if prompt_bytes>40000:
                        row['status']='prompt_limit'
                    else:
                        inp,out=PRICES[provider]
                        reserve=((prompt_bytes+4096)*inp+MAX_OUTPUT*out)/1_000_000
                        if not ledger.reserve(key,reserve):
                            row['status']='previous_attempt_or_budget_limit'
                        else:
                            try:
                                response=generate(provider,prompt,env=env,max_output_tokens=MAX_OUTPUT)
                            except Exception:
                                row['status']='request_failed_or_unknown'
                            if response is not None:
                                try: _save(response_path,response,env)
                                except Exception:
                                    row['status']='checkpoint_failed_stop'; stop=True
                if response is not None and not stop:
                    try: ledger.settle(key,response['usage'],provider)
                    except (ValueError,KeyError,TypeError):
                        row['status']='usage_invalid_stop'; stop=True
                    if not stop:
                        try: payload=json.loads(response['text'])
                        except (ValueError,TypeError,KeyError): payload=None
                        row['structural_errors']=validate_package(payload,case)
                        row['status']='structure_pass_review_required' if not row['structural_errors'] else 'structure_failed'
                report['results'].append(row)
                report['reserved_or_spent_usd']=ledger.total()
                _save(output/'report.json',report,env)
        if all(r['status']=='structure_pass_review_required' for r in report['results']):
            report['status']='generated_awaiting_human_review'
        report['detail']='Structural checks do not verify factual entailment, Arabic quality, novelty or visual suitability. Unknown paid attempts retain full reservations; never auto-retry.'
    _save(output/'report.json',report,env)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['offline','readiness','models','images'],default='offline')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--allow-paid',action='store_true')
    args=parser.parse_args()
    try:
        report=run(args.mode,args.output,env=os.environ,allow_paid=args.allow_paid)
    except Exception:
        print('Evaluation could not complete. No raw provider error is logged.'); return 2
    print(json.dumps({'status':report['status'],'mode':args.mode,'report':str(args.output/'report.json')}))
    return 0 if report['status'] in {'offline_ready','access_report_only','generated_awaiting_human_review'} else 1

if __name__=='__main__': raise SystemExit(main())
