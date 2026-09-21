"""Production wiring: established design, shared budget and Bundle receipts."""
import argparse
import copy
import hashlib
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image
from daily_budget import GitHubStore, Ledger, day_key
from publishing_v2.bundle_api import BundleClient, GitHubJournal, publish
from publishing_v2.preview import render_card
from publishing_v2.public_images import get_bytes, inspect_image, atomic_write, download_image
from .agents import Agents
from .pipeline import Pipeline
from .policy import RIYADH, digest, validate_review, story_counter, validate_image_variety
from .sources import Sources, reusable_image, subject_metadata_matches
from .credits import LICENSE_URLS, attribution_eligible, render_credits, render_public_attribution
from .video import compile_story
from publishing_v2.publication import publication_indices, image_publication_eligible, validate_public_attribution


class Renderer:
    def __init__(self, agent, sources):
        self.agent, self.sources = agent, sources
        self._catalog_key, self._catalog, self._selected = None, {}, []

    def plan_visuals(self, candidate):
        subjects = [row['name'] for row in candidate.get('resolved_subjects', [])]
        if not subjects:
            subjects = [candidate.get('resolved_subject', {}).get('name') or candidate['editorial']['research_query']]
        found, hashes, origins = {}, set(), set()
        for subject in subjects:
            subject_search = getattr(self.sources, 'subject_images', None)
            rows = (subject_search(subject, subject) if subject_search else
                    self.image_options({'image_query': subject}, {'candidate': candidate}))
            usable = [row for row in rows if image_publication_eligible(row) and subject_metadata_matches(subject, row)]
            if not usable:
                return []
            for row in usable:
                # Different providers, resized copies and multi-subject searches
                # can expose the same photograph under different asset IDs.
                sha, origin = row.get('sha256'), row.get('origin_key')
                if (row['asset_id'] in found or (sha and sha in hashes)
                        or (origin and origin in origins)):
                    continue
                if sha:
                    hashes.add(sha)
                if origin:
                    origins.add(origin)
                found[row['asset_id']] = {'asset_id': row['asset_id'], 'title': row.get('title', '')[:250],
                    'description': row.get('description', '')[:900],
                    'image_role': row.get('image_role', 'subject illustration; event date requires review')}
        return list(found.values())

    def image_options(self, card, package):
        candidate = package.get('candidate', {})
        subject = (candidate.get('resolved_subject', {}).get('name')
                   or candidate.get('editorial', {}).get('research_query') or candidate.get('title'))
        subjects = [row['name'] for row in candidate.get('resolved_subjects', [])]
        queries = list(dict.fromkeys([card['image_query']] + subjects + ([subject[:130]] if subject else [])))
        recovery = getattr(self.sources, 'recovery', False) is True
        if recovery:
            queries = subjects or ([subject] if subject else [card['image_query']])
        rows, seen = [], set()
        for query in queries:
            try:
                subject_search = getattr(self.sources, 'subject_images', None)
                options = subject_search(query, query) if subject_search and (recovery or query in subjects) else self.sources.images(query)
                for row in options:
                    if not image_publication_eligible(row):
                        continue
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
        key = package.get('candidate', {}).get('id')
        if not key or key != self._catalog_key:
            self._catalog_key, self._catalog, self._selected = key, {}, []
        # Keep selected source metadata available when a rewrite changes queries.
        # Selection is reconsidered; no previous visual approval is carried over.
        catalog = {ident: self._catalog[ident] for ident in self._selected
                   if ident in self._catalog}
        for card in package['cards']:
            if card.get('kind') == 'credits':
                continue
            for row in self.image_options(card, package):
                catalog.setdefault(row['asset_id'], row)
        for ident, row in self._catalog.items():
            catalog.setdefault(ident, row)
        excluded = set(package.get('repair', {}).get('excluded_image_ids', []))
        self._catalog = dict([(ident, row) for ident, row in catalog.items() if ident not in excluded][:35])
        return list(self._catalog.values())

    def __call__(self, package, output):
        with tempfile.TemporaryDirectory(prefix='snap-source-') as temporary:
            return self._render(package, output, Path(temporary))

    def _render(self, package, output, source_root):
        output = Path(output); output.mkdir(parents=True, exist_ok=True)
        cards = [card for card in package['cards'] if card.get('kind') != 'credits']
        if not all('image' in c for c in cards):
            catalog = self.image_catalog(package)
            if not catalog:
                raise ValueError('relevant_reusable_image_unavailable')
            # Share the subject's catalog across cards: a date-fruit photo
            # retrieved for one card can correctly illustrate another card.
            choices = [catalog for card in cards]
            options = [{'asset_id': row['asset_id'], 'title': row.get('title', '')[:250],
                        'description': row.get('description', '')[:900],
                        'date_created': row.get('date_created', '')[:100],
                        'image_role': row.get('image_role', 'subject illustration; event date requires review')}
                       for row in catalog]
            selected = self.agent.run('visual', {'cards': cards, 'options': options,
                                               'repair': package.get('repair', {})})
            ids = selected.get('image_ids', [])
            if len(ids) != len(cards):
                raise ValueError('incomplete_visual_selection')
            self._selected = list(dict.fromkeys(ident for ident in ids
                if isinstance(ident, str) and ident in self._catalog))
            for card, rows, ident in zip(cards, choices, ids):
                matches = [r for r in rows if r['asset_id'] == ident]
                if len(matches) != 1:
                    raise ValueError('unknown_visual_selection: ' + card['image_query'] + ': '
                                     + str(selected.get('reason', ''))[:800])
                card['image'] = dict(matches[0])
        validate_image_variety(cards)
        needs_credits = True  # Every review includes sources; public selection excludes this card.
        existing_credits = [card for card in package['cards'] if card.get('kind') == 'credits']
        if existing_credits and (not needs_credits or len(existing_credits) != 1):
            raise ValueError('invalid_credits_card')
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
                raw = download_image(image, fetch=get_bytes)
            except Exception as error:
                raise ValueError('image_download_or_validation_failed: ' + str(image.get('asset_id'))
                                 + ': ' + str(error)[:150]) from None
            sha = hashlib.sha256(raw).hexdigest()
            if image.get('sha256') and sha != image['sha256']:
                raise ValueError('source_image_changed')
            image['sha256'] = sha
            validate_image_variety(cards)
            source = source_root / f'source-{i:02d}.jpg'
            atomic_write(source, raw)
            target = output / f'card-{i:02d}.jpg'
            if card['kind'] == 'info':
                render_card({'title_lines': [card['title']], 'body_lines': [card['body']],
                             'closing_lines': [card['punch']], 'brand': 'ملخص تنفيذي - معلومة'}, source, target)
            else:
                story_bot.render_frame(target.with_suffix('.png'), 'ملخص تنفيذي - قصة',
                    story_counter(i, len(cards)-1), card['title'], 64, sub=card['body'],
                    photo=source, punch=card['punch'],
                    footer=('المصادر: ' + source_names) if i == len(cards)-1 and source_names and not needs_credits else None)
                with Image.open(target.with_suffix('.png')) as image:
                    image.convert('RGB').save(target, 'JPEG', quality=95)
            if card['image'].get('license') in LICENSE_URLS:
                render_public_attribution(card, target)
            else:
                card.pop('public_attribution', None)
            with Image.open(target) as rendered:
                if rendered.size != (1080, 1920):
                    raise ValueError('wrong_frame_dimensions')
            paths.append(target)
        if needs_credits:
            credit_card = {'kind': 'credits', 'title': 'المصادر والصور',
                           'body': 'Editorial sources and photo attribution',
                           'image': dict(cards[0]['image'])}
            if existing_credits:
                if existing_credits[0] != credit_card:
                    raise ValueError('credits_card_changed')
            else:
                package['cards'].append(credit_card)
            target = output / f'card-{len(cards):02d}.jpg'
            render_credits(package, source_root / 'source-00.jpg', target)
            paths.append(target)
            if package.get('delivery'):
                raise ValueError('review_video_requires_fresh_review')
        return paths


def publish_package(package, paths, *, client=None, journal_factory=GitHubJournal):
    validate_image_variety(package.get('cards', []))
    cards = package.get('cards', [])
    indices = publication_indices(cards)
    if len(cards) != len(paths):
        raise ValueError('review_media_count_mismatch')
    if package.get('delivery') and len(indices) != len(cards):
        raise ValueError('review_video_not_publishable')
    media = [(Path(paths[i]), Path(paths[i]).read_bytes()) for i in indices]
    for index, (_, raw) in zip(indices, media):
        validate_public_attribution(cards[index], raw)
    frame_hashes = [hashlib.sha256(raw).hexdigest() for _, raw in media]
    if len(frame_hashes) != len(set(frame_hashes)):
        raise ValueError('duplicate_rendered_card')
    delivery = package.get('delivery')
    if delivery:
        if (delivery.get('kind') != 'video' or delivery.get('filename') != 'story.mp4'
                or delivery.get('frame_sha256') != frame_hashes
                or not 5 <= delivery.get('duration_seconds', 0) <= 60):
            raise ValueError('invalid_video_delivery')
        video = Path(paths[0]).parent / 'story.mp4'
        raw = video.read_bytes()
        if not 0 < len(raw) <= 100_000_000 or hashlib.sha256(raw).hexdigest() != delivery['sha256']:
            raise ValueError('approved_video_changed')
        media = [(video, raw)]
    # Bind the complete review identity, matching the manual publisher. A
    # previously sent package must not resend when its final credits are omitted.
    hashes = ([hashlib.sha256(raw).hexdigest() for _, raw in media] if delivery else
              [hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths])
    client = client or BundleClient()
    client.check()
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
    rows = [state.get(str(i + 1), {}) for i in range(len(media))]
    if any(row.get('status') != 'POSTED' or not row.get('post_id') for row in rows):
        raise ValueError('incomplete_delivery_receipts')
    return {'status': 'POSTED', 'identity': identity, 'post_ids': [r['post_id'] for r in rows],
            'card_count': len(indices), 'review_card_count': len(paths), 'media_count': len(media)}


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


def promotable_shadow(state, engine, lane, now, source_slot):
    """Reuse today's exact approved package; never regenerate during promotion."""
    try:
        if (state.get('status') != 'shadow_passed' or state.get('mode') != 'shadow'
                or state.get('engine') != engine or state.get('lane') != lane
                or day_key(datetime.fromisoformat(state['started_at'])) != day_key(now)
                or datetime.fromisoformat(state['package']['expires_at']) <= now
                or digest(state['package']) != state['approval']['package_sha256']
                or len(state['approval']['media_sha256']) != len(state['package']['cards'])):
            return None
        validate_review(state['review'], len(state['package']['cards']))
    except (KeyError, TypeError, ValueError):
        return None
    result = copy.deepcopy(state)
    result.update(mode='live', status='approved', source_shadow_slot=source_slot)
    result['audit'].append({'event':'promoted_shadow', 'at':now.isoformat(), 'source_slot':source_slot})
    return result


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
        agent, sources = Agents(env=os.environ, ledger=ledger), Sources(recovery=True, publication_only=True)
        slot = f'autopilot-{day_key(now())}-{lane}-{args.mode}'
        if args.mode == 'shadow':
            slot += '-' + engine[:16]
        store = GitHubJournal(slot)
        if args.mode == 'live' and verified and not store.read():
            record = readiness.read().get(lane, {})
            if record.get('status') == 'shadow_passed' and record.get('slot'):
                shadow = GitHubJournal(record['slot']).read()
                promoted = promotable_shadow(shadow, engine, lane, now(), record['slot'])
                if promoted:
                    store.save(promoted)
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
                        'reason': result.get('reason'), 'budget_diagnostic': result.get('budget_diagnostic'),
                        'receipt': result.get('receipt')})
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
