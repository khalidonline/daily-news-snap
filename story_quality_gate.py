#!/usr/bin/env python3
"""Deterministic pre-review quality gate for six-card Stories.

No renderer, network, model, Telegram, or Snapchat side effects live here.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

QUALITY_POLICY = "story-quality-v1"

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u0600-\u06ff]+", re.UNICODE)
_YEAR_RE = re.compile(r"(?<!\d)((?:18|19|20)\d{2})(?!\d)")
_AR_DIACRITICS_RE = re.compile(r"[\u064b-\u065f\u0670\u06d6-\u06ed]")
_AR_PREFIXES = ("و", "ف", "ب", "ك", "ل")

_SUBJECT_STOPWORDS = {
    "قصة", "قصه", "كيف", "لماذا", "من", "الى", "إلى", "في", "على", "عن",
    "مع", "و", "ثم", "تطور", "تطورها", "تطوره", "رحلة", "رحله", "حكاية",
    "حكايه", "شركة", "شركه", "تاريخ", "بداية", "بدايه", "اول", "أول",
    "the", "story", "of", "how", "why", "history", "evolution", "company",
}

_SUPPORT_CUES = (
    "ولهذا", "ولذلك", "لذلك", "لكن", "ومع", "مع ذلك", "بعدها", "بعد ذلك",
    "في المقابل", "بسبب ذلك", "نتيجة لذلك", "result", "therefore", "however",
    "because", "meanwhile", "after that",
)
_FLASHBACK_CUES = (
    "بالعودة", "نعود", "قبل ذلك", "قبلها", "وقبل", "عودة إلى", "عوده الى",
    "looking back", "flashback", "back in",
)
_CURRENT_CUES = (
    "اليوم", "حالياً", "حاليا", "الآن", "الان", "في الوقت الحالي",
    "today", "currently", "now", "present day", "present-day",
)
_HISTORICAL_COPY_CUES = (
    "قديماً", "قديما", "تاريخياً", "تاريخيا", "في الماضي", "سابقاً", "سابقا",
    "historically", "in the past", "formerly",
)
_ARCHIVE_VISUAL_CUES = (
    "historic", "historical", "archive", "archival", "old", "vintage", "retro",
    "قديم", "قديمة", "قديمه", "أرشيف", "ارشيف",
)
_MODERN_VISUAL_CUES = (
    "modern", "current", "today", "present day", "present-day", "terminal 1",
    "terminal1", "new terminal", "حديث", "حديثة", "حديثه", "حالي", "حالية", "حاليه",
)

_EXCLUSIVITY_PATTERNS = (
    re.compile(r"\bالوحيد(?:ة)?\b"), re.compile(r"\bحصراً\b"),
    re.compile(r"\bحصرا\b"), re.compile(r"\bلا\s+يوجد\s+غير\b"),
    re.compile(r"\bالطريق\s+الوحيد\b"), re.compile(r"\bonly\b", re.I),
    re.compile(r"\bsole\b", re.I), re.compile(r"\bexclusively\b", re.I),
)
_UNIVERSALITY_PATTERNS = (
    re.compile(r"\bدائماً\b"), re.compile(r"\bدائما\b"), re.compile(r"\bالجميع\b"),
    re.compile(r"\bكل\s+الناس\b"), re.compile(r"\bأبداً\b"),
    re.compile(r"\balways\b", re.I), re.compile(r"\bnever\b", re.I),
)
_SUPERLATIVE_PATTERNS = (
    re.compile(r"\bالأول\s+في\s+العالم\b"), re.compile(r"\bالأكبر\s+في\s+العالم\b"),
    re.compile(r"\bالأغلى\s+في\s+العالم\b"),
    re.compile(r"\bthe\s+(?:first|largest|biggest|most expensive)\s+in\s+the\s+world\b", re.I),
)

_SAUDI_CONTEXT_TERMS = (
    "السعودية", "السعوديه", "سعودي", "المملكة العربية السعودية", "الرياض",
    "جدة", "جده", "مكة", "مكه", "المدينة", "المدينه", "الدمام", "الخبر",
    "الطائف", "أبها", "ابها", "القصيم", "تبوك", "نيوم",
)

_VISUAL_DIMENSIONS = {"visual_chronology", "final_frame_currency"}
_EDITORIAL_DIMENSIONS = {"subject_focus", "claim_precision", "narrative_chronology"}
_REPAIR_MESSAGES = {
    "subject_focus": "keep the frame centered on the named Story subject",
    "claim_precision": "rewrite the claim precisely and remove unsupported exclusivity or ambiguity",
    "narrative_chronology": "restore chronological order or make the flashback explicit",
    "visual_chronology": "replace the visual with one matching this frame's time period",
    "final_frame_currency": "use a clearly current visual for the present-day ending",
}


def _clean(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_arabic(value: str) -> str:
    text = _AR_DIACRITICS_RE.sub("", value)
    return text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي")


def _stem_token(token: str) -> str:
    token = _normalize_arabic(token.casefold())
    if re.search(r"[\u0600-\u06ff]", token):
        # Strip conjunctions (و/ف) freely, and other one-letter clitics only
        # when they introduce the definite article. This handles forms such
        # as "وبالعودة" without corrupting normal words such as "لاحقا".
        while len(token) > 4 and token[:1] in _AR_PREFIXES:
            first = token[0]
            rest = token[1:]
            if first in {"و", "ف"} or rest.startswith("ال"):
                token = rest
                continue
            break
        if len(token) > 4 and token.startswith("ال"):
            token = token[2:]
    return token


def _tokens(value: object) -> list[str]:
    return [_stem_token(token) for token in _TOKEN_RE.findall(_clean(value)) if token]


def _has_any(value: object, cues: Iterable[str]) -> bool:
    """Phrase match on normalized token boundaries, never arbitrary substrings."""
    haystack = " " + " ".join(_tokens(value)) + " "
    for cue in cues:
        needle_tokens = _tokens(cue)
        if needle_tokens and (" " + " ".join(needle_tokens) + " ") in haystack:
            return True
    return False


def _copy_blob(frame: dict[str, Any]) -> str:
    return " ".join(
        _clean(frame.get(key)) for key in ("heading", "text", "punch")
        if _clean(frame.get(key))
    )


def _subject_terms(story: str) -> set[str]:
    stop = {_stem_token(word) for word in _SUBJECT_STOPWORDS}
    terms = [
        token for token in _tokens(story)
        if token not in stop and not token.startswith("تطور") and not token.startswith("حكاي")
    ]
    return set(terms or _tokens(story))


def _keyword_blob(frame: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("image_keywords", "image_keywords_ar"):
        value = frame.get(key) or []
        if isinstance(value, (list, tuple)):
            parts.extend(_clean(item) for item in value)
        else:
            parts.append(_clean(value))
    return " ".join(parts)


def _focus_label(frame: dict[str, Any], subject_terms: set[str]) -> tuple[str, list[str]]:
    copy_overlap = set(_tokens(_copy_blob(frame))) & subject_terms
    visual_overlap = set(_tokens(_keyword_blob(frame))) & subject_terms
    threshold = 1 if len(subject_terms) <= 2 else 2
    if len(copy_overlap) >= threshold:
        return "DIRECT", sorted(copy_overlap)
    if _has_any(_copy_blob(frame), _SUPPORT_CUES) or copy_overlap or visual_overlap:
        return "SUPPORTING", sorted(copy_overlap | visual_overlap)
    return "DRIFT", []


def _years(value: object) -> list[int]:
    return [int(match) for match in _YEAR_RE.findall(_clean(value))]


def _is_current(frame: dict[str, Any]) -> bool:
    return _has_any(_copy_blob(frame), _CURRENT_CUES)


def _is_flashback(frame: dict[str, Any]) -> bool:
    return _has_any(_copy_blob(frame), _FLASHBACK_CUES)


def _is_historical_copy(frame: dict[str, Any]) -> bool:
    years = _years(_copy_blob(frame))
    return bool(years and max(years) < 2015) or _has_any(_copy_blob(frame), _HISTORICAL_COPY_CUES)


def _saudi_context(story: str, frames: list[dict[str, Any]]) -> bool:
    blob = " ".join([story] + [_copy_blob(frame) for frame in frames])
    return _has_any(blob, _SAUDI_CONTEXT_TERMS)


def _finding(frame: int, dimension: str, code: str, message: str) -> dict[str, Any]:
    return {
        "frame": int(frame), "dimension": dimension, "severity": "BLOCK",
        "code": code, "message": message,
    }


def _string_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            if key != "frame_payload":
                yield from _string_values(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _string_values(item)


def _visual_blob(frame: dict[str, Any], visual_row: dict[str, Any]) -> str:
    return " ".join([_keyword_blob(frame)] + list(_string_values(visual_row or {})))


def _visual_era(frame: dict[str, Any], visual_row: dict[str, Any]) -> dict[str, Any]:
    blob = _visual_blob(frame, visual_row)
    years = _years(blob)
    archival = _has_any(blob, _ARCHIVE_VISUAL_CUES)
    modern = _has_any(blob, _MODERN_VISUAL_CUES)
    if years:
        modern = modern or max(years) >= 2015
        archival = archival or max(years) < 2010
    if archival and not (modern and years and max(years) >= 2015):
        label = "HISTORICAL"
    elif modern:
        label = "CURRENT"
    else:
        label = "UNKNOWN"
    return {"label": label, "years": years}


def repair_target(report: dict[str, Any]) -> dict[str, Any]:
    by_frame: dict[int, set[str]] = {}
    dimensions: set[str] = set()
    instructions: dict[str, list[str]] = {}
    for item in report.get("findings", []) or []:
        if item.get("severity") != "BLOCK":
            continue
        frame_no = int(item.get("frame") or 0)
        if frame_no <= 0:
            continue
        dimension = str(item.get("dimension") or "")
        dimensions.add(dimension)
        by_frame.setdefault(frame_no, set()).add(dimension)
        message = _REPAIR_MESSAGES.get(dimension)
        if message:
            instructions.setdefault(str(frame_no), [])
            if message not in instructions[str(frame_no)]:
                instructions[str(frame_no)].append(message)
    frame_modes = {}
    for frame_no, dims in by_frame.items():
        if dims <= _VISUAL_DIMENSIONS:
            mode = "visual_only"
        elif dims <= _EDITORIAL_DIMENSIONS:
            mode = "editorial_frame"
        else:
            mode = "mixed_frame"
        frame_modes[str(frame_no)] = mode
    return {
        "frames": sorted(by_frame), "dimensions": sorted(dimensions),
        "frame_modes": frame_modes, "instructions": instructions,
        "full_deck_regeneration": False,
    }


def release_ready(report: dict[str, Any]) -> bool:
    return bool(report) and report.get("status") == "PASS" and not any(
        item.get("severity") == "BLOCK" for item in report.get("findings", []) or []
    )


def evaluate_story_quality(
    story: str, frames: list[dict[str, Any]], visual_state: dict[str, Any]
) -> dict[str, Any]:
    frames = [frame if isinstance(frame, dict) else {} for frame in (frames or [])]
    findings: list[dict[str, Any]] = []
    dimensions = {key: "PASS" for key in (
        "subject_focus", "claim_precision", "narrative_chronology",
        "visual_chronology", "final_frame_currency",
    )}
    subject_terms = _subject_terms(story)
    visual_rows = (visual_state or {}).get("frames") or {}
    frame_evidence: list[dict[str, Any]] = []
    supporting_run = 0
    last_copy_year: int | None = None
    current_seen = False
    last_visual_year: int | None = None
    last_visual_rank: int | None = None
    saudi_context = _saudi_context(story, frames)

    for index, frame in enumerate(frames, 1):
        focus, overlap = _focus_label(frame, subject_terms)
        copy_blob = _copy_blob(frame)
        current = _is_current(frame)
        flashback = _is_flashback(frame)
        copy_years = _years(copy_blob)
        visual = _visual_era(frame, visual_rows.get(str(index)) or {})
        frame_evidence.append({
            "frame": index, "focus": focus, "subject_overlap": overlap,
            "copy_years": copy_years, "current": current, "flashback": flashback,
            "visual_era": visual["label"], "visual_years": visual["years"],
        })

        supporting_run = supporting_run + 1 if focus == "SUPPORTING" else 0
        if focus == "DRIFT" or (index in {1, len(frames)} and focus != "DIRECT"):
            dimensions["subject_focus"] = "BLOCKED"
            findings.append(_finding(
                index, "subject_focus",
                "CRITICAL_FRAME_NOT_DIRECT" if index in {1, len(frames)} else "SUBJECT_DRIFT",
                "frame does not materially advance the named Story subject",
            ))
        if supporting_run > 2:
            dimensions["subject_focus"] = "BLOCKED"
            findings.append(_finding(
                index, "subject_focus", "TOO_MUCH_SUPPORTING_CONTEXT",
                "supporting context dominates too many consecutive frames",
            ))

        normalized_copy = _normalize_arabic(copy_blob.casefold())
        if any(pattern.search(normalized_copy) for pattern in _EXCLUSIVITY_PATTERNS):
            dimensions["claim_precision"] = "BLOCKED"
            findings.append(_finding(index, "claim_precision", "UNSUPPORTED_EXCLUSIVITY",
                                     "exclusive wording requires narrower evidence-backed phrasing"))
        if any(pattern.search(normalized_copy) for pattern in _UNIVERSALITY_PATTERNS):
            dimensions["claim_precision"] = "BLOCKED"
            findings.append(_finding(index, "claim_precision", "UNSUPPORTED_UNIVERSALITY",
                                     "universal wording is too broad for release"))
        if any(pattern.search(normalized_copy) for pattern in _SUPERLATIVE_PATTERNS):
            dimensions["claim_precision"] = "BLOCKED"
            findings.append(_finding(index, "claim_precision", "UNSUPPORTED_SUPERLATIVE",
                                     "superlative wording needs explicit evidence"))
        if saudi_context and _has_any(copy_blob, ("الجزيرة",)) and not _has_any(copy_blob, ("شبه الجزيرة",)):
            dimensions["claim_precision"] = "BLOCKED"
            findings.append(_finding(index, "claim_precision", "SAUDI_GEOGRAPHY_AMBIGUOUS",
                                     "use السعودية or المملكة when the modern Kingdom is intended"))

        if copy_years:
            first_year = min(copy_years)
            if last_copy_year is not None and first_year < last_copy_year and not flashback:
                dimensions["narrative_chronology"] = "BLOCKED"
                findings.append(_finding(
                    index, "narrative_chronology", "UNEXPLAINED_TIME_REGRESSION",
                    f"narrative year regresses from {last_copy_year} to {first_year} without flashback",
                ))
            if not flashback:
                last_copy_year = max(last_copy_year or first_year, max(copy_years))
        if current_seen and _is_historical_copy(frame) and not flashback:
            dimensions["narrative_chronology"] = "BLOCKED"
            if not any(f["frame"] == index and f["code"] == "UNEXPLAINED_TIME_REGRESSION" for f in findings):
                findings.append(_finding(index, "narrative_chronology", "CURRENT_TO_HISTORICAL_REGRESSION",
                                         "narrative moves backward after reaching the present day"))
        current_seen = current_seen or current

        visual_years = visual["years"]
        if visual_years:
            visual_year = max(visual_years)
            if last_visual_year is not None and visual_year < last_visual_year and not flashback:
                dimensions["visual_chronology"] = "BLOCKED"
                findings.append(_finding(index, "visual_chronology", "VISUAL_TIME_REGRESSION",
                                         f"visual evidence regresses from {last_visual_year} to {visual_year}"))
            if not flashback:
                last_visual_year = max(last_visual_year or visual_year, visual_year)
        rank = {"HISTORICAL": 0, "UNKNOWN": 1, "CURRENT": 2}[visual["label"]]
        if last_visual_rank is not None and rank < last_visual_rank and not flashback:
            dimensions["visual_chronology"] = "BLOCKED"
            findings.append(_finding(index, "visual_chronology", "VISUAL_ERA_REGRESSION",
                                     "visual sequence moves backward in time without narrative reason"))
        if visual["label"] != "UNKNOWN" and not flashback:
            last_visual_rank = rank
        if current and visual["label"] == "HISTORICAL":
            dimensions["visual_chronology"] = "BLOCKED"
            findings.append(_finding(index, "visual_chronology", "CURRENT_COPY_ARCHIVAL_VISUAL",
                                     "present-day copy is paired with archival visual evidence"))

        if index == len(frames) and current:
            if visual["label"] == "HISTORICAL":
                dimensions["final_frame_currency"] = "BLOCKED"
                findings.append(_finding(index, "final_frame_currency", "CURRENT_COPY_ARCHIVAL_VISUAL",
                                         "current ending cannot use an archival visual"))
            elif visual["label"] != "CURRENT":
                dimensions["final_frame_currency"] = "BLOCKED"
                findings.append(_finding(index, "final_frame_currency", "CURRENT_COPY_UNPROVEN_VISUAL",
                                         "current ending needs positive modern/current visual evidence"))

    status = "BLOCKED" if any(item["severity"] == "BLOCK" for item in findings) else "PASS"
    report = {
        "policy": QUALITY_POLICY, "status": status, "story": story,
        "story_subject_terms": sorted(subject_terms), "dimensions": dimensions,
        "findings": findings, "frame_evidence": frame_evidence,
    }
    report["repair"] = repair_target(report)
    return report
