#!/usr/bin/env python3
"""
موضوع اليوم — بحث وتحليل -> سناب شات
Topic research mode.

You give it a topic. Claude searches the web (server-side web_search tool),
analyses what it finds, and returns a short Arabic brief. Rendered as one
card and posted the same way as the news bot.

    TOPIC="مستقبل الطاقة المتجددة في السعودية" python topic_bot.py

Reuses the fetch/post/render plumbing from news_bot.py.
"""

import json
import os
import re
import urllib.parse
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

try:
    from news_bot import (
        ANTHROPIC_API_KEY, CLAUDE_MODEL, DRY_RUN, MEDIA_MODE, OUT_DIR,
        W, H, BG_TOP, BG_BOTTOM, ACCENT, TEXT, MUTED, AR_DIGITS,
        ar, load_font, _wrap,
        publish_via_github, upload_media, post_story,
        fetch_headlines, commit_and_push, quota_ok, quota_bump,
        POST_ENABLED, CARDS_DIR,
        THEME, BRAND, USER_AGENT, IMAGE_SOURCE, PEXELS_API_KEY,
        draw_brand_badge, seal_photo, closing_seal,
        register_photos, recent_fallback, recent_warning,
        DOMAIN_CREDITS, fetch_article_photo, fetch_openverse_photo, fetch_photo,
        fetch_spa_photo, fetch_local_photo, fetch_generated_photo,
        ksa_stamp, notify, deliver_unposted, post_ok, describe_failure,
        POST_PROVIDER,
        _clean_model_id,
        REQUIRE_PHOTO,
        render_story,
    )
except ImportError as exc:
    raise SystemExit(
        f"news_bot.py is missing something topic_bot needs ({exc}).\n"
        "The two files must be uploaded together — get the latest news_bot.py "
        "into the repo and run again."
    )

TOPIC = os.getenv("TOPIC", "").strip()
TOPICS_FILE = Path(os.getenv("TOPICS_FILE", "topics.txt"))
REQUESTS_FILE = Path(os.getenv("REQUESTS_FILE", "requests.txt"))


def load_requests():
    """Topics followers asked for. These outrank everything else."""
    try:
        lines = REQUESTS_FILE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    return [ln.strip() for ln in lines
            if ln.strip() and not ln.strip().startswith("#")]
VOICE_FILE = Path(os.getenv("VOICE_FILE", "voice.txt"))


def load_voice():
    """Sample lines showing the register to imitate. Empty file = no examples."""
    try:
        lines = VOICE_FILE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    return [ln.strip() for ln in lines
            if ln.strip() and not ln.strip().startswith("#")]


def load_topics():
    """Topics from topics.txt.

    Each line is a topic, optionally followed by trigger keywords:
        الموضوع؟ | تضخم, أسعار, inflation
    A trigger appearing in yesterday's headlines pushes that topic up.
    Returns [{"topic": str, "triggers": [str]}].
    """
    if not TOPICS_FILE.exists():
        here = sorted(p.name for p in Path(".").iterdir() if p.is_file())
        print(f"  ! {TOPICS_FILE} not found. Files here: {', '.join(here)}")
        return []

    lines = TOPICS_FILE.read_text(encoding="utf-8").splitlines()
    topics = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, _, trig = line.partition("|")
        topics.append({
            "topic": name.strip(),
            "triggers": [t.strip().lower() for t in trig.split(",") if t.strip()],
        })
    if not topics:
        print(f"  ! {TOPICS_FILE} has {len(lines)} lines but none usable "
              "— are they all comments?")
    return topics


# --------------------------------------------------------------------------
# Seasonal calendar — Ramadan, Hajj, National Day, back to school, LEAP...
# --------------------------------------------------------------------------

SEASONS_FILE = Path(os.getenv("SEASONS_FILE", "seasons.txt"))

try:                                    # optional: only needed for hijri dates
    from hijri_converter import Hijri as _Hijri, Gregorian as _Gregorian
    HIJRI_OK = True
except ImportError:
    try:
        from hijridate import Hijri as _Hijri, Gregorian as _Gregorian
        HIJRI_OK = True
    except ImportError:
        HIJRI_OK = False


def load_seasons():
    """Parse seasons.txt into [{name, spec, before, after, topics}]."""
    try:
        lines = SEASONS_FILE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []

    seasons, current = [], None
    for raw in lines:
        line = raw.strip()
        if not line or (line.startswith("#") and not line.startswith("##")):
            continue
        if line.startswith("##"):
            parts = [p.strip() for p in line.lstrip("#").split("|")]
            if len(parts) < 2:
                continue
            current = {
                "name": parts[0],
                "spec": parts[1],
                "before": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0,
                "after": int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0,
                "topics": [],
            }
            seasons.append(current)
        elif current is not None:
            current["topics"].append(line)
    return [s for s in seasons if s["topics"]]


def _hijri_to_gregorian(month, day, today):
    """The Gregorian date of a hijri month/day, for whichever hijri year
    lands nearest today. Returns None if the converter isn't installed."""
    if not HIJRI_OK:
        return None
    try:
        this_hijri_year = _Gregorian(today.year, today.month, today.day) \
            .to_hijri().year
    except Exception:
        return None

    best = None
    for year in (this_hijri_year - 1, this_hijri_year, this_hijri_year + 1):
        try:
            g = _Hijri(year, month, day).to_gregorian()
        except Exception:
            continue
        candidate = date(g.year, g.month, g.day)
        if best is None or abs((candidate - today).days) < abs((best - today).days):
            best = candidate
    return best


def _season_window(season, today):
    """Return (start, end) dates for this season in the current cycle."""
    spec = season["spec"]
    before = timedelta(days=season["before"])
    after = timedelta(days=season["after"])

    if spec.startswith("hijri"):
        try:
            month, day = (int(x) for x in spec.split()[1].split("-"))
        except (ValueError, IndexError):
            return None
        peak = _hijri_to_gregorian(month, day, today)
        if peak is None:
            return None
        return peak - before, peak + after

    if spec.startswith("monthly"):
        body = spec.split(None, 1)[1] if " " in spec else ""
        try:
            if ".." in body:
                a, b = (int(x) for x in body.split(".."))
            else:
                a = b = int(body)
        except ValueError:
            return None
        day = today.day
        inside = (a <= day <= b) if a <= b else (day >= a or day <= b)
        return (today, today) if inside else None

    if spec.startswith("weekday"):
        names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        try:
            want = names.index(spec.split()[1].lower()[:3])
        except (ValueError, IndexError):
            return None
        return (today, today) if today.weekday() == want else None

    if spec.startswith("greg"):
        body = spec.split(None, 1)[1] if " " in spec else ""

        def parse_part(text, fallback_year):
            """Accept MM-DD or YYYY-MM-DD."""
            bits = [int(x) for x in text.split("-")]
            if len(bits) == 3:
                return date(bits[0], bits[1], bits[2]), True
            return date(fallback_year, bits[0], bits[1]), False

        try:
            if ".." in body:                       # a date range
                a, b = body.split("..")
                start, a_fixed = parse_part(a, today.year)
                end, b_fixed = parse_part(b, today.year)
                if not (a_fixed or b_fixed) and end < start:   # wraps new year
                    if today >= start:
                        end = date(today.year + 1, end.month, end.day)
                    else:
                        start = date(today.year - 1, start.month, start.day)
                return start - before, end + after

            peak, fixed = parse_part(body, today.year)
            if not fixed and (peak - today).days < -90:
                peak = date(today.year + 1, peak.month, peak.day)
            return peak - before, peak + after
        except (ValueError, IndexError):
            return None
    return None


_HIJRI_WARNED = False


def active_seasons(today=None):
    """Seasons whose window contains today, soonest peak first."""
    today = today or date.today()
    live = []
    for season in load_seasons():
        window = _season_window(season, today)
        if not window:
            if season["spec"].startswith("hijri") and not HIJRI_OK:
                global _HIJRI_WARNED
                if not _HIJRI_WARNED:
                    _HIJRI_WARNED = True
                    print("  ! hijri seasons (رمضان، الأعياد، الحج) need the "
                          "hijri-converter package — skipping them")
            continue
        start, end = window
        if start <= today <= end:
            live.append((abs((start - today).days), season))
    live.sort(key=lambda s: s[0])
    return [s for _, s in live]


USED_FILE = Path("state/topics_used.json")
COOLDOWN_DAYS = int(os.getenv("COOLDOWN_DAYS", "21"))
HARD_COOLDOWN_DAYS = int(os.getenv("HARD_COOLDOWN_DAYS", "5"))
SELECT_MODEL = _clean_model_id(os.getenv("SELECT_MODEL"), "claude-sonnet-5")
# when a season is running, prefer its topics over the general list
SEASON_PRIORITY = os.getenv("SEASON_PRIORITY", "1").strip() not in ("", "0", "false")
# manual runs can force a season by name, ignoring the calendar
FORCE_SEASON = os.getenv("FORCE_SEASON", "").strip()


def load_used():
    """Topics covered recently, so the picker doesn't repeat itself."""
    try:
        data = json.loads(USED_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    cutoff = (datetime.now() - timedelta(days=COOLDOWN_DAYS)).isoformat()
    return [e for e in data if e.get("at", "") >= cutoff]


def save_used(previous, topic):
    USED_FILE.parent.mkdir(parents=True, exist_ok=True)
    entries = previous + [{"topic": topic, "at": datetime.now().isoformat()}]
    USED_FILE.write_text(json.dumps(entries, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    return USED_FILE


SELECT_PROMPT = """أنت محرر تختار موضوع اليوم لموجز يُنشر على سناب شات لجمهور سعودي.

ستصلك قائمة مواضيع مرقّمة، وعناوين أخبار الأمس. اختر الموضوع الأكثر ارتباطاً \
بما يشغل الناس الآن بناءً على تلك العناوين.

معايير الاختيار:
- الموضوع الذي تلمسه أخبار الأمس مباشرة يسبق غيره.
- الموضوع الذي يجيب على سؤال يطرحه الناس بعد قراءة تلك الأخبار.
- إن لم يرتبط أي موضوع بالأخبار، اختر الأكثر أهمية للقارئ السعودي عموماً.
- المواضيع في قائمة "استُخدمت مؤخراً" ليست ممنوعة: يجوز إعادة أحدها إذا كانت \
أخبار الأمس تعيده بقوة إلى الواجهة وتضيف إليه جديداً. غير ذلك، فضّل موضوعاً جديداً.

كل موضوع مرفق بأسبابه بين قوسين: ارتباط بأخبار الأمس، أو موسم جارٍ، أو مرحلة من
الدورة الشهرية (الراتب، الفواتير، منتصف الشهر). رجّح ما يجمع أكثر من سبب.

أجب بصيغة JSON فقط: {"index": رقم الموضوع, "why": "سبب الاختيار في جملة قصيرة"}"""


SCORE_REQUEST = int(os.getenv("SCORE_REQUEST", "").strip() or "60")
SCORE_TRIGGER = int(os.getenv("SCORE_TRIGGER", "").strip() or "40")
SCORE_SEASON = int(os.getenv("SCORE_SEASON", "").strip() or "30")
SCORE_MONTHLY = int(os.getenv("SCORE_MONTHLY", "").strip() or "20")
SCORE_RECENT = int(os.getenv("SCORE_RECENT", "").strip() or "-25")
SCORE_UNUSED = int(os.getenv("SCORE_UNUSED", "").strip() or "5")

MONTHLY_SEASONS = ("أيام الراتب", "بداية الشهر والفواتير",
                   "منتصف الشهر", "قبل الراتب")


def score_topics(items, blocked, recent, forced_pool=None):
    """Score every topic on why it fits today.
    Returns a sorted list of {topic, score, reasons, driver}."""
    headline_text = " ".join(i.get("title", "") for i in items).lower()

    # narrower windows beat broad ones: Cityscape (4 days) should outrank
    # موسم الرياض (5+ months) when both are live
    in_season, season_bonus = {}, {}
    today = date.today()
    for season in active_seasons():
        spec = season["spec"]
        if spec.startswith("weekday"):
            bonus = 0          # a weekly slot recurs; a dated event doesn't
        else:
            # measure the event itself, not the lead-in we added around it
            bare = dict(season, before=0, after=0)
            window = _season_window(bare, today) or _season_window(season, today)
            span = (window[1] - window[0]).days if window else 999
            bonus = 12 if span <= 14 else (6 if span <= 45 else 0)
        for name in season["topics"]:
            if name not in in_season or bonus > season_bonus.get(name, 0):
                in_season[name] = season["name"]
                season_bonus[name] = bonus

    # topics.txt entries, season-only topics, and anything followers asked for
    entries = list(load_topics())
    known = {e["topic"] for e in entries}
    requested = set(load_requests())
    for name in requested:
        if name not in known:
            entries.append({"topic": name, "triggers": []})
            known.add(name)
    for name in in_season:
        if name not in known:
            entries.append({"topic": name, "triggers": []})

    scored = []
    for entry in entries:
        name = entry["topic"]
        if name in blocked:
            continue
        if forced_pool is not None and name not in forced_pool:
            continue

        score, reasons = 0, []

        if name in requested:
            score += SCORE_REQUEST
            reasons.append("طلبه متابع")

        hits = [t for t in entry["triggers"] if t and t in headline_text]
        if hits:
            score += SCORE_TRIGGER
            reasons.append(f"في أخبار الأمس: {'، '.join(hits[:3])}")

        season = in_season.get(name)
        if season:
            monthly = season in MONTHLY_SEASONS
            score += (SCORE_MONTHLY if monthly else SCORE_SEASON) \
                + season_bonus.get(name, 0)
            reasons.append(("الدورة الشهرية: " if monthly else "موسم: ") + season)

        if name in recent:
            score += SCORE_RECENT
            reasons.append("نُشر مؤخراً")
        else:
            score += SCORE_UNUSED

        if score > 0:
            scored.append({"topic": name, "score": score, "driver": season or "—",
                           "reasons": reasons or ["من القائمة العامة"]})

    scored.sort(key=lambda s: -s["score"])
    return scored


def report_shortlist(scored, when):
    """The plan: date/driver, topic, and why — side by side."""
    print()
    print(f"    خطة اختيار الموضوع — {when:%Y-%m-%d}")
    print(f"    {'الحدث / الدافع':<30}{'الموضوع':<46}السبب")
    print("    " + "-" * 108)
    for row in scored[:8]:
        print(f"    {row['driver'][:28]:<30}{row['topic'][:44]:<46}"
              f"{row['reasons'][0][:38]}  ({row['score']:+d})")
    print()


def choose_topic(exclude=()):
    """Pick the topic that best fits today's date, season and news."""
    if not load_topics():
        return ""

    used = load_used()
    exclude = set(exclude)
    hard_cutoff = (datetime.now() - timedelta(days=HARD_COOLDOWN_DAYS)).isoformat()
    blocked = {e["topic"] for e in used if e.get("at", "") >= hard_cutoff} | exclude
    recent = {e["topic"] for e in used} - blocked

    forced_pool = None
    if FORCE_SEASON:
        want = FORCE_SEASON.lower()
        matches = [s for s in load_seasons()
                   if want in s["name"].lower() or s["name"].lower() in want]
        if matches:
            forced_pool = {t for s in matches for t in s["topics"]}
            print(f"    forced season(s): {'، '.join(s['name'] for s in matches)}")
        else:
            print(f"  ! no season matching {FORCE_SEASON!r}. Available:")
            for s in load_seasons():
                print(f"      - {s['name']}")

    print("    reading yesterday's headlines...")
    try:
        items = fetch_headlines()
    except Exception as exc:
        print(f"  ! couldn't fetch headlines ({exc})")
        items = []

    scored = score_topics(items, blocked, recent, forced_pool)
    if not scored:
        print("  ! everything is on cooldown — ignoring it for this run")
        scored = score_topics(items, exclude, recent, forced_pool)
    if not scored:
        return ""

    report_shortlist(scored, datetime.now())
    shortlist = scored[:8]

    if not items or not ANTHROPIC_API_KEY:
        print(f"    no headlines to judge by — taking the top score")
        return shortlist[0]["topic"]

    listing = "\n".join(
        f"{n}. {row['topic']}  [{'، '.join(row['reasons'])}]"
        for n, row in enumerate(shortlist))
    headlines = "\n".join(f"- {i['title']}" for i in items[:50])
    recent_list = "\n".join(f"- {t}" for t in recent) or "لا يوجد"

    payload = {
        "model": SELECT_MODEL,
        "max_tokens": 500,
        "system": SELECT_PROMPT,
        "messages": [{"role": "user", "content":
                      f"المواضيع المرشحة:\n{listing}\n\n"
                      f"عناوين الأمس:\n{headlines}\n\n"
                      f"استُخدمت مؤخراً:\n{recent_list}"}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json",
                 "x-api-key": ANTHROPIC_API_KEY,
                 "anthropic-version": "2023-06-01"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read())
        text = "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text")
        a, b = text.find("{"), text.rfind("}")
        choice = json.loads(text[a:b + 1])
        topic = shortlist[int(choice["index"])]["topic"]
        print(f"    chose: {topic}")
        print(f"    why:   {choice.get('why', '')}")
        return topic
    except Exception as exc:
        print(f"  ! selection call failed ({exc}) — taking the top score")
        return shortlist[0]["topic"]


TOPIC_MODEL = _clean_model_id(os.getenv("TOPIC_MODEL"), "claude-opus-5")
# how many topics to try before giving up on finding a photo
TOPIC_ATTEMPTS = int(os.getenv("TOPIC_ATTEMPTS", "").strip() or "3")
MAX_SEARCHES = int(os.getenv("MAX_SEARCHES", "6"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "16000"))
POINTS = int(os.getenv("POINTS", "3"))
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "").strip()
HERO_HEIGHT = int(os.getenv("HERO_HEIGHT", "620"))


KICKER = os.getenv("KICKER", "ملخص تنفيذي")



# --------------------------------------------------------------------------
# Research
# --------------------------------------------------------------------------

SYSTEM_PROMPT = """أنت تكتب موجزاً يُنشر على سناب شات لجمهور سعودي عام.

سيعطيك المستخدم موضوعاً. ابحث في الإنترنت، ثم اكتب موجزاً يوقف القارئ عن التمرير: \
دقيق وموثّق، لكن بلغة قريبة وسهلة — لا لغة تقارير ولا بيانات رسمية.

الشكل المطلوب — ثلاثة عناصر فقط، كل عنصر فكرة واحدة:

- title: عنوان لا يتجاوز ٤٥ حرفاً. يقول ما الجديد، لا اسم الموضوع.

- body: فقرة واحدة، ثلاث جمل قصيرة كحد أقصى، لا تتجاوز ٢٦٠ حرفاً كاملة.
  الجملة الأولى: لماذا يخصّك هذا الآن.
  الجملة الثانية: الحقيقة الأساسية برقمها ومصدرها.
  الجملة الثالثة (اختيارية): تفصيل واحد يكمّلها.
  ممنوع حشر أكثر من فكرة في جملة واحدة. إن كان عندك تفصيلان، احذف الأضعف.

- takeaway: جملة واحدة فقط، لا تتجاوز ١١٠ حرفاً، فيها فكرة واحدة لا أكثر.
  إما نصيحة عملية، أو نتيجة تهمّ القارئ. ليست ملخصاً لكل ما سبق.
  ✗ "الإنفاق بلغ 1.03 مليار ريال، اشترِ قبل الذروة، وتذكّر أن الكتب مجانية"
    (ثلاث أفكار في سطر واحد)
  ✓ "اشترِ المستلزمات قبل الأسبوع الأخير — الأسعار ترتفع مع الزحمة"

- caption: نص المنشور المرافق، لا يتجاوز ١٢٠ حرفاً

- sources: أسماء المصادر (٢ إلى ٤). إن كان المصدر أجنبياً فاكتبه بالعربية.

- image_queries: ثلاث عبارات إنجليزية للبحث عن صورة، مرتبة من الأدق إلى الأعم.
  كل عبارة تصف مشهداً ملموساً يمكن تصويره، وتتضمن "saudi" أو اسم مدينة سعودية.
  للمواضيع المالية صِف الجهة (وزارة، بورصة، مبنى) لا مشاهد المال:
  ✓ "Saudi Ministry of Finance building Riyadh"  ✗ "Saudi riyal banknotes"

- image_queries_ar: ثلاث كلمات مفتاحية عربية مفردة للبحث في أرشيف الصور
  السعودي — كلمة واحدة لكل عنصر، لا عبارات. ✓ ["الرياض", "مدارس", "طلاب"]
  للمواضيع المالية اطلب المؤسسة لا المال نفسه: الأرشيف الرسمي مليء بصور
  «المالية» و«تداول» ومبانيهما وخالٍ من مشاهد النقود.
  ✓ ["المالية", "تداول", "الميزانية"]  ✗ ["ريالات", "نقود", "أوراق نقدية"]

- image_prompt: وصف إنجليزي من جملة واحدة لمشهد واحد متماسك يمكن تصويره فعلاً.
  المكان يجب أن يكون منطقياً: الأدوات المدرسية على مكتب داخل غرفة، لا في الشارع.
  لا تجمع مشهدين في وصف واحد.
  ✓ "a study desk with notebooks and a backpack in a bright Saudi home room"
  ✗ "a desk with school supplies and a Saudi neighbourhood street behind it"

- source_url: رابط الخبر الرسمي الأدق الذي اعتمدت عليه.

قواعد الأسلوب — قريبة من الناس، لا رسمية:
- ابدأ بما يهم القارئ شخصياً، لا بالجهة التي أصدرت الخبر.
  ✗ "أعلنت الهيئة العامة للعقار تعديلاً على..."  ✓ "إيجارك قد يتغير السنة الجاية، وهذا السبب"
- خاطب القارئ مباشرة حين يناسب: "إذا كنت تفكر في شراء سيارة الآن..."
- جمل قصيرة. تجنّب التراكيب الطويلة والمبني للمجهول.
- استخدم كلمات الحياة اليومية بدل المصطلح المؤسسي: "تكلفة" لا "الكلفة التشغيلية".
- إن وُجدت أمثلة نبرة في نهاية هذه التعليمات فهي المرجع الأول للمستوى اللغوي.
  وإن لم توجد، فاكتب بفصحى مبسّطة قريبة من كلام الناس في السعودية.
- يجوز أن يكون العنوان سؤالاً أو مفارقة تجذب الانتباه — بشرط أن يكون صادقاً ولا يبالغ.
- ادّعاء البطاقة لا يجوز أن يكون بديهياً. الاختبار: هل يستطيع قارئ لم
  يبحث الموضوع قط أن يخمّن الجواب من مجرد طرح السؤال؟ إن نعم، فليست
  بطاقة — أعد بناءها على الحقيقة المحددة القابلة للتحقق، وغالباً
  تجدها جاهزة في متن ما كتبت.
  ✗ «أول خطوة في سوق الأسهم ليست شراء سهم» — الجواب «افتح محفظة»
    يعرفه كل من سأل السؤال أصلاً؛ والمحتوى الحقيقي كان في المتن:
    العمولة لها سقف 0.155% أي 15.5 ريالاً لكل 10,000.
  ✓ «عمولة تداول الأسهم لها سقف نظامي: 15.5 ريالاً لكل 10,000 تستثمرها»
    — هذا هو البطاقة.
- قدّم الرقم الذي يتصرف القارئ بناءً عليه أو يتحقق منه بنفسه: نسبة،
  سقف، حد، رسم، تاريخ سريان. وأخّر أو احذف نصائح التسلسل («أولاً افعل
  كذا ثم كذا») والتعريفات وكل ما قيمته توجيهٌ لا معلومة.
- ممنوع الحشو: "تجدر الإشارة"، "في هذا السياق"، "من الجدير بالذكر"، "وفي الختام".
- ممنوع الصفات الترويجية: هائل، مذهل، ضخم، تاريخي، غير مسبوق، ثورة.
- استخدم أفعالاً محايدة: تتغير، ترتفع، تنخفض، تزيد. وتجنّب الأفعال المبالِغة مثل: تقفز، تنهار، تشتعل، تتهاوى، تنفجر.
- لا تبدأ الفقرة برقم. الأرقام تدعم الفكرة ولا تحل محلها.
- جملة واحدة = فكرة واحدة. الجمل الطويلة المتشعبة ممنوعة.
- انسب كل رقم لمصدره بعبارة قصيرة: "وفق أرقام وزارة..."، "بحسب تقرير...".
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
- لا تستخدم مصطلحاً مهنياً دون شرحه في نفس الجملة.

قواعد اللهجة والمصطلح — اكتب بلسان سعودي رسمي:
- قل "المملكة" لا "السعودية" في كل مرة، و"المواطنين" و"المقيمين" حين يلزم.
- استخدم الأسماء الرسمية للجهات: "المركز الوطني للنخيل والتمور"، "الهيئة العامة \
للإحصاء"، "وكالة الأنباء السعودية (واس)".
- استخدم أسماء المناطق كما تُستخدم محلياً: القصيم، المنطقة الشرقية، عسير، جازان.
- العملة ريال، واذكر "مليار ريال" لا "مليار دولار" إن كان المصدر بالريال.
- تجنّب التعابير المصرية أو الشامية أو المترجمة حرفياً عن الإنجليزية.
- التواريخ ميلادية بالأشهر العربية المعروفة في المملكة: يناير، فبراير، مارس...
- استخدم المفردات السعودية المألوفة، وتجنّب التعابير المصرية أو الشامية.

ممنوع منعاً باتاً:
- أي وسوم أو أقواس مراجع داخل النص مثل <cite> أو [1] أو (المصدر: ...).
- النص يجب أن يكون نصاً عربياً نظيفاً فقط. ضع أسماء المصادر في حقل sources وحده.

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

قواعد المقارنات — إذا كان الموضوع يقارن السعودية بسوق آخر:
- حدّد المنتج بدقة كاملة في العنوان والنص: الطراز والفئة والسعة واللون إن لزم.
  للمنتجات ذات الإصدارات المتعددة (iPhone 17 / Air / Pro / Pro Max) اذكر أيها
  بالضبط وبأي سعة تخزين. "سعر iPhone" بلا تحديد مقارنة بلا معنى.
  ✓ "iPhone 17 سعة 256 جيجابايت"   ✗ "iPhone 17"
- قارن الشيء نفسه: نفس الطراز ونفس سنة الصنع ونفس الفئة، أو نفس نوع العقار
  ونفس المنطقة. مقارنة طرازين مختلفين مقارنة خاطئة.

- المصادر: خذ سعر السوق السعودي من متجر Apple السعودية أو جرير أو إكسترا أو
  الوكيل الرسمي، وسعر السوق الآخر من متجر الشركة الرسمي في ذلك البلد
  (Apple US مثلاً). لا تعتمد على مواقع مقارنة الأسعار أو المدونات أو المتاجر
  غير المعتمدة — أرقامها متضاربة وغير رسمية.
  إن اختلفت أسعار التجزئة بين المتاجر المحلية، اذكر نطاقاً واذكر المتاجر.
- حوّل كل الأسعار إلى الريال، واذكر أنك حوّلتها وبأي تاريخ للصرف.
- اذكر تاريخ السعر صراحة. أسعار السيارات والعقار تتغير، وسعر بلا تاريخ عديم القيمة.
- اذكر سبب الفرق، لأنه جوهر الموضوع: الضريبة، الرسوم الجمركية، الشحن،
  المواصفات المختلفة، أو الطلب المحلي. الفرق بلا تفسير يضلّل القارئ.
- إن كان السعر النهائي يشمل ضريبة في سوق ولا يشملها في آخر، قل ذلك.
- إن لم تجد سعرين موثوقين لنفس الشيء، اجعل title هو "لا توجد بيانات كافية للمقارنة"
  واشرح السبب. لا تقارن رقماً موثوقاً برقم تقديري.
- لا تذكر الضمان كسبب للفرق إلا إذا تحققت منه فعلاً. كثير من العلامات العالمية
  (ومنها Apple) تقدّم ضماناً دولياً، فادعاء "لا ضمان محلي" خطأ شائع.
  وكذلك لا تفترض فروق المواصفات دون دليل.
- انتبه إلى ما يشمله السعر المعلن: أسعار أمريكا لا تشمل ضريبة المبيعات
  (تختلف بين الولايات)، بينما السعر السعودي يشمل ضريبة القيمة المضافة 15%.
  قارن على أساس واحد وقل للقارئ أيهما تقارن.

- في takeaway: اذكر الخلاصة العملية، لا الرقم فقط.
  ✓ "الفرق 35% معظمه رسوم وضريبة، فالاستيراد لا يوفر بعد الحساب الكامل"
  وفي بطاقة المالية الحكومية يحمل السطر الأحمر دلالة الرقم، لا حكماً على
  أداء الدولة — انظر قواعد المالية العامة أدناه.

الأنظمة والقواعد السعودية:
- إذا كان الموضوع يمسّ مجالاً تنظّمه الدولة — الإيجارات، الرواتب، مكافأة
  نهاية الخدمة، الرسوم، التأمين، حماية المستهلك، الدفع الآجل، عقود العمل —
  فابحث عن النظام الساري قبل الكتابة، واذكره في البطاقة.
- البطاقة التي تعطي نصيحة عملية وتغفل النظام الذي يحكمها بطاقة ناقصة، حتى لو
  كانت كل أرقامها صحيحة.
- اذكر النظام بصيغته الحالية ومصدره الرسمي، وتاريخ آخر تحديث إن وُجد.
- مثال: بطاقة عن ارتفاع الإيجارات تنصح بتجديد العقد، دون ذكر ما إذا كان هناك
  سقف نظامي لرفع الإيجار، بطاقة مضلّلة.
- إن لم تجد نظاماً واضحاً، قل ذلك صراحة بدل الصمت عنه.

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

قواعد الدقة:
- اعتمد فقط على ما وجدته في البحث. لا تستخرج أرقاماً من ذاكرتك.
- إذا تضاربت المعلومات، قل ذلك واذكر التقديرين.
- إذا لم تجد ما يكفي، اجعل title هو "لا توجد معلومات كافية" واشرح السبب.

قبل أن تجيب، اقرأه كأنك رأيته في سناب شات: هل توقفت عنده أم مررت؟ هل يبدو \
كلاماً بشرياً أم بياناً رسمياً؟ وهل كل رقم منسوب لمصدره وله وحدة وتاريخ؟ \
إن كان أحد الجوابين لا، أعد الكتابة.

أجب بصيغة JSON فقط، بدون markdown وبدون مقدمة:
{{"title": "...", "body": "...", "takeaway": "...", "caption": "...", \
"image_queries": ["...", "...", "..."], "image_queries_ar": ["...", "...", "..."], \
"image_prompt": "...", "source_url": "...", "sources": ["...", "..."]}}"""


UNIT_WORDS = ("نقطة", "نقاط", "دولار", "دولاراً", "ريال", "ريالاً", "يورو",
              "مليون", "مليار", "ألف", "برميل", "برميلاً", "طن", "طناً", "كم",
              "متر", "يوم", "يوماً", "أيام", "شهر", "أشهر", "سنة", "سنوات",
              "أسبوع", "أسابيع", "ساعة", "حاوية", "قدماً", "بالمئة", "درجة",
              "عاماً", "عام", "سنوياً", "دقيقة", "كيلومتر", "كيلومترات",
              "هللة", "هللات", "كيلوواط", "ميغاواط", "جيجاواط", "واط",
              "لتر", "لتراً", "كيلو", "كيلوغرام", "غرام", "وحدة", "وحدات",
              "مقعد", "مقعداً", "شخص", "شخصاً", "زائر", "زائراً", "نسمة",
              "متراً", "أمتار", "هكتار", "مليونا", "مليارا")

MONTH_WORDS = ("يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو",
               "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر")


def warn_about_bare_numbers(brief):
    """Flag figures with neither a unit nor a date right after them —
    the reader can't tell whether 4,547 is dollars, points or something else."""
    chunks = [("body", brief.get("body", "")),
              ("takeaway", brief.get("takeaway", ""))]
    for point in brief.get("points", []):
        chunks.append((point.get("heading", "point"), point.get("text", "")))

    for where, text in chunks:
        for match in re.finditer(r"\d[\d,\.]*", text):
            token = match.group().rstrip(".,")
            if re.fullmatch(r"(19|20)\d{2}", token):
                continue                      # a year needs no unit
            tail = text[match.end():]
            if tail.startswith("%"):
                continue
            next_word = tail.strip().split(" ")[0].strip("،.:؛)") if tail.strip() else ""
            if next_word in UNIT_WORDS or next_word in MONTH_WORDS:
                continue
            print(f"  ! bare number {match.group()!r} in "
                  f"{where!r} — followed by {next_word!r}, "
                  f"no unit given")


CITE_RE = re.compile(r"</?cite[^>]*>", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]{1,80}>")


def strip_markup(value):
    """Remove citation tags and stray markup the model sometimes emits."""
    if isinstance(value, str):
        cleaned = CITE_RE.sub("", value)
        cleaned = TAG_RE.sub("", cleaned)
        return re.sub(r"\s{2,}", " ", cleaned).strip()
    if isinstance(value, list):
        return [strip_markup(v) for v in value]
    if isinstance(value, dict):
        return {k: strip_markup(v) for k, v in value.items()}
    return value


def research(topic):
    if not ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY is not set")

    messages = [{"role": "user", "content": f"الموضوع: {topic}"}]
    searches = 0
    budget = MAX_TOKENS

    system = SYSTEM_PROMPT.format(n=POINTS)
    voice = load_voice()
    if voice:
        samples = "\n".join(f"- {v}" for v in voice[:15])
        system += ("\n\nأمثلة على النبرة المطلوبة — احتذِ بمستواها اللغوي "
                   "وإيقاعها وطريقة مخاطبتها للقارئ. لا تنسخ عباراتها ولا "
                   "تستخدمها كما هي، بل اكتب بنفس الروح عن موضوعك:\n"
                   f"{samples}")
        print(f"    voice: {len(voice)} sample lines from {VOICE_FILE}")

    # pause_turn continuations plus up to one budget retry
    for _ in range(6):
        payload = {
            "model": TOPIC_MODEL,
            "max_tokens": budget,
            "system": system,
            "messages": messages,
            "tools": [{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": MAX_SEARCHES,
            }],
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
        data = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=300) as resp:
                    data = json.loads(resp.read())
                break
            except urllib.error.HTTPError as exc:
                body = exc.read().decode()[:400]
                # 429 and 529 (overloaded) are transient: exponential
                # backoff with jitter, four attempts, then give up — a
                # momentary API brownout must not cost a whole run.
                if exc.code in (429, 503, 529) and attempt < 3:
                    import random
                    import time as _t
                    wait = (2 ** (attempt + 1)) + random.uniform(0, 1.5)
                    print(f"  ! Claude API {exc.code} (transient) — "
                          f"backing off {wait:.0f}s ({attempt + 1}/3)")
                    _t.sleep(wait)
                    continue
                raise RuntimeError(f"Claude API {exc.code}: {body}")
            except (TimeoutError, urllib.error.URLError, OSError) as exc:
                # RemoteDisconnected and friends are OSErrors, not
                # HTTPErrors — a dropped socket must not escape unhandled.
                if attempt == 3:
                    raise RuntimeError(
                        f"Claude unreachable after 4 attempts: {exc}")
                print(f"  ! Claude call failed ({exc}) — retrying "
                      f"({attempt + 1}/3)")
                import time as _t
                _t.sleep(8)

        content = data.get("content", [])
        searches += sum(1 for b in content if b.get("type") == "server_tool_use")

        if data.get("stop_reason") == "pause_turn":
            messages.append({"role": "assistant", "content": content})
            continue

        if data.get("stop_reason") == "max_tokens":
            if budget < 32000:
                budget = min(32000, budget * 2)
                print(f"  ! reply truncated — retrying with max_tokens={budget}")
                messages = [{"role": "user", "content": f"الموضوع: {topic}"}]
                continue
            raise SystemExit(
                "Reply truncated even at 32000 tokens — lower MAX_SEARCHES "
                "or narrow the topic")

        text = "".join(b.get("text", "") for b in content
                       if b.get("type") == "text").strip()
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()

        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise SystemExit(f"No JSON in reply: {text[:300]}")

        print(f"    {searches} web searches used")
        return strip_markup(json.loads(text[start:end + 1]))

    raise SystemExit("Research didn't finish after 4 continuations")


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------

def _build_layout(draw, brief, scale, max_w, kw):
    """Measure the whole card before drawing any of it.
    Returns (blocks, total_height) where each block carries its own font."""
    f_title = load_font(int(58 * scale), bold=True)
    f_lead = load_font(int(38 * scale))
    f_head = load_font(int(40 * scale), bold=True)
    f_body = load_font(int(34 * scale))

    lh_title, lh_lead = int(78 * scale), int(62 * scale)
    lh_head, lh_body = int(58 * scale), int(56 * scale)

    blocks, height = [], 0

    def add(kind, text, font, line_h, fill, indent, first=False):
        nonlocal height
        blocks.append({"kind": kind, "text": text, "font": font, "lh": line_h,
                       "fill": fill, "indent": indent, "first": first})
        height += line_h

    for line in _wrap(draw, brief["title"], f_title, max_w, kw):
        add("title", line, f_title, lh_title, TEXT, 0)

    lead = brief.get("lead", "").strip()
    if lead:
        add("gap", "", None, int(34 * scale), None, 0)
        for line in _wrap(draw, lead, f_lead, max_w - 24, kw):
            add("lead", line, f_lead, lh_lead, (255, 236, 170), 24)

    for i, point in enumerate(brief.get("points", [])):
        add("gap", "", None, int((70 if i == 0 else 62) * scale), None, 0)

        first = True
        for line in _wrap(draw, point["heading"], f_head, max_w - 44, kw):
            add("head", line, f_head, lh_head, ACCENT, 44, first)
            first = False

        add("gap", "", None, int(14 * scale), None, 0)
        for line in _wrap(draw, point["text"], f_body, max_w - 44, kw):
            add("body", line, f_body, lh_body, (206, 212, 228), 44)

    return blocks, height


def _draw_hero(img, photo_path):
    """Top-of-card photo, cropped to fill, fading into the background."""
    try:
        photo = Image.open(photo_path).convert("RGB")
    except Exception as exc:
        print(f"  ! couldn't open photo: {exc}")
        return 0

    target_ratio = W / HERO_HEIGHT
    w, h = photo.size
    if w / h > target_ratio:                     # too wide — crop sides
        new_w = int(h * target_ratio)
        photo = photo.crop(((w - new_w) // 2, 0, (w - new_w) // 2 + new_w, h))
    else:                                        # too tall — crop bottom
        new_h = int(w / target_ratio)
        photo = photo.crop((0, 0, w, new_h))
    photo = photo.resize((W, HERO_HEIGHT), Image.LANCZOS)

    # darken overall so the accent bar and kicker stay readable on top
    overlay = Image.new("RGB", (W, HERO_HEIGHT), BG_TOP)
    photo = Image.blend(photo, overlay, 0.38)
    img.paste(photo, (0, 0))

    # fade the bottom third into the card background
    fade_h = 260
    fade = Image.new("L", (1, fade_h))
    for i in range(fade_h):
        fade.putpixel((0, i), int(255 * (i / fade_h) ** 1.4))
    mask = fade.resize((W, fade_h))
    img.paste(Image.new("RGB", (W, fade_h), BG_TOP),
              (0, HERO_HEIGHT - fade_h), mask)
    return HERO_HEIGHT


def render_topic(brief, out_path, photo_path=None, photo_credit=None):
    img = Image.new("RGB", (W, H), BG_TOP)
    draw = ImageDraw.Draw(img)

    for y in range(H):
        t = y / H
        draw.line([(0, y), (W, y)],
                  fill=tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)))

    hero = _draw_hero(img, photo_path) if photo_path else 0
    draw = ImageDraw.Draw(img)
    draw_brand_badge(img)
    if hero:
        # mark 2 applies to the hero like any photo — press graphics with
        # their own agency logos included, no special casing
        seal_photo(img, W, HERO_HEIGHT)

    margin = 80
    right = W - margin
    max_w = W - 2 * margin
    _, kw = ar("م")

    TOP = (hero - 40) if hero else 330
    # closing-seal height RESERVED before text sizing — see news_bot
    BOTTOM = H - 360
    available = BOTTOM - TOP

    # Shrink to fit. Only drop a point if even the smallest size overflows.
    points = list(brief.get("points", []))[:POINTS]
    scale, blocks = 1.0, None
    while blocks is None:
        trial = dict(brief, points=points)
        for candidate in (1.0, 0.96, 0.92, 0.88):
            trial_blocks, height = _build_layout(draw, trial, candidate, max_w, kw)
            if height <= available:
                scale, blocks = candidate, trial_blocks
                break
        if blocks is None:
            if len(points) > 2:
                points = points[:-1]
                print(f"  ! content too long — trimmed to {len(points)} points")
            else:
                print("  ! content overflows even at minimum size")
                scale, blocks = 0.88, trial_blocks
    if scale < 1.0:
        print(f"  layout scaled to {int(scale * 100)}% to fit")

    def rtl(xy, text, font, fill, anchor="ra"):
        shaped, k = ar(text)
        draw.text(xy, shaped, font=font, fill=fill, anchor=anchor, **k)

    kicker_y = 96 if hero else 200
    draw.rectangle([right - 110, kicker_y, right, kicker_y + 10], fill=ACCENT)
    rtl((right, kicker_y + 46), KICKER,
        load_font(int(32 * scale), bold=True), ACCENT)

    y = TOP
    lead_top = lead_bottom = None
    for block in blocks:
        if block["kind"] == "gap":
            y += block["lh"]
            continue
        if block["kind"] == "lead":
            if lead_top is None:
                lead_top = y - 6
            lead_bottom = y + block["lh"] - 14
        if block["kind"] == "head" and block["first"]:
            r = max(5, int(7 * scale))
            draw.ellipse([right - 18, y + int(16 * scale),
                          right - 18 + 2 * r, y + int(16 * scale) + 2 * r],
                         fill=ACCENT)
        rtl((right - block["indent"], y), block["text"], block["font"], block["fill"])
        y += block["lh"]

    if lead_top is not None:
        draw.rectangle([right - 6, lead_top, right, lead_bottom], fill=ACCENT)

    f_foot = load_font(28)
    closing_seal(img, H - 270)

    # drop sources until the line fits, rather than letting it run off the edge
    names = list(brief.get("sources", []))[:4]
    credit_w = draw.textlength(ar(f"الصورة: {photo_credit}")[0], font=f_foot, **kw) \
        if photo_credit else 0
    room = max_w - credit_w - 40
    while names:
        label = f"المصادر: {'، '.join(names)}"
        if draw.textlength(ar(label)[0], font=f_foot, **kw) <= room or len(names) == 1:
            break
        names.pop()
    label = f"المصادر: {'، '.join(names)}"
    while names and draw.textlength(ar(label)[0], font=f_foot, **kw) > room:
        names[0] = names[0][:-4] + "..."       # last resort: shorten the name
        label = f"المصادر: {'، '.join(names)}"
        if len(names[0]) <= 8:
            break

    rtl((right, H - 155), label, f_foot, MUTED)
    if photo_credit:
        rtl((margin, H - 155), f"الصورة: {photo_credit}", f_foot, MUTED,
            anchor="la")

    img.save(out_path, "PNG", optimize=True)
    return out_path


# --------------------------------------------------------------------------

def build_card(topic):
    """Research one topic and find it a photo.
    Returns (brief, photo, credit) — photo is None if nothing was found."""
    print(f"1/3 researching: {topic}")
    brief = research(topic)
    print(f"    {brief['title']}")
    warn_about_bare_numbers(brief)
    print(f"    body:     {brief.get('body', '')[:80]}...")
    print(f"    takeaway: {brief.get('takeaway', '')[:80]}")

    queries = brief.get("image_queries", [])
    queries_ar = brief.get("image_queries_ar", [])
    hero = OUT_DIR / "hero.jpg"
    Path(str(hero) + ".recentkeep").unlink(missing_ok=True)
    photo, credit = None, None

    print("2/3 finding a photo...")

    # "generate" forces the AI image, skipping the real sources — for testing
    if IMAGE_SOURCE == "generate":
        print("    forcing a generated image (IMAGE_SOURCE=generate)")
        photo, credit = fetch_generated_photo(brief.get("image_prompt", ""), hero)
        return brief, photo, credit

    photo, credit = fetch_local_photo(queries_ar, queries, hero)

    if photo is None and IMAGE_SOURCE in ("spa", "openverse"):
        photo, credit = fetch_spa_photo(queries_ar, hero)

    if photo is None and IMAGE_SOURCE == "article":
        photo, domain = fetch_article_photo(brief.get("source_url", ""), hero)
        if photo and not domain:
            domain = urllib.parse.urlparse(brief.get("source_url", "")).netloc \
                .replace("www.", "")
        credit = DOMAIN_CREDITS.get(domain, domain) if domain else None
    elif photo is None and IMAGE_SOURCE == "stock":
        photo = fetch_photo(queries, hero)
        credit = "Pexels" if photo else None
    elif photo is None and IMAGE_SOURCE == "openverse":
        photo, credit = fetch_openverse_photo(queries, hero)

    if photo is None and IMAGE_SOURCE != "none":
        if IMAGE_SOURCE != "openverse":
            photo, credit = fetch_openverse_photo(queries, hero)
        if photo is None and IMAGE_SOURCE != "article":
            print("    trying the article photo...")
            photo, domain = fetch_article_photo(brief.get("source_url", ""), hero)
            credit = DOMAIN_CREDITS.get(domain, domain) if domain else None
        if photo is None and PEXELS_API_KEY and IMAGE_SOURCE != "stock":
            print("    trying Pexels...")
            photo = fetch_photo(queries, hero)
            credit = "Pexels" if photo else None
        if photo is None:
            # a recent real photo beats generated filler — accept it loudly
            photo, credit = recent_fallback(hero), None
        if photo is None:
            photo, credit = fetch_generated_photo(brief.get("image_prompt", ""), hero)

    return brief, photo, credit


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    tried, brief, photo, credit, topic = [], None, None, None, None

    for attempt in range(1, TOPIC_ATTEMPTS + 1):
        topic = TOPIC or choose_topic(exclude=tried)
        if not topic:
            raise SystemExit(f"No topic given and none found in {TOPICS_FILE}")
        if attempt > 1:
            print(f"--- attempt {attempt} of {TOPIC_ATTEMPTS} ---")

        brief, photo, credit = build_card(topic)

        if photo is not None or not REQUIRE_PHOTO or IMAGE_SOURCE == "none":
            break

        tried.append(topic)
        if TOPIC or IMAGE_SOURCE == "generate":
            break                       # a forced topic or a generation test
        if attempt < TOPIC_ATTEMPTS:
            print(f"  ! no photo for {topic!r} — trying a different topic")

    if photo is None and REQUIRE_PHOTO and IMAGE_SOURCE != "none":
        print(f"  ! tried {len(tried)} topic(s) and found no photo — "
              "not publishing a bare card.")
        notify(f"⚠️ {ksa_stamp()} — no topic card: tried {len(tried)} "
               "topic(s) and none had a usable photo")
        return

    print("3/3 rendering card...")
    slug = re.sub(r"[^\w]+", "-", topic, flags=re.UNICODE)[:40].strip("-")
    stamp = ksa_stamp()
    brief.setdefault("punch", brief.get("takeaway", ""))
    renderer = render_story if THEME == "light" else render_topic
    card = renderer(brief, OUT_DIR / f"{stamp}-{slug}.png", photo, credit)

    if photo:
        # hybrid and dry runs register too (dry writes locally, no push):
        # the photo reached Telegram and is spent
        register_photos([photo], "topic")

    if DRY_RUN:
        print(f"    DRY_RUN — nothing published. Card at {Path(card).resolve()}")
        notify(f"[DRY RUN] would have posted: {brief['title']}\n"
               f"({stamp} — تجربة، البطاقة مرفقة)", card)
        return

    if not POST_ENABLED:
        print("    hybrid mode — publishing the card, not posting to Snapchat")
        url = publish_via_github(card)
        repo = os.getenv("GITHUB_REPOSITORY", "")
        branch = os.getenv("GITHUB_REF_NAME", "main")
        print(f"    today's card: {url}")
        if repo:
            print("    always-latest link: https://raw.githubusercontent.com/"
                  f"{repo}/{branch}/{CARDS_DIR}/latest.png")
        commit_and_push(save_used(load_used(), topic), f"topic: {slug}")
        notify(f"{recent_warning()}💡 {stamp}\n{brief['title']}\n\n"
               f"{brief.get('takeaway', '')}", card)
        return

    if not quota_ok():
        deliver_unposted(card, brief["title"])
        return

    print("    posting to Snapchat...")
    url = None
    if POST_PROVIDER != "bundle":
        url = publish_via_github(card) if MEDIA_MODE == "github" else upload_media(card)
        print(f"    media: {url}")
    response = post_story(brief.get("caption", topic), [url] if url else [], card)
    print("   ", response)

    if post_ok(response):
        commit_and_push(save_used(load_used(), topic), f"topic: {slug}")
        commit_and_push(quota_bump(), f"quota {stamp}")
        notify(f"✅ posted {stamp}\n{brief['title']}", card)
    else:
        notify(f"❌ {stamp} — Snapchat post failed\n"
               f"{describe_failure(response)}")


if __name__ == "__main__":
    main()
