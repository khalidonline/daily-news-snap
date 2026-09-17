"""Production wiring: established design, shared budget and Bundle receipts."""
import argparse
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

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

    def __call__(self, package, output):
        output = Path(output); output.mkdir(parents=True, exist_ok=True)
        cards = package['cards']
        if not all('image' in c for c in cards):
            choices = []
            for card in cards:
                try:
                    rows = self.sources.images(card['image_query'])
                except Exception:
                    rows = []
                choices.append(rows)
            if any(not row for row in choices):
                raise ValueError('relevant_reusable_image_unavailable')
            selected = self.agent.run('visual', {'cards': cards, 'options': choices})
            ids = selected.get('image_ids', [])
            if len(ids) != len(cards):
                raise ValueError('incomplete_visual_selection')
            for card, rows, ident in zip(cards, choices, ids):
                matches = [r for r in rows if r['asset_id'] == ident]
                if len(matches) != 1:
                    raise ValueError('unknown_visual_selection')
                card['image'] = dict(matches[0])
        os.environ['THEME'] = 'light'; os.environ['FONT_FAMILY'] = 'Almarai'
        import story_bot
        paths = []
        for i, card in enumerate(cards):
            image = card['image']
            if not reusable_image(image):
                raise ValueError('image_rights_not_supported')
            try:
                raw = get_bytes(image['download_url'])
                inspect_image(raw)
            except Exception:
                raise ValueError('image_download_or_validation_failed') from None
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
                    photo=source, punch=card['punch'])
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
    ledger = Ledger(GitHubStore(os.environ['GITHUB_REPOSITORY'], token))
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
