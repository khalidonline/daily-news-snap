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
    # Saudi first — these fill tier 1
    ("اليوم",        "https://www.alyaum.com/rssFeed/1005"),
    ("الشرق الأوسط", "https://aawsat.com/feed"),
    # regional and world, for when Saudi news doesn't fill the card
    ("بي بي سي",     "https://feeds.bbci.co.uk/arabic/rss.xml"),
]

STORIES_PER_DAY = int(os.getenv("STORIES_PER_DAY", "1"))
# ask for several ranked candidates so we can skip any we can't illustrate
CANDIDATES = int(os.getenv("CANDIDATES", "5"))
REQUIRE_PHOTO = os.getenv("REQUIRE_PHOTO", "1").strip() not in ("", "0", "false")
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "30"))
MAX_HEADLINES_TO_MODEL = 60

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
AYRSHARE_API_KEY = os.getenv("AYRSHARE_API_KEY", "").strip()
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
    BRAND_INK = (13, 35, 66)        # navy, for the bar and the label
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
MIN_PHOTO_SCORE = int(os.getenv("MIN_PHOTO_SCORE", "10"))
# Openverse/Pexels are global libraries: without this, a US classroom passes
# for a Saudi school story. Article photos and SPA are Saudi by definition.
# a photo has to match at least this many of the query words. One weak match
# plus a Saudi mention got a WIPO meeting onto a story about insurance rules.
MIN_TERM_HITS = int(os.getenv("MIN_TERM_HITS", "2"))

# generic officialdom: true of a thousand events, specific to none
MEETING_HINTS = ("conference", "meeting", "delegation", "summit", "panel",
                 "signing ceremony", "press conference", "forum", "assembly",
                 "session", "committee", "podium", "speech", "award ceremony")

REQUIRE_SAUDI_CONTEXT = os.getenv("REQUIRE_SAUDI_CONTEXT", "1").strip() \
    not in ("", "0", "false", "False")

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
)


_BLOCKED_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in BLOCKED_IMAGE_TERMS) + r")\b",
    re.IGNORECASE)


def looks_like_a_graphic(path):
    """True for logo cards, infographics and other flat artwork.

    SPA's archive mixes branded graphics in with photographs; a logo card is
    mostly flat white with a small mark in the middle, so it reads very
    differently from a photo at the pixel level.
    """
    try:
        img = Image.open(path).convert("RGB")
    except Exception:
        return False

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
    return False


def _clear_generated_marker(path):
    """A real photo overwrites the file, so drop any stale marker."""
    marker = Path(str(path) + ".generated")
    if marker.exists():
        marker.unlink()


def _image_is_safe(text):
    """Reject candidates whose description touches conflict or sensitive themes.

    Whole words only — substring matching rejected 'warehouse' for containing
    'war', which quietly killed every result on ordinary searches.
    """
    match = _BLOCKED_RE.search(text or "")
    if match:
        print(f"  ! skipped an image ({match.group(0)!r} in its description)")
        return False
    return True

STATE_FILE = Path("state/posted.json")
QUOTA_FILE = Path("state/quota.json")
MONTHLY_POST_LIMIT = int(os.getenv("MONTHLY_POST_LIMIT", "0"))   # 0 = no limit
# "0" = hybrid: build the card and commit it, but don't publish to Snapchat
POST_ENABLED = os.getenv("POST_TO_SNAPCHAT", "1").strip() not in ("", "0", "false", "False")
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


def sanitize(text):
    """Normalize odd characters. NEVER deletes — a dropped '-' turns
    '8700-9400' into '87009400', which is a wrong number nobody notices.
    Anything unmappable is left in place to render as a visible box."""
    for bad, good in CHAR_FIXES.items():
        text = text.replace(bad, good)

    for wrong, right in COMMON_TYPOS.items():
        if wrong in text:
            print(f"  · fixed spelling: {wrong} -> {right}")
            text = text.replace(wrong, right)

    charset = _font_charset(_find_arabic_font(False))
    if charset is not None:
        for ch in text:
            if ch not in " \n\t" and ord(ch) not in charset \
                    and ch not in _missing_reported:
                _missing_reported.add(ch)
                print(f"  ! font has no glyph for {ch!r} (U+{ord(ch):04X}) "
                      f"— will render as a box")
    return text


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

ستصلك عناوين اليوم. اختر {n} أخبار سعودية مهمة فقط. المعيار صارم: \
الخبر الكبير الذي يستحق أن يتوقف له القارئ، لا مجرد خبر اليوم.

اختر فقط ما يستوفي واحداً من هذه على الأقل:
- قرار رسمي أو نظام أو لائحة جديدة صادرة عن جهة حكومية
- إعلان يمس حياة عدد كبير من الناس: أسعار، رسوم، تأشيرات، مواعيد الدراسة، الإجازات
- حدث اقتصادي كبير: صفقة أو اكتتاب أو مشروع باستثمار ضخم أو نتائج شركة كبرى
- تحذير أو تنبيه رسمي يمس السلامة أو الحركة أو الصحة العامة
- حدث وطني أو دولي كبير يخص المملكة مباشرة

استبعد تماماً:
- الأنشطة الروتينية والفعاليات المحلية الصغيرة والمهرجانات والمسابقات
- التصريحات العامة والزيارات البروتوكولية التي لا يتبعها قرار
- أخبار الشركات الصغيرة والإعلانات التجارية
- المقالات والتحليلات والآراء
- المشاهير والفن
- الرياضة، إلا إذا كانت حدثاً وطنياً كبيراً

اختبار الأهمية: هل سيظل هذا الخبر مهماً لشخص في مدينة أخرى بعد أسبوع؟ \
إن كان الجواب لا، فاستبعده.

الأولوية عند الاختيار: القرار الرسمي أولاً، ثم الأثر على أكبر عدد من الناس، \
ثم حجم الرقم.

النطاق: السعودية فقط. الخبر يجب أن يقع داخل المملكة أو يخصّها مباشرة \
(قرار حكومي سعودي، جهة سعودية، سوق سعودي، حدث على أرض المملكة).

استبعد كل ما عدا ذلك: الأخبار الإقليمية والعالمية التي لا تخصّ المملكة \
مباشرة، مهما كانت كبيرة.

أعد {n} أخبار مرتبة من الأهم إلى الأقل. سيُنشر خبر واحد فقط، والبقية بدائل \
تُستخدم إذا تعذّر إيجاد صورة مناسبة للخبر الأول.
لا تختر خبرين عن الحدث نفسه.

لكل خبر اكتب:
- headline: عنوان لا يتجاوز ٥٥ حرفاً، واضح ومباشر، بدون نقطة في نهايته
- summary: جملتان قصيرتان، لا تتجاوزان ١٥٠ حرفاً، بلغة عربية بسيطة
- takeaway: جملة واحدة قصيرة (حتى ٩٠ حرفاً) تقول شيئاً بنفسها، لا تعد بمعلومة.
  ممنوع التشويق: لا تكتب "أرقام تكشف..." أو "إليك ما يجب أن تعرفه" أو
  "تفاصيل مهمة عن..." — القارئ لن يفتح رابطاً، هذه آخر جملة يقرأها.
  ✗ "أرقام تكشف أي مناطق المملكة الأكثر أماناً على الطريق"
  ✓ "إذا تقود يومياً بين المدن، الفرق بين المناطق يوصل للضعف"
  ✓ "يهمك إذا كنت مستأجراً: المهلة تبدأ من تاريخ الإشعار لا من التوقيع"
- source: اسم المصدر كما ورد لك
- item: رقم الخبر كما ورد في القائمة المرقّمة (رقم فقط)
- لا تذكر أي معلومة غير موجودة في العنوان والوصف المعطى لك. لا تخمّن.
- اكتب كل الأرقام بالأرقام اللاتينية (2027, 306, 13) لا بالأرقام العربية الهندية.
- راجع الإملاء قبل الإجابة. الأخطاء الشائعة: "باطولة" والصحيح "بطولة"، "التى" والصحيح "التي"، "الذى" والصحيح "الذي".

- image_queries: ثلاث عبارات إنجليزية للبحث عن صورة لهذا الخبر تحديداً، مرتبة
  من الأدق إلى الأعم. كل عبارة تصف مشهداً ملموساً يمكن تصويره، لا فكرة مجردة.
  ✓ ["riyadh city skyline", "saudi arabia desert heat", "arabian gulf port"]
  كل عبارة إنجليزية يجب أن تتضمن "saudi" أو اسم مدينة سعودية (riyadh, jeddah,
  dammam, mecca, medina, khobar) — وإلا سيأتي البحث بصور من دول أخرى.
  ✗ "football stadium" (يعطي ملاعب أوروبية)   ✓ "riyadh stadium"
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
"takeaway": "...", "source": "...", "item": 0, "image_queries": ["...", "...", "..."], \
"image_queries_ar": ["...", "..."]}}]}}"""


def summarize(items, already_posted=()):
    if not ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY is not set")

    shortlist = items[:MAX_HEADLINES_TO_MODEL]
    feed_text = "\n".join(
        f"{n}. [{i['source']}] {i['title']} — {i['summary']}"
        for n, i in enumerate(shortlist, 1)
    )

    user_msg = f"عناوين اليوم:\n\n{feed_text}"
    if already_posted:
        covered = "\n".join(f"- {h}" for h in already_posted)
        user_msg += ("\n\nأخبار نُشرت بالفعل خلال الأيام الماضية — لا تخترها ولا "
                     f"تختر خبراً عن الحدث نفسه:\n{covered}")

    budget = int(os.getenv("MAX_TOKENS", "8000"))

    for _ in range(3):
        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": budget,
            "system": SYSTEM_PROMPT.format(n=CANDIDATES),
            "messages": [{"role": "user", "content": user_msg}],
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

        if data.get("stop_reason") == "max_tokens":
            if budget < 32000:
                budget = min(32000, budget * 2)
                print(f"  ! reply truncated — retrying with max_tokens={budget}")
                continue
            raise SystemExit("Reply truncated even at 32000 tokens")

        text = "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text").strip()
        text = re.sub(r"</?cite[^>]*>", "", text, flags=re.IGNORECASE)
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


def _candidate_paths(bold):
    weight = "Bold" if bold else "Regular"
    yield Path("fonts") / f"{FONT_FAMILY}-{weight}.ttf"
    for directory in ("/usr/share/fonts/truetype/noto",
                      "/usr/share/fonts/truetype",
                      "/usr/share/fonts"):
        yield Path(directory) / f"{FONT_FAMILY}-{weight}.ttf"


def _covers_required(path):
    charset = _font_charset(str(path))
    if charset is None:
        return True                       # unreadable table — don't block on it
    missing = [c for c in REQUIRED_CHARS if ord(c) not in charset]
    if missing:
        print(f"  ! {path} is missing {''.join(missing)!r} — falling back")
        return False
    return True


def _find_arabic_font(bold):
    """Locate an Arabic font that can actually draw digits, % and dashes."""
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
        _git("push")
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


def fetch_openverse_photo(queries, out_path):
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
            if REQUIRE_SAUDI_CONTEXT and _geo_adjust(described) <= 0:
                continue
            if _term_hits(described, terms) < MIN_TERM_HITS:
                continue
            score = _ov_score(item, terms)
            if any(h in described.lower() for h in MEETING_HINTS):
                score -= 15
            candidates.append((score, query, item))
        if any(c[0] >= 10 for c in candidates):
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
                with urllib.request.urlopen(req, timeout=45) as resp:
                    payload = resp.read()
            except Exception as exc:
                print(f"  ! {field} failed ({exc}) — trying the next image")
                continue
            if len(payload) < 8_000:
                continue
            data, best, best_score, best_query = payload, item, score, query
            if field == "thumbnail":
                print("    (using Openverse thumbnail — original host refused)")
            break
        if data:
            break

    if data is None:
        print("  ! every Openverse candidate failed to download")
        return None, None
    _clear_generated_marker(out_path)
    Path(out_path).write_bytes(data)

    creator = (best.get("creator") or "").strip() or best.get("source", "Openverse")
    licence = (best.get("license") or "").upper()
    version = best.get("license_version") or ""
    credit = f"{creator} / CC {licence} {version}".strip()

    print(f"    photo: {best.get('title') or '(untitled)'} — {credit} "
          f"[{best_query}]")
    return str(out_path), credit


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


def fetch_photo(queries, out_path):
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
            if REQUIRE_SAUDI_CONTEXT and _geo_adjust(photo.get("alt")) <= 0:
                continue
            if _term_hits(photo.get("alt"), terms) < MIN_TERM_HITS:
                continue
            score = _score(photo, terms)
            if any(h in (photo.get("alt") or "").lower() for h in MEETING_HINTS):
                score -= 15
            if score > best_score:
                best, best_score, best_query = photo, score, query

        # a clear match on an early (more specific) query wins outright
        if best_score >= 10:
            break

    if best is None:
        print("  ! no photo found — rendering without one")
        return None

    if best_score < MIN_PHOTO_SCORE:
        print(f"  ! best Pexels match scored {best_score:.0f} — "
              "posting without a photo instead")
        return None

    src = best["src"].get("large2x") or best["src"]["large"]
    try:
        with urllib.request.urlopen(src, timeout=60) as resp:
            Path(out_path).write_bytes(resp.read())
    except Exception as exc:
        print(f"  ! photo download failed: {exc}")
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
    y = 170
    draw.rectangle([right - 110, y, right, y + 10], fill=BRAND_INK)
    rtl((right, y + 46), BRAND, load_font(32, bold=True), BRAND_INK)

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
        rule_w = 260
        draw.line([(centre - rule_w // 2, H - 176),
                   (centre + rule_w // 2, H - 176)], fill=RULE, width=2)
        mid((centre, H - 130), "   •   ".join(parts), f_foot, muted)

    img.save(out_path, "PNG", optimize=True)
    return out_path


def render_story(brief, out_path, photo_path=None, photo_credit=None):
    """Light card: photo, a short paragraph, one line in red. Centred.
    Everything is measured before it is drawn, so nothing can overflow."""
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
    FOOTER_TOP = H - 200                  # above the credit line

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
    y = 170
    draw.rectangle([right - 110, y, right, y + 10], fill=BRAND_INK)
    rtl((right, y + 46), BRAND, load_font(32, bold=True), BRAND_INK)

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

    lines = []
    sources = "، ".join(brief.get("sources", [])[:3])
    if sources:
        lines.append(fit(f"المصدر: {sources}"))
    if photo_credit:
        # its own line, so a long source list can never truncate it away
        lines.append(fit(f"الصورة: {photo_credit}"))

    if lines:
        rule_w = 260
        top = H - 176 if len(lines) == 1 else H - 206
        draw.line([(centre - rule_w // 2, top),
                   (centre + rule_w // 2, top)], fill=RULE, width=2)
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

# the English blocklist won't catch Arabic captions
BLOCKED_AR_TERMS = (
    "جندي", "جنود", "عسكري", "عسكرية", "سلاح", "أسلحة", "بندقية", "مدفع",
    "حرب", "قتال", "اشتباك", "غارة", "قصف", "انفجار", "صاروخ",
    "شرطة", "اعتقال", "توقيف", "سجن", "سجين", "محكمة",
    "احتجاج", "مظاهرة", "عنف", "دماء", "إصابة", "مصاب", "جنازة", "عزاء",
    "حادث", "حريق", "كارثة", "ضحايا", "قتلى",
)


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


_BLOCKED_AR_RE = re.compile(
    r"(?<![\u0621-\u064A])(" + "|".join(re.escape(t) for t in BLOCKED_AR_TERMS)
    + r")(?![\u0621-\u064A])")


def _spa_safe(text):
    """Whole-word matching, so a blocked root doesn't reject an innocent word."""
    match = _BLOCKED_AR_RE.search(text or "")
    hit = match.group(0) if match else None
    if hit:
        print(f"  ! skipped an SPA image ({hit!r} in its caption)")
        return False
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


def _spa_image_urls(item):
    """Full size first, thumbnail as a fallback."""
    thumb = item.get("thumbnailUrl") or ""
    if not thumb:
        return []
    urls = []
    if "_th." in thumb:
        urls.append(SPA_BASE + thumb.replace("_th.", "."))
    urls.append(SPA_BASE + thumb)
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


def fetch_local_photo(queries_ar, queries_en, out_path):
    """Pick the best match from your own library. Returns (path, credit)."""
    library = load_local_images()
    if not library:
        return None, None

    terms = []
    for q in list(queries_ar or []) + list(queries_en or []):
        terms.extend(t.lower() for t in re.split(r"[\s,]+", str(q)) if len(t) > 2)
    if not terms:
        return None, None

    best, best_score = None, 0
    for entry in library:
        score = sum(10 for t in terms
                    if any(t in tag or tag in t for tag in entry["tags"]))
        if score > best_score:
            best, best_score = entry, score

    if best is None or best_score < MIN_PHOTO_SCORE:
        print(f"    local library: no match ({len(library)} images indexed)")
        return None, None

    import shutil as _shutil
    _clear_generated_marker(out_path)
    _shutil.copyfile(best["path"], out_path)
    print(f"    photo: {best['path'].name} from your library "
          f"(matched {best_score // 10} tag(s))")
    return str(out_path), best.get("credit")


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


ARK_MODEL = _clean_model_id(os.getenv("ARK_MODEL"), "seedream-4-0-250828")
ALLOW_GENERATED = os.getenv("ALLOW_GENERATED", "0").strip() not in ("", "0", "false", "False")
GENERATED_CREDIT = "صورة مولّدة بالذكاء الاصطناعي"

# appended to every prompt — the constraints matter more than the description
GEN_GUARD = (
    "Editorial illustration, photographic style, Saudi Arabian setting. "
    "CRITICAL: absolutely no text, letters, words, numbers, characters, "
    "signage, billboards, shop signs, building signs, banners, licence plates "
    "or any written script anywhere in the image, in any language. "
    "Buildings and vehicles must be completely unmarked and unbranded. "
    "No logos, brands, flags or emblems. "
    "No people's faces, no recognisable individuals, no crowds. "
    "No weapons, uniforms, police or military. "
    "Natural daylight, neutral and calm, documentary feel, wide shot."
)


def fetch_generated_photo(prompt, out_path):
    """Generate an illustration. Returns (path, credit) or (None, None).

    Only ever called for topic cards. A generated image on a news card would
    imply photography of a real event, so news never reaches this.
    """
    if not ALLOW_GENERATED:
        return None, None
    prompt = (prompt or "").strip()
    if not prompt:
        return None, None

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

    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
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
        return None, None
    except Exception as exc:
        print(f"  ! image generation failed: {exc}")
        return None, None

    # fal returns {"images":[{"url":...}]}, ModelArk returns {"data":[{"url":...}]}
    items = data.get("images") or data.get("data") or []
    link = items[0].get("url") if items else None
    if not link:
        print(f"  ! no image in the response: {str(data)[:250]}")
        return None, None

    try:
        with urllib.request.urlopen(link, timeout=120) as resp:
            Path(out_path).write_bytes(resp.read())
    except Exception as exc:
        print(f"  ! couldn't download the generated image: {exc}")
        return None, None

    Path(str(out_path) + ".generated").write_text("1", encoding="utf-8")
    print(f"    photo: generated via {IMAGE_GEN} — {prompt[:60]}")
    return str(out_path), GENERATED_CREDIT


def publish_via_github(png_path):
    import shutil
    import time

    repo = os.getenv("GITHUB_REPOSITORY")
    branch = os.getenv("GITHUB_REF_NAME", "main")
    if not repo:
        raise SystemExit("GITHUB_REPOSITORY unset — MEDIA_MODE=github only works in Actions")

    Path(CARDS_DIR).mkdir(exist_ok=True)

    # Arabic filenames can't go in a URL unencoded, and git/CDN handling of
    # them varies — commit under an ASCII name instead.
    stem = Path(png_path).stem
    ascii_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-")
    digest = hashlib.md5(stem.encode("utf-8")).hexdigest()[:8]
    dest = Path(CARDS_DIR) / f"{ascii_stem or 'card'}-{digest}.png"
    shutil.copyfile(png_path, dest)

    def git(*args):
        subprocess.run(["git", *args], check=True, capture_output=True)

    git("config", "user.name", "news-bot")
    git("config", "user.email", "news-bot@users.noreply.github.com")
    latest = Path(CARDS_DIR) / "latest.png"
    shutil.copyfile(png_path, latest)

    removed = prune_old_cards()
    git("add", "-A", CARDS_DIR)
    if removed:
        print(f"    pruned {removed} card(s) older than {KEEP_CARDS_DAYS} days")
    try:
        git("commit", "-m", f"card {dest.name}")
    except subprocess.CalledProcessError:
        pass
    git("push")

    url = ("https://raw.githubusercontent.com/"
           f"{repo}/{branch}/{CARDS_DIR}/{urllib.parse.quote(dest.name)}")
    for delay in (0, 2, 3, 5, 8, 10):
        time.sleep(delay)
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
    posted = load_posted()
    if posted:
        print(f"    skipping {len(posted)} stories posted in the last "
              f"{REMEMBER_DAYS} days")
    result = summarize(items, [e["headline"] for e in posted])
    stories = result.get("stories", [])[:CANDIDATES]
    caption = result.get("caption", "موجز اليوم")

    if not stories:
        print("    no stories returned — not posting this run")
        return

    for s in stories:
        print(f"    • {s['headline']}  ({s.get('source')})")

    print("3/4 finding a photo and rendering...")
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    hero = OUT_DIR / "hero.jpg"

    chosen, photo, credit = None, None, None
    for i, story in enumerate(stories, 1):
        if IMAGE_SOURCE == "none":
            chosen = story
            break
        print(f"    [{i}/{len(stories)}] {story['headline']}")
        photo, credit = None, None
        photo, credit = fetch_local_photo(story.get("image_queries_ar", []),
                                          story.get("image_queries", []), hero)
        if photo is None and story.get("link"):
            photo, domain = fetch_article_photo(story["link"], hero)
            if photo and not domain:
                domain = urllib.parse.urlparse(story["link"]).netloc.replace("www.", "")
            credit = DOMAIN_CREDITS.get(domain, domain) if domain else None
        if photo is None and IMAGE_SOURCE in ("spa", "openverse"):
            photo, credit = fetch_spa_photo(story.get("image_queries_ar", []), hero)
        if photo is None:
            photo, credit = fetch_openverse_photo(story.get("image_queries", []), hero)
        if photo is None and PEXELS_API_KEY:
            photo = fetch_photo(story.get("image_queries", []), hero)
            credit = "Pexels" if photo else None
        if photo:
            chosen = story
            break
        print("      no usable photo — trying the next story")

    if chosen is None:
        if REQUIRE_PHOTO:
            print(f"  ! none of the {len(stories)} stories could be illustrated "
                  "— not posting this run")
            return
        chosen, photo, credit = stories[0], None, None

    stories = [chosen]
    card = render_story({
        "title": chosen["headline"],
        "body": chosen.get("summary", ""),
        "punch": chosen.get("takeaway", ""),
        "sources": [chosen.get("source", "")],
    }, OUT_DIR / f"{stamp}-brief.png", photo, credit)

    if DRY_RUN:
        print(f"4/4 DRY_RUN — nothing posted. Card at {Path(card).resolve()}")
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
        return

    if not quota_ok():
        return

    print("4/4 posting to Snapchat...")
    if not AYRSHARE_API_KEY:
        raise SystemExit("AYRSHARE_API_KEY is not set")
    url = publish_via_github(card) if MEDIA_MODE == "github" else upload_media(card)
    print(f"    media: {url}")
    response = post_story(caption, [url])
    print("   ", response)

    # only record them as covered once the post actually went out
    if str(response.get("status", "")).lower() != "error":
        state = save_posted(posted, stories)
        commit_and_push(state, f"posted {stamp}")
        commit_and_push(quota_bump(), f"quota {stamp}")


if __name__ == "__main__":
    main()
