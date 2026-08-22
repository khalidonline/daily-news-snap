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
import subprocess
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
# bundle.social allows ONE upload per Snapchat post, so a six-frame story goes
# up as a single video — which also finally gives each frame a dwell time the
# viewer can actually read in, instead of Snapchat's own image timing.
# 8s x 6 frames = 48s, safely inside Snapchat's 60s video limit; 10 would
# land exactly on the limit, and exactly-on-the-limit is where uploads fail.
FRAME_SECONDS = int(os.getenv("FRAME_SECONDS", "").strip() or "8")

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


def frames_to_video(frames, out_path):
    """One MP4 from the frames, FRAME_SECONDS each. Returns the path.

    Uses the concat demuxer rather than one -loop input per frame: the frame
    count varies, and a malformed filter graph fails with an error message
    that says nothing about which frame broke it.
    """
    total = len(frames) * FRAME_SECONDS
    if total > 60:
        raise SystemExit(f"{len(frames)} frames x {FRAME_SECONDS}s = {total}s, "
                         "over Snapchat's 60s video limit — lower FRAME_SECONDS")
    listing = Path(out_path).with_suffix(".txt")
    lines = []
    for frame in frames:
        lines.append(f"file '{Path(frame).resolve()}'")
        lines.append(f"duration {FRAME_SECONDS}")
    # Deliberately NO trailing repeat of the last file. The widely-copied
    # concat recipe repeats it "so the last duration isn't dropped" — measured
    # on ffmpeg 7, the repeat itself adds a full extra cycle (56s instead of
    # 48), with or without its own duration line. Modern ffmpeg honours the
    # last duration as written; the listing above is complete.
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
           "-i", str(listing),
           "-vf", "fps=30,format=yuv420p,scale=1080:1920",
           "-c:v", "libx264", "-preset", "medium", "-movflags", "+faststart",
           str(out_path)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        raise SystemExit("ffmpeg not found — it is preinstalled on GitHub "
                         "runners; install it to publish from elsewhere")
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"ffmpeg failed: {exc.stderr[-400:]}")
    finally:
        listing.unlink(missing_ok=True)
    size = Path(out_path).stat().st_size
    print(f"    video: {len(frames)} frames x {FRAME_SECONDS}s = {total}s, "
          f"{size:,} bytes")
    return str(out_path)


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

    # One upload per Snapchat post is all bundle.social accepts — six frames
    # posted as six images would be six posts against the plan. As one video
    # it is a single post, and each frame holds for FRAME_SECONDS.
    media = frames
    if len(frames) > 1:
        media = [frames_to_video(frames, Path(CARDS_DIR) / f"{stamp}-story.mp4")]

    urls = []
    if POST_PROVIDER != "bundle":
        urls = (publish_many_via_github(media) if MEDIA_MODE == "github"
                else [upload_media(f) for f in media])

    response = post_story(caption, urls, media)
    print("   ", response)

    if post_ok(response):
        commit_and_push(quota_bump(), f"quota {ksa_stamp()}")
        notify_album(f"✅ نُشرت القصة — {stamp}", frames)
    else:
        notify(f"❌ {stamp} — لم تُنشر\n{describe_failure(response)}")


if __name__ == "__main__":
    main()
