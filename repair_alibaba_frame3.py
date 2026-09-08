#!/usr/bin/env python3
"""Repair Alibaba frame 3 with the reviewed 1995 Jack Ma photograph."""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("THEME", "light")
os.environ.setdefault("FONT_FAMILY", "Almarai")
os.environ.setdefault("STORY_FORMAT", "riyadh-story-v1")
os.environ.setdefault("BRAND", "ملخص تنفيذي - قصة")

import ready_story_publish as rsp
import story_bot
from review_visual_gate import require_photo_coverage


TITLE = "أول لقاء مع الإنترنت"
BODY = (
    "ثم تغيّر كل شيء. سنة 1995 زار Jack Ma الولايات المتحدة "
    "واستخدم الإنترنت لأول مرة في حياته. كتب كلمة beer في محرك البحث، "
    "فظهرت نتائج من أمريكا وألمانيا ولم تظهر أي نتيجة من الصين."
)


def repair_frame(frame_path, photo_path):
    frame_path = Path(frame_path)
    photo_path = Path(photo_path)
    story_bot.render_frame(
        frame_path,
        "ملخص تنفيذي - قصة",
        "3 / 6",
        TITLE,
        60,
        sub=BODY,
        photo=photo_path,
    )
    return frame_path


def repair_deck(root, photo_path):
    root = Path(root)
    manifest_path = root / "story-review.json"
    old = json.loads(manifest_path.read_text(encoding="utf-8"))
    frames = [root / row["path"] for row in old["frames"]]
    repair_frame(frames[2], photo_path)
    require_photo_coverage(frames, minimum=6)
    manifest = rsp.build_review_manifest(
        old["story"],
        f"{old['revision']}-frame3-photo",
        "READY",
        frames,
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Alibaba repaired deck verified: 6/6 photos ({manifest['deck_hash']})")
    return manifest_path


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: repair_alibaba_frame3.py ARTIFACT_OUT PHOTO")
    repair_deck(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
