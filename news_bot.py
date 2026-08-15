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
    ("اليوم",        "https://www.alyaum.com/rssFeed/1005"),
    ("الشرق الأوسط", "https://aawsat.com/feed"),
]

STORIES_PER_DAY = int(os.getenv("STORIES_PER_DAY", "4"))
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

BRIEF_TITLE = os.getenv("BRIEF_TITLE", "ملخص تنفيذي - أخبار السعودية")

STATE_FILE = Path("state/posted.json")
REMEMBER_DAYS = int(os.getenv("REMEMBER_DAYS", "3"))


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
    "٪": "%", "٬": ",", "٫": ".", "؊": "-",
    "—": "-", "–": "-", "―": "-", "−": "-", "‐": "-", "‑": "-",
    "•": "،", "·": "،", "…": "...", "‎": "", "‏": "",
    "“": '"', "”": '"', "„": '"', "‘": "'", "’": "'",
    "\u00a0": " ", "\u200b": "", "\u2066": "", "\u2069": "",
}

# If the font can't draw these, meaning gets mangled — so we refuse to use it.
REQUIRED_CHARS = "0123456789%-.,:()اب"

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

ستصلك عناوين اليوم. اختر حتى {n} أخبار سعودية مهمة فقط. المعيار صارم: \
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
- المشاهير والفن، والرياضة إلا إذا كانت حدثاً وطنياً كبيراً
- الأخبار الدولية التي لا علاقة لها بالمملكة

اختبار الأهمية: هل سيظل هذا الخبر مهماً لشخص في مدينة أخرى بعد أسبوع؟ \
إن كان الجواب لا، فاستبعده.

الأولوية عند الاختيار: القرار الرسمي أولاً، ثم الأثر على أكبر عدد من الناس، \
ثم حجم الرقم.

مهم جداً: إن لم تجد {n} أخبار تستوفي المعيار، أعد عدداً أقل. لا تملأ العدد \
بأخبار ضعيفة. خبران مهمان أفضل من أربعة عادية. وإن لم تجد أي خبر مهم، أعد \
قائمة stories فارغة.
لا تختر خبرين عن الحدث نفسه.

لكل خبر اكتب:
- headline: عنوان لا يتجاوز ٥٥ حرفاً، واضح ومباشر، بدون نقطة في نهايته
- summary: جملتان قصيرتان، لا تتجاوزان ١٥٠ حرفاً، بلغة عربية فصحى بسيطة
- source: اسم المصدر كما ورد لك
- لا تذكر أي معلومة غير موجودة في العنوان والوصف المعطى لك. لا تخمّن.

واكتب أيضاً caption واحداً: لا يتجاوز ١٢٠ حرفاً، نص المنشور المرافق.

أجب بصيغة JSON فقط. بدون markdown وبدون أي مقدمة:
{{"caption": "...", "stories": [{{"headline": "...", "summary": "...", "source": "..."}}]}}"""


def summarize(items, already_posted=()):
    if not ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY is not set")

    feed_text = "\n".join(
        f"[{i['source']}] {i['title']} — {i['summary']}"
        for i in items[:MAX_HEADLINES_TO_MODEL]
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
            "system": SYSTEM_PROMPT.format(n=STORIES_PER_DAY),
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
        return json.loads(text[start:end + 1])

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

        first = True
        for line in _wrap(draw, story["headline"], f_head, max_w - 44, kw):
            add("head", line, f_head, lh_head, ACCENT, 44, first)
            first = False

        add("gap", "", None, int(14 * scale), None, 0)
        for line in _wrap(draw, story["summary"], f_body, max_w - 44, kw):
            add("body", line, f_body, lh_body, (206, 212, 228), 44)

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
            draw.line([(margin, y), (right, y)], fill=(58, 66, 90), width=2)
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
    git("add", str(dest))
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
    stories = result.get("stories", [])[:STORIES_PER_DAY]
    caption = result.get("caption", "موجز اليوم")

    if not stories:
        print("    nothing met the bar for a major story — not posting this run")
        return
    if len(stories) < STORIES_PER_DAY:
        print(f"    only {len(stories)} of {STORIES_PER_DAY} met the bar "
              "— posting the ones that did")
    for s in stories:
        print(f"    • {s['headline']}  ({s.get('source')})")

    print("3/4 rendering card...")
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    card = render_brief(stories, OUT_DIR / f"{stamp}-brief.png")

    if DRY_RUN:
        print(f"4/4 DRY_RUN — nothing posted. Card at {Path(card).resolve()}")
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


if __name__ == "__main__":
    main()
