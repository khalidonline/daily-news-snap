"""One operational Telegram report per run, with durable ambiguous-send handling."""
import json
import os
from pathlib import Path
from publishing_v2.bundle_api import GitHubJournal, request


def user_message(summary, env):
    """Only publication outcomes belong in the owner's operational chat."""
    expected_live = (env.get('GITHUB_EVENT_NAME') == 'schedule'
                     or env.get('AUTOPILOT_REQUESTED_MODE') == 'live'
                     or summary.get('mode') == 'live')
    if not expected_live:
        return None
    results = summary.get('results', [])
    if not results:
        return ('⚠️ تعذّر تأكيد نتيجة النشر.\n'
                'المطلوب: فحص سجل التشغيل والتحقق من المنشورات قبل إعادة المحاولة.')
    lines = []
    for row in results:
        lane = 'الباقة المحلية' if row.get('lane') == 'local' else 'الباقة اليومية'
        receipt = row.get('receipt') or {}
        if (row.get('status') == 'published' and receipt.get('status') == 'POSTED'
                and receipt.get('post_ids')):
            title = ' '.join(str(row.get('title') or lane).split())[:120]
            count = len(receipt['post_ids'])
            unit = 'مقطع' if row.get('delivery_kind') == 'video' else 'بطاقات'
            lines.append(f'✅ تم نشر {lane}: {title} — {count} {unit}.')
        elif row.get('reason') == 'BudgetBlocked':
            lines.append(f'⏸️ لم تُنشر {lane}: المتبقي من ميزانية اليوم لا يكفي لإكمالها.\n'
                         'المحاولة التالية ضمن ميزانية اليوم التالي؛ بدون رفع السقف تلقائيًا.')
        elif row.get('status') == 'delivery_pending':
            lines.append(f'⚠️ نشر {lane} غير مؤكّد وقد تكون بعض البطاقات وصلت.\n'
                         'المطلوب: التحقق من المنشورات قبل إعادة المحاولة لتجنب التكرار.')
        elif summary.get('mode') == 'shadow':
            lines.append(f'⏸️ لم تُنشر {lane}: التشغيل الآلي ما زال في مرحلة التحقق.\n'
                         'المطلوب: اجتياز اختبار الجاهزية قبل تفعيل النشر.')
        elif row.get('reason') in {'no_package_passed_review', 'no_current_candidates'}:
            lines.append(f'⏸️ لم تُنشر {lane}: لم تجتز أي باقة شروط الجودة والتوقيت.\n'
                         'المطلوب: مراجعة أسباب الرفض وتحسين الاختيار قبل المحاولة التالية.')
        else:
            lines.append(f'⚠️ تعذّر تأكيد نشر {lane}.\n'
                         'المطلوب: فحص سجل التشغيل والتحقق من المنشورات قبل إعادة المحاولة.')
    return '\n\n'.join(lines)


def main():
    path = Path('autopilot-output/summary.json')
    summary = json.loads(path.read_text()) if path.exists() else {}
    message = user_message(summary, os.environ)
    if message is None:
        print('Review-only run: details retained in workflow artifacts')
        return 0
    token, chat = os.environ.get('TELEGRAM_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat:
        print('Telegram report unavailable: missing existing chat configuration')
        return 1
    journal = GitHubJournal('autopilot-report-' + os.environ['GITHUB_RUN_ID'])
    if journal.read():
        print('Report already attempted; no duplicate send')
        return 0
    journal.save({'status': 'sending'})
    response = request('https://api.telegram.org/bot' + token + '/sendMessage',
                       {'Content-Type': 'application/json'}, 'POST',
                       json.dumps({'chat_id': chat, 'text': message,
                                   'disable_web_page_preview': True}).encode())
    result = response.get('result', {})
    if (response.get('ok') is not True or type(result.get('message_id')) is not int
            or str(result.get('chat', {}).get('id')) != str(chat)):
        raise ValueError('report_receipt_invalid')
    journal.save({'status': 'sent', 'message_id': result['message_id']})
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print('Report delivery unresolved: ' + type(error).__name__)
        raise SystemExit(1) from None
