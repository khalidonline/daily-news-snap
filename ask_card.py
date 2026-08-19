#!/usr/bin/env python3
"""
بطاقة سؤال المتابعين — تسأل الجمهور عن المواضيع التي يريدونها.

    THEME=light python ask_card.py
    THEME=light python ask_card.py "وش الشي اللي يحيّرك في فلوسك؟"

تُنتج البطاقة في out/ وترسلها لتيليجرام إن كانت مفاتيحه مضبوطة.
الردود تصل كرسائل خاصة على سناب — انسخ ما يعجبك إلى requests.txt.
"""

import os
import random
import sys
from pathlib import Path

from news_bot import (render_story, notify, commit_and_push,
                      OUT_DIR, CARDS_DIR, ksa_stamp)

# صيغ مختلفة — السؤال المحدد يجلب ردوداً أكثر من السؤال المفتوح
PROMPTS = [
    {
        "title": "وش الموضوع اللي تبينا نفكّكه لك؟",
        "body": "كل يوم ننشر موجزاً عن الفلوس والأسعار والتقنية. "
                "لكن الأفضل أن يكون الموضوع من عندك أنت.",
        "punch": "رد على هذا السناب بالموضوع اللي يحيّرك، ونشتغل عليه.",
    },
    {
        "title": "أي رقم تبي نتحقق منه؟",
        "body": "سعر سيارة، إيجار شقة، فاتورة، راتب في مجال معيّن — "
                "أي رقم سمعته وما تدري إن كان صحيحاً.",
        "punch": "رد بالرقم أو السؤال، ونرجع لك بالمصدر الرسمي.",
    },
    {
        "title": "أغلى في السعودية أو برا؟",
        "body": "ننشر مقارنات أسعار بين السعودية وأسواق ثانية: "
                "سيارات، عقار، أجهزة، علامات فاخرة.",
        "punch": "رد بالشي اللي تبي نقارنه، والأكثر طلباً ننشره أول.",
    },
    {
        "title": "وش اللي تحتاج تفهمه قبل نهاية الشهر؟",
        "body": "قرار مالي، عقد، نظام عمل، أو شي قريت عنه وما اتضح لك.",
        "punch": "رد بسؤالك — نجاوب عليه بالأرقام والمصدر، لا بالرأي.",
    },
]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    typed = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    if typed:                                   # a question typed by hand
        card = {"title": typed,
                "body": "رد على هذا السناب بموضوعك أو سؤالك.",
                "punch": "الأكثر طلباً ننشره أول.",
                "sources": []}
    else:
        card = dict(random.choice(PROMPTS), sources=[])

    stamp = ksa_stamp()
    path = OUT_DIR / f"{stamp}-ask.png"
    render_story(card, path, None, None)

    print(f"    {card['title']}")

    # in Actions, commit the card so there's a link — but don't touch
    # latest.png, which belongs to the news and topic cards
    repo = os.getenv("GITHUB_REPOSITORY", "")
    if repo:
        import shutil
        Path(CARDS_DIR).mkdir(exist_ok=True)
        dest = Path(CARDS_DIR) / f"{stamp}-ask.png"
        shutil.copyfile(path, dest)
        commit_and_push(dest, f"ask card {stamp}")
        branch = os.getenv("GITHUB_REF_NAME", "main")
        print(f"    card: https://raw.githubusercontent.com/"
              f"{repo}/{branch}/{CARDS_DIR}/{dest.name}")
    else:
        print(f"    card: {Path(path).resolve()}")

    notify(f"❓ {stamp} — بطاقة سؤال المتابعين\n{card['title']}", str(path))


if __name__ == "__main__":
    main()
