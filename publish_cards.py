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
import shutil
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
# up as a single video. Snapchat then splits a long story video into
# 10-SECOND snaps — at 8s per frame those segments straddled two frames each,
# and a viewer tapping through snaps jumped clean over frame 5 of the first
# published story. 10s per frame makes each snap exactly one frame, which is
# also the dwell time asked for in the first place. 6 frames = 60s, which is
# Snapchat's ceiling, hence the <= below rather than <.
FRAME_SECONDS = int(os.getenv("FRAME_SECONDS", "").strip() or "10")
# A 60.00s video sits exactly on Snapchat's ceiling, and Snapchat shaves the
# tail — the republished Aramco story lost the end of frame 6 even with clean
# 10s alignment. The last frame surrenders this margin so the video ends
# inside the limit; every earlier frame keeps its full snap.
TAIL_MARGIN = int(os.getenv("TAIL_MARGIN", "").strip() or "1")

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


def _sidecar_frames(stamp):
    """The exact frame files the run recorded, if its sidecar names them."""
    try:
        data = json.loads((Path(CARDS_DIR) / f"{stamp}-story.json")
                          .read_text(encoding="utf-8"))
    except Exception:
        return []
    frames = [Path(CARDS_DIR) / n for n in data.get("frames", [])]
    return frames if frames and all(f.exists() for f in frames) else []


def find_story(stamp=""):
    """The frames of one story, in order. Returns (stamp, [paths])."""
    groups = {}
    dupes = set()
    for path in Path(CARDS_DIR).glob("*-story-*.png"):
        match = _FRAME_RE.match(path.name)
        if match:
            st, n = match.group("stamp"), int(match.group("n"))
            if n in groups.get(st, {}):
                dupes.add(st)
            groups.setdefault(st, {})[n] = path
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

    # The sidecar's own list wins outright: it is the one record of which
    # files belong to one run.
    recorded = _sidecar_frames(chosen)
    if recorded:
        # frames post by EXPLICIT index, and the set must be exactly 1..N —
        # a gap or duplicate means a mixed or torn run; refuse rather than
        # ship a deck with a hole in it
        nums = []
        for f in recorded:
            m = _FRAME_RE.match(f.name)
            if m:
                nums.append(int(m.group("n")))
        if sorted(nums) != list(range(1, len(recorded) + 1)):
            raise SystemExit(f"{chosen}: sidecar frames are {sorted(nums)}, "
                             f"expected 1..{len(recorded)} — refusing")
        recorded = [f for _, f in sorted(zip(nums, recorded))]
        return chosen, [str(f) for f in recorded]

    # Two runs in the same KSA hour leave two files per frame number, and
    # picking by glob order would stitch a story out of both — the very first
    # publish attempt did exactly that. Without a sidecar to arbitrate,
    # refusing is the only honest answer.
    if chosen in dupes:
        raise SystemExit(
            f"{chosen}: more than one file per frame number — two runs share "
            "this stamp and no sidecar names the real set. Delete the stale "
            "set from cards/ (git log shows which commit owns which files).")

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
    durations = [FRAME_SECONDS] * len(frames)
    durations[-1] = max(2, int(FRAME_SECONDS - TAIL_MARGIN))
    total = sum(durations)
    if total > 60:
        raise SystemExit(f"frames add up to {total}s, over Snapchat's 60s "
                         "video limit — lower FRAME_SECONDS")
    listing = Path(out_path).with_suffix(".txt")
    # Every frame becomes repeated ONE-SECOND entries. Measured on ffmpeg 7,
    # the concat demuxer holds the final frame for the PREVIOUS entry's
    # duration and ignores its own ([10,10,9] plays 30s, [8,8,4] plays 24s) —
    # equal durations masked this until the last frame needed a shorter hold.
    # With every entry at 1s the quirk has nothing to distort. Durations must
    # therefore stay whole seconds.
    lines = []
    for frame, dur in zip(frames, durations):
        for _ in range(int(dur)):
            lines.append(f"file '{Path(frame).resolve()}'")
            lines.append("duration 1")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # GitHub's runner image does NOT ship ffmpeg on PATH — the first live run
    # proved it. imageio-ffmpeg carries a static binary and installs from a
    # wheel in seconds, so it is the fallback everywhere.
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            raise SystemExit("no ffmpeg on PATH and imageio-ffmpeg not "
                             "installed — pip install imageio-ffmpeg")
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
           "-i", str(listing),
           "-vf", "fps=30,format=yuv420p,scale=1080:1920",
           "-c:v", "libx264", "-preset", "medium", "-movflags", "+faststart",
           str(out_path)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"ffmpeg failed: {exc.stderr[-400:]}")
    finally:
        listing.unlink(missing_ok=True)
    size = Path(out_path).stat().st_size
    print(f"    video: {len(frames)} frames, {total:g}s "
          f"(last frame {durations[-1]:g}s), {size:,} bytes")
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
