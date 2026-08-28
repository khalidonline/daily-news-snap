#!/usr/bin/env python3
"""Batch-validate repaired stories and send one Telegram text summary.

No story images are sent by this script and Snapchat/Bundle are never called.
Jack Bogle is excluded because it has already passed the single-story review.
"""

import json
import os
import urllib.parse
import urllib.request

import safe_publish_cards as review

REVIEW_PHOTO_STANDARD = 4
JACK_BOGLE = "Jack Bogle: أنشأ صندوق المؤشرات ورفض أن يصبح ملياردير"

REPAIRED_STORIES = [
    "Fred Smith: كتب فكرة FedEx في بحث جامعي ونال درجة متوسطة",
    JACK_BOGLE,
    "سليمان الراجحي: من حمّال في السوق إلى مؤسس أكبر بنك ثم تبرّع بثروته",
    "صالح الراجحي: الشريك الذي بنى المؤسسة وابتعد عن الأضواء",
    "قصة Emirates: من شركتين مستأجرتين إلى أكبر ناقل دولي",
    "قصة IKEA من قرية سويدية",
    "قصة Microsoft: الشركة التي صنعت آلاف المليونيرات في بلدة واحدة",
    "قصة NVIDIA: الموظفون الذين صاروا مليونيرات بالأسهم",
    "قصة NVIDIA: من رقائق الألعاب إلى أغلى شركة في العالم",
    "قصة Netflix: من تأجير الأقراص إلى إنتاج الأفلام",
    "قصة Publix: سلسلة متاجر يملكها موظفوها بالكامل",
    "قصة Samsung: من متجر بقالة إلى عملاق إلكترونيات",
    "قصة Steve Jobs: الطرد من شركته ثم العودة",
    "قصة أرامكو: من اكتشاف الزيت إلى أكبر اكتتاب في التاريخ",
    "قصة مصرف الراجحي من صرافة إلى أكبر بنك",
    "قصة نوكيا من مصنع ورق إلى الهواتف",
    "كيف بنت TSMC احتكاراً على رقائق العالم",
    "كيف تأسست Apple في مرآب، ومن باع حصته مبكراً",
    "كيف تحولت Microsoft من بيع الأنظمة إلى السحابة",
    "كيف خسرت Kodak السوق الذي اخترعته بنفسها",
    "كيف صارت شركة واحدة تتحكم في أسعار الشحن العالمي؟",
    "لماذا سقطت Nokia رغم أنها كانت الأولى عالمياً؟",
    "من بنى Alibaba؟ قصة معلم إنجليزي رُفض 30 مرة",
    "من هم أول الموظفين السعوديين في أرامكو؟",
    "من هو مؤسس أرامكو الحقيقي؟ قصة الاكتشاف الأول",
]


def remaining_repaired_stories():
    return [s for s in REPAIRED_STORIES if s != JACK_BOGLE]


def validate_story(story):
    """Fresh-build one story and prove four photos plus fallback visuals."""
    try:
        stamp, frames = review._build_fresh_review_story(story)
        canonical = review._story_identity(stamp)
        photos, logos = review.approved_runtime_visuals(canonical)
        if len(photos) < REVIEW_PHOTO_STANDARD:
            return False, f"only {len(photos)} approved photos"
        review.apply_requested_photos(
            frames, photos, requested=REVIEW_PHOTO_STANDARD
        )
        fallback_visuals = logos or photos[:1]
        filled = review.apply_fallback_visuals(
            frames, fallback_visuals, start_index=REVIEW_PHOTO_STANDARD
        )
        count = review.require_photo_coverage(
            frames, minimum=REVIEW_PHOTO_STANDARD
        )
        return True, f"{count}/6 photos + {filled} fallback visuals"
    except BaseException as exc:
        return False, str(exc).replace("\n", " ")[:180]


def format_summary(results):
    passed = sum(1 for _story, ok, _detail in results if ok)
    total = len(results)
    lines = [f"Batch story validation: {passed}/{total} ready", ""]
    for i, (story, ok, detail) in enumerate(results, 1):
        mark = "✅ PASS" if ok else "❌ FAIL"
        lines.append(f"{i}. {mark} — {story}")
        if not ok:
            lines.append(f"   {detail}")
    return "\n".join(lines)


def send_summary(text):
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not (token and chat_id):
        raise SystemExit("TELEGRAM_TOKEN and TELEGRAM_CHAT_ID must both be set")
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=data
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        payload = json.loads(resp.read() or b"{}")
    if payload.get("ok") is not True:
        raise SystemExit("Telegram did not confirm batch summary")


def run_batch(stories=None, already_ready=None):
    stories = list(stories if stories is not None else REPAIRED_STORIES)
    already_ready = set(already_ready if already_ready is not None else {JACK_BOGLE})
    targets = [story for story in stories if story not in already_ready]
    results = []
    for index, story in enumerate(targets, 1):
        print(f"[{index}/{len(targets)}] validating {story}")
        ok, detail = validate_story(story)
        results.append((story, ok, detail))
        print(f"    {'PASS' if ok else 'FAIL'}: {detail}")
    send_summary(format_summary(results))
    return results


def main():
    run_batch(remaining_repaired_stories(), already_ready=set())


if __name__ == "__main__":
    main()
