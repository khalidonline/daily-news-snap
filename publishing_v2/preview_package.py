"""Supervised eight-card review package using the established production renderers."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from PIL import Image
from .preview import ROOT, render_card, review_card, validate_date, _telegram
from .public_images import atomic_write, get_bytes, inspect_image

SPEC = ROOT / 'evaluation/first_complete_preview.json'


def verify_reviews(paths, reviews):
    if len(paths) != len(reviews) or not paths:
        raise ValueError('incomplete_package_review')
    for path, review in zip(paths, reviews):
        if review.get('passed') is not True or review.get('card_sha256') != hashlib.sha256(Path(path).read_bytes()).hexdigest():
            raise ValueError('unapproved_or_changed_card')


def send_album_once(paths, captions, journal, *, env, transport=None):
    if len(paths) != 8 or len(captions) != 8:
        raise ValueError('eight_cards_required')
    token, chat = env.get('TELEGRAM_TOKEN','').strip(), env.get('TELEGRAM_CHAT_ID','').strip()
    if not token or not chat:
        raise ValueError('missing_telegram_credentials')
    raws=[Path(p).read_bytes() for p in paths]
    state={'status':'unknown','card_sha256s':[hashlib.sha256(raw).hexdigest() for raw in raws]}
    journal=Path(journal)
    try:
        with journal.open('x') as stream:
            json.dump(state,stream);stream.flush();os.fsync(stream.fileno())
    except FileExistsError:
        raise RuntimeError('album_already_attempted') from None
    boundary='preview-'+os.urandom(16).hex()
    media=[{'type':'photo','media':f'attach://card{n}','caption':caption} for n,caption in enumerate(captions)]
    body=bytearray()
    for name,value in [('chat_id',chat),('media',json.dumps(media,ensure_ascii=False))]:
        body.extend((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n').encode())
    for n,raw in enumerate(raws):
        body.extend((f'--{boundary}\r\nContent-Disposition: form-data; name="card{n}"; filename="card{n}.jpg"\r\nContent-Type: image/jpeg\r\n\r\n').encode())
        body.extend(raw);body.extend(b'\r\n')
    body.extend(f'--{boundary}--\r\n'.encode())
    try:
        response=(transport or _telegram)('https://api.telegram.org/bot'+token+'/sendMediaGroup',bytes(body),
                                          {'Content-Type':'multipart/form-data; boundary='+boundary})
        messages=response.get('result')
        if response.get('ok') is not True or not isinstance(messages,list) or len(messages)!=8:
            raise ValueError('incomplete_album_receipt')
        if any(type(m.get('message_id')) is not int or str(m.get('chat',{}).get('id'))!=chat for m in messages):
            raise ValueError('invalid_album_receipt')
        ids=[m['message_id'] for m in messages]
        if len(set(ids))!=8:
            raise ValueError('duplicate_album_receipt')
    except Exception:
        raise RuntimeError('album_unknown_do_not_retry') from None
    state.update(status='sent',message_ids=ids)
    atomic_write(journal,json.dumps(state).encode())
    return state


def render_package(spec, output):
    os.environ['THEME']='light';os.environ['FONT_FAMILY']='Almarai'
    import news_bot
    import story_bot
    if news_bot.THEME!='light' or news_bot.FONT_FAMILY!='Almarai' or news_bot.brand_badge(150) is None:
        raise ValueError('original_design_unavailable')
    cards=spec['cards']
    if [c['kind'] for c in cards]!=['info','topic']+['story']*6:
        raise ValueError('invalid_package_structure')
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    paths=[]
    for n,card in enumerate(cards):
        source=output/(card['image']['sha256']+'.jpg')
        if not source.exists():
            atomic_write(source,get_bytes(card['image']['download_url']))
        raw=source.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=card['image']['sha256']:
            raise ValueError('source_image_changed')
        inspect_image(raw)
        # Curated source framing; the production template and photo box are unchanged.
        crop=card['image'].get('crop_box')
        if crop is not None:
            if len(crop)!=4 or not (0<=crop[0]<crop[2]<=1 and 0<=crop[1]<crop[3]<=1):
                raise ValueError('invalid_source_crop')
            with Image.open(source) as photo:
                w,h=photo.size
                framed=photo.crop((round(crop[0]*w),round(crop[1]*h),round(crop[2]*w),round(crop[3]*h))).convert('RGB')
            source=output/f'framed-{n+1:02d}.png'
            framed.save(source,'PNG')
        target=output/f'{n+1:02d}-{card["kind"]}.jpg'
        if card['kind']=='story':
            story_bot.render_frame(target.with_suffix('.png'),'ملخص تنفيذي - قصة',f'{n-1} من 6',card['title'],64,
                                   sub=card['body'],photo=source,punch=card['punch'])
            with Image.open(target.with_suffix('.png')) as rendered:
                rgb=rendered.convert('RGB')
            rgb.save(target,'JPEG',quality=95)
        else:
            render_card({'title_lines':[card['title']],'body_lines':[card['body']],
                         'closing_lines':[card['punch']],'brand':'معلومة تهمك'},source,target)
        paths.append(target)
    return paths


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='complete-preview-output')
    parser.add_argument('--review',action='store_true')
    parser.add_argument('--send',action='store_true')
    args=parser.parse_args()
    spec=json.loads(SPEC.read_text());validate_date(spec['activation_date'])
    if args.send and (not args.review or os.environ.get('GITHUB_RUN_ATTEMPT')!='1'):
        raise ValueError('send_requires_review_and_first_attempt')
    output=Path(args.output)
    paths=render_package(spec,output)
    atomic_write(output/'package.json',json.dumps(spec,ensure_ascii=False).encode())
    if not args.review:
        return 0
    reviews=[]
    for n,(path,card) in enumerate(zip(paths,spec['cards'])):
        # A maximum of eight reviews (one per card), each using the bounded adapter.
        brief={'activation_date':spec['activation_date'],'trigger_url':spec['trigger_url'],
               'trigger_type':'daily_editorial_feature','card':card,
               'review_context':'Historical Apollo 11 story in 1969. Modern aurora photo is illustrative, not an Apollo-era photograph. Photo credits are in the accompanying Telegram captions.'}
        review=review_card(path,brief,env=os.environ);reviews.append(review)
        atomic_write(output/f'review-{n+1:02d}.json',json.dumps(review,ensure_ascii=False).encode())
        print(json.dumps({'card':n+1,'passed':review['passed'],'reason':review['reason'],'model':review['model'],'usage':review['usage']},ensure_ascii=False),flush=True)
    verify_reviews(paths,reviews)
    if args.send:
        validate_date(spec['activation_date'])
        captions=[]
        for n,card in enumerate(spec['cards']):
            label=['معلومة — بالتصميم السابق','موضوع'][n] if n<2 else f'قصة مايكل كولينز — {n-1}/6'
            caption=label+'\n'+card['title']+'\nللمراجعة فقط — لم تُنشر على سناب شات.\n'
            caption+='المحفز: صورة الفلك اليوم 12 سبتمبر 2026. القصة تاريخية من 1969.\n'
            caption+='Photo: '+card['image']['credit']+'\n'+card['source_url']
            if len(caption)>1024:raise ValueError('caption_too_long')
            captions.append(caption)
        print(json.dumps(send_album_once(paths,captions,output/'telegram-album-receipt.json',env=os.environ)),flush=True)
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print('Complete preview stopped: '+type(error).__name__)
        raise SystemExit(1)
