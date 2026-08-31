#!/usr/bin/env python3
"""Run a confirmed breaking event with a fail-closed visual relevance gate.

Normal scheduled news keeps news_bot.py's existing image policy. This runner is
used only after breaking_watch.py has pinned a confirmed breaking event.
"""

import base64
import json
import urllib.request
from pathlib import Path

from PIL import Image

import news_bot

BREAKING_VISUAL_EXIT = 42

_BREAKING_VISION_PROMPT = """أنت بوابة صور صارمة لبطاقة «خبر عاجل» على سناب شات.

الحدث العاجل:
{context}

احكم على الصورة نفسها. أجب بكلمة واحدة أولاً: نعم أو محايدة أو لا، ثم سبب قصير.

نعم فقط إذا كانت الصورة تُظهر بوضوح شخصاً مسمى في الحدث، جهة أو مؤسسة
مشاركة مباشرة، اجتماعاً/مؤتمراً/توقيعاً مرتبطاً بالحدث، أو مكاناً/شيئاً
مذكوراً مباشرة ويصلح دليلاً بصرياً للقصة.

محايدة إذا كانت الصورة من المجال العام للقصة لكن الرابط غير مباشر.
لا إذا كانت الصورة حشواً أو قد توهم القارئ بعلاقة غير موجودة.

قاعدة مهمة جداً: مجرد كون الحدث سعودياً لا يجعل أي صورة للرياض أو السعودية
صالحة. سوق قديم، أفق مدينة، صحراء، كورنيش، أو معلم عام = لا، ما لم يكن ذلك
المكان نفسه جزءاً محدداً من الحدث. في العاجل، الشك لا يمر."""


def _strict_vision_verdict(bot, photo_path, context):
    """Return yes/neutral/no; any inability to verify is a hard no."""
    if not getattr(bot, "VISION_GATE", True):
        print("  ! breaking visual gate disabled — rejecting photo fail-closed")
        return "no"
    api_key = (getattr(bot, "ANTHROPIC_API_KEY", "") or "").strip()
    if not api_key:
        print("  ! no vision API key — rejecting breaking photo fail-closed")
        return "no"
    try:
        import io
        img = Image.open(photo_path).convert("RGB")
        img.thumbnail((800, 800))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=80)
        encoded = base64.b64encode(buf.getvalue()).decode()
    except Exception as exc:
        print(f"  ! breaking visual unreadable ({exc}) — rejecting")
        return "no"

    payload = {
        "model": getattr(bot, "VISION_MODEL", "claude-haiku-4-5-20251001"),
        "max_tokens": 150,
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {
                "type": "base64", "media_type": "image/jpeg", "data": encoded,
            }},
            {"type": "text", "text": _BREAKING_VISION_PROMPT.format(
                context=(context or "")[:900]
            )},
        ]}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        text = "".join(
            block.get("text", "") for block in data.get("content", [])
            if block.get("type") == "text"
        ).strip()
    except Exception as exc:
        print(f"  ! breaking visual gate unavailable ({exc}) — rejecting fail-closed")
        return "no"

    head = text[:50]
    positions = {word: head.find(word) for word in ("نعم", "محايدة", "لا")}
    found = [(pos, word) for word, pos in positions.items() if pos >= 0]
    word = min(found)[1] if found else "لا"
    verdict = {"نعم": "yes", "محايدة": "neutral", "لا": "no"}[word]
    print(f"    breaking visual gate: {verdict} — {text[:140]}")
    return verdict


def _breaking_photo_acceptable(bot, photo_path, event, extra_context=""):
    if not photo_path:
        return False
    context = "\n".join(part for part in (event, extra_context) if part)
    return _strict_vision_verdict(bot, photo_path, context) == "yes"


def _cleanup_rejected(path):
    if not path:
        return
    for suffix in ("", ".exempt", ".generated"):
        try:
            Path(str(path) + suffix).unlink(missing_ok=True)
        except Exception:
            pass


def _context_from_call(args, kwargs):
    pieces = []
    for value in list(args) + list(kwargs.values()):
        if isinstance(value, str):
            if not value.startswith(("http://", "https://")):
                pieces.append(value)
        elif isinstance(value, (list, tuple)):
            pieces.extend(str(item) for item in value if isinstance(item, str))
    return " | ".join(pieces)[:600]


def install_strict_visual_gate(bot):
    """Wrap breaking-image providers so only an explicit visual yes survives."""
    state = {"accepted_photo": False, "post_called": False, "notified": False}
    event = (getattr(bot, "PINNED_EVENT", "") or "").strip()

    pair_names = (
        "fetch_local_photo", "fetch_article_photo", "fetch_spa_photo",
        "fetch_commons_photo", "fetch_loc_photo", "fetch_openverse_photo",
    )
    for name in pair_names:
        original = getattr(bot, name, None)
        if not callable(original):
            continue

        def make_pair_wrapper(func):
            def wrapped(*args, **kwargs):
                photo, credit = func(*args, **kwargs)
                if not photo:
                    return photo, credit
                if _breaking_photo_acceptable(
                    bot, photo, event, _context_from_call(args, kwargs)
                ):
                    state["accepted_photo"] = True
                    return photo, credit
                print("      breaking visual rejected — trying next source")
                _cleanup_rejected(photo)
                return None, None
            return wrapped

        setattr(bot, name, make_pair_wrapper(original))

    original_stock = getattr(bot, "fetch_photo", None)
    if callable(original_stock):
        def strict_stock(*args, **kwargs):
            photo = original_stock(*args, **kwargs)
            if not photo:
                return None
            if _breaking_photo_acceptable(
                bot, photo, event, _context_from_call(args, kwargs)
            ):
                state["accepted_photo"] = True
                return photo
            print("      breaking visual rejected — trying next source")
            _cleanup_rejected(photo)
            return None
        bot.fetch_photo = strict_stock

    original_post = getattr(bot, "post_story", None)
    if callable(original_post):
        def strict_post(*args, **kwargs):
            if not state["accepted_photo"]:
                _abort_no_visual(bot, event, state)
            state["post_called"] = True
            return original_post(*args, **kwargs)
        bot.post_story = strict_post

    return state


def _abort_no_visual(bot, event, state):
    if not state.get("notified"):
        bot.notify(
            f"🚨⏸️ {bot.ksa_stamp()} — تأكد الحدث العاجل لكن لم يُنشر: "
            "لم توجد صورة مرتبطة بالحدث بما يكفي\n"
            f"{event[:150]}"
        )
        state["notified"] = True
    print("  ! confirmed breaking event withheld — no sufficiently relevant visual")
    raise SystemExit(BREAKING_VISUAL_EXIT)


def run_bot(bot=news_bot):
    event = (getattr(bot, "PINNED_EVENT", "") or "").strip()
    if not event:
        return bot.main()

    state = install_strict_visual_gate(bot)
    result = bot.main()

    # news_bot currently returns normally when REQUIRE_PHOTO exhausts all
    # sources. In breaking mode that must not be interpreted by the watcher as
    # a successful publish. A dedicated non-zero exit keeps the daily cap free.
    dry_run = bool(getattr(bot, "DRY_RUN", False))
    if getattr(bot, "POST_ENABLED", True) and not dry_run and not state["post_called"]:
        _abort_no_visual(bot, event, state)
    return result


if __name__ == "__main__":
    run_bot()
