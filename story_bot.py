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
        describe_failure, notify, notify_album, ksa_stamp,
        quota_ok, quota_bump,
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
# 4 is terse, 6 gives a story room to breathe. Snapchat's own guidance
# favours 5-8 frame stories with a clear beginning, middle and end.
STORY_FRAMES = max(4, min(7, int(os.getenv("STORY_FRAMES", "").strip() or "6")))
# generated filler hurts a story more than it helps — off by default here
ALLOW_STORY_GENERATION = os.getenv("ALLOW_STORY_GENERATION", "0").strip() \
    not in ("", "0", "false", "False")
COOLDOWN_DAYS = int(os.getenv("STORY_COOLDOWN_DAYS", "").strip() or "60")

SYSTEM_PROMPT = """أنت تكتب قصة تُنشر على سناب شات لجمهور سعودي، في {n} لقطات.

القصة ليست خبراً ولا مقالاً. لها بداية ومنعطف ورقم ونهاية تترك أثراً.
ابحث في الإنترنت أولاً، ثم اكتب. كل ما تكتبه يجب أن يكون صحيحاً وموثقاً.

القصة تُروى في {n} لقطات. لها بطل وتوتر، وليست قائمة معلومات.

البناء:
1. المشهد الأول — من هو البطل، وأين كان، وما الذي كان يواجهه.
   ضع القارئ في المكان. ابدأ بالشخص لا بالتاريخ.
   ✗ "سنة 1945، جدة. محطة وقود واحدة تبيع قطع غيار."
   ✓ "عبداللطيف جميل كان يبيع البنزين في محطة على طريق مكة القديم، والطرق
      وقتها غير معبّدة."

2. العقبة — ما الذي كان يقف في الطريق؟ لماذا لم تكن الفكرة سهلة؟
   هنا يبدأ القارئ يهتم: لأن هناك ما يمكن أن يخسره البطل.

3. المنعطف — القرار أو اللحظة التي كان يمكن أن تمر عادية ثم غيّرت المسار.

4. الثمن — ما الذي كلّفه ذلك؟ رفض، إفلاس وشيك، سخرية، سنوات ضائعة.
   القصة بلا ثمن لا تُصدّق.

5. النتيجة — رقم واحد كبير بمصدره وتاريخه، مربوط بالبداية:
   "من أربع سيارات إلى ربع مليون".

6. المعنى — لماذا تستحق هذه القصة أن تُروى اليوم؟ ملاحظة ذكية عن سبب النجاح
   أو الفشل. ليست تلخيصاً ولا وعظاً.

إن طلبت لقطات أقل من ٦، ادمج العقبة مع المشهد الأول والثمن مع المنعطف.
إن طلبت ٧، افصل المنعطف عن نتيجته المباشرة.

قاعدة التسليم بين اللقطات — الأهم في القصة:

- كل اسم (شخص، شركة، مكان، منتج) يجب أن يُقدَّم عند أول ذكر له: من هو،
  وما علاقته بالبطل. لا يظهر اسم فجأة كأن القارئ يعرفه.
  ✗ اللقطة 3: "Fairchild أرسلت لوسون ليفحص النموذج" — ومن أين جاءت Fairchild؟
  ✓ اللقطة 2 تنتهي بـ: "وفي 1970 دخل Jerry Lawson شركة Fairchild لصناعة
     الرقائق، مهندساً في قسم المبيعات."
     ثم اللقطة 3 تبدأ بـ: "وهناك وصله نموذج غريب..."

- كل لقطة تبدأ بما يربطها بالتي قبلها: ضمير، أو إشارة، أو أداة سرد.
  "وهناك"، "وبعد سنتين"، "لكن المشكلة أن"، "هذا الجهاز".

- اللقطة التي تبدأ باسم جديد بلا تمهيد تكسر القصة. اقرأ كل لقطة وحدها
  واسأل: هل فيها اسم لم يُشرح من قبل؟ إن كان الجواب نعم، أضف التمهيد
  في اللقطة السابقة لا في هذه.

- نهاية كل لقطة تفتح سؤالاً تجيب عنه التي بعدها. القارئ ينتقل لأنه يريد
  أن يعرف، لا لأن هناك لقطة أخرى.

الربط بين اللقطات:
- كل لقطة تكمل التي قبلها. استخدم أدوات السرد: "لكن"، "وفي تلك السنة"،
  "ما توقّع أحد"، "وهنا".
- اللقطة التي تصلح للوقوف وحدها بلا ترتيب ليست جزءاً من قصة، بل معلومة.
- اختبار قبل التسليم: اقرأ اللقطات بالترتيب. هل تُقرأ كحكاية متصلة؟
  إن لم تكن كذلك، أعد الكتابة.

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
- text: من جملتين إلى أربع جمل (١٢٠ إلى ٢٨٠ حرفاً).
  خذ راحتك: القصة المضغوطة تفقد معناها. اشرح السبب والنتيجة،
  لا العناوين فقط. لكن بلا حشو — كل جملة تضيف شيئاً جديداً.
- image_keywords: من كلمتين إلى أربع كلمات إنجليزية بسيطة للبحث عن صورة
  حقيقية. أسماء علم فقط: اسم الشخص أو الشركة أو المنتج أو المكان.
  ✓ ["Steve Jobs", "Macintosh 128K", "Apple Park"]
  ✗ ["a garage in California in 1976"]   ✗ ["office building", "modern desk"]

  اللقطة الأولى: صورة البطل نفسه. ضع اسمه الكامل أولاً في القائمة.
  القصة عن شخص تبدأ بوجهه، لا بمشهد عام للمدينة أو المبنى.
  ✓ ["Abdul Latif Jameel", "Sulaiman Al Rajhi", "Ali Al-Naimi"]

  بقية اللقطات: المنتج أو الشركة أو المكان المذكور في تلك اللقطة تحديداً.
  لا تضع كلمات عامة (مكتب، مبنى، موظفون) — الصورة العامة أسوأ من لا شيء
  لأنها تبدو حشواً. اختر ما تتوقع وجوده فعلاً في أرشيف صور.

واكتب أيضاً:
- title: عنوان القصة كاملاً (حتى ٤٥ حرفاً) — يظهر في اللقطة الأولى
- caption: نص المنشور المرافق (حتى ١٢٠ حرفاً)
- sources: من ٢ إلى ٤ مصادر
- image_queries: ثلاث عبارات إنجليزية لصورة اللقطة الأولى، مشهد ملموس
  بلا أشخاص ولا شعارات ولا نصوص
- image_queries_ar: ثلاث كلمات عربية مفردة للبحث في أرشيف الصور السعودي
- image_prompt: وصف إنجليزي لمشهد واحد متماسك، بلا نصوص ولا وجوه

أجب بصيغة JSON فقط:
{{"title": "...", "caption": "...", \
"frames": [{{"heading": "...", "text": "...", \
"image_keywords": ["...", "...", "..."]}}], \
"sources": ["..."], "image_queries": ["..."], "image_queries_ar": ["..."], \
"image_prompt": "..."}}"""


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
            "system": SYSTEM_PROMPT.format(n=STORY_FRAMES),
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
        # longer frames are allowed now, so shrink until the text fits the space
        available = (H - 260 if footer else H - 180) - y
        sub_size, line_gap = 42, 60
        while sub_size > 28:
            f_sub = load_font(sub_size, bold=sub_colour == ACCENT)
            lines = _wrap(draw, sub, f_sub, max_w, kw)
            line_gap = int(sub_size * 1.42)
            if len(lines) * line_gap <= available:
                break
            sub_size -= 2
        for line in lines:
            mid(y, line, f_sub, sub_colour or BODY)
            y += line_gap

    if footer:
        draw.line([(centre - 130, H - 206), (centre + 130, H - 206)],
                  fill=RULE, width=2)
        mid(H - 160, footer, load_font(26), MUTED)

    img.save(path, "PNG", optimize=True)
    return path


# words that introduce a name: "شركة X", "جهاز Y", "مدينة Z"
INTRODUCERS = ("شركة", "مؤسسة", "مصنع", "بنك", "متجر", "جهاز", "منتج", "طراز",
               "مدينة", "قرية", "ميناء", "مطار", "جامعة", "مهندس", "مؤسس",
               "رئيس", "مدير", "شريك", "منافس", "علامة", "مشروع", "صندوق",
               "لعبة", "سيارة", "طائرة", "تطبيق", "موقع", "برنامج")


def warn_about_unintroduced_names(brief):
    """Flag proper names dropped into the middle of a story with no
    introduction — a reader meeting 'Fairchild' in frame 3 has lost the thread.

    A name is treated as introduced if an Arabic descriptor sits just before it
    (شركة Fairchild) or if it already appeared earlier. Latin script only;
    Arabic names are left to the prompt.
    """
    frames = brief.get("frames", [])
    seen = set(re.findall(r"\b[A-Z][A-Za-z0-9&.\-]{2,}", brief.get("title", "")))
    ignore = {"The", "And", "For", "USA", "US", "UK", "AI", "TV", "CEO", "GDP"}
    flagged = 0

    for n, frame in enumerate(frames, 1):
        text = f"{frame.get('heading', '')} {frame.get('text', '')}"
        names = set(re.findall(r"\b[A-Z][A-Za-z0-9&.\-]{2,}", text)) - ignore

        for name in sorted(names - seen):
            if n == 1:
                continue
            # is it introduced right here?
            window = text[max(0, text.find(name) - 24):text.find(name)]
            if any(word in window for word in INTRODUCERS):
                continue
            flagged += 1
            print(f"  ? {name} appears in frame {n} with no introduction — "
                  "the previous frame should hand it over")
        seen |= names

    if not flagged and len(frames) > 1:
        print("    handshakes: every name is introduced before use")


def build_frames(brief, stamp, photos):
    """Render one frame per beat. The last frame carries the sources."""
    frames = brief.get("frames", [])[:STORY_FRAMES]
    if len(frames) < 4:
        raise SystemExit(f"expected at least 4 frames, got {len(frames)}")

    if len(photos) < len(frames):
        raise SystemExit(f"{len(frames)} frames but only {len(photos)} photos")

    # source names only — a raw URL in the footer looks like a mistake
    names = []
    for src in brief.get("sources", [])[:3]:
        src = re.sub(r"^https?://(www\.)?", "", str(src)).split("/")[0]
        names.append(src)
    sources = "، ".join(names)
    total = len(frames)
    paths = []

    for n, frame in enumerate(frames, 1):
        last = n == total
        # the opening frame leads with the story title, the rest with their beat
        heading = brief["title"] if n == 1 else frame.get("heading", "")
        paths.append(render_frame(
            OUT_DIR / f"{stamp}-story-{n}.png", BRAND, f"{n} / {total}",
            heading, 60, sub=frame.get("text", ""),
            sub_colour=ACCENT if last else None,
            photo=photos[n - 1],
            footer=(f"المصدر: {sources}" if sources else None) if last else None))

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

    if photo is None and ALLOW_STORY_GENERATION:
        # Nothing in the archive. Generating a building or an office produces
        # filler with invented signage, so ask for something plain instead.
        subject = keywords[0] if keywords else spec.get("heading", "")
        prompt = (f"A plain, unbranded photograph relating to {subject}. "
                  "No buildings with signs, no offices, no logos, no text.")
        photo, _ = fetch_generated_photo(prompt, out_path)
    return photo


def find_all_photos(brief):
    """Every frame gets its own picture. Returns a list of 4, or None if any
    frame came up empty — a frame without a picture is not published."""
    photos = []
    for n, frame in enumerate(brief.get("frames", [])[:STORY_FRAMES], 1):
        spec = dict(frame)
        if not spec.get("image_keywords"):
            spec["image_keywords"] = brief.get("image_keywords", [])
        print(f"    frame {n}: {', '.join(spec.get('image_keywords', [])[:4])}")
        photo = find_photo(spec, OUT_DIR / f"story-frame-{n}.jpg")
        if photo is None:
            print(f"  ! frame {n} found no real photo for "
                  f"{', '.join(spec.get('image_keywords', [])[:3])}")
            print("    a story with filler pictures is worse than no story")
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
    warn_about_unintroduced_names(brief)

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
        notify_album(f"📖 {stamp} — {brief['title']}\n{len(frames)} لقطات",
                     frames)
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
        notify_album(f"✅ {stamp} — {brief['title']}", frames)
    else:
        notify(f"❌ {stamp} — story post failed\n{describe_failure(response)}")


if __name__ == "__main__":
    main()
