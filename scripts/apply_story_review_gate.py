from pathlib import Path

ready = Path('ready_story_publish.py')
text = ready.read_text(encoding='utf-8')
if 'def review_delivery_allowed(' not in text:
    text = text.replace('import json\n', 'import hashlib\nimport json\n', 1)
    needle = '\ndef notify_final_candidate(\n'
    block = r'''

def review_delivery_allowed(*, status, approved):
    """Only a human-approved READY deck may leave the review boundary."""
    return str(status or "").strip().upper() == "READY" and bool(approved)


def build_review_manifest(story, revision, status, frames):
    """Freeze the exact rendered deck by recording each frame SHA-256."""
    frames = [Path(frame) for frame in (frames or [])]
    if len(frames) != 6:
        raise ValueError(f"review deck must contain exactly 6 frames, got {len(frames)}")
    rows = []
    for index, frame in enumerate(frames, start=1):
        if not frame.exists() or not frame.is_file():
            raise ValueError(f"review frame missing: {frame}")
        rows.append({
            "index": index,
            "path": frame.name,
            "sha256": hashlib.sha256(frame.read_bytes()).hexdigest(),
        })
    return {
        "schema_version": 1,
        "story": str(story),
        "revision": str(revision),
        "status": str(status or "").strip().upper(),
        "frame_count": len(rows),
        "deck_hash": sns.deck_hash(frames),
        "frames": rows,
    }


def write_review_manifest(story, revision, status, frames, path=None):
    """Write a review manifest beside the frozen PNGs for artifact upload."""
    manifest = build_review_manifest(story, revision, status, frames)
    path = Path(path or (nb.OUT_DIR / "story-review.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"    review artifact frozen: {path} ({manifest['deck_hash'][:12]})")
    return path


def verify_review_manifest(manifest, root):
    """Return exact frozen frame paths only when READY and hashes still match."""
    manifest = dict(manifest or {})
    if manifest.get("status") != "READY":
        raise ValueError("only READY review artifacts may be approved")
    rows = manifest.get("frames") or []
    if manifest.get("frame_count") != 6 or len(rows) != 6:
        raise ValueError("approved review artifact must contain exactly 6 frames")
    root = Path(root)
    frames = []
    for expected, row in enumerate(rows, start=1):
        if int(row.get("index", 0) or 0) != expected:
            raise ValueError("review frame order changed")
        rel = str(row.get("path") or "")
        if not rel or Path(rel).name != rel:
            raise ValueError("review frame path must be a frozen basename")
        frame = root / rel
        if not frame.exists() or not frame.is_file():
            raise ValueError(f"review frame missing: {rel}")
        digest = hashlib.sha256(frame.read_bytes()).hexdigest()
        if digest != row.get("sha256"):
            raise ValueError(f"review frame hash mismatch: {rel}")
        frames.append(frame)
    if sns.deck_hash(frames) != manifest.get("deck_hash"):
        raise ValueError("review deck hash mismatch")
    return frames
'''
    if needle not in text:
        raise SystemExit('ready_story_publish insertion point not found')
    text = text.replace(needle, block + needle, 1)

if 'def deliver_approved_review(' not in text:
    needle = '\ndef notify_final_candidate(\n'
    block = r'''

def deliver_approved_review(manifest_path, *, notify_fn=None):
    """Deliver the exact approved artifact; never render or regenerate here."""
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    frames = verify_review_manifest(manifest, manifest_path.parent)
    caption = f"[APPROVED] {manifest['story']}\nHuman-reviewed publication candidate"
    if notify_fn is not None:
        notify_fn(caption, frames, as_documents=True)
        return True
    return notify_final_candidate(
        manifest["story"],
        frames,
        "READY",
        manifest["revision"],
        digest=manifest.get("deck_hash"),
    )
'''
    if needle not in text:
        raise SystemExit('approved delivery insertion point not found')
    text = text.replace(needle, block + needle, 1)

ready.write_text(text, encoding='utf-8')

guarded = Path('guarded_story_publish.py')
gtext = guarded.read_text(encoding='utf-8')
old = '''    rsp.persist_editorial_state()\n    rsp.notify_final_candidate(story, frames, final_status, revision)\n\n    if rsp.nb.DRY_RUN or not rsp.nb.POST_ENABLED:\n'''
new = '''    rsp.persist_editorial_state()\n    manifest_path = rsp.write_review_manifest(\n        story, revision, final_status, frames\n    )\n    human_approved = (os.getenv("STORY_HUMAN_APPROVED") or "").strip() == "1"\n    if rsp.review_delivery_allowed(status=final_status, approved=human_approved):\n        rsp.notify_final_candidate(story, frames, final_status, revision)\n    else:\n        print(\n            f"REVIEW_GATE: {final_status} deck frozen for human review; "\n            f"Telegram untouched; artifact={manifest_path}"\n        )\n        if not human_approved:\n            print("REVIEW_REQUIRED — no Telegram or Snapchat delivery before approval")\n            return\n\n    if rsp.nb.DRY_RUN or not rsp.nb.POST_ENABLED:\n'''
if old in gtext:
    gtext = gtext.replace(old, new, 1)
elif 'REVIEW_REQUIRED — no Telegram or Snapchat delivery before approval' not in gtext:
    raise SystemExit('guarded_story_publish replacement point not found')
guarded.write_text(gtext, encoding='utf-8')
