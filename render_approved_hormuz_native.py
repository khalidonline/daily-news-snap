#!/usr/bin/env python3
"""Rebuild the approved Hormuz deck with the native Riyadh Story renderer."""

from pathlib import Path
import argparse

from PIL import Image

import story_bot


FRAMES = [
    {
        "title": "هل مرّت أغراض بيتك من هنا؟",
        "body": "هاتفك، سيارتك، ملابسك، أغراض المنزل والطعام المستورد... كثير من السلع الداخلة إلى موانئ الخليج تعبر أولاً مضيق هرمز.",
        "footer": "الصورة توضيحية",
    },
    {
        "title": "لأن الخليج له بوابة بحرية واحدة",
        "body": "أي سفينة قادمة من المحيط إلى موانئ الإمارات وقطر والبحرين والكويت، أو خارجة منها إلى العالم، تمر عبر هرمز. لا يوجد مدخل بحري آخر إلى الخليج.",
        "footer": "المصدر: الموسوعة البريطانية",
    },
    {
        "title": "فهل تسيطر إيران على هذه البوابة؟",
        "body": "لا. المضيق يقع بين إيران وعُمان، ولا تملكه إيران وحدها. لكن قرب سواحلها وجزرها وقواتها من مسارات السفن يمنحها قدرة كبيرة على تهديد الحركة أو تعطيلها.",
        "footer": "المصدر: الموسوعة البريطانية",
    },
    {
        "title": "مثال على الأثر: ميناء جبل علي",
        "body": "ناول ميناء جبل علي 15.5 مليون حاوية قياسية خلال 2024، بمتوسط يتجاوز 42 ألف حاوية يوميًا. تمر عبر مضيق هرمز السفن التي تربطه بالأسواق خارج الخليج، سواء كانت قادمة إلى الميناء أو مغادرة منه؛ لذلك قد يؤدي اضطراب المضيق إلى تأخير جزء كبير من حركته ورفع تكاليف الشحن.",
        "footer": "المصدر: موانئ دبي العالمية — 2024",
    },
    {
        "title": "والتعطيل لا يحتاج إلى إغلاق كامل",
        "body": "السفن لا تستخدم عرض المضيق كله، بل تمر ضمن ممرين ملاحيين محدودين—عرض كل منهما نحو 3.7 كيلومتر فقط. لذلك قد يكفي حادث أو تهديد لرفع التأمين والشحن، وإبطاء الحركة عبر البوابة كلها.",
        "footer": "المصدر: الموسوعة البريطانية",
    },
    {
        "title": "عرفوا قيمة هرمز قبل 500 سنة",
        "body": "كانت مملكة هرمز مركزًا تجاريًا بالغ الثراء، حتى قيل: «لو كان العالم خاتمًا، لكانت هرمز جوهرته.»",
        "punch": "تغيّرت السفن والبضائع، وبقيت الجغرافيا.",
        "footer": "المصدر: الموسوعة البريطانية",
    },
]

PHOTO_BOX = (96, 420, 984, 1059)
KICKER = "ملخص تنفيذي - قصة"\n# Delivery revision: exact native Riyadh card format.


def render_deck(source_frames, output_dir):
    source_frames = [Path(path) for path in source_frames]
    if len(source_frames) != 6:
        raise ValueError("The approved Hormuz deck must contain exactly six frames")
    if not all(path.is_file() for path in source_frames):
        raise FileNotFoundError("One or more approved source frames are missing")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    photo_dir = output_dir / ".hormuz-native-photos"
    photo_dir.mkdir(exist_ok=True)

    photos = []
    for index, source in enumerate(source_frames, start=1):
        photo = photo_dir / f"photo-{index:02d}.png"
        with Image.open(source) as image:
            image.convert("RGB").crop(PHOTO_BOX).save(photo, "PNG")
        photos.append(photo)

    outputs = []
    original_seal_photo = story_bot.seal_photo
    story_bot.seal_photo = lambda *_args, **_kwargs: None
    try:
        for index, (copy, photo) in enumerate(zip(FRAMES, photos), start=1):
            output = output_dir / f"2026-09-06-hormuz-native-story-{index:02d}.png"
            story_bot.render_frame(
                output,
                KICKER,
                f"{index} / 6",
                copy["title"],
                64,
                sub=copy["body"],
                photo=photo,
                footer=copy["footer"],
                punch=copy.get("punch"),
            )
            outputs.append(output)
    finally:
        story_bot.seal_photo = original_seal_photo

    return outputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    parser.add_argument(
        "sources",
        nargs="*",
        default=[f"2026-09-06-hormuz-final-v4-story-{i:02d}.png" for i in range(1, 7)],
    )
    args = parser.parse_args()
    for path in render_deck(args.sources, args.output_dir):
        print(path)


if __name__ == "__main__":
    main()
