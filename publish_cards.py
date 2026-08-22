#!/usr/bin/env python3
"""
نشر بطاقات جاهزة — ينشر قصة بُنيت من قبل، بلا إعادة بحث.

story_bot يبني ست لقطات ويرسلها لتيليجرام دون نشرها، لتُقرأ أولاً. هذا الملف
ينشر تلك اللقطات نفسها بعد مراجعتها: لا يستدعي النموذج، ولا يغيّر حرفاً، ولا
يبحث عن صورة. ما رأيته في تيليجرام هو ما يُنشر.

    python publish_cards.py                        # آخر قصة بُنيت
    CARDS_STAMP=2026-08-22-2pm python publish_cards.py
    DRY_RUN=1 python publish_cards.py              # اعرض ما سيُنشر فقط
"""

import json
import os
import re
from pathlib import Path

try:
    from news_bot import (
        CARDS_DIR, DRY_RUN, POST_PROVIDER, MEDIA_MODE,
        post_story, post_ok, describe_failure,
        quota_ok, quota_bump, commit_and_push,
        notify, notify_album, ksa_stamp, deliver_unposted,
        publish_many_via_github, upload_media,
    )
except ImportError as exc:
    raise SystemExit(
        f"news_bot.py is missing something publish_cards needs ({exc}).\n"
        "The two files must be uploaded together."
    )

STAMP = os.getenv("CARDS_STAMP", "").strip()
CAPTION = os.getenv("CAPTION", "").strip()

# 2026-08-22-2pm-story-3-fe471e27.png
_FRAME_RE = re.compile(
    r"^(?P<stamp>\d{4}-\d{2}-\d{2}-\d{1,2}(?:am|pm))-story-"
    r"(?P<n>\d+)-[0-9a-f]+\.png$")


def _stamp_key(stamp):
    """Sort chronologically. Lexical order puts 10am after 2pm — the hour is
    written for people, not for sorting."""
    date, hour = stamp.rsplit("-", 1)
    h = int(hour[:-2]) % 12
    if hour.endswith("pm"):
        h += 12
    return (date, h)


def find_story(stamp=""):
    """The frames of one story, in order. Returns (stamp, [paths])."""
    groups = {}
    for path in Path(CARDS_DIR).glob("*-story-*.png"):
        match = _FRAME_RE.match(path.name)
        if match:
            groups.setdefault(match.group("stamp"), {})[
                int(match.group("n"))] = path
    if not groups:
        return "", []

    available = sorted(groups, key=_stamp_key)
    if stamp:
        if stamp not in groups:
            raise SystemExit(f"no story cards stamped {stamp!r}. "
                             f"available: {', '.join(available)}")
        chosen = stamp
    else:
        chosen = available[-1]

    frames = groups[chosen]
    order = sorted(frames)
    # a story with a hole in it is worse than no story
    if order != list(range(1, len(order) + 1)):
        raise SystemExit(f"{chosen}: found frames {order}, expected "
                         f"1..{len(order)} — refusing to post a partial story")
    return chosen, [str(frames[n]) for n in order]


def load_caption(stamp, frame_count):
    """The caption story_bot wrote beside the cards, or a plain fallback.

    Older stories were built before the sidecar existed, so this has to work
    without one rather than refuse to publish them.
    """
    if CAPTION:
        return CAPTION
    sidecar = Path(CARDS_DIR) / f"{stamp}-story.json"
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except Exception:
        print(f"    no caption saved for {stamp} — using a plain one")
        return f"قصة في {frame_count} لقطات"
    return (data.get("caption") or data.get("title")
            or f"قصة في {frame_count} لقطات")


def main():
    stamp, frames = find_story(STAMP)
    if not frames:
        raise SystemExit(f"no story cards found in {CARDS_DIR}/")

    caption = load_caption(stamp, len(frames))
    print(f"publishing {len(frames)} frames from {stamp}")
    for path in frames:
        print(f"    {Path(path).name}")
    print(f"    caption: {caption}")

    if DRY_RUN:
        print("DRY_RUN — nothing posted")
        return

    if not quota_ok():
        deliver_unposted(frames, caption)
        return

    # bundle.social uploads the files itself; the others need public URLs,
    # and these cards are already committed so they already have them
    urls = []
    if POST_PROVIDER != "bundle":
        urls = (publish_many_via_github(frames) if MEDIA_MODE == "github"
                else [upload_media(f) for f in frames])

    response = post_story(caption, urls, frames)
    print("   ", response)

    if post_ok(response):
        commit_and_push(quota_bump(), f"quota {ksa_stamp()}")
        notify_album(f"✅ نُشرت القصة — {stamp}", frames)
    else:
        notify(f"❌ {stamp} — لم تُنشر\n{describe_failure(response)}")


if __name__ == "__main__":
    main()
