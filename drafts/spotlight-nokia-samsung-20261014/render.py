"""Spotlight challenge «من بدأ أول؟ نوكيا ولا سامسونج» — 12 s vertical MP4.

Layout copied from the owner-approved Puma/Adidas Spotlight (10 Oct,
post 65096cfc): white logo card, question line, two answer pills, a
five-second countdown, then the answer with founding years.
Facts: Nokia began in 1865 (Fredrik Idestam's pulp mill); Samsung began in
1938 (Lee Byung-chul's trading store in Daegu). 1938 - 1865 = 73.
Wordmarks: Wikimedia Commons «Nokia wordmark.svg», «Samsung wordmark.svg».
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
BG, CARD, DIVIDER = '#EDE9E1', '#FFFFFF', '#EEE8E1'
NAVY, EMERALD, RED, GREY = '#153A4E', '#154A36', '#A9273B', '#909792'
PILL, PILL_OFF, SHARE = '#DAE5DA', '#E5E6DE', '#EEDDDE'
HERE = Path(__file__).parent
ASSETS, OUT = HERE / 'assets', HERE / 'out'

# Right column is read first in Arabic.
RIGHT = dict(name='سامسونج', logo='samsung.png', year='1938')
LEFT = dict(name='نوكيا', logo='nokia.png', year='1865')
WINNER = 'left'
QUESTION = 'مين تأسست أول؟'
VERDICT = 'نوكيا سبقت سامسونج بـ 73 سنة'


def text(d, xy, s, size, fill, bold=True, anchor='mm'):
    shaped, kw = news_bot.ar(s)
    d.text(xy, shaped, font=news_bot.load_font(size, bold=bold), fill=fill, anchor=anchor, **kw)


def paste_fit(img, path, box):
    logo = Image.open(path).convert('RGBA')
    x0, y0, x1, y1 = box
    scale = min((x1 - x0) / logo.width, (y1 - y0) / logo.height)
    logo = logo.resize((int(logo.width * scale), int(logo.height * scale)), Image.LANCZOS)
    img.paste(logo, ((x0 + x1 - logo.width) // 2, (y0 + y1 - logo.height) // 2), logo)


def badge(img, cx, cy, size):
    b = Image.open(ASSETS / 'badge.jpg').convert('RGB').resize((size, size), Image.LANCZOS)
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    img.paste(b, (cx - size // 2, cy - size // 2), mask)


def check(d, x, y):
    d.line([(x - 18, y), (x - 4, y + 14), (x + 20, y - 14)], fill=BG, width=6, joint='curve')


def frame(countdown=None, reveal=False):
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    badge(img, 128, 146, 82)
    d.rectangle([876, 115, 990, 124], fill=EMERALD)
    text(d, (988, 168), 'ملخص تنفيذي', 34, EMERALD, anchor='rm')
    text(d, (540, 296), 'من بدأ أول؟', 52, RED)

    d.rounded_rectangle([82, 362, 998, 972], radius=34, fill=CARD)
    d.line([540, 442, 540, 892], fill=DIVIDER, width=4)
    for side, cx in (('right', 783), ('left', 297)):
        opt = RIGHT if side == 'right' else LEFT
        paste_fit(img, ASSETS / opt['logo'], (cx - 170, 560, cx + 170, 730))
        text(d, (cx, 836), opt['name'], 46, NAVY)

    text(d, (540, 1065), QUESTION, 46, EMERALD)
    for side, box in (('right', (568, 1170, 998, 1280)), ('left', (82, 1170, 512, 1280))):
        opt = RIGHT if side == 'right' else LEFT
        cx = (box[0] + box[2]) // 2
        if reveal and side == WINNER:
            d.rounded_rectangle(box, radius=24, fill=EMERALD)
            text(d, (cx, 1222), opt['name'], 46, BG)
            check(d, box[0] + 48, 1222)
        elif reveal:
            d.rounded_rectangle(box, radius=24, fill=PILL_OFF)
            text(d, (cx, 1222), opt['name'], 46, GREY)
        else:
            d.rounded_rectangle(box, radius=24, fill=PILL)
            text(d, (cx, 1222), opt['name'], 46, NAVY)
        if reveal:
            text(d, (cx, 1330), 'سنة التأسيس', 30, NAVY)
            d.text((cx, 1380), opt['year'], font=news_bot.load_font(50, bold=True),
                   fill=EMERALD, anchor='mm')

    if reveal:
        text(d, (540, 1484), VERDICT, 38, EMERALD)
    else:
        text(d, (540, 1327), 'عندك 5 ثواني تختار', 34, NAVY)
        if countdown:
            d.text((540, 1410), str(countdown), font=news_bot.load_font(80, bold=True),
                   fill=RED, anchor='mm')

    d.rounded_rectangle([82, 1560, 998, 1662], radius=28, fill=SHARE)
    text(d, (540, 1610), 'شاركها مع صديقك وشف يجيبها؟', 42, RED)
    badge(img, 540, 1717, 50)
    return img


def main():
    OUT.mkdir(exist_ok=True)
    # 3 s to read, 5-4-3-2-1, then 4 s of answer — the Puma/Adidas timing.
    timeline = [(frame(), 3)] + [(frame(n), 1) for n in (5, 4, 3, 2, 1)] + [(frame(reveal=True), 4)]
    listing = OUT / 'concat.txt'
    lines = []
    for i, (img, seconds) in enumerate(timeline):
        path = OUT / f'scene-{i}.png'
        img.save(path)
        # whole-second repeated entries: ffmpeg 7 concat holds stills unpredictably otherwise
        lines += [f"file '{path.name}'\nduration 1\n"] * seconds
    lines.append(f"file '{path.name}'\n")
    listing.write_text(''.join(lines))
    timeline[0][0].save(OUT / 'preview-question.png')
    timeline[2][0].save(OUT / 'preview-countdown.png')
    timeline[-1][0].save(OUT / 'preview-answer.png')
    mp4 = OUT / 'nokia-samsung.mp4'
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-loglevel', 'error',
                    '-f', 'concat', '-safe', '0', '-i', str(listing),
                    # The approved Puma/Adidas track: a tick at 3,4,5,6,7 s and a chime at 8 s,
                    # which is exactly this timeline.
                    '-i', str(ASSETS / 'countdown-sound.m4a'), '-t', '12',
                    '-vf', f'fps={FPS},format=yuv420p', '-c:v', 'libx264', '-c:a', 'aac',
                    '-movflags', '+faststart', str(mp4)], check=True)
    for p in OUT.glob('scene-*.png'):
        p.unlink()
    listing.unlink()
    print(mp4, mp4.stat().st_size, 'bytes')


if __name__ == '__main__':
    main()
