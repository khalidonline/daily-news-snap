#!/usr/bin/env python3
"""Download owner-reviewed repair assets and register them in the runtime library.

The manifest is deliberately explicit: URL, filename, story, tags, credit and
relevance verdict. A download must decode as an image and must not duplicate an
existing local image before it is registered.
"""
from __future__ import annotations
import io
import json
import hashlib
import urllib.request
from pathlib import Path

from PIL import Image
import image_precheck as ipc

MANIFEST = Path("repair_assets.json")
IMAGES = Path("images")
INDEX = IMAGES / "images.txt"
LEDGER = IMAGES / "relevance.json"
UA = "Mozilla/5.0 (compatible; story-visual-repair/1.0)"


def existing_hashes(exclude=None):
    exact, perceptual = {}, []
    for p in IMAGES.glob("*.*"):
        if p.is_dir() or p == exclude or p.name in {"images.txt", "relevance.json"}:
            continue
        try:
            raw = p.read_bytes()
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            img.thumbnail((1000, 1000))
            exact[hashlib.sha256(raw).hexdigest()] = p
            dh = ipc.dhash(p)
            if dh is not None:
                perceptual.append((dh, p))
        except Exception:
            continue
    return exact, perceptual


def download(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = resp.read()
    if len(raw) < 5000:
        raise ValueError(f"download too small ({len(raw)} bytes)")
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    if img.width < 300 or img.height < 250:
        raise ValueError(f"image too small ({img.width}x{img.height})")
    return img, raw


def save_jpeg(img, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG", quality=93, optimize=True)


def append_index(filename, tags, credit):
    text = INDEX.read_text(encoding="utf-8") if INDEX.exists() else ""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if any(ln.split("|", 1)[0].strip() == filename for ln in lines):
        return False
    with INDEX.open("a", encoding="utf-8") as fh:
        if text and not text.endswith("\n"):
            fh.write("\n")
        fh.write(f"{filename} | {', '.join(tags)} | {credit}\n")
    return True


def update_ledger(filename, story, verdict, source_url):
    try:
        doc = json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception:
        doc = {"version": 2, "policy": "Only DIRECT and STRONG_CONTEXT count.", "assets": {}}
    row = doc.setdefault("assets", {}).setdefault(filename, {"stories": {}})
    row.setdefault("stories", {})[story] = verdict
    row["source_url"] = source_url
    LEDGER.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    changed = 0
    for spec in manifest.get("assets", []):
        filename = spec["filename"]
        dest = IMAGES / filename
        if dest.exists():
            print(f"exists: {filename}")
            append_index(filename, spec["tags"], spec["credit"])
            update_ledger(filename, spec["story"], spec["verdict"], spec["url"])
            continue
        print(f"downloading: {filename}")
        img, raw = download(spec["url"])
        # Compare the normalized image to existing files. Exact-source bytes are
        # checked too, but normalization makes PNG/JPEG copies detectable by dhash.
        exact, perceptual = existing_hashes()
        raw_sha = hashlib.sha256(raw).hexdigest()
        if raw_sha in exact:
            raise SystemExit(f"{filename}: exact duplicate of {exact[raw_sha].name}")
        tmp = IMAGES / (filename + ".tmp.jpg")
        save_jpeg(img, tmp)
        dh = ipc.dhash(tmp)
        twin = None
        if dh is not None:
            for old_h, old_p in perceptual:
                if bin(dh ^ old_h).count("1") <= ipc.DHASH_MAX_DISTANCE:
                    twin = old_p
                    break
        if twin:
            tmp.unlink(missing_ok=True)
            raise SystemExit(f"{filename}: perceptual duplicate of {twin.name}")
        tmp.replace(dest)
        append_index(filename, spec["tags"], spec["credit"])
        update_ledger(filename, spec["story"], spec["verdict"], spec["url"])
        changed += 1
        print(f"  seeded {filename} ({img.width}x{img.height})")
    print(f"repair assets seeded: {changed}")

if __name__ == "__main__":
    main()
