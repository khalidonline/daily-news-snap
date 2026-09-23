"""Review-only replay of saved evidence and photos; never promotes or publishes."""
import argparse
import copy
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, urlencode
from . import policy


def restore_text(row):
    # Exact saved locations only: no discovery, title resolution or image search.
    from .sources import fetch, plain, wiki_json
    url = row['url']; parts = urlsplit(url)
    page = parse_qs(parts.query).get('curid', [])
    if parts.hostname in {'en.wikipedia.org', 'ar.wikipedia.org'} and len(page) == 1 and page[0].isdigit():
        data = wiki_json('https://' + parts.hostname + '/w/api.php?' + urlencode({
            'action':'query', 'format':'json', 'pageids':page[0], 'prop':'extracts', 'explaintext':1}))
        return str(data['query']['pages'][page[0]]['extract'])[:10000]
    return plain(fetch(url).decode('utf-8', errors='replace'))


def replay(saved, *, agent, render, output, now, restore=restore_text, save=lambda state: None, resume=None):
    if resume is not None:
        if resume.get('source_digest') != policy.digest(saved):
            raise ValueError('resume_source_mismatch')
        if (resume.get('status') != 'held' or not resume.get('package')
                or resume.get('review') or any(r.get('role') == 'reviewer' for r in resume.get('agent_receipts', []))
                or not (resume.get('budget_diagnostic') or 'daily budget:' in resume.get('reason', ''))):
            raise ValueError('resume_requires_unstarted_budget_blocked_review')
    stamp = now()
    expires = datetime.fromisoformat(saved['expires_at'])
    if expires.tzinfo is None or stamp >= expires:
        raise ValueError('saved_package_expired')
    policy.validate_attention(saved['candidate'], stamp)
    sources = []
    for row in saved['sources']:
        body = restore(row)
        expected = row.get('retrieved_text_sha256')
        if not expected or hashlib.sha256(body.encode()).hexdigest() != expected:
            raise ValueError('saved_source_changed')
        sources.append(dict(row, text=body))
    policy.validate_timing(saved['timing'], sources, stamp)
    policy.validate_research(saved['research'], sources, saved['lane'], stamp)
    old = [c for c in saved['package']['cards'] if c['kind'] != 'credits']
    if not 3 <= len(old) <= 4 or any(not c.get('image', {}).get('sha256') for c in old):
        raise ValueError('saved_images_required')
    state = copy.deepcopy(resume) if resume is not None else {
        'mode':'saved_replay', 'automated_readiness':False,
        'source_digest':policy.digest(saved), 'started_at':stamp.isoformat()}
    previous_receipts = copy.deepcopy(state.get('agent_receipts', []))
    state.update(status='working', reason=None)
    state.pop('budget_diagnostic', None)
    save(state)
    try:
        if resume is not None:
            package = copy.deepcopy(state['package'])
            for key in ('candidate', 'research', 'sources', 'lane', 'expires_at'):
                if package.get(key) != saved.get(key):
                    raise ValueError('resume_evidence_changed')
            visible = [{k:v for k,v in c.items() if k in {'kind','title','body','punch','claim_ids','image_query','image_caption'}}
                       for c in package['cards'] if c['kind'] != 'credits']
            policy.validate_draft({'title':package['title'],'cards':visible}, saved['research'])
            state['package'] = package
        else:
            original = [{k:v for k,v in c.items() if k in {'kind','title','body','punch','claim_ids','image_query','image_caption'}} for c in old]
            result = agent.run('writer', {'candidate':saved['candidate'], 'research':saved['research'],
                'original_cards':original,
                'visual_options':[c['image'] for c in old],
                'feedback':f'Simplify this saved draft. Keep exactly {len(old)} cards in the same order, using the SAME photo for each position. Remove nonessential names and model codes, keep the supported progression and endpoint. No new research or facts.'})
            policy.validate_draft(result, saved['research'])
            if len(result['cards']) != len(old):
                raise ValueError('saved_replay_card_count_changed')
            package = dict(copy.deepcopy(result), sources=copy.deepcopy(saved['sources']),
                           research=copy.deepcopy(saved['research']), candidate=copy.deepcopy(saved['candidate']),
                           lane=saved['lane'], expires_at=saved['expires_at'], as_of=stamp.isoformat(),
                           editorial_feedback=saved['package'].get('editorial_feedback', []))
            for card, previous in zip(package['cards'], old):
                card['image'] = copy.deepcopy(previous['image'])
            state.update(package=package, status='drafted'); save(state)
        paths = render(package, Path(output))
        if len(paths) != len(package['cards']):
            raise ValueError('missing_rendered_cards')
        seal = policy.seal(package, paths)
        review = agent.run('reviewer', dict(copy.deepcopy(package), original_sources=sources), images=paths)
        state['review'] = review
        policy.validate_review(review, len(paths))
        policy.verify_seal(package, paths, seal, now())
        state.update(status='replay_review_passed', paths=[str(p) for p in paths], replay_seal=seal)
        return state
    except Exception as error:
        state.update(status='held', reason=str(error)[:2000])
        if hasattr(error, 'diagnostic'):
            state['budget_diagnostic'] = copy.deepcopy(error.diagnostic)
        raise
    finally:
        state['agent_receipts'] = previous_receipts + copy.deepcopy(agent.receipts)
        save(state)


def main():
    from daily_budget import Ledger, GitHubStore, autopilot_daily_limit
    from publishing_v2.bundle_api import GitHubJournal
    from .agents import Agents
    from .runtime import Renderer, engine_id
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-slot', required=True)
    parser.add_argument('--resume-slot', default='')
    parser.add_argument('--output', default='replay-output')
    args=parser.parse_args()
    if os.environ.get('GITHUB_REPOSITORY') != 'khalidonline/daily-news-snap' or os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('configured_main_required')
    if not re.fullmatch(r'autopilot-\d{4}-\d{2}-\d{2}-(daily|local)-shadow-[a-f0-9]{16}', args.source_slot):
        raise ValueError('invalid_source_slot')
    output=Path(args.output); output.mkdir(parents=True, exist_ok=True)
    source=GitHubJournal(args.source_slot).read()
    if args.resume_slot and not re.fullmatch(r'replay-[a-f0-9]{32}', args.resume_slot):
        raise ValueError('invalid_resume_slot')
    journal=GitHubJournal(args.resume_slot or ('replay-' + policy.digest({'source':source, 'engine':engine_id()})[:32]))
    existing=journal.read()
    if existing and not args.resume_slot:
        raise ValueError('replay_already_recorded')
    if args.resume_slot and not existing:
        raise ValueError('resume_not_found')
    now=lambda:datetime.now(timezone.utc)
    token=os.environ.get('DAILY_BUDGET_GITHUB_TOKEN') or os.environ.get('GITHUB_TOKEN')
    ledger=Ledger(GitHubStore(os.environ['GITHUB_REPOSITORY'],token),
                  limit_micro_usd=autopilot_daily_limit(now(), os.environ.get('AUTOPILOT_DAILY_LIMIT_MICRO_USD','3000000')))
    agent=Agents(env=os.environ,ledger=ledger)
    def save(state):
        journal.save(state)
        (output/'result.json').write_text(json.dumps(state,ensure_ascii=False,indent=2))
    # Every card already has a saved image, so Renderer cannot call discovery.
    replay(source,agent=agent,render=Renderer(agent,None),output=output,now=now,save=save,resume=existing if args.resume_slot else None)
    print('Saved replay complete for review only; no readiness or publishing changes.')

if __name__ == '__main__':
    main()
