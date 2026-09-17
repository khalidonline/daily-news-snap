"""Production wiring: established design, shared budget and Bundle receipts."""
import argparse
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image
from daily_budget import GitHubStore, Ledger, day_key
from publishing_v2.bundle_api import BundleClient, GitHubJournal, publish
from publishing_v2.preview import render_card
from publishing_v2.public_images import get_bytes, inspect_image, atomic_write
from .agents import Agents
from .pipeline import Pipeline
from .policy import RIYADH, digest
from .sources import Sources, reusable_image


class Renderer:
    def __init__(self, agent, sources):
        self.agent, self.sources = agent, sources

    def image_options(self, card, package):
        candidate = package.get('candidate', {})
        subject = candidate.get('editorial', {}).get('research_query') or candidate.get('title')
        queries = list(dict.fromkeys([card['image_query']] + ([subject[:130]] if subject else [])))
        rows, seen = [], set()
        for query in queries:
            try:
                for row in self.sources.images(query):
                    if (row.get('width') and row.get('height')
                            and (min(row['width'], row['height']) < 600
                                 or max(row['width'], row['height']) < 1000)):
                        continue
                    if row['asset_id'] not in seen:
                        seen.add(row['asset_id']); rows.append(row)
            except Exception:
                continue
        return rows[:10]

    def image_catalog(self, package):
        catalog = {}
        for card in package['cards']:
            for row in self.image_options(card, package):
                catalog.setdefault(row['asset_id'], row)
        return list(catalog.values())[:35]

    def __call__(self, package, output):
        output = Path(output); output.mkdir(parents=True, exist_ok=True)
        cards = package['cards']
        if not all('image' in c for c in cards):
            catalog = self.image_catalog(package)
            if not catalog:
                raise ValueError('relevant_reusable_image_unavailable')
            # Share the subject's catalog across cards: a date-fruit photo
            # retrieved for one card can correctly illustrate another card.
            choices = [catalog for card in cards]
            options = [{'asset_id': row['asset_id'], 'title': row.get('title', '')[:250],
                        'description': row.get('description', '')[:900],
                        'date_created': row.get('date_created', '')[:100]}
                       for row in catalog]
            selected = self.agent.run('visual', {'cards': cards, 'options': options})
            ids = selected.get('image_ids', [])
            if len(ids) != len(cards):
                raise ValueError('incomplete_visual_selection')
            for card, rows, ident in zip(cards, choices, ids):
                matches = [r for r in rows if r['asset_id'] == ident]
                if len(matches) != 1:
                    raise ValueError('unknown_visual_selection: ' + card['image_query'] + ': '
                                     + str(selected.get('reason', ''))[:800])
                card['image'] = dict(matches[0])
        os.environ['THEME'] = 'light'; os.environ['FONT_FAMILY'] = 'Almarai'
        import story_bot
        names = {'en.wikipedia.org': 'ويكيبيديا', 'ar.wikipedia.org': 'ويكيبيديا',
                 'bbc.co.uk': 'BBC', 'bbc.com': 'BBC', 'alyaum.com': 'اليوم',
                 'aawsat.com': 'الشرق الأوسط'}
        hosts = [urlsplit(row['url']).hostname.removeprefix('www.') for row in package.get('sources', [])]
        source_names = '، '.join(dict.fromkeys(names.get(host, host) for host in hosts))
        paths = []
        for i, card in enumerate(cards):
            image = card['image']
            if not reusable_image(image):
                raise ValueError('image_rights_not_supported')
            try:
                raw = get_bytes(image['download_url'])
                inspect_image(raw)
            except Exception as error:
                raise ValueError('image_download_or_validation_failed: ' + str(image.get('asset_id'))
                                 + ': ' + str(error)[:150]) from None
            sha = hashlib.sha256(raw).hexdigest()
            if image.get('sha256') and sha != image['sha256']:
                raise ValueError('source_image_changed')
            image['sha256'] = sha
            source = output / f'source-{i:02d}.jpg'
            atomic_write(source, raw)
            target = output / f'card-{i:02d}.jpg'
            if card['kind'] == 'info':
                render_card({'title_lines': [card['title']], 'body_lines': [card['body']],
                             'closing_lines': [card['punch']], 'brand': 'ملخص تنفيذي - معلومة'}, source, target)
            else:
                story_bot.render_frame(target.with_suffix('.png'), 'ملخص تنفيذي - قصة',
                    f'{i} من {len(cards)-1}', card['title'], 64, sub=card['body'],
                    photo=source, punch=card['punch'],
                    footer=('المصادر: ' + source_names) if i == len(cards)-1 and source_names else None)
                with Image.open(target.with_suffix('.png')) as image:
                    image.convert('RGB').save(target, 'JPEG', quality=95)
            with Image.open(target) as rendered:
                if rendered.size != (1080, 1920):
                    raise ValueError('wrong_frame_dimensions')
            paths.append(target)
        return paths


def publish_package(package, paths, *, client=None, journal_factory=GitHubJournal):
    client = client or BundleClient()
    client.check()
    media = [(Path(p), Path(p).read_bytes()) for p in paths]
    hashes = [hashlib.sha256(raw).hexdigest() for _, raw in media]
    if len(hashes) != len(set(hashes)):
        raise ValueError('duplicate_rendered_card')
    # Same identity as the existing manual publisher: cross-route deduplication.
    identity = hashlib.sha256(('executivesaudi:' + ':'.join(hashes)).encode()).hexdigest()
    journal = journal_factory(identity)
    expires = datetime.fromisoformat(package['expires_at'])
    class TimedClient:
        def upload(self, item): return client.upload(item)
        def create(self, title, upload):
            if datetime.now(timezone.utc) >= expires:
                raise ValueError('package_expired_before_create')
            return client.create(title, upload)
        def wait(self, post_id): return client.wait(post_id)
    publish(TimedClient(), journal, package['title'], media)
    state = journal.read()
    rows = [state.get(str(i + 1), {}) for i in range(len(paths))]
    if any(row.get('status') != 'POSTED' or not row.get('post_id') for row in rows):
        raise ValueError('incomplete_delivery_receipts')
    return {'status': 'POSTED', 'identity': identity, 'post_ids': [r['post_id'] for r in rows]}


def engine_id():
    root = Path(__file__).resolve().parents[2]
    paths = sorted(Path(__file__).parent.glob('*.py')) + sorted((root / 'publishing_v2').glob('*.py')) + [
             root / 'daily_budget.py', root / 'news_bot.py', root / 'story_bot.py',
             root / 'requirements.txt', root / 'requirements-v2-images.txt']
    return digest({'files': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                   'models': {key: value for key, value in os.environ.items()
                              if key.startswith('AUTOPILOT_') and key.endswith('_MODEL')}})


def shadow_record(result, engine, slot):
    if result.get('engine') != engine or result.get('status') != 'shadow_passed':
        raise ValueError('shadow_engine_not_validated')
    return {'status': 'shadow_passed', 'at': result['started_at'],
            'engine': result['engine'], 'slot': slot, 'approval': result['approval']}


def rollout_ready(state, engine, now):
    try:
        for lane in ('daily', 'local'):
            row = state[lane]
            at = datetime.fromisoformat(row['at'])
            if (row['status'] not in {'shadow_passed', 'published'} or row['engine'] != engine or at.tzinfo is None
                    or not now - timedelta(days=3) <= at <= now):
                return False
        return True
    except (KeyError, TypeError, ValueError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['shadow', 'live'], default='shadow')
    parser.add_argument('--lane', choices=['daily', 'local', 'both'], default='both')
    parser.add_argument('--output', default='autopilot-output')
    args = parser.parse_args()
    if os.environ.get('GITHUB_REPOSITORY') != 'khalidonline/daily-news-snap':
        raise ValueError('configured_repository_required')
    if os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('main_branch_required')
    now = lambda: datetime.now(timezone.utc)
    output = Path(args.output).resolve(); output.mkdir(parents=True, exist_ok=True)
    token = os.environ.get('DAILY_BUDGET_GITHUB_TOKEN') or os.environ.get('GITHUB_TOKEN')
    ledger = Ledger(GitHubStore(os.environ['GITHUB_REPOSITORY'], token),
                    limit_micro_usd=int(os.environ.get('AUTOPILOT_DAILY_LIMIT_MICRO_USD', '3000000')))
    readiness = GitHubJournal('autopilot-readiness')
    engine = engine_id()
    verified = rollout_ready(readiness.read(), engine, now())
    if args.mode == 'live' and not verified:
        print('Live validation unavailable: running shadow to establish readiness')
        args.mode = 'shadow'
        args.lane = 'both'
    results = []
    for lane in (['daily', 'local'] if args.lane == 'both' else [args.lane]):
        agent, sources = Agents(env=os.environ, ledger=ledger), Sources()
        slot = f'autopilot-{day_key(now())}-{lane}-{args.mode}'
        if args.mode == 'shadow':
            slot += '-' + engine[:16]
        store = GitHubJournal(slot)
        pipeline = Pipeline(agent=agent, sources=sources, render=Renderer(agent, sources),
            store=store, publish=publish_package, output=output / lane, now=now, engine=engine)
        result = pipeline.run(lane, args.mode, rollout_verified=verified)
        atomic_write(output / f'{lane}.json', json.dumps(result, ensure_ascii=False).encode())
        if result['status'] == 'shadow_passed':
            state = readiness.read()
            state[lane] = shadow_record(result, engine, slot)
            readiness.save(state)
        elif result['status'] == 'published':
            state = readiness.read()
            state[lane] = {'status': 'published', 'at': result['started_at'],
                           'engine': result['engine'], 'slot': slot, 'approval': result['approval']}
            readiness.save(state)
        results.append({'lane': lane, 'status': result['status'], 'slot': slot,
                        'cost_micro_usd': sum(r['cost_micro_usd'] for r in agent.receipts),
                        'reason': result.get('reason'), 'receipt': result.get('receipt')})
    summary = {'mode': args.mode, 'engine': engine, 'results': results,
               'note': 'Costs here cover this attempt; shared ledger includes retained reservations and other runs.'}
    atomic_write(output / 'summary.json', json.dumps(summary, ensure_ascii=False).encode())
    print(json.dumps(summary, ensure_ascii=False))
    summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary_path:
        with open(summary_path, 'a') as stream:
            stream.write('\n## Agentic autopilot\n\n' + '\n'.join(
                f"- {r['lane']}: **{r['status']}**; this attempt ${r['cost_micro_usd']/1e6:.4f}" for r in results) + '\n')
    return 0 if all(r['status'] in {'shadow_passed', 'published'} for r in results) else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print('Autopilot stopped: ' + type(error).__name__)
        raise SystemExit(1) from None
