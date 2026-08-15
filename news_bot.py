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
    ("عكاظ",          "https://www.okaz.com.sa/rssFeed/190"),
    ("المدينة",        "https://www.al-madina.com/rssFeed/193"),
    ("اليوم",          "https://www.alyaum.com/rssFeed/1005"),
    ("الشرق الأوسط",   "https://aawsat.com/feed"),
    ("العربية",        "https://www.alarabiya.net/.mrss/ar/saudi-today.xml"),
]

STORIES_PER_DAY = int(os.getenv("STORIES_PER_DAY", "3"))
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "30"))
MAX_HEADLINES_TO_MODEL = 60

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
AYRSHARE_API_KEY = os.getenv("AYRSHARE_API_KEY", "").strip()
DRY_RUN = os.getenv("DRY_RUN", "").strip() not in ("", "0", "false", "False")

MEDIA_MODE = os.getenv("MEDIA_MODE", "github").strip()
CARDS_DIR = "cards"

OUT_DIR = Path(os.getenv("OUT_DIR", "out"))
W, H = 1080, 1920

BG_TOP = (14, 17, 26)
BG_BOTTOM = (28, 34, 52)
ACCENT = (255, 215, 64)
TEXT = (245, 246, 250)
MUTED = (150, 158, 178)

USER_AGENT = "Mozilla/5.0 (compatible; daily-news-bot/1.0)"

AR_MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
             "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
AR_DAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس",
           "الجمعة", "السبت", "الأحد"]
AR_DIGITS = str.maketrans("0123456789", "0123456789")   # digits stay Latin


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

# Characters models commonly emit that many Arabic fonts don't include.
# Mapped to equivalents that are present nearly everywhere.
CHAR_FIXES = {
    "٪": "%", "٬": ",", "٫": ".", "؊": "-",
    "—": "-", "–": "-", "―": "-", "−": "-",
    "•": "،", "·": "،", "…": "...", "‎": "", "‏": "",
    "“": '"', "”": '"', "„": '"', "‘": "'", "’": "'",
    "\u00a0": " ", "\u200b": "", "\u2066": "", "\u2069": "",
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


def sanitize(text):
    """Normalize odd characters, then drop anything the font can't draw."""
    for bad, good in CHAR_FIXES.items():
        text = text.replace(bad, good)

    charset = _font_charset(_find_arabic_font(False))
    if charset is None:
        return text

    out = []
    for ch in text:
        if ch in " \n\t" or ord(ch) in charset:
            out.append(ch)
        elif ch not in _missing_reported:
            _missing_reported.add(ch)
            print(f"  ! font has no glyph for {ch!r} (U+{ord(ch):04X}) — removed")
    return "".join(out)


def ar(text):
    """Return (text_to_draw, draw_kwargs) for a piece of Arabic text."""
    text = sanitize(text)
    if HAS_RAQM:
        return text, {"direction": "rtl", "language": "ar"}
    return get_display(arabic_reshaper.reshape(text)), {}


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

SYSTEM_PROMPT = """أنت محرر موجز أخبار سعودي يومي يُنشر على سناب شات.

ستصلك عناوين اليوم. اختر {n} أخبار سعودية فقط — أي خبر يهم القارئ داخل المملكة \
العربية السعودية: قرارات حكومية، اقتصاد، مشاريع، تعليم، صحة، مجتمع، طقس مؤثر.

استبعد تماماً: الأخبار الدولية التي لا علاقة لها بالسعودية، وأخبار المشاهير \
والفن، والرياضة إلا إذا كانت حدثاً وطنياً كبيراً، والمقالات والآراء.
لا تختر خبرين عن الحدث نفسه.

لكل خبر اكتب:
- headline: عنوان لا يتجاوز ٥٥ حرفاً، واضح ومباشر، بدون نقطة في نهايته
- summary: جملتان قصيرتان، لا تتجاوزان ١٩٠ حرفاً، بلغة عربية فصحى بسيطة
- source: اسم المصدر كما ورد لك
- لا تذكر أي معلومة غير موجودة في العنوان والوصف المعطى لك. لا تخمّن.

واكتب أيضاً caption واحداً: لا يتجاوز ١٢٠ حرفاً، نص المنشور المرافق.

أجب بصيغة JSON فقط. بدون markdown وبدون أي مقدمة:
{{"caption": "...", "stories": [{{"headline": "...", "summary": "...", "source": "..."}}]}}"""


def summarize(items):
    if not ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY is not set")

    feed_text = "\n".join(
        f"[{i['source']}] {i['title']} — {i['summary']}"
        for i in items[:MAX_HEADLINES_TO_MODEL]
    )

    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 2000,
        "system": SYSTEM_PROMPT.format(n=STORIES_PER_DAY),
        "messages": [{"role": "user", "content": f"عناوين اليوم:\n\n{feed_text}"}],
    }

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Claude API {exc.code}: {exc.read().decode()[:500]}")

    text = "".join(b.get("text", "") for b in data.get("content", [])).strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    return json.loads(text)


# --------------------------------------------------------------------------
# 3. Render (right-to-left)
# --------------------------------------------------------------------------

def _find_arabic_font(bold):
    """Locate an Arabic-capable font, preferring bundled, then system."""
    bundled = Path("fonts") / ("NotoNaskhArabic-Bold.ttf" if bold
                               else "NotoNaskhArabic-Regular.ttf")
    if bundled.exists():
        return str(bundled)

    for path in [
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-{}.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-{}.ttf",
    ]:
        candidate = path.format("Bold" if bold else "Regular")
        if os.path.exists(candidate):
            return candidate

    # last resort: ask fontconfig for anything that covers Arabic
    try:
        query = ":lang=ar:weight=" + ("bold" if bold else "regular")
        out = subprocess.run(["fc-match", "-f", "%{file}", query],
                             capture_output=True, text=True, check=True)
        if out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    raise SystemExit("No Arabic font found — install fonts-noto-core or bundle one in fonts/")


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

    f_kicker = load_font(34, bold=True)
    f_title = load_font(64, bold=True)
    f_head = load_font(52, bold=True)
    f_body = load_font(36)
    f_num = load_font(40, bold=True)
    f_foot = load_font(30)

    _, kw = ar("م")               # shared draw kwargs

    def rtl(xy, text, font, fill, anchor="ra"):
        shaped, k = ar(text)
        draw.text(xy, shaped, font=font, fill=fill, anchor=anchor, **k)

    # header (accent bar now on the right)
    draw.rectangle([right - 110, 210, right, 220], fill=ACCENT)
    rtl((right, 258), arabic_date(), f_kicker, ACCENT)
    rtl((right, 316), "موجز السعودية", f_title, TEXT)

    y = 470
    for i, story in enumerate(stories, 1):
        if i > 1:
            draw.line([(margin, y), (right, y)], fill=(58, 66, 90), width=2)
            y += 54

        rtl((right, y), str(i).translate(AR_DIGITS), f_num, ACCENT)
        text_right = right - 78
        text_w = max_w - 78

        for line in _wrap(draw, story["headline"], f_head, text_w, kw):
            rtl((text_right, y), line, f_head, TEXT)
            y += 64

        y += 16
        for line in _wrap(draw, story["summary"], f_body, text_w, kw):
            rtl((text_right, y), line, f_body, (206, 212, 228))
            y += 50

        y += 10
        rtl((text_right, y), story.get("source", ""), f_foot, MUTED)
        y += 68

    draw.line([(margin, H - 190), (right, H - 190)], fill=(58, 66, 90), width=2)
    rtl((right, H - 155), "الموجز اليومي", f_foot, ACCENT)
    rtl((margin, H - 155), f"{len(stories)} أخبار".translate(AR_DIGITS),
        f_foot, MUTED, anchor="la")

    img.save(out_path, "PNG", optimize=True)
    return out_path


# --------------------------------------------------------------------------
# 4. Post
# --------------------------------------------------------------------------

def publish_via_github(png_path):
    import shutil
    import time

    repo = os.getenv("GITHUB_REPOSITORY")
    branch = os.getenv("GITHUB_REF_NAME", "main")
    if not repo:
        raise SystemExit("GITHUB_REPOSITORY unset — MEDIA_MODE=github only works in Actions")

    Path(CARDS_DIR).mkdir(exist_ok=True)
    dest = Path(CARDS_DIR) / Path(png_path).name
    shutil.copyfile(png_path, dest)

    def git(*args):
        subprocess.run(["git", *args], check=True, capture_output=True)

    git("config", "user.name", "news-bot")
    git("config", "user.email", "news-bot@users.noreply.github.com")
    git("add", str(dest))
    try:
        git("commit", "-m", f"card {dest.name}")
    except subprocess.CalledProcessError:
        pass
    git("push")

    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{CARDS_DIR}/{dest.name}"
    for _ in range(6):
        time.sleep(3)
        try:
            urllib.request.urlopen(
                urllib.request.Request(url, method="HEAD",
                                       headers={"User-Agent": USER_AGENT}),
                timeout=15)
            return url
        except urllib.error.HTTPError:
            continue
    raise SystemExit(f"Card not reachable at {url} — is the repo public?")


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


def post_story(caption, media_urls):
    return _ayrshare("post", {
        "post": caption,
        "platforms": ["snapchat"],
        "mediaUrls": media_urls,
    })


# --------------------------------------------------------------------------

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"    Arabic shaping via {'libraqm' if HAS_RAQM else 'arabic-reshaper'}")

    print("1/4 fetching feeds...")
    items = fetch_headlines()
    if len(items) < 5:
        raise SystemExit(f"Only {len(items)} items fetched — aborting rather than posting thin.")
    print(f"    {len(items)} unique recent items")

    print("2/4 summarizing...")
    result = summarize(items)
    stories = result["stories"][:STORIES_PER_DAY]
    caption = result.get("caption", "موجز اليوم")
    for s in stories:
        print(f"    • {s['headline']}  ({s.get('source')})")

    print("3/4 rendering card...")
    stamp = datetime.now().strftime("%Y-%m-%d")
    card = render_brief(stories, OUT_DIR / f"{stamp}-brief.png")

    if DRY_RUN:
        print(f"4/4 DRY_RUN — nothing posted. Card at {Path(card).resolve()}")
        return

    print("4/4 posting to Snapchat...")
    if not AYRSHARE_API_KEY:
        raise SystemExit("AYRSHARE_API_KEY is not set")
    url = publish_via_github(card) if MEDIA_MODE == "github" else upload_media(card)
    print(f"    media: {url}")
    print("   ", post_story(caption, [url]))


if __name__ == "__main__":
    main()
