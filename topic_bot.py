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

قواعد اللهجة والمصطلح — اكتب بلسان سعودي رسمي:
- قل "المملكة" لا "السعودية" في كل مرة، و"المواطنين" و"المقيمين" حين يلزم.
- استخدم الأسماء الرسمية للجهات: "المركز الوطني للنخيل والتمور"، "الهيئة العامة \
للإحصاء"، "وكالة الأنباء السعودية (واس)".
- استخدم أسماء المناطق كما تُستخدم محلياً: القصيم، المنطقة الشرقية، عسير، جازان.
- العملة ريال، واذكر "مليار ريال" لا "مليار دولار" إن كان المصدر بالريال.
- تجنّب التعابير المصرية أو الشامية أو المترجمة حرفياً عن الإنجليزية.
- التواريخ ميلادية بالأشهر العربية المعروفة في المملكة: يناير، فبراير، مارس...
- نبرة رصينة قريبة من نشرات "أرقام" و"واس": خبرية، بلا حماس، بلا مبالغة.

ممنوع منعاً باتاً:
- أي وسوم أو أقواس مراجع داخل النص مثل <cite> أو [1] أو (المصدر: ...).
- النص يجب أن يكون نصاً عربياً نظيفاً فقط. ضع أسماء المصادر في حقل sources وحده.

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


CITE_RE = re.compile(r"</?cite[^>]*>", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]{1,80}>")


def strip_markup(value):
    """Remove citation tags and stray markup the model sometimes emits."""
    if isinstance(value, str):
        cleaned = CITE_RE.sub("", value)
        cleaned = TAG_RE.sub("", cleaned)
        return re.sub(r"\s{2,}", " ", cleaned).strip()
    if isinstance(value, list):
        return [strip_markup(v) for v in value]
    if isinstance(value, dict):
        return {k: strip_markup(v) for k, v in value.items()}
    return value


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
        return strip_markup(json.loads(text[start:end + 1]))

    raise SystemExit("Research didn't finish after 4 continuations")


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------

def _build_layout(draw, brief, scale, max_w, kw):
    """Measure the whole card before drawing any of it.
    Returns (blocks, total_height) where each block carries its own font."""
    f_title = load_font(int(58 * scale), bold=True)
    f_lead = load_font(int(38 * scale))
    f_head = load_font(int(40 * scale), bold=True)
    f_body = load_font(int(34 * scale))

    lh_title, lh_lead = int(72 * scale), int(54 * scale)
    lh_head, lh_body = int(50 * scale), int(48 * scale)

    blocks, height = [], 0

    def add(kind, text, font, line_h, fill, indent, first=False):
        nonlocal height
        blocks.append({"kind": kind, "text": text, "font": font, "lh": line_h,
                       "fill": fill, "indent": indent, "first": first})
        height += line_h

    for line in _wrap(draw, brief["title"], f_title, max_w, kw):
        add("title", line, f_title, lh_title, TEXT, 0)

    lead = brief.get("lead", "").strip()
    if lead:
        add("gap", "", None, int(28 * scale), None, 0)
        for line in _wrap(draw, lead, f_lead, max_w - 24, kw):
            add("lead", line, f_lead, lh_lead, (255, 236, 170), 24)

    for i, point in enumerate(brief.get("points", [])):
        add("gap", "", None, int((56 if i == 0 else 46) * scale), None, 0)

        first = True
        for line in _wrap(draw, point["heading"], f_head, max_w - 44, kw):
            add("head", line, f_head, lh_head, ACCENT, 44, first)
            first = False

        add("gap", "", None, int(8 * scale), None, 0)
        for line in _wrap(draw, point["text"], f_body, max_w - 44, kw):
            add("body", line, f_body, lh_body, (206, 212, 228), 44)

    return blocks, height


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

    TOP, BOTTOM = 330, H - 250
    available = BOTTOM - TOP

    # Shrink to fit. Only drop a point if even the smallest size overflows.
    points = list(brief.get("points", []))[:POINTS]
    scale, blocks = 1.0, None
    while blocks is None:
        trial = dict(brief, points=points)
        for candidate in (1.0, 0.94, 0.88, 0.82, 0.76, 0.70):
            trial_blocks, height = _build_layout(draw, trial, candidate, max_w, kw)
            if height <= available:
                scale, blocks = candidate, trial_blocks
                break
        if blocks is None:
            if len(points) > 2:
                points = points[:-1]
                print(f"  ! content too long — trimmed to {len(points)} points")
            else:
                print("  ! content overflows even at minimum size")
                scale, blocks = 0.70, trial_blocks
    if scale < 1.0:
        print(f"  layout scaled to {int(scale * 100)}% to fit")

    def rtl(xy, text, font, fill, anchor="ra"):
        shaped, k = ar(text)
        draw.text(xy, shaped, font=font, fill=fill, anchor=anchor, **k)

    draw.rectangle([right - 110, 200, right, 210], fill=ACCENT)
    rtl((right, 246), f"تحليل: {arabic_date()}",
        load_font(int(32 * scale), bold=True), ACCENT)

    y = TOP
    lead_top = lead_bottom = None
    for block in blocks:
        if block["kind"] == "gap":
            y += block["lh"]
            continue
        if block["kind"] == "lead":
            if lead_top is None:
                lead_top = y - 6
            lead_bottom = y + block["lh"] - 14
        if block["kind"] == "head" and block["first"]:
            r = max(5, int(7 * scale))
            draw.ellipse([right - 18, y + int(16 * scale),
                          right - 18 + 2 * r, y + int(16 * scale) + 2 * r],
                         fill=ACCENT)
        rtl((right - block["indent"], y), block["text"], block["font"], block["fill"])
        y += block["lh"]

    if lead_top is not None:
        draw.rectangle([right - 6, lead_top, right, lead_bottom], fill=ACCENT)

    f_foot = load_font(28)
    draw.line([(margin, H - 200), (right, H - 200)], fill=(58, 66, 90), width=2)
    sources = "، ".join(brief.get("sources", [])[:4])
    rtl((right, H - 165), f"المصادر: {sources}", f_foot, MUTED)
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
