"""Deterministic candidate information-card template. Never authorizes delivery.

Almarai Regular is an explicit candidate asset, NOT an identified historical
reference font. Owner visual approval is required before this new template is live.
"""
from pathlib import Path
import json
import hashlib
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]


def render(headline, bullets, closing, photos, captions, *, bullet_styles=None, share_icon=None):
    settings=json.loads((ROOT/'publishing_v2/design-settings.json').read_text())
    colors=settings['palette']['exact_numeric_tokens']
    if not 1 <= len(bullets) <= 4 or len(photos)!=2 or len(captions)!=2:
        raise ValueError('Expected 1–4 bullets and two captioned photos')
    image=Image.new('RGB',(1080,1920),colors['background'])
    draw=ImageDraw.Draw(image); blocks=[]
    font_path=ROOT/'fonts/Almarai-Regular.ttf'
    if hashlib.sha256(font_path.read_bytes()).hexdigest() != '94cc03a8a668a8657735a39947fc4ab26a45f60dfde20e892f5d4bae968563c0':
        raise ValueError('Template font asset changed; review required')

    if bullet_styles is None:
        approved=settings['typography']['information_bullets']
        bullet_styles=[(approved['size_px'],approved['weight_name'])]*len(bullets)
    if len(bullet_styles)!=len(bullets) or any(s not in range(40,49) or w not in {'Regular','Bold'} for s,w in bullet_styles):
        raise ValueError('Invalid owner comparison styles')

    def block(text,role,top,size,color,left=60,right=1020,limit=2,weight='Regular'):
        selected=ROOT/f'fonts/Almarai-{weight}.ttf'
        if weight=='Bold' and hashlib.sha256(selected.read_bytes()).hexdigest()!='353c525f8afc461ca6213ee210e77b865f2969ad1222a2cfc634680f1f4621d9':
            raise ValueError('Bold font asset changed')
        font=ImageFont.truetype(str(selected),size)
        lines=[]; line=''
        for word in text.split():
            trial=(line+' '+word).strip()
            measured=draw.textbbox((0,0),trial,font=font,direction='rtl')
            if measured[2]-measured[0]>right-left-2:
                if not line:raise ValueError(role+' overflow: unbreakable word')
                lines.append(line);line=word
                if draw.textlength(word,font=font,direction='rtl')>right-left:
                    raise ValueError(role+' overflow: unbreakable word')
            else:line=trial
        if line:lines.append(line)
        if not lines or len(lines)>limit:raise ValueError(role+' overflow: shorten copy, never shrink')
        bounds=[]
        for i,line in enumerate(lines):
            # Keep real Arabic ascenders/descenders in distinct line boxes.
            x=right if role=='bullet' else (left+right)/2
            anchor='rt' if role=='bullet' else 'mt'
            y=top+i*round(size*1.5)
            b=draw.textbbox((x,y),line,font=font,anchor=anchor,direction='rtl',language='ar')
            if b[0]<left or b[2]>right or b[3]>1730:raise ValueError(f'{role} overflow: {line} {b}')
            draw.text((x,y),line,font=font,fill=color,anchor=anchor,direction='rtl',language='ar')
            bounds.append(b)
        blocks.append({'role':role,'text':text,'color':color,'font_size':size,'font_weight':weight,
                       'line_boxes':[[int(v) for v in b] for b in bounds],
                       'line_count':len(lines),'box':[int(min(b[0] for b in bounds)),int(top),
                       int(max(b[2] for b in bounds))+1,int(max(b[3] for b in bounds))+1]})

    def logo(x,y,size):
        badge=Image.open(ROOT/'images/brand/badge.png').convert('RGB')
        badge=ImageOps.contain(badge,(size,size))
        mask=Image.new('L',badge.size);ImageDraw.Draw(mask).ellipse((0,0,badge.width-1,badge.height-1),fill=255)
        image.paste(badge,(x,y),mask)

    logo(70,115,95)
    draw.rectangle((800,125,1000,137),fill=colors['green'])
    brand=ImageFont.truetype(str(font_path),36)
    draw.text((1000,175),'ملخص تنفيذي',font=brand,fill=colors['green'],anchor='rt',direction='rtl')
    block(headline,'headline',280,52,colors['red'],limit=1)
    for photo,caption,left in zip(photos,captions,[60,552]):
        panel=ImageOps.fit(photo.convert('RGB'),(468,410),method=Image.Resampling.LANCZOS)
        mask=Image.new('L',panel.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,467,409),radius=24,fill=255)
        image.paste(panel,(left,380),mask)
        block(caption,'caption',815,28,colors['caption'],left=left,right=left+468,limit=1)
    for n,text in enumerate(bullets):
        y=905+n*146
        size,weight=bullet_styles[n]
        block(text,'bullet',y,size,colors['body'],left=70,right=980,weight=weight)
        draw.ellipse((1000,y+15,1013,y+28),fill=colors['body'])
        blocks[-1]['box'][2]=1015
    block(closing,'closing',1500,44,colors['red'])
    draw.rounded_rectangle((60,1630,1020,1720),radius=24,fill=colors['cta_background'])
    block(settings['editorial_master']['cta_exact'],'cta',1650,40,colors['red'],left=80,right=920,limit=1)
    if share_icon is not None:
        if share_icon.size!=(100,87):raise ValueError('Pinned sharing icon must be 100x87')
        image.paste(share_icon,(910,1630))
    else:
        # Curved sharing arrow retained from the existing approved renderer.
        points=[(924,1705)]
        def curve(c1,c2,end):
            start=points[-1]
            for k in range(1,21):
                t=k/20;u=1-t
                points.append(tuple(u*u*u*start[i]+3*u*u*t*c1[i]+3*u*t*t*c2[i]+t*t*t*end[i] for i in (0,1)))
        curve((922,1675),(937,1661),(960,1659))
        points.extend([(960,1646),(964,1644),(991,1669),(993,1673),(991,1677),(966,1699),(960,1697),(960,1685)])
        curve((946,1685),(935,1690),(927,1706));draw.polygon(points,fill=colors['red'])
    logo(510,1750,60)
    return image,blocks
