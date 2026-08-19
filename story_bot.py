#!/usr/bin/env python3
"""
بوت القصص — قصة واحدة في أربع لقطات، تُنشر كسلسلة على سناب شات.

يختار قصة من stories.txt، يبحث عنها، ثم يبني ٤ لقطات:
  ١) المشهد الأول — من أين بدأت
  ٢) المنعطف — اللحظة التي غيّرت كل شيء
  ٣) الرقم — حجم ما صارت إليه
  ٤) الخلاصة — ماذا يعني هذا اليوم

    python story_bot.py
    python story_bot.py "قصة NVIDIA"
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

try:
    from news_bot import (
        ANTHROPIC_API_KEY, DRY_RUN, OUT_DIR, CARDS_DIR, W, H,
        BG_TOP, TEXT, BODY, ACCENT, MUTED, BRAND_INK, RULE,
        ar, load_font, _wrap, _rounded, _clean_model_id,
        commit_and_push, publish_via_github, post_story, post_ok,
        describe_failure, notify, ksa_stamp, quota_ok, quota_bump,
        POST_ENABLED, POST_PROVIDER, MEDIA_MODE, upload_media,
        fetch_local_photo, fetch_spa_photo, fetch_openverse_photo,
        fetch_generated_photo, IMAGE_SOURCE,
    )
except ImportError as exc:
    raise SystemExit(
        f"news_bot.py is missing something story_bot needs ({exc}).\n"
        "Upload the latest news_bot.py alongside this file."
    )

STORIES_FILE = Path(os.getenv("STORIES_FILE", "stories.txt"))
USED_FILE = Path("state/stories_used.json")
STORY = os.getenv("STORY", "").strip()
STORY_MODEL = _clean_model_id(os.getenv("STORY_MODEL"), "claude-opus-5")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "").strip() or "16000")
MAX_SEARCHES = int(os.getenv("MAX_SEARCHES", "").strip() or "6")
BRAND = os.getenv("BRAND", "ملخص تنفيذي - قصة")
COOLDOWN_DAYS = int(os.getenv("STORY_COOLDOWN_DAYS", "").strip() or "60")

SYSTEM_PROMPT = """أنت تكتب قصة قصيرة تُنشر على سناب شات لجمهور سعودي، في أربع لقطات.

القصة ليست خبراً ولا مقالاً. لها بداية ومنعطف ورقم ونهاية تترك أثراً.
ابحث في الإنترنت أولاً، ثم اكتب. كل ما تكتبه يجب أن يكون صحيحاً وموثقاً.

اللقطات الأربع:
1. البداية — أين ومتى بدأت، بتفصيل ملموس يعلق في الذهن (مكان، مبلغ، عمر).
2. المنعطف — اللحظة أو القرار الذي غيّر المسار. هنا المفاجأة.
3. الرقم — حجم ما صارت إليه اليوم، برقم واحد كبير ووحدته ومصدره.
4. الخلاصة — ماذا يعني هذا للقارئ الآن. ليست عبرة وعظية، بل ملاحظة ذكية.

قواعد الكتابة:
- عربية بسيطة قريبة من كلام الناس، لا لغة كتب.
- كل لقطة فكرة واحدة فقط. جمل قصيرة.
- كل رقم بوحدته وتاريخه ومصدره. لا تخمّن ولا تقرّب بلا داعٍ.
- أسماء الشركات والأشخاص الأجانب بالإنجليزية: Apple، Steve Jobs، NVIDIA.
- الأرقام لاتينية: 1976 لا ١٩٧٦.
- تجنّب اللغة الرسمية والوعظ. لا "وهكذا نتعلم أن".
- إن لم تجد مصادر موثوقة للقصة، أعد title = "لا توجد مصادر كافية" واشرح.
- عنوان القصة في stories.txt هو اقتراح لا حقيقة. كثير من قصص المشاهير
  متداولة بصيغة مبالغ فيها أو غير مؤكدة (منديل، ورقة جامعية، رفض عرض).
  تحقق من الرواية أولاً: إن كانت مؤكدة فاروِها، وإن كانت مختلَفاً عليها فقل ذلك
  صراحة في اللقطة نفسها ("الرواية المتداولة... لكن المصادر الموثوقة تقول").
  وإن ثبت أنها غير صحيحة، اروِ القصة الحقيقية بدل الشائعة.
- للأشخاص الأحياء: التزم بالوقائع الموثقة فقط. لا تنسب لهم أقوالاً ولا نوايا،
  ولا تتحدث عن ثرواتهم أو حياتهم الخاصة إلا بما نشرته مصادر رسمية.

لكل لقطة:
- heading: سطر قصير جداً (حتى ٣٠ حرفاً) — يظهر كبيراً
- text: جملة أو جملتان (حتى ١٦٠ حرفاً)
- image_keywords: من كلمتين إلى أربع كلمات إنجليزية بسيطة للبحث عن صورة
  حقيقية تخص القصة. اسم الشركة أو الشخص أو المنتج أو المكان — لا وصف مشهد.
  الصور الحقيقية من الأرشيف أفضل من الصور المولّدة، فاختر ما يُرجّح وجوده.
  ✓ ["Steve Jobs", "Macintosh computer", "Apple logo", "Apple headquarters"]
  ✗ ["a garage in California in 1976 with two young men assembling boards"]
  نوّع بين اللقطات: شخص، منتج، مبنى، شعار — أي صورة تخص القصة تفي بالغرض.

واكتب أيضاً:
- title: عنوان القصة كاملاً (حتى ٤٥ حرفاً) — يظهر في اللقطة الأولى
- caption: نص المنشور المرافق (حتى ١٢٠ حرفاً)
- sources: من ٢ إلى ٤ مصادر
- image_queries: ثلاث عبارات إنجليزية لصورة اللقطة الأولى، مشهد ملموس
  بلا أشخاص ولا شعارات ولا نصوص
- image_queries_ar: ثلاث كلمات عربية مفردة للبحث في أرشيف الصور السعودي
- image_prompt: وصف إنجليزي لمشهد واحد متماسك، بلا نصوص ولا وجوه

أجب بصيغة JSON فقط:
{"title": "...", "caption": "...", \
"frames": [{"heading": "...", "text": "...", \
"image_keywords": ["...", "...", "..."]}], \
"sources": ["..."], "image_queries": ["..."], "image_queries_ar": ["..."], \
"image_prompt": "..."}"""


def load_stories():
    try:
        lines = STORIES_FILE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        print(f"  ! {STORIES_FILE} not found")
        return []
    return [ln.strip() for ln in lines
            if ln.strip() and not ln.strip().startswith("#")]


def load_used():
    try:
        data = json.loads(USED_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    cutoff = (datetime.now() - timedelta(days=COOLDOWN_DAYS)).isoformat()
    return [e for e in data if e.get("at", "") >= cutoff]


def save_used(previous, story):
    USED_FILE.parent.mkdir(parents=True, exist_ok=True)
    entries = previous + [{"story": story, "at": datetime.now().isoformat()}]
    USED_FILE.write_text(json.dumps(entries, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    return USED_FILE


def choose_story():
    stories = load_stories()
    if not stories:
        return ""
    used = {e["story"] for e in load_used()}
    fresh = [s for s in stories if s not in used]
    if not fresh:
        print("    every story used recently — starting the cycle again")
        fresh = stories
    pick = fresh[datetime.now().toordinal() % len(fresh)]
    print(f"    {len(fresh)} of {len(stories)} stories available")
    return pick


def research(story):
    if not ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY is not set")

    messages = [{"role": "user", "content": f"القصة: {story}"}]
    searches = 0

    for _ in range(6):
        payload = {
            "model": STORY_MODEL,
            "max_tokens": MAX_TOKENS,
            "system": SYSTEM_PROMPT,
            "messages": messages,
            "tools": [{"type": "web_search_20250305", "name": "web_search",
                       "max_uses": MAX_SEARCHES}],
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={"content-type": "application/json",
                     "x-api-key": ANTHROPIC_API_KEY,
                     "anthropic-version": "2023-06-01"},
        )
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"Claude API {exc.code}: {exc.read().decode()[:400]}")

        searches += sum(1 for b in data.get("content", [])
                        if b.get("type") == "server_tool_use")

        if data.get("stop_reason") == "pause_turn":
            messages.append({"role": "assistant", "content": data["content"]})
            continue

        text = "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text")
        print(f"    {searches} web searches used")
        start, end = text.find("{"), text.rfind("}")
        if start == -1:
            raise SystemExit(f"No JSON in reply: {text[:300]}")
        return json.loads(text[start:end + 1])

    raise SystemExit("Gave up after too many continuations")


def render_frame(path, kicker, counter, big, big_size, sub=None,
                 sub_colour=None, photo=None, footer=None):
    img = Image.new("RGB", (W, H), BG_TOP)
    draw = ImageDraw.Draw(img)
    margin, centre, right = 96, W // 2, W - 96
    max_w = W - 2 * margin
    _, kw = ar("م")

    def mid(y, text, font, fill):
        shaped, k = ar(text)
        draw.text((centre, y), shaped, font=font, fill=fill, anchor="ma", **k)

    draw.rectangle([right - 110, 170, right, 180], fill=BRAND_INK)
    shaped, k = ar(kicker)
    draw.text((right, 216), shaped, font=load_font(32, bold=True),
              fill=BRAND_INK, anchor="ra", **k)
    shaped, k = ar(counter)
    draw.text((margin, 216), shaped, font=load_font(28), fill=MUTED,
              anchor="la", **k)

    y = 420
    if photo:
        try:
            pic = Image.open(photo).convert("RGB")
            box_w, box_h = max_w, int(max_w * 0.72)
            pw, ph = pic.size
            if pw / ph > box_w / box_h:
                new_w = int(ph * box_w / box_h)
                pic = pic.crop(((pw - new_w) // 2, 0,
                                (pw - new_w) // 2 + new_w, ph))
            else:
                pic = pic.crop((0, 0, pw, int(pw * box_h / box_w)))
            pic = pic.resize((box_w, box_h), Image.LANCZOS)
            rounded = _rounded(pic, 36)
            img.paste(rounded, (margin, y), rounded)
            y += box_h + 80
        except Exception as exc:
            print(f"  ! couldn't place photo: {exc}")

    size = big_size
    while size > 44:
        f_big = load_font(size, bold=True)
        lines = _wrap(draw, big, f_big, max_w, kw)
        if len(lines) <= (2 if photo else 3):
            break
        size -= 8
    if not photo:
        y = (H - len(lines) * int(size * 1.25)) // 2 - 140
    for line in lines:
        mid(y, line, f_big, TEXT)
        y += int(size * 1.25)

    if sub:
        y += 46
        f_sub = load_font(42, bold=sub_colour == ACCENT)
        for line in _wrap(draw, sub, f_sub, max_w, kw):
            mid(y, line, f_sub, sub_colour or BODY)
            y += 60

    if footer:
        draw.line([(centre - 130, H - 206), (centre + 130, H - 206)],
                  fill=RULE, width=2)
        mid(H - 160, footer, load_font(26), MUTED)

    img.save(path, "PNG", optimize=True)
    return path


def build_frames(brief, stamp, photos):
    frames = brief.get("frames", [])[:4]
    if len(frames) < 4:
        raise SystemExit(f"expected 4 frames, got {len(frames)}")

    sources = "، ".join(brief.get("sources", [])[:3])
    paths = []

    # 1 — the opening, with the photo
    paths.append(render_frame(
        OUT_DIR / f"{stamp}-story-1.png", BRAND, "1 / 4",
        brief["title"], 60, sub=frames[0]["text"], photo=photos[0]))

    # 2 — the turning point
    paths.append(render_frame(
        OUT_DIR / f"{stamp}-story-2.png", BRAND, "2 / 4",
        frames[1]["heading"], 60, sub=frames[1]["text"], photo=photos[1]))

    # 3 — the number, as large as it will go
    paths.append(render_frame(
        OUT_DIR / f"{stamp}-story-3.png", BRAND, "3 / 4",
        frames[2]["heading"], 96, sub=frames[2]["text"], photo=photos[2]))

    # 4 — what it means, plus the sources
    paths.append(render_frame(
        OUT_DIR / f"{stamp}-story-4.png", BRAND, "4 / 4",
        frames[3]["heading"], 60, sub=frames[3]["text"], sub_colour=ACCENT,
        photo=photos[3], footer=f"المصدر: {sources}" if sources else None))

    return [str(p) for p in paths]


def find_photo(spec, out_path):
    """One photo for one frame, searched by subject.

    Any real photograph about the story serves — the person, the product, the
    building, the logo. A single keyword match is enough here, because we are
    searching for a subject rather than matching a described scene.
    """
    keywords = [k for k in (spec.get("image_keywords") or []) if k]
    if not keywords:
        keywords = spec.get("image_queries") or []

    photo, _ = fetch_local_photo([], keywords, out_path)

    # try each keyword on its own — "Steve Jobs" finds more than a long phrase
    for keyword in keywords:
        if photo:
            break
        photo, _ = fetch_openverse_photo([keyword], out_path, need_saudi=False,
                                         min_hits=1, subject_mode=True)

    if photo is None:
        # nothing in the archive — generate something simple about the subject
        subject = keywords[0] if keywords else spec.get("heading", "")
        prompt = f"A clear editorial photograph of {subject}"
        photo, _ = fetch_generated_photo(prompt, out_path)
    return photo


def find_all_photos(brief):
    """Every frame gets its own picture. Returns a list of 4, or None if any
    frame came up empty — a frame without a picture is not published."""
    photos = []
    for n, frame in enumerate(brief.get("frames", [])[:4], 1):
        spec = dict(frame)
        if not spec.get("image_keywords"):
            spec["image_keywords"] = brief.get("image_keywords", [])
        print(f"    frame {n}: {', '.join(spec.get('image_keywords', [])[:4])}")
        photo = find_photo(spec, OUT_DIR / f"story-frame-{n}.jpg")
        if photo is None:
            print(f"  ! frame {n} has no picture — not publishing this story")
            return None
        photos.append(photo)
    return photos


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    story = STORY or choose_story()
    if not story:
        raise SystemExit(f"No story given and none found in {STORIES_FILE}")

    print(f"1/3 researching: {story}")
    brief = research(story)
    print(f"    {brief['title']}")
    for n, f in enumerate(brief.get("frames", []), 1):
        print(f"    {n}. {f.get('heading', '')} — {f.get('text', '')[:60]}")

    print("2/3 finding a picture for every frame...")
    photos = find_all_photos(brief)
    if photos is None:
        notify(f"⚠️ {ksa_stamp()} — story skipped: a frame had no picture")
        return
    stamp = ksa_stamp()
    frames = build_frames(brief, stamp, photos)
    print(f"    {len(frames)} frames written")

    if DRY_RUN:
        print(f"    DRY_RUN — nothing published. Frames in {OUT_DIR.resolve()}")
        return

    slug = re.sub(r"[^\w]+", "-", story, flags=re.UNICODE)[:40].strip("-")

    if not POST_ENABLED:
        print("3/3 hybrid mode — publishing the frames, not posting")
        urls = [publish_via_github(f) for f in frames]
        for u in urls:
            print(f"    {u}")
        commit_and_push(save_used(load_used(), story), f"story: {slug}")
        notify(f"📖 {stamp} — {brief['title']}\n{len(frames)} لقطات", frames[0])
        return

    if not quota_ok():
        return

    print("3/3 posting the story to Snapchat...")
    urls = []
    if POST_PROVIDER != "bundle":
        urls = [publish_via_github(f) if MEDIA_MODE == "github"
                else upload_media(f) for f in frames]

    response = post_story(brief.get("caption", story), urls, frames)
    print("   ", response)

    if post_ok(response):
        commit_and_push(save_used(load_used(), story), f"story: {slug}")
        commit_and_push(quota_bump(), f"quota {stamp}")
        notify(f"✅ {stamp} — {brief['title']}", frames[0])
    else:
        notify(f"❌ {stamp} — story post failed\n{describe_failure(response)}")


if __name__ == "__main__":
    main()
