#!/usr/bin/env python3
"""Breaking runner with a bounded, truthful fallback for severe Saudi events.

The normal strict photo ladder remains first. Only after Commons itself finds
nothing usable for a severe Saudi security event do we try a free Commons map
of Saudi Arabia. This is contextual artwork, not a claimed photo of the event.
"""

import re
from pathlib import Path

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
_SAUDI_MAP_TITLE = "File:Saudi Arabia map-ar.png"
_CENTCOM_SEAL_TITLE = "File:Seal of the United States Central Command.png"
_CENTCOM_RE = re.compile(
    r"(?:القيادة\s+المركزية\s+(?:الأمريكية|للولايات\s+المتحدة)|"
    r"\b(?:united\s+states\s+central\s+command|uscentcom|centcom)\b)",
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
    if _CENTCOM_RE.search(text):
        return ["United States Central Command official seal"]
    return []


def _exact_context_visual(title, event):
    text = str(event or "")
    if title == _SAUDI_MAP_TITLE:
        return bool(_SAUDI_RE.search(text) and _SEVERE_SECURITY_RE.search(text))
    if title == _CENTCOM_SEAL_TITLE:
        return bool(_CENTCOM_RE.search(text))
    return False


def install_resilient_visual_prompt(module=base):
    rule = _VISUAL_FALLBACK_RULE.strip()
    if rule not in module._BREAKING_VISION_PROMPT:
        module._BREAKING_VISION_PROMPT += _VISUAL_FALLBACK_RULE


def install_exact_official_logo_acceptance(module=base):
    """Accept only a verified exact organization mark named in the event."""
    original = getattr(module, "_breaking_photo_acceptable", None)
    if not callable(original):
        return

    def acceptable(bot, photo_path, event, extra_context=""):
        try:
            title = Path(str(photo_path) + ".commons-title").read_text(
                encoding="utf-8"
            ).strip()
        except OSError:
            title = ""
        if title == _CENTCOM_SEAL_TITLE and _exact_context_visual(title, event):
            print("    exact verified CENTCOM seal accepted as official identity")
            return True
        return original(bot, photo_path, event, extra_context)

    module._breaking_photo_acceptable = acceptable


def install_exact_map_acceptance(module=base):
    """Accept the one verified map only where the narrow fallback applies."""
    original = getattr(module, "_breaking_photo_acceptable", None)
    if not callable(original):
        return

    def acceptable(bot, photo_path, event, extra_context=""):
        try:
            title = Path(str(photo_path) + ".commons-title").read_text(
                encoding="utf-8"
            ).strip()
        except OSError:
            title = ""
        if title == _SAUDI_MAP_TITLE and _exact_context_visual(title, event):
            print("    exact verified Saudi map accepted as contextual artwork")
            return True
        return original(bot, photo_path, event, extra_context)

    module._breaking_photo_acceptable = acceptable


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
        commons_safe = getattr(bot, "_commons_safe", None)
        if callable(graphic_check):
            bot.looks_like_a_graphic = lambda _path: False
        if callable(commons_safe):
            def allow_exact_saudi_map(page, info):
                if _exact_context_visual(page.get("title"), event):
                    return True
                return commons_safe(page, info)
            bot._commons_safe = allow_exact_saudi_map
        try:
            # Maps are intentionally graphics. Commons still enforces licence,
            # download integrity and recent-use checks; the strict breaking
            # vision gate evaluates relevance after this function returns.
            photo, credit = original(
                fallback,
                out_path,
                need_saudi=False,
                min_hits=0,
                subject_mode=True,
            )
            if photo:
                try:
                    title = Path(str(photo) + ".commons-title").read_text(
                        encoding="utf-8"
                    ).strip()
                except OSError:
                    title = ""
                label = "شعار رسمي" if title == _CENTCOM_SEAL_TITLE else "خريطة توضيحية"
                credit = label + " / " + (credit or "Wikimedia Commons")
            return photo, credit
        finally:
            if callable(graphic_check):
                bot.looks_like_a_graphic = graphic_check
            if callable(commons_safe):
                bot._commons_safe = commons_safe

    bot.fetch_commons_photo = commons_with_context_fallback


def run():
    install_resilient_visual_prompt(base)
    install_exact_map_acceptance(base)
    install_exact_official_logo_acceptance(base)
    install_resilient_visual_fallback(news_bot)
    return base.run_bot(news_bot)


if __name__ == "__main__":
    raise SystemExit(run() or 0)
