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
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

try:
    from news_bot import (
        CARDS_DIR, DRY_RUN, POST_PROVIDER, MEDIA_MODE,
        BUNDLE_API_KEY, BUNDLE_BASE, BUNDLE_HEADERS,
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
BUNDLE_STATUS_TIMEOUT = int(os.getenv("BUNDLE_STATUS_TIMEOUT", "").strip() or "150")
BUNDLE_STATUS_POLL = int(os.getenv("BUNDLE_STATUS_POLL", "").strip() or "5")

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


def _ffmpeg_exe():
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise SystemExit("no ffmpeg on PATH and imageio-ffmpeg not installed — "
                         "pip install imageio-ffmpeg")


def _frame_durations(frames):
    if not frames:
        return []
    durations = [FRAME_SECONDS] * len(frames)
    durations[-1] = max(2, int(FRAME_SECONDS - TAIL_MARGIN))
    return durations


def frames_to_video(frames, out_path):
    """Create one Snapchat-compatible MP4 containing every reviewed card."""
    durations = _frame_durations(frames)
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

    ffmpeg = _ffmpeg_exe()
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


def _image_distance(left, right):
    diff = ImageChops.difference(left, right)
    means = ImageStat.Stat(diff).mean
    return sum(means) / len(means)


def validate_story_video(video_path, frames):
    """Decode the MP4 and prove every source card is present in order.

    One sample is extracted from the middle of each card's hold. The decoded
    sample must be closest to the corresponding source card (not any other
    card) and must stay within a conservative compression-distance threshold.
    Refuse publication if any segment cannot be proven.
    """
    if not frames:
        raise SystemExit("cannot validate a story video with no source frames")

    durations = _frame_durations(frames)
    ffmpeg = _ffmpeg_exe()
    thumb_size = (270, 480)
    sources = []
    for frame in frames:
        with Image.open(frame) as img:
            sources.append(img.convert("RGB").resize(thumb_size))

    elapsed = 0.0
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for index, (frame, dur) in enumerate(zip(frames, durations)):
            sample_at = elapsed + (float(dur) / 2.0)
            sample = root / f"sample-{index + 1}.png"
            cmd = [ffmpeg, "-y", "-loglevel", "error", "-ss", f"{sample_at:.3f}",
                   "-i", str(video_path), "-frames:v", "1", str(sample)]
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as exc:
                raise SystemExit(
                    f"story video validation failed at frame {index + 1}: "
                    f"{exc.stderr[-300:]}"
                )
            if not sample.exists():
                raise SystemExit(
                    f"story video validation failed: no decoded sample for frame {index + 1}"
                )
            with Image.open(sample) as decoded:
                decoded_thumb = decoded.convert("RGB").resize(thumb_size)
            distances = [_image_distance(decoded_thumb, source) for source in sources]
            closest = min(range(len(distances)), key=distances.__getitem__)
            expected_distance = distances[index]
            if closest != index or expected_distance > 18.0:
                raise SystemExit(
                    f"story video validation failed at segment {index + 1}: "
                    f"closest source is frame {closest + 1}, distance={expected_distance:.2f}"
                )
            elapsed += float(dur)

    print(f"    video validation: {len(frames)}/{len(frames)} source frames confirmed in order")
    return True


def wait_for_bundle_post(response, timeout=None, poll=None):
    """Wait until Bundle confirms POSTED; SCHEDULED alone is not success."""
    if not isinstance(response, dict):
        return {"status": "error", "message": "invalid Bundle post response"}
    post_id = str(response.get("id") or "").strip()
    if not post_id:
        return {"status": "error", "message": "Bundle returned no post id"}

    timeout = BUNDLE_STATUS_TIMEOUT if timeout is None else int(timeout)
    poll = BUNDLE_STATUS_POLL if poll is None else int(poll)
    deadline = time.monotonic() + max(1, timeout)
    last = response
    seen_status = None

    while True:
        status = str(last.get("status") or "").upper()
        if status != seen_status:
            print(f"    bundle delivery status: {status or 'UNKNOWN'}")
            seen_status = status
        if status == "POSTED":
            return last
        if status in ("ERROR", "DELETED"):
            return last
        if time.monotonic() >= deadline:
            return {
                "status": "error",
                "message": f"Bundle post {post_id} did not reach POSTED within {timeout}s",
                "last": last,
            }

        time.sleep(max(1, poll))
        req = urllib.request.Request(
            f"{BUNDLE_BASE.rstrip('/')}/post/{post_id}",
            headers={**BUNDLE_HEADERS, "x-api-key": BUNDLE_API_KEY,
                     "Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                last = json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()[:300]
            if exc.code != 429 and 400 <= exc.code < 500:
                return {"status": "error", "code": exc.code, "message": body}
            print(f"  ! Bundle status check {exc.code}: {body}")
        except Exception as exc:
            print(f"  ! Bundle status check failed: {exc}")


def prepare_publish_media(frames, stamp):
    """Non-Bundle providers retain the single-video compatibility path."""
    media = list(frames)
    if len(media) > 1:
        return [frames_to_video(media,
                                Path(CARDS_DIR) / f"{stamp}-story.mp4")]
    return media


def publish_bundle_story(caption, frames, stamp):
    """Publish one verified MP4 because Bundle Snapchat Stories accept one media item."""
    video = frames_to_video(frames, Path(CARDS_DIR) / f"{stamp}-story.mp4")
    validate_story_video(video, frames)
    scheduled = post_story(caption, [], [video])
    if not post_ok(scheduled):
        return scheduled
    return wait_for_bundle_post(scheduled)


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
        response = publish_bundle_story(caption, frames, stamp)
        success = (isinstance(response, dict)
                   and str(response.get("status") or "").upper() == "POSTED"
                   and post_ok(response))
        _record_quota_posts(1 if success else 0)
    else:
        media = prepare_publish_media(frames, stamp)
        urls = (publish_many_via_github(media) if MEDIA_MODE == "github"
                else [upload_media(f) for f in media])
        response = post_story(caption, urls, media)
        success = post_ok(response)
        _record_quota_posts(1 if success else 0)

    print("   ", response)

    if success:
        notify_album(f"✅ نُشرت القصة — {stamp}", frames)
    else:
        notify(f"❌ {stamp} — لم تُنشر\n{describe_failure(response)}")


if __name__ == "__main__":
    main()
