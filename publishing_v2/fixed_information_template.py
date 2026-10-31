"""Owner-authorized information template; all geometry comes from the master.

Rendering never authorizes delivery. Final content/mobile review is required.
"""
from pathlib import Path
import json
import hashlib
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]


def render(headline, bullets, closing, photos, captions, *, bullet_styles=None, share_icon=None):
    settings=json.loads((ROOT/'publishing_v2/design-settings.json').read_text())
    colors=settings['palette']['exact_numeric_tokens']
    layout=settings['information_template']
    balanced=layout.get('approved_layout_override')
    if balanced:
        grid=balanced['regions_xyxy']
        layout={**layout,'title_top':grid['title'][1], 'photo_top':grid['images'][1],
                'photo_height':grid['images'][3]-grid['images'][1],
                'caption_top':grid['captions'][1]+5,'closing_top':grid['closing'][1]}
    sizes=settings['typography']['sizes_px']
    if not 1 <= len(bullets) <= 4 or len(photos) not in (1,2) or len(captions)!=len(photos):
        raise ValueError('Expected 1–4 bullets and one or two captioned photos')
    artwork=ROOT/layout['base_artwork_path']
    if hashlib.sha256(artwork.read_bytes()).hexdigest()!=layout['base_artwork_sha256']:
        raise ValueError('Approved artwork changed; review required')
    reference=Image.open(artwork).convert('RGB')
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

    def block(text,role,top,size,color,left=60,right=1020,limit=2,weight='Regular',measure=False):
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
        if balanced and role=='bullet':
            masks=[]
            for line in lines:
                mask=Image.new('L',(1100,150))
                ImageDraw.Draw(mask).text((1080,0),line,font=font,anchor='rt',direction='rtl',language='ar',fill=255)
                masks.append(mask.crop(mask.getbbox()))
            gap=balanced['line_spacing']['visible_gap_px']
            if measure:return sum(m.height for m in masks)+gap*(len(masks)-1)
            bounds=[]; y=top
            for mask in masks:
                b=[right-mask.width,y,right,y+mask.height]
                if b[0]<left or b[3]>grid['body'][3]:raise ValueError('bullet overflow: shorten copy, never shrink')
                image.paste(color,(b[0],b[1]),mask)
                bounds.append(b);y=b[3]+gap
            blocks.append({'role':role,'text':text,'color':color,'font_size':size,'font_weight':weight,
                           'line_boxes':bounds,'line_count':len(lines),
                           'box':[min(b[0] for b in bounds),top,right,bounds[-1][3]]})
            return
        bounds=[]
        for i,line in enumerate(lines):
            # Keep real Arabic ascenders/descenders in distinct line boxes.
            x=right if role in {'bullet','headline'} else (left+right)/2
            anchor='rt' if role in {'bullet','headline'} else 'mt'
            y=top+i*(layout['line_step'] if role=='bullet' else round(size*1.5))
            b=draw.textbbox((x,y),line,font=font,anchor=anchor,direction='rtl',language='ar')
            if b[0]<left or b[2]>right or b[3]>1730:raise ValueError(f'{role} overflow: {line} {b}')
            draw.text((x,y),line,font=font,fill=color,anchor=anchor,direction='rtl',language='ar')
            bounds.append(b)
        blocks.append({'role':role,'text':text,'color':color,'font_size':size,'font_weight':weight,
                       'line_boxes':[[int(v) for v in b] for b in bounds],
                       'line_count':len(lines),'box':[int(min(b[0] for b in bounds)),int(top),
                       int(max(b[2] for b in bounds)),int(max(b[3] for b in bounds))+1]})

    def logo(x,y,size):
        badge=Image.open(ROOT/'images/brand/badge.png').convert('RGB')
        badge=ImageOps.contain(badge,(size,size))
        mask=Image.new('L',badge.size);ImageDraw.Draw(mask).ellipse((0,0,badge.width-1,badge.height-1),fill=255)
        image.paste(badge,(x,y),mask)

    logo(70,115,95)
    region=layout['header_region']
    if balanced:
        header=ImageOps.contain(reference.crop(region),(95,95),method=Image.Resampling.LANCZOS)
        target=grid['account_name']
        image.paste(header,(target[2]-header.width,target[1]+(95-header.height)//2))
    else:image.paste(reference.crop(region),tuple(region[:2]))
    block(headline,'headline',layout['title_top'],sizes['headline'],colors['red'],limit=1)
    width=960 if len(photos)==1 else 468
    for photo,caption,left in zip(photos,captions,[60,552]):
        height=layout['photo_height']
        panel=ImageOps.fit(photo.convert('RGB'),(width,height),method=Image.Resampling.LANCZOS)
        mask=Image.new('L',panel.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,width-1,height-1),radius=24,fill=255)
        image.paste(panel,(left,layout['photo_top']),mask)
        block(caption,'caption',layout['caption_top'],sizes['caption'],colors['caption'],left=left,right=left+width,limit=1)
    if balanced:
        heights=[block(t,'bullet',0,s,colors['body'],left=70,right=980,weight=w,measure=True)
                 for t,(s,w) in zip(bullets,bullet_styles)]
        top=balanced['paragraph_distribution']['top_boundary']
        bottom=balanced['paragraph_distribution']['bottom_boundary']
        gap=(bottom-top-sum(heights))/(len(bullets)+1)
        if gap<layout['minimum_actual_block_gap']:raise ValueError('bullet overflow: insufficient paragraph gaps')
    for n,text in enumerate(bullets):
        y=(top+round(gap*(n+1))+sum(heights[:n])) if balanced else layout['body_top']+round(n*(layout['last_bullet_top']-layout['body_top'])/max(1,len(bullets)-1))
        size,weight=bullet_styles[n]
        block(text,'bullet',y,size,colors['body'],left=70,right=980,weight=weight)
        draw.ellipse((1000,y+15,1013,y+28),fill=colors['body'])
        blocks[-1]['box'][2]=1015
    block(closing,'closing',layout['closing_top'],sizes['closing'],colors['red'],limit=layout['closing_max_lines'])
    cta_box=grid['cta'] if balanced else (60,1630,1020,1720)
    draw.rounded_rectangle(cta_box,radius=24,fill=colors['cta_background'])
    block(settings['editorial_master']['cta_exact'],'cta',cta_box[1]+9 if balanced else 1650,sizes['cta'],colors['red'],left=80,right=920,limit=1)
    if share_icon is None:
        share_icon=reference.crop(layout['share_icon_region'])
    if share_icon is not None:
        if share_icon.size!=(100,87):raise ValueError('Pinned sharing icon must be 100x87')
        if balanced:
            share_icon=ImageOps.contain(share_icon,(75,65),method=Image.Resampling.LANCZOS)
            image.paste(share_icon,(1020-share_icon.width,cta_box[1]))
        else:image.paste(share_icon,(910,1630))
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
    from .design_contract import _information_geometry
    _information_geometry(blocks,settings)
    return image,blocks
