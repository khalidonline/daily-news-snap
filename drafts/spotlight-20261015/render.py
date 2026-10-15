"""Five Spotlight challenges for 15 Oct, one per format, in the approved layouts.

Photo layout from the 14 Oct photo challenges (Pepsi/iPhone/Disah); the logo
layout from the Nokia/Samsung one (itself the Puma/Adidas design). Correct pill
turns emerald with a tick, the other greys out. Prices in riyals at 3.75.

Facts:
- Coca-Cola: first sold in Atlanta, 1886. Pepsi: created as «Brad's Drink»
  in New Bern, 1893. 1893 - 1886 = 7.
- Nintendo Virtual Boy: released Jul 1995 (Japan) / Aug 1995 (US), dropped
  Dec 1995 in Japan and early 1996 in the US — under a year on sale.
- PlayStation (US launch 9 Sep 1995): $299 = 1,121 riyals at 3.75.
- Abraj Al Bait clock tower 601 m; Empire State Building 443 m to the tip.
- Umluj: Pexels «A pod of dolphins ... Red Sea near Umluj» (Abdulhalim Mudag).
Photos: Virtual Boy and PlayStation are Evan-Amos public domain (Commons);
clock tower and Umluj are Pexels licence. None needs a credit.
"""
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault('FONT_FAMILY', 'Almarai')
os.environ.setdefault('THEME', 'light')
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import imageio_ffmpeg
from PIL import Image, ImageDraw

import news_bot

W, H, FPS = 1080, 1920, 30
BG = '#EDE9E1'
NAVY, EMERALD, RED, GREY = '#153A4E', '#154A36', '#A9273B', '#909792'
PILL, PILL_OFF, SHARE = '#DAE5DA', '#E5E6DE', '#EEDDDE'
HERE = Path(__file__).parent
ASSETS, OUT = HERE / 'assets', HERE / 'out'
CARD = (82, 362, 998, 972)

CHALLENGES = {
    'coke-pepsi': dict(
        kicker='من بدأ أول؟', logos=True, question='مين بدأت أول؟',
        right=dict(name='بيبسي', logo='pepsi.png', year='1893'),
        left=dict(name='كوكاكولا', logo='cocacola.png', year='1886'),
        answer='left', verdict='كوكاكولا سبقت بيبسي بـ 7 سنوات'),
    'virtual-boy': dict(
        kicker='نزل بالسوق؟', photo='virtualboy.jpg', credit=None, fit=True,
        question='نظارة ألعاب ثلاثية الأبعاد من نينتندو؟', sub=None,
        right='نزل بالسوق', left='مجرد فكرة', answer='right',
        lines=('اسمها Virtual Boy ونزلت 1995', 'وانسحبت من السوق بأقل من سنة')),
    'playstation-1': dict(
        kicker='توقّع السعر', photo='ps1.jpg', credit=None, fit=True,
        question='كم كان سعر بلايستيشن 1 أول ما نزل؟', sub=None,
        right='1,120 ريال', left='560 ريال', answer='right',
        lines=('سعره حوالي 1,120 ريال', 'عند نزوله في أمريكا سنة 1995')),
    'clock-tower': dict(
        kicker='أطول أو أقصر', photo='clocktower.jpg', credit=None,
        question='برج الساعة في مكة أطول أو أقصر من إمباير ستيت؟', sub=None,
        right='أطول', left='أقصر', answer='right',
        lines=('برج الساعة 601 متر', 'وإمباير ستيت 443 متر')),
    'umluj': dict(
        kicker='توقّع المكان', photo='umluj.jpg', credit=None,
        question='وين هالمكان؟', sub=None,
        right='هاواي', left='أملج', answer='left',
        lines=('هذي دلافين في البحر الأحمر', 'قريب من أملج')),
}


def text(d, xy, s, size, fill, bold=True, anchor='mm'):
    shaped, kw = news_bot.ar(s)
    d.text(xy, shaped, font=news_bot.load_font(size, bold=bold), fill=fill, anchor=anchor, **kw)


def badge(img, cx, cy, size):
    b = Image.open(ASSETS / 'badge.jpg').convert('RGB').resize((size, size), Image.LANCZOS)
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    img.paste(b, (cx - size // 2, cy - size // 2), mask)


def photo_card(img, name, fit=False):
    x0, y0, x1, y1 = CARD
    w, h = x1 - x0, y1 - y0
    src = Image.open(ASSETS / name).convert('RGB')
    scale = max(w / src.width, h / src.height)
    cover = src.resize((round(src.width * scale), round(src.height * scale)), Image.LANCZOS)
    left, top = (cover.width - w) // 2, (cover.height - h) // 2
    card = cover.crop((left, top, left + w, top + h))
    if fit:
        # Studio shot on white: show the whole object with margin — a cover crop
        # cut the Virtual Boy's headset and the PlayStation's lid off.
        card = Image.new('RGB', (w, h), '#FFFFFF')
        k = min((w - 80) / src.width, (h - 60) / src.height)
        whole = src.resize((round(src.width * k), round(src.height * k)), Image.LANCZOS)
        card.paste(whole, ((w - whole.width) // 2, (h - whole.height) // 2))
    elif src.height > src.width:
        # Portrait product shot: the whole object on a plain light panel, never a
        # crop that loses it (a blurred fill read as a smeared photo).
        card = Image.new('RGB', (w, h), '#F6F4F0')
        fit = min(w / src.width, h / src.height)
        whole = src.resize((round(src.width * fit), round(src.height * fit)), Image.LANCZOS)
        card.paste(whole, ((w - whole.width) // 2, (h - whole.height) // 2))
    mask = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=34, fill=255)
    img.paste(card, (x0, y0), mask)


def paste_fit(img, path, box):
    logo = Image.open(path).convert('RGBA')
    x0, y0, x1, y1 = box
    scale = min((x1 - x0) / logo.width, (y1 - y0) / logo.height)
    logo = logo.resize((int(logo.width * scale), int(logo.height * scale)), Image.LANCZOS)
    img.paste(logo, ((x0 + x1 - logo.width) // 2, (y0 + y1 - logo.height) // 2), logo)


def logo_card(img, d, c):
    # The Nokia/Samsung card: white panel, divider, logo over name per side.
    d.rounded_rectangle(CARD, radius=34, fill='#FFFFFF')
    d.line([540, 442, 540, 892], fill='#EEE8E1', width=4)
    for side, cx in (('right', 783), ('left', 297)):
        paste_fit(img, ASSETS / c[side]['logo'], (cx - 170, 560, cx + 170, 730))
        text(d, (cx, 836), c[side]['name'], 46, NAVY)


def check(d, x, y):
    d.line([(x - 18, y), (x - 4, y + 14), (x + 20, y - 14)], fill=BG, width=6, joint='curve')


def frame(c, countdown=None, reveal=False):
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    badge(img, 128, 146, 82)
    d.rectangle([876, 115, 990, 124], fill=EMERALD)
    text(d, (988, 168), 'ملخص تنفيذي', 34, EMERALD, anchor='rm')
    text(d, (540, 296), c['kicker'], 52, RED)
    if c.get('logos'):
        logo_card(img, d, c)
    else:
        photo_card(img, c['photo'], c.get('fit', False))
    if c.get('credit'):
        text(d, (990, 998), c['credit'], 22, GREY, bold=False, anchor='rm')

    text(d, (540, 1062), c['question'], 40 if len(c['question']) > 42 else 44 if len(c['question']) > 30 else 46, EMERALD)
    if c.get('sub'):
        text(d, (540, 1115), c['sub'], 30, NAVY, bold=False)

    if reveal and c.get('big'):
        text(d, (540, 1255), c['big'], 66, EMERALD)
        text(d, (540, 1345), c['lines'][0], 38, NAVY)
        text(d, (540, 1405), c['lines'][1], 38, NAVY)
    else:
        for side, box in (('right', (568, 1170, 998, 1280)), ('left', (82, 1170, 512, 1280))):
            cx = (box[0] + box[2]) // 2
            label = c[side]['name'] if c.get('logos') else c[side]
            if reveal and side == c['answer']:
                d.rounded_rectangle(box, radius=24, fill=EMERALD)
                text(d, (cx, 1222), label, 44, BG)
                check(d, box[0] + 48, 1222)
            elif reveal:
                d.rounded_rectangle(box, radius=24, fill=PILL_OFF)
                text(d, (cx, 1222), label, 44, GREY)
            else:
                d.rounded_rectangle(box, radius=24, fill=PILL)
                text(d, (cx, 1222), label, 44, NAVY)
        if reveal and c.get('logos'):
            for side, cx in (('right', 783), ('left', 297)):
                text(d, (cx, 1330), 'سنة التأسيس', 30, NAVY)
                d.text((cx, 1380), c[side]['year'], font=news_bot.load_font(50, bold=True),
                       fill=EMERALD, anchor='mm')
            text(d, (540, 1484), c['verdict'], 38, EMERALD)
        elif reveal:
            text(d, (540, 1355), c['lines'][0], 40, EMERALD)
            text(d, (540, 1425), c['lines'][1], 38, NAVY)
        else:
            text(d, (540, 1327), 'عندك 5 ثواني تختار', 34, NAVY)
            if countdown:
                d.text((540, 1410), str(countdown), font=news_bot.load_font(80, bold=True),
                       fill=RED, anchor='mm')

    d.rounded_rectangle([82, 1560, 998, 1662], radius=28, fill=SHARE)
    text(d, (540, 1610), 'شاركها مع صديقك وشف يجيبها؟', 42, RED)
    badge(img, 540, 1717, 50)
    return img


def render(slug, c):
    out = OUT / slug
    out.mkdir(parents=True, exist_ok=True)
    # 3 s to read, 5-4-3-2-1, then 4 s of answer — the approved timing.
    timeline = [(frame(c), 3)] + [(frame(c, n), 1) for n in (5, 4, 3, 2, 1)] \
        + [(frame(c, reveal=True), 4)]
    lines = []
    for i, (img, seconds) in enumerate(timeline):
        path = out / f'scene-{i}.png'
        img.save(path)
        lines += [f"file '{path.name}'\nduration 1\n"] * seconds
    lines.append(f"file '{path.name}'\n")
    listing = out / 'concat.txt'
    listing.write_text(''.join(lines))
    timeline[2][0].save(out / 'preview-countdown.png')
    timeline[-1][0].save(out / 'preview-answer.png')
    mp4 = out / f'{slug}.mp4'
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-loglevel', 'error',
                    '-f', 'concat', '-safe', '0', '-i', str(listing),
                    # Approved track: ticks at 3-7 s, chime at 8 s — this timeline.
                    '-i', str(ASSETS / 'countdown-sound.m4a'), '-t', '12',
                    '-vf', f'fps={FPS},format=yuv420p', '-c:v', 'libx264', '-c:a', 'aac',
                    '-movflags', '+faststart', str(mp4)], check=True)
    for p in out.glob('scene-*.png'):
        p.unlink()
    listing.unlink()
    print(mp4, mp4.stat().st_size, 'bytes')


if __name__ == '__main__':
    for slug in sys.argv[1:] or CHALLENGES:
        render(slug, CHALLENGES[slug])
