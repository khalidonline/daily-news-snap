"""Deterministic editorial-quality checks for Story-to-Snapchat briefs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class EditorialQualityResult:
    passed: bool
    status: str
    reasons: tuple[str, ...]


_BOILERPLATE = (
    "as an ai",
    "language model",
    "here is the answer",
    "إليك الإجابة",
    "كنموذج",
    "tbd",
    "todo",
    "lorem ipsum",
    "```",
)

_UNSUPPORTED_COMPARATIVES = (
    "تتفوق على",
    "الأولى في العالم",
    "الأكبر في العالم",
    "أعلى من الجميع",
)

_TOKEN_RE = re.compile(r"[\w\u0600-\u06ff]+", re.UNICODE)
_URL_RE = re.compile(r"https?://", re.IGNORECASE)


def _clean(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _norm(value: object) -> str:
    text = _clean(value).casefold()
    return " ".join(_TOKEN_RE.findall(text))


def _tokens(value: object) -> set[str]:
    return set(_TOKEN_RE.findall(_clean(value).casefold()))


def _near_duplicate(a: object, b: object) -> bool:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    ta, tb = _tokens(a), _tokens(b)
    if min(len(ta), len(tb)) < 5:
        return False
    return len(ta & tb) / max(1, len(ta | tb)) >= 0.86


def _nonempty_list(value: object) -> bool:
    return isinstance(value, (list, tuple)) and any(_clean(item) for item in value)


def _text_fragments(frames: Iterable[dict]) -> Iterable[str]:
    for frame in frames:
        for key in ("heading", "text", "punch"):
            yield _clean(frame.get(key))


def evaluate_brief(brief: dict, expected_frames: int) -> EditorialQualityResult:
    reasons: list[str] = []
    if not isinstance(brief, dict):
        return EditorialQualityResult(False, "EDITORIAL_FAILED", ("brief must be an object",))

    frames = list(brief.get("frames") or [])
    if len(frames) != int(expected_frames):
        reasons.append(f"expected {int(expected_frames)} frames, got {len(frames)}")

    sources = brief.get("sources") or []
    if not isinstance(sources, (list, tuple)) or not any(_clean(source) for source in sources):
        reasons.append("missing source/search evidence")

    valid_frames: list[dict] = []
    for index, raw in enumerate(frames, start=1):
        if not isinstance(raw, dict):
            reasons.append(f"frame {index} must be an object")
            continue
        valid_frames.append(raw)
        for field in ("heading", "text", "punch", "subject_kind"):
            if not _clean(raw.get(field)):
                reasons.append(f"frame {index} missing {field}")
        if not (_nonempty_list(raw.get("image_keywords")) or _nonempty_list(raw.get("image_keywords_ar"))):
            reasons.append(f"frame {index} missing visual targeting keywords")

    for i, frame in enumerate(valid_frames):
        for j in range(i):
            other = valid_frames[j]
            if _norm(frame.get("heading")) and _norm(frame.get("heading")) == _norm(other.get("heading")):
                reasons.append(f"duplicate heading in frames {j + 1} and {i + 1}")
            if _near_duplicate(frame.get("text"), other.get("text")):
                reasons.append(f"near-duplicate body in frames {j + 1} and {i + 1}")

    for fragment in _text_fragments(valid_frames):
        folded = fragment.casefold()
        if any(marker in folded for marker in _BOILERPLATE):
            reasons.append("model/placeholder boilerplate detected")
            break
        if _URL_RE.findall(fragment) and (_URL_RE.findall(fragment).__len__() > 1 or "{" in fragment or "}" in fragment):
            reasons.append("excessive raw URL/JSON fragment detected")
            break
        if any(phrase in fragment for phrase in _UNSUPPORTED_COMPARATIVES):
            reasons.append("unsupported comparative/superlative wording detected")
            break

    # A story-shaped deck needs an opening, a middle, and a concrete closing.
    if valid_frames:
        first = valid_frames[0]
        if len(_tokens(first.get("text"))) < 5:
            reasons.append("opening lacks enough narrative context")
    if len(valid_frames) >= 3:
        middle = valid_frames[1:-1]
        if not any(len(_tokens(frame.get("text"))) >= 5 for frame in middle):
            reasons.append("middle story development is incomplete")
    if valid_frames:
        closing = valid_frames[-1]
        closing_text = _clean(closing.get("text"))
        closing_punch = _clean(closing.get("punch"))
        if len(_tokens(closing_text)) < 5 or len(_tokens(closing_punch)) < 2:
            reasons.append("closing payoff is too thin")
        if closing_text.endswith("؟") or closing_punch.endswith("؟") or closing_text.endswith("?") or closing_punch.endswith("?"):
            reasons.append("closing must resolve with a payoff, not a question")

    # Deduplicate reasons while preserving deterministic order.
    unique_reasons = tuple(dict.fromkeys(reasons))
    passed = not unique_reasons
    return EditorialQualityResult(
        passed=passed,
        status="EDITORIAL_LOCKED" if passed else "EDITORIAL_REVIEW",
        reasons=unique_reasons,
    )
