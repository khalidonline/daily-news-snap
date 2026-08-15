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
TOPIC_MODEL = os.getenv("TOPIC_MODEL", "claude-opus-5")
MAX_SEARCHES = int(os.getenv("MAX_SEARCHES", "6"))
POINTS = int(os.getenv("POINTS", "3"))


# --------------------------------------------------------------------------
# Research
# --------------------------------------------------------------------------

SYSTEM_PROMPT = """أنت محرر اقتصادي في موقع "أرقام" تكتب موجزاً يُنشر على سناب شات.

سيعطيك المستخدم موضوعاً. ابحث في الإنترنت، ثم اكتب موجزاً بأسلوب أرقام: دقيق، \
موثّق، خبري، بلا مبالغة — يفهمه قارئ ذكي لا يعرف الموضوع مسبقاً.

الشكل المطلوب:
- title: عنوان لا يتجاوز ٤٥ حرفاً. يقول ما حدث، لا اسم الموضوع فقط. يجوز أن \
يتضمن رقماً محورياً مع وحدته.
- lead: جملة واحدة، لا تتجاوز ١٣٠ حرفاً، تلخّص الخلاصة الأهم. لو لم يقرأ \
القارئ سوى هذه الجملة، ماذا يجب أن يعرف؟
- points: {n} نقاط. كل نقطة:
  - heading: ٣ إلى ٥ كلمات تقول فكرة، لا عنواناً محايداً.
    ✗ "تراجع بعد ذروة الصيف"   ✓ "الهدوء الصيفي لم يدم"
  - text: جملتان أو ثلاث، حتى ٢٢٠ حرفاً. الجملة الأولى تقول ماذا حدث، \
والثانية تقول لماذا يهم أو ما الذي يترتب عليه.
- caption: نص المنشور المرافق، لا يتجاوز ١٢٠ حرفاً
- sources: أسماء المصادر (٢ إلى ٤). إن كان المصدر أجنبياً فاكتبه بالعربية.

قواعد الأسلوب — اكتب بأسلوب موقع "أرقام" الاقتصادي:
- ابدأ الجملة بالجهة صاحبة الخبر: "أعلنت أرامكو"، "رفع صندوق النقد توقعاته".
- انسب كل رقم لمصدره داخل الجملة نفسها: "وفق بيانات درويري"، "بحسب بيان الشركة".
- جمل خبرية مكتملة ومترابطة. لا عبارات مبتورة ولا أسلوب برقيات.
- استخدم المصطلح الاقتصادي الدقيق كما هو، واشرحه بثلاث كلمات إن كان غير شائع.
- ممنوع الصفات الترويجية: هائل، مذهل، ضخم، تاريخي، غير مسبوق.
- ممنوع لغة الإثارة والتعجب. الخبر يقنع بدقته لا بنبرته.
- لا تبدأ أكثر من نقطة واحدة برقم. الأرقام تدعم الفكرة ولا تحل محلها.
- كل نقطة تضيف زاوية جديدة. لا تكرر الفكرة بأرقام مختلفة.
- النقطة الأخيرة تذكر الأثر المتوقع على السوق أو المستثمر أو المستورد.
- لا تستخدم مصطلحاً مهنياً دون شرحه في نفس الجملة.

قواعد الأرقام:
- كل رقم تليه وحدته مباشرة: "4,547 نقطة" أو "9,400 دولار للحاوية" أو "14%".
- عند ذكر مؤشر لأول مرة عرّفه في ٣ كلمات: "مؤشر درويري لأسعار الحاويات".
- كل رقم يحتاج تاريخاً أو فترة: "في 23 يوليو" أو "خلال أغسطس".
- إذا لم تعرف وحدة الرقم أو تاريخه بيقين، احذفه.
- اكتب النطاقات بالكلمات: "من 8700 إلى 9400 دولار" وليس "8700-9400".
- لا تستخدم الشرطة بين رقمين أو اسمين (اكتب "شنغهاي إلى نيويورك").

قواعد الدقة:
- اعتمد فقط على ما وجدته في البحث. لا تستخرج أرقاماً من ذاكرتك.
- إذا تضاربت المعلومات، قل ذلك واذكر التقديرين.
- إذا لم تجد ما يكفي، اجعل title هو "لا توجد معلومات كافية" واشرح السبب.

قبل أن تجيب، اسأل نفسك: هل يمكن نشر هذا النص في "أرقام" كما هو؟ هل كل رقم \
منسوب لمصدره وله وحدة وتاريخ؟ هل خلا النص من الصفات الترويجية؟ إن كان الجواب \
لا، أعد الكتابة.

أجب بصيغة JSON فقط، بدون markdown وبدون مقدمة:
{{"title": "...", "lead": "...", "points": [{{"heading": "...", "text": "..."}}], \
"caption": "...", "sources": ["...", "..."]}}"""


UNIT_WORDS = ("نقطة", "نقاط", "دولار", "دولاراً", "ريال", "ريالاً", "يورو",
              "مليون", "مليار", "ألف", "برميل", "برميلاً", "طن", "طناً", "كم",
              "متر", "يوم", "يوماً", "أيام", "شهر", "أشهر", "سنة", "سنوات",
              "أسبوع", "أسابيع", "ساعة", "حاوية", "قدماً", "بالمئة", "درجة")

MONTH_WORDS = ("يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو",
               "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر")


def warn_about_bare_numbers(brief):
    """Flag figures with neither a unit nor a date right after them —
    the reader can't tell whether 4,547 is dollars, points or something else."""
    for point in brief.get("points", []):
        text = point.get("text", "")
        for match in re.finditer(r"\d[\d,\.]*", text):
            tail = text[match.end():]
            if tail.startswith("%"):
                continue
            next_word = tail.strip().split(" ")[0].strip("،.:؛)") if tail.strip() else ""
            if next_word in UNIT_WORDS or next_word in MONTH_WORDS:
                continue
            print(f"  ! bare number {match.group()!r} in "
                  f"{point.get('heading')!r} — followed by {next_word!r}, "
                  f"no unit given")


def research(topic):
    if not ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY is not set")

    messages = [{"role": "user", "content": f"الموضوع: {topic}"}]
    searches = 0

    # Claude may return stop_reason="pause_turn" mid-research; continue it.
    for _ in range(4):
        payload = {
            "model": TOPIC_MODEL,
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
    f_title = load_font(58, bold=True)
    f_lead = load_font(38)
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
        y += 72

    lead = brief.get("lead", "").strip()
    if lead:
        y += 28
        lead_lines = _wrap(draw, lead, f_lead, max_w - 24, kw)
        bar_top = y - 6
        for line in lead_lines:
            rtl((right - 24, y), line, f_lead, (255, 236, 170))
            y += 54
        draw.rectangle([right - 6, bar_top, right, y - 16], fill=ACCENT)

    y += 56
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
    warn_about_bare_numbers(brief)
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
