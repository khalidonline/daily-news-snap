#!/usr/bin/env python3
"""Production entrypoint for breaking watch with strict visual publishing."""

import os
import subprocess
import sys

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
إذا كان breaking=true، اختم حقل event دائماً بـ «— وقت الحدث: HH:MM بتوقيت
السعودية» مستخدماً وقت وقوع/إعلان الحدث من المصدر، لا وقت تشغيل المراقب.
إذا لم يعطِ أي مصدر وقتاً دقيقاً فاكتب «— وقت الحدث: غير محدد» ولا تخمّن.
خذ عمر الحدث في الحسبان عند تطبيق شرط «عمره ساعات لا أيام»: تحديث قديم لا
يصبح عاجلاً لمجرد أن مقالاً جديداً أعاد نشره، أما تطور جديد مستقل فله وقته.
"""


def _run_strict_news_bot(extra_env):
    env = os.environ.copy()
    env.update(extra_env)
    # Review phase: breaking cards may be generated and sent to Telegram,
    # but this entrypoint must never allow a direct Snapchat publish.
    env["POST_TO_SNAPCHAT"] = "0"
    return subprocess.call([sys.executable, "breaking_resilient_runner.py"], env=env)


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
    """Make source-based event time part of every positive breaking verdict."""
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
        mode = os.getenv("BREAKING_RUN_MODE", "repair_visual").strip()
        print(f"manual confirmed-event reproduction ({mode}) — classifier bypassed, dry run forced")
        return _run_strict_news_bot({
            "PINNED_EVENT": confirmed_event,
            "BREAKING_RUN_MODE": mode,
            "POST_TO_SNAPCHAT": "0",
            "DRY_RUN": "1",
        })

    _install_quiet_notifications()
    _install_trusted_verification_rule()
    _install_breaking_time_guidance()
    breaking_watch.watch()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
