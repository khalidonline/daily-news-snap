"""Measure sealed raster text bands without pretending to know generated fonts.

This supplements mandatory mobile visual review. It is not OCR or factual review.
Only manually owner-approved composites may use this profile.
"""
import hashlib
import io
import json
from pathlib import Path
from PIL import Image


def validate_raster(report_path, report, media):
    from .readability import fail
    try:
        manifest=json.loads((Path(report_path).parent/'manifest.json').read_text())
    except (OSError,ValueError):
        fail('raster manifest unavailable')
    hashes=[hashlib.sha256(raw).hexdigest() for _,raw in media]
    if (manifest.get('format')!='owner-reviewed-composite-v1' or manifest.get('approved') is not True
        or manifest.get('owner_review',{}).get('approved_media_sha256')!=hashes):
        fail('raster owner approval mismatch')
    review=report['visual_review']
    if review.get('mobile_width')!=390 or review.get('captions_match_images') is not True:
        fail('raster mobile/caption review required')
    expected={'headline':'#B60E32','bullet':'#0B3656','caption':'#7A7973',
              'closing':'#B60E32','cta':'#B60E32'}
    all_counts=[]
    for card,(_,raw),sha in zip(report['cards'],media,hashes):
        if card.get('sha256')!=sha: fail('raster bytes changed')
        im=Image.open(io.BytesIO(raw)).convert('RGB')
        if im.size!=(1080,1920): fail('raster requires 1080x1920')
        blocks=card.get('blocks')
        if not isinstance(blocks,list): fail('raster blocks required')
        roles=[b.get('role') for b in blocks if isinstance(b,dict)]
        if (len(roles)!=len(blocks) or any(r not in expected for r in roles)
            or any(roles.count(r)!=1 for r in ('headline','closing','cta'))
            or not 1<=roles.count('bullet')<=4 or not 1<=roles.count('caption')<=2):
            fail('raster block roles invalid')
        used=[]; counts=[]
        for block in blocks:
            role=block['role'];box=block.get('box')
            if (not isinstance(box,list) or len(box)!=4 or any(type(v) is not int for v in box)
                or not (40<=box[0]<box[2]<=1040 and 240<=box[1]<box[3]<=1820)):
                fail('raster block outside safe area')
            for old in used:
                if max(box[0],old[0])<min(box[2],old[2]) and max(box[1],old[1])<min(box[3],old[3]):
                    fail('raster blocks overlap')
            used.append(box)
            if block.get('color')!=expected[role]: fail('raster palette role changed')
            color=tuple(bytes.fromhex(expected[role][1:]))
            crop=im.crop(box); pixels=crop.load(); active=[]
            for y in range(crop.height):
                if sum(pixels[x,y]==color for x in range(crop.width))>=4: active.append(y)
            bands=[]
            for y in active:
                if not bands or y-bands[-1][-1]>8: bands.append([y])
                else: bands[-1].append(y)
            maximum=2 if role in {'bullet','closing'} else 1
            if not 1<=len(bands)<=maximum or block.get('line_count')!=len(bands):
                fail('raster line count differs or exceeds limit')
            # Measured ink height, NOT an inferred font-size claim.
            minimum=16 if role=='caption' else 24
            if any(b[-1]-b[0]+1<minimum for b in bands): fail('raster text too small')
            if role=='bullet': counts.append(len(bands))
        all_counts.append(counts)
    return {'status':'readability_validated','card_count':len(media),'preview_width':390,
            'basis':'sealed-owner-review-and-measured-ink-bands','bullet_line_counts':all_counts}
