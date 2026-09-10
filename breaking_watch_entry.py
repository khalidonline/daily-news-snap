#!/usr/bin/env python3
"""Production entrypoint for breaking watch with strict visual publishing."""

import os
import subprocess
import sys

import breaking_freshness
import breaking_watch


_TRUSTED_VERIFICATION_RULE = """

قاعدة تحقق إلزامية للحوادث عالية الخطورة في السعودية والخليج:
إذا كان أي مرشح يتعلق بهجوم عسكري أو صاروخي/مسير، إصابات أو وفيات،
مطارات أو قواعد أو منشآت طاقة، سفن أو مضيق هرمز أو الملاحة الخليجية،
فاستخدم بحث التحقق المتاح تحديداً للتحقق من Reuters أو AP أو مصدر رسمي
سعودي/خليجي ذي صلة قبل الرفض بسبب نقص التأكيد. لا ترفض هذا النوع لمجرد
أن أول عنوان غير رسمي؛ افحص المصدر الموثوق أولاً. لا يغيّر هذا شروط
العاجل الأخرى ولا يضيف بحثاً مدفوعاً آخر: إذا لم يؤكد مصدر موثوق الحدث
بعد هذا البحث فالأصل الرفض. قبل الرفض دوّن في reason ما إذا وُجد أو لم
يوجد تأكيد من Reuters/AP/مصدر رسمي.
"""

_EVENT_TIME_RULE = """

وقت الحدث إلزامي في حكم العاجل حتى نعرف هل ما زال عاجلاً:
إذا كان breaking=true، اختم حقل event دائماً بالصيغة الدقيقة
«— وقت الحدث: YYYY-MM-DD HH:MM بتوقيت السعودية» مستخدماً وقت وقوع/إعلان
الحدث من المصدر، لا وقت تشغيل المراقب ولا وقت نشر مقال يعيد تغطية الحدث.
إذا لم تستطع إثبات تاريخ وقوع الحدث نفسه فلا تجعله breaking=true.
خبر وقع في تاريخ سعودي سابق لا يكون «خبر عاجل» اليوم حتى لو ظهر له مقال
جديد اليوم؛ تطور جديد مستقل فقط يمكن أن يكون عاجلاً، وله تاريخ ووقت جديدان.
"""


def _event_time_from_env_or_event(extra_env):
    return (
        str(extra_env.get("PINNED_EVENT_OCCURRED_AT", "") or "").strip()
        or str(extra_env.get("PINNED_EVENT", "") or "").strip()
    )


def _run_strict_news_bot(extra_env):
    # Hard fail-closed freshness gate. This runs before editorial generation,
    # visual search, Telegram delivery, or any direct publishing path.
    event_time = _event_time_from_env_or_event(extra_env)
    if not breaking_freshness.is_same_ksa_day(event_time, breaking_watch.ksa_now()):
        print("stale/unknown Breaking event time — refused before card generation")
        return 0

    env = os.environ.copy()
    env.update(extra_env)
    # Review phase: breaking cards may be generated and sent to Telegram,
    # but this entrypoint must never allow a direct Snapchat publish.
    env["POST_TO_SNAPCHAT"] = "0"
    return subprocess.call([sys.executable, "breaking_resilient_runner.py"], env=env)


def _manual_delivery_context(event):
    now = breaking_watch.ksa_now()
    state = breaking_watch.load_state()
    return now, state, breaking_watch.event_fp(event)


def _manual_delivery_already_recorded(now, state, fingerprint):
    return (
        state.get("date") == now.date().isoformat()
        and state.get("event_fp") == fingerprint
        and bool(state.get("reviewed") or state.get("posted"))
    )


def _record_manual_review_delivery(now, state, fingerprint):
    today = now.date().isoformat()
    same_day = state.get("date") == today
    updated = dict(state)
    updated.update(
        date=today,
        posted=bool(state.get("posted")) if same_day else False,
        reviewed=True,
        event_fp=fingerprint,
        lock_at="",
        stamps=(list(state.get("stamps", [])) if same_day else [])
        + [breaking_watch.ksa_stamp()],
    )
    breaking_watch.save_state(updated)


def _install_quiet_notifications():
    """Silence routine watcher status while preserving real alerts/failures."""
    send = breaking_watch.notify

    def notify(message):
        text = str(message)
        if text.startswith("⚪️"):
            print("routine breaking-watch Telegram notification suppressed")
            return None
        return send(message)

    breaking_watch.notify = notify


def _install_trusted_verification_rule():
    """Tighten the existing single search for severe Gulf candidates."""
    if _TRUSTED_VERIFICATION_RULE.strip() not in breaking_watch.WATCH_PROMPT:
        breaking_watch.WATCH_PROMPT += _TRUSTED_VERIFICATION_RULE


def _install_breaking_time_guidance():
    """Make source-based event date/time mandatory for a positive verdict."""
    if _EVENT_TIME_RULE.strip() not in breaking_watch.WATCH_PROMPT:
        breaking_watch.WATCH_PROMPT += _EVENT_TIME_RULE


breaking_watch._run_news_bot = _run_strict_news_bot


def run():
    """Run the watcher, or safely reproduce an already-confirmed event."""
    confirmed_event = (
        os.getenv("CONFIRMED_BREAKING_EVENT", "").strip()
        or os.getenv("TRIGGER_CONFIRMED_EVENT", "").strip()
    )
    if confirmed_event:
        now, state, fingerprint = _manual_delivery_context(confirmed_event)
        if _manual_delivery_already_recorded(now, state, fingerprint):
            print("manual Breaking recovery already delivered to Telegram today — quiet duplicate")
            return 0

        occurred_at = os.getenv("CONFIRMED_BREAKING_OCCURRED_AT", "").strip()
        if not breaking_freshness.is_same_ksa_day(
            occurred_at or confirmed_event, now
        ):
            print("manual Breaking recovery is stale or lacks same-day event time — refused")
            return 0

        mode = os.getenv("BREAKING_RUN_MODE", "repair_visual").strip()
        print(f"manual confirmed-event reproduction ({mode}) — classifier bypassed, dry run forced")
        rc = _run_strict_news_bot({
            "PINNED_EVENT": confirmed_event,
            "PINNED_EVENT_OCCURRED_AT": occurred_at,
            "BREAKING_RUN_MODE": mode,
            "POST_TO_SNAPCHAT": "0",
            "DRY_RUN": "1",
        })
        if rc == 0 and breaking_watch.PERSIST_REVIEW_STATE:
            _record_manual_review_delivery(now, state, fingerprint)
        return rc

    _install_quiet_notifications()
    _install_trusted_verification_rule()
    _install_breaking_time_guidance()
    breaking_watch.watch()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
