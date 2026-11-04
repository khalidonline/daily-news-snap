"""Offline, explicit import of cached Tawari copy into the fixed information route.

Not installed in the autopilot scheduler. No downloads, model calls, previews,
owner approvals, publish requests, or provider calls. Existing package names are
never overwritten. Actual review and the normal uploaded-preview gate follow.
"""
import argparse
import copy
from datetime import datetime
import io
import json
import re
from pathlib import Path
import tempfile

from PIL import Image

from publishing_v2.editorial_production import require_text_approval
from publishing_v2.fixed_information_template import render
from publishing_v2.information_text_fit import ROOT, prepare_text
from publishing_v2.prepared_information import digest, package_path, safe_path
from publishing_v2.publication import image_without_public_credit


def stage(package, source_dir, name):
    """Preserve approved input wording and selected cached image bytes exactly."""
    if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,80}', name):
        raise ValueError('Package name must be a plain lowercase slug')
    target = package_path(Path('approved') / name)
    if target.exists():
        raise FileExistsError('Package exists; retain its identity and review bytes')
    package = copy.deepcopy(package)
    if package.get('delivery') or package.get('content_type') == 'challenge':
        raise ValueError('Information stills only; challenge/video routes unchanged')
    cards = package.get('cards', [])
    if not cards or any(c.get('kind') not in {'info', 'story', 'credits'} for c in cards):
        raise ValueError('Explicit information/story kinds required')
    credits = [i for i,c in enumerate(cards) if c['kind'] == 'credits']
    if credits and credits != [len(cards)-1]:
        raise ValueError('Review credits must be last')
    cards = [c for c in cards if c['kind'] != 'credits']
    if not 1 <= len(cards) <= 2:
        raise ValueError('One or two cards required; never silently split or drop copy')
    fixed_schema = package.get('information_schema_version') == 1
    if fixed_schema:
        from . import fixed_information
        fixed_information.require_text_approval(package)
    else:
        require_text_approval(package)
    expires = package.get('expires_at', '')
    not_before = package.get('as_of', '')
    start, end = [datetime.fromisoformat(v.replace('Z', '+00:00')) for v in (not_before, expires)]
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise ValueError('Valid timezone-aware authorization window required')
    if not isinstance(package.get('title'), str) or not package['title'].strip():
        raise ValueError('Package title required')
    settings_raw = (ROOT/'publishing_v2/design-settings.json').read_bytes()
    if safe_path('publishing_v2/design-settings.json').read_bytes() != settings_raw:
        raise ValueError('Working directory master differs from renderer master')
    settings = json.loads(settings_raw)
    fits, images, rendered, blocks = [], [], [], []
    for i, card in enumerate(cards):
        # The legacy body is a single exact paragraph. Do not reinterpret,
        # truncate, westernize digits or shorten already-reviewed copy to fit.
        draft = (fixed_information.card_draft(card) if fixed_schema else
                 {'headline':card['title'], 'bullets':[card['body']], 'closing':card['punch']})
        fit = prepare_text(draft)
        if not fit['fit']:
            raise ValueError('Text fit failed for card %d: %s' % (i, '; '.join(fit['violations'])))
        fit['display_text'] += '\n\n' + settings['editorial_master']['cta_exact']
        fits.append(fit)
        image = card.get('image', {})
        # Do not reuse a legacy attribution receipt bound to different pixels,
        # or draw its old footer over the current fixed template.
        if not image_without_public_credit(image):
            raise ValueError('Attribution requires explicit fixed-template review; import stopped')
        source = safe_path(Path(source_dir)/f'source-{i:02d}.jpg')
        raw = source.read_bytes()
        if digest(raw) != image.get('sha256'):
            raise ValueError('Selected cached source changed')
        caption = card.get('image_caption')
        if not isinstance(caption, str) or not caption.strip():
            raise ValueError('Exact image caption required')
        with Image.open(io.BytesIO(raw)) as photo:
            photo.load()
            output, geometry = render(draft['headline'], draft['bullets'], draft['closing'],
                                      [photo.convert('RGB')], [caption])
        buffer = io.BytesIO(); output.save(buffer, 'PNG')
        images.append(raw); rendered.append(buffer.getvalue()); blocks.append(geometry)
    base = target.relative_to(Path.cwd().resolve()).as_posix()
    media, assets = [], []
    for i, (card, raw, result) in enumerate(zip(cards, images, rendered)):
        asset = {**card['image'], 'path':f'{base}/source-{i:02d}.jpg', 'sha256':digest(raw)}
        assets.append(asset)
        media.append({'kind':'info', 'path':f'{base}/card-{i:02d}.png',
                      'sha256':digest(result), 'source_assets':[asset],
                      'provenance':{'usage':'mixed_editorial_composite',
                                    'generated_components':bool(card['image'].get('generated',False))}})
    manifest = {'format':'owner-reviewed-composite-v1', 'approved':False,
                'account':'executivesaudi', 'content_type':'information',
                'approved_destinations':['STORY','SAVED_STORY'], 'story_duration':'ONE_WEEK',
                'title':package['title'], 'not_before':not_before, 'expires_at':expires, 'media':media,
                'owner_review':{'approved_media_sha256':[m['sha256'] for m in media],
                                'approved_source_sha256':[a['sha256'] for a in assets]}}
    encoded = lambda value: json.dumps(value,ensure_ascii=False,indent=2)+'\n'
    manifest_raw = encoded(manifest)
    identity = digest(('executivesaudi:'+':'.join(m['sha256'] for m in media)).encode())
    archive = {'approved':False, 'account':'executivesaudi', 'manifest':base+'/manifest.json',
               'manifest_sha256':digest(manifest_raw.encode()), 'identity':identity,
               'public_indices':list(range(1,len(media)+1)), 'title':package['title'],
               'expires_at':expires, 'empty_profile_confirmation':''}
    review = {'version':1, 'content_type':'information',
              'settings_revision':settings['canonical_reference']['revision'],
              'settings_sha256':digest(settings_raw), 'status':'PENDING_ACTUAL_REVIEW',
              'destinations':['STORY','SAVED_STORY'], 'review':{},
              'cards':[{'sha256':m['sha256'],'blocks':b} for m,b in zip(media,blocks)]}
    target.parent.mkdir(parents=True, exist_ok=True)
    # Assemble privately and rename only once; no partially successful package
    # is mistaken for a reviewed export after fit/render/write failure.
    with tempfile.TemporaryDirectory(prefix='.tawari-', dir=target.parent) as temporary:
        staged = Path(temporary)/target.name; staged.mkdir()
        for i, (raw, result) in enumerate(zip(images,rendered)):
            (staged/f'source-{i:02d}.jpg').write_bytes(raw)
            (staged/f'card-{i:02d}.png').write_bytes(result)
        for filename, data in {
            'manifest.json':manifest, 'archive-approval.json':archive,
            'design-review.json':review, 'text-fit.json':fits,
            'sources.json':{'facts':package.get('sources',[]), 'image_assets':assets},
            'autopilot-input.json':package,
        }.items():
            (staged/filename).write_text(encoded(data),encoding='utf-8')
        if target.exists():
            raise FileExistsError('Package appeared during staging; no overwrite')
        staged.rename(target)
    return {'status':'DRAFT_REQUIRES_REVIEW', 'package':base, 'identity':identity,
            'preview_allowed':False, 'publish_authorized':False,
            'next_step':'Actual mobile/palette/overlay review and profile baseline, then prepare-local-preview'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-json',required=True)
    parser.add_argument('--sources-dir',required=True)
    parser.add_argument('--name',required=True)
    args = parser.parse_args()
    result = stage(json.loads(safe_path(args.package_json).read_text()),args.sources_dir,args.name)
    print(json.dumps(result,ensure_ascii=False))


if __name__ == '__main__':
    main()
