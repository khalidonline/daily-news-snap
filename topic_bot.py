#!/usr/bin/env python3
"""
موضوع اليوم — بحث وتحليل -> سناب شات
Topic research mode.

You give it a topic. Claude searches the web (server-side web_search tool),
analyses what it finds, and returns a short Arabic brief. Rendered as one
card and posted the same way as the news bot.

    TOPIC="مستقبل الطاقة المتجددة في السعودية" python topic_bot.py

Reuses the fetch/post/render plumbing from news_bot.py.
"""

import json
import os
import re
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

from news_bot import (
    ANTHROPIC_API_KEY, CLAUDE_MODEL, DRY_RUN, MEDIA_MODE, OUT_DIR,
    W, H, BG_TOP, BG_BOTTOM, ACCENT, TEXT, MUTED, AR_DIGITS,
    ar, arabic_date, load_font, _wrap,
    publish_via_github, upload_media, post_story,
)

TOPIC = os.getenv("TOPIC", "").strip()
MAX_SEARCHES = int(os.getenv("MAX_SEARCHES", "6"))
POINTS = int(os.getenv("POINTS", "4"))


# --------------------------------------------------------------------------
# Research
# --------------------------------------------------------------------------

SYSTEM_PROMPT = """أنت محلل تكتب موجزاً عربياً قصيراً يُنشر على سناب شات.

سيعطيك المستخدم موضوعاً. ابحث في الإنترنت عن أحدث المعلومات عنه، ثم حلّلها \
واكتب موجزاً مركزاً.

المطلوب:
- title: عنوان الموضوع، لا يتجاوز ٤٥ حرفاً
- points: {n} نقاط. كل نقطة فيها:
  - heading: ٣ إلى ٥ كلمات
  - text: جملة أو جملتان، لا تتجاوز ١٦٠ حرفاً
- caption: نص المنشور المرافق، لا يتجاوز ١٢٠ حرفاً
- sources: أسماء المصادر التي اعتمدت عليها (٢ إلى ٤ أسماء مختصرة)

قواعد صارمة:
- اعتمد فقط على ما وجدته في البحث. لا تستنتج أرقاماً ولا تواريخ من ذاكرتك.
- إذا كانت المعلومات متضاربة أو غير مؤكدة، قل ذلك صراحة في النقطة.
- إذا لم تجد معلومات كافية، اجعل title هو "لا توجد معلومات كافية" واشرح السبب \
في أول نقطة.
- لغة عربية فصحى بسيطة، بدون مبالغة أو لغة تسويقية.

أجب بصيغة JSON فقط، بدون markdown وبدون أي مقدمة:
{{"title": "...", "points": [{{"heading": "...", "text": "..."}}], \
"caption": "...", "sources": ["...", "..."]}}"""


def research(topic):
    if not ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY is not set")

    messages = [{"role": "user", "content": f"الموضوع: {topic}"}]
    searches = 0

    # Claude may return stop_reason="pause_turn" mid-research; continue it.
    for _ in range(4):
        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": 4000,
            "system": SYSTEM_PROMPT.format(n=POINTS),
            "messages": messages,
            "tools": [{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": MAX_SEARCHES,
            }],
        }

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={
                "content-type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"Claude API {exc.code}: {exc.read().decode()[:500]}")

        content = data.get("content", [])
        searches += sum(1 for b in content if b.get("type") == "server_tool_use")

        if data.get("stop_reason") == "pause_turn":
            messages.append({"role": "assistant", "content": content})
            continue

        if data.get("stop_reason") == "max_tokens":
            raise SystemExit("Reply truncated — raise max_tokens")

        text = "".join(b.get("text", "") for b in content
                       if b.get("type") == "text").strip()
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()

        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise SystemExit(f"No JSON in reply: {text[:300]}")

        print(f"    {searches} web searches used")
        return json.loads(text[start:end + 1])

    raise SystemExit("Research didn't finish after 4 continuations")


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------

def render_topic(brief, out_path):
    img = Image.new("RGB", (W, H), BG_TOP)
    draw = ImageDraw.Draw(img)

    for y in range(H):
        t = y / H
        draw.line([(0, y), (W, y)],
                  fill=tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)))

    margin = 80
    right = W - margin
    max_w = W - 2 * margin
    _, kw = ar("م")

    f_kicker = load_font(32, bold=True)
    f_title = load_font(60, bold=True)
    f_head = load_font(40, bold=True)
    f_body = load_font(34)
    f_foot = load_font(28)

    def rtl(xy, text, font, fill, anchor="ra"):
        shaped, k = ar(text)
        draw.text(xy, shaped, font=font, fill=fill, anchor=anchor, **k)

    draw.rectangle([right - 110, 200, right, 210], fill=ACCENT)
    rtl((right, 246), f"تحليل: {arabic_date()}", f_kicker, ACCENT)

    y = 320
    for line in _wrap(draw, brief["title"], f_title, max_w, kw):
        rtl((right, y), line, f_title, TEXT)
        y += 74

    y += 60
    for point in brief["points"][:POINTS]:
        draw.ellipse([right - 16, y + 14, right - 4, y + 26], fill=ACCENT)
        head_right = right - 40

        for line in _wrap(draw, point["heading"], f_head, max_w - 40, kw):
            rtl((head_right, y), line, f_head, ACCENT)
            y += 50

        y += 6
        for line in _wrap(draw, point["text"], f_body, max_w - 40, kw):
            rtl((head_right, y), line, f_body, (206, 212, 228))
            y += 48
        y += 40

    draw.line([(margin, H - 200), (right, H - 200)], fill=(58, 66, 90), width=2)
    sources = "، ".join(brief.get("sources", [])[:4])
    rtl((right, H - 165), f"المصادر: {sources}"[:80], f_foot, MUTED)
    rtl((right, H - 120), "بحث آلي: راجع المصادر", f_foot, ACCENT)

    img.save(out_path, "PNG", optimize=True)
    return out_path


# --------------------------------------------------------------------------

def main():
    if not TOPIC:
        raise SystemExit("TOPIC is not set — pass a topic to research")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"1/3 researching: {TOPIC}")
    brief = research(TOPIC)
    print(f"    {brief['title']}")
    for p in brief["points"]:
        print(f"    • {p['heading']}")

    print("2/3 rendering card...")
    slug = re.sub(r"[^\w]+", "-", TOPIC, flags=re.UNICODE)[:40].strip("-")
    stamp = datetime.now().strftime("%Y-%m-%d")
    card = render_topic(brief, OUT_DIR / f"{stamp}-{slug}.png")

    if DRY_RUN:
        print(f"3/3 DRY_RUN — nothing posted. Card at {Path(card).resolve()}")
        return

    print("3/3 posting to Snapchat...")
    url = publish_via_github(card) if MEDIA_MODE == "github" else upload_media(card)
    print(f"    media: {url}")
    print("   ", post_story(brief.get("caption", TOPIC), [url]))


if __name__ == "__main__":
    main()
