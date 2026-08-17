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
        DOMAIN_CREDITS, fetch_article_photo, fetch_openverse_photo, fetch_photo,
        fetch_spa_photo, fetch_local_photo, fetch_generated_photo,
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
    """Topics from topics.txt, ignoring blanks and # comments."""
    if not TOPICS_FILE.exists():
        here = sorted(p.name for p in Path(".").iterdir() if p.is_file())
        print(f"  ! {TOPICS_FILE} not found. Files here: {', '.join(here)}")
        return []
    lines = TOPICS_FILE.read_text(encoding="utf-8").splitlines()
    topics = [ln.strip() for ln in lines
              if ln.strip() and not ln.strip().startswith("#")]
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


def active_seasons(today=None):
    """Seasons whose window contains today, soonest peak first."""
    today = today or date.today()
    live = []
    for season in load_seasons():
        window = _season_window(season, today)
        if not window:
            if season["spec"].startswith("hijri") and not HIJRI_OK:
                print(f"  ! {season['name']}: hijri dates need the "
                      "hijri-converter package")
            continue
        start, end = window
        if start <= today <= end:
            live.append((abs((start - today).days), season))
    live.sort(key=lambda s: s[0])
    return [s for _, s in live]


USED_FILE = Path("state/topics_used.json")
COOLDOWN_DAYS = int(os.getenv("COOLDOWN_DAYS", "21"))
HARD_COOLDOWN_DAYS = int(os.getenv("HARD_COOLDOWN_DAYS", "5"))
SELECT_MODEL = os.getenv("SELECT_MODEL", "claude-sonnet-5")
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

أجب بصيغة JSON فقط: {"index": رقم الموضوع, "why": "سبب الاختيار في جملة قصيرة"}"""


def choose_topic():
    """Pick the topic that best fits yesterday's news."""
    topics = load_topics()
    if not topics:
        return ""

    used = load_used()
    hard_cutoff = (datetime.now() - timedelta(days=HARD_COOLDOWN_DAYS)).isoformat()
    blocked = {e["topic"] for e in used if e.get("at", "") >= hard_cutoff}
    recent = {e["topic"] for e in used} - blocked

    # a running season takes precedence — its topics are only useful now
    season_pool = []

    if FORCE_SEASON:
        want = FORCE_SEASON.lower()
        matches = [s for s in load_seasons()
                   if want in s["name"].lower() or s["name"].lower() in want]
        if matches:
            for season in matches:
                print(f"    forced season: {season['name']} "
                      f"({len(season['topics'])} topics)")
                season_pool.extend(season["topics"])
        else:
            print(f"  ! no season matching {FORCE_SEASON!r}. Available:")
            for s in load_seasons():
                print(f"      - {s['name']}")

    if SEASON_PRIORITY and not season_pool:
        live = active_seasons()
        if len(live) > 3:
            # too many overlapping windows dilutes the pool — keep the nearest
            live = live[:3]
        for season in live:
            fresh = [t for t in season["topics"] if t not in blocked]
            if fresh:
                print(f"    season: {season['name']} ({len(fresh)} topics available)")
                season_pool.extend(fresh)
        if live and not season_pool:
            print("    season topics all used recently — falling back to the "
                  "general list")

    if season_pool:
        topics = season_pool
        available = list(enumerate(topics))
    else:
        available = [(i, t) for i, t in enumerate(topics) if t not in blocked]
        if not available:
            available = list(enumerate(topics))

    print(f"    {len(available)} topics available "
          f"({len(blocked)} on cooldown, {len(recent)} recently used)")
    print("    reading yesterday's headlines to pick a topic...")
    try:
        items = fetch_headlines()
    except Exception as exc:
        print(f"  ! couldn't fetch headlines ({exc}) — falling back to rotation")
        items = []

    if not items or not ANTHROPIC_API_KEY:
        index, topic = available[datetime.now().toordinal() % len(available)]
        print(f"    fallback rotation -> {topic}")
        return topic

    listing = "\n".join(f"{i}. {t}" for i, t in available)
    headlines = "\n".join(f"- {i['title']}" for i in items[:50])
    recent_list = "\n".join(f"- {t}" for t in recent) or "لا يوجد"

    payload = {
        "model": SELECT_MODEL,
        "max_tokens": 500,
        "system": SELECT_PROMPT,
        "messages": [{"role": "user", "content":
                      f"المواضيع المتاحة:\n{listing}\n\n"
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
        start, end = text.find("{"), text.rfind("}")
        choice = json.loads(text[start:end + 1])
        topic = topics[int(choice["index"])]
        print(f"    chose: {topic}")
        print(f"    why:   {choice.get('why', '')}")
        return topic
    except Exception as exc:
        print(f"  ! topic selection failed ({exc}) — falling back to rotation")
        index, topic = available[datetime.now().toordinal() % len(available)]
        print(f"    fallback rotation -> {topic}")
        return topic
TOPIC_MODEL = os.getenv("TOPIC_MODEL", "claude-opus-5")
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

الشكل المطلوب:
- title: عنوان لا يتجاوز ٤٥ حرفاً. يقول ما حدث، لا اسم الموضوع فقط. يجوز أن \
يتضمن رقماً محورياً مع وحدته.
- lead: جملة واحدة، لا تتجاوز ١٢٠ حرفاً. اجعلها الجملة التي تجعل القارئ \
يكمل: أهم ما في الموضوع، بصياغة تمسّه هو.
- points: {n} نقاط. كل نقطة:
  - heading: ٣ إلى ٥ كلمات تقول فكرة، لا عنواناً محايداً.
    ✗ "تراجع بعد ذروة الصيف"   ✓ "الهدوء الصيفي لم يدم"
  - text: جملتان قصيرتان، حتى ١٧٠ حرفاً — الإيجاز مطلوب. الجملة الأولى تقول ماذا حدث، \
والثانية تقول لماذا يهم أو ما الذي يترتب عليه.
- caption: نص المنشور المرافق، لا يتجاوز ١٢٠ حرفاً
- image_queries: ثلاث عبارات إنجليزية للبحث عن صورة، مرتبة من الأدق إلى الأعم.
  كل عبارة من كلمتين إلى أربع، وتصف شيئاً ملموساً يمكن تصويره — لا فكرة مجردة.
  ✗ "economic growth" أو "market analysis" (لا يمكن تصويرها)
  ✓ ["ripe dates closeup", "date palm harvest", "date fruit market"]
  الأولى تصف جوهر الموضوع نفسه، والثانية أوسع، والثالثة أعم ما يمكن.
  لا تذكر أشخاصاً بأعينهم ولا شعارات ولا علامات تجارية.
- image_queries_ar: ثلاث كلمات مفتاحية عربية مفردة للبحث في أرشيف الصور
  السعودي — كلمة واحدة لكل عنصر، لا عبارات. ✓ ["الرياض", "كهرباء", "صيف"]
- image_prompt: وصف إنجليزي من جملة واحدة لصورة توضيحية تُولّد آلياً إن لم
  تتوفر صورة حقيقية. صف مشهداً سعودياً ملموساً بلا أشخاص ولا شعارات ولا نصوص.
  ✓ "a modern Saudi apartment living room with a wall air conditioner unit"
  اطلب مشاهد محايدة يمكن تصويرها: مبانٍ، مكاتب، طرق، مدن، وثائق، أجهزة،
  مطارات، أسواق، طبيعة، لوحات إرشادية.
  ممنوع منعاً باتاً طلب صور: أشخاص بوجوه واضحة، جنود، أسلحة، شرطة، جيوش،
  احتجاجات، حوادث، إصابات، سجون، أو أي مشهد عنف أو نزاع — حتى لو كان الخبر
  عن أمن أو مخالفات أو قرارات عقابية. في هذه الحالات اطلب مشهداً محايداً
  تماماً مثل "government building exterior" أو "airport terminal hall".
- sources: أسماء المصادر (٢ إلى ٤). إن كان المصدر أجنبياً فاكتبه بالعربية.
- source_url: رابط الخبر الرسمي الأدق الذي اعتمدت عليه (يفضَّل مصدر حكومي سعودي \
مثل واس أو موقع الجهة المعنية). ضع الرابط كاملاً كما ظهر في البحث.

قواعد الأسلوب — قريبة من الناس، لا رسمية:
- ابدأ بما يهم القارئ شخصياً، لا بالجهة التي أصدرت الخبر.
  ✗ "أعلنت الهيئة العامة للعقار تعديلاً على..."  ✓ "إيجارك قد يتغير السنة الجاية، وهذا السبب"
- خاطب القارئ مباشرة حين يناسب: "إذا كنت تفكر في شراء سيارة الآن..."
- جمل قصيرة. تجنّب التراكيب الطويلة والمبني للمجهول.
- استخدم كلمات الحياة اليومية بدل المصطلح المؤسسي: "تكلفة" لا "الكلفة التشغيلية".
- إن وُجدت أمثلة نبرة في نهاية هذه التعليمات فهي المرجع الأول للمستوى اللغوي.
  وإن لم توجد، فاكتب بفصحى مبسّطة قريبة من كلام الناس في السعودية.
- يجوز أن يكون العنوان سؤالاً أو مفارقة تجذب الانتباه — بشرط أن يكون صادقاً ولا يبالغ.
- ممنوع الحشو: "تجدر الإشارة"، "في هذا السياق"، "من الجدير بالذكر"، "وفي الختام".
- ممنوع الصفات الترويجية: هائل، مذهل، ضخم، تاريخي، غير مسبوق، ثورة.
- استخدم أفعالاً محايدة: تتغير، ترتفع، تنخفض، تزيد. وتجنّب الأفعال المبالِغة مثل: تقفز، تنهار، تشتعل، تتهاوى، تنفجر.
- لا تبدأ أكثر من نقطة واحدة برقم. الأرقام تدعم الفكرة ولا تحل محلها.
- كل نقطة تضيف زاوية جديدة، والأخيرة تجيب: ماذا يعني هذا لي؟
- انسب كل رقم لمصدره بعبارة قصيرة: "وفق أرقام وزارة..."، "بحسب تقرير...".
- اكتب كل الأرقام بالأرقام اللاتينية (2027, 306, 13) لا بالأرقام العربية الهندية.
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

قواعد الدقة:
- اعتمد فقط على ما وجدته في البحث. لا تستخرج أرقاماً من ذاكرتك.
- إذا تضاربت المعلومات، قل ذلك واذكر التقديرين.
- إذا لم تجد ما يكفي، اجعل title هو "لا توجد معلومات كافية" واشرح السبب.

قبل أن تجيب، اقرأه كأنك رأيته في سناب شات: هل توقفت عنده أم مررت؟ هل يبدو \
كلاماً بشرياً أم بياناً رسمياً؟ وهل كل رقم منسوب لمصدره وله وحدة وتاريخ؟ \
إن كان أحد الجوابين لا، أعد الكتابة.

أجب بصيغة JSON فقط، بدون markdown وبدون مقدمة:
{{"title": "...", "lead": "...", "points": [{{"heading": "...", "text": "..."}}], \
"caption": "...", "image_queries": ["...", "...", "..."], \
"image_queries_ar": ["...", "..."], "image_prompt": "...", "source_url": "...", "sources": ["...", "..."]}}"""


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
    for point in brief.get("points", []):
        text = point.get("text", "")
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
                  f"{point.get('heading')!r} — followed by {next_word!r}, "
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
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"Claude API {exc.code}: {exc.read().decode()[:500]}")

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

    margin = 80
    right = W - margin
    max_w = W - 2 * margin
    _, kw = ar("م")

    TOP = (hero - 40) if hero else 330
    BOTTOM = H - 250
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
    draw.line([(margin, H - 200), (right, H - 200)], fill=(58, 66, 90), width=2)

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

def main():
    topic = TOPIC or choose_topic()
    if not topic:
        raise SystemExit(f"No topic given and none found in {TOPICS_FILE}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"1/3 researching: {topic}")
    brief = research(topic)
    print(f"    {brief['title']}")
    warn_about_bare_numbers(brief)
    for p in brief["points"]:
        print(f"    • {p['heading']}")

    print("2/3 rendering card...")
    slug = re.sub(r"[^\w]+", "-", topic, flags=re.UNICODE)[:40].strip("-")
    stamp = datetime.now().strftime("%Y-%m-%d")
    queries = brief.get("image_queries", [])
    hero = OUT_DIR / "hero.jpg"
    photo, credit = None, None

    queries_ar = brief.get("image_queries_ar", [])
    photo, credit = None, None

    # "generate" forces the AI image, skipping the real sources — for testing
    if IMAGE_SOURCE == "generate":
        print("    forcing a generated image (IMAGE_SOURCE=generate)")
        photo, credit = fetch_generated_photo(brief.get("image_prompt", ""), hero)
        if photo is None:
            print("    generation failed — falling back to the normal sources")

    if photo is None:
        photo, credit = fetch_local_photo(queries_ar, queries, hero)

    if photo is None and IMAGE_SOURCE in ("spa", "openverse"):
        photo, credit = fetch_spa_photo(queries_ar, hero)

    if photo is not None:
        pass
    elif IMAGE_SOURCE == "article":
        photo, domain = fetch_article_photo(brief.get("source_url", ""), hero)
        if domain:
            credit = DOMAIN_CREDITS.get(domain, domain)
    elif IMAGE_SOURCE == "stock":
        photo = fetch_photo(queries, hero)
        credit = "Pexels" if photo else None
    elif IMAGE_SOURCE == "openverse":
        photo, credit = fetch_openverse_photo(queries, hero)

    # cascade through the remaining sources rather than giving up
    if photo is None and IMAGE_SOURCE != "none":
        if IMAGE_SOURCE != "openverse":
            photo, credit = fetch_openverse_photo(queries, hero)
        if photo is None and IMAGE_SOURCE != "article":
            print("    falling back to the article photo...")
            photo, domain = fetch_article_photo(brief.get("source_url", ""), hero)
            credit = DOMAIN_CREDITS.get(domain, domain) if domain else None
        if photo is None and PEXELS_API_KEY and IMAGE_SOURCE != "stock":
            print("    falling back to Pexels...")
            photo = fetch_photo(queries, hero)
            credit = "Pexels" if photo else None
        if photo is None:
            photo, credit = fetch_generated_photo(brief.get("image_prompt", ""), hero)
        if photo is None:
            print("  ! no photo from any source — card will be text only")

    renderer = render_story if THEME == "light" else render_topic
    card = renderer(brief, OUT_DIR / f"{stamp}-{slug}.png", photo, credit)

    if DRY_RUN:
        print(f"3/3 DRY_RUN — nothing posted. Card at {Path(card).resolve()}")
        return

    if not POST_ENABLED:
        print("3/3 hybrid mode — publishing the card, not posting to Snapchat")
        url = publish_via_github(card)
        repo = os.getenv("GITHUB_REPOSITORY", "")
        branch = os.getenv("GITHUB_REF_NAME", "main")
        print(f"    today's card: {url}")
        if repo:
            print("    always-latest link: https://raw.githubusercontent.com/"
                  f"{repo}/{branch}/{CARDS_DIR}/latest.png")
        commit_and_push(save_used(load_used(), topic), f"topic: {slug}")
        return

    if not quota_ok():
        return

    print("3/3 posting to Snapchat...")
    url = publish_via_github(card) if MEDIA_MODE == "github" else upload_media(card)
    print(f"    media: {url}")
    response = post_story(brief.get("caption", topic), [url])
    print("   ", response)

    if str(response.get("status", "")).lower() != "error":
        used_file = save_used(load_used(), topic)
        commit_and_push(used_file, f"topic: {slug}")
        commit_and_push(quota_bump(), f"quota {stamp}")


if __name__ == "__main__":
    main()
