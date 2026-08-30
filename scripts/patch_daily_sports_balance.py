from pathlib import Path

path = Path("daily_news_runner.py")
text = path.read_text(encoding="utf-8")

old_constants = '''_STORY_CONTEXTS = {}

_DEDUPE_TOKEN_RE = re.compile(r"[A-Za-z0-9\\u0600-\\u06ff]+")
'''
new_constants = '''_STORY_CONTEXTS = {}

# Cross-run mix guard. Sports remains a valid lane, but after one sports card
# the next three selected cards should come from other lanes when at least one
# valid alternative can be illustrated. This prevents famous club/player names
# from dominating repeated review runs without banning genuinely major sports.
SPORTS_BALANCE_WINDOW = 3
_SPORTS_MEMORY_STRONG_RE = re.compile(
    r"(?:رونالدو|ميسي|نيمار|ليفربول|ريال مدريد|برشلونة|مانشستر سيتي|"
    r"مانشستر يونايتد|باريس سان جيرمان|دوري|بطولة|مباراة|مباريات|كأس|"
    r"هدف|هداف|أهداف|لاعب|مدرب|كرة القدم|نهائي|يتأهل|تأهل|لقب|خماسية|"
    r"ronaldo|messi|neymar|liverpool|real madrid|barcelona|"
    r"manchester (?:city|united)|paris saint-germain|football|soccer|"
    r"league|cup|match|goal|player|coach|transfer|champion)",
    re.IGNORECASE,
)
_SPORTS_MEMORY_HILAL_CONTEXT_RE = re.compile(
    r"(?:صفقة|موسم|نادي|يسجل|سجل|يفوز|فوز|يخسر|خسارة|تعادل|تعاقد|"
    r"انتقال|لاعب|مدرب|دوري|مباراة|بطولة|كأس|هدف|نهائي|خماسية)"
)

_DEDUPE_TOKEN_RE = re.compile(r"[A-Za-z0-9\\u0600-\\u06ff]+")
'''
assert old_constants in text
text = text.replace(old_constants, new_constants, 1)

anchor = '''def _normalize_source_link(value):
'''
insert = '''def _story_lane(story, shortlist):
    """Return the deterministic source lane for one ranked model story."""
    if not isinstance(story, dict):
        return ""
    item_no = story.get("item")
    if isinstance(item_no, bool) or not isinstance(item_no, int):
        return ""
    if item_no < 1 or item_no > len(shortlist):
        return ""
    return str(shortlist[item_no - 1].get("lane", "business_tech") or "")


def _legacy_headline_is_sports(headline):
    """Conservative fallback for old posted-state rows that lack a lane.

    New rows persist the exact editorial lane. The text fallback only needs to
    bridge the existing 3-day memory, so prefer false negatives over treating a
    business headline as sports. Al Hilal is special-cased to avoid الهلال الأحمر.
    """
    text = str(headline or "").strip()
    if not text:
        return False
    if _SPORTS_MEMORY_STRONG_RE.search(text):
        return True
    if "الهلال" in text and "الهلال الأحمر" not in text:
        return bool(_SPORTS_MEMORY_HILAL_CONTEXT_RE.search(text))
    return False


def _posted_story_lane(entry):
    if not isinstance(entry, dict):
        return ""
    lane = str(entry.get("lane", "") or "").strip()
    if lane in LANE_ORDER:
        return lane
    if _legacy_headline_is_sports(entry.get("headline", "")):
        return "sports"
    return ""


def _recent_sports_card(posted, window=SPORTS_BALANCE_WINDOW):
    recent = [entry for entry in (posted or []) if isinstance(entry, dict)][-window:]
    return any(_posted_story_lane(entry) == "sports" for entry in recent)


def rebalance_ranked_result(result, shortlist, posted):
    """Keep sports to at most one selected card in a rolling four-card window.

    The model still decides quality within each lane. When a sports card exists
    among the previous three outputs, stable-partition the already validated
    ranking so every valid non-sports alternative is tried for imagery before
    another sports story. If no non-sports alternative can ultimately render,
    sports remains available as the fallback rather than causing a dead run.
    """
    if not isinstance(result, dict):
        return result
    stories = result.get("stories")
    if not isinstance(stories, list):
        return result

    annotated = []
    for story in stories:
        if not isinstance(story, dict):
            continue
        copy = dict(story)
        lane = _story_lane(copy, shortlist)
        if lane:
            copy["_editorial_lane"] = lane
        annotated.append(copy)

    balanced = dict(result)
    balanced["stories"] = annotated
    if not _recent_sports_card(posted):
        return balanced

    non_sports = [s for s in annotated if s.get("_editorial_lane") != "sports"]
    sports = [s for s in annotated if s.get("_editorial_lane") == "sports"]
    if not non_sports or not sports:
        return balanced

    reordered = non_sports + sports
    if reordered != annotated:
        print(
            "    sports balance: a sports card appeared in the previous "
            f"{SPORTS_BALANCE_WINDOW} outputs — trying {len(non_sports)} "
            "non-sports alternative(s) first"
        )
        balanced["stories"] = reordered
    return balanced


'''
assert anchor in text
text = text.replace(anchor, insert + anchor, 1)

old_save = '''            link = _normalize_source_link(story.get("link"))
            if link and entry.get("source_link") != link:
                entry["source_link"] = link
                changed = True
'''
new_save = '''            link = _normalize_source_link(story.get("link"))
            if link and entry.get("source_link") != link:
                entry["source_link"] = link
                changed = True
            lane = str(story.get("_editorial_lane", "") or "").strip()
            if lane in LANE_ORDER and entry.get("lane") != lane:
                entry["lane"] = lane
                changed = True
'''
assert old_save in text
text = text.replace(old_save, new_save, 1)

old_summary = '''        raw = original_summarize(decorated, already_posted, pinned)
        validated = validate_ranked_result(raw, shortlist)
        return remember_story_contexts(validated)
'''
new_summary = '''        raw = original_summarize(decorated, already_posted, pinned)
        validated = validate_ranked_result(raw, shortlist)
        load_posted = getattr(news_bot_module, "load_posted", None)
        posted = load_posted() if callable(load_posted) else []
        balanced = rebalance_ranked_result(validated, shortlist, posted)
        return remember_story_contexts(balanced)
'''
assert old_summary in text
text = text.replace(old_summary, new_summary, 1)

path.write_text(text, encoding="utf-8")
