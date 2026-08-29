#!/usr/bin/env python3
"""Saudi Snapchat editorial runtime for topic_bot.

This keeps the mature research/render/post plumbing in topic_bot.py intact while
installing stricter audience selection, relevance-first automatic imagery, and
publish-time editorial safeguards.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from daily_news_runner import install_auto_image_selector, remember_story_contexts
from topic_editorial import (
    balanced_shortlist,
    enhance_prompt,
    load_performance,
    load_topics_with_categories,
    performance_adjustment,
    validate_brief,
)

PERFORMANCE_FILE = Path(os.getenv("TOPIC_PERFORMANCE_FILE", "state/topic_performance.json"))

_LENGTH_LIMITS = {"title": 45, "body": 260, "takeaway": 110, "caption": 120}
_LENGTH_TARGETS = {"title": 40, "body": 230, "takeaway": 95, "caption": 105}
_LENGTH_ERROR_RE = re.compile(r"^(title|body|takeaway|caption) exceeds \d+ characters$")


def prepare_shortlist(bot: Any, scored: list[dict[str, Any]], performance: dict[str, Any],
                      limit: int = 8) -> list[dict[str, Any]]:
    """Attach categories/audience performance, then build a diverse shortlist."""
    category_by_topic = {
        row["topic"]: row.get("category", "عام")
        for row in load_topics_with_categories(bot.TOPICS_FILE)
    }
    enriched: list[dict[str, Any]] = []
    for source in scored:
        row = dict(source)
        category = category_by_topic.get(row.get("topic"), "موسمي")
        row["category"] = category
        adjustment = performance_adjustment(row.get("topic", ""), category, performance)
        row["score"] = row.get("score", 0) + adjustment
        if adjustment:
            row["reasons"] = list(row.get("reasons", [])) + [
                f"أداء الجمهور: {adjustment:+d}"
            ]
        enriched.append(row)
    return balanced_shortlist(enriched, limit=limit)


def topic_image_story(brief: dict[str, Any]) -> dict[str, Any]:
    """Translate a topic card into the story shape used by the shared image judge."""
    return {
        "headline": str(brief.get("title", "") or "").strip(),
        "summary": str(brief.get("body", "") or "").strip(),
        "takeaway": str(brief.get("takeaway", "") or "").strip(),
        "link": str(brief.get("source_url", "") or "").strip(),
        "scope": "saudi",
        "image_queries": list(brief.get("image_queries", []) or []),
        "image_queries_ar": list(brief.get("image_queries_ar", []) or []),
    }


def _remember_topic_image_context(brief: dict[str, Any]) -> None:
    remember_story_contexts({"stories": [topic_image_story(brief)]})


def _credit_requires_visible(provider: str, credit: str | None) -> bool:
    """Return True when a candidate cannot be shown without a visible credit."""
    provider = (provider or "").strip().lower()
    text = (credit or "").strip().lower()
    if provider == "commons":
        return True
    if provider == "openverse":
        return not any(token in text for token in (
            "cc0", "public domain", "pdm", "public-domain"
        ))
    return False


def _creditless_pair(fetcher, provider: str):
    """Keep a provider for auto search, but reject attribution-required results."""
    def wrapped(*args, **kwargs):
        photo, credit = fetcher(*args, **kwargs)
        if photo and _credit_requires_visible(provider, credit):
            print(f"      auto image [{provider}]: skipped — visible attribution required")
            return None, None
        return photo, credit
    return wrapped


def _creditless_renderer(renderer, generated_credit: str | None = None):
    """Hide ordinary photographer/source credits while retaining AI disclosure."""
    def wrapped(brief, out_path, photo_path=None, photo_credit=None):
        visible_credit = None
        if photo_path and generated_credit \
                and Path(str(photo_path) + ".generated").exists():
            visible_credit = generated_credit
        return renderer(brief, out_path, photo_path, visible_credit)
    return wrapped


def _local_provenance_name(photo) -> str:
    marker = Path(str(photo) + ".exempt")
    try:
        value = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not value.lower().startswith("local:"):
        return ""
    return value.split(":", 1)[1].strip().lower().replace("_", "-")


def _curated_subject_override(photo, context: str) -> bool:
    """Recognize the verified SAMA artifact even when final copy omits its name.

    The local-library selector already chose the asset from the current story's
    image queries. Its provenance marker is therefore stronger evidence than a
    generic vision model calling a known central-bank building "architecture".
    We still require a finance/rates context when the final copy does not name
    SAMA explicitly, so the asset can never override an unrelated topic.
    """
    name = Path(str(photo)).name.lower().replace("_", "-")
    provenance = _local_provenance_name(photo)
    text = str(context or "").lower()
    sama_artifact = "sama" in name or "sama" in provenance
    sama_topic = (
        "sama" in text
        or "ساما" in text
        or "البنك المركزي السعودي" in text
        or "المركزي السعودي" in text
    )
    finance_context = any(token in text for token in (
        "فائدة", "الفائدة", "تمويل", "الفيدرالي", "سايبور",
        "interest rate", "interest-rate", "financing", "banking",
    ))
    return sama_artifact and (sama_topic or finance_context)


def _direct_relevance_only(judge):
    """Topic cards require a direct visual match; verified subject provenance can win."""
    def wrapped(photo, context):
        verdict = str(judge(photo, context)).strip().lower()
        if _curated_subject_override(photo, context):
            if verdict != "yes":
                print("      topic image: verified curated SAMA artifact accepted — direct subject provenance")
            return "yes"
        if verdict == "neutral":
            print("      topic image: neutral candidate rejected — direct relevance required")
            return "no"
        return verdict
    return wrapped


def _topic_generated_photo(fetcher, cleaner=None):
    """Force AI fallback to communicate the topic visually, never with wording.

    The underlying generator already has its own safety check. Topic Brief adds
    a second independent pass because run #78 showed that one visual check can
    miss small storefront/flag lettering. If the second pass finds any text or
    signage, fail closed instead of publishing a bad generated image.
    """
    def wrapped(prompt, out_path):
        strict_prompt = (
            f"{prompt}\n\n"
            "Create a high-quality realistic editorial photograph directly related to the topic. "
            "Communicate the subject through the scene, people, architecture, and objects only. "
            "No visible text of any kind. No Arabic or English words. No names. No labels. "
            "No signs. No logos. No institution names. No building names. No numbers. "
            "No screens with writing. No documents with readable writing. No billboards. "
            "No watermarks. No captions. No emblems. No fake official signage. "
            "Avoid flags, storefronts, signboards, license plates, branded facades, and any "
            "other scene element that normally carries lettering. Do not invent official branding. "
            "Any unavoidable surface that would normally contain writing must be blank or visually unreadable."
        )
        photo, credit = fetcher(strict_prompt, out_path)
        if not photo or cleaner is None:
            return photo, credit
        ok, reason = cleaner(photo)
        if ok:
            return photo, credit
        print(f"  ! topic generated image rejected by second text/signage gate: {reason}")
        Path(str(photo)).unlink(missing_ok=True)
        for suffix in (".generated", ".exempt"):
            Path(str(photo) + suffix).unlink(missing_ok=True)
        return None, None
    return wrapped


def _install_topic_image_policy(bot: Any) -> None:
    """Make relevance-first auto imagery mandatory for Topic Brief."""
    bot.IMAGE_SOURCE = "auto"

    required = ("fetch_commons_photo", "fetch_loc_photo", "photo_shows")
    shared_news = None
    if any(not hasattr(bot, name) for name in required):
        import news_bot as shared_news
        for name in required:
            if not hasattr(bot, name):
                setattr(bot, name, getattr(shared_news, name))

    if not getattr(bot, "_TOPIC_OPEN_LICENSE_POLICY_INSTALLED", False):
        if hasattr(bot, "fetch_commons_photo"):
            bot.fetch_commons_photo = _creditless_pair(bot.fetch_commons_photo, "commons")
        if hasattr(bot, "fetch_openverse_photo"):
            bot.fetch_openverse_photo = _creditless_pair(bot.fetch_openverse_photo, "openverse")
        bot._TOPIC_OPEN_LICENSE_POLICY_INSTALLED = True

    if not getattr(bot, "_TOPIC_DIRECT_IMAGE_JUDGE_INSTALLED", False):
        bot.photo_shows = _direct_relevance_only(bot.photo_shows)
        bot._TOPIC_DIRECT_IMAGE_JUDGE_INSTALLED = True

    if hasattr(bot, "fetch_generated_photo") and not getattr(bot, "_TOPIC_TEXT_FREE_AI_INSTALLED", False):
        if shared_news is None:
            import news_bot as shared_news
        bot.fetch_generated_photo = _topic_generated_photo(
            bot.fetch_generated_photo,
            cleaner=getattr(shared_news, "generated_image_clean", None),
        )
        bot._TOPIC_TEXT_FREE_AI_INSTALLED = True

    bot.recent_fallback = lambda _hero: None

    install_auto_image_selector(bot)

    if not getattr(bot, "_TOPIC_CREDITLESS_RENDERERS_INSTALLED", False):
        if shared_news is None:
            try:
                import news_bot as shared_news
            except Exception:
                shared_news = None
        generated_credit = getattr(shared_news, "GENERATED_CREDIT", None) \
            if shared_news is not None else None
        if hasattr(bot, "render_story"):
            bot.render_story = _creditless_renderer(bot.render_story, generated_credit)
        if hasattr(bot, "render_topic"):
            bot.render_topic = _creditless_renderer(bot.render_topic, generated_credit)
        bot._TOPIC_CREDITLESS_RENDERERS_INSTALLED = True


def _retry_length_feedback(brief: dict[str, Any], errors: list[str]) -> str:
    """Give the rewrite model exact counts and targets instead of a vague max error."""
    lines: list[str] = []
    for field, limit in _LENGTH_LIMITS.items():
        if not any(error.startswith(f"{field} exceeds ") for error in errors):
            continue
        value = str(brief.get(field, "") or "").strip()
        lines.append(
            f"- {field} طوله الحالي {len(value)} حرفاً؛ استهدف {_LENGTH_TARGETS[field]} "
            f"حرفاً أو أقل (الحد الأقصى {limit}). اختصر المعنى ولا تضف تفاصيل جديدة."
        )
    return "\n".join(lines)


def _only_length_errors(errors: list[str]) -> bool:
    return bool(errors) and all(_LENGTH_ERROR_RE.match(error) for error in errors)


def _third_draft_worth_retrying(errors: list[str]) -> bool:
    """Spend one final model call only on fixable editorial/source finance errors."""
    if not errors:
        return False
    retryable_fragments = (
        "state each institution's decision separately",
        "Federal Reserve and SAMA primary sources are required",
        "policy rate is not the only driver of variable financing",
    )
    return all(
        bool(_LENGTH_ERROR_RE.match(error))
        or any(fragment in error for fragment in retryable_fragments)
        for error in errors
    )


def _compact_text(text: str, target: int) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= target:
        return clean

    window = clean[:target + 1]
    floor = max(40, int(target * 0.55))
    sentence_cut = max(window.rfind(mark) for mark in (".", "؟", "!", "؛"))
    if sentence_cut >= floor:
        return window[:sentence_cut + 1].strip()

    word_cut = window.rfind(" ")
    if word_cut < floor:
        word_cut = target
    shortened = window[:word_cut].rstrip(" ،؛:-")
    if shortened and len(shortened) < target:
        shortened += "…"
    return shortened[:target].rstrip()


def _compact_length_fields(brief: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    compacted = dict(brief)
    for field, target in _LENGTH_TARGETS.items():
        if any(error.startswith(f"{field} exceeds ") for error in errors):
            compacted[field] = _compact_text(str(compacted.get(field, "") or ""), target)
    return compacted


def _research_with_transport_retry(original_research, topic: str) -> dict[str, Any]:
    """Retry one whole research call when an HTTP response body is truncated."""
    try:
        return original_research(topic)
    except http.client.HTTPException as exc:
        print(f"  ! topic research transport failed ({exc}) — retrying once")
        return original_research(topic)


def _retry_prompt(original_prompt: str, brief: dict[str, Any], errors: list[str],
                  final: bool = False) -> str:
    length_feedback = _retry_length_feedback(brief, errors)
    intro = (
        "\n\nالمحاولة السابقة فشلت في بوابة الجودة قبل النشر. "
        + ("هذه هي محاولة التصحيح الأخيرة. " if final else "")
        + "أعد البحث والكتابة من الصفر، ولا تكرر الأخطاء التالية:\n- "
        + "\n- ".join(errors)
    )
    if final:
        intro += (
            "\n\nمهم: لا تربط قرار جهة بجهة بصياغة متابعة أو مماثلة. اذكر قرار كل جهة "
            "بشكل مستقل ومحايد، واستخدم المصادر الأولية المطلوبة صراحةً."
        )
    if length_feedback:
        intro += "\n\nقيود الطول الدقيقة لهذه المحاولة:\n" + length_feedback
    return original_prompt + intro


def _accept_length_only(brief: dict[str, Any], errors: list[str], label: str):
    if not _only_length_errors(errors):
        return brief, errors
    compacted = _compact_length_fields(brief, errors)
    compact_errors = validate_brief(compacted)
    if not compact_errors:
        print(f"  ! {label} was editorially valid but over length — compacted safely")
        return compacted, []
    return brief, errors


def research_with_validation(bot: Any, original_research, topic: str) -> dict[str, Any]:
    """Research and strictly validate up to three drafts before publication."""
    remember_story_contexts({"stories": []})
    original_prompt = bot.SYSTEM_PROMPT

    brief = _research_with_transport_retry(original_research, topic)
    errors = validate_brief(brief)
    if not errors:
        _remember_topic_image_context(brief)
        return brief

    print("  ! topic brief failed editorial validation — retrying")
    for error in errors:
        print(f"      - {error}")

    bot.SYSTEM_PROMPT = _retry_prompt(original_prompt, brief, errors)
    try:
        brief = _research_with_transport_retry(original_research, topic)
    finally:
        bot.SYSTEM_PROMPT = original_prompt

    errors = validate_brief(brief)
    brief, errors = _accept_length_only(brief, errors, "second draft")
    if not errors:
        _remember_topic_image_context(brief)
        return brief

    if not _third_draft_worth_retrying(errors):
        raise SystemExit(
            "Topic brief failed editorial validation after retry: " + "; ".join(errors)
        )

    print("  ! second draft still failed a fixable editorial gate — final rewrite")
    for error in errors:
        print(f"      - {error}")

    bot.SYSTEM_PROMPT = _retry_prompt(original_prompt, brief, errors, final=True)
    try:
        brief = _research_with_transport_retry(original_research, topic)
    finally:
        bot.SYSTEM_PROMPT = original_prompt

    errors = validate_brief(brief)
    brief, errors = _accept_length_only(brief, errors, "final draft")
    if errors:
        raise SystemExit(
            "Topic brief failed editorial validation after final rewrite: "
            + "; ".join(errors)
        )

    _remember_topic_image_context(brief)
    return brief


def _make_choose_topic(bot: Any):
    """Build a selector that enforces full cooldown and category diversity."""

    def choose_topic(exclude=()):
        catalog = bot.load_topics()
        if not catalog:
            return ""

        used = bot.load_used()
        exclude_set = set(exclude)
        blocked = {entry["topic"] for entry in used} | exclude_set

        forced_pool = None
        if bot.FORCE_SEASON:
            want = bot.FORCE_SEASON.lower()
            matches = [
                season for season in bot.load_seasons()
                if want in season["name"].lower() or season["name"].lower() in want
            ]
            if matches:
                forced_pool = {topic for season in matches for topic in season["topics"]}
                print(f"    forced season(s): {'، '.join(s['name'] for s in matches)}")
            else:
                print(f"  ! no season matching {bot.FORCE_SEASON!r}")

        print("    reading yesterday's headlines...")
        try:
            items = bot.fetch_headlines()
        except Exception as exc:
            print(f"  ! couldn't fetch headlines ({exc})")
            items = []

        scored = bot.score_topics(items, blocked, set(), forced_pool)
        if not scored:
            print("  ! no eligible topics outside the full cooldown window")
            return ""

        performance = load_performance(PERFORMANCE_FILE)
        shortlist = prepare_shortlist(bot, scored, performance, limit=8)
        bot.report_shortlist(shortlist, datetime.now())

        if not items or not bot.ANTHROPIC_API_KEY:
            print("    no headlines to judge by — taking the strongest balanced candidate")
            return shortlist[0]["topic"]

        listing = "\n".join(
            f"{index}. {row['topic']}  [الفئة: {row.get('category', 'عام')}؛ "
            f"{'، '.join(row.get('reasons', []))}]"
            for index, row in enumerate(shortlist)
        )
        headlines = "\n".join(f"- {item['title']}" for item in items[:50])
        payload = {
            "model": bot.SELECT_MODEL,
            "max_tokens": 500,
            "system": bot.SELECT_PROMPT,
            "messages": [{
                "role": "user",
                "content": (
                    f"المواضيع المرشحة:\n{listing}\n\n"
                    f"عناوين الأمس:\n{headlines}\n\n"
                    "ملاحظة: المواضيع المنشورة خلال فترة التهدئة أزيلت مسبقاً."
                ),
            }],
        }
        request = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={
                "content-type": "application/json",
                "x-api-key": bot.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                data = json.loads(response.read())
            text = "".join(
                block.get("text", "") for block in data.get("content", [])
                if block.get("type") == "text"
            )
            start, end = text.find("{"), text.rfind("}")
            choice = json.loads(text[start:end + 1])
            topic = shortlist[int(choice["index"])]["topic"]
            print(f"    chose: {topic}")
            print(f"    why:   {choice.get('why', '')}")
            return topic
        except Exception as exc:
            print(f"  ! selection call failed ({exc}) — taking balanced top score")
            return shortlist[0]["topic"]

    return choose_topic


def install(bot: Any) -> None:
    """Install Saudi Snapchat audience rules into an imported topic_bot module."""
    bot.HARD_COOLDOWN_DAYS = bot.COOLDOWN_DAYS
    bot.KICKER = os.getenv("KICKER", "معلومة تهمك")
    bot.TOPIC_MODEL = bot.CLAUDE_MODEL
    bot.SYSTEM_PROMPT = enhance_prompt(bot.SYSTEM_PROMPT)
    _install_topic_image_policy(bot)

    selector_prompt = getattr(bot, "SELECT_PROMPT", "")
    if selector_prompt:
        bot.SELECT_PROMPT = selector_prompt + (
            "\n\nتذكّر أن المنصة سناب شات والجمهور سعودي عربي. عند تقارب الأهمية، "
            "اختر الموضوع الذي يملك أهمية واضحة للحياة في السعودية أو مفاجأة موثقة أو "
            "رقماً أو زاوية تشرح لماذا يستحق الانتباه الآن. لا ترجّح موضوعاً لأنه يسمح "
            "بإعطاء نصائح أو خطوات؛ Topic Brief يبرز الموضوع ولا يوجّه المتابع لما يفعله. "
            "وتجنب المواضيع العامة التي تبدو كعنوان تقرير."
        )

    original_research = bot.research
    bot.load_topics = lambda: load_topics_with_categories(bot.TOPICS_FILE)
    bot.choose_topic = _make_choose_topic(bot)
    bot.research = lambda topic: research_with_validation(bot, original_research, topic)


def main() -> None:
    import topic_bot

    install(topic_bot)
    topic_bot.main()


if __name__ == "__main__":
    main()
