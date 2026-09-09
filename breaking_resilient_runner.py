#!/usr/bin/env python3
"""Breaking runner with a bounded, truthful fallback for severe Saudi events.

The normal strict photo ladder remains first. Only after Commons itself finds
nothing usable for a severe Saudi security event do we try a free Commons map
of Saudi Arabia. This is contextual artwork, not a claimed photo of the event.
"""

import os
import re

import breaking_news_runner as base
import news_bot


_SAUDI_RE = re.compile(
    r"(?:السعود|أبها|خميس\s*مشيط|جيزان|جازان|نجران|الرياض|جدة|"
    r"\b(?:saudi(?: arabia)?|ksa|abha|khamis mushait|jizan|jazan|najran|riyadh|jeddah)\b)",
    re.IGNORECASE,
)
_SEVERE_SECURITY_RE = re.compile(
    r"(?:هجوم|اعتداء|صاروخ|صواريخ|مسيّر|مسيرة|طائرات مسيرة|إصابة|إصابات|"
    r"قتيل|قتلى|انفجار|قصف|منشآت|مطار|قاعدة|دفاع|تحالف|"
    r"\b(?:attack|missile|drone|injur|killed|explosion|strike|facility|airport|base|defen[cs]e)\w*\b)",
    re.IGNORECASE,
)

_VISUAL_FALLBACK_RULE = """

استثناء تحريري ضيق بعد استنفاد الصور الحقيقية فقط:
- في حدث أمني سعودي شديد يمس عدة مدن/مناطق أو المملكة ككل، «خريطة السعودية»
  الواضحة مقبولة كصورة سياقية، ولا تُعامل كأنها صورة للحظة الهجوم.
- شعار الجهة الرسمية مقبول فقط إذا كانت الجهة نفسها مسماة مباشرة في الحدث
  أو هي الجهة التي أصدرت التأكيد؛ لا تستخدم شعار جهة قريبة أو مشابهة.
- لا يفتح هذا الاستثناء الباب لمعلم عام أو أفق مدينة أو صورة عسكرية عامة.
"""


def _fallback_queries(event):
    text = str(event or "")
    if _SAUDI_RE.search(text) and _SEVERE_SECURITY_RE.search(text):
        return ["Saudi Arabia map"]
    return []


def install_resilient_visual_prompt(module=base):
    rule = _VISUAL_FALLBACK_RULE.strip()
    if rule not in module._BREAKING_VISION_PROMPT:
        module._BREAKING_VISION_PROMPT += _VISUAL_FALLBACK_RULE


def install_resilient_visual_fallback(bot=news_bot):
    """Retry Commons once with a Saudi map; no model/search-provider spend."""
    event = (getattr(bot, "PINNED_EVENT", "") or "").strip()
    fallback = _fallback_queries(event)
    original = getattr(bot, "fetch_commons_photo", None)
    if not fallback or not callable(original):
        return

    def commons_with_context_fallback(queries, out_path, *args, **kwargs):
        photo, credit = original(queries, out_path, *args, **kwargs)
        if photo:
            return photo, credit

        print("    breaking visual fallback: trying contextual Saudi map")
        graphic_check = getattr(bot, "looks_like_a_graphic", None)
        if callable(graphic_check):
            bot.looks_like_a_graphic = lambda _path: False
        try:
            # Maps are intentionally graphics. Commons still enforces licence,
            # download integrity and recent-use checks; the strict breaking
            # vision gate evaluates relevance after this function returns.
            return original(
                fallback,
                out_path,
                need_saudi=False,
                min_hits=0,
                subject_mode=True,
            )
        finally:
            if callable(graphic_check):
                bot.looks_like_a_graphic = graphic_check

    bot.fetch_commons_photo = commons_with_context_fallback


def run():
    install_resilient_visual_prompt(base)
    install_resilient_visual_fallback(news_bot)
    return base.run_bot(news_bot)


if __name__ == "__main__":
    raise SystemExit(run() or 0)
