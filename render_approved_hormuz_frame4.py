#!/usr/bin/env python3
"""Rebuild approved Hormuz frame 4 while preserving every non-text pixel."""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TITLE = "مثال على الأثر: ميناء جبل علي"
BODY = (
    "ناول ميناء جبل علي 15.5 مليون حاوية قياسية خلال 2024، بمتوسط يتجاوز "
    "42 ألف حاوية يوميًا. تمر عبر مضيق هرمز السفن التي تربطه بالأسواق خارج "
    "الخليج، سواء كانت قادمة إلى الميناء أو مغادرة منه؛ لذلك قد يؤدي اضطراب "
    "المضيق إلى تأخير جزء كبير من حركته ورفع تكاليف الشحن."
)
SOURCE = Path("2026-09-06-hormuz-final-v4-story-04.png")
TEXT_REGION = (72, 1110, 1008, 1585)
SEAL_TOP = 1688
BACKGROUND = (242, 237, 230)
TEXT_COLOUR = (18, 62, 111)

sys.path.insert(0, str(Path.cwd()))
from news_bot_core import ar, _wrap  # noqa: E402


def font(size, *, bold=False):
    weight = "Bold" if bold else "Regular"
    return ImageFont.truetype(Path("fonts") / f"Almarai-{weight}.ttf", size)


def layout(draw):
    max_width = TEXT_REGION[2] - TEXT_REGION[0] - 40
    _, kwargs = ar("م")
    title_font = font(58, bold=True)
    title_lines = _wrap(draw, TITLE, title_font, max_width, kwargs)
    title_gap = int(58 * 1.24)
    title_top = 1160
    body_top = title_top + len(title_lines) * title_gap + 42

    body_size = 38
    while body_size >= 28:
        body_font = font(body_size)
        body_lines = _wrap(draw, BODY, body_font, max_width, kwargs)
        body_gap = int(body_size * 1.42)
        body_bottom = body_top + len(body_lines) * body_gap
        if body_bottom < SEAL_TOP:
            break
        body_size -= 2
    if body_bottom >= SEAL_TOP:
        raise SystemExit("approved frame 4 text overlaps the closing seal")
    return title_font, title_lines, title_gap, title_top, body_font, body_lines, body_gap, body_top


def main():
    image = Image.open(SOURCE).convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.rectangle(TEXT_REGION, fill=BACKGROUND)
    title_font, title_lines, title_gap, title_top, body_font, body_lines, body_gap, body_top = layout(draw)
    centre = image.width // 2

    y = title_top
    for line in title_lines:
        shaped, kwargs = ar(line)
        draw.text((centre, y), shaped, font=title_font, fill=TEXT_COLOUR, anchor="ma", **kwargs)
        y += title_gap

    y = body_top
    for line in body_lines:
        shaped, kwargs = ar(line)
        draw.text((centre, y), shaped, font=body_font, fill=TEXT_COLOUR, anchor="ma", **kwargs)
        y += body_gap

    image.save(SOURCE, "PNG", optimize=True)
    print("Approved Hormuz frame 4 rebuilt:", SOURCE)


if __name__ == "__main__":
    main()
