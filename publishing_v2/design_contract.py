"""Final-byte design gate shared by all provider mutations.

Pixel checks are not OCR or semantic review. Those fields require a real,
hash-bound human/agent review; this module never manufactures evidence.
"""
import hashlib
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image

SETTINGS = Path(__file__).with_name('design-settings.json')


def fail(reason):
    from .bundle_api import BundleError
    raise BundleError('Design: ' + reason)


def validate_design(media, report, placement):
    settings_raw=SETTINGS.read_bytes(); settings=json.loads(settings_raw)
    if (not isinstance(report,dict) or report.get('version')!=1
            or report.get('settings_revision')!=settings['canonical_reference']['revision']
            or report.get('settings_sha256')!=hashlib.sha256(settings_raw).hexdigest()
            or placement not in report.get('destinations',[])
            or placement not in {'STORY','SPOTLIGHT','SAVED_STORY'}):
        fail('missing/current settings and destination review required')
    if report.get('archive_exception') is not None:
        return _six_legacy_archives(media, report, placement)
    review=report.get('review',{})
    checks=('saudi_editorial','approved_wording','photos_and_captions','cta_visible','overlay_checked')
    if (not isinstance(review,dict) or not review.get('reference') or review.get('mobile_width')!=390
            or any(review.get(k) is not True for k in checks)):
        fail('final mobile/editorial review required')
    # Owner may approve Bold for one role; require a truthful typography review,
    # not a false assertion that all final text uses Regular.
    if review.get('approved_typography') is not True and review.get('regular_font') is not True:
        fail('approved typography review required')
    overlays=review.get('overlay_destinations',{})
    if not isinstance(overlays,dict) or not isinstance(overlays.get(placement),str) or not overlays[placement].strip():
        fail('separate destination overlay review required')
    cards=report.get('cards')
    if not isinstance(cards,list) or len(cards)!=len(media) or not 1<=len(media)<=2:
        fail('one or two reviewed media required')
    content_type=report.get('content_type')
    if content_type not in {'information','challenge'}:fail('explicit content type required')
    for card,(path,raw) in zip(cards,media):
        if not isinstance(card,dict) or card.get('sha256')!=hashlib.sha256(raw).hexdigest():fail('final bytes changed')
        if Path(path).suffix.lower()=='.mp4':
            if content_type!='challenge':fail('video requires challenge review')
            from .challenge_contract import validate_challenge
            from .reviewed_video import validate_reviewed_video
            data=getattr(media,'snapshot',{})
            validate_challenge(data.get('title',''),media)
            _,_,verified=validate_reviewed_video(data,Path.cwd().resolve())
            if [hashlib.sha256(r).hexdigest() for _,r in verified]!=[card['sha256']]:fail('video evidence mismatch')
            _video_design(card,data,settings)
            continue
        if content_type!='information' or placement=='SPOTLIGHT':fail('challenge must be final video')
        try:
            image=Image.open(io.BytesIO(raw)).convert('RGB');image.load()
        except (OSError,ValueError):fail('invalid image')
        if image.size!=(1080,1920):fail('dimensions must be 1080x1920')
        _flat_palette(image,card.get('palette_samples'),settings)
        _pixels(image,card.get('blocks'),settings)
    return {'status':'validated','sha256':[hashlib.sha256(raw).hexdigest() for _,raw in media]}


def _six_legacy_archives(media, report, placement):
    """Khalid's explicit 30-Oct approval: archive these six unchanged originals.

    This is NOT a design pass. The normal publisher still checks revocable
    approval, source POSTED receipts/provider uploads, quota and idempotency.
    No new uploads, Story/Spotlight sends, other files or later use authorized.
    """
    from .bundle_api import ApprovedMedia
    allowed = {
        '5a65b46f79b77ac672fecab6ef18e8ddd715ed823accbcfe77a22713be51cb21': 'approved/rice-20261026/Rice-Final.png',
        '7184b392653d46162372e9db05e444a65e2a76c4c65b66962e5d99fa2f9eeced': 'approved/oxford-20261027/card.png',
        'bed4072e9bc8dc373f018869af8e6598863f6e4e3d5521dcf73e6a4fe10d1e62': 'approved/global-entry-20261028/card.png',
        'e121b2af27b343e6d1eaf6d08c7009c8ff9508c9302bd33f1d2d0ba0638a01d2': 'approved/youtube-shopping-20261028/card.png',
        'd791c1d50c73bdbd3fd73e309f4729afa9f62508197584d19d0a43309ce3b170': 'approved/shubaily-20261029/card.png',
        '422748afae9bbf1e578102b24697748598b7ce1bd33dba6bfcc0c939425667ba': 'approved/twins-20261029/card.png',
    }
    tag='khalid-six-archives-20261030'
    data=getattr(media,'snapshot',{})
    if (not isinstance(media,ApprovedMedia) or len(media)!=1
            or placement!='SAVED_STORY' or report.get('archive_exception')!=tag
            or report.get('waived_checks')!=['current_template_design_review']
            or data.get('archive_exception')!=tag or data.get('approved') is not True
            or data.get('account')!='executivesaudi' or data.get('content_type')!='information'
            or data.get('approved_destinations')!=['SAVED_STORY']):
        fail('archive exception outside owner-approved scope')
    try:
        expiry=datetime.fromisoformat(data['expires_at'].replace('Z','+00:00'))
        deadline=datetime.fromisoformat('2026-10-31T00:00:00+00:00')
        if expiry.tzinfo is None or not datetime.now(timezone.utc)<expiry<=deadline:
            fail('archive exception expired or extended')
    except (KeyError,ValueError,TypeError):
        fail('archive exception expiry invalid')
    path,raw=media[0];digest=hashlib.sha256(raw).hexdigest()
    if digest not in allowed or Path(path).resolve()!=(Path.cwd()/allowed[digest]).resolve():
        fail('archive exception does not cover these bytes')
    frames=data.get('media',[])
    if (len(frames)!=1 or frames[0].get('sha256')!=digest
            or frames[0].get('kind') not in {'info','story','topic'}):
        fail('archive exception media declaration mismatch')
    return {'status':'owner_authorized_archive_exception','sha256':[digest],
            'waived_checks':['current_template_design_review']}


def _flat_palette(image,samples,settings,tolerance=0):
    if not isinstance(samples,dict):fail('flat palette samples required')
    for role in ('background','green','cta_background'):
        box=samples.get(role)
        if (not isinstance(box,list) or len(box)!=4 or any(type(v) is not int for v in box)
                or not (0<=box[0]<box[2]<=1080 and 0<=box[1]<box[3]<=1920)
                or (box[2]-box[0])*(box[3]-box[1])<100):fail('invalid palette sample')
        if role=='green' and not 110<=box[1]<box[3]<=230:fail('green palette sample must be header')
        if role=='cta_background' and not 1600<=box[1]<box[3]<=1730:fail('CTA palette sample outside safe area')
        crop=image.crop(box);rgb=tuple(bytes.fromhex(settings['palette']['exact_numeric_tokens'][role][1:]))
        count=sum(max(abs(pixel[c]-rgb[c]) for c in range(3))<=tolerance for pixel in crop.get_flattened_data())
        if count < crop.width*crop.height*.95:fail('flat palette mismatch: '+role)


def _pixels(image, blocks, settings, challenge=False, tolerance=0):
    palette=settings['palette']['exact_numeric_tokens']
    roles={'headline':'red','bullet':'body','caption':'caption','closing':'red','cta':'red'}
    if challenge:roles.update(question='green',option='body',answer='body',countdown='body')
    if not isinstance(blocks,list) or any(not isinstance(b,dict) for b in blocks):fail('text boxes required')
    names=[b.get('role') for b in blocks]
    if challenge:
        valid=(all(names.count(r)==1 for r in ('headline','question','cta')) and 2<=names.count('option')<=4)
    else:
        valid=(all(names.count(r)==1 for r in ('headline','closing','cta')) and 1<=names.count('bullet')<=4 and 1<=names.count('caption')<=3)
    if any(r not in roles for r in names) or not valid:fail('text roles missing')
    if not challenge:
        _information_geometry(blocks,settings)
    used=[]
    for block in blocks:
        role=block['role'];box=block.get('box');color=palette[roles[role]]
        v2 = challenge and bool(settings.get('challenges',{}).get('approved_template_v2'))
        filled = block.get('filled_correct_option') is True
        if filled:
            if not v2 or role != 'option':fail('filled option outside approved challenge template')
            color=palette['background']
        if v2 and role=='answer' and block.get('answer_reveal') is True:
            color=palette['green']
        if (not isinstance(box,list) or len(box)!=4 or any(type(v) is not int for v in box)
                or not (60<=box[0]<box[2]<=1020 and (215 if not challenge and settings['information_template'].get('approved_layout_override') else 260)<=box[1]<box[3]<=1730)):
            fail('text outside safe area')
        if any(max(box[0],b[0])<min(box[2],b[2]) and max(box[1],b[1])<min(box[3],b[3]) for b in used):fail('overlapping text boxes')
        used.append(box)
        if block.get('color')!=color:fail('wrong palette token')
        crop=image.crop(box);pixels=crop.load();rgb=tuple(bytes.fromhex(color[1:]));bands=[]
        # Exact-color presence alone is not enough: reject dominant wrong ink.
        bghex=palette['green'] if filled else ('#DBEFE6' if challenge and role=='option' else palette['cta_background' if role=='cta' else 'background'])
        bg=tuple(bytes.fromhex(bghex[1:]))
        vector=[bg[i]-rgb[i] for i in range(3)];denominator=sum(v*v for v in vector)
        core=bad=0
        for pixel in crop.get_flattened_data():
            alpha=sum((bg[i]-pixel[i])*vector[i] for i in range(3))/denominator
            if alpha>=.5:
                core+=1
                if max(abs(pixel[i]-(bg[i]-alpha*vector[i])) for i in range(3))>max(8,tolerance):bad+=1
        if not core or bad/core>.05:fail('dominant ink differs from palette')
        for y in range(crop.height):
            if sum(max(abs(pixels[x,y][c]-rgb[c]) for c in range(3))<=tolerance for x in range(crop.width))>=4:
                if not bands or y-bands[-1][-1]>8:bands.append([y])
                else:bands[-1].append(y)
        maximum=2 if role in {'bullet','closing','question','answer'} else 1
        line_boxes=block.get('line_boxes')
        if line_boxes is not None:
            # Native renderer glyph bounds avoid treating Arabic dots/descenders
            # as separate lines. This is geometry evidence, not semantic OCR.
            size=block.get('font_size')
            if not isinstance(size,int) or size<24 or not isinstance(line_boxes,list) or not 1<=len(line_boxes)<=maximum or len(line_boxes)!=block.get('line_count'):
                fail('invalid native line geometry')
            last_bottom=box[1]
            for line in line_boxes:
                if (not isinstance(line,list) or len(line)!=4 or any(type(v) is not int for v in line)
                        or not box[0]<=line[0]<line[2]<=box[2]
                        or not last_bottom<=line[1]<line[3]<=box[3]
                        or not 16<=line[3]-line[1]<=size*1.6):fail('native line outside bounds')
                last_bottom=line[3]
                ink=image.crop(line)
                if sum(max(abs(p[c]-rgb[c]) for c in range(3))<=tolerance for p in ink.get_flattened_data())<20:fail('native line missing ink')
            continue
        if not 1<=len(bands)<=maximum or block.get('line_count')!=len(bands):fail('ink/line count mismatch')
        if any(b[-1]-b[0]+1<(16 if role=='caption' else 24) for b in bands):fail('ink too small')


def _information_geometry(blocks, settings):
    """Shared information-only region/gap gate; never changes challenge layout."""
    grid=settings['layout']['numeric_grid_px']
    balanced=settings['information_template'].get('approved_layout_override')
    if balanced:
        grid={**grid,**balanced['regions_xyxy']}
    regions={'headline':'title','caption':'captions','bullet':'body','closing':'closing','cta':'cta'}
    for block in blocks:
        box=block.get('box'); region=grid[regions[block['role']]]
        if (not isinstance(box,list) or len(box)!=4 or any(type(v) is not int for v in box)
                or not region[0]<=box[0]<box[2]<=region[2]
                or not region[1]<=box[1]<box[3]<=region[3]):
            fail('information text outside role region: '+block['role'])
        if block['role'] in {'headline','closing'} and block.get('line_count')!=1:
            fail('information title and closing require one line')
    ordered=sorted(blocks,key=lambda b:b['box'][1])
    if balanced:
        bullets=[b for b in ordered if b['role']=='bullet']
        if not 1<=len(bullets)<=4:fail('information bullet count')
        for b in bullets:
            lines=b.get('line_boxes',[])
            if not 1<=len(lines)<=2:fail('balanced information needs ink bounds')
            if b.get('font_size')!=44 or b.get('font_weight')!='Bold':fail('balanced information font changed')
            if b['box'][1]!=lines[0][1] or b['box'][3]!=lines[-1][3]:fail('paragraph bounds differ from ink')
            if any(z[1]-a[3]!=balanced['line_spacing']['visible_gap_px'] for a,z in zip(lines,lines[1:])):fail('unequal visible line gaps')
        edges=balanced['paragraph_distribution']
        gaps=[bullets[0]['box'][1]-edges['top_boundary']]+[b['box'][1]-a['box'][3] for a,b in zip(bullets,bullets[1:])]+[edges['bottom_boundary']-bullets[-1]['box'][3]]
        if min(gaps)<grid['minimum_block_gap'] or max(gaps)-min(gaps)>1:fail('unequal paragraph distribution')
    for a,b in zip(ordered,ordered[1:]):
        if a['role']==b['role']=='caption':continue  # side-by-side labels
        if b['box'][1]-a['box'][3]<grid['minimum_block_gap']:
            fail('information actual block gap below minimum')


def _video_design(card,data,settings):
    frames=data.get('video_review',{}).get('frames',[])
    designs=card.get('frame_designs')
    if not frames or not isinstance(designs,list) or len(designs)!=len(frames):fail('all decoded frame designs required')
    for frame,design in zip(frames,designs):
        if design.get('at')!=frame['at'] or design.get('sha256')!=frame['sha256']:fail('decoded design evidence mismatch')
        filled=[b for b in design.get('blocks',[]) if b.get('filled_correct_option') is True]
        reveals=[b for b in design.get('blocks',[]) if b.get('answer_reveal') is True]
        if (filled or reveals) and (frame['at']<8 or len(filled)!=1 or len(reveals)!=1):
            fail('filled answer must occur only at approved reveal time')
        image=Image.open(Path(frame['path'])).convert('RGB')
        # reviewed_video already binds these decoded bytes to the final MP4.
        _pixels(image,design.get('blocks'),settings,challenge=True,tolerance=12)
        _flat_palette(image,design.get('palette_samples'),settings,tolerance=12)


class DeliveryReview:
    """Re-read immutable report and revocable approval on each mutation."""
    def __init__(self, media, placement):
        from .bundle_api import ApprovedMedia
        if not isinstance(media,ApprovedMedia):fail('approved manifest wrapper required')
        self.media=media;self.placement=placement
        self.path=media.path.parent/'design-review.json'
        try:self.raw=self.path.read_bytes()
        except OSError:fail('design-review.json required before upload')
        self.check()

    def check(self, placement=None):
        placement=placement or self.placement
        self.media.check_approval()
        from .challenge_contract import validate_challenge
        validate_challenge(self.media.snapshot.get('title',''),self.media)
        if os.environ.get('GITHUB_ACTIONS')=='true':
            from .bundle_api import request
            import base64
            token=os.environ.get('GITHUB_TOKEN','')
            if not token:fail('live settings unavailable')
            remote=request('https://api.github.com/repos/khalidonline/daily-news-snap/contents/publishing_v2/design-settings.json?ref=main',
                           {'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Cache-Control':'no-cache'})
            if remote.get('encoding')!='base64' or base64.b64decode(remote['content'])!=SETTINGS.read_bytes():
                fail('checkout settings are stale versus live master')
        try:
            if self.path.read_bytes()!=self.raw:fail('review changed after validation')
            report=json.loads(self.raw)
            if placement not in self.media.snapshot.get('approved_destinations',[]):fail('destination not approved')
            if report.get('content_type')!=self.media.snapshot.get('content_type'):fail('content type mismatch')
            return validate_design(self.media,report,placement)
        except (OSError,ValueError,KeyError,TypeError):fail('invalid final design report')


def review_for_item(item):
    from .bundle_api import load_package, BundleError
    path,raw=item;path=Path(path).resolve()
    try:
        _,_,media=load_package(str(path.parent/'manifest.json'))
        if not any(p==path and data==raw for p,data in media):fail('upload differs from approved bytes')
        placements=media.snapshot.get('approved_destinations',[])
        placement='STORY' if 'STORY' in placements else 'SPOTLIGHT'
        return DeliveryReview(media,placement)
    except (OSError,ValueError,KeyError,TypeError,BundleError) as exc:
        fail('approved package and final report required: '+str(exc))
