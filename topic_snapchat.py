#!/usr/bin/env python3
"""Saudi Snapchat editorial runtime for topic_bot.

This keeps the mature research/render/post plumbing in topic_bot.py intact while
installing stricter audience selection and publish-time editorial safeguards.
"""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from topic_editorial import (
    balanced_shortlist,
    enhance_prompt,
    load_performance,
    load_topics_with_categories,
    performance_adjustment,
    validate_brief,
)

PERFORMANCE_FILE = Path(os.getenv("TOPIC_PERFORMANCE_FILE", "state/topic_performance.json"))


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


def research_with_validation(bot: Any, original_research, topic: str) -> dict[str, Any]:
    """Research, validate, retry once with exact feedback, then block bad output."""
    brief = original_research(topic)
    errors = validate_brief(brief)
    if not errors:
        return brief

    print("  ! topic brief failed editorial validation — retrying once")
    for error in errors:
        print(f"      - {error}")

    original_prompt = bot.SYSTEM_PROMPT
    bot.SYSTEM_PROMPT = original_prompt + (
        "\n\nالمحاولة السابقة فشلت في بوابة الجودة قبل النشر. أعد البحث والكتابة من الصفر، "
        "ولا تكرر الأخطاء التالية:\n- " + "\n- ".join(errors)
    )
    try:
        brief = original_research(topic)
    finally:
        bot.SYSTEM_PROMPT = original_prompt

    errors = validate_brief(brief)
    if errors:
        raise SystemExit(
            "Topic brief failed editorial validation after retry: " + "; ".join(errors)
        )
    return brief


def _make_choose_topic(bot: Any):
    """Build a selector that enforces full cooldown and category diversity."""

    def choose_topic(exclude=()):
        catalog = bot.load_topics()
        if not catalog:
            return ""

        used = bot.load_used()
        exclude_set = set(exclude)
        # load_used() is already trimmed to COOLDOWN_DAYS, so every entry here is
        # a hard exact-topic block. A new angle belongs as a new topic string.
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

        # Recent is empty because exact repeats are now blocked for the full window.
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

    selector_prompt = getattr(bot, "SELECT_PROMPT", "")
    if selector_prompt:
        bot.SELECT_PROMPT = selector_prompt + (
            "\n\nتذكّر أن المنصة سناب شات والجمهور سعودي عربي. عند تقارب الأهمية، "
            "اختر الموضوع الذي يملك فائدة شخصية واضحة أو مفاجأة موثقة أو رقماً يمكن "
            "للمتابع استخدامه، وتجنب المواضيع العامة التي تبدو كعنوان تقرير."
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
