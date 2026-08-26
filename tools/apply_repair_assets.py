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


def crop_from_spec(img, spec):
    """Apply an optional relative crop box ``[left, top, right, bottom]``.

    Repair manifests sometimes point at an official editorial composite where
    the relevant photograph occupies only part of the source. Cropping here is
    safer than teaching the renderer source-specific geometry: the runtime sees
    a normal local photograph and all provenance remains attached to the same
    reviewed source URL.
    """
    box = spec.get("crop_box")
    if not box:
        return img
    if not isinstance(box, list) or len(box) != 4:
        raise ValueError("crop_box must be [left, top, right, bottom]")
    try:
        left, top, right, bottom = [float(v) for v in box]
    except (TypeError, ValueError):
        raise ValueError("crop_box values must be numbers")
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        raise ValueError("crop_box values must be relative coordinates in 0..1")
    px = (
        round(img.width * left),
        round(img.height * top),
        round(img.width * right),
        round(img.height * bottom),
    )
    cropped = img.crop(px)
    if cropped.width < 300 or cropped.height < 250:
        raise ValueError(
            f"cropped image too small ({cropped.width}x{cropped.height})")
    return cropped


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
        replace_existing = bool(spec.get("replace_existing"))
        if dest.exists() and not replace_existing:
            print(f"exists: {filename}")
            append_index(filename, spec["tags"], spec["credit"])
            update_ledger(filename, spec["story"], spec["verdict"], spec["url"])
            continue
        action = "rebuilding" if dest.exists() else "downloading"
        print(f"{action}: {filename}")
        img, raw = download(spec["url"])
        img = crop_from_spec(img, spec)
        # Compare the normalized image to existing files. Exact-source bytes are
        # checked too, but normalization makes PNG/JPEG copies detectable by dhash.
        # When rebuilding a reviewed asset, exclude its old version from the
        # duplicate pool so the deterministic replacement can overwrite itself.
        exact, perceptual = existing_hashes(exclude=dest if dest.exists() else None)
        raw_sha = hashlib.sha256(raw).hexdigest()
        if raw_sha in exact and not spec.get("crop_box"):
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
