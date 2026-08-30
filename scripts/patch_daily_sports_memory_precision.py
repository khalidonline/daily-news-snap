from pathlib import Path

path = Path("daily_news_runner.py")
text = path.read_text(encoding="utf-8")

old_constants = '''_SPORTS_MEMORY_STRONG_RE = re.compile(
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
'''
new_constants = '''_SPORTS_MEMORY_AR_TOKENS = {
    "رونالدو", "ميسي", "نيمار", "ليفربول", "برشلونة",
    "دوري", "بطولة", "مباراة", "مباريات", "كأس", "هداف", "أهداف",
    "لاعب", "مدرب", "خماسية", "يتأهل", "تأهل",
}
_SPORTS_MEMORY_PHRASE_RE = re.compile(
    r"(?:ريال مدريد|مانشستر سيتي|مانشستر يونايتد|باريس سان جيرمان|"
    r"\\b(?:ronaldo|messi|neymar|liverpool|real madrid|barcelona|"
    r"manchester (?:city|united)|paris saint-germain|football|soccer|"
    r"league|cup|match|goal|player|coach|transfer|champion)\\b)",
    re.IGNORECASE,
)
_SPORTS_MEMORY_HILAL_CONTEXT_TOKENS = {
    "صفقة", "موسم", "نادي", "يسجل", "سجل", "يفوز", "فوز", "يخسر",
    "خسارة", "تعادل", "تعاقد", "انتقال", "لاعب", "مدرب", "دوري",
    "مباراة", "بطولة", "كأس", "هداف", "أهداف", "خماسية",
}
'''
assert old_constants in text
text = text.replace(old_constants, new_constants, 1)

old_function = '''def _legacy_headline_is_sports(headline):
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
'''
new_function = '''def _legacy_headline_is_sports(headline):
    """Conservative fallback for old posted-state rows that lack a lane.

    New rows persist the exact editorial lane. The text fallback only needs to
    bridge the existing 3-day memory, so use exact Arabic tokens and specific
    sports names/phrases. Avoid generic substrings such as هدف/نهائي because
    they also appear in ordinary business and government headlines.
    """
    text = str(headline or "").strip()
    if not text:
        return False
    if _SPORTS_MEMORY_PHRASE_RE.search(text):
        return True
    normalized = _ARABIC_DIACRITICS_RE.sub("", text).translate(
        _ARABIC_NORMALIZATION
    )
    tokens = set(_DEDUPE_TOKEN_RE.findall(normalized))
    if tokens & _SPORTS_MEMORY_AR_TOKENS:
        return True
    if "الهلال" in tokens and "الاحمر" not in tokens:
        return bool(tokens & _SPORTS_MEMORY_HILAL_CONTEXT_TOKENS)
    return False
'''
assert old_function in text
text = text.replace(old_function, new_function, 1)

path.write_text(text, encoding="utf-8")
