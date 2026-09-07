#!/usr/bin/env python3
"""Apply frame 4's typography and spacing to all approved Hormuz frames."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from news_bot_core import ar, _wrap


FONT_FAMILY = "Almarai"
TITLE_SIZE = 58
BODY_START_SIZE = 38
TITLE_TOP = 1160
# Frame 4 is the locked visual reference for every card.
TEXT_REGION = (72, 1110, 1008, 1680)
FOOTER_REGION = (48, 1832, 1032, 1918)
BACKGROUND = (242, 237, 230)
TEXT_COLOUR = (18, 62, 111)
ACCENT = (190, 150, 0)
MUTED = (143, 136, 129)
CONSOLIDATED_SOURCES = (
    "المصادر: المنظمة البحرية الدولية، وكالة الطاقة الدولية، "
    "موانئ دبي العالمية، كلية لندن للاقتصاد"
)

FRAMES = [
    {
        "title": "هل مرّت أغراض بيتك من هنا؟",
        "body": "هاتفك، سيارتك، ملابسك، أغراض المنزل والطعام المستورد... كثير من السلع الداخلة إلى موانئ الخليج تعبر أولاً مضيق هرمز.",
    },
    {
        "title": "لأن الخليج له بوابة بحرية واحدة",
        "body": "أي سفينة قادمة من المحيط إلى موانئ الإمارات وقطر والبحرين والكويت، أو خارجة منها إلى العالم، تمر عبر هرمز. لا يوجد مدخل بحري آخر إلى الخليج.",
    },
    {
        "title": "فهل تسيطر إيران على هذه البوابة؟",
        "body": "لا. المضيق يقع بين إيران وعُمان، ولا تملكه إيران وحدها. لكن قرب سواحلها وجزرها وقواتها من مسارات السفن يمنحها قدرة كبيرة على تهديد الحركة أو تعطيلها.",
    },
    {
        "title": "مثال على الأثر: ميناء جبل علي",
        "body": "ناول ميناء جبل علي 15.5 مليون حاوية قياسية خلال 2024، بمتوسط يتجاوز 42 ألف حاوية يوميًا. تمر عبر مضيق هرمز السفن التي تربطه بالأسواق خارج الخليج، سواء كانت قادمة إلى الميناء أو مغادرة منه؛ لذلك قد يؤدي اضطراب المضيق إلى تأخير جزء كبير من حركته ورفع تكاليف الشحن.",
    },
    {
        "title": "والتعطيل لا يحتاج إلى إغلاق كامل",
        "body": "السفن لا تستخدم عرض المضيق كله، بل تمر ضمن ممرين ملاحيين محدودين—عرض كل منهما نحو 3.7 كيلومتر فقط. لذلك قد يكفي حادث أو تهديد لرفع التأمين والشحن، وإبطاء الحركة عبر البوابة كلها.",
    },
    {
        "title": "عرفوا قيمة هرمز قبل 500 سنة",
        "body": "كانت مملكة هرمز مركزًا تجاريًا بالغ الثراء، حتى قيل: «لو كان العالم خاتمًا، لكانت هرمز جوهرته.»",
        "punch": "تغيّرت السفن والبضائع، وبقيت الجغرافيا.",
    },
]


def font(size, *, bold=False):
    weight = "Bold" if bold else "Regular"
    return ImageFont.truetype(Path("fonts") / f"{FONT_FAMILY}-{weight}.ttf", size)


def _draw_centred(draw, lines, y, selected_font, gap, colour, centre):
    for line in lines:
        shaped, kwargs = ar(line)
        draw.text((centre, y), shaped, font=selected_font, fill=colour, anchor="ma", **kwargs)
        y += gap
    return y


def rebuild_frame(path, copy, footer=None):
    path = Path(path)
    image = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.rectangle(TEXT_REGION, fill=BACKGROUND)
    max_width = TEXT_REGION[2] - TEXT_REGION[0] - 40
    _, kwargs = ar("م")

    title_font = font(TITLE_SIZE, bold=True)
    title_lines = _wrap(draw, copy["title"], title_font, max_width, kwargs)
    title_gap = int(TITLE_SIZE * 1.24)
    body_top = TITLE_TOP + len(title_lines) * title_gap + 42

    punch = copy.get("punch", "")
    punch_font = font(40, bold=True)
    punch_lines = _wrap(draw, punch, punch_font, max_width, kwargs) if punch else []
    punch_gap = 54
    punch_block = len(punch_lines) * punch_gap + (30 if punch_lines else 0)

    body_size = BODY_START_SIZE
    while body_size >= 28:
        body_font = font(body_size)
        body_lines = _wrap(draw, copy["body"], body_font, max_width, kwargs)
        body_gap = int(body_size * 1.42)
        if body_top + len(body_lines) * body_gap + punch_block < TEXT_REGION[3]:
            break
        body_size -= 2
    else:
        raise ValueError(f"Text does not fit frame: {path.name}")

    centre = image.width // 2
    _draw_centred(draw, title_lines, TITLE_TOP, title_font, title_gap, TEXT_COLOUR, centre)
    y = _draw_centred(draw, body_lines, body_top, body_font, body_gap, TEXT_COLOUR, centre)
    if punch_lines:
        _draw_centred(draw, punch_lines, y + 30, punch_font, punch_gap, ACCENT, centre)

    # Riyadh format: the source band is reserved on every frame, but text
    # appears only once on the closing frame.
    draw.rectangle(FOOTER_REGION, fill=BACKGROUND)
    if footer:
        footer_size = 22
        footer_font = font(footer_size)
        shaped, footer_kwargs = ar(footer)
        while footer_size > 16 and draw.textlength(
                shaped, font=footer_font, **footer_kwargs) > 920:
            footer_size -= 1
            footer_font = font(footer_size)
        draw.text(
            (centre, 1870), shaped, font=footer_font, fill=MUTED,
            anchor="ma", **footer_kwargs,
        )

    image.save(path, "PNG", optimize=True)
    return path


def rebuild_deck(paths):
    paths = [Path(path) for path in paths]
    if len(paths) != 6:
        raise ValueError("Hormuz deck must contain exactly six frames")
    return [
        rebuild_frame(
            path,
            copy,
            footer=CONSOLIDATED_SOURCES if index == len(paths) else None,
        )
        for index, (path, copy) in enumerate(zip(paths, FRAMES), start=1)
    ]


def main():
    paths = [Path(f"2026-09-06-hormuz-final-v4-story-{index:02d}.png") for index in range(1, 7)]
    for path in rebuild_deck(paths):
        print("Frame 4 format applied:", path)


if __name__ == "__main__":
    main()
