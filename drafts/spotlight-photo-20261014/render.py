"""Three photo Spotlight challenges in the owner-approved photo layout.

Layout and timing copied from the 10 Oct Spotlights «توقّع السعر — توستر سميج»
(a41d0b3d), «نزل بالسوق؟» (838f1d62) and «أعلى أو أقل — ويمبلي» (20d1c374):
photo card, question, two answer pills, 5-second countdown, answer at 8 s.
Photos are from Wikimedia Commons; CC BY ones carry a credit under the photo.

Facts:
- Crystal Pepsi launched in the US in 1992 and was withdrawn about a year later.
- The first iPhone launched 29 Jun 2007 at $499 (4 GB) and $599 (8 GB) with a
  two-year contract.
- Riyadh city 7,009,100 (GASTAT census 2022); Dubai about 3.8 million (Dubai
  Statistics Center, end 2024) — under twice, though people guess over.
"""
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault('FONT_FAMILY', 'Almarai')
os.environ.setdefault('THEME', 'light')
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFilter

import news_bot

W, H, FPS = 1080, 1920, 30
BG = '#EDE9E1'
NAVY, EMERALD, RED, GREY = '#153A4E', '#154A36', '#A9273B', '#909792'
PILL, PILL_OFF, SHARE = '#DAE5DA', '#E5E6DE', '#EEDDDE'
HERE = Path(__file__).parent
ASSETS, OUT = HERE / 'assets', HERE / 'out'
CARD = (82, 362, 998, 972)

CHALLENGES = {
    'crystal-pepsi': dict(
        kicker='نزل بالسوق؟', photo='pepsi.jpg',
        credit='الصورة: Mike Mozart · CC BY 2.0',
        question='بيبسي شفاف مثل الماء؟', sub=None,
        right='نزل بالسوق', left='مجرد فكرة', answer='right',
        lines=('اسمه Crystal Pepsi ونزل 1992', 'وانسحب من السوق بعد سنة تقريبًا')),
    'first-iphone': dict(
        kicker='توقّع السعر', photo='iphone.jpg', credit=None,
        question='كم كان سعر أول آيفون؟', sub='iPhone الأول من 2007، مع عقد سنتين',
        right='999 دولار', left='499 دولار', answer='left',
        lines=('سعره عند الإطلاق 499 دولار', 'لنسخة 4 جيجا، و599 لنسخة 8 جيجا')),
    # Haramain High Speed Railway 453 km (Makkah-Madinah) vs the LGV Sud-Est,
    # France's first high-speed line, 409 km (Paris-Lyon, opened 1981). Owner
    # asked for a shorter rival so Saudi viewers win the comparison.
    'haramain-train': dict(
        kicker='أطول أو أقصر', photo='haramain.jpg',
        credit='الصورة: محطة المدينة · Virtual trip · CC BY 4.0',
        question='قطار الحرمين أطول أو أقصر من باريس–ليون؟', sub=None,
        right='أطول', left='أقصر', answer='right', big='أطول!',
        lines=('قطار الحرمين 453 كم', 'وباريس–ليون 409 كم')),
    'riyadh-dubai': dict(
        kicker='أعلى أو أقل', photo='riyadh.jpg', credit=None,
        question='سكان الرياض أكثر أو أقل من ضعف سكان دبي؟', sub=None,
        right='أكثر', left='أقل', answer='left', big='أقل!',
        lines=('الرياض 7 ملايين (تعداد 2022)', 'ودبي 3.8 مليون (2024)')),
}


def text(d, xy, s, size, fill, bold=True, anchor='mm'):
    shaped, kw = news_bot.ar(s)
    d.text(xy, shaped, font=news_bot.load_font(size, bold=bold), fill=fill, anchor=anchor, **kw)


def badge(img, cx, cy, size):
    b = Image.open(ASSETS / 'badge.jpg').convert('RGB').resize((size, size), Image.LANCZOS)
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    img.paste(b, (cx - size // 2, cy - size // 2), mask)


def photo_card(img, name):
    x0, y0, x1, y1 = CARD
    w, h = x1 - x0, y1 - y0
    src = Image.open(ASSETS / name).convert('RGB')
    scale = max(w / src.width, h / src.height)
    cover = src.resize((round(src.width * scale), round(src.height * scale)), Image.LANCZOS)
    left, top = (cover.width - w) // 2, (cover.height - h) // 2
    card = cover.crop((left, top, left + w, top + h))
    if src.height > src.width:
        # Portrait product shot: the whole object on a plain light panel, never a
        # crop that loses it (a blurred fill read as a smeared photo).
        card = Image.new('RGB', (w, h), '#F6F4F0')
        fit = min(w / src.width, h / src.height)
        whole = src.resize((round(src.width * fit), round(src.height * fit)), Image.LANCZOS)
        card.paste(whole, ((w - whole.width) // 2, (h - whole.height) // 2))
    mask = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=34, fill=255)
    img.paste(card, (x0, y0), mask)


def check(d, x, y):
    d.line([(x - 18, y), (x - 4, y + 14), (x + 20, y - 14)], fill=BG, width=6, joint='curve')


def frame(c, countdown=None, reveal=False):
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    badge(img, 128, 146, 82)
    d.rectangle([876, 115, 990, 124], fill=EMERALD)
    text(d, (988, 168), 'ملخص تنفيذي', 34, EMERALD, anchor='rm')
    text(d, (540, 296), c['kicker'], 52, RED)
    photo_card(img, c['photo'])
    if c['credit']:
        text(d, (990, 998), c['credit'], 22, GREY, bold=False, anchor='rm')

    text(d, (540, 1062), c['question'], 40 if len(c['question']) > 42 else 44 if len(c['question']) > 30 else 46, EMERALD)
    if c['sub']:
        text(d, (540, 1115), c['sub'], 30, NAVY, bold=False)

    if reveal and c.get('big'):
        text(d, (540, 1255), c['big'], 66, EMERALD)
        text(d, (540, 1345), c['lines'][0], 38, NAVY)
        text(d, (540, 1405), c['lines'][1], 38, NAVY)
    else:
        for side, box in (('right', (568, 1170, 998, 1280)), ('left', (82, 1170, 512, 1280))):
            cx = (box[0] + box[2]) // 2
            label = c[side]
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
        if reveal:
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
