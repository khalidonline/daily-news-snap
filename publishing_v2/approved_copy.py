"""Offline, render-only handoff. Copy approval is NOT publication approval.

No model calls, image retrieval, sealing or delivery. The normal visual, rights,
readiness, expiry and publication gates must still approve the rendered assets.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_FIELDS = ('kind', 'title', 'body', 'punch', 'caption')

def digest(value):
    return hashlib.sha256(value).hexdigest()

def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()

def copy_hash(cards):
    return digest(encoded([{k:c.get(k,'') for k in TEXT_FIELDS} for c in cards]))

def template_hash():
    names = ['publishing_v2/approved_copy.py','publishing_v2/preview.py','news_bot.py','story_bot.py']
    paths = [ROOT/n for n in names] + sorted((ROOT/'fonts').glob('*.ttf')) + sorted((ROOT/'images/brand').glob('*'))
    return digest(b''.join(p.read_bytes() for p in paths if p.is_file()))

def render(card, photo, target, counter):
    os.environ['THEME']='light'; os.environ['FONT_FAMILY']='Almarai'
    from .preview import render_card
    from PIL import Image
    if card['kind']=='info':
        render_card({'brand':'ملخص تنفيذي - معلومة','title_lines':[card['title']],
                     'body_lines':[card['body']],'closing_lines':[card.get('punch','')]},photo,target)
    else:
        from story_bot import render_frame
        render_frame(target.with_suffix('.png'),'ملخص تنفيذي - قصة',counter,card['title'],64,
                     sub=card['body'],punch=card.get('punch',''),photo=photo,photo_caption=card.get('caption',''))
        with Image.open(target.with_suffix('.png')) as image:
            image.convert('RGB').save(target,quality=95)

def prepare(doc, assets, output, *, renderer=render):
    cards=doc.get('cards',[]); approval=doc.get('approval',{})
    if (doc.get('version')!=1 or not isinstance(cards,list) or not 2<=len(cards)<=10
        or not all(isinstance(c,dict) for c in cards)
        or [c.get('kind') for c in cards] != ['info']+['story']*(len(cards)-1)):
        raise ValueError('invalid_cards')
    for card in cards:
        if any(not isinstance(card.get(k,''),str) for k in TEXT_FIELDS):
            raise ValueError('invalid_copy')
        if not card.get('title','').strip() or not card.get('body','').strip():
            raise ValueError('empty_copy')
    if (not isinstance(approval,dict) or not isinstance(approval.get('reference'),str)
        or not approval['reference'].strip() or approval.get('copy_sha256')!=copy_hash(cards)):
        raise ValueError('copy_approval_required_or_changed')
    assets=Path(assets).resolve(); output=Path(output).resolve()
    # Validate every input before touching any output; require real local assets.
    photos=[]
    for card in cards:
        if not isinstance(card.get('photo'),str): raise ValueError('photo_required')
        photo=(assets/card['photo']).resolve()
        if not photo.is_relative_to(assets) or not photo.is_file(): raise ValueError('unsafe_or_missing_photo')
        photos.append(photo)
    output.mkdir(parents=True,exist_ok=True)
    state_path=output/'render-state.json'
    previous=json.loads(state_path.read_text()) if state_path.exists() else {}
    cache=previous.get('cards',{})
    report={'production_ready':False,'publication_approval':False,'model_requests':0,
            'copy_sha256':copy_hash(cards),'rendered':[],'reused':[],'cards':{}}
    template=template_hash(); digits=str.maketrans('0123456789','٠١٢٣٤٥٦٧٨٩')
    for index,(card,photo) in enumerate(zip(cards,photos)):
        name=f'card-{index:02d}.jpg'; target=output/name
        counter=f'{index} من {len(cards)-1}'.translate(digits) if index else ''
        key=digest(encoded([card,counter,digest(photo.read_bytes()),template]))
        prior=cache.get(name,{})
        if (prior.get('input_sha256')==key and target.is_file()
            and prior.get('output_sha256')==digest(target.read_bytes())):
            report['reused'].append(name)
        else:
            temporary=output/f'.{name}'
            renderer(card,photo,temporary,counter)
            temporary.replace(target)
            temporary.with_suffix('.png').unlink(missing_ok=True)
            report['rendered'].append(name)
        report['cards'][name]={'input_sha256':key,'output_sha256':digest(target.read_bytes()),'counter':counter}
    # Exact copy retained for visual comparison. This file grants no media approval.
    (output/'copy.json').write_bytes(encoded(doc))
    temporary=state_path.with_suffix('.tmp'); temporary.write_bytes(encoded(report));temporary.replace(state_path)
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--copy',type=Path,required=True)
    parser.add_argument('--assets',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(json.loads(args.copy.read_text()),args.assets,args.output),ensure_ascii=False))

if __name__=='__main__': main()
