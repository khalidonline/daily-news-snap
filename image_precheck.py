#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
image_precheck.py — one pass that runs *before* a story is marked READY.

Order matters: guards run before dedupe, dedupe runs before counting.
A story is scored on DISTINCT, CORROBORATED, RENDERABLE images — not on
how many slots got filled.

    1. slot/alias typing   — a person alias may only fill the portrait slot
    2. homonym guard       — trap tokens need a second corroborating token
    3. logo sanity         — reject SVGs that rasterize to a bar or a block
    4. dedupe              — exact hash, then perceptual near-dupe
    5. readiness           — recomputed from the surviving unique set

Pillow is optional. Without it you still get exact-hash dedupe and both
text guards; you lose near-dupe detection and logo rasterization checks.

CLI:
    python image_precheck.py --manifest candidates.json --stories stories.txt
    python image_precheck.py --selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

try:
    from PIL import Image
    HAVE_PIL = True
except ImportError:  # pragma: no cover
    HAVE_PIL = False


# ─────────────────────────────────────────────────────────────────────────────
# Tunables
# ─────────────────────────────────────────────────────────────────────────────

FRAMES_PER_STORY = 6      # every frame must carry a picture
READY_MIN_UNIQUE = 3      # unique editorial images below which READY is a lie
THIN_MIN_UNIQUE = 1
DHASH_MAX_DISTANCE = 5    # hamming distance on a 64-bit dhash = "same photo"

# Slot priority: when two slots hold the same file, the survivor keeps the
# slot listed first here and the other slot is reported as UNFILLED.
SLOT_PRIORITY = ("portrait", "entity", "archive", "logo")

# Which alias type each slot is allowed to resolve on. This is the صالح كامل
# fix: "Dallah Al Baraka" is an entity alias, so it can never reach portrait.
SLOT_ALIAS_TYPES = {
    "portrait": ("person",),
    "archive":  ("person", "entity"),
    "entity":   ("entity",),
    "logo":     ("entity",),
}

# Tokens that reliably match the wrong thing on their own. A candidate that
# matched ONLY on a trap token needs a second, independent story token in its
# caption before it is allowed through.
TRAP_TOKENS = {
    "amazon", "apple", "tesla", "snap", "souq", "sama", "noon", "hunger",
    "orange", "shell", "gulf", "oracle", "lucid", "smith", "khan", "ali",
    "نون", "سوق", "ساما", "علي",
}

# Hard rejects: caption carries a marker of the *wrong* sense of a trap token.
# Every entry below is a failure that actually shipped in the catalogue.
WRONG_SENSE_MARKERS = {
    "amazon":  {"parrot", "rainforest", "river", "forest", "turquoise-fronted"},
    "apple":   {"tree", "fruit", "orchard", "malus", "barkevik"},
    "tesla":   {"nikola", "coil", "colorado springs"},
    "snap":    {"fastener", "fasteners", "button", "druckknopf", "press stud"},
    "souq":    {"waqif", "doha", "qatar", "marrakesh", "medina souk"},
    "sama":    {"sufi", "sufis", "whirling", "dervish", "performing sama"},
    "noon":    {"orientalist", "painting", "bazaar", "street scene", "watercolor"},
    "hunger":  {"hill", "geograph", "strike", "moor"},
    "smith":   {"baseball", "guitarist", "band", "punk"},
    "ali":     {"football", "footballer", "match", "stadium", "sanad"},
}


# ─────────────────────────────────────────────────────────────────────────────
# Text normalization
# ─────────────────────────────────────────────────────────────────────────────

_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")


def normalize(text: str) -> str:
    """Casefold, strip diacritics/tatweel, unify alef+ya+ta-marbuta."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _ARABIC_DIACRITICS.sub("", text)
    text = (text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
                .replace("ى", "ي").replace("ة", "ه"))
    return text.casefold().strip()


def tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^\w؀-ۿ]+", normalize(text)) if len(t) > 2}


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Story:
    title: str
    pool: str = "saudi"                       # saudi | general
    person_aliases: list[str] = field(default_factory=list)
    entity_aliases: list[str] = field(default_factory=list)
    context: list[str] = field(default_factory=list)  # sector, country, co-founders

    def aliases_for(self, slot: str) -> list[str]:
        out: list[str] = []
        for kind in SLOT_ALIAS_TYPES.get(slot, ()):
            out += self.person_aliases if kind == "person" else self.entity_aliases
        return out

    @property
    def corroborators(self) -> set[str]:
        """Tokens that count as independent evidence a caption is on-topic."""
        bag: set[str] = set()
        for s in [self.title, *self.person_aliases, *self.entity_aliases, *self.context]:
            bag |= tokens(s)
        return bag


@dataclass
class Candidate:
    path: str
    caption: str
    slot: str                                  # portrait | archive | entity | logo
    matched_on: str = ""                       # the alias/token that retrieved it
    archive_id: str = ""                       # stable ID if the archive gives one

    # filled in by the pass
    rejected: str = ""                         # reason, empty if kept
    fingerprint: str = ""
    dupe_of: str = ""


@dataclass
class Result:
    story: Story
    kept: list[Candidate]
    rejected: list[Candidate]
    status: str                                # READY | THIN | NOT_READY
    slots_unfilled: list[str]
    notes: list[str]

    def to_dict(self) -> dict:
        return {
            "title": self.story.title,
            "pool": self.story.pool,
            "status": self.status,
            "unique_images": len(self.kept),
            "kept": [{"path": c.path, "slot": c.slot} for c in self.kept],
            "rejected": [{"path": c.path, "slot": c.slot, "reason": c.rejected,
                          "dupe_of": c.dupe_of} for c in self.rejected],
            "slots_unfilled": self.slots_unfilled,
            "notes": self.notes,
        }


# ─────────────────────────────────────────────────────────────────────────────
# stories.txt parsing  —  title | person: a, b | entity: c | context: d
# ─────────────────────────────────────────────────────────────────────────────

def parse_stories(path: str | Path, pool: str = "saudi") -> list[Story]:
    stories: list[Story] = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        stories.append(parse_story_line(line, pool))
    return stories


def parse_story_line(line: str, pool: str = "saudi") -> Story:
    parts = [p.strip() for p in line.split("|")]
    story = Story(title=parts[0], pool=pool)
    for seg in parts[1:]:
        if ":" in seg:
            kind, _, values = seg.partition(":")
            vals = [v.strip() for v in values.split(",") if v.strip()]
            kind = kind.strip().casefold()
            if kind in ("person", "شخص"):
                story.person_aliases += vals
            elif kind in ("entity", "كيان", "company"):
                story.entity_aliases += vals
            elif kind in ("context", "سياق"):
                story.context += vals
        else:
            # Legacy untyped alias. Treat as entity — never as a portrait key.
            story.entity_aliases += [v.strip() for v in seg.split(",") if v.strip()]
    return story


# ─────────────────────────────────────────────────────────────────────────────
# Guard 1 — slot/alias typing
# ─────────────────────────────────────────────────────────────────────────────

def guard_alias_type(cand: Candidate, story: Story) -> str:
    if cand.slot not in SLOT_ALIAS_TYPES:
        return ""
    # A company story has no portrait slot at all. This alone kills the
    # "NaDeC Base Nagaoka" class of match.
    if cand.slot == "portrait" and not story.person_aliases:
        return "portrait slot but the story declares no person"
    if not cand.matched_on:
        return ""
    allowed = {normalize(a) for a in story.aliases_for(cand.slot) if a}
    if cand.slot != "portrait":
        allowed |= tokens(story.title)
    if not allowed:
        return ""
    m = normalize(cand.matched_on)
    if m in allowed or any(m in a or a in m for a in allowed):
        return ""
    return (f"slot '{cand.slot}' may not resolve on '{cand.matched_on}' "
            f"(wrong alias type)")


# ─────────────────────────────────────────────────────────────────────────────
# Guard 2 — homonym / corroboration
# ─────────────────────────────────────────────────────────────────────────────

def guard_homonym(cand: Candidate, story: Story) -> str:
    cap = normalize(cand.caption)
    cap_tokens = tokens(cand.caption)

    for trap, markers in WRONG_SENSE_MARKERS.items():
        if trap in cap_tokens or trap in cap:
            for marker in markers:
                if normalize(marker) in cap:
                    return f"wrong sense of '{trap}' — caption says '{marker}'"

    matched = normalize(cand.matched_on)
    if matched and matched in TRAP_TOKENS:
        others = (cap_tokens & story.corroborators) - {matched}
        if not others:
            return (f"matched only on trap token '{matched}' with no second "
                    f"story token in the caption")
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Guard 3 — logo / rasterization sanity
# ─────────────────────────────────────────────────────────────────────────────

def guard_render(cand: Candidate) -> str:
    """Catch the black-bar and solid-block rasterizations (Lucid, Tokyo)."""
    if not HAVE_PIL:
        return ""
    p = Path(cand.path)
    if not p.exists():
        return ""
    try:
        img = Image.open(p).convert("RGBA")
    except Exception as exc:                       # noqa: BLE001
        return f"unreadable image ({exc.__class__.__name__})"

    bg = Image.new("RGBA", img.size, (245, 242, 235, 255))   # the cream card
    flat = Image.alpha_composite(bg, img).convert("L")
    w, h = flat.size
    if w < 24 or h < 24:
        return f"too small to place ({w}x{h})"

    hist = flat.histogram()
    px = w * h
    if max(hist) / px > 0.995:
        return "renders as a single flat color on the cream card"

    ink = sum(hist[:80]) / px                      # near-black coverage
    if ink > 0.90:
        return "renders as a solid dark block"

    bbox = flat.point(lambda v: 255 if v < 200 else 0).getbbox()
    if bbox is None:
        return "nothing visible on a cream background"
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    if bw and bh:
        aspect = max(bw / bh, bh / bw)
        if aspect > 12 and ink < 0.35:
            return "renders as a bar, not a mark"
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Dedupe — exact, then perceptual
# ─────────────────────────────────────────────────────────────────────────────

def sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def dhash(path: str | Path, size: int = 8) -> int | None:
    if not HAVE_PIL:
        return None
    try:
        img = Image.open(path).convert("L").resize((size + 1, size), Image.LANCZOS)
    except Exception:                              # noqa: BLE001
        return None
    px = list(img.getdata())
    bits = 0
    for row in range(size):
        for col in range(size):
            left = px[row * (size + 1) + col]
            right = px[row * (size + 1) + col + 1]
            bits = (bits << 1) | int(left > right)
    return bits


def _slot_rank(slot: str) -> int:
    return SLOT_PRIORITY.index(slot) if slot in SLOT_PRIORITY else len(SLOT_PRIORITY)


def dedupe(cands: list[Candidate]) -> tuple[list[Candidate], list[Candidate]]:
    """Keep one candidate per distinct picture; the highest-priority slot wins."""
    for c in cands:
        if c.archive_id:
            c.fingerprint = f"id:{c.archive_id}"
        elif Path(c.path).exists():
            c.fingerprint = f"sha:{sha256(c.path)}"
        else:
            c.fingerprint = f"name:{normalize(Path(c.path).name)}"

    ordered = sorted(cands, key=lambda c: (_slot_rank(c.slot), c.path))
    kept: list[Candidate] = []
    dropped: list[Candidate] = []
    hashes: list[tuple[int, Candidate]] = []

    for c in ordered:
        twin = next((k for k in kept if k.fingerprint == c.fingerprint), None)
        if twin is None:
            dh = dhash(c.path) if Path(c.path).exists() else None
            if dh is not None:
                for other_h, other_c in hashes:
                    if bin(dh ^ other_h).count("1") <= DHASH_MAX_DISTANCE:
                        twin = other_c
                        break
                if twin is None:
                    hashes.append((dh, c))
        if twin is not None:
            c.rejected = "duplicate picture"
            c.dupe_of = twin.path
            dropped.append(c)
        else:
            kept.append(c)
    return kept, dropped


# ─────────────────────────────────────────────────────────────────────────────
# The pass
# ─────────────────────────────────────────────────────────────────────────────

def precheck(story: Story, cands: list[Candidate]) -> Result:
    survivors: list[Candidate] = []
    rejected: list[Candidate] = []

    for c in cands:
        reason = (guard_alias_type(c, story)
                  or guard_homonym(c, story)
                  or (guard_render(c) if c.slot == "logo" else ""))
        if reason:
            c.rejected = reason
            rejected.append(c)
        else:
            survivors.append(c)

    kept, dupes = dedupe(survivors)
    rejected += dupes

    n = len(kept)
    if n == 0:
        status = "NOT_READY"
    elif n < READY_MIN_UNIQUE:
        status = "THIN"
    else:
        status = "READY"

    filled = {c.slot for c in kept}
    unfilled = [s for s in SLOT_PRIORITY if s not in filled]

    notes: list[str] = []
    if status == "READY" and n < FRAMES_PER_STORY:
        notes.append(f"{n} unique for {FRAMES_PER_STORY} frames — "
                     f"{FRAMES_PER_STORY - n} will need a curated logo fallback")
    if any(c.rejected == "duplicate picture" for c in rejected):
        notes.append("slot count overstated readiness before dedupe")

    return Result(story, kept, rejected, status, unfilled, notes)


def precheck_all(pairs: Iterable[tuple[Story, list[Candidate]]]) -> list[Result]:
    """Also flags stories that share an image set with another story."""
    results = [precheck(s, c) for s, c in pairs]
    seen: dict[str, str] = {}
    for r in results:
        if not r.kept:
            continue
        sig = "|".join(sorted(c.fingerprint for c in r.kept))
        if sig in seen:
            r.notes.append(f"identical image set to «{seen[sig]}» — "
                           f"merge the stories or re-source one")
        else:
            seen[sig] = r.story.title
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Manifest I/O
# ─────────────────────────────────────────────────────────────────────────────

def load_manifest(path: str | Path) -> list[tuple[Story, list[Candidate]]]:
    """
    [{"title": "...", "pool": "saudi",
      "person": ["..."], "entity": ["..."], "context": ["..."],
      "candidates": [{"path": "...", "caption": "...", "slot": "portrait",
                      "matched_on": "...", "archive_id": "..."}]}]
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for row in data:
        story = Story(
            title=row["title"],
            pool=row.get("pool", "saudi"),
            person_aliases=row.get("person", []),
            entity_aliases=row.get("entity", []),
            context=row.get("context", []),
        )
        cands = [Candidate(**c) for c in row.get("candidates", [])]
        out.append((story, cands))
    return out


def report(results: list[Result]) -> str:
    lines = []
    tally = {"READY": 0, "THIN": 0, "NOT_READY": 0}
    for r in results:
        tally[r.status] += 1
        lines.append(f"[{r.status:9}] {r.story.title}  ({len(r.kept)} unique)")
        for c in r.rejected:
            extra = f" ← {Path(c.dupe_of).name}" if c.dupe_of else ""
            lines.append(f"            ✗ {Path(c.path).name}: {c.rejected}{extra}")
        for note in r.notes:
            lines.append(f"            ⚠ {note}")
    lines.append("")
    lines.append(f"READY {tally['READY']}  THIN {tally['THIN']}  "
                 f"NOT READY {tally['NOT_READY']}  (of {len(results)})")
    if not HAVE_PIL:
        lines.append("note: Pillow missing — near-dupe and render checks skipped")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Self-test — the three failures from the catalogue
# ─────────────────────────────────────────────────────────────────────────────

def selftest() -> int:
    cases = [
        (parse_story_line("قصة صالح كامل ودلة البركة | person: صالح كامل, Saleh Kamel "
                          "| entity: دلة البركة, Dallah Al Baraka"),
         [Candidate("a/boeing737.jpg", "Boeing 737-9LBER (BBJ3) Dallah Al Baraka",
                    "archive", matched_on="Dallah Al Baraka"),
          Candidate("a/boeing737_copy.jpg", "Dallah Al Baraka",
                    "portrait", matched_on="Dallah Al Baraka")]),

        (parse_story_line("قصة هنقرستيشن وحرب تطبيقات التوصيل | entity: HungerStation "
                          "| context: توصيل, السعودية, delivery"),
         [Candidate("a/hunger_hill.jpg", "Hunger Hill - geograph.org.uk",
                    "archive", matched_on="hunger")]),

        (parse_story_line("قصة نادك للأغذية | entity: نادك, NADEC"),
         [Candidate("a/nadec.png", "NADEC-New-logo", "logo", archive_id="nadec-logo"),
          Candidate("a/nadec2.png", "NADEC", "entity", archive_id="nadec-logo"),
          Candidate("a/nadec3.png", "NADEC-New-logo", "archive", archive_id="nadec-logo"),
          Candidate("a/nagaoka.jpg", "NaDeC Base Nagaoka", "portrait",
                    matched_on="NADEC")]),
    ]
    results = precheck_all(cases)
    print(report(results))

    # صالح كامل → THIN: the aircraft is a legitimate *archive* image of دلة البركة,
    # it just may never stand in as the man's portrait. One unique image, honestly
    # labelled, is the right answer — the story stays out of the 6-frame build.
    expected = ["THIN", "NOT_READY", "THIN"]
    got = [r.status for r in results]
    ok = got == expected
    print(f"\nselftest: {'PASS' if ok else 'FAIL'}  expected {expected}, got {got}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Story image pre-check")
    ap.add_argument("--manifest", help="candidates JSON")
    ap.add_argument("--stories", help="stories.txt (typed aliases)")
    ap.add_argument("--json-out", help="write machine-readable results here")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.stories and not args.manifest:
        for s in parse_stories(args.stories):
            print(f"{s.title}\n  person={s.person_aliases}\n  entity={s.entity_aliases}")
        return 0
    if not args.manifest:
        ap.error("need --manifest or --selftest")

    results = precheck_all(load_manifest(args.manifest))
    print(report(results))
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2),
            encoding="utf-8")
    return 0 if all(r.status != "READY" or r.kept for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
