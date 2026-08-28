#!/usr/bin/env python3
"""
نشر بطاقات جاهزة — ينشر قصة بُنيت من قبل، بلا إعادة بحث.

story_bot يبني ست لقطات ويرسلها لتيليجرام دون نشرها، لتُقرأ أولاً. هذا الملف
ينشر تلك اللقطات نفسها بعد مراجعتها: لا يستدعي النموذج، ولا يغيّر حرفاً، ولا
يبحث عن صورة. ما رأيته في تيليجرام هو ما يُنشر.

    python publish_cards.py                        # آخر قصة بُنيت
    CARDS_STAMP=2026-08-22-2pm python publish_cards.py
    CARDS_STAMP='سليمان' python publish_cards.py
    DRY_RUN=1 python publish_cards.py              # اعرض ما سيُنشر فقط
"""

import json
import os
import re
import shutil
import subprocess
import time
import unicodedata
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
FRAME_SECONDS = int(os.getenv("FRAME_SECONDS", "").strip() or "10")
TAIL_MARGIN = int(os.getenv("TAIL_MARGIN", "").strip() or "1")
# Bundle creates one Snapchat STORY post per frame. Firing all six at the same
# instant caused only one item to appear on Snapchat even though all uploads
# succeeded. Space successful posts so the platform can ingest them in order.
BUNDLE_FRAME_SPACING_SECONDS = int(
    os.getenv("BUNDLE_FRAME_SPACING_SECONDS", "").strip() or "15"
)

_STAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{1,2}(?:am|pm)$")
_FRAME_RE = re.compile(
    r"^(?P<stamp>\d{4}-\d{2}-\d{2}-\d{1,2}(?:am|pm))-story-"
    r"(?P<n>\d+)-[0-9a-f]+\.png$")


def _stamp_key(stamp):
    date, hour = stamp.rsplit("-", 1)
    h = int(hour[:-2]) % 12
    if hour.endswith("pm"):
        h += 12
    return (date, h)


def _normalise_selector(value):
    """Normalise Arabic/English title text without fuzzy guessing."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("ـ", "")
    text = text.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي"}))
    return " ".join(text.casefold().split())


def resolve_story_selector(selector=""):
    """Resolve a timestamp or a unique full/partial built-story title."""
    selector = (selector or "").strip()
    if not selector or _STAMP_RE.fullmatch(selector):
        return selector

    wanted = _normalise_selector(selector)
    matches = {}
    available = []

    for sidecar in Path(CARDS_DIR).glob("*-story.json"):
        stamp = sidecar.name[:-len("-story.json")]
        if not _STAMP_RE.fullmatch(stamp):
            continue
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
        except Exception:
            continue

        story = str(data.get("story") or "").strip()
        title = str(data.get("title") or "").strip()
        label = story or title or stamp
        available.append((stamp, label))

        haystacks = [_normalise_selector(story), _normalise_selector(title)]
        if any(wanted and wanted in text for text in haystacks if text):
            matches[stamp] = label

    if not matches:
        choices = ", ".join(
            f"{stamp} — {label}"
            for stamp, label in sorted(available, key=lambda x: _stamp_key(x[0]))
        )
        suffix = f" Available built stories: {choices}" if choices else ""
        raise SystemExit(f"no built story matches {selector!r}.{suffix}")

    if len(matches) > 1:
        choices = "\n".join(
            f"- {stamp} — {matches[stamp]}"
            for stamp in sorted(matches, key=_stamp_key)
        )
        raise SystemExit(
            f"multiple built stories match {selector!r}; use more of the title "
            f"or the timestamp:\n{choices}"
        )

    stamp, label = next(iter(matches.items()))
    print(f"    story selector {selector!r} -> {stamp} — {label}")
    return stamp


def _sidecar_frames(stamp):
    try:
        data = json.loads((Path(CARDS_DIR) / f"{stamp}-story.json")
                          .read_text(encoding="utf-8"))
    except Exception:
        return []
    frames = [Path(CARDS_DIR) / n for n in data.get("frames", [])]
    return frames if frames and all(f.exists() for f in frames) else []


def find_story(stamp=""):
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

    recorded = _sidecar_frames(chosen)
    if recorded:
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

    if chosen in dupes:
        raise SystemExit(
            f"{chosen}: more than one file per frame number — two runs share "
            "this stamp and no sidecar names the real set. Delete the stale "
            "set from cards/ (git log shows which commit owns which files).")

    frames = groups[chosen]
    order = sorted(frames)
    if order != list(range(1, len(order) + 1)):
        raise SystemExit(f"{chosen}: found frames {order}, expected "
                         f"1..{len(order)} — refusing to post a partial story")
    return chosen, [str(frames[n]) for n in order]


def load_caption(stamp, frame_count):
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
    """Compatibility fallback for non-Bundle providers."""
    durations = [FRAME_SECONDS] * len(frames)
    durations[-1] = max(2, int(FRAME_SECONDS - TAIL_MARGIN))
    total = sum(durations)
    if total > 60:
        raise SystemExit(f"frames add up to {total}s, over Snapchat's 60s "
                         "video limit — lower FRAME_SECONDS")
    listing = Path(out_path).with_suffix(".txt")
    lines = []
    for frame, dur in zip(frames, durations):
        for _ in range(int(dur)):
            lines.append(f"file '{Path(frame).resolve()}'")
            lines.append("duration 1")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")

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


def prepare_publish_media(frames, stamp):
    """Non-Bundle providers retain the single-video compatibility path."""
    media = list(frames)
    if len(media) > 1:
        return [frames_to_video(media,
                                Path(CARDS_DIR) / f"{stamp}-story.mp4")]
    return media


def publish_bundle_frames(caption, frames):
    """Publish each reviewed frame as its own Snapchat STORY post.

    Bundle's Snapchat API rejects more than one uploadId in a post, so a
    multi-frame story is sent as sequential one-frame STORY posts. Bundle's
    "publish now" path is asynchronous; spacing successful submissions avoids
    a burst where Snapchat only exposes the final item. Stop on first failure.
    """
    last_response = {"status": "error", "message": "no frames to publish"}
    published = 0
    for index, frame in enumerate(frames, start=1):
        print(f"    bundle frame {index}/{len(frames)}: {Path(frame).name}")
        last_response = post_story(caption, [], [frame])
        if not post_ok(last_response):
            if isinstance(last_response, dict):
                last_response["_published_frames"] = published
            return last_response
        published += 1
        if index < len(frames) and BUNDLE_FRAME_SPACING_SECONDS > 0:
            print(f"    waiting {BUNDLE_FRAME_SPACING_SECONDS}s before next frame")
            time.sleep(BUNDLE_FRAME_SPACING_SECONDS)
    if isinstance(last_response, dict):
        last_response["_published_frames"] = published
    return last_response


def _record_quota_posts(count):
    """Record exactly the provider posts that succeeded and commit once."""
    quota_file = None
    for _ in range(max(0, int(count))):
        quota_file = quota_bump()
    if quota_file is not None:
        commit_and_push(quota_file, f"quota {ksa_stamp()} +{count}")


def main():
    stamp, frames = find_story(resolve_story_selector(STAMP))
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

    if POST_PROVIDER == "bundle":
        response = publish_bundle_frames(caption, frames)
        published_count = int(response.get("_published_frames", 0)) if isinstance(response, dict) else 0
        _record_quota_posts(published_count)
    else:
        media = prepare_publish_media(frames, stamp)
        urls = (publish_many_via_github(media) if MEDIA_MODE == "github"
                else [upload_media(f) for f in media])
        response = post_story(caption, urls, media)
        published_count = 1 if post_ok(response) else 0
        _record_quota_posts(published_count)

    print("   ", response)

    if post_ok(response) and published_count == len(frames) if POST_PROVIDER == "bundle" else post_ok(response):
        notify_album(f"✅ نُشرت القصة — {stamp}", frames)
    else:
        notify(f"❌ {stamp} — لم تُنشر\n{describe_failure(response)}")


if __name__ == "__main__":
    main()
