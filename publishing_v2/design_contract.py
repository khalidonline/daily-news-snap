"""Final-byte design gate shared by all provider mutations.

Pixel checks are not OCR or semantic review. Those fields require a real,
hash-bound human/agent review; this module never manufactures evidence.
"""
import hashlib
import io
import json
import os
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
        valid=(all(names.count(r)==1 for r in ('headline','closing','cta')) and 1<=names.count('bullet')<=4 and 1<=names.count('caption')<=2)
    if any(r not in roles for r in names) or not valid:fail('text roles missing')
    if not challenge:
        _information_geometry(blocks,settings)
    used=[]
    for block in blocks:
        role=block['role'];box=block.get('box');color=palette[roles[role]]
        if (not isinstance(box,list) or len(box)!=4 or any(type(v) is not int for v in box)
                or not (60<=box[0]<box[2]<=1020 and 260<=box[1]<box[3]<=1730)):
            fail('text outside safe area')
        if any(max(box[0],b[0])<min(box[2],b[2]) and max(box[1],b[1])<min(box[3],b[3]) for b in used):fail('overlapping text boxes')
        used.append(box)
        if block.get('color')!=color:fail('wrong palette token')
        crop=image.crop(box);pixels=crop.load();rgb=tuple(bytes.fromhex(color[1:]));bands=[]
        # Exact-color presence alone is not enough: reject dominant wrong ink.
        bg=tuple(bytes.fromhex(palette['cta_background' if role=='cta' else 'background'][1:]))
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
