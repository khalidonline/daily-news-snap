"""One operational Telegram report per run, with durable ambiguous-send handling."""
import json
import os
from pathlib import Path
from publishing_v2.bundle_api import GitHubJournal, request


def main():
    token, chat = os.environ.get('TELEGRAM_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat:
        print('Telegram report unavailable: missing existing chat configuration')
        return 1
    path = Path('autopilot-output/summary.json')
    summary = json.loads(path.read_text()) if path.exists() else {}
    lines = ['Agentic daily-news-snap · ' + str(summary.get('mode', 'run interrupted'))]
    for row in summary.get('results', []):
        lines.append(f"{row['lane']}: {row['status']} · ${row['cost_micro_usd']/1e6:.4f} this attempt")
        if row.get('reason') == 'BudgetBlocked':
            lines.append('BudgetBlocked: $3/day shared budget guard stopped this package. '
                         'Previous spending and unresolved reservations still count. '
                         'Review costs before deciding whether an increase is needed; '
                         'any increase requires your approval. No automatic increase.')
    lines.append('https://github.com/khalidonline/daily-news-snap/actions/runs/' + os.environ['GITHUB_RUN_ID'])
    journal = GitHubJournal('autopilot-report-' + os.environ['GITHUB_RUN_ID'])
    if journal.read():
        print('Report already attempted; no duplicate send')
        return 0
    journal.save({'status': 'sending'})
    response = request('https://api.telegram.org/bot' + token + '/sendMessage',
                       {'Content-Type': 'application/json'}, 'POST',
                       json.dumps({'chat_id': chat, 'text': '\n'.join(lines),
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
