from pathlib import Path

path = Path("breaking_watch.py")
text = path.read_text(encoding="utf-8")

old_import = "import random\nimport subprocess\n"
new_import = "import random\nimport re\nimport subprocess\n"
assert old_import in text
text = text.replace(old_import, new_import, 1)

new_config = r'''# Feed-diff pre-filter: RSS/network reads are cheap; model calls and web
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
)'''
config_start = text.index("# Feed-diff pre-filter:")
config_end = text.index("\nBEATS =", config_start)
text = text[:config_start] + new_config + text[config_end:]

new_feed = r'''def _feed_spec(raw):
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
'''
feed_start = text.index("def feed_fresh_items():")
feed_end = text.index("\ndef classify(", feed_start)
text = text[:feed_start] + new_feed + text[feed_end:]

new_classify = r'''    known_candidate = bool(fresh_titles)
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
'''
classify_start = text.index("def classify(")
user_start = text.index('    user = (f"الآن', classify_start)
req_start = text.index("    req = urllib.request.Request(", user_start)
text = text[:user_start] + new_classify + text[req_start:]

old_response = '''            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
            text = "".join(b.get("text", "") for b in data.get("content", [])
'''
new_response = '''            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
            usage = data.get("usage") or {}
            if usage:
                print("  classifier usage:",
                      json.dumps(usage, ensure_ascii=False, sort_keys=True))
            text = "".join(b.get("text", "") for b in data.get("content", [])
'''
assert old_response in text
text = text.replace(old_response, new_response, 1)

path.write_text(text, encoding="utf-8")
