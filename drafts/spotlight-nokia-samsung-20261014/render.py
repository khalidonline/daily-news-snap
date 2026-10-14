"""Spotlight challenge «من بدأ أول؟ Nokia ولا Samsung» — 12 s vertical MP4.

Typographic on purpose: no third-party photos or logos, so nothing to license.
Facts: Nokia began in 1865 as Fredrik Idestam's groundwood pulp mill (paper);
Samsung began in 1938 as Lee Byung-chul's Daegu trading store selling dried
fish, groceries and noodles. 1938 - 1865 = 73 years.
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

W, H, FPS = 1080, 1920, 10
CREAM, BLUE, EMERALD, RED = '#EEE8E3', '#183861', '#0B3D2E', '#B71C2C'
MUTED = '#8A8F98'
OUT = Path(__file__).with_name('out')


def text(d, xy, s, size, fill, bold=True, anchor='ma'):
    shaped, kw = news_bot.ar(s)
    d.text(xy, shaped, font=news_bot.load_font(size, bold=bold), fill=fill, anchor=anchor, **kw)


def base():
    img = Image.new('RGB', (W, H), CREAM)
    d = ImageDraw.Draw(img)
    d.rectangle([W - 300, 120, W - 80, 136], fill=EMERALD)
    text(d, (W - 80, 160), 'ملخص تنفيذي - تحدّي', 40, EMERALD, anchor='ra')
    text(d, (W // 2, 330), 'من بدأ أول؟', 120, BLUE)
    return img, d


def option(d, box, name, chosen=None, year=None, note=None):
    x0, y0, x1, y1 = box
    fill, ink, edge = CREAM, BLUE, BLUE
    if chosen is True:
        fill, ink, edge = EMERALD, CREAM, EMERALD
    elif chosen is False:
        ink, edge = MUTED, MUTED
    d.rounded_rectangle(box, radius=40, fill=fill, outline=edge, width=8)
    cx = (x0 + x1) // 2
    d.text((cx, y0 + 70), name, font=news_bot.load_font(86, bold=True), fill=ink, anchor='ma')
    if year:
        d.text((cx, y0 + 230), year, font=news_bot.load_font(150, bold=True), fill=ink, anchor='ma')
    else:
        d.text((cx, y0 + 250), '?', font=news_bot.load_font(200, bold=True), fill=ink, anchor='ma')
    for i, line in enumerate(note or ()):
        text(d, (cx, y0 + 450 + i * 66), line, 48, ink, bold=False)


LEFT, RIGHT = (90, 560, 520, 1230), (560, 560, 990, 1230)


def question(countdown=None):
    img, d = base()
    option(d, RIGHT, 'Nokia')
    option(d, LEFT, 'Samsung')
    text(d, (W // 2, 1320), 'وحدة منها أقدم بأكثر من 70 سنة', 54, BLUE, bold=False)
    if countdown:
        d.ellipse([W // 2 - 130, 1440, W // 2 + 130, 1700], fill=RED)
        d.text((W // 2, 1570), str(countdown), font=news_bot.load_font(170, bold=True),
               fill=CREAM, anchor='mm')
    else:
        text(d, (W // 2, 1500), 'توقّع قبل ما يطلع الجواب', 64, RED)
    return img


def answer():
    img, d = base()
    option(d, RIGHT, 'Nokia', True, '1865', ('بدأت', 'مصنع ورق'))
    option(d, LEFT, 'Samsung', False, '1938', ('بدأت محل', 'سمك مجفف وخضار'))
    text(d, (W // 2, 1320), 'Nokia أقدم من Samsung بـ 73 سنة', 62, RED)
    d.line([200, 1460, W - 200, 1460], fill=MUTED, width=3)
    text(d, (W // 2, 1520), 'لقيتها صح؟ خلّ خويك يجرّب', 58, BLUE)
    return img


def main():
    OUT.mkdir(exist_ok=True)
    frames = [question()] * 40 + [question(3)] * 10 + [question(2)] * 10 + [question(1)] * 10 \
        + [answer()] * 50
    stills = OUT / 'frames'
    stills.mkdir(exist_ok=True)
    for old in stills.glob('*.png'):
        old.unlink()
    cache = {}
    for i, frame in enumerate(frames):
        key = id(frame)
        if key not in cache:
            cache[key] = frame
        frame.save(stills / f'{i:04d}.png')
    question().save(OUT / 'preview-question.png')
    question(3).save(OUT / 'preview-countdown.png')
    answer().save(OUT / 'preview-answer.png')
    mp4 = OUT / 'nokia-samsung.mp4'
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-loglevel', 'error',
                    '-framerate', str(FPS), '-i', str(stills / '%04d.png'),
                    '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-shortest',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', '30', '-c:a', 'aac',
                    '-movflags', '+faststart', str(mp4)], check=True)
    print(mp4, mp4.stat().st_size, 'bytes,', len(frames) / FPS, 's')


if __name__ == '__main__':
    main()
