#!/usr/bin/env python3
"""Rebuild the approved Hormuz deck on the clean Riyadh story template."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

os.environ.setdefault("THEME", "light")
os.environ.setdefault("FONT_FAMILY", "Almarai")
os.environ.setdefault("STORY_FORMAT", "riyadh-story-v1")
os.environ.setdefault("BRAND", "ملخص تنفيذي - قصة")

import story_bot
from story_format import MARGIN, PHOTO_ASPECT_HEIGHT, PHOTO_TOP


PHOTO_HEIGHT = int((story_bot.W - 2 * MARGIN) * PHOTO_ASPECT_HEIGHT)
CONSOLIDATED_SOURCES = (
    "المصدر: المنظمة البحرية الدولية، وكالة الطاقة الدولية، "
    "موانئ دبي العالمية"
)

FRAMES = [
    {"title": "هل مرّت أغراض بيتك من هنا؟", "body": "هاتفك، سيارتك، ملابسك، أغراض المنزل والطعام المستورد... كثير من السلع الداخلة إلى موانئ الخليج تعبر أولاً مضيق هرمز."},
    {"title": "لأن الخليج له بوابة بحرية واحدة", "body": "أي سفينة قادمة من المحيط إلى موانئ الإمارات وقطر والبحرين والكويت، أو خارجة منها إلى العالم، تمر عبر هرمز. لا يوجد مدخل بحري آخر إلى الخليج."},
    {"title": "فهل تسيطر إيران على هذه البوابة؟", "body": "لا. المضيق يقع بين إيران وعُمان، ولا تملكه إيران وحدها. لكن قرب سواحلها وجزرها وقواتها من مسارات السفن يمنحها قدرة كبيرة على تهديد الحركة أو تعطيلها."},
    {"title": "مثال على الأثر: ميناء جبل علي", "body": "ناول ميناء جبل علي 15.5 مليون حاوية قياسية خلال 2024، بمتوسط يتجاوز 42 ألف حاوية يوميًا. تمر عبر مضيق هرمز السفن التي تربطه بالأسواق خارج الخليج، سواء كانت قادمة إلى الميناء أو مغادرة منه؛ لذلك قد يؤدي اضطراب المضيق إلى تأخير جزء كبير من حركته ورفع تكاليف الشحن."},
    {"title": "والتعطيل لا يحتاج إلى إغلاق كامل", "body": "السفن لا تستخدم عرض المضيق كله، بل تمر ضمن ممرين ملاحيين محدودين—عرض كل منهما نحو 3.7 كيلومتر فقط. لذلك قد يكفي حادث أو تهديد لرفع التأمين والشحن، وإبطاء الحركة عبر البوابة كلها."},
    {"title": "عرفوا قيمة هرمز قبل 500 سنة", "body": "كانت مملكة هرمز مركزًا تجاريًا بالغ الثراء، حتى قيل: «لو كان العالم خاتمًا، لكانت هرمز جوهرته.»", "punch": "تغيّرت السفن والبضائع، وبقيت الجغرافيا."},
]


def save_verified_png(image, path):
    """Write a complete PNG before replacing a reviewed frame."""
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        image.save(temporary, "PNG")
        with Image.open(temporary) as rendered:
            rendered.verify()
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def extract_approved_photo(frame_path, photo_path):
    """Keep the approved photo crop, including its existing photo seal."""
    with Image.open(frame_path) as frame:
        photo = frame.convert("RGB").crop(
            (MARGIN, PHOTO_TOP, story_bot.W - MARGIN, PHOTO_TOP + PHOTO_HEIGHT)
        )
    save_verified_png(photo, photo_path)
    return photo_path


def rebuild_frame(path, copy, index, footer=None, photo_path=None):
    """Rebuild one complete frame; no legacy canvas pixels are retained."""
    path = Path(path)
    if photo_path is None:
        photo_path = path.with_name(f".{path.stem}-photo.png")
        remove_photo = True
        extract_approved_photo(path, photo_path)
    else:
        remove_photo = False

    original_seal_photo = story_bot.seal_photo
    story_bot.seal_photo = lambda *_args, **_kwargs: None
    try:
        story_bot.render_frame(
            path,
            "ملخص تنفيذي - قصة",
            f"{index} / 6",
            copy["title"],
            60,
            sub=copy["body"],
            photo=photo_path,
            footer=footer,
            punch=copy.get("punch"),
        )
    finally:
        story_bot.seal_photo = original_seal_photo
        if remove_photo:
            Path(photo_path).unlink(missing_ok=True)

    with Image.open(path) as rendered:
        rendered.verify()
    return path


def rebuild_deck(paths):
    paths = [Path(path) for path in paths]
    if len(paths) != 6:
        raise ValueError("Hormuz deck must contain exactly six frames")
    with TemporaryDirectory() as directory:
        photo_paths = []
        for index, path in enumerate(paths, start=1):
            photo_path = Path(directory) / f"photo-{index:02d}.png"
            photo_paths.append(extract_approved_photo(path, photo_path))
        return [
            rebuild_frame(
                path, copy, index,
                footer=CONSOLIDATED_SOURCES if index == 6 else None,
                photo_path=photo_paths[index - 1],
            )
            for index, (path, copy) in enumerate(zip(paths, FRAMES), start=1)
        ]


def main():
    paths = [Path(f"2026-09-06-hormuz-final-v4-story-{index:02d}.png") for index in range(1, 7)]
    for path in rebuild_deck(paths):
        print("Clean Riyadh frame rebuilt:", path)


if __name__ == "__main__":
    main()
