#!/usr/bin/env python3
"""
موجز الأخبار السعودية اليومي -> سناب شات
Daily Saudi news brief -> Snapchat.

Same pipeline as before, in Arabic:
  fetch Saudi RSS -> Claude picks + summarizes in Arabic -> RTL card -> Snapchat
"""

import base64
import json
import os
import re
import subprocess
import sys
import hashlib
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from functools import lru_cache
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw, ImageFont, features
from fontTools.ttLib import TTFont

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

# Saudi Arabic sources. Run once with DRY_RUN=1 and check the per-feed counts
# in the log — delete any that report 0 items and keep the rest.
FEEDS = [
    # business, finance and technology — the core of the feed now
    ("BBC Business",   "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("BBC Technology",   "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("TechCrunch",           "https://techcrunch.com/feed/"),
    ("The Verge",            "https://www.theverge.com/rss/index.xml"),
    ("Engadget",           "https://www.engadget.com/rss.xml"),
    ("CNBC",        "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("CNBC Tech", "https://www.cnbc.com/id/19854910/device/rss/rss.html"),
    # regional and Saudi, kept for stories that matter close to home
    ("الشرق الأوسط",       "https://aawsat.com/feed"),
    ("اليوم",              "https://www.alyaum.com/rssFeed/1005"),
    ("BBC عربي",      "https://feeds.bbci.co.uk/arabic/rss.xml"),
]

STORIES_PER_DAY = int(os.getenv("STORIES_PER_DAY", "1"))
# ask for several ranked candidates so we can skip any we can't illustrate
CANDIDATES = int(os.getenv("CANDIDATES", "5"))
REQUIRE_PHOTO = os.getenv("REQUIRE_PHOTO", "1").strip() not in ("", "0", "false")
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "30"))
MAX_HEADLINES_TO_MODEL = 60

def _clean_model_id(raw, fallback):
    """Accept a pasted code snippet as well as a bare id.

    model="seedream-4-5-251128"  ->  seedream-4-5-251128
    """
    value = (raw or "").strip()
    if not value:
        return fallback
    if "=" in value:
        value = value.split("=", 1)[1]
    return value.strip().strip('"').strip("'").strip() or fallback


CLAUDE_MODEL = _clean_model_id(os.getenv("CLAUDE_MODEL"), "claude-sonnet-5")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
AYRSHARE_API_KEY = os.getenv("AYRSHARE_API_KEY", "").strip()

# which service actually publishes to Snapchat: bundle | ayrshare | zernio
POST_PROVIDER = os.getenv("POST_PROVIDER", "bundle").strip().lower()

# bundle.social
BUNDLE_API_KEY = os.getenv("BUNDLE_API_KEY", "").strip()
BUNDLE_TEAM_ID = os.getenv("BUNDLE_TEAM_ID", "").strip()
BUNDLE_BASE = os.getenv("BUNDLE_BASE", "").strip() or "https://api.bundle.social/api/v1"

# Cloudflare sits in front of bundle.social and returns "error code: 1010" to
# requests without a browser-like fingerprint, so send real headers.
BUNDLE_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}
ZERNIO_API_KEY = os.getenv("ZERNIO_API_KEY", "").strip()
ZERNIO_BASE = os.getenv("ZERNIO_BASE", "").strip() or "https://api.zernio.com/v1"
# the Snapchat account id from your Zernio dashboard; blank = let Zernio pick
ZERNIO_ACCOUNT_ID = os.getenv("ZERNIO_ACCOUNT_ID", "").strip()
DRY_RUN = os.getenv("DRY_RUN", "").strip() not in ("", "0", "false", "False")

MEDIA_MODE = os.getenv("MEDIA_MODE", "github").strip()
CARDS_DIR = "cards"
KEEP_CARDS_DAYS = int(os.getenv("KEEP_CARDS_DAYS", "30"))   # 0 = keep forever

OUT_DIR = Path(os.getenv("OUT_DIR", "out"))
W, H = 1080, 1920

THEME = os.getenv("THEME", "dark").strip()          # dark | light

if THEME == "light":
    BG_TOP = (238, 232, 227)
    BG_BOTTOM = (232, 225, 219)
    ACCENT = (183, 28, 44)          # red, only for the takeaway line
    BRAND_INK = (11, 61, 46)        # deep emerald, for the bar and the label
    TEXT = (24, 56, 97)             # blue, headline and body
    BODY = (40, 72, 112)
    MUTED = (140, 130, 122)
    RULE = (206, 197, 189)
else:
    BG_TOP = (14, 17, 26)
    BG_BOTTOM = (28, 34, 52)
    ACCENT = (255, 215, 64)
    BRAND_INK = (255, 215, 64)
    TEXT = (245, 246, 250)
    BODY = (206, 212, 228)
    MUTED = (150, 158, 178)
    RULE = (58, 66, 90)

USER_AGENT = "Mozilla/5.0 (compatible; daily-news-bot/1.0)"

AR_MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
             "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
AR_DAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس",
           "الجمعة", "السبت", "الأحد"]
AR_DIGITS = str.maketrans("0123456789", "0123456789")   # digits stay Latin

BRIEF_TITLE = os.getenv("BRIEF_TITLE", "ملخص تنفيذي - أخبار السعودية")
BRAND = os.getenv("BRAND", "ملخص تنفيذي")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "").strip()
HERO_HEIGHT = int(os.getenv("HERO_HEIGHT", "620"))
MIN_PHOTO_SCORE = int(os.getenv("MIN_PHOTO_SCORE", "").strip() or "10")
# Openverse/Pexels are global libraries: without this, a US classroom passes
# for a Saudi school story. Article photos and SPA are Saudi by definition.
# a photo has to match at least this many of the query words. One weak match
# plus a Saudi mention got a WIPO meeting onto a story about insurance rules.
MIN_TERM_HITS = int(os.getenv("MIN_TERM_HITS", "").strip() or "2")

# generic officialdom: true of a thousand events, specific to none
MEETING_HINTS = ("conference", "meeting", "delegation", "summit", "panel",
                 "signing ceremony", "press conference", "forum", "assembly",
                 "session", "committee", "podium", "speech", "award ceremony")

REQUIRE_SAUDI_CONTEXT = (os.getenv("REQUIRE_SAUDI_CONTEXT", "").strip() or "1") \
    not in ("0", "false", "False")

# A wrong photo is worse than no photo. Anything whose own description mentions
# these is rejected outright — they turn a neutral story into a claim.
BLOCKED_IMAGE_TERMS = (
    "weapon", "weapons", "gun", "guns", "rifle", "rifles", "pistol", "firearm",
    "soldier", "soldiers", "military", "army", "armed", "troops", "war",
    "combat", "battle", "tank", "missile", "bomb", "explosion", "airstrike",
    "police", "arrest", "handcuff", "prison", "jail", "detention",
    "protest", "riot", "demonstration", "clash", "violence", "blood",
    "injured", "casualty", "funeral", "grave", "refugee", "terror",
    "smoking", "alcohol", "beer", "wine", "bikini", "lingerie",
    # political figures: a business/econ account has no card where a
    # named politician is the picture — Arafat sailed through every
    # existing list onto the shemagh story's candidates. Surnames only,
    # high precision; the vision gate remains the judge of anyone else.
    "arafat", "netanyahu", "erdogan", "assad", "putin", "zelensky",
    "trump", "biden", "obama", "khamenei", "khomeini", "gaddafi",
    "saddam", "mussolini", "hitler", "stalin",
)


# the English blocklist won't catch an Arabic caption, and since stories now
# search Openverse in Arabic too, Arabic captions arrive from every source
# rather than only from SPA
BLOCKED_AR_TERMS = (
    "جندي", "جنود", "عسكري", "عسكرية", "سلاح", "أسلحة", "بندقية", "مدفع",
    "حرب", "قتال", "اشتباك", "غارة", "قصف", "انفجار", "صاروخ",
    "شرطة", "اعتقال", "توقيف", "سجن", "سجين", "محكمة",
    "احتجاج", "مظاهرة", "عنف", "دماء", "إصابة", "مصاب", "جنازة", "عزاء",
    "حادث", "حريق", "كارثة", "ضحايا", "قتلى",
)

# Artwork is not evidence. A story about a real person or a real place needs a
# photograph of it — political art, a propaganda poster or a caricature is
# somebody's argument about the subject, and putting it on the card passes
# that argument off as a record. The pixel check catches flat logo cards; this
# catches artwork that is photographic enough to survive it.
NOT_A_PHOTOGRAPH_TERMS = (
    "propaganda", "poster", "posters", "caricature", "caricatures",
    "cartoon", "cartoons", "illustration", "illustrations", "illustrated",
    "drawing", "drawings", "artwork", "painting", "paintings", "sketch",
    "engraving", "lithograph", "woodcut", "etching", "mural", "clipart",
    # documents, not photographs. An award certificate photographed at an
    # angle isn't flat enough for the pixel check and its description says
    # "certificate", not "poster" — one reached the closing frame of the
    # Tesla story, made out to two doctors, matched on the word Tesla.
    # NOT bare "award": that would reject an award-winning building. Award
    # ceremonies are already handled by MEETING_HINTS as a score penalty.
    "certificate", "certificates", "diploma", "diplomas",
    "plaque", "plaques", "award certificate",
    # a labelled location map reached a story frame — a map is a diagram,
    # however useful. NOT "mapping"/"mapped": whole-word matching covers that.
    "map", "maps", "atlas", "cartography",
)

# NOT "رسم" or "رسوم" on their own: those are the ordinary words for a fee,
# and "الرسوم الجمركية" (customs duties) is core business vocabulary — the
# same trap as 'war' inside 'warehouse'. Only unambiguous forms here.
NOT_A_PHOTOGRAPH_AR = (
    "كاريكاتير", "كاريكاتور", "كاريكاتيري",
    "بروباغندا", "بروباجندا", "دعاية", "دعائية",
    "ملصق", "ملصقات", "رسمة", "رسومات",
    "رسم توضيحي", "رسوم متحركة", "رسم كرتوني", "لوحة زيتية",
    # NOT "شهادة" on its own — it is the ordinary word for a school or
    # university qualification and would reject education photos
    "شهادة تقدير", "شهادة شكر", "دبلوم", "لوحة تذكارية", "درع تكريمي",
    "خريطة", "خرائط",
)


def _latin_word_re(terms):
    return re.compile(r"\b(" + "|".join(re.escape(t) for t in terms) + r")\b",
                      re.IGNORECASE)


def _arabic_word_re(terms):
    """Arabic has no \\b, so bound the match with the Arabic letter range —
    otherwise a blocked word rejects every word that merely contains it.

    Arabic also glues its article and prepositions onto the front of a word,
    and a caption almost always uses them: 'الجنود' not 'جنود', 'بالسلاح' not
    'سلاح'. Bounding on the letter range alone meant the article defeated
    every term in the list, so the most common form of each one walked
    straight through. Allow the usual proclitics before the match.
    """
    prefix = r"(?:لل|[وفبكل]?ال|[وفبكل])?"
    return re.compile(r"(?<![ء-ي])" + prefix + r"("
                      + "|".join(re.escape(t) for t in terms)
                      + r")(?![ء-ي])")


_BLOCKED_RE = _latin_word_re(BLOCKED_IMAGE_TERMS)
_BLOCKED_AR_RE = _arabic_word_re(BLOCKED_AR_TERMS)
_ARTWORK_RE = _latin_word_re(NOT_A_PHOTOGRAPH_TERMS)

# Commons names award documents in ways the plain word list misses: "Genius
# Nikola Tesla Award", "Diplôme de Participation", "Honorary Charter", "Order
# of the White Lion awarded to Nikola Tesla". Three of them reached story
# frames after "certificate" was blocked, because none of them says
# certificate. "award" as a noun is the common thread — but "award-winning"
# is an adjective describing a real building, so that one form is spared.
_DOCUMENT_RE = re.compile(
    r"\bawarded\s+to\b"
    r"|\baward\b(?!\s*-?\s*winning)"
    r"|\bdipl[oô]me\b"
    r"|\bhonorary\s+(?:doctorate|degree|charter|diploma|certificate)\b"
    r"|\bmedals?\b|\btroph(?:y|ies)\b"
    r"|\byearbooks?\b|\bprint edition\b|\bfront pages?\b"
    r"|\bregulations?\b|\bdirective\b"
    r"|\bmicroform\b|\bfolio\b",
    re.IGNORECASE)
_ARTWORK_AR_RE = _arabic_word_re(NOT_A_PHOTOGRAPH_AR)


def looks_like_a_graphic(path):
    """True for logo cards, infographics and other flat artwork.

    SPA's archive mixes branded graphics in with photographs; a logo card is
    mostly flat white with a small mark in the middle, so it reads very
    differently from a photo at the pixel level.
    """
    try:
        img = Image.open(path).convert("RGB")
    except Exception as exc:
        # fail CLOSED: a file PIL cannot decode (an SVG chart from
        # Openverse reached four Samsung frames this way) is not a
        # photograph — declaring it "not a graphic" passed it onward
        print(f"  ! undecodable image ({exc}) — rejecting")
        return True

    small = img.resize((120, 120))
    pixels = list(small.getdata())
    total = len(pixels)

    near_white = sum(1 for r, g, b in pixels if r > 235 and g > 235 and b > 235)
    if near_white / total > 0.55:
        print(f"  ! looks like a logo card ({near_white * 100 // total}% white)")
        return True

    # flat artwork has little tonal variation; photographs have plenty
    lum = [0.299 * r + 0.587 * g + 0.114 * b for r, g, b in pixels]
    mean = sum(lum) / total
    spread = (sum((v - mean) ** 2 for v in lum) / total) ** 0.5
    if spread < 22:
        print(f"  ! looks like flat artwork (contrast spread {spread:.0f})")
        return True

    # A two-tone graphic sails past BOTH checks above: white under 55%, and
    # two flat colours far apart give a big luminance spread. What it cannot
    # fake is tonal SPREAD — it piles its pixels into two luminance bins.
    # (Counting distinct colours was the first attempt and flagged every
    # black-and-white photograph, which quantizes to a handful of greys.
    # Measured on shipped cards: the green-and-white chart that reached a
    # frame concentrates 95% of pixels in its top two bins; real photos,
    # including the 1938 monochromes, stay at or under 41%.)
    bins = [0] * 32
    for v in lum:
        bins[int(v) >> 3] += 1
    top2 = sum(sorted(bins, reverse=True)[:2]) / total
    if top2 > 0.70:
        print(f"  ! looks like a graphic ({top2:.0%} of pixels in two tones)")
        return True
    return False


def _clear_generated_marker(path):
    """A real photo overwrites the file, so drop any stale marker.

    Also clears the .exempt provenance marker for the same reason: every
    archive fetcher calls this before writing, so a curated local photo
    followed by an archive fetch into the same slot can never keep the
    local file's cooldown exemption.
    """
    for suffix in (".generated", ".exempt"):
        marker = Path(str(path) + suffix)
        if marker.exists():
            marker.unlink()


# --------------------------------------------------------------------------
# Cross-run photo cooldown — state/photos_used.json
# --------------------------------------------------------------------------
# Two cards published the SAME DAY carried the same واس corniche photo:
# dedup existed only within one story run, and news, topic and story shared
# no photo memory. One registry now, same discipline as quota.json — one
# file, all bots, pushed immediately so the 07:00 run's photos are visible
# to the 09:00 run. Digests are the 16x16 perceptual hash, which already
# treats a re-encode of one picture as the same picture.
PHOTO_REUSE_DAYS = int(os.getenv("PHOTO_REUSE_DAYS", "").strip() or "7")
# the library's OWN short window — the total exemption let one seeded
# Riyadh skyline front the 7am news card and the 9am topic card of a
# single morning, invisibly (exempt files were never registered either)
LIBRARY_REUSE_DAYS = int(os.getenv("LIBRARY_REUSE_DAYS", "").strip() or "2")
PHOTOS_USED_FILE = Path("state/photos_used.json")
# set when the exhaustion path had to reuse a recent photo — the bots
# prepend it to their Telegram delivery so the owner sees the flaw
RECENT_REUSE_WARNING = ""


def _photo_digest(path):
    """Perceptual hash, so the same picture found twice reads as the same.

    Byte-hashing missed a real repeat: frames 1 and 6 of one story fetched
    the same image through different downloads — a re-encode, different
    bytes — and md5 called them distinct. A 16x16 average hash sees the
    picture, not the file.
    """
    try:
        img = Image.open(path).convert("L").resize((16, 16))
        px = list(img.getdata())
        mean = sum(px) / len(px)
        return "".join("1" if v > mean else "0" for v in px)
    except Exception:
        return ""


# Exact-digest equality missed three re-crops of one orange Riyadh skyline
# on a single deck (Mrsool frames 1/5/6): a crop shifts the 16x16 grid and
# bits flip. Near-duplicate detection is hamming distance on the SAME
# ahash. Tuned on real fixtures: re-crops of one scene score 9-23 bits
# (a 5% crop already scores 9, so the first-guess threshold of 8 missed
# actual re-crops), while genuinely different photos score 47+ — even two
# different Riyadh skylines differ by 47. 32 sits in the middle of that
# gap with margin on both sides.
PHOTO_HAMMING_THRESHOLD = int(
    os.getenv("PHOTO_HAMMING_THRESHOLD", "").strip() or "32")


def same_picture(d1, d2):
    """True when two ahash digests are the same picture, re-crops included."""
    if not d1 or not d2 or len(d1) != len(d2):
        return False
    return sum(a != b for a, b in zip(d1, d2)) <= PHOTO_HAMMING_THRESHOLD


def load_photos_used():
    """Registry entries younger than PHOTO_REUSE_DAYS; older ones pruned."""
    try:
        data = json.loads(PHOTOS_USED_FILE.read_text(encoding="utf-8"))
        entries = data.get("entries", [])
    except Exception:
        return []
    cutoff = (datetime.now(timezone.utc)
              - timedelta(days=PHOTO_REUSE_DAYS)).isoformat()
    return [e for e in entries if e.get("at", "") >= cutoff]


def photo_recently_used(path):
    d = _photo_digest(path)
    return bool(d) and any(same_picture(d, e.get("d", ""))
                           for e in load_photos_used())


def _library_recently_used(src_path):
    """The library rests LIBRARY_REUSE_DAYS, not the archives' seven.

    Seeded photos exist to return quickly on recurring beats — the full
    cooldown would defeat their purpose — but never twice in one
    morning across two bots. A match against a non-library entry blocks
    for the full window as usual."""
    d = _photo_digest(src_path)
    if not d:
        return False
    cutoff = (datetime.now(timezone.utc)
              - timedelta(days=LIBRARY_REUSE_DAYS)).isoformat()
    for e in load_photos_used():
        if not same_picture(d, e.get("d", "")):
            continue
        if not e.get("lib") or e.get("at", "") >= cutoff:
            return True
    return False


def _recent_reject(out_path):
    """True when this just-accepted photo was on a recent post.

    The fetcher then returns empty and the chain continues with the next
    keyword or source — the same behaviour as the within-story seen set.
    The rejected file is kept aside so the exhaustion path can still use
    it: a repeated photo is a flaw, a dead run is worse.
    """
    if not photo_recently_used(out_path):
        return False
    keep = Path(str(out_path) + ".recentkeep")
    if not keep.exists():
        import shutil as _sh
        _sh.copyfile(out_path, keep)
    print("      (photo used on a recent post — looking further)")
    return True


def recent_fallback(out_path):
    """The kept-aside recent photo, accepted loudly, or None."""
    global RECENT_REUSE_WARNING
    keep = Path(str(out_path) + ".recentkeep")
    if not keep.exists():
        return None
    import shutil as _sh
    _sh.copyfile(keep, out_path)
    keep.unlink(missing_ok=True)
    RECENT_REUSE_WARNING = "⚠️ الصورة ظهرت على منشور حديث — لم يوجد بديل\n"
    print("  ! every fresh photo exhausted — reusing a RECENT one")
    return str(out_path)


def recent_warning():
    """Read the flag through a function so importers see mutations."""
    return RECENT_REUSE_WARNING


def register_photos(paths, by):
    """Record accepted card photos, one write and one push for the run.

    Local-library photos and curated logos carry a .exempt marker and are
    skipped — a portrait legitimately reappears when its story re-runs, and
    the curated logo repeats by design. DRY_RUN writes the file locally but
    never pushes, so tests stay off the shared state.
    """
    entries = load_photos_used()
    known = {e.get("d") for e in entries}
    added = False
    for path in paths:
        if not path:
            continue
        marker = Path(str(path) + ".exempt")
        is_lib = False
        if marker.exists():
            # only the library registers (flagged, for its short window);
            # curated logos and flags repeat by design and stay out
            if marker.read_text(encoding="utf-8").strip() != "local":
                continue
            is_lib = True
        # a generation is unique each time — cooldown would be noise
        if Path(str(path) + ".generated").exists():
            continue
        d = _photo_digest(path)
        if not d or any(same_picture(d, k) for k in known):
            continue
        known.add(d)
        entry = {"d": d, "at": datetime.now(timezone.utc).isoformat(),
                 "by": by}
        if is_lib:
            entry["lib"] = True
        entries.append(entry)
        added = True
    if not added:
        return
    PHOTOS_USED_FILE.parent.mkdir(parents=True, exist_ok=True)
    PHOTOS_USED_FILE.write_text(
        json.dumps({"entries": entries}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    if not DRY_RUN:
        commit_and_push(PHOTOS_USED_FILE, f"photos used {ksa_stamp()}")


def _image_is_safe(text):
    """Reject candidates whose description touches conflict or sensitive
    themes, or says the thing is artwork rather than a photograph.

    Whole words only — substring matching rejected 'warehouse' for containing
    'war', which quietly killed every result on ordinary searches.
    """
    text = text or ""
    for pattern in (_BLOCKED_RE, _BLOCKED_AR_RE):
        match = pattern.search(text)
        if match:
            print(f"  ! skipped an image ({match.group(0)!r} in its description)")
            return False
    for pattern in (_ARTWORK_RE, _ARTWORK_AR_RE, _DOCUMENT_RE):
        match = pattern.search(text)
        if match:
            print(f"  ! skipped artwork, not a photograph "
                  f"({match.group(0)!r} in its description)")
            return False
    return True

STATE_FILE = Path("state/posted.json")
QUOTA_FILE = Path("state/quota.json")
MONTHLY_POST_LIMIT = int(os.getenv("MONTHLY_POST_LIMIT", "0"))   # 0 = no limit
# "0" = hybrid: build the card and commit it, but don't publish to Snapchat
POST_ENABLED = os.getenv("POST_TO_SNAPCHAT", "1").strip() not in ("", "0", "false", "False")
# Breaking-news mode: when set, the run is about THIS event and nothing else.
# breaking_watch.py sets it after its classifier confirms an event; the model
# re-verifies through the normal prompt and the run ABORTS if it can't —
# a watcher false positive must die here, not print a thin card.
PINNED_EVENT = os.getenv("PINNED_EVENT", "").strip()
REMEMBER_DAYS = int(os.getenv("REMEMBER_DAYS", "3"))


def quota_used():
    """How many posts we've published in the current calendar month."""
    month = datetime.now().strftime("%Y-%m")
    try:
        data = json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return month, 0
    return month, int(data.get(month, 0))


def quota_ok():
    """False when this month's self-imposed posting limit is already reached."""
    if MONTHLY_POST_LIMIT <= 0:
        return True
    month, used = quota_used()
    if used >= MONTHLY_POST_LIMIT:
        print(f"  ! monthly limit reached ({used}/{MONTHLY_POST_LIMIT} posts in "
              f"{month}) — not posting. Raise MONTHLY_POST_LIMIT to allow more.")
        return False
    print(f"    quota: {used}/{MONTHLY_POST_LIMIT} posts used this month")
    return True


def quota_bump():
    """Record one published post. Returns the file so it can be committed."""
    month, used = quota_used()
    try:
        data = json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    data[month] = used + 1
    QUOTA_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUOTA_FILE.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return QUOTA_FILE


def load_posted():
    """Headlines already posted recently, so repeat runs don't repeat news."""
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=REMEMBER_DAYS)).isoformat()
    return [e for e in data if e.get("at", "") >= cutoff]


def save_posted(previous, stories):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    entries = previous + [{"headline": s["headline"], "at": now} for s in stories]
    STATE_FILE.write_text(json.dumps(entries, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    return STATE_FILE


# --------------------------------------------------------------------------
# Arabic text shaping
# --------------------------------------------------------------------------
# Arabic letters change shape by position and run right-to-left. Pillow does
# this natively IF it was built with libraqm. If not, we do it ourselves with
# arabic-reshaper + python-bidi. Doing BOTH would double-reverse the text,
# so we pick exactly one path.

HAS_RAQM = features.check("raqm")

if not HAS_RAQM:
    import arabic_reshaper
    from bidi.algorithm import get_display

    # The reshaper rewrites text into Arabic Presentation Forms (U+FE70-FEFF).
    # Almarai and Cairo ship the initial/medial/final forms but NOT the
    # isolated ones — so ا إ أ ء د ذ ر ز و ة ي, every letter that doesn't join
    # to its left, came out as an empty box. A whole card of tofu, and the
    # glyph warning below never fired because it was checking the text before
    # reshaping. use_unshaped_instead_of_isolated falls back to the plain
    # letter, which every Arabic font has. Verified: with this set, Almarai
    # and Cairo have zero gaps across all four positions, the lam-alef
    # ligatures and the harakat.
    # delete_harakat defaults to True, which would silently strip the
    # diacritics libraqm keeps — the two paths must agree, and sanitize()
    # promises never to delete.
    _RESHAPER = arabic_reshaper.ArabicReshaper(configuration={
        "use_unshaped_instead_of_isolated": True,
        "delete_harakat": False,
    })

# Zero-width joiners and marks are meant to be invisible; a font having no
# glyph for them is normal and not worth warning about.
_INVISIBLE = {0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2066, 0x2069, 0xFEFF}


def _shape(text):
    """The exact string that gets handed to Pillow, on whichever path is live."""
    if HAS_RAQM:
        return text
    return get_display(_RESHAPER.reshape(text))


# Every Arabic letter in all four positions, both lam-alef ligatures, and the
# harakat — enough to prove a font can carry a card before we render one.
_SHAPING_PROBES = tuple(
    [c for ch in "ءآأؤإئابةتثجحخدذرزسشصضطظعغفقكلمنهوىي"
     for c in (ch, ch + "ب", "ب" + ch + "ب", "ب" + ch)]
    + ["ل" + a for a in "اأإآ"] + ["بل" + a for a in "اأإآ"]
    + ["ب" + h for h in "ًٌٍَُِّْ"]
)


def _shaping_gaps(font_path):
    """Codepoints this font can't draw once the text has been shaped.

    Checking the raw text is not enough: on the reshaper path what reaches
    Pillow is a different set of codepoints entirely, and that is where the
    holes are.
    """
    charset = _font_charset(str(font_path))
    if charset is None:
        return set()                  # unreadable table — don't block on it
    gaps = set()
    for probe in _SHAPING_PROBES:
        for ch in _shape(probe):
            if ch != " " and ord(ch) not in charset and ord(ch) not in _INVISIBLE:
                gaps.add(ch)
    return gaps

# Characters models commonly emit that many Arabic fonts don't include.
# Mapped to equivalents present in essentially every font.
CHAR_FIXES = {
    # digits stay Latin no matter what the model writes
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
    "٪": "%", "٬": ",", "٫": ".", "؊": "-",
    "—": "-", "–": "-", "―": "-", "−": "-", "‐": "-", "‑": "-",
    "•": "،", "·": "،", "…": "...", "‎": "", "‏": "",
    "“": '"', "”": '"', "„": '"', "‘": "'", "’": "'",
    "\u00a0": " ", "\u200b": "", "\u2066": "", "\u2069": "",
}

# If the font can't draw these, meaning gets mangled — so we refuse to use it.
REQUIRED_CHARS = "0123456789%-.,:()اب"

# Arabic misspellings the models produce now and then. Add as you spot them —
# the key is the wrong form, the value the correct one.
COMMON_TYPOS = {
    "باطولة": "بطولة",
    "باطولات": "بطولات",
    "إنشاء الله": "إن شاء الله",
    "لاكن": "لكن",
    "إنما": "إنما",
    "هاذا": "هذا",
    "هاذه": "هذه",
    "الذى": "الذي",
    "التى": "التي",
    "علي أن": "على أن",
    "إلي أن": "إلى أن",
}

_missing_reported = set()


@lru_cache(maxsize=8)
def _font_charset(path):
    """Every codepoint the font can actually draw, or None if unreadable."""
    try:
        font = TTFont(path, fontNumber=0, lazy=True)
        chars = set()
        for table in font["cmap"].tables:
            chars.update(table.cmap.keys())
        return frozenset(chars)
    except Exception as exc:
        print(f"  ! couldn't read glyph table of {path}: {exc}")
        return None


_CITE_WARNED = False


def sanitize(text):
    """Normalize odd characters. NEVER deletes — a dropped '-' turns
    '8700-9400' into '87009400', which is a wrong number nobody notices.
    Anything unmappable is left in place to render as a visible box."""
    # Citation markup from web search leaks into model output, often malformed:
    # <cite index="14-1,14-2">  or  cite index="3-5  with no closing bracket.
    if "cite" in text or "index=" in text:
        before = text
        text = re.sub(r"</?cite[^>]*>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"</?\s*cite\b[^<>]*", " ", text, flags=re.IGNORECASE)
        text = re.sub(r'index\s*=\s*"?[0-9,\-\s]*"?\s*>?', " ", text)
        text = text.replace("<", " ").replace(">", " ")
        text = re.sub(r"\s+([،.؟!:])", r"\1", text)      # no space before punctuation
        text = re.sub(r"\s{2,}", " ", text).strip()
        global _CITE_WARNED
        if text != before and not _CITE_WARNED:
            _CITE_WARNED = True
            print("  · stripped citation markup from the text")

    for bad, good in CHAR_FIXES.items():
        text = text.replace(bad, good)

    for wrong, right in COMMON_TYPOS.items():
        if wrong in text:
            print(f"  · fixed spelling: {wrong} -> {right}")
            text = text.replace(wrong, right)

    return text


def _warn_about_missing_glyphs(shaped):
    """Report anything that will render as a box. Runs on the SHAPED string —
    checking the text before shaping missed a card's worth of tofu once,
    because the reshaper had turned it into codepoints the font lacked."""
    charset = _font_charset(_find_arabic_font(False))
    if charset is None:
        return
    for ch in shaped:
        if ch in " \n\t" or ord(ch) in _INVISIBLE or ch in _missing_reported:
            continue
        if ord(ch) not in charset:
            _missing_reported.add(ch)
            print(f"  ! font has no glyph for {ch!r} (U+{ord(ch):04X}) "
                  f"— will render as a box")


def ar(text):
    """Return (text_to_draw, draw_kwargs) for a piece of Arabic text."""
    shaped = _shape(sanitize(text))
    _warn_about_missing_glyphs(shaped)
    if HAS_RAQM:
        return shaped, {"direction": "rtl", "language": "ar"}
    return shaped, {}


def arabic_date():
    now = datetime.now()
    return (f"{AR_DAYS[now.weekday()]}، {now.day} {AR_MONTHS[now.month - 1]}"
            .translate(AR_DIGITS))


# --------------------------------------------------------------------------
# 1. Fetch
# --------------------------------------------------------------------------

def _http_get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _clean(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&amp;", "&").replace("&#39;", "'")
                .replace("&quot;", '"').replace("&nbsp;", " ")
                .replace("&lt;", "<").replace("&gt;", ">"))
    return re.sub(r"\s+", " ", text).strip()


def _parse_date(raw):
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def fetch_headlines():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    items, seen = [], set()

    for source, url in FEEDS:
        try:
            root = ET.fromstring(_http_get(url))
        except Exception as exc:
            print(f"  ! {source}: {exc}", file=sys.stderr)
            print(f"  {source}: 0 items (failed)")
            continue

        entries = root.iter("item") if root.find(".//item") is not None else \
            root.iter("{http://www.w3.org/2005/Atom}entry")

        count = 0
        for entry in entries:
            def field(*names):
                for n in names:
                    el = entry.find(n)
                    if el is not None:
                        return el.text or el.get("href") or ""
                return ""

            title = _clean(field("title", "{http://www.w3.org/2005/Atom}title"))
            if not title:
                continue

            key = re.sub(r"\s", "", title)[:60]
            if key in seen:
                continue

            published = _parse_date(field(
                "pubDate", "{http://www.w3.org/2005/Atom}updated",
                "{http://www.w3.org/2005/Atom}published"))
            if published and published < cutoff:
                continue

            seen.add(key)
            items.append({
                "source": source,
                "title": title,
                "summary": _clean(field(
                    "description", "{http://www.w3.org/2005/Atom}summary"))[:400],
                "link": field("link", "{http://www.w3.org/2005/Atom}link"),
            })
            count += 1
        print(f"  {source}: {count} recent items")

    return items


# --------------------------------------------------------------------------
# 2. Pick + summarize (Arabic)
# --------------------------------------------------------------------------

SYSTEM_PROMPT = """أنت محرر موجز أخبار يومي يُنشر على سناب شات لجمهور سعودي.
تكتب بالعربية دائماً، حتى لو كان الخبر الأصلي بالإنجليزية.

ستصلك عناوين اليوم، بعضها بالإنجليزية. اختر {n} أخبار مهمة. المعيار صارم: \
الخبر الكبير الذي يستحق أن يتوقف له القارئ، لا مجرد خبر اليوم.

اختر فقط ما يستوفي واحداً من هذه على الأقل:
- إطلاق منتج أو ميزة من شركة تقنية يعرفها الناس ويستخدمونها
- صفقة أو استحواذ أو اكتتاب أو نتائج مالية لشركة كبرى
- قرار اقتصادي عالمي يصل أثره إلى القارئ فعلاً: سعر الفائدة (الريال مربوط
  بالدولار، فقرار الفيدرالي ينتقل إلى فوائد القروض والودائع هنا)، أسعار
  النفط، التضخم وأسعار السلع، أو سوق يستثمر فيه الناس
- تغيير في سياسة شركة كبرى يمسّ المستخدمين: أسعار، خصوصية، اشتراكات
- أزمة أو دعوى قضائية أو تحقيق يواجه شركة معروفة
- قرار حكومي سعودي أو خليجي كبير في الاقتصاد أو التقنية
- خبر اقتصادي سعودي: ميزانية، أسعار، رسوم، استثمار، قطاع كامل
- خبر عقاري في السعودية أو الخليج: أسعار، إيجارات، تمويل، مشاريع كبرى
- خبر سفر وسياحة في السعودية: مطارات، طيران، تأشيرات، وجهات، أسعار

استبعد تماماً:
- السياسة الحزبية والانتخابات والحروب والصراعات
- الجريمة والحوادث والكوارث
- الرياضة والمشاهير والفن
- الشركات الصغيرة والشركات الناشئة المجهولة والإعلانات التجارية
- المقالات والتحليلات والآراء والمراجعات
- الشائعات والتسريبات غير المؤكدة ("يُقال إن"، "مصادر تشير")
- أخبار العمالة: أعداد العمالة الوافدة، التوطين، سوق العمل، تصاريح العمل

اختبار الأهمية: هل يعرف القارئ الشركة أو يستخدم منتجها؟ وهل تغيّر هذا الخبر
شيئاً ملموساً؟ إن كان الجواب لا للسؤالين، فاستبعده.

واختبار القرب قبل ذلك: بماذا يمسّ هذا الخبر قارئاً في الرياض؟ الإجابة
الجيدة قصيرة وفي جملة واحدة: "يستخدم هذا المنتج"، "يملك هذا السهم"،
"يدفع هذا السعر"، "يعمل في هذا القطاع". إن احتاج الشرح ثلاث خطوات
للوصول إلى القارئ، فالخبر بعيد مهما كان كبيراً في مكانه.
✓ أخبار اقتصادية في السعودية
✓ أخبار عقارية في السعودية
✓ أخبار عقارية في الخليج
✓ أخبار السفر والسياحة في السعودية
✗ أخبار العمالة في السعودية
✓ Google تغيّر شيئاً في Android — ملايين هنا يستخدمونه كل يوم
✓ Apple ترفع سعر iPhone — يُشترى هنا بهذا السعر
✓ النفط يهبط — يمسّ الميزانية والوظائف والإنفاق
✗ تقرير اقتصادي أمريكي شهري لا يظهر أثره في أي سعر يدفعه القارئ
✗ "الجدل حول سقف الدين الأمريكي يتجدد في الكونغرس"
✓ "الفيدرالي يخفض الفائدة، وساما تتبعه عادة خلال ساعات"

واختبار التوقف، وهو الأخير: القارئ يمرّر بإبهامه بسرعة. هل يتوقف عند هذا
الخبر؟ ما يوقفه واحد من ثلاثة، لا غير:
- اسم يعرفه ويستخدمه، وقد تغيّر فيه شيء يخصّه
- رقم يفاجئه: سعر، مبلغ، نسبة، فرق لم يكن يتوقعه
- نتيجة يشعر بها: يدفع أكثر، أو أقل، أو يتغيّر شيء في عمله أو يومه

وما لا يوقفه: الخبر الصحيح المهم المتوقَّع. النتائج التي جاءت كما توقّع
الجميع، التحديث الدوري، الإعلان الذي لا يغيّر شيئاً بعد، الاجتماع الذي
انعقد. هذه أخبار تُقرأ في موقع اقتصادي، لا بطاقة يتوقف عندها أحد.
✗ "شركة تعلن نتائجها الفصلية مطابقة لتوقعات المحللين"
✗ "تحديث جديد للتطبيق يضيف خيارات في الواجهة"
✗ "اجتماع لبحث التعاون في مجال الطاقة"
✓ "Apple ترفع سعر iPhone 17 في السعودية 200 ريال"
✓ "أرامكو تعلن أكبر توزيع أرباح في تاريخها"
✓ "Google تلغي ميزة يستخدمها ملايين في Android"

مهم: التوقف يأتي من الخبر نفسه، لا من صياغته. لا تختر خبراً ضعيفاً ثم
تكتب له عنواناً مثيراً — العنوان المشوّق على خبر عادي يخسر القارئ مرتين:
مرة حين يقرأ، ومرة حين لا يعود.

ورتّب الأخبار التي تعيدها بهذا الاختبار: الأقوى أولاً. الخبر الأول هو
الذي سيُنشر، والبقية بدائل.

النطاق: العالم كله، بتركيز واضح على الأعمال والاقتصاد والمال والتقنية.

الأولوية بهذا الترتيب:
1. أخبار شركات التقنية الكبرى التي يعرفها الناس ويستخدمون منتجاتها:
   Google، Apple، Meta، Snap، OpenAI، Amazon، Microsoft، NVIDIA، Tesla،
   TikTok، Netflix، Samsung، Anthropic. إطلاق منتج، صفقة، نتائج مالية،
   تسريح موظفين، دعوى قضائية، تغيير يمسّ المستخدم.
2. أخبار الاقتصاد والمال العالمية التي تصل إلى هنا: أسعار الفائدة، النفط،
   التضخم، الأسواق، صفقات الاستحواذ الكبرى، أزمات الشركات. الشرط أن تذكر
   في البطاقة كيف يصل الأثر — إن لم تستطع، فالخبر ليس لنا.
3. أخبار الأعمال والتقنية والعقار والسياحة السعودية والخليجية.
4. أي خبر عالمي كبير له أثر اقتصادي واضح على القارئ هنا، لا على بلده فقط.

المعيار: هل يعرف القارئ السعودي هذه الشركة أو يستخدم منتجها؟ وهل الخبر
يغيّر شيئاً ملموساً؟ إن كان الجواب لا للسؤالين، استبعده.

استبعد: السياسة الحزبية، الحروب والصراعات، الجريمة، الرياضة، المشاهير
والفن، والأخبار المحلية في دول أخرى التي لا أثر لها خارج حدودها.

ومن ذلك الشأن الاقتصادي الداخلي لدولة أخرى، ولو بدا كبيراً: سقف الدين
الأمريكي، ميزانية الكونغرس، خلاف حزبي على الإنفاق، إعانات محلية، مؤشرات
شهرية لا يشعر بها أحد هنا. هي أخبار مهمة في بلدها ولا تغيّر شيئاً في يوم
قارئ سعودي.

أعد {n} أخبار مرتبة من الأهم إلى الأقل. سيُنشر خبر واحد فقط، والبقية بدائل \
تُستخدم إذا تعذّر إيجاد صورة مناسبة للخبر الأول.
لا تختر خبرين عن الحدث نفسه.

لكل خبر اكتب:
- headline: عنوان لا يتجاوز ٥٥ حرفاً، واضح ومباشر، بدون نقطة في نهايته
- summary: جملتان قصيرتان، لا تتجاوزان ١٥٠ حرفاً، بلغة عربية بسيطة
- takeaway: جملة واحدة قصيرة (حتى ٩٠ حرفاً) تقول شيئاً بنفسها، لا تعد بمعلومة.
  وفي خبر المالية الحكومية تحمل هذه الجملة دلالة الرقم، لا حكماً على أداء
  الدولة — انظر قواعد المالية العامة أدناه.
  سطر "وش يعنيني" لا يُعلّق على مكان أو سوق ليس فيه القارئ: شرطية مثل
  «إذا كنت تملك…» في بلد آخر تقول للقارئ إن الخبر ليس له. اجعلها ملاحظة
  استشرافية تصح لأي قارئ، وسمِّ الشيء بعينه لا «هذا التصميم»، وكل توقع
  مُحوّط بـ«قد» أو «ربما» — لا توقع مطلقاً أبداً.
  ✗ «إذا كنت تملك سيارة كهربائية في الصين فستتغير مقابضها»
  ✓ «قد لا نرى مقابض الأبواب المخفية في الموديلات القادمة»
  ممنوع التشويق: لا تكتب "أرقام تكشف..." أو "إليك ما يجب أن تعرفه" أو
  "تفاصيل مهمة عن..." — القارئ لن يفتح رابطاً، هذه آخر جملة يقرأها.
  ✗ "أرقام تكشف أي مناطق المملكة الأكثر أماناً على الطريق"
  ✓ "إذا تقود يومياً بين المدن، الفرق بين المناطق يوصل للضعف"
  ✓ "يهمك إذا كنت مستأجراً: المهلة تبدأ من تاريخ الإشعار لا من التوقيع"
- source: اسم المصدر كما ورد لك
- item: رقم الخبر كما ورد في القائمة المرقّمة (رقم فقط)
- scope: "saudi" إذا كان الخبر سعودياً أو خليجياً، و"world" لغير ذلك
- لا تذكر أي معلومة غير موجودة في العنوان والوصف المعطى لك. لا تخمّن.
- اكتب كل الأرقام بالأرقام اللاتينية (2027, 306, 13) لا بالأرقام العربية الهندية.
- تجنّب اللغة القانونية أو الرسمية حين توجد كلمة طبيعية. اكتب كما يتكلم الناس:
  ✗ القاصرين، المراهقين     ✓ الأبناء، الصغار، طلاب المدارس، الأعمار الأصغر
  ✗ ذوي الدخل المحدود        ✓ أصحاب الرواتب المتوسطة
  ✗ المستفيدين، المنتفعين    ✓ المستخدمين، الناس، العملاء
  ✗ الشريحة المستهدفة        ✓ من يهمه الأمر، الفئة
  ✗ يُشترط على المكلفين      ✓ لازم عليك، تحتاج
  القاعدة: لو ما تقولها لصديقك بهذه الصيغة، فلا تكتبها.
- اكتب أسماء الشركات والمنتجات الأجنبية بالإنجليزية كما هي:
  ✓ NVIDIA، OpenAI، Google، Meta، Snap، Apple، Microsoft، TikTok، Tesla
  ✗ إنفيديا، أوبن إيه آي، جوجل، ميتا، سناب، آبل، مايكروسوفت
  وكذلك أسماء المصادر الأجنبية: CNBC، Reuters، TechCrunch، The Verge، BBC.

- أما الأسماء السعودية والعربية فتُكتب بالعربية دائماً، حتى لو شاع تداولها
  بحروف لاتينية أو كان اسمها الرسمي بالإنجليزية:
  ✓ مرايا، أرامكو، نيوم، الدرعية، العلا، طيران ناس، تمارا، stc
  ✗ Maraya، Aramco، NEOM، Diriyah، AlUla، flynas
  الاسم العربي أقرب للقارئ، ويظهر في نص عربي أفضل من اللاتيني.
- راجع الإملاء قبل الإجابة. الأخطاء الشائعة: "باطولة" والصحيح "بطولة"، "التى" والصحيح "التي"، "الذى" والصحيح "الذي".

قواعد المقارنة بين رقمين:
- لا تقارن رقمين إلا إذا كانا قابلين للمقارنة فعلاً: نفس الوحدة، نفس الفترة،
  ونفس الأساس.
- مكوّنات المؤشر الواحد ليست متنافسة. الإيجار والغذاء كلاهما جزء من مؤشر
  أسعار المستهلك بأوزان مختلفة، فمقارنة ارتفاعهما ببعض تُضلّل القارئ.
  ✗ "الإيجارات ارتفعت 4.3% بينما الغذاء 1.5% فقط"
  ✓ "السكن أكبر بند في سلة المؤشر، فارتفاعه 4.3% هو ما رفع الرقم العام"
- إن كان أحد البندين يحرّك الرقم العام أكثر، فقل ذلك بوزنه في السلة، لا
  بمقارنته ببند آخر.
- المقارنة الصحيحة تكون بين الشيء ونفسه عبر الزمن، أو بينه وبين نظيره في
  سوق آخر.

المالية العامة والسياسات الحكومية:
- انقل الرقم ومصدره، ولا تُصدر حكماً على أداء الدولة أو وتيرة
  سياساتها. «ببطء»، «متعثر»، «متأخر»، «نجح»، «فشل» أحكام —
  لا تُكتب إلا منسوبة إلى جهة قالتها، بمصدرها.
- لا حكم على الوتيرة (سريع/بطيء) بلا مقياس معلن في البطاقة
  نفسها: مستهدف رسمي منشور، أو نظير محدد قابل للمقارنة.
  إن وُجد المقياس فاذكره وانسبه؛ وإن لم يوجد فلا حكم.
- لا تخاطب القارئ بوصفه المموِّل («كل ريال تدفعه») ولا تصغ
  إيرادات الدولة كأنها مأخوذة منه. صفها بصيغتها الرسمية.
- ربع واحد لا يصنع اتجاهاً: مقارنة سنوية لربع واحد لا تتحول
  إلى معدل نمو «سنوي» مستمر.
✗ «كل ريال تدفعه ضريبة أو رسم حكومي يظهر في هذا الرقم»
✓ «الإيرادات غير النفطية — ضرائب ورسوم وعوائد استثمار —
   بلغت 153.7 مليار ريال في الربع الثاني»
✗ «التنويع يتقدم ببطء: نمو 3% سنوياً في الدخل غير النفطي»
✓ «45% من إيرادات الربع جاءت من غير النفط — النسبة التي
   تُقاس بها خطة التنويع» (وإن وُجد مستهدف رسمي معلن،
   فاذكره بمصدره وقارن به)

- image_queries: ثلاث عبارات إنجليزية للبحث عن صورة لهذا الخبر تحديداً، مرتبة
  من الأدق إلى الأعم. كل عبارة تصف مشهداً ملموساً يمكن تصويره، لا فكرة مجردة.
  ✓ ["riyadh city skyline", "saudi arabia desert heat", "arabian gulf port"]
  إذا كان scope = "saudi" فيجب أن تتضمن كل عبارة "saudi" أو اسم مدينة سعودية
  (riyadh, jeddah, dammam, mecca, medina, khobar) — وإلا سيأتي البحث بصور من
  دول أخرى. ✗ "football stadium"   ✓ "riyadh stadium"
  وإذا كان scope = "world" فاذكر الشركة أو المكان الحقيقي بدلاً من ذلك.
  ✓ ["google headquarters building", "smartphone app icons", "stock exchange screen"]
- image_queries_ar: ثلاث كلمات مفتاحية عربية مفردة للبحث في أرشيف الصور
  السعودي — كلمة واحدة لكل عنصر، لا عبارات. البحث لا يطابق الجمل.
  ✓ ["منى", "الحجاج", "المشاعر"]   ✗ ["مخيمات منى", "المشاعر المقدسة"]
  نفس القيود: مشاهد محايدة فقط، بلا أشخاص أو جنود أو شرطة أو عنف.
  اطلب مشاهد محايدة يمكن تصويرها: مبانٍ، مكاتب، طرق، مدن، وثائق، أجهزة،
  مطارات، أسواق، طبيعة، لوحات إرشادية.
  ممنوع منعاً باتاً طلب صور: أشخاص بوجوه واضحة، جنود، أسلحة، شرطة، جيوش،
  احتجاجات، حوادث، إصابات، سجون، أو أي مشهد عنف أو نزاع — حتى لو كان الخبر
  عن أمن أو مخالفات أو قرارات عقابية. في هذه الحالات اطلب مشهداً محايداً
  تماماً مثل "government building exterior" أو "airport terminal hall".


واكتب أيضاً caption واحداً: نص المنشور المرافق، لا يتجاوز ١٢٠ حرفاً.

أجب بصيغة JSON فقط. بدون markdown وبدون أي مقدمة:
{{"caption": "...", "stories": [{{"headline": "...", "summary": "...", \
"takeaway": "...", "source": "...", "item": 0, "scope": "world", "image_queries": ["...", "...", "..."], \
"image_queries_ar": ["...", "..."]}}]}}"""


def summarize(items, already_posted=(), pinned=""):
    if not ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY is not set")

    shortlist = items[:MAX_HEADLINES_TO_MODEL]
    feed_text = "\n".join(
        f"{n}. [{i['source']}] {i['title']} — {i['summary']}"
        for n, i in enumerate(shortlist, 1)
    )

    if pinned:
        # same prompt, same rules — only the input changes: one event to
        # verify and write, instead of a feed to choose from
        user_msg = (
            f"حدث عاجل مثبّت: {pinned}\n\n"
            "تحقق منه بالبحث الآن قبل الكتابة: مصدران مستقلان على الأقل "
            "يؤكدانه، وإن كان حكومياً أو تنظيمياً فمصدر رسمي (واس، تداول، "
            "الوزارة المعنية، بيان الجهة نفسها). إن تأكد فاكتب خبراً واحداً "
            "عنه بكل القواعد أعلاه (stories بعنصر واحد). وإن لم تستطع "
            'تأكيده الآن فأعد {"stories": [], "reason": "ما الذي ينقص"} — '
            "ولا تكتب عن أي حدث آخر بدلاً منه.")
    else:
        user_msg = f"عناوين اليوم:\n\n{feed_text}"
    if already_posted:
        covered = "\n".join(f"- {h}" for h in already_posted)
        user_msg += ("\n\nأخبار نُشرت بالفعل خلال الأيام الماضية — لا تخترها ولا "
                     f"تختر خبراً عن الحدث نفسه:\n{covered}")

    # 8000 was not enough for CANDIDATES stories in Arabic, so every run paid
    # for a truncated reply and then a second, longer one. Start where it fits.
    budget = int(os.getenv("MAX_TOKENS", "").strip() or "16000")

    for attempt in range(4):
        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": budget,
            "system": SYSTEM_PROMPT.format(n=CANDIDATES),
            "messages": [{"role": "user", "content": user_msg}],
        }
        if pinned:
            # the feed run needs no tools (candidates arrive in the message);
            # a pinned event has no feed item behind it, so the model must be
            # able to search to confirm it
            payload["tools"] = [{"type": "web_search_20250305",
                                 "name": "web_search", "max_uses": 3}]

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={
                "content-type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
        )
        # Generation time scales with the budget. A fixed 120s could not
        # finish a 16000-token reply, and the socket timeout is not an
        # HTTPError, so it escaped the handler below and killed the run
        # before a card had been built.
        timeout = min(360, max(180, budget // 45))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()[:500]
            if exc.code in (429, 503, 529) and attempt < 3:
                import random
                import time as _t
                wait = (2 ** (attempt + 1)) + random.uniform(0, 1.5)
                print(f"  ! Claude API {exc.code} (transient) — backing "
                      f"off {wait:.0f}s ({attempt + 1}/3)")
                _t.sleep(wait)
                continue
            raise SystemExit(f"Claude API {exc.code}: {body}")
        except (TimeoutError, urllib.error.URLError, OSError) as exc:
            if attempt < 3:
                print(f"  ! Claude call failed ({exc}) — retrying "
                      f"({attempt + 1}/3)")
                continue
            raise SystemExit(f"Claude unreachable after 4 attempts: {exc}")

        if data.get("stop_reason") == "max_tokens":
            if budget < 32000:
                budget = min(32000, budget * 2)
                print(f"  ! reply truncated — retrying with max_tokens={budget}")
                continue
            raise SystemExit("Reply truncated even at 32000 tokens")

        text = "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text").strip()
        # Search results carry citation markup and the model sometimes copies
        # it in, often malformed: <cite index="14-1,14-2>  or  cite index="3-5
        text = re.sub(r"</?cite[^>]*>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"</?\s*cite\b[^<>]*?/?>?", "", text, flags=re.IGNORECASE)
        text = re.sub(r'\\bindex\\s*=\\s*"[0-9,\\-\\s]*"?>?', "", text)
        text = re.sub(r"[<>]", "", text)
        text = re.sub(r"\s{2,}", " ", text).strip()
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()

        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise SystemExit(f"No JSON in reply: {text[:300]}")
        result = json.loads(text[start:end + 1])

        # map each story back to the article it came from
        for story in result.get("stories", []):
            try:
                idx = int(story.get("item", 0)) - 1
            except (TypeError, ValueError):
                idx = -1
            if 0 <= idx < len(shortlist):
                story["link"] = shortlist[idx].get("link", "")
        return result

    raise SystemExit("Could not get a complete reply from Claude")


# --------------------------------------------------------------------------
# 3. Render (right-to-left)
# --------------------------------------------------------------------------

FONT_FAMILY = os.getenv("FONT_FAMILY", "NotoNaskhArabic").strip()

_font_cache = {}


# NotoNaskhArabic is the safety net: it is bundled in fonts/ and is the one
# family verified to have no gaps on either shaping path. It is only reached
# if the configured family fails the check below, which would otherwise mean
# publishing a card full of boxes.
FONT_FALLBACK = "NotoNaskhArabic"


def _candidate_paths(bold):
    weight = "Bold" if bold else "Regular"
    families = [FONT_FAMILY]
    if FONT_FALLBACK != FONT_FAMILY:
        families.append(FONT_FALLBACK)
    for family in families:
        yield Path("fonts") / f"{family}-{weight}.ttf"
        for directory in ("/usr/share/fonts/truetype/noto",
                          "/usr/share/fonts/truetype",
                          "/usr/share/fonts"):
            yield Path(directory) / f"{family}-{weight}.ttf"


def _covers_required(path):
    charset = _font_charset(str(path))
    if charset is None:
        return True                       # unreadable table — don't block on it
    missing = [c for c in REQUIRED_CHARS if ord(c) not in charset]
    if missing:
        print(f"  ! {path} is missing {''.join(missing)!r} — falling back")
        return False

    # A font can hold every letter we asked for and still have no glyph for
    # the form the shaper asks it to draw. That is invisible until you look
    # at the card, so it is checked here instead.
    gaps = _shaping_gaps(path)
    if gaps:
        shown = "".join(sorted(gaps))[:12]
        print(f"  ! {path} can't draw {len(gaps)} shaped form(s) ({shown}) "
              f"— text would render as boxes, falling back")
        return False
    return True


def _find_arabic_font(bold):
    """Locate an Arabic font that can actually draw digits, % and dashes,
    and that survives whichever shaping path is live in this environment."""
    if bold in _font_cache:
        return _font_cache[bold]

    for candidate in _candidate_paths(bold):
        if candidate.exists() and _covers_required(candidate):
            print(f"  font ({'bold' if bold else 'regular'}): {candidate}")
            _font_cache[bold] = str(candidate)
            return str(candidate)

    try:
        query = ":lang=ar:weight=" + ("bold" if bold else "regular")
        out = subprocess.run(["fc-match", "-f", "%{file}", query],
                             capture_output=True, text=True, check=True)
        if out.stdout.strip():
            print(f"  font ({'bold' if bold else 'regular'}): {out.stdout.strip()} (fallback)")
            _font_cache[bold] = out.stdout.strip()
            return _font_cache[bold]
    except Exception:
        pass
    raise SystemExit(f"No usable Arabic font for {FONT_FAMILY} — "
                     "install fonts-noto-core or bundle one in fonts/")


def load_font(size, bold=False):
    return ImageFont.truetype(_find_arabic_font(bold), size)


def _wrap(draw, text, font, max_width, kw):
    words, lines, line = text.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        shaped, _ = ar(trial)
        if draw.textlength(shaped, font=font, **kw) <= max_width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _brief_layout(draw, stories, scale, max_w, kw):
    """Measure the story blocks before drawing, same approach as the topic card."""
    f_head = load_font(int(46 * scale), bold=True)
    f_body = load_font(int(34 * scale))
    lh_head, lh_body = int(60 * scale), int(56 * scale)

    blocks, height = [], 0

    def add(kind, text, font, line_h, fill, indent, first=False):
        nonlocal height
        blocks.append({"kind": kind, "text": text, "font": font, "lh": line_h,
                       "fill": fill, "indent": indent, "first": first})
        height += line_h

    for i, story in enumerate(stories):
        if i:
            add("gap", "", None, int(40 * scale), None, 0)
            add("rule", "", None, 2, None, 0)
            add("gap", "", None, int(40 * scale), None, 0)
        else:
            add("gap", "", None, int(30 * scale), None, 0)

        head_fill = TEXT if THEME == "light" else ACCENT
        first = True
        for line in _wrap(draw, story["headline"], f_head, max_w - 44, kw):
            add("head", line, f_head, lh_head, head_fill, 44, first)
            first = False

        add("gap", "", None, int(14 * scale), None, 0)
        for line in _wrap(draw, story["summary"], f_body, max_w - 44, kw):
            add("body", line, f_body, lh_body, BODY, 44)

    return blocks, height


def render_brief(stories, out_path):
    img = Image.new("RGB", (W, H), BG_TOP)
    draw = ImageDraw.Draw(img)

    for y in range(H):
        t = y / H
        draw.line([(0, y), (W, y)],
                  fill=tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)))

    margin = 80
    right = W - margin           # everything is anchored to the RIGHT edge
    max_w = W - 2 * margin
    _, kw = ar("م")

    def rtl(xy, text, font, fill, anchor="ra"):
        shaped, k = ar(text)
        draw.text(xy, shaped, font=font, fill=fill, anchor=anchor, **k)

    # header
    draw.rectangle([right - 110, 200, right, 210], fill=ACCENT)
    title_size = 64
    while title_size > 34:
        f_title = load_font(title_size, bold=True)
        if draw.textlength(ar(BRIEF_TITLE)[0], font=f_title, **kw) <= max_w:
            break
        title_size -= 2
    rtl((right, 262 + (64 - title_size) // 3), BRIEF_TITLE, f_title, TEXT)

    TOP, BOTTOM = 400, H - 180
    available = BOTTOM - TOP

    shown = list(stories)
    scale, blocks = 1.0, None
    while blocks is None:
        for candidate in (1.0, 0.96, 0.92, 0.88):
            trial_blocks, height = _brief_layout(draw, shown, candidate, max_w, kw)
            if height <= available:
                scale, blocks = candidate, trial_blocks
                break
        if blocks is None:
            if len(shown) > 2:
                shown = shown[:-1]
                print(f"  ! content too long — trimmed to {len(shown)} stories")
            else:
                print("  ! content overflows even at minimum size")
                scale, blocks = 0.88, trial_blocks
    if scale < 1.0:
        print(f"  layout scaled to {int(scale * 100)}% to fit")

    y = TOP
    for block in blocks:
        if block["kind"] == "gap":
            y += block["lh"]
            continue
        if block["kind"] == "rule":
            draw.line([(margin, y), (right, y)], fill=RULE, width=2)
            y += block["lh"]
            continue
        if block["kind"] == "head" and block["first"]:
            r = max(5, int(7 * scale))
            draw.ellipse([right - 18, y + int(18 * scale),
                          right - 18 + 2 * r, y + int(18 * scale) + 2 * r],
                         fill=ACCENT)
        rtl((right - block["indent"], y), block["text"], block["font"], block["fill"])
        y += block["lh"]

    img.save(out_path, "PNG", optimize=True)
    return out_path


# --------------------------------------------------------------------------
# 4. Post
# --------------------------------------------------------------------------

def _git(*args):
    import subprocess as _sp
    _sp.run(["git", *args], check=True, capture_output=True)


def _git_identity():
    _git("config", "user.name", "news-bot")
    _git("config", "user.email", "news-bot@users.noreply.github.com")


def _git_push(attempts=3):
    """Push, rebasing onto anything that landed in the meantime.

    Three bots share one branch and each run pushes more than once, so losing
    a race is an ordinary event rather than an error. A bare `git push` raised
    CalledProcessError and killed the run *after* the research call and the
    rendering had already been paid for. Returns True if the push landed.
    """
    import subprocess as _sp
    for attempt in range(1, attempts + 1):
        try:
            _git("push")
            return True
        except _sp.CalledProcessError as exc:
            detail = (exc.stderr or b"").decode("utf-8", "ignore").strip()
            if attempt == attempts:
                print(f"  ! push failed after {attempts} attempts: "
                      f"{detail.splitlines()[-1][:160] if detail else '?'}")
                return False
            print(f"  · push rejected — rebasing and retrying "
                  f"({attempt}/{attempts - 1})")
            try:
                _git("pull", "--rebase", "--autostash")
            except _sp.CalledProcessError as pull_exc:
                pull_detail = (pull_exc.stderr or b"").decode("utf-8", "ignore")
                print(f"  ! rebase failed: {pull_detail.strip()[:160]}")
                return False
    return False


def commit_and_push(path, message):
    """Commit one file. Used for the card and for the posted-history state."""
    import subprocess as _sp
    try:
        _git_identity()
        _git("add", str(path))
        try:
            _git("commit", "-m", message)
        except _sp.CalledProcessError:
            return                      # nothing changed
        _git("pull", "--rebase", "--autostash")
        _git_push()
    except Exception as exc:
        print(f"  ! couldn't commit {path}: {exc}")


IMAGE_SOURCE = os.getenv("IMAGE_SOURCE", "none").strip()
if IMAGE_SOURCE == "pexels":            # friendlier alias for "stock"
    IMAGE_SOURCE = "stock"
# openverse (free, no key) | article (publisher photo) | stock (Pexels, needs key) | none

OG_IMAGE_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE)
OG_IMAGE_ALT_RE = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:image["\']',
    re.IGNORECASE)


def fetch_article_photo(url, out_path):
    """Pull the lead photo an article publishes in its og:image tag.

    IMPORTANT: that photo belongs to the publisher. Only use this for sources
    whose terms permit republication, and always show the credit the card
    renders from the returned domain.
    Returns (path, domain) or (None, None).
    """
    if not url:
        return None, None

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read(400_000).decode("utf-8", "ignore")
    except Exception as exc:
        print(f"  ! couldn't read {url}: {exc}")
        return None, None

    match = OG_IMAGE_RE.search(html) or OG_IMAGE_ALT_RE.search(html)
    if not match:
        print(f"  ! no og:image on {url}")
        return None, None

    img_url = urllib.parse.urljoin(url, match.group(1))
    domain = urllib.parse.urlparse(url).netloc.replace("www.", "")
    try:
        req = urllib.request.Request(img_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        if len(data) < 15_000:
            print("  ! og:image too small — probably a logo, skipping")
            return None, None
        _clear_generated_marker(out_path)
        Path(out_path).write_bytes(data)
        if looks_like_a_graphic(out_path):
            print("  ! the article's image is a graphic, not a photo — skipping")
            return None, None
    except Exception as exc:
        print(f"  ! photo download failed: {exc}")
        return None, None

    if _recent_reject(out_path):
        return None, None
    print(f"    photo: article image from {domain}")
    return str(out_path), domain


DOMAIN_CREDITS = {
    "spa.gov.sa": "واس",
    "sabq.org": "صحيفة سبق",
    "makkahnewspaper.com": "صحيفة مكة",
    "al-madina.com": "المدينة",
    "aleqt.com": "الاقتصادية",
    "argaam.com": "أرقام",
    "alriyadh.com": "الرياض",
    "alwatan.com.sa": "الوطن",
    "alarabiya.net": "العربية",
    "alekhbariya.net": "الإخبارية",
    "argaam.com": "أرقام",
    "aawsat.com": "الشرق الأوسط",
    "alarabiya.net": "العربية",
    "okaz.com.sa": "عكاظ",
    "alyaum.com": "اليوم",
}


def _openverse_search(query, page_size=12):
    """Search Openverse for openly licensed images. No API key needed.

    Anonymous access is rate limited, so a 429 here is normal on repeat runs.
    """
    url = ("https://api.openverse.org/v1/images/"
           f"?q={urllib.parse.quote(query)}&page_size={page_size}"
           "&license_type=commercial,modification&mature=false")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            results = json.loads(resp.read()).get("results", [])
        print(f"    Openverse: {len(results)} results for {query!r}")
        return results
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            print("  ! Openverse rate limited (anonymous quota) — try again later")
        else:
            print(f"  ! Openverse HTTP {exc.code} for {query!r}")
        return []
    except Exception as exc:
        print(f"  ! Openverse error for {query!r}: {exc}")
        return []


def _ov_score(item, terms):
    text = " ".join(filter(None, [
        item.get("title") or "",
        " ".join(t.get("name", "") for t in item.get("tags") or []),
    ])).lower()
    if not text:
        return 0
    hits = sum(1 for t in terms if t in text)
    wide = (item.get("width") or 0) >= (item.get("height") or 1)
    return hits * 10 + (3 if wide else 0) + _geo_adjust(text)


def fetch_openverse_photo(queries, out_path, need_saudi=None, min_hits=None,
                          subject_mode=False):
    """Fetch an openly licensed photo. Returns (path, credit) or (None, None).

    Only commercial-use, modification-allowed licences are requested, and the
    creator and licence are returned so the card can credit them.
    """
    if isinstance(queries, str):
        queries = [queries]
    queries = [q.strip() for q in queries if q and q.strip()]
    if not queries:
        return None, None

    candidates = []
    for query in queries:
        terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
        results = _openverse_search(query)
        if not results:
            continue
        for item in results:
            described = " ".join(filter(None, [
                item.get("title") or "",
                " ".join(t.get("name", "") for t in item.get("tags") or []),
            ]))
            if not _image_is_safe(described):
                continue
            want_saudi = REQUIRE_SAUDI_CONTEXT if need_saudi is None else need_saudi
            if want_saudi and _geo_adjust(described) <= 0:
                continue
            want_hits = MIN_TERM_HITS if min_hits is None else min_hits
            if _term_hits(described, terms) < want_hits:
                continue
            score = _ov_score(item, terms)
            # a keynote photo IS the story when searching for a person or a
            # company, so only penalise generic event shots for news
            if not subject_mode and any(h in described.lower()
                                        for h in MEETING_HINTS):
                score -= 15
            candidates.append((score, query, item))
        # Stop only once something is good enough to actually publish. This
        # used to break at a hardcoded 10, so raising MIN_PHOTO_SCORE — the
        # obvious thing to do after a bad photo — made the search worse: it
        # still stopped at the mediocre match, then rejected it against the
        # higher bar and returned nothing, and REQUIRE_PHOTO turned that into
        # no card at all. Same rule as fetch_spa_photo.
        if any(c[0] >= MIN_PHOTO_SCORE for c in candidates):
            break

    if not candidates:
        note = " with Saudi context" if REQUIRE_SAUDI_CONTEXT else ""
        print(f"  ! no openly licensed photo found{note}")
        return None, None

    candidates.sort(key=lambda c: -c[0])
    if candidates[0][0] < MIN_PHOTO_SCORE:
        print(f"  ! best match scored {candidates[0][0]:.0f}, below "
              f"{MIN_PHOTO_SCORE} — posting without a photo instead")
        return None, None

    # work down the ranked list — one dead host shouldn't cost us the photo
    data, best, best_score, best_query = None, None, 0, None
    for score, query, item in candidates[:5]:
        for field in ("url", "thumbnail"):
            link = item.get(field)
            if not link:
                continue
            try:
                req = urllib.request.Request(link,
                                             headers={"User-Agent": USER_AGENT})
                try:
                    with urllib.request.urlopen(req, timeout=45) as resp:
                        payload = resp.read()
                except urllib.error.HTTPError as exc:
                    if exc.code != 429:
                        raise
                    # Anonymous Openverse rate-limits in short bursts: the
                    # Steineke photo was FOUND and then lost to two 429s,
                    # while the same query succeeded a minute later on the
                    # next frame. One brief pause and one retry of the same
                    # URL; a second 429 counts as failure exactly as before.
                    import time as _t
                    print(f"  ! {field} hit 429 — pausing 3s and retrying once")
                    _t.sleep(3)
                    with urllib.request.urlopen(req, timeout=45) as resp:
                        payload = resp.read()
            except Exception as exc:
                print(f"  ! {field} failed ({exc}) — trying the next image")
                continue
            if len(payload) < 8_000:
                continue
            # Openverse never ran the graphic check — article, SPA, Commons
            # and LoC all did, and the one path without it delivered the same
            # green chart to two stories. Check the bytes before accepting.
            _clear_generated_marker(out_path)
            Path(out_path).write_bytes(payload)
            if looks_like_a_graphic(out_path):
                break                     # next candidate, not next field
            data, best, best_score, best_query = payload, item, score, query
            if field == "thumbnail":
                print("    (using Openverse thumbnail — original host refused)")
            break
        if data:
            break

    if data is None:
        print("  ! every usable Openverse candidate failed to download")
        return None, None
    _clear_generated_marker(out_path)
    Path(out_path).write_bytes(data)

    creator = (best.get("creator") or "").strip() or best.get("source", "Openverse")
    licence = (best.get("license") or "").upper()
    version = best.get("license_version") or ""
    credit = f"{creator} / CC {licence} {version}".strip()

    if _recent_reject(out_path):
        return None, None
    print(f"    photo: {best.get('title') or '(untitled)'} — {credit} "
          f"[{best_query}]")
    return str(out_path), credit


# --------------------------------------------------------------------------
# Wikimedia Commons — freely licensed media, no key
# --------------------------------------------------------------------------
# Two lookups per keyword, because they find different things. Searching
# Commons finds places, buildings and objects. Asking Wikipedia for an
# article's lead image finds people: a portrait is usually filed against the
# person's article rather than under a caption anyone would search for.

# Both Wikimedia and the Library of Congress want a descriptive agent naming
# the project and a contact. USER_AGENT above is a browser-ish string, and LoC
# answers it with a flat 403 — verified, not guessed.
PUBLIC_API_UA = ("daily-news-snap/1.0 "
                 "(https://github.com/khalidonline/daily-news-snap) Python-urllib")

# ar first: a Saudi subject is far more likely to have an Arabic article, and
# its lead image is the one a Saudi reader would recognise.
WIKI_LANGS = tuple(l for l in (os.getenv("WIKI_LANGS", "").strip()
                               or "ar,en").split(",") if l.strip())

COMMONS_API = "https://commons.wikimedia.org/w/api.php"

# Commons is free-content only, but "free" there still covers licences we
# can't use: match what we ask Openverse for — commercial use and modification.
_BAD_LICENCE = re.compile(
    r"(non-?commercial|no-?derivat|\bnc\b|\bnd\b|fair\s*use)", re.IGNORECASE)


def _wiki_get(url, params, timeout=30, label="wikimedia"):
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{query}", headers={
        "User-Agent": PUBLIC_API_UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        print(f"  ! {label} HTTP {exc.code}")
    except Exception as exc:
        print(f"  ! {label} request failed: {exc}")
    return {}


def _commons_meta(info, key):
    """One extmetadata value, or ''. The values arrive as HTML."""
    field = (info.get("extmetadata") or {}).get(key) or {}
    return _clean(str(field.get("value", "")))


def _commons_licence_ok(info):
    licence = " ".join(_commons_meta(info, k) for k in
                       ("License", "LicenseShortName", "UsageTerms"))
    if not licence.strip():
        return False               # unknown licence — never guess in our favour
    return not _BAD_LICENCE.search(licence)


_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
# Credit is a provenance blob, not an author field: links, galleries, dates
# and several labels run together. The name, when it is in there, is labelled.
# the label is matched case-insensitively, the name is not: the capture
# relies on capitalisation to know where a name starts and stops
_CREDIT_AUTHOR_RE = re.compile(
    r"(?i:photographer|photograph by|author|artist|creator)\s*:?\s*"
    r"([A-Z][\w.\-']*(?:\s+[A-Z][\w.\-']*){0,2})")


def _commons_person(text):
    """A person's name out of a metadata field, or "".

    Strips links first: some files carry only a URL where the photographer
    belongs, and printing it puts a raw hyperlink on the card.
    """
    text = re.sub(r"\s+", " ", _URL_RE.sub(" ", text or "")).strip(" ,;·-:")
    if not text:
        return ""
    match = _CREDIT_AUTHOR_RE.search(text)
    if match:
        return match.group(1).strip(" ,;")
    if ":" in text:            # still a labelled blob, no name we can trust
        return ""
    return text


def _commons_credit(info):
    """Most Commons files are CC BY-SA: the credit line is not optional."""
    artist = _commons_person(_commons_meta(info, "Artist")) \
        or _commons_person(_commons_meta(info, "Credit"))
    if len(artist) > 60:                     # some Artist fields are a paragraph
        artist = artist[:60].rsplit(" ", 1)[0].rstrip(" ,;")
    licence = _commons_meta(info, "LicenseShortName").strip()
    # never a bare licence with nobody named — say where it came from instead
    return " / ".join(p for p in (artist or "Wikimedia Commons", licence) if p)


def _commons_described(page, info):
    """Everything the file says about itself, for matching a query."""
    return " ".join(filter(None, [
        _commons_depicts(page, info),
        _commons_meta(info, "Categories").replace("|", " "),
    ]))


def _commons_depicts(page, info):
    """What the picture actually shows — no categories.

    Categories classify the SUBJECT, not the image. A portrait of someone who
    once served is filed under military categories, and judging it by those
    rejected a perfectly ordinary headshot: searching Yuan Geng lost his
    photograph to 'Armed' and 'Army' sitting in his biography.
    """
    return " ".join(filter(None, [
        page.get("title", "").replace("File:", ""),
        _commons_meta(info, "ObjectName"),
        _commons_meta(info, "ImageDescription"),
    ]))


# Categories are still worth checking, but only against words that describe a
# scene and could never describe a career. "Army" and "police" say what a
# person was; "explosion" and "riot" say what is in the frame.
_AFFILIATION_TERMS = {"military", "army", "armed", "soldier", "soldiers",
                      "troops", "police"}
# Commons names categories in the plural — "Riots", "Explosions" — while the
# blocklist holds singulars, so an optional s is the difference between this
# check working and doing nothing at all.
_CATEGORY_BLOCKED_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in BLOCKED_IMAGE_TERMS
                      if t not in _AFFILIATION_TERMS) + r")s?\b",
    re.IGNORECASE)


def _commons_safe(page, info):
    """Reject on what the picture shows, and on categories that can only
    describe content. Keeps rule 3 without vetoing a soldier's headshot."""
    if not _image_is_safe(_commons_depicts(page, info)):
        return False
    categories = _commons_meta(info, "Categories").replace("|", " ")
    match = _CATEGORY_BLOCKED_RE.search(categories)
    if match:
        print(f"  ! skipped an image ({match.group(0)!r} in its categories)")
        return False
    return True


def _commons_fileinfo(titles):
    """imageinfo + licence metadata for File: titles. Titles missing here are
    hosted locally on a Wikipedia rather than on Commons, which usually means
    they are not freely licensed — dropping them is the point."""
    titles = [t for t in titles if t][:20]
    if not titles:
        return []
    data = _wiki_get(COMMONS_API, {
        "action": "query", "format": "json", "titles": "|".join(titles),
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|size|mime", "iiurlwidth": "1600",
    }, label="Commons")
    pages = (data.get("query") or {}).get("pages", {})
    out = []
    for page in pages.values():
        if "missing" in page or not page.get("imageinfo"):
            continue
        out.append((page, page["imageinfo"][0]))
    return out


_REJECTED_FILE = Path("images/rejected.txt")
_rejected_cache = None


def _owner_rejected(title):
    """True for a Commons file title the owner has vetoed by review.

    images/rejected.txt is a content file: one title per line, with or
    without the File: prefix, # comments allowed. A rejected file never
    reaches a card, a probe count, or a portrait slot again — rejecting
    a candidate in the catalogue must be a decision made once."""
    global _rejected_cache
    if _rejected_cache is None:
        entries = set()
        try:
            for ln in _REJECTED_FILE.read_text("utf-8").splitlines():
                ln = ln.split("#")[0].strip()
                if ln:
                    entries.add(ln.removeprefix("File:")
                                .replace("_", " ").casefold())
        except Exception:
            pass
        _rejected_cache = entries
    t = str(title or "").removeprefix("File:").replace("_", " ").casefold()
    if t in _rejected_cache:
        return True
    # a trailing * vetoes by prefix: two Deir Jarir photos were vetoed
    # and two OTHERS surfaced — a wrong-subject family needs one line
    return any(r.endswith("*") and t.startswith(r[:-1])
               for r in _rejected_cache)


def _commons_search(term, limit=12):
    data = _wiki_get(COMMONS_API, {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": term, "gsrnamespace": "6", "gsrlimit": str(limit),
        "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime",
        "iiurlwidth": "1600",
    }, label="Commons")
    pages = (data.get("query") or {}).get("pages", {})
    found = [(p, p["imageinfo"][0]) for p in pages.values()
             if p.get("imageinfo") and not _owner_rejected(p.get("title"))]
    print(f"    Commons: {len(found)} files for {term!r}")
    return found


def _wikipedia_lead_files(term):
    """File: titles of the lead images of articles matching this term.

    A portrait of a person is almost never captioned with a phrase anyone
    would search for, but it is nearly always the lead image of their article.
    """
    titles = []
    for lang in WIKI_LANGS:
        data = _wiki_get(f"https://{lang}.wikipedia.org/w/api.php", {
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": term, "gsrnamespace": "0", "gsrlimit": "3",
            "redirects": "1", "prop": "pageimages", "piprop": "name",
        }, label=f"{lang}.wikipedia")
        pages = list((data.get("query") or {}).get("pages", {}).values())
        # search ranks a loosely related article first often enough to matter,
        # so an exact title match jumps the queue
        pages.sort(key=lambda p: (p.get("title", "").strip().lower()
                                  != term.strip().lower()))
        # The lead image is exempt from the term-hit check below, because it
        # is the article's own picture. That only holds if the article is
        # really about what we asked for — so require the title to carry every
        # word of the query. Searching for "علي النعيمي" otherwise returned the
        # article for a different النعيمي and, with it, a photograph of the
        # wrong man.
        wanted = [w for w in re.split(r"\W+", term.lower()) if len(w) > 2]
        # whole words, not substrings: an Arabic name fragment turns up inside
        # unrelated words, which is how a different النعيمي got matched
        checks = [(_latin_word_re([w]) if w.isascii() else _arabic_word_re([w]))
                  for w in wanted]
        for page in pages:
            name = page.get("pageimage")
            title = (page.get("title") or "").lower()
            if not name or not checks:
                continue
            if not all(rx.search(title) for rx in checks):
                continue
            titles.append(f"File:{name}")
    if titles:
        print(f"    Wikipedia lead image(s) for {term!r}: {len(titles)}")
    titles = [t for t in titles if not _owner_rejected(t)]
    return titles


def fetch_commons_photo(queries, out_path, need_saudi=None, min_hits=None,
                        subject_mode=False):
    """Fetch a freely licensed photo from Wikimedia Commons.

    Returns (path, credit) or (None, None). Same signature as
    fetch_openverse_photo so the two are interchangeable.
    """
    if isinstance(queries, str):
        queries = [queries]
    queries = [q.strip() for q in queries if q and q.strip()]
    if not queries:
        return None, None

    want_saudi = REQUIRE_SAUDI_CONTEXT if need_saudi is None else need_saudi
    want_hits = MIN_TERM_HITS if min_hits is None else min_hits

    candidates = []
    for query in queries:
        terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
        found = _commons_search(query)
        lead = _commons_fileinfo(_wikipedia_lead_files(query))
        for page, _info in lead:
            page["_lead"] = True      # scored differently: see below
        found += lead

        for page, info in found:
            if (info.get("mime") or "").startswith("image/svg"):
                continue                      # a diagram, never a photograph
            if not _commons_licence_ok(info):
                continue
            described = _commons_described(page, info)
            if not _commons_safe(page, info):
                continue
            if want_saudi and _geo_adjust(described) <= 0:
                continue
            hits = _term_hits(described, terms)
            # A lead image is the article's own picture of the subject, so it
            # is on-topic even when its filename shares no words with the
            # query — that is exactly the portrait case this source is for.
            from_article = page.get("_lead", False)
            if not from_article and hits < want_hits:
                continue
            score = hits * 10 + _geo_adjust(described)
            if (info.get("width") or 0) >= (info.get("height") or 1):
                score += 3
            if from_article:
                # The article title had to carry every word of the query to
                # get here, so this really is a picture of the subject. That
                # beats a filename that merely happens to contain the words:
                # searching "علي النعيمي" scored a different النعيمي above the
                # correct man, because _term_hits matches substrings and short
                # Arabic tokens turn up inside unrelated words.
                score += 25
            if not subject_mode and any(h in described.lower()
                                        for h in MEETING_HINTS):
                score -= 15
            candidates.append((score, query, page, info))

        if any(c[0] >= MIN_PHOTO_SCORE for c in candidates):
            break

    if not candidates:
        print("  ! no Commons photo found")
        return None, None

    candidates.sort(key=lambda c: -c[0])
    if candidates[0][0] < MIN_PHOTO_SCORE:
        print(f"  ! best Commons match scored {candidates[0][0]:.0f}, below "
              f"{MIN_PHOTO_SCORE} — skipping")
        return None, None

    for score, query, page, info in candidates[:5]:
        # thumburl is a resized copy; originals run to tens of megabytes
        for link in (info.get("thumburl"), info.get("url")):
            if not link:
                continue
            try:
                req = urllib.request.Request(link, headers={"User-Agent": PUBLIC_API_UA})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = resp.read()
            except Exception as exc:
                print(f"  ! Commons download failed ({exc}) — trying next")
                continue
            if len(data) < 15_000:
                continue
            _clear_generated_marker(out_path)
            Path(out_path).write_bytes(data)
            if looks_like_a_graphic(out_path):
                break                        # try the next candidate instead
            if _recent_reject(out_path):
                continue
            credit = _commons_credit(info)
            print(f"    photo: {page.get('title', '')[:70]} — {credit} [{query}]")
            return str(out_path), credit

    print("  ! every Commons candidate failed to download")
    return None, None


def fetch_commons_portrait(name, out_path):
    """A free photograph of a named person, or (None, None).

    Deliberately stricter than fetch_commons_photo. A portrait of the wrong
    person is worse than no portrait: nothing downstream would catch it, and
    the card would put a stranger's face on someone else's story. Searching
    "علي النعيمي" returned a different النعيمي precisely this way, because the
    ordinary term scoring matches substrings and a short Arabic token turns up
    inside unrelated words.

    Two ways in, both requiring the whole name:
      1. the lead image of an article whose title carries every word of it
      2. a Commons file whose own description names the person in full
    """
    name = (name or "").strip()
    parts = [p for p in re.split(r"\W+", name) if len(p) > 2]
    if not parts:
        return None, None
    checks = [(_latin_word_re([p]) if p.isascii() else _arabic_word_re([p]))
              for p in parts]

    candidates = []
    for page, info in _commons_fileinfo(_wikipedia_lead_files(name)):
        candidates.append((2, page, info))          # the subject's own article
    for page, info in _commons_search(name):
        # The name must be in the FILE TITLE, not merely somewhere in the
        # description. Anyone by that name appearing in a caption was enough
        # before, which put a US embassy reception under "Robert Plath" and a
        # football match under "Jack Bogle". A photograph of someone else is
        # the one failure nothing downstream can catch.
        if all(rx.search(page.get("title", "")) for rx in checks):
            candidates.append((1, page, info))

    for rank, page, info in sorted(candidates, key=lambda c: -c[0])[:6]:
        if (info.get("mime") or "").startswith("image/svg"):
            continue
        if not _commons_licence_ok(info):
            continue
        if not _commons_safe(page, info):
            continue
        for link in (info.get("thumburl"), info.get("url")):
            if not link:
                continue
            try:
                req = urllib.request.Request(
                    link, headers={"User-Agent": PUBLIC_API_UA})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = resp.read()
            except Exception:
                continue
            if len(data) < 15_000:
                continue
            _clear_generated_marker(out_path)
            Path(out_path).write_bytes(data)
            if looks_like_a_graphic(out_path):
                break
            credit = _commons_credit(info)
            print(f"    portrait: {page.get('title', '')[:60]} — {credit}")
            return str(out_path), credit
    return None, None


# --------------------------------------------------------------------------
# Library of Congress — public domain photography, no key
# --------------------------------------------------------------------------
# Strong on historical subjects, which is where an open-licence search usually
# comes back empty. The API is slow and drops connections often enough that
# every call here is best-effort.

LOC_SEARCH = "https://www.loc.gov/photos/"
LOC_CREDIT = "Library of Congress"

# access_restricted is not the signal it looks like — items whose advisory
# reads "No known restrictions on publication" still come back True. The
# advisory text is what actually says whether we may publish, so require it
# to say so, and reject anything hedged.
_LOC_CLEAR = re.compile(r"no known restrictions", re.IGNORECASE)
_LOC_HEDGED = re.compile(
    r"(may be restricted|not been evaluated|not evaluated|permission|"
    r"rights status|contact)", re.IGNORECASE)


def _loc_search(term, limit=12):
    url = (f"{LOC_SEARCH}?q={urllib.parse.quote(term)}"
           f"&fo=json&c={limit}&at=results")
    req = urllib.request.Request(url, headers={"User-Agent": PUBLIC_API_UA,
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            results = json.loads(resp.read()).get("results", [])
    except Exception as exc:
        print(f"  ! Library of Congress unavailable for {term!r}: {exc}")
        return []
    print(f"    Library of Congress: {len(results)} results for {term!r}")
    return results


def _loc_may_publish(item):
    advisory = " ".join(str(item.get(k) or "") for k in
                        ("rights_advisory", "rights", "rights_information"))
    if not _LOC_CLEAR.search(advisory):
        return False
    return not _LOC_HEDGED.search(advisory)


def _loc_image_url(result, item):
    """The service copy. image_url is a 150px thumbnail — unusable on a card."""
    link = item.get("service_medium") or ""
    if not link:
        for candidate in (result.get("image_url") or []):
            if candidate.lower().split("#")[0].endswith((".jpg", ".jpeg")):
                link = candidate
                break
    link = link.split("#")[0]
    # some records point at a shared placeholder graphic instead of a scan
    if not link or link.lower().endswith(".gif"):
        return ""
    return link


def fetch_loc_photo(queries, out_path, need_saudi=None, min_hits=None,
                    subject_mode=False):
    """Fetch a public domain photo from the Library of Congress.

    Returns (path, credit) or (None, None). Only items whose own rights
    statement says there are no known restrictions are used.
    """
    if isinstance(queries, str):
        queries = [queries]
    queries = [q.strip() for q in queries if q and q.strip()]
    if not queries:
        return None, None

    want_saudi = REQUIRE_SAUDI_CONTEXT if need_saudi is None else need_saudi
    want_hits = MIN_TERM_HITS if min_hits is None else min_hits

    candidates = []
    for query in queries:
        terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
        for result in _loc_search(query):
            item = result.get("item") or {}
            if not _loc_may_publish(item):
                continue
            described = " ".join(filter(None, [
                str(result.get("title") or ""),
                " ".join(str(s) for s in (result.get("subject") or [])),
                str(item.get("summary") or ""),
            ]))
            if not _image_is_safe(described):
                continue
            if want_saudi and _geo_adjust(described) <= 0:
                continue
            hits = _term_hits(described, terms)
            if hits < want_hits:
                continue
            score = hits * 10 + _geo_adjust(described)
            if not subject_mode and any(h in described.lower()
                                        for h in MEETING_HINTS):
                score -= 15
            link = _loc_image_url(result, item)
            if link:
                candidates.append((score, query, result, link))

        if any(c[0] >= MIN_PHOTO_SCORE for c in candidates):
            break

    if not candidates:
        print("  ! no Library of Congress photo found")
        return None, None

    candidates.sort(key=lambda c: -c[0])
    if candidates[0][0] < MIN_PHOTO_SCORE:
        print(f"  ! best Library of Congress match scored "
              f"{candidates[0][0]:.0f}, below {MIN_PHOTO_SCORE} — skipping")
        return None, None

    for score, query, result, link in candidates[:5]:
        try:
            req = urllib.request.Request(link,
                                         headers={"User-Agent": PUBLIC_API_UA})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
        except Exception as exc:
            print(f"  ! LoC download failed ({exc}) — trying next")
            continue
        if len(data) < 15_000:
            continue
        _clear_generated_marker(out_path)
        Path(out_path).write_bytes(data)
        if looks_like_a_graphic(out_path):
            continue
        if _recent_reject(out_path):
            continue
        print(f"    photo: {str(result.get('title'))[:70]} — "
              f"{LOC_CREDIT} [{query}]")
        return str(out_path), LOC_CREDIT

    print("  ! every Library of Congress candidate failed to download")
    return None, None


def _pexels_search(query, per_page=12):
    url = (f"https://api.pexels.com/v1/search?per_page={per_page}"
           f"&orientation=landscape&query={urllib.parse.quote(query)}")
    req = urllib.request.Request(url, headers={"Authorization": PEXELS_API_KEY})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read()).get("photos", [])
    except urllib.error.HTTPError as exc:
        print(f"  ! Pexels {exc.code} for {query!r}")
        return []
    except Exception as exc:
        print(f"  ! Pexels error for {query!r}: {exc}")
        return []


SAUDI_HINTS = ("saudi", "riyadh", "jeddah", "dammam", "mecca", "makkah",
               "medina", "madinah", "khobar", "arabia", "arabian", "gulf")

# well-known places that would misrepresent a Saudi story
FOREIGN_HINTS = ("barcelona", "madrid", "london", "paris", "berlin", "rome",
                 "tokyo", "beijing", "moscow", "new york", "dubai", "doha",
                 "abu dhabi", "kuwait", "cairo", "istanbul", "camp nou",
                 "wembley", "eiffel", "colosseum")


def _term_hits(text, terms):
    low = (text or "").lower()
    return sum(1 for t in terms if t and t in low)


def _geo_adjust(text):
    """+ for Saudi context, - for a recognisable foreign landmark."""
    low = (text or "").lower()
    if any(h in low for h in FOREIGN_HINTS) and not any(h in low for h in SAUDI_HINTS):
        return -25
    if any(h in low for h in SAUDI_HINTS):
        return 8
    return 0


def _score(photo, terms):
    """How well does this photo's own description match what we asked for?"""
    alt = (photo.get("alt") or "").lower()
    if not alt:
        return 0
    hits = sum(1 for t in terms if t in alt)
    # a short, on-point caption beats a long one that happens to contain the word
    return hits * 10 - len(alt.split()) * 0.05 + _geo_adjust(alt)


def fetch_photo(queries, out_path, need_saudi=None):
    """Fetch a licence-clear photo from Pexels, trying each query in turn and
    picking the result whose description best matches. Returns a path or None.

    Pexels images are free to use commercially without attribution. Never pull
    photos from news sites — those are licensed to the publisher.
    """
    if not PEXELS_API_KEY:
        print("  ! PEXELS_API_KEY not set — rendering without a photo")
        return None

    if isinstance(queries, str):
        queries = [queries]
    queries = [q.strip() for q in queries if q and q.strip()]
    if not queries:
        return None

    best, best_score, best_query = None, -999, None
    for query in queries:
        terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
        photos = _pexels_search(query)
        if not photos:
            print(f"    no results for {query!r}")
            continue

        for photo in photos:
            if not _image_is_safe(photo.get("alt")):
                continue
            want_saudi = REQUIRE_SAUDI_CONTEXT if need_saudi is None else need_saudi
            if want_saudi and _geo_adjust(photo.get("alt")) <= 0:
                continue
            if _term_hits(photo.get("alt"), terms) < MIN_TERM_HITS:
                continue
            score = _score(photo, terms)
            if any(h in (photo.get("alt") or "").lower() for h in MEETING_HINTS):
                score -= 15
            if score > best_score:
                best, best_score, best_query = photo, score, query

        # A clear match on an early (more specific) query wins outright — but
        # only if it clears the publish bar, or we'd stop searching while
        # holding something we're about to reject. See fetch_openverse_photo.
        if best_score >= MIN_PHOTO_SCORE:
            break

    if best is None:
        print("  ! no photo found — rendering without one")
        return None

    if best_score < MIN_PHOTO_SCORE:
        # one decimal: the length tiebreak makes near-misses land just under
        # the bar, and "scored 30, below 30" reads like a bug
        print(f"  ! best Pexels match scored {best_score:.1f}, below "
              f"{MIN_PHOTO_SCORE} — posting without a photo instead")
        return None

    src = best["src"].get("large2x") or best["src"]["large"]
    try:
        with urllib.request.urlopen(src, timeout=60) as resp:
            Path(out_path).write_bytes(resp.read())
    except Exception as exc:
        print(f"  ! photo download failed: {exc}")
        return None
    if looks_like_a_graphic(out_path):
        return None                       # Pexels had the same blind spot

    if _recent_reject(out_path):
        return None
    print(f"    photo: {best.get('alt') or '(no description)'} "
          f"— {best.get('photographer')} / Pexels [{best_query}]")
    return str(out_path)
MAX_SEARCHES = int(os.getenv("MAX_SEARCHES", "6"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "16000"))
POINTS = int(os.getenv("POINTS", "3"))


# --------------------------------------------------------------------------
# Light "story" card — cream background, one photo, very little text
# --------------------------------------------------------------------------

def _rounded(img, radius):
    """Round the corners of a photo, as in the reference layout."""
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, *img.size], radius, fill=255)
    out = Image.new("RGBA", img.size)
    out.paste(img, (0, 0), mask)
    return out


# The three brand marks, all drawn from the owner's circular badge asset
# (images/brand/badge.png, 1000x1000 RGBA). The badge is on unless the owner
# turns it off; GitHub passes "" for an unset variable, which must not
# silently hide a brand mark. A missing asset logs loudly and draws nothing
# rather than inventing a stand-in — a placeholder monogram shipped to a
# live card once, which is exactly what this rule exists to prevent.
BRAND_BADGE = (os.getenv("BRAND_BADGE", "").strip() or "1") != "0"
BADGE_FILE = Path(os.getenv("BADGE_FILE", "").strip()
                  or "images/brand/badge.png")
_badge_cache = {}


def brand_badge(size, alpha=255):
    """The circular badge at `size` px, circle-masked, or None."""
    if not BRAND_BADGE:
        return None
    key = (size, alpha)
    if key not in _badge_cache:
        try:
            src = Image.open(BADGE_FILE).convert("RGBA")                        .resize((size, size), Image.LANCZOS)
        except Exception as exc:
            print(f"  ! brand badge unavailable ({exc}) — cards go unmarked")
            _badge_cache[key] = None
            return None
        mask = Image.new("L", (size * 4, size * 4), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size * 4 - 1, size * 4 - 1],
                                     fill=255)
        mask = mask.resize((size, size), Image.LANCZOS)
        if alpha < 255:
            mask = mask.point(lambda v: v * alpha // 255)
        src.putalpha(mask)
        _badge_cache[key] = src
    return _badge_cache[key]


def draw_brand_badge(img, xy=(96, 128), size=150):
    """Mark 1 — the badge top-left on every card of every bot."""
    badge = brand_badge(size)
    if badge:
        img.paste(badge, xy, badge)


def seal_photo(img, box_right, box_bottom, size=120, inset=26):
    """Mark 2 — translucent seal inside the photo box, bottom-right.

    Only ever called when a photo exists; 55% alpha so it reads as a
    watermark, not a sticker. Applies to every photo without exception —
    agency press graphics that carry their own logos included.
    """
    badge = brand_badge(size, alpha=140)          # 55% of 255
    if badge:
        img.paste(badge, (box_right - inset - size,
                          box_bottom - inset - size), badge)


def closing_seal(img, centre_y, size=120):
    """Mark 3 — full-strength badge centred where the footer rule was."""
    badge = brand_badge(size)
    if badge:
        img.paste(badge, (W // 2 - size // 2, centre_y - size // 2), badge)


def _draw_header(draw, rtl, right, y=170):
    """Bar + label, shared by both news renderers.

    Breaking variant — keyed off pinned-event mode, NOT a separate
    renderer: when the watcher pinned an event the card announces itself
    with the عاجل label and the accent red replaces the emerald. The 20:00
    fallback and every scheduled run keep the normal label and colour.
    """
    label, colour = BRAND, BRAND_INK
    if PINNED_EVENT:
        label, colour = f"{BRAND} عاجل", ACCENT
    draw.rectangle([right - 110, y, right, y + 10], fill=colour)
    rtl((right, y + 46), label, load_font(32, bold=True), colour)


def render_number(brief, out_path, photo_credit=None):
    """Card built around one dominant figure — for stories where the number
    IS the story (a budget line, a report total, a percentage change)."""
    bg, ink, red, muted = BG_TOP, TEXT, ACCENT, MUTED
    body_ink = BODY

    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    margin = 96
    max_w = W - 2 * margin
    centre = W // 2
    right = W - margin
    _, kw = ar("م")

    def mid(xy, text, font, fill):
        shaped, k = ar(text)
        draw.text(xy, shaped, font=font, fill=fill, anchor="ma", **k)

    def rtl(xy, text, font, fill):
        shaped, k = ar(text)
        draw.text(xy, shaped, font=font, fill=fill, anchor="ra", **k)

    figure = str(brief.get("figure", "")).strip()
    label = str(brief.get("figure_label", "")).strip()
    body = (brief.get("body") or "").strip()
    punch = (brief.get("punch") or "").strip()

    # header
    _draw_header(draw, rtl, right)
    draw_brand_badge(img)

    y = 330
    f_title = load_font(52, bold=True)
    for line in _wrap(draw, brief["title"], f_title, max_w, kw):
        mid((centre, y), line, f_title, ink)
        y += 68
    y += 70

    # the figure, as large as it can be while still fitting
    size = 240
    while size > 90:
        f_num = load_font(size, bold=True)
        if draw.textlength(ar(figure)[0], font=f_num, **kw) <= max_w:
            break
        size -= 10
    mid((centre, y), figure, f_num, BRAND_INK)
    y += int(size * 1.12)

    if label:
        f_label = load_font(40, bold=True)
        for line in _wrap(draw, label, f_label, max_w, kw):
            mid((centre, y), line, f_label, muted)
            y += 54
    y += 60

    f_body = load_font(42)
    for line in _wrap(draw, body, f_body, max_w, kw):
        mid((centre, y), line, f_body, body_ink)
        y += 60
    y += 44

    f_punch = load_font(42, bold=True)
    for line in _wrap(draw, punch, f_punch, max_w, kw):
        mid((centre, y), line, f_punch, red)
        y += 62

    f_foot = load_font(26)
    parts = []
    sources = "، ".join(brief.get("sources", [])[:3])
    if sources:
        parts.append(f"المصدر: {sources}")
    # a generated image must always be labelled, whatever was passed in
    if photo_path and Path(str(photo_path) + ".generated").exists():
        photo_credit = GENERATED_CREDIT
    if photo_credit:
        parts.append(f"الصورة: {photo_credit}")
    if parts:
        closing_seal(img, H - 246)
        mid((centre, H - 130), "   •   ".join(parts), f_foot, muted)

    img.save(out_path, "PNG", optimize=True)
    return out_path


def render_story(brief, out_path, photo_path=None, photo_credit=None):
    """Light card: photo, a short paragraph, one line in red. Centred.
    Everything is measured before it is drawn, so nothing can overflow."""
    if photo_path:
        try:
            Image.open(photo_path).close()
        except Exception as exc:
            # layout is decided by a successfully-opened image, never a
            # truthy path (the Samsung SVG lesson): unreadable means the
            # card reflows as photoless, not a blank hole mid-card
            print(f"  ! photo unreadable ({exc}) — rendering photoless")
            photo_path = None
    bg, ink, red, muted = BG_TOP, TEXT, ACCENT, MUTED
    body_ink = BODY

    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    margin = 96
    max_w = W - 2 * margin
    centre = W // 2
    right = W - margin
    _, kw = ar("م")

    def mid(xy, text, font, fill):
        shaped, k = ar(text)
        draw.text(xy, shaped, font=font, fill=fill, anchor="ma", **k)

    def rtl(xy, text, font, fill):
        shaped, k = ar(text)
        draw.text(xy, shaped, font=font, fill=fill, anchor="ra", **k)

    # what we have to fit
    points = brief.get("points", [])
    body = brief.get("body")
    if body is None:
        body = brief.get("lead", "").strip()
        if points:
            body = f"{body} {points[0].get('text', '').strip()}".strip()
    body = (body or "").strip()

    punch = brief.get("punch")
    if punch is None:
        punch = points[-1].get("text", "") if len(points) > 1 else ""
    punch = (punch or "").strip()

    HEADER_END = 320                      # below the bar and the label
    # the closing seal's height is RESERVED here, before any text sizing —
    # fitting the body first and squeezing the seal in after is how marks
    # end up on top of text
    FOOTER_TOP = H - 340                  # above the closing seal + credits

    def measure(scale, photo_h):
        f_title = load_font(int(60 * scale), bold=True)
        f_body = load_font(int(44 * scale))
        f_punch = load_font(int(44 * scale), bold=True)
        title_lines = _wrap(draw, brief["title"], f_title, max_w, kw)
        body_lines = _wrap(draw, body, f_body, max_w, kw) if body else []
        punch_lines = _wrap(draw, punch, f_punch, max_w, kw) if punch else []
        height = (len(title_lines) * int(78 * scale) + int(46 * scale)
                  + (photo_h + int(64 * scale) if photo_h else 0)
                  + len(body_lines) * int(64 * scale) + int(44 * scale)
                  + len(punch_lines) * int(66 * scale))
        return {
            "fonts": (f_title, f_body, f_punch),
            "lines": (title_lines, body_lines, punch_lines),
            "scale": scale, "photo_h": photo_h, "height": height,
        }

    available = FOOTER_TOP - HEADER_END
    base_photo_h = int((W - 2 * margin) * 0.78) if photo_path else 0

    layout = None
    for photo_frac in (1.0, 0.86, 0.72, 0.6):
        for scale in (1.0, 0.94, 0.88, 0.82):
            trial = measure(scale, int(base_photo_h * photo_frac))
            if trial["height"] <= available:
                layout = trial
                break
        if layout:
            break

    if layout is None:                    # still too long — trim the body
        while body and len(body) > 80:
            body = body.rsplit(" ", 1)[0]
            trial = measure(0.82, int(base_photo_h * 0.6))
            if trial["height"] <= available:
                layout = trial
                body = body.rstrip(" ،.") + "."
                break
        layout = layout or measure(0.82, int(base_photo_h * 0.6))
        print("  ! card content trimmed to fit")

    scale = layout["scale"]
    f_title, f_body, f_punch = layout["fonts"]
    title_lines, body_lines, punch_lines = layout["lines"]

    # with no photo the block would sit at the top and leave the card empty
    start_y = HEADER_END
    if not photo_path or not layout["photo_h"]:
        start_y = max(HEADER_END,
                      HEADER_END + (available - layout["height"]) // 2 - 40)
    if scale < 1.0 or layout["photo_h"] != base_photo_h:
        print(f"    layout: text {int(scale * 100)}%, "
              f"photo {layout['photo_h']}px")

    # header
    _draw_header(draw, rtl, right)
    draw_brand_badge(img)

    y = start_y
    for line in title_lines:
        mid((centre, y), line, f_title, ink)
        y += int(78 * scale)
    y += int(46 * scale)

    if photo_path and layout["photo_h"]:
        try:
            photo = Image.open(photo_path).convert("RGB")
            box_w, box_h = W - 2 * margin, layout["photo_h"]
            pw, ph = photo.size
            if pw / ph > box_w / box_h:
                new_w = int(ph * box_w / box_h)
                photo = photo.crop(((pw - new_w) // 2, 0,
                                    (pw - new_w) // 2 + new_w, ph))
            else:
                new_h = int(pw * box_h / box_w)
                photo = photo.crop((0, 0, pw, new_h))
            photo = photo.resize((box_w, box_h), Image.LANCZOS)
            rounded = _rounded(photo, 36)
            img.paste(rounded, (margin, y), rounded)
            seal_photo(img, margin + box_w, y + box_h)
            y += box_h + int(64 * scale)
        except Exception as exc:
            print(f"  ! couldn't place photo: {exc}")

    for line in body_lines:
        mid((centre, y), line, f_body, body_ink)
        y += int(64 * scale)
    y += int(44 * scale)

    for line in punch_lines:
        mid((centre, y), line, f_punch, red)
        y += int(66 * scale)

    # credit, always clear of the text above it
    f_foot = load_font(26)
    # a generated image must always be labelled, whatever was passed in
    if photo_path and Path(str(photo_path) + ".generated").exists():
        photo_credit = GENERATED_CREDIT

    def fit(text):
        while text and draw.textlength(ar(text)[0], font=f_foot, **kw) > max_w:
            text = text.rsplit("، ", 1)[0] if "، " in text else text[:-4]
        return text

    def norm(text):
        return "".join((text or "").split()).replace("ـ", "").lower()

    src_list = [s for s in brief.get("sources", []) if s][:3]
    lines = []
    if src_list:
        lines.append(fit("المصدر: " + "، ".join(src_list)))

    # when the photo came from the same outlet, one credit line is enough
    same = photo_credit and any(norm(photo_credit) == norm(s) or
                                norm(s) in norm(photo_credit)
                                for s in src_list)
    if photo_credit and not same:
        # its own line, so a long source list can never truncate it away
        lines.append(fit(f"الصورة: {photo_credit}"))

    if lines:
        top = H - 176 if len(lines) == 1 else H - 206
        closing_seal(img, top - 70)
        y = top + 46
        for line in lines:
            mid((centre, y), line, f_foot, muted)
            y += 40

    img.save(out_path, "PNG", optimize=True)
    return out_path


# --------------------------------------------------------------------------
# منصة الصور السعودية (SPA) — official Saudi photography, CC BY-SA 4.0
# --------------------------------------------------------------------------

SPA_BASE = "https://cc.spa.gov.sa"
SPA_YEARS = int(os.getenv("SPA_YEARS", "3"))
SPA_CREDIT = os.getenv("SPA_CREDIT", "واس / CC BY-SA 4.0")


def _ticks(dt):
    """.NET ticks — what the SPA search API expects for dates."""
    return int((dt - datetime(1, 1, 1)).total_seconds() * 10_000_000)


def _spa_search(term, count=16):
    """Search the Saudi Photos platform. Returns raw result dicts."""
    now = datetime.now()
    model = {
        "DataLangId": 1058,                       # Arabic
        "CategoryId": 0,
        "SearchText": f' "*{term}*"',
        "SearchTextCompareType": 1,
        "FromDate": _ticks(now - timedelta(days=365 * SPA_YEARS)),
        "ToDate": _ticks(now),
        "GetCount": count,
    }
    url = (f"{SPA_BASE}/Utility/SearchPaging?langChar=ar"
           f"&searchModel={urllib.parse.quote(json.dumps(model, ensure_ascii=False))}"
           "&pageNumber=1")
    req = urllib.request.Request(url, headers={
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/126.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ar,en;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{SPA_BASE}/ar/search",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            ctype = resp.headers.get("Content-Type", "?")
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        print(f"  ! SPA HTTP {exc.code} for {term!r}")
        return []
    except Exception as exc:
        print(f"  ! SPA request failed for {term!r}: {exc}")
        return []

    if status == 204 or not raw.strip():
        print(f"    SPA: 0 results for {term!r}")
        return []

    try:
        results = json.loads(raw.decode("utf-8-sig"))
    except Exception:
        head = raw[:200].decode("utf-8", "ignore").replace("\n", " ").strip()
        print(f"  ! SPA returned non-JSON for {term!r} "
              f"(status {status}, type {ctype}, {len(raw)} bytes)")
        print(f"    body starts: {head!r}")
        return []

    print(f"    SPA: {len(results)} results for {term!r}")
    return results if isinstance(results, list) else []


# titles that signal a posed portrait or a protocol shot, not a scene
GRAPHIC_HINTS = ("شعار", "لوجو", "إنفوجرافيك", "انفوجرافيك", "رسم توضيحي",
                 "تصميم", "بطاقة", "غلاف", "هوية بصرية", "بيان", "إعلان")

PORTRAIT_HINTS = ("معالي", "سمو", "سموه", "الأمير", "وزير", "الوزير", "رئيس",
                  "المدير التنفيذي", "يستقبل", "يلتقي", "يبحث مع", "خلال لقائه",
                  "يرأس", "يدشن", "يفتتح", "مؤتمر صحفي", "كلمة")


def _spa_text(item):
    return " ".join(filter(None, [
        item.get("title") or "",
        " ".join(item.get("keywords") or []),
        item.get("parantName") or "",
    ]))


def _spa_safe(text):
    """SPA captions are Arabic; _image_is_safe checks both languages now."""
    return _image_is_safe(text)


def _spa_score(item, terms):
    """Overlap between the caption and what we asked for."""
    text = _spa_text(item)
    if not text:
        return 0
    hits = sum(1 for t in terms if t and t in text)
    recent = 3 if "2025" in text or "2026" in text else 0
    score = hits * 10 + recent
    title = item.get("title") or ""
    if any(h in title for h in PORTRAIT_HINTS):
        score -= 20          # a person announcing a thing isn't a photo of it
    if any(h in title for h in GRAPHIC_HINTS):
        score -= 30          # logo cards and infographics aren't photographs
    return score


# SPA moved its media to a CDN (observed 2026-08): the old
# cc.spa.gov.sa/media/... paths now return a 70-byte HTML "Page not found"
# stub WITH HTTP 200, so every candidate died at the size check and the
# 09:00 topic run lost its best source without a single error line. The
# search API still advertises the old relative paths; the same path on the
# CDN serves the _th thumbnail at ~1000px — card quality — while the
# full-size name 404s there. Try CDN full-size first anyway (cheap, and
# right if it ever returns), then the CDN thumbnail, then the legacy host
# in case the move reverts.
SPA_CDN = "https://cc-cdn.spa.gov.sa/mashaa"


def _spa_image_urls(item):
    """Working URLs for one search item, best first — see the SPA_CDN note."""
    thumb = item.get("thumbnailUrl") or ""
    if not thumb:
        return []
    urls = []
    for base in (SPA_CDN, SPA_BASE):
        if "_th." in thumb:
            urls.append(base + thumb.replace("_th.", "."))
        urls.append(base + thumb)
    return urls


def fetch_spa_photo(queries_ar, out_path):
    """Fetch an official Saudi photo. Returns (path, credit) or (None, None).

    Images are CC BY-SA 4.0 — the credit line is not optional.
    """
    if isinstance(queries_ar, str):
        queries_ar = [queries_ar]
    queries_ar = [q.strip() for q in queries_ar if q and q.strip()]
    if not queries_ar:
        return None, None

    # "*مخيمات منى*" matches the exact phrase and finds nothing; single
    # words do the work. Try the phrase, then each word in it.
    searches = []
    for query in queries_ar:
        words = [w for w in re.split(r"\s+", query) if len(w) > 2]
        if len(words) > 1:
            searches.append((query, words))          # phrase first
        for word in words:
            searches.append((word, words))           # then each word
    seen_terms = set()

    candidates = []
    for term, terms in searches:
        if term in seen_terms:
            continue
        seen_terms.add(term)
        for item in _spa_search(term):
            if not _spa_safe(_spa_text(item)):
                continue
            candidates.append((_spa_score(item, terms), term, item))
        if any(c[0] >= MIN_PHOTO_SCORE for c in candidates):
            break

    if not candidates:
        print("  ! no SPA photo found")
        return None, None

    candidates.sort(key=lambda c: -c[0])
    if candidates[0][0] < MIN_PHOTO_SCORE:
        print(f"  ! best SPA match scored {candidates[0][0]:.0f}, below "
              f"{MIN_PHOTO_SCORE} — skipping")
        return None, None

    for score, query, item in candidates[:5]:
        for link in _spa_image_urls(item):
            try:
                req = urllib.request.Request(link,
                                             headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=45) as resp:
                    data = resp.read()
            except Exception as exc:
                print(f"  ! SPA download failed ({exc}) — trying next")
                continue
            if len(data) < 15_000:
                continue
            _clear_generated_marker(out_path)
            Path(out_path).write_bytes(data)
            if looks_like_a_graphic(out_path):
                break                    # try the next candidate instead
            if _recent_reject(out_path):
                continue
            print(f"    photo: {item.get('title', '')[:70]} [{query}]")
            return str(out_path), SPA_CREDIT

    print("  ! every SPA candidate failed to download")
    return None, None


# --------------------------------------------------------------------------
# Local image library — your own licensed images, matched by tags
# --------------------------------------------------------------------------

IMAGES_DIR = Path(os.getenv("IMAGES_DIR", "images"))
IMAGES_INDEX = Path(os.getenv("IMAGES_INDEX", "images/images.txt"))


def load_local_images():
    """Parse images/images.txt.

    One image per line:
        filename.jpg | كلمات, مفتاحية, english, keywords | credit (optional)

    Lines starting with # are ignored. The credit field is optional — leave it
    out for images you licensed yourself and don't need to attribute.
    """
    try:
        lines = IMAGES_INDEX.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []

    entries = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            continue
        path = IMAGES_DIR / parts[0]
        if not path.exists():
            print(f"  ! {path} listed in the index but not on disk")
            continue
        tags = [t.strip().lower() for t in parts[1].split(",") if t.strip()]
        entries.append({
            "path": path,
            "tags": tags,
            "credit": parts[2] if len(parts) > 2 and parts[2] else None,
        })
    return entries


def fetch_local_photo(queries_ar, queries_en, out_path,
                      respect_cooldown=True):
    """Pick the best match from your own library. Returns (path, credit).

    respect_cooldown=False is for PERSON identity fetches only: a
    verified portrait legitimately reappears when its story re-runs,
    and identity beats variety there."""
    library = load_local_images()
    if not library:
        return None, None

    # EXACT identity matching (the Savola lesson, relearned here: the
    # substring matcher let 'saudi' inside 'Saudi Central Bank' put the
    # SAMA headquarters on the coffee story's person frame). A tag
    # matches when it EQUALS a query phrase, or a single-word tag
    # equals a query word — never by containment.
    phrases = {str(q).strip().casefold()
               for q in list(queries_ar or []) + list(queries_en or [])
               if str(q).strip()}
    words = set()
    for q in phrases:
        words |= {t for t in re.split(r"[\s,]+", q) if len(t) > 2}
    if not phrases:
        return None, None

    scored = []
    for entry in library:
        tags = {t.casefold() for t in entry["tags"]}
        score = sum(10 for tag in tags
                    if tag in phrases
                    or (" " not in tag and tag in words))
        if score >= MIN_PHOTO_SCORE:
            scored.append((score, entry))
    scored.sort(key=lambda se: -se[0])

    if not scored:
        print(f"    local library: no match ({len(library)} images indexed)")
        return None, None

    best = None
    for best_score, entry in scored:
        if respect_cooldown and _library_recently_used(entry["path"]):
            print(f"    local library: {entry['path'].name} rests "
                  f"(used within {LIBRARY_REUSE_DAYS} day(s)) — "
                  "trying the next match")
            continue
        best = entry
        break
    if best is None:
        print("    local library: every matching photo rests under the "
              "short cooldown — falling through to the archives")
        return None, None

    import shutil as _shutil
    _clear_generated_marker(out_path)
    _shutil.copyfile(best["path"], out_path)
    # curated library photos are exempt from the cross-run cooldown: the
    # owner chose them, and dropping a good photo into images/ is exactly
    # how a recurring subject sidesteps the cooldown by design
    Path(str(out_path) + ".exempt").write_text("local", encoding="utf-8")
    print(f"    photo: {best['path'].name} from your library "
          f"(matched {best_score // 10} tag(s))")
    return str(out_path), best.get("credit")


def ksa_stamp():
    """Date plus the run hour in KSA time, e.g. 2026-08-18-7am.
    Runners are UTC, so a 07:00 KSA run would otherwise be stamped 0400."""
    now = datetime.now(timezone.utc) + timedelta(hours=3)
    hour = now.hour % 12 or 12
    suffix = "am" if now.hour < 12 else "pm"
    return f"{now.strftime('%Y-%m-%d')}-{hour}{suffix}"


# --------------------------------------------------------------------------
# Telegram notifications — the card lands on your phone, ready to post
# --------------------------------------------------------------------------

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


def notify(text, photo_path=None):
    """Send a message, with the card attached when there is one.
    Silent no-op if the secrets aren't set."""
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        return

    base = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    try:
        if photo_path and Path(photo_path).exists():
            boundary = "----snapnews" + hashlib.md5(text.encode()).hexdigest()[:12]
            data = Path(photo_path).read_bytes()
            parts = []
            for name, value in (("chat_id", TELEGRAM_CHAT_ID), ("caption", text)):
                parts.append(
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                    f"{value}\r\n".encode())
            parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="photo"; '
                f'filename="card.png"\r\n'
                f"Content-Type: image/png\r\n\r\n".encode())
            body = b"".join(parts) + data + f"\r\n--{boundary}--\r\n".encode()
            req = urllib.request.Request(
                f"{base}/sendPhoto", data=body,
                headers={"Content-Type":
                         f"multipart/form-data; boundary={boundary}"})
        else:
            body = urllib.parse.urlencode({
                "chat_id": TELEGRAM_CHAT_ID, "text": text}).encode()
            req = urllib.request.Request(f"{base}/sendMessage", data=body)

        with urllib.request.urlopen(req, timeout=60) as resp:
            ok = json.loads(resp.read()).get("ok")
        print(f"    telegram: {'sent' if ok else 'rejected'}")
    except Exception as exc:
        print(f"  ! telegram notification failed: {exc}")


def notify_album(text, photo_paths, as_documents=False):
    """Send several images as one Telegram album, captioned on the first.

    as_documents=True sends FILES rather than photos: Telegram preserves
    the exact filename and full quality. Photos get recompressed and
    renamed with an epoch-ms prefix on download, which scrambled the
    owner's frame order (1787589023931_...-story-06.png) — for anything
    uploaded onward by hand, documents with index-FIRST names are the fix.
    """
    paths = [p for p in (photo_paths or []) if p and Path(p).exists()]
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID) or not paths:
        return
    if len(paths) == 1 and not as_documents:
        return notify(text, paths[0])

    boundary = "----snapalbum" + hashlib.md5(text.encode()).hexdigest()[:12]
    media = []
    parts = []
    kind = "document" if as_documents else "photo"
    for n, path in enumerate(paths[:10]):        # Telegram allows up to 10
        name = f"photo{n}"
        item = {"type": kind, "media": f"attach://{name}"}
        if n == 0:
            item["caption"] = text
        media.append(item)
        # the frame index comes FIRST in the delivered filename, so any
        # download sorts 01..06 lexically whatever the client prepends
        fname = (f"{n + 1:02d}-{Path(path).name}" if as_documents
                 else Path(path).name)
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"; '
            f'filename="{fname}"\r\n'
            f"Content-Type: image/png\r\n\r\n".encode()
            + Path(path).read_bytes() + b"\r\n")

    head = []
    for key, value in (("chat_id", TELEGRAM_CHAT_ID),
                       ("media", json.dumps(media, ensure_ascii=False))):
        head.append(f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
                    f"{value}\r\n".encode())

    body = b"".join(head) + b"".join(parts) + f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMediaGroup",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            ok = json.loads(resp.read()).get("ok")
        print(f"    telegram: album of {len(paths)} {'sent' if ok else 'rejected'}")
    except Exception as exc:
        print(f"  ! telegram album failed ({exc}) — sending one photo instead")
        notify(text, paths[0])


def deliver_unposted(cards, headline):
    """Send a card we built but aren't publishing, so it never just vanishes.

    The monthly limit stops the automatic post, not the work — by the time we
    get here the card is rendered and the research is already paid for. It
    goes to the phone instead, to be posted by hand. Before this the bots
    returned silently when the limit hit and the account simply went quiet
    with nothing said in the log, on Telegram or anywhere else.
    """
    month, used = quota_used()
    note = (f"⏸️ {ksa_stamp()} — لم يُنشر تلقائياً: بلغت حصة الشهر "
            f"({used}/{MONTHLY_POST_LIMIT} في {month})\n{headline}")
    paths = [cards] if isinstance(cards, (str, Path)) else [c for c in cards if c]
    if len(paths) > 1:
        # multi-frame deliveries are for hand-upload: documents with
        # index-first names, or the download scrambles the order
        notify_album(note, paths, as_documents=True)
    else:
        notify(note, paths[0] if paths else None)


def prune_old_cards():
    """Delete committed cards older than KEEP_CARDS_DAYS so the folder
    doesn't grow forever. latest.png is always kept."""
    if KEEP_CARDS_DAYS <= 0:
        return 0
    folder = Path(CARDS_DIR)
    if not folder.exists():
        return 0
    cutoff = datetime.now() - timedelta(days=KEEP_CARDS_DAYS)
    removed = 0
    for card in folder.glob("*.png"):
        if card.name == "latest.png":
            continue
        stamp = card.name[:10]                  # cards are named YYYY-MM-DD-...
        try:
            when = datetime.strptime(stamp, "%Y-%m-%d")
        except ValueError:
            continue
        if when < cutoff:
            card.unlink()
            removed += 1
    return removed


# --------------------------------------------------------------------------
# Generated images (fal.ai / Seedream) — illustration only, never for news
# --------------------------------------------------------------------------

IMAGE_GEN = os.getenv("IMAGE_GEN", "byteplus").strip()      # byteplus | fal

FAL_KEY = os.getenv("FAL_KEY", "").strip()
FAL_MODEL = os.getenv("FAL_MODEL", "fal-ai/bytedance/seedream/v4/text-to-image")

# BytePlus ModelArk. Confirm the host and model id in your console — the region
# in the URL differs between accounts.
ARK_KEY = os.getenv("ARK_API_KEY", "").strip()
# an unset GitHub repo variable arrives as "", so fall back explicitly
ARK_URL = os.getenv("ARK_URL", "").strip() or \
    "https://ark.ap-southeast.bytepluses.com/api/v3/images/generations"
ARK_MODEL = _clean_model_id(os.getenv("ARK_MODEL"), "seedream-4-0-250828")

# --------------------------------------------------------------------------
# Vision gate — a small model looks at the chosen photo before it ships
# --------------------------------------------------------------------------
# Every photo failure a human caught in review — a certificate, a chart, a
# perfume vial on an oil story, the Golden Gate on a boardroom beat — was
# obvious in one glance and invisible to text-metadata scoring. This is that
# glance, automated. Haiku-class: pennies per story.

VISION_MODEL = _clean_model_id(os.getenv("VISION_MODEL"),
                               "claude-haiku-4-5-20251001")
VISION_GATE = os.getenv("VISION_GATE", "").strip() not in ("0", "false", "False")

_VISION_JUDGE = """أنت تفحص صورة قبل وضعها على بطاقة قصة تُنشر لجمهور عام.

نص اللقطة التي ستحمل الصورة:
{context}

أجب بكلمة واحدة أولاً بلا أي تنسيق: نعم أو محايدة أو لا، ثم سطر واحد يشرح.

- نعم: صورة فوتوغرافية حقيقية لشخصٍ أو مكانٍ أو شيءٍ يسمّيه نص اللقطة —
  حتى لو لم تُظهر الحدث الموصوف نفسه أو لحظته. لا تطلب صورة "اللحظة":
  الأرشيف نادراً ما يملكها. صورة شخصٍ يسمّيه النص هي "نعم" دائماً.
  والاختبار: هل يرى القارئ العادي الصورة وحدها فيفهم أنها توضح هذه
  الجملة؟ إن احتاج تخميناً أو شرحاً ليربطها بالنص فليست نعم — قل
  محايدة. البطاقة تملك بديلاً أنيقاً (شعار الشركة)، فالحيرة أسوأ من
  غياب الصورة.
  ✓ يجب أن تكون "نعم": صورة Max Steineke في السعودية 1938 للقطة نصها
    يسمّي Steineke — الحكم كان "محايد" فنُشرت صورة جوية حديثة بدلاً منه.
  ✗ يجب ألا تكون "نعم": جسمٌ محفور أو درعٌ تذكارية أو قطعة غامضة على
    لقطة عن تأسيس شركة — وصلت واحدة إلى بطاقة منشورة لأن الحكم كان
    "نعم" ضعيفة. الجسم الغامض جوابه محايدة أو لا.
- محايدة: صورة فوتوغرافية حقيقية من موضوع القصة لكنها تُظهر شيئاً لا
  يسمّيه نص هذه اللقطة: المقر الحديث للشركة على لقطة عن الثلاثينات،
  صحراء المنطقة على لقطة عن اجتماع. أما عشب أخضر أو كورنيش ليلي أو أي
  منظر جميل لا يربطه بالموضوع شيء فليس محايداً — إنه حشو، وجوابه لا.
- لا: ليست صورة فوتوغرافية (خريطة، رسم بياني، شهادة، ملصق، لقطة شاشة
  بواجهة برنامج)، أو تُظهر شيئاً يناقض النص أو يضلل القارئ: شخصاً آخر،
  مكاناً آخر يوحي بأنه المكان المقصود، شيئاً لا صلة له يبدو كأنه دليل.
  وإن ذكر النص موضوع القصة («القصة عن X») فكل ما يخص علامةً أو جهةً
  أخرى غير X جوابه لا — القارئ سينسب ما في الصورة إلى X.
  وإن حدّد النص سنةً أو حقبةً قديمة وكانت الصورة حديثة بوضوح — سيارات
  حديثة، أبراج زجاجية، لافتات رقمية — فجوابها لا: صورة جوية لعمران حديث
  على لقطة نصها «طوكيو 1983» من صنف «الجهة الغلط» نفسه.
  ✗ طائرة Riyadh Air على بطاقة قصتها عن ترخيص زين — لا، مهما كانت الصورة
    جميلة: الجهة غلط.

بين نعم ومحايدة: إن سمّى النص ما في الصورة ورآه القارئ فيها بوضوح فهي
نعم؛ والشك كله محايدة. وبين محايدة ولا، ما يضلل فهو لا."""


_vision_stats = {"asked": 0, "rejected": 0, "neutral": 0}
# AramcoCoreArea.jpg was downloaded and judged five times in one run — same
# bytes, same context, five vision calls. In-memory only, per process.
_gate_cache = {}


def photo_shows(photo_path, context):
    """Does the picture actually show what the frame is about?

    Returns "yes", "neutral" or "no". Fail-open by design: no key, gate off,
    or an API error all return "yes", so an outage degrades to the old
    behaviour instead of losing the story. A rejection prints the reason.
    """
    if not (VISION_GATE and ANTHROPIC_API_KEY):
        return "yes"
    try:
        raw = Path(photo_path).read_bytes()
        cache_key = (hashlib.md5(raw).hexdigest(),
                     hashlib.md5(context[:600].encode()).hexdigest())
        if cache_key in _gate_cache:
            print("      (gate verdict cached)")
            return _gate_cache[cache_key]
    except Exception:
        cache_key = None
    try:
        import io as _io
        img = Image.open(photo_path).convert("RGB")
        img.thumbnail((800, 800))          # vision cost scales with pixels
        buf = _io.BytesIO()
        img.save(buf, "JPEG", quality=80)
        b64 = base64.b64encode(buf.getvalue()).decode()
    except Exception as exc:
        # a fail-open that can't tell "gate is down" from "file is
        # broken" is not a fail-open: this failure is the FILE's, and
        # the verdict is a rejection — the API outage path stays below
        print(f"  ✂ vision gate: unreadable image ({exc}) — rejected")
        if cache_key:
            _gate_cache[cache_key] = "no"
        return "no"
    try:
        payload = {
            "model": VISION_MODEL,
            "max_tokens": 150,
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                                             "media_type": "image/jpeg",
                                             "data": b64}},
                {"type": "text",
                 "text": _VISION_JUDGE.format(context=context[:600])},
            ]}],
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={"content-type": "application/json",
                     "x-api-key": ANTHROPIC_API_KEY,
                     "anthropic-version": "2023-06-01"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        text = "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text").strip()
    except Exception as exc:
        print(f"  ! vision gate unavailable ({exc}) — letting the photo through")
        return "yes"

    _vision_stats["asked"] += 1
    # The verdict word may arrive dressed — "**نعم**", «نعم», a leading dash.
    # Take the first verdict token found anywhere in the head of the reply;
    # startswith() alone once misread every bolded approval as a rejection.
    head = text[:40]
    positions = {w: head.find(w) for w in ("نعم", "محايدة", "لا")}
    found = [(i, w) for w, i in positions.items() if i != -1]
    verdict = min(found)[1] if found else "لا"
    if verdict == "لا":
        _vision_stats["rejected"] += 1
        print(f"  ✂ vision gate rejected the photo: {text[:140]}")
    elif verdict == "محايدة":
        _vision_stats["neutral"] += 1
    result = {"نعم": "yes", "محايدة": "neutral"}.get(verdict, "no")
    if cache_key:
        _gate_cache[cache_key] = result
    return result


def vision_gate_summary():
    if _vision_stats["asked"]:
        print(f"    vision gate: {_vision_stats['asked']} checked, "
              f"{_vision_stats['rejected']} rejected, "
              f"{_vision_stats['neutral']} neutral")

ALLOW_GENERATED = os.getenv("ALLOW_GENERATED", "0").strip() not in ("", "0", "false", "False")
GENERATED_CREDIT = "صورة مولّدة بالذكاء الاصطناعي"

# appended to every prompt — the constraints matter more than the description
GEN_GUARD = (
    "Editorial photograph, Saudi Arabian setting. "
    "ONE single coherent real location — either an interior or an exterior, "
    "never both. Every object must sit where it plausibly belongs: furniture "
    "indoors, vehicles on roads. No collage, no floating or composited items, "
    "no impossible juxtapositions. "
    "CRITICAL: absolutely no text, letters, words, numbers, characters, "
    "signage, billboards, shop signs, building signs, banners, book pages with "
    "writing, screens with writing, or any written script anywhere in the "
    "image, in any language. Notebooks and papers must be blank. "
    "Buildings and vehicles completely unmarked and unbranded. "
    "No logos, brands, flags or emblems. No maps. "
    "No money, banknotes, coins or currency of any kind. "
    "No people's faces, no recognisable individuals, no crowds. "
    "No weapons, uniforms, police or military. "
    "Natural daylight, neutral and calm, documentary feel, realistic photo."
)


# The 09:00 KSA topic run of 2026-08-24 live-posted a budget card whose
# generated image showed FAKE Saudi banknotes — invented note design, a face
# on the currency, pseudo-Arabic gibberish printed across it. Properly
# labelled, still hand-deleted: imitation currency imagery is legally
# sensitive in Saudi Arabia, and garbled Arabic wrecks the brand. Two
# defences, deliberately redundant: the prompt scrub below keeps money out
# of the ask, and _GEN_JUDGE checks what actually came back.
_MONEY_RE = re.compile(
    r"(?i)\b(?:riyals?|banknotes?|cash|money|currenc(?:y|ies)|bills?)\b"
    r"|ريال|عملات|عملة|نقود|أوراق نقدية")

# NOT photo_shows: fetched photographs fail by being irrelevant, generated
# images fail by containing fabrications. Text presence alone disqualifies —
# generators cannot render Arabic, so ANY text will be garbled or fake;
# never try to judge whether the text "looks okay".
_GEN_JUDGE = """هل تحتوي الصورة على أيٍّ من التالي؟
1) نصوص أو حروف من أي نوع (لافتة، ورقة مكتوبة، شعار، أرقام)
2) وجه إنسان
3) عملات أو أوراق نقدية أو ما يشبهها
4) كتابة عربية مشوّهة أو حروف بلا معنى
5) علم دولة أو خريطة أو معلم شهير يدل على بلد بعينه
أجب: "نظيفة" أو اذكر ما وجدت."""


def generated_image_clean(photo_path):
    """(True, "") for a clean generated image, else (False, reason).

    FAIL-CLOSED, unlike photo_shows: a fetched photo that skips its gate is
    a real photograph at worst mis-matched, but an unchecked generated image
    is how fake riyals reached a live post. The run already holds the same
    API key for research, so in practice this only bites on a transient
    error — and then the card falls back to its no-photo behaviour.
    """
    if not ANTHROPIC_API_KEY:
        print("  ! no API key to check a generated image — rejecting it")
        return False, "no key to verify"
    try:
        import io as _io
        img = Image.open(photo_path).convert("RGB")
        img.thumbnail((800, 800))
        buf = _io.BytesIO()
        img.save(buf, "JPEG", quality=80)
        b64 = base64.b64encode(buf.getvalue()).decode()
        payload = {
            "model": VISION_MODEL,
            "max_tokens": 150,
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                                             "media_type": "image/jpeg",
                                             "data": b64}},
                {"type": "text", "text": _GEN_JUDGE},
            ]}],
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={"content-type": "application/json",
                     "x-api-key": ANTHROPIC_API_KEY,
                     "anthropic-version": "2023-06-01"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        text = "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text").strip()
    except Exception as exc:
        print(f"  ! generation gate unavailable ({exc}) — rejecting the image")
        return False, "gate unavailable"
    # the verdict word may arrive dressed, same as photo_shows verdicts
    if "نظيفة" in text[:40]:
        return True, ""
    return False, text[:200]


def fetch_generated_photo(prompt, out_path):
    """Generate an illustration. Returns (path, credit) or (None, None).

    Only ever called for topic cards (and story frames when the owner turns
    ALLOW_STORY_GENERATION on). A generated image on a news card would imply
    photography of a real event, so news never reaches this. Every output
    passes generated_image_clean before it can be used: one regeneration on
    rejection, then a clean give-up — a card must never carry a failed
    generation.
    """
    if not ALLOW_GENERATED:
        return None, None
    prompt = (prompt or "").strip()
    if not prompt:
        return None, None

    if _MONEY_RE.search(prompt):
        prompt = _MONEY_RE.sub("", prompt)
        prompt = re.sub(r"\s{2,}", " ", prompt).strip(" .,،")
        prompt += (". No money, no banknotes, no currency, "
                   "no documents with text")
        print("    image prompt asked for money — scrubbed")

    full = f"{prompt}. {GEN_GUARD}"

    if IMAGE_GEN == "fal":
        if not FAL_KEY:
            print("  ! FAL_KEY not set — skipping image generation")
            return None, None
        url = f"https://fal.run/{FAL_MODEL}"
        headers = {"Authorization": f"Key {FAL_KEY}",
                   "Content-Type": "application/json"}
        payload = {"prompt": full,
                   "image_size": {"width": 1280, "height": 960},
                   "num_images": 1}
    else:
        if not ARK_KEY:
            print("  ! ARK_API_KEY not set — skipping image generation")
            return None, None
        url = ARK_URL
        headers = {"Authorization": f"Bearer {ARK_KEY}",
                   "Content-Type": "application/json"}
        payload = {"model": ARK_MODEL, "prompt": full,
                   "size": "2K", "response_format": "url",
                   "watermark": False}
        print(f"    generating via byteplus, model={ARK_MODEL}")

    def _generate(ask):
        pay = dict(payload)
        pay["prompt"] = ask
        req = urllib.request.Request(url, data=json.dumps(pay).encode(),
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()[:250]
            print(f"  ! {IMAGE_GEN} {exc.code}: {body}")
            if "ModelNotOpen" in body or "not activated" in body:
                print(f"    the account hasn't activated {ARK_MODEL!r}.")
                print("    Activate it in the Ark Console, or set the ARK_MODEL repo")
                print("    variable to the id of a model you HAVE activated —")
                print("    the display name (ByteDance-Seedream-4.5) is not the id.")
            return False
        except Exception as exc:
            print(f"  ! image generation failed: {exc}")
            return False
        # fal returns {"images":[{"url":...}]}, ModelArk {"data":[{"url":...}]}
        items = data.get("images") or data.get("data") or []
        link = items[0].get("url") if items else None
        if not link:
            print(f"  ! no image in the response: {str(data)[:250]}")
            return False
        try:
            with urllib.request.urlopen(link, timeout=120) as resp:
                Path(out_path).write_bytes(resp.read())
        except Exception as exc:
            print(f"  ! couldn't download the generated image: {exc}")
            return False
        return True

    if not _generate(full):
        return None, None
    ok, reason = generated_image_clean(out_path)
    if not ok and reason == "no key to verify":
        # a retry would be just as unverifiable — don't pay for it
        print("  ! generation gave up (nothing can pass the gate without a key)")
        Path(out_path).unlink(missing_ok=True)
        Path(str(out_path) + ".generated").unlink(missing_ok=True)
        return None, None
    if not ok:
        print(f"  ! generated image rejected: {reason}")
        print("    regenerating once")
        retry = (f"{full} The previous attempt contained: {reason}. "
                 "Absolutely no text of any kind, no faces, no money or "
                 "banknotes.")
        if _generate(retry):
            ok, reason = generated_image_clean(out_path)
            if not ok:
                print(f"  ! generated image rejected: {reason}")
        if not ok:
            print("  ! generation gave up after retry")
            Path(out_path).unlink(missing_ok=True)
            Path(str(out_path) + ".generated").unlink(missing_ok=True)
            return None, None

    Path(str(out_path) + ".generated").write_text("1", encoding="utf-8")
    print(f"    photo: generated via {IMAGE_GEN} — {prompt[:60]}")
    return str(out_path), GENERATED_CREDIT


def _card_destination(png_path):
    """Where a card lands in cards/.

    Arabic filenames can't go in a URL unencoded, and git/CDN handling of
    them varies — commit under an ASCII name instead.

    The digest covers the card's BYTES as well as its name. Hashing the name
    alone made the filename a function of the KSA hour, so two stories run in
    the same hour produced identical names for all six frames and the second
    silently overwrote the first — it happened on 2026-08-19, where the riyal
    story's cards were replaced by the China story's. Including the content
    also keeps this idempotent: republishing the same card reuses its name
    instead of littering cards/ with copies.
    """
    stem = Path(png_path).stem
    ascii_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-")
    try:
        content = Path(png_path).read_bytes()
    except Exception:
        content = b""          # unreadable: fall back to name-only, as before
    digest = hashlib.md5(stem.encode("utf-8") + content).hexdigest()[:8]
    return Path(CARDS_DIR) / f"{ascii_stem or 'card'}-{digest}.png"


def publish_many_via_github(png_paths):
    """Commit every card in ONE commit and return their public URLs.

    A story is six frames. Publishing them one at a time meant six commits,
    six pushes and six waits for the CDN inside a 15-minute job — six chances
    to lose a race with another bot, and minutes of the budget spent waiting.
    They all land in one commit now, so one CDN check covers the set.
    """
    import shutil
    import time

    repo = os.getenv("GITHUB_REPOSITORY")
    branch = os.getenv("GITHUB_REF_NAME", "main")
    if not repo:
        raise SystemExit("GITHUB_REPOSITORY unset — MEDIA_MODE=github only works in Actions")

    paths = [png_paths] if isinstance(png_paths, (str, Path)) else list(png_paths)
    if not paths:
        return []

    Path(CARDS_DIR).mkdir(exist_ok=True)
    dests = []
    for png_path in paths:
        dest = _card_destination(png_path)
        shutil.copyfile(png_path, dest)
        dests.append(dest)

    _git_identity()
    # latest.png points at the last frame, which is the one worth landing on
    shutil.copyfile(paths[-1], Path(CARDS_DIR) / "latest.png")

    removed = prune_old_cards()
    _git("add", "-A", CARDS_DIR)
    if removed:
        print(f"    pruned {removed} card(s) older than {KEEP_CARDS_DAYS} days")
    label = dests[0].name if len(dests) == 1 else f"{len(dests)} cards, {dests[0].name}"
    try:
        _git("commit", "-m", f"card {label}")
    except subprocess.CalledProcessError:
        pass
    if not _git_push():
        raise SystemExit("Couldn't push the card(s) — the URLs below would 404")

    urls = ["https://raw.githubusercontent.com/"
            f"{repo}/{branch}/{CARDS_DIR}/{urllib.parse.quote(d.name)}"
            for d in dests]

    # one commit, so if the last file is live the whole set is
    for delay in (0, 2, 3, 5, 8, 10):
        time.sleep(delay)
        try:
            urllib.request.urlopen(
                urllib.request.Request(urls[-1], method="HEAD",
                                       headers={"User-Agent": USER_AGENT}),
                timeout=15)
            return urls
        except urllib.error.HTTPError:
            continue
    raise SystemExit(f"Card not reachable at {urls[-1]} — is the repo public?")


def publish_via_github(png_path):
    """One card, one URL. Thin wrapper so existing callers are unchanged."""
    return publish_many_via_github([png_path])[0]


def _ayrshare(path_, payload):
    req = urllib.request.Request(
        f"https://api.ayrshare.com/api/{path_}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {AYRSHARE_API_KEY}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Ayrshare {path_} failed: {exc.code} {exc.read().decode()}")


def upload_media(png_path):
    b64 = base64.b64encode(Path(png_path).read_bytes()).decode()
    res = _ayrshare("media/upload", {
        "file": f"data:image/png;base64,{b64}",
        "fileName": Path(png_path).name,
    })
    url = res.get("url") or res.get("mediaUrl")
    if not url:
        raise SystemExit(f"No media URL in upload response: {res}")
    return url


def describe_failure(response):
    """A short, readable reason — not the whole API response."""
    if not isinstance(response, dict):
        return str(response)[:200]
    for key in ("message", "error", "errors", "status"):
        value = response.get(key)
        if value:
            return f"{key}: {str(value)[:200]}"
    return str(response)[:200]


def post_ok(response):
    """True when the post really went out, whichever provider sent it.

    bundle.social always returns error/errors keys, set to None and {} on
    success — so check the values, never the presence of the keys.
    """
    if not isinstance(response, dict):
        return False
    if str(response.get("status", "")).lower() in ("error", "failed"):
        return False
    if response.get("error"):
        return False
    if response.get("errors"):
        return False
    return True


def _multipart(fields, file_field, filename, data, mime="image/png"):
    """Build a multipart/form-data body without pulling in requests."""
    boundary = "----snapnews" + hashlib.md5(filename.encode()).hexdigest()[:12]
    parts = []
    for name, value in fields.items():
        parts.append(f"--{boundary}\r\n"
                     f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                     f"{value}\r\n".encode())
    parts.append(f"--{boundary}\r\n"
                 f'Content-Disposition: form-data; name="{file_field}"; '
                 f'filename="{filename}"\r\n'
                 f"Content-Type: {mime}\r\n\r\n".encode())
    body = b"".join(parts) + data + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def bundle_upload(card_path):
    """Upload the card to bundle.social. Returns the upload id."""
    data = Path(card_path).read_bytes()
    # stories go up as one MP4 now — an MP4 declared image/png gets rejected
    mime = ("video/mp4" if str(card_path).lower().endswith(".mp4")
            else "image/png")
    body, content_type = _multipart({"teamId": BUNDLE_TEAM_ID}, "file",
                                    Path(card_path).name, data, mime=mime)
    req = urllib.request.Request(
        f"{BUNDLE_BASE.rstrip('/')}/upload", data=body,
        headers={**BUNDLE_HEADERS, "x-api-key": BUNDLE_API_KEY,
                 "Content-Type": content_type})
    with urllib.request.urlopen(req, timeout=180) as resp:
        result = json.loads(resp.read())
    upload_id = result.get("id") or result.get("uploadId")
    print(f"    uploaded to bundle.social: {upload_id} ({len(data):,} bytes)")
    return upload_id


def _bundle_post(caption, card_path):
    """Upload the card(s), then publish as a Snapchat Story.
    card_path may be one path or a list of paths (a multi-frame story)."""
    if not (BUNDLE_API_KEY and BUNDLE_TEAM_ID):
        raise SystemExit("BUNDLE_API_KEY and BUNDLE_TEAM_ID must both be set")
    if not card_path:
        return {"status": "error", "message": "bundle.social needs the card file"}

    cards = [card_path] if isinstance(card_path, (str, Path)) else list(card_path)

    try:
        upload_ids = [bundle_upload(c) for c in cards]
        upload_id = upload_ids[0]
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()[:400]
        print(f"  ! bundle.social upload {exc.code}: {body}")
        if "1010" in body:
            print("    (Cloudflare blocked the request — bot protection. If this")
            print("     persists with browser headers, ask bundle.social to allow")
            print("     GitHub Actions IPs for your account.)")
        return {"status": "error", "code": exc.code, "message": body}
    except Exception as exc:
        print(f"  ! bundle.social upload failed: {exc}")
        return {"status": "error", "message": str(exc)}
    if not upload_id:
        return {"status": "error", "message": "no upload id returned"}
    upload_ids = [u for u in upload_ids if u]

    payload = {
        "teamId": BUNDLE_TEAM_ID,
        "title": caption[:50],
        # current time with SCHEDULED means "publish now"
        "postDate": datetime.now(timezone.utc).isoformat(),
        "status": "SCHEDULED",
        "socialAccountTypes": ["SNAPCHAT"],
        "data": {"SNAPCHAT": {"type": "STORY", "text": caption,
                              "uploadIds": upload_ids}},
    }
    req = urllib.request.Request(
        f"{BUNDLE_BASE.rstrip('/')}/post", data=json.dumps(payload).encode(),
        headers={**BUNDLE_HEADERS, "x-api-key": BUNDLE_API_KEY,
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()[:400]
        print(f"  ! bundle.social post {exc.code}: {body}")
        return {"status": "error", "code": exc.code, "message": body}
    except Exception as exc:
        print(f"  ! bundle.social post failed: {exc}")
        return {"status": "error", "message": str(exc)}


def _zernio(path, payload):
    """Call the Zernio API. Returns the decoded response, or an error dict."""
    if not ZERNIO_API_KEY:
        raise SystemExit("ZERNIO_API_KEY is not set")
    req = urllib.request.Request(
        f"{ZERNIO_BASE.rstrip('/')}/{path.lstrip('/')}",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {ZERNIO_API_KEY}",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()[:400]
        print(f"  ! Zernio {exc.code}: {body}")
        return {"status": "error", "code": exc.code, "message": body}
    except Exception as exc:
        print(f"  ! Zernio request failed: {exc}")
        return {"status": "error", "message": str(exc)}


def post_story(caption, media_urls, card_path=None):
    """Publish the card as a Snapchat Story.

    bundle.social uploads the file itself; the others take a public URL.
    """
    if POST_PROVIDER == "bundle":
        print(f"    posting via bundle.social -> {BUNDLE_BASE}")
        return _bundle_post(caption, card_path)

    if POST_PROVIDER == "ayrshare":
        return _ayrshare("post", {
            "post": caption,
            "platforms": ["snapchat"],
            "mediaUrls": media_urls,
        })

    post = {
        "content": caption,
        "platforms": [{"platform": "snapchat"}],
        "mediaUrls": media_urls,
    }
    if ZERNIO_ACCOUNT_ID:
        post["platforms"][0]["accountId"] = ZERNIO_ACCOUNT_ID
    print(f"    posting via zernio -> {ZERNIO_BASE}")
    return _zernio("posts", post)


# --------------------------------------------------------------------------

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"    Arabic shaping via {'libraqm' if HAS_RAQM else 'arabic-reshaper'}")

    if PINNED_EVENT:
        print(f"1/4 pinned event — skipping feeds: {PINNED_EVENT[:90]}")
        items = []
    else:
        print("1/4 fetching feeds...")
        items = fetch_headlines()
        if len(items) < 5:
            raise SystemExit(f"Only {len(items)} items fetched — aborting rather than posting thin.")
        print(f"    {len(items)} unique recent items")

    print("2/4 summarizing...")
    posted = load_posted()
    if posted:
        print(f"    skipping {len(posted)} stories posted in the last "
              f"{REMEMBER_DAYS} days")
    result = summarize(items, [e["headline"] for e in posted],
                       pinned=PINNED_EVENT)
    stories = result.get("stories", [])[:CANDIDATES]
    caption = result.get("caption", "موجز اليوم")

    if not stories:
        if PINNED_EVENT:
            reason = result.get("reason", "بلا سبب مذكور")
            print(f"    pinned event NOT confirmed — aborting: {reason}")
            notify(f"🚨❌ {ksa_stamp()} — الحدث المثبّت لم يتأكد فلم يُنشر\n"
                   f"{PINNED_EVENT[:150]}\nالسبب: {reason}")
            raise SystemExit("pinned event unconfirmed — no card, nothing posted")
        print("    no stories returned — not posting this run")
        notify(f"⚠️ {ksa_stamp()} — no card: the model returned no stories")
        return

    for s in stories:
        print(f"    • {s['headline']}  ({s.get('source')})")

    print("3/4 finding a photo and rendering...")
    stamp = ksa_stamp()
    hero = OUT_DIR / "hero.jpg"

    chosen, photo, credit = None, None, None
    recent_candidate = None
    Path(str(hero) + ".recentkeep").unlink(missing_ok=True)

    def _article(story):
        link = story.get("link")
        if not link:
            return None, None
        photo, domain = fetch_article_photo(link, hero)
        if photo and not domain:
            domain = urllib.parse.urlparse(link).netloc.replace("www.", "")
        return photo, (DOMAIN_CREDITS.get(domain, domain) if domain else None)

    def _spa(story):
        # SPA is a Saudi archive — pointless for a story about Google
        if story.get("scope", "world") != "saudi":
            return None, None
        return fetch_spa_photo(story.get("image_queries_ar", []), hero)

    def _commons(story):
        saudi = story.get("scope", "world") == "saudi"
        return fetch_commons_photo(story.get("image_queries", []), hero,
                                   need_saudi=saudi)

    def _loc(story):
        saudi = story.get("scope", "world") == "saudi"
        return fetch_loc_photo(story.get("image_queries", []), hero,
                               need_saudi=saudi)

    def _openverse(story):
        saudi = story.get("scope", "world") == "saudi"
        return fetch_openverse_photo(story.get("image_queries", []), hero,
                                     need_saudi=saudi)

    def _stock(story):
        if not PEXELS_API_KEY:
            return None, None
        saudi = story.get("scope", "world") == "saudi"
        found = fetch_photo(story.get("image_queries", []), hero,
                            need_saudi=saudi)
        return found, ("Pexels" if found else None)

    def _local(story):
        return fetch_local_photo(story.get("image_queries_ar", []),
                                 story.get("image_queries", []), hero)

    SOURCES = {"article": _article, "spa": _spa, "commons": _commons,
               "loc": _loc, "openverse": _openverse, "stock": _stock}

    # whatever the workflow selected goes first, then the rest in a sensible
    # order. The local library is always tried first — it's curated.
    # Commons and the Library of Congress sit ahead of Openverse: both are
    # curated collections with real licence metadata, and between them they
    # cover the two cases Openverse is worst at — a named person, and a
    # subject that only exists in historical photography.
    order = ["article", "spa", "commons", "loc", "openverse", "stock"]
    if IMAGE_SOURCE in order:
        order.remove(IMAGE_SOURCE)
        order.insert(0, IMAGE_SOURCE)
    print(f"    photo order: local, {', '.join(order)}")

    for i, story in enumerate(stories, 1):
        if IMAGE_SOURCE == "none":
            chosen = story
            break
        print(f"    [{i}/{len(stories)}] {story['headline']}")

        photo, credit = _local(story)
        for name in order:
            if photo is not None:
                break
            photo, credit = SOURCES[name](story)

        if photo:
            chosen = story
            break
        if recent_candidate is None and \
                Path(str(hero) + ".recentkeep").exists():
            recent_candidate = story        # remember whose search kept it
        print("      no usable photo — trying the next story")

    if chosen is None and recent_candidate is not None:
        # every story exhausted its fresh options — a repeated photo is a
        # flaw, a dead run is worse
        photo, credit = recent_fallback(hero), None
        chosen = recent_candidate

    if chosen is None:
        if REQUIRE_PHOTO:
            print(f"  ! none of the {len(stories)} stories could be illustrated "
                  "— not posting this run")
            notify(f"⚠️ {ksa_stamp()} — no card: none of the "
                   f"{len(stories)} stories had a usable photo")
            return
        chosen, photo, credit = stories[0], None, None

    stories = [chosen]
    card = render_story({
        "title": chosen["headline"],
        "body": chosen.get("summary", ""),
        "punch": chosen.get("takeaway", ""),
        "sources": [chosen.get("source", "")],
    }, OUT_DIR / f"{stamp}-brief.png", photo, credit)

    if photo:
        # registered even on hybrid runs: the card reached Telegram and may
        # be published later — its photo is spent either way
        register_photos([photo], "news")

    if DRY_RUN:
        print(f"4/4 DRY_RUN — nothing posted. Card at {Path(card).resolve()}")
        # the post flag gates PUBLISHING only — it never gates reporting.
        # A held card written only to disk/artifact is a card never seen.
        notify(f"{RECENT_REUSE_WARNING}[DRY RUN] would have posted: "
               f"{chosen['headline']}\n({stamp} — البطاقة مرفقة؛ "
               "للنشر فعلاً شغّل daily مع تفعيل post)",
               card)
        return

    if not POST_ENABLED:
        print("4/4 hybrid mode — publishing the card, not posting to Snapchat")
        url = publish_via_github(card)
        repo = os.getenv("GITHUB_REPOSITORY", "")
        branch = os.getenv("GITHUB_REF_NAME", "main")
        print(f"    today's card: {url}")
        if repo:
            print("    always-latest link: https://raw.githubusercontent.com/"
                  f"{repo}/{branch}/{CARDS_DIR}/latest.png")
        # still record it, so the next run doesn't pick the same story
        commit_and_push(save_posted(posted, stories), f"card {stamp}")
        notify(f"{RECENT_REUSE_WARNING}📰 {stamp}\n{chosen['headline']}\n\n"
               f"{chosen.get('takeaway', '')}", card)
        return

    if not quota_ok():
        deliver_unposted(card, chosen["headline"])
        return

    print("4/4 posting to Snapchat...")
    if POST_PROVIDER == "ayrshare" and not AYRSHARE_API_KEY:
        raise SystemExit("AYRSHARE_API_KEY is not set")

    # bundle.social uploads the file itself, so no public URL is needed
    url = None
    if POST_PROVIDER != "bundle":
        url = publish_via_github(card) if MEDIA_MODE == "github" else upload_media(card)
        print(f"    media: {url}")
    response = post_story(caption, [url] if url else [], card)
    print("   ", response)

    # only record them as covered once the post actually went out
    if post_ok(response):
        state = save_posted(posted, stories)
        commit_and_push(state, f"posted {stamp}")
        commit_and_push(quota_bump(), f"quota {stamp}")
        notify(f"{RECENT_REUSE_WARNING}✅ posted {stamp}\n{chosen['headline']}", card)
    else:
        notify(f"❌ {stamp} — Snapchat post failed\n"
               f"{describe_failure(response)}")


if __name__ == "__main__":
    main()
