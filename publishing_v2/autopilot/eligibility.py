"""Early routine-trigger eligibility; independent research remains mandatory."""
import re


def routine_trigger_rejection(candidate):
    # High-confidence headline patterns, not a general medical/safety classifier.
    # Do not scan background history or ban the person, food or company itself.
    title = candidate.get('title', '')
    if not isinstance(title, str):
        return None
    title = re.sub(r'[\u064b-\u065f\u0670\u0640]', '', title).casefold()
    title = title.translate(str.maketrans({'أ':'ا', 'إ':'ا', 'آ':'ا'}))
    title = ' '.join(title.split()).lstrip('«“" ')
    if (re.search(r'^(?:عاجل\s*[:：-]?\s*)?(?:وفاة|وفاه|توفي|توفى)\b', title)
            or re.search(r'\b(?:dies|died|dead)\s+(?:aged|at\s+(?:the\s+)?age\s+of)\s+\d+', title)):
        return 'obituary_trigger'
    arabic_condition = any(term in title for term in ('الكوليسترول', 'السكري', 'ضغط الدم'))
    arabic_advice = re.search(r'(?<!\w)(?:تناول|اطعمة|غذاء|فوائد|مشروبات|مكملات)(?!\w)', title)
    english_condition = re.search(r'\b(?:cholesterol|diabetes|blood pressure)\b', title)
    english_advice = re.search(r'\b(?:eat|eating|foods?|diet|drinks?|supplements?)\b', title)
    if (arabic_condition and arabic_advice) or (english_condition and english_advice):
        return 'medical_advice_trigger'
    return None
