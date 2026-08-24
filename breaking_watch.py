#!/usr/bin/env python3
"""مراقب العاجل — بديل موعد التاسعة مساءً الثابت.

    python breaking_watch.py            # دورة مراقبة (كل ٣٠ دقيقة نهاراً)
    python breaking_watch.py fallback   # موعد الثامنة مساءً الاحتياطي

الدورة رخيصة: نموذج صغير يمسح أخبار الساعات الأخيرة ويصنّف فقط — الأصل
الرفض، ومعظم الدورات تنتهي بسطر واحد ولا تلمس الحالة ولا تكلّف commit.
إن تأكد حدث عاجل، تُقفل الدورة القفل ثم تشغّل news_bot كاملاً والحدث
مثبّت (PINNED_EVENT): النموذج الكبير يعيد التحقق ويكتب بكل قواعد
البطاقة، وإن لم يتأكد الحدث يموت التشغيل هناك دون نشر.

الثامنة مساءً: إن كانت بطاقة عاجلة نُشرت اليوم، يعمل news_bot مهجّناً
(بناء وتيليجرام دون نشر — المساء أخذ بطاقته)؛ وإلا فينشر أقوى خبر اليوم
كما كان موعد التاسعة يفعل. جدول المساء كله مكتوب في breaking.yml.
"""

import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from news_bot import (
        ANTHROPIC_API_KEY, DRY_RUN, commit_and_push, ksa_stamp, notify,
    )
except ImportError as exc:
    raise SystemExit(f"news_bot.py is missing something breaking_watch "
                     f"needs ({exc}). The two files move together.")

STATE_FILE = Path("state/breaking.json")
MAX_BREAKING_PER_DAY = 1        # v1 cap — one breaking post a day, full stop
LOCK_MINUTES = 25               # under the 30-minute cadence, so a stuck
                                # lock never outlives the next cycle by much
WATCH_START_H, WATCH_END_H = 8.0, 19.5      # KSA; 20:00 belongs to fallback
# classification is a small-model job — budget it tightly
WATCH_MODEL = os.getenv("WATCH_MODEL", "").strip() or "claude-haiku-4-5-20251001"
WATCH_MAX_TOKENS = int(os.getenv("WATCH_MAX_TOKENS", "").strip() or "1200")
WATCH_MAX_SEARCHES = int(os.getenv("WATCH_MAX_SEARCHES", "").strip() or "2")

BEATS = ("الاقتصاد السعودي، العقار السعودي والخليجي، السفر والسياحة "
         "السعودية، أخبار الأعمال والتقنية الكبرى")

WATCH_PROMPT = """أنت حارس بوابة «العاجل» لحساب أخبار أعمال سعودي على سناب شات.
مهمتك تصنيف لا كتابة: هل وقع خلال الساعات الأخيرة حدثٌ يستحق بطاقة
عاجلة الآن قبل موعد المساء؟ الأصل الرفض — معظم الدورات جوابها لا،
وبطاقة المساء تلتقط كل ما يحتمل الانتظار.

لا يمر الحدث إلا إذا اجتاز الشروط كلها:
- العاجل حدثٌ عمره ساعات لا أيام — خبر أمس ليس عاجلاً اليوم.
- مصدران مستقلان على الأقل يؤكدانه الآن.
- إن كان الخبر حكومياً أو تنظيمياً أو عن جهة رسمية: لا يمر إلا بمصدر
  رسمي (واس، تداول، الوزارة المعنية، بيان الشركة نفسها).
- يجتاز الاختبارات الثلاثة بوضوح — الأهمية والقرب والتوقف — وأشدها
  التوقف: الحدث الذي «يمكن أن ينتظر الغد» ليس عاجلاً.
✗ «الأسواق تترقب قرار الفائدة» (ترقّب، لا حدث)
✗ «تقرير: نمو القطاع العقاري 12% هذا العام» (تقرير دوري، ينتظر)
✗ «مصدر واحد: استقالة وشيكة» (لا تأكيد)
✓ «تداول تعلق تداول سهم X — بيان رسمي منذ ساعة، وكالتان»
✓ «إعلان حكومي الآن يغيّر رسوم Y ابتداء من الغد — واس»

أجب بـJSON فقط، بلا أي نص قبله أو بعده:
{"breaking": true/false,
 "event": "وصف الحدث في جملة واحدة، بالجهة والوقت",
 "sources": ["المصدر ١", "المصدر ٢"],
 "official_source": true/false,
 "reason": "لماذا مرّ أو لماذا رُفض"}"""


def ksa_now():
    return datetime.now(timezone.utc) + timedelta(hours=3)


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    # shared-file discipline: same rebase-and-retry push as quota.json.
    # A DRY_RUN keeps its state local so tests never race the live bots.
    if not DRY_RUN:
        commit_and_push(STATE_FILE, f"breaking state {ksa_stamp()}")


def event_fp(event):
    """Coarse same-day fingerprint so one event can't post twice in
    different words. Word-set hash: order and punctuation don't matter."""
    words = sorted(set(w for w in event.split() if len(w) > 2))
    return hashlib.md5(" ".join(words).encode()).hexdigest()[:16]


def classify(now):
    """One small-model call with tightly budgeted search. None on error —
    and None is treated as 'not breaking': a broken classifier must fail
    quiet, never fail posting."""
    if not ANTHROPIC_API_KEY:
        print("  ! no ANTHROPIC_API_KEY — cannot classify, exiting quiet")
        return None
    user = (f"الآن {now:%Y-%m-%d %H:%M} بتوقيت السعودية. امسح أخبار "
            f"الساعات الأخيرة في هذه الملفات: {BEATS}. "
            f"ابحث بحثاً أو بحثين موجهين لليوم فقط، ثم أصدر الحكم.")
    payload = {
        "model": WATCH_MODEL,
        "max_tokens": WATCH_MAX_TOKENS,
        "system": WATCH_PROMPT,
        "messages": [{"role": "user", "content": user}],
        "tools": [{"type": "web_search_20250305", "name": "web_search",
                   "max_uses": WATCH_MAX_SEARCHES}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json",
                 "x-api-key": ANTHROPIC_API_KEY,
                 "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        text = "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text").strip()
        start, end = text.find("{"), text.rfind("}")
        return json.loads(text[start:end + 1])
    except Exception as exc:
        print(f"  ! classifier failed ({exc}) — treating as not breaking")
        return None


def _run_news_bot(extra_env):
    env = os.environ.copy()
    env.update(extra_env)
    return subprocess.call([sys.executable, "news_bot.py"], env=env)


def watch():
    # Every run reports — a working watcher and a dead one must never
    # produce the same observable output (nothing). One Telegram line per
    # cycle, whatever happened; errors are sent, not swallowed.
    try:
        _watch()
    except SystemExit:
        raise
    except Exception as exc:
        notify(f"🔴 {ksa_stamp()} — مراقب العاجل تعطّل: {exc}")
        raise


def _watch():
    now = ksa_now()
    hour = now.hour + now.minute / 60
    # the cron already stops outside the window, but GitHub replays stale
    # crons after workflow edits (see the bitten list) — the script itself
    # must be safe to fire at any time, twice
    if not WATCH_START_H <= hour <= WATCH_END_H:
        print(f"outside the watch window ({now:%H:%M} KSA) — exiting")
        return

    state = load_state()
    today = now.date().isoformat()
    if state.get("date") == today:
        if state.get("posted") and \
                len(state.get("stamps", [])) >= MAX_BREAKING_PER_DAY:
            print("today's breaking post already went out — quiet cycle")
            notify(f"⚪️ {ksa_stamp()} — مراقب العاجل: بطاقة اليوم العاجلة "
                   "نُشرت — دورة هادئة")
            return
        lock = state.get("lock_at", "")
        if lock:
            try:
                held = (now - datetime.fromisoformat(lock)).total_seconds()
            except ValueError:
                held = 0
            if held < LOCK_MINUTES * 60:
                print("another live cycle holds the lock — quiet cycle")
                notify(f"⚪️ {ksa_stamp()} — مراقب العاجل: دورة أخرى تعمل "
                       "الآن (قفل) — خرجت")
                return

    verdict = classify(now)
    if verdict:
        print("verdict:", json.dumps(verdict, ensure_ascii=False))
    if not verdict:
        print("no breaking news this cycle (classifier unavailable)")
        notify(f"🔴 {ksa_stamp()} — مراقب العاجل: تعذّر التصنيف هذه الدورة "
               "(خطأ في الاستدعاء) — عومل كلا عاجل")
        return
    if not verdict.get("breaking"):
        print("no breaking news this cycle")
        n_src = len(verdict.get("sources") or [])
        reason = (verdict.get("reason") or "").strip()[:120]
        notify(f"⚪️ {ksa_stamp()} — مراقب العاجل: لا عاجل — "
               f"{reason or 'لا حدث يجتاز الشروط'}"
               + (f" (مصادر مفحوصة: {n_src})" if n_src else ""))
        return
    # the prompt gates on these too, but a gate the code doesn't hold is a
    # gate a malformed reply walks through
    if len(verdict.get("sources") or []) < 2:
        print("  ! breaking=true with fewer than two sources — refused")
        notify(f"⚪️ {ksa_stamp()} — مراقب العاجل: مرشح واحد رُفض "
               "(أقل من مصدرين) — لا نشر")
        return
    event = (verdict.get("event") or "").strip()
    if not event:
        print("  ! breaking=true with an empty event — refused")
        notify(f"⚪️ {ksa_stamp()} — مراقب العاجل: حكم مشوّه رُفض — لا نشر")
        return
    fp = event_fp(event)
    if state.get("date") == today and state.get("event_fp") == fp:
        print("same event already handled today — quiet cycle")
        notify(f"⚪️ {ksa_stamp()} — مراقب العاجل: الحدث نفسه سبق فحصه "
               f"اليوم — لا تكرار\n{event[:100]}")
        return

    # acquire the cycle lock BEFORE the expensive pipeline
    state = {"date": today, "posted": False, "event_fp": fp,
             "lock_at": now.isoformat(),
             "stamps": state.get("stamps", []) if state.get("date") == today
             else []}
    save_state(state)

    print(f"BREAKING — pinning the event and running the full pipeline:\n"
          f"    {event}")
    rc = _run_news_bot({"PINNED_EVENT": event, "POST_TO_SNAPCHAT": "1"})

    state = load_state()
    if rc == 0:
        if DRY_RUN:
            # the pipeline already sent the [DRY RUN] card message; the
            # watcher must not claim a publish that never happened, nor
            # burn the daily cap on a rehearsal
            state["lock_at"] = ""
            save_state(state)
            print("dry run: card built and reported — nothing posted, "
                  "cap untouched")
            return
        state.update(posted=True, lock_at="",
                     stamps=state.get("stamps", []) + [ksa_stamp()])
        save_state(state)
        notify(f"🚨 بطاقة عاجلة نُشرت تلقائياً\n{event[:150]}")
    else:
        # keep the fingerprint: an event the big model could not confirm
        # must not be retried every half hour — the 20:00 fallback still
        # covers the story through the feeds if it firms up
        state["lock_at"] = ""
        save_state(state)
        print("pinned pipeline aborted — lock released, fingerprint kept")


def fallback():
    state = load_state()
    today = ksa_now().date().isoformat()
    already = state.get("date") == today and state.get("posted")
    if already:
        print("a breaking card already posted today — the 20:00 run goes "
              "hybrid (build + Telegram, no post)")
    else:
        print("no breaking post today — the 20:00 run posts the day's "
              "strongest story, as the old 21:00 slot did")
    rc = _run_news_bot({"POST_TO_SNAPCHAT": "0" if already else "1"})
    sys.exit(rc)


def main():
    role = (sys.argv[1] if len(sys.argv) > 1 else "watch").strip().lower()
    if role == "fallback":
        fallback()
    elif role == "watch":
        watch()
    else:
        raise SystemExit(f"unknown role {role!r} — use 'watch' or 'fallback'")


if __name__ == "__main__":
    main()
