#!/usr/bin/env python3
"""مراقب العاجل — يفحص الأخبار كل 30 دقيقة نهاراً.

    python breaking_watch.py            # دورة مراقبة

الدورة رخيصة: فحص الخلاصات أولاً (بلا نموذج) — إن لم يظهر جديد منذ آخر
دورة انتهت الدورة هنا. وإن ظهر، نموذج صغير يصنّف والعناوين أمامه — الأصل
الرفض، ومعظم الدورات تنتهي بسطر واحد ولا تلمس الحالة ولا تكلّف commit.
إن تأكد حدث عاجل، تُقفل الدورة القفل ثم تشغّل news_bot كاملاً والحدث
مثبّت (PINNED_EVENT): النموذج الكبير يعيد التحقق ويكتب بكل قواعد
البطاقة، وإن لم يتأكد الحدث يموت التشغيل هناك دون نشر.

لا بطاقة مسائية بديلة: لا بطاقة عاجلة إلا إذا اجتاز حدثٌ البوابات كلها —
ومعظم الأيام لا يُنشر مساءً شيء، وهذا هو المقصود. الصمت نتيجة لا عطل،
والمراقب يرسل سطراً في كل دورة على أي حال.
"""

import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

try:
    from news_bot import (
        ANTHROPIC_API_KEY, DRY_RUN, commit_and_push, ksa_stamp, notify,
    )
except ImportError as exc:
    raise SystemExit(f"news_bot.py is missing something breaking_watch "
                     f"needs ({exc}). The two files move together.")

STATE_FILE = Path("state/breaking.json")
MAX_BREAKING_PER_DAY = 1        # v1 cap — one breaking post a day, full stop
LOCK_MINUTES = 25               # under the 30-minute cadence, so a stuck
                                # lock never outlives the next cycle by much
# GitHub cron can start several minutes late. The last scheduled cycle is
# 22:30 KSA, but the script accepts delayed starts until (not including) 23:00.
WATCH_START_H, WATCH_END_H = 8.0, 23.0
# classification is a small-model job — budget it tightly
WATCH_MODEL = os.getenv("WATCH_MODEL", "").strip() or "claude-haiku-4-5-20251001"
WATCH_MAX_TOKENS = int(os.getenv("WATCH_MAX_TOKENS", "").strip() or "1200")
WATCH_MAX_SEARCHES = int(os.getenv("WATCH_MAX_SEARCHES", "").strip() or "2")

# Feed-diff pre-filter: RSS/network reads are cheap; model calls and web
# searches are not. Core Saudi feeds may fail open into classification, while
# broader regional/global feeds are optional tripwires whose outages never
# create paid work by themselves. Broad-source headlines are filtered with a
# deterministic Saudi/Gulf relevance gate before Claude sees them.
WATCH_FEED_DIFF = (os.getenv("WATCH_FEED_DIFF", "").strip() or "1") != "0"
_DEFAULT_WATCH_FEEDS = [
    {"name": "Saudi Google News",
     "url": "https://news.google.com/rss?hl=ar&gl=SA&ceid=SA:ar",
     "tier": "core"},
    {"name": "Saudi Business",
     "url": "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ar&gl=SA&ceid=SA:ar",
     "tier": "core"},
    {"name": "Saudi Technology",
     "url": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=ar&gl=SA&ceid=SA:ar",
     "tier": "core"},
    {"name": "Asharq Al-Awsat Economy",
     "url": "https://aawsat.com/feed/economy", "tier": "core"},
    {"name": "Al Arabiya",
     "url": "https://news.google.com/rss/search?q=site%3Aalarabiya.net&hl=ar&gl=SA&ceid=SA:ar",
     "tier": "regional"},
    {"name": "Al Jazeera",
     "url": "https://news.google.com/rss/search?q=site%3Aaljazeera.net&hl=ar&gl=SA&ceid=SA:ar",
     "tier": "regional"},
    {"name": "Asharq Business",
     "url": "https://news.google.com/rss/search?q=site%3Aasharq.com&hl=ar&gl=SA&ceid=SA:ar",
     "tier": "regional"},
    {"name": "Argaam",
     "url": "https://news.google.com/rss/search?q=site%3Aargaam.com&hl=ar&gl=SA&ceid=SA:ar",
     "tier": "regional"},
    {"name": "CNBC Arabia",
     "url": "https://news.google.com/rss/search?q=site%3Acnbcarabia.com&hl=ar&gl=SA&ceid=SA:ar",
     "tier": "regional"},
    {"name": "CNN",
     "url": "https://news.google.com/rss/search?q=site%3Acnn.com&hl=en&gl=US&ceid=US:en",
     "tier": "global"},
    {"name": "BBC",
     "url": "https://news.google.com/rss/search?q=site%3Abbc.com&hl=en&gl=US&ceid=US:en",
     "tier": "global"},
    {"name": "Reuters",
     "url": "https://news.google.com/rss/search?q=site%3Areuters.com&hl=en&gl=US&ceid=US:en",
     "tier": "global"},
    {"name": "AP",
     "url": "https://news.google.com/rss/search?q=site%3Aapnews.com&hl=en&gl=US&ceid=US:en",
     "tier": "global"},
]
_custom_feeds = os.getenv("WATCH_FEEDS", "").strip()
WATCH_FEEDS = ([{"name": u, "url": u, "tier": "core"}
                for u in _custom_feeds.split(",") if u.strip()]
               if _custom_feeds else _DEFAULT_WATCH_FEEDS)
# A wider stateless window makes the watcher resilient to delayed/missed
# hosted-runner starts without forcing a state commit every 30 minutes.
# The classifier still applies the stricter "hours, not days" breaking gate.
WATCH_FEED_WINDOW_MIN = int(
    os.getenv("WATCH_FEED_WINDOW_MIN", "").strip() or "180")
WATCH_MAX_FEED_TITLES = int(
    os.getenv("WATCH_MAX_FEED_TITLES", "").strip() or "12")
FEED_UA = "Mozilla/5.0 (compatible; daily-news-bot/1.0)"

_REGION_RELEVANCE_RE = re.compile(
    r"(?:السعود(?:ية|ي)|الرياض|جدة|مكة|المدينة|نيوم|أرامكو|"
    r"صندوق الاستثمارات|الإمارات|دبي|أبوظبي|قطر|الدوحة|الكويت|"
    r"البحرين|عمان|مسقط|الخليج|أوبك|البحر الأحمر|"
    r"\b(?:saudi(?: arabia)?|ksa|riyadh|jeddah|makkah|mecca|medina|"
    r"neom|aramco|pif|public investment fund|uae|united arab emirates|"
    r"dubai|abu dhabi|qatar|doha|kuwait|bahrain|oman|muscat|gcc|opec|"
    r"red sea|gulf (?:states?|airlines?|region|markets?))\b)",
    re.IGNORECASE,
)
BEATS = ("القرارات والتنظيمات والأخبار الوطنية السعودية، الاقتصاد السعودي، "
         "العقار السعودي والخليجي، السفر والسياحة السعودية، أخبار الأعمال "
         "والتقنية الكبرى")

WATCH_PROMPT = """أنت حارس بوابة «العاجل» لحساب أخبار أعمال سعودي على سناب شات.
مهمتك تصنيف لا كتابة: هل وقع خلال الساعات الأخيرة حدثٌ يستحق بطاقة
عاجلة الآن قبل موعد المساء؟ الأصل الرفض — معظم الدورات جوابها لا،
وبطاقة المساء تلتقط كل ما يحتمل الانتظار.

لا يمر الحدث إلا إذا اجتاز الشروط كلها:
- العاجل حدثٌ عمره ساعات لا أيام — خبر أمس ليس عاجلاً اليوم.
- مصدران مستقلان على الأقل يؤكدانه الآن.
- إن كان الخبر حكومياً أو تنظيمياً أو عن جهة رسمية: لا يمر إلا بمصدر
  رسمي (واس، تداول، الوزارة المعنية، بيان الشركة نفسها).
- وقع حدثٌ منفصل في لحظة معلومة: وُقّع، أُعلن، صدر، استقال، تعطّل،
  حُكم. أما «تجري مفاوضات»، «تدرس»، «تستكشف»، «يُتوقع»، «تتلقى
  عروضاً» فليست حدثاً — والاختبار: إن بقيت الجملة صحيحةً الأسبوع
  القادم كما هي فليست عاجلة.
- للقارئ السعودي مصلحة مباشرة في الخبر: إن كان سطر «وش يعنيني» يصف
  أثر الخبر على ناسٍ في مكان آخر (مطوّرين حول العالم، أسواق أمريكا)
  فلا مصلحة له — وجّهه لبطاقة عادية مجدولة، لا عاجلة.
- يجتاز الاختبارات الثلاثة بوضوح — الأهمية والقرب والتوقف — وأشدها
  التوقف: الحدث الذي «يمكن أن ينتظر الغد» ليس عاجلاً.
✗ «الأسواق تترقب قرار الفائدة» (ترقّب، لا حدث)
✗ «تقرير: نمو القطاع العقاري 12% هذا العام» (تقرير دوري، ينتظر)
✗ «مصدر واحد: استقالة وشيكة» (لا تأكيد)
✗ «Hugging Face تتلقى عروض استحواذ بـ13 مليار» — مفاوضات جارية لا
  حدث، وجمهورها مطوّرون لا قرّاؤنا؛ تصلح بطاقة تقنية مجدولة لا عاجلة.

الزيارات الرسمية وزيارات الدولة: الزيارة وعاءٌ لا حدث. لا تنشر
«الزيارة» عاجلاً — انشر اللحظة المنفصلة داخلها:
- وصولٌ أو بدء زيارة رسمية → عاجل
- اتفاقية أو مذكرة تفاهم وُقّعت (برقمها) → عاجل
- بيان مشترك أو قرار مُعلن → عاجل
- «الزيارة مستمرة»، تغطية اليوم الثاني → ليست عاجلة
وبطاقة واحدة لكل تطورٍ منفصل: لا بطاقتين للحظة نفسها مهما تعددت
المقالات عنها.
والأخبار الرسمية السعودية عالية الأولوية — مصلحة القارئ فيها تلقائية،
ويبقى شرط المصدر الرسمي واختبار شكل الحدث كما هما.
✓ «وصول ولي العهد إلى واشنطن في زيارة دولة — واس والوكالات»
✗ «اليوم الثاني من الزيارة: جولات ولقاءات» (وعاء مستمر، لا لحظة)
✓ «تداول تعلق تداول سهم X — بيان رسمي منذ ساعة، وكالتان»
✓ «إعلان حكومي الآن يغيّر رسوم Y ابتداء من الغد — واس»

عند الشك: ليست عاجلة. خبر عاجل فائت يكلّف منشوراً متأخراً واحداً؛
وخبر عاجل زائف يكلّف معنى الصيغة كلها — إذا اشتعل الرأس الأحمر على
خبر عادي كفّ عن أن يشير إلى شيء.

أجب بـJSON فقط، بلا أي نص قبله أو بعده:
{"breaking": true/false,
 "event": "وصف الحدث في جملة واحدة، بالجهة والوقت",
 "sources": ["المصدر ١", "المصدر ٢"],
 "official_source": true/false,
 "reason": "لماذا مرّ أو لماذا رُفض"}"""


def ksa_now():
    return datetime.now(timezone.utc) + timedelta(hours=3)


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    # shared-file discipline: same rebase-and-retry push as quota.json.
    # A DRY_RUN keeps its state local so tests never race the live bots.
    if not DRY_RUN:
        commit_and_push(STATE_FILE, f"breaking state {ksa_stamp()}")


def event_fp(event):
    """Coarse same-day fingerprint so one event can't post twice in
    different words. Word-set hash: order and punctuation don't matter."""
    words = sorted(set(w for w in event.split() if len(w) > 2))
    return hashlib.md5(" ".join(words).encode()).hexdigest()[:16]


def _feed_entry_time(item):
    """The item's own timestamp, or None when it doesn't carry a usable
    one. RSS pubDate is RFC822; Atom updated/published is ISO."""
    for tag in ("pubDate", "updated", "published",
                "{http://www.w3.org/2005/Atom}updated",
                "{http://www.w3.org/2005/Atom}published"):
        el = item.find(tag)
        if el is None or not (el.text or "").strip():
            continue
        raw = el.text.strip()
        try:
            dt = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return None


def _feed_title(item):
    """Return RSS or Atom title without relying on Element truthiness.

    ElementTree elements with no child nodes currently evaluate false, so
    `rss_title or atom_title` drops a perfectly valid RSS <title>. Test
    explicitly for None instead.
    """
    el = item.find("title")
    if el is None:
        el = item.find("{http://www.w3.org/2005/Atom}title")
    return (el.text or "").strip() if el is not None else ""


def _feed_spec(raw):
    if isinstance(raw, str):
        return {"name": raw, "url": raw, "tier": "core"}
    return {
        "name": str(raw.get("name") or raw.get("url") or "feed"),
        "url": str(raw.get("url") or ""),
        "tier": str(raw.get("tier") or "core").lower(),
    }


def _headline_relevant(title, tier):
    return tier == "core" or bool(_REGION_RELEVANCE_RE.search(title))


def _headline_key(title):
    # Google News commonly appends " - Publisher"; strip that so the same
    # syndicated headline from two source feeds costs one classifier slot.
    base = re.sub(r"\s+-\s+[^-]{2,60}$", "", title.strip())
    return " ".join(re.sub(r"[^\w]+", " ", base.casefold()).split())


def _round_robin_titles(buckets, limit):
    selected, seen = [], set()
    queues = [list(bucket) for bucket in buckets]
    while len(selected) < limit:
        progressed = False
        for queue in queues:
            while queue:
                title = queue.pop(0)
                key = _headline_key(title)
                if not key or key in seen:
                    continue
                seen.add(key)
                selected.append(title)
                progressed = True
                break
            if len(selected) >= limit:
                break
        if not progressed:
            break
    return selected


def feed_fresh_items():
    """Return a small, source-diverse set of fresh trigger headlines.

    Core Saudi feeds protect visibility and may fail open into classification.
    Regional/global feeds widen coverage but are optional: their failures are
    logged and never create a paid model call by themselves. Broad-source
    headlines must pass a deterministic Saudi/Gulf relevance filter first.
    """
    cutoff = (datetime.now(timezone.utc)
              - timedelta(minutes=WATCH_FEED_WINDOW_MIN))
    buckets = []
    reachable = 0
    core_seen = 0
    core_healthy = True

    for raw in WATCH_FEEDS:
        spec = _feed_spec(raw)
        name, url, tier = spec["name"], spec["url"], spec["tier"]
        if tier == "core":
            core_seen += 1
        try:
            req = urllib.request.Request(url, headers={"User-Agent": FEED_UA})
            with urllib.request.urlopen(req, timeout=20) as resp:
                root = ET.fromstring(resp.read())
        except Exception as exc:
            if tier == "core":
                core_healthy = False
                print(f"  ! CORE feed unreachable ({exc}): {name}")
            else:
                print(f"  ! optional feed unreachable ({exc}): {name}")
            continue

        reachable += 1
        items = (root.findall(".//item")
                 or root.findall(".//{http://www.w3.org/2005/Atom}entry"))
        titled = 0
        raw_fresh = 0
        accepted = []
        for item in items:
            title = _feed_title(item)
            if not title:
                continue
            titled += 1
            when = _feed_entry_time(item)
            if when is not None and when < cutoff:
                continue
            raw_fresh += 1
            if _headline_relevant(title, tier):
                accepted.append(title)

        print(f"  feed scan [{tier}] {name}: entries={len(items)} "
              f"titles={titled} fresh={raw_fresh} accepted={len(accepted)}")
        if not items or titled == 0:
            if tier == "core":
                core_healthy = False
                print("  ! core feed parsed without usable titled entries — "
                      "pre-filter will fail open")
            else:
                print("  ! optional feed parsed without usable titled entries")
        buckets.append(accepted)

    fresh = _round_robin_titles(buckets, WATCH_MAX_FEED_TITLES)
    if len(fresh) >= WATCH_MAX_FEED_TITLES:
        print(f"  feed shortlist capped at {WATCH_MAX_FEED_TITLES} titles")
    if core_seen:
        feeds_healthy = core_healthy
    else:
        # Unit/custom configurations with no declared core feed still work,
        # but production defaults always contain four core Saudi feeds.
        feeds_healthy = bool(reachable)
    return fresh, feeds_healthy


def _classifier_search_budget(fresh_titles):
    # A known RSS candidate needs verification, not rediscovery. Keep the
    # second search only for fail-open cycles where the feed layer is blind.
    return min(1, WATCH_MAX_SEARCHES) if fresh_titles else WATCH_MAX_SEARCHES

def classify(now, fresh_titles=None):
    """One small-model call with tightly budgeted search. None on error —
    and None is treated as 'not breaking': a broken classifier must fail
    quiet, never fail posting."""
    if not ANTHROPIC_API_KEY:
        print("  ! no ANTHROPIC_API_KEY — cannot classify, exiting quiet")
        return None
    known_candidate = bool(fresh_titles)
    search_budget = _classifier_search_budget(fresh_titles)
    search_wording = ("ابحث بحثاً واحداً موجهاً للتحقق من المرشح"
                      if known_candidate else
                      "ابحث بحثاً أو بحثين موجهين لليوم")
    user = (f"الآن {now:%Y-%m-%d %H:%M} بتوقيت السعودية. امسح أخبار "
            f"الساعات الأخيرة في هذه الملفات: {BEATS}. "
            f"{search_wording}، ثم أصدر الحكم.")
    if fresh_titles:
        listing = "\n".join(
            f"- {t}" for t in fresh_titles[:WATCH_MAX_FEED_TITLES])
        user += ("\n\nعناوين ظهرت في الخلاصات منذ الدورة الماضية — "
                 "قيّمها أولاً، وابحث للتحقق لا للاكتشاف:\n" + listing)
    print(f"  classifier budget: 1 call, max web searches={search_budget}, "
          f"feed_titles={len(fresh_titles or [])}")
    payload = {
        "model": WATCH_MODEL,
        "max_tokens": WATCH_MAX_TOKENS,
        "system": WATCH_PROMPT,
        "messages": [{"role": "user", "content": user}],
        "tools": [{"type": "web_search_20250305", "name": "web_search",
                   "max_uses": search_budget}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json",
                 "x-api-key": ANTHROPIC_API_KEY,
                 "anthropic-version": "2023-06-01"})
    # a 529 at the wrong minute used to become a silent "not breaking"
    # for the whole cycle — transient failures get three attempts before
    # the quiet verdict (the 🔴 line still reports a final failure)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
            usage = data.get("usage") or {}
            if usage:
                print("  classifier usage:",
                      json.dumps(usage, ensure_ascii=False, sort_keys=True))
            text = "".join(b.get("text", "") for b in data.get("content", [])
                           if b.get("type") == "text").strip()
            start, end = text.find("{"), text.rfind("}")
            return json.loads(text[start:end + 1])
        except Exception as exc:
            if attempt < 2:
                wait = (15, 45)[attempt] + random.uniform(0, 10)
                print(f"  ! classifier attempt {attempt + 1} failed "
                      f"({exc}) — retrying in {wait:.0f}s")
                time.sleep(wait)
                continue
            print(f"  ! classifier failed ({exc}) — treating as not breaking")
            return None


def _run_news_bot(extra_env):
    env = os.environ.copy()
    env.update(extra_env)
    return subprocess.call([sys.executable, "news_bot.py"], env=env)


def watch():
    # Every run reports — a working watcher and a dead one must never
    # produce the same observable output (nothing). One Telegram line per
    # cycle, whatever happened; errors are sent, not swallowed.
    try:
        _watch()
    except SystemExit:
        raise
    except Exception as exc:
        notify(f"🔴 {ksa_stamp()} — مراقب العاجل تعطّل: {exc}")
        raise


def _watch():
    now = ksa_now()
    hour = now.hour + now.minute / 60
    # The cron schedules through 22:30 KSA, but hosted runners can start
    # late. Accept a delayed final cycle until 23:00, then stay safely off.
    if not WATCH_START_H <= hour < WATCH_END_H:
        print(f"outside the watch window ({now:%H:%M} KSA) — exiting")
        notify(f"⚪️ {ksa_stamp()} — مراقب العاجل: خارج نافذة المراقبة "
               f"({now:%H:%M} بتوقيت السعودية؛ الجدول 08:00–22:30 "
               "مع مهلة تأخير حتى 23:00). لم يُفحص شيء — "
               "لا توجد دورة مسائية بديلة.")
        return

    state = load_state()
    today = now.date().isoformat()
    if state.get("date") == today:
        if state.get("posted") and \
                len(state.get("stamps", [])) >= MAX_BREAKING_PER_DAY:
            print("today's breaking post already went out — quiet cycle")
            notify(f"⚪️ {ksa_stamp()} — مراقب العاجل: بطاقة اليوم العاجلة "
                   "نُشرت — دورة هادئة")
            return
        lock = state.get("lock_at", "")
        if lock:
            try:
                held = (now - datetime.fromisoformat(lock)).total_seconds()
            except ValueError:
                held = 0
            if held < LOCK_MINUTES * 60:
                print("another live cycle holds the lock — quiet cycle")
                notify(f"⚪️ {ksa_stamp()} — مراقب العاجل: دورة أخرى تعمل "
                       "الآن (قفل) — خرجت")
                return

    fresh_titles = None
    if WATCH_FEED_DIFF:
        fresh_titles, feeds_ok = feed_fresh_items()
        if not feeds_ok:
            # Any incomplete/broken pre-filter fails OPEN into the model.
            # A partial feed outage must not suppress a real breaking event.
            print("  ! feed pre-filter unhealthy/incomplete — "
                  "classifying anyway")
            fresh_titles = None
        elif not fresh_titles:
            print("no new feed items this cycle — classifier not called")
            notify(f"⚪️ {ksa_stamp()} — مراقب العاجل: لا جديد في "
                   f"الخلاصات ضمن نافذة {WATCH_FEED_WINDOW_MIN} دقيقة — "
                   "لم يُستدعَ المصنّف")
            return
        else:
            print(f"  {len(fresh_titles)} fresh feed item(s) — classifying")

    verdict = classify(now, fresh_titles)
    if verdict:
        print("verdict:", json.dumps(verdict, ensure_ascii=False))
    if not verdict:
        print("no breaking news this cycle (classifier unavailable)")
        notify(f"🔴 {ksa_stamp()} — مراقب العاجل: تعذّر التصنيف هذه الدورة "
               "(خطأ في الاستدعاء) — عومل كلا عاجل")
        return
    if not verdict.get("breaking"):
        print("no breaking news this cycle")
        n_src = len(verdict.get("sources") or [])
        reason = (verdict.get("reason") or "").strip()[:120]
        notify(f"⚪️ {ksa_stamp()} — مراقب العاجل: لا عاجل — "
               f"{reason or 'لا حدث يجتاز الشروط'}"
               + (f" (مصادر مفحوصة: {n_src})" if n_src else ""))
        return
    # the prompt gates on these too, but a gate the code doesn't hold is a
    # gate a malformed reply walks through
    if len(verdict.get("sources") or []) < 2:
        print("  ! breaking=true with fewer than two sources — refused")
        notify(f"⚪️ {ksa_stamp()} — مراقب العاجل: مرشح واحد رُفض "
               "(أقل من مصدرين) — لا نشر")
        return
    event = (verdict.get("event") or "").strip()
    if not event:
        print("  ! breaking=true with an empty event — refused")
        notify(f"⚪️ {ksa_stamp()} — مراقب العاجل: حكم مشوّه رُفض — لا نشر")
        return
    fp = event_fp(event)
    if state.get("date") == today and state.get("event_fp") == fp:
        print("same event already handled today — quiet cycle")
        notify(f"⚪️ {ksa_stamp()} — مراقب العاجل: الحدث نفسه سبق فحصه "
               f"اليوم — لا تكرار\n{event[:100]}")
        return

    # acquire the cycle lock BEFORE the expensive pipeline
    state = {"date": today, "posted": False, "event_fp": fp,
             "lock_at": now.isoformat(),
             "stamps": state.get("stamps", []) if state.get("date") == today
             else []}
    save_state(state)

    print(f"BREAKING — pinning the event and running the full pipeline:\n"
          f"    {event}")
    rc = _run_news_bot({"PINNED_EVENT": event, "POST_TO_SNAPCHAT": "1"})

    state = load_state()
    if rc == 0:
        if DRY_RUN:
            # the pipeline already sent the [DRY RUN] card message; the
            # watcher must not claim a publish that never happened, nor
            # burn the daily cap on a rehearsal
            state["lock_at"] = ""
            save_state(state)
            print("dry run: card built and reported — nothing posted, "
                  "cap untouched")
            return
        state.update(posted=True, lock_at="",
                     stamps=state.get("stamps", []) + [ksa_stamp()])
        save_state(state)
        notify(f"🚨 بطاقة عاجلة نُشرت تلقائياً\n{event[:150]}")
    else:
        # keep the fingerprint: an event the big model could not confirm
        # must not be retried every half hour. A later genuinely new event
        # can still be evaluated by the watcher.
        state["lock_at"] = ""
        save_state(state)
        print("pinned pipeline aborted — lock released, fingerprint kept")
        # the one exit that said nothing: in a dry run the pipeline's own
        # card message never comes (nothing was built), so this line is
        # the cycle's only report
        notify(f"⚪️ {ksa_stamp()} — مراقب العاجل: الحدث المثبّت لم يجتز "
               f"التحقق الكامل — أُلغي دون نشر\n{event[:100]}")


def main():
    role = (sys.argv[1] if len(sys.argv) > 1 else "watch").strip().lower()
    if role == "watch":
        watch()
    else:
        raise SystemExit(f"unknown role {role!r} — only 'watch' exists")


if __name__ == "__main__":
    main()