#!/usr/bin/env python3
"""Shared $3/day paid API ceiling, independent of bot, branch, run or retry.

Prices: https://platform.claude.com/docs/en/about-claude/pricing (2026-09-10).
Reservations use conservative request bounds, never average historic costs.
The Contents API's SHA precondition serializes competing runners atomically.
Unknown prices/usage/transport outcomes fail closed. Free retrieval stays free.
"""
from __future__ import annotations

import argparse
import base64
import copy
import io
import json
import os
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

LIMIT_MICRO_USD = 3_000_000
KSA = timezone(timedelta(hours=3))
LEDGER_BRANCH = 'cost-ledger'
# Input, output USD/MTok, maximum context. Reject new models until reviewed.
PRICES = {
    'claude-sonnet-5': (2, 10, 1_000_000),
    'claude-opus-5': (5, 25, 1_000_000),
    'claude-haiku-4-5-20251001': (1, 5, 200_000),
}
_transport = urllib.request.urlopen


class BudgetBlocked(RuntimeError):
    pass


def day_key(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(KSA).date().isoformat()


class GitHubStore:
    def __init__(self, repository, token):
        if not repository or not token:
            raise BudgetBlocked('shared $3 daily budget credentials are missing')
        self.repository = repository
        self.token = token

    def request(self, method, day, payload=None):
        url = f'https://api.github.com/repos/{self.repository}/contents/daily/{day}.json'
        if method == 'GET':
            url += '?ref=' + LEDGER_BRANCH
        req = urllib.request.Request(url, method=method,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Authorization': 'Bearer ' + self.token,
                     'Accept': 'application/vnd.github+json',
                     'Content-Type': 'application/json',
                     'User-Agent': 'daily-news-snap-budget'})
        with _transport(req, timeout=30) as response:
            return json.loads(response.read())

    def read(self, day):
        try:
            response = self.request('GET', day)
            row = json.loads(base64.b64decode(response['content'], validate=False))
            return response['sha'], row
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                # A missing branch or permission must not create a local balance;
                # the following PUT must succeed before any provider call.
                return None, None
            raise BudgetBlocked('cannot read shared daily budget') from exc
        except Exception as exc:
            raise BudgetBlocked('cannot read shared daily budget') from exc

    def write(self, day, version, row):
        payload = {'message': f'budget: {day}', 'branch': LEDGER_BRANCH,
                   'content': base64.b64encode(json.dumps(row, sort_keys=True).encode()).decode()}
        if version:
            payload['sha'] = version
        try:
            self.request('PUT', day, payload)
            return True
        except urllib.error.HTTPError as exc:
            if exc.code in (409, 422):
                return False
            raise BudgetBlocked('cannot persist shared daily budget') from exc
        except Exception as exc:
            # An ambiguous PUT may have succeeded. Do not send a paid request.
            raise BudgetBlocked('cannot confirm daily budget reservation') from exc


class Ledger:
    def __init__(self, store, now=None):
        self.store = store
        self.now = now or (lambda: datetime.now(timezone.utc))

    def change(self, day, change):
        for attempt in range(50):
            version, row = self.store.read(day)
            if row is None:
                row = {'version': 1, 'day': day, 'limit_micro_usd': LIMIT_MICRO_USD,
                       'entries': {}}
            try:
                assert row['version'] == 1 and row['day'] == day
                assert row['limit_micro_usd'] == LIMIT_MICRO_USD
                assert isinstance(row['entries'], dict)
                for entry in row['entries'].values():
                    assert type(entry['charged_micro_usd']) is int
                    assert entry['charged_micro_usd'] >= 0
            except (KeyError, TypeError, AssertionError):
                raise BudgetBlocked('daily budget ledger is invalid')
            change(row)
            if self.store.write(day, version, row):
                return
            time.sleep(min(0.005 * (attempt + 1), 0.1))
        raise BudgetBlocked('daily budget is busy; no paid request authorized')

    def reserve(self, amount, bot):
        if type(amount) is not int or not 0 < amount <= LIMIT_MICRO_USD:
            raise BudgetBlocked('request cannot fit within the $3 daily ceiling')
        day, ident = day_key(self.now()), uuid.uuid4().hex
        def update(row):
            total = sum(e['charged_micro_usd'] for e in row['entries'].values())
            if total + amount > LIMIT_MICRO_USD:
                raise BudgetBlocked(f'$3 daily budget: ${total / 1e6:.4f} spent/reserved; request held')
            row['entries'][ident] = {
                'bot': bot, 'run_id': os.getenv('GITHUB_RUN_ID'),
                'run_attempt': os.getenv('GITHUB_RUN_ATTEMPT'),
                'reserved_at': self.now().isoformat(),
                'reserved_micro_usd': amount, 'charged_micro_usd': amount,
                'status': 'reserved',
            }
        self.change(day, update)
        return day, ident

    def settle(self, token, actual):
        if type(actual) is not int or actual < 0:
            raise BudgetBlocked('unpriced response retains full reservation')
        day, ident = token
        def update(row):
            entry = row['entries'][ident]
            if entry['status'] == 'settled':
                if entry['charged_micro_usd'] != actual:
                    raise BudgetBlocked('conflicting daily budget settlement')
                return
            entry['charged_micro_usd'] = actual
            entry['status'] = 'settled'
        self.change(day, update)


def shared_ledger():
    return Ledger(GitHubStore(os.getenv('GITHUB_REPOSITORY'),
                             os.getenv('DAILY_BUDGET_GITHUB_TOKEN')))


def _contains(value, key):
    if isinstance(value, dict):
        return key in value or any(_contains(v, key) for v in value.values())
    if isinstance(value, list):
        return any(_contains(v, key) for v in value)
    return False


def prepare(original):
    payload = copy.deepcopy(original)
    model = payload.get('model')
    if model not in PRICES:
        raise BudgetBlocked(f'unpriced model blocked by $3 daily budget: {model}')
    if payload.get('stream') or payload.get('speed') or payload.get('inference_geo', 'global') != 'global':
        raise BudgetBlocked('unpriced API mode blocked by daily budget')
    # Server-side search can accumulate hidden input across turns. At most one
    # search per request fits a conservative Sonnet context reservation in $3.
    searches = 0
    for tool in payload.get('tools', []):
        if tool.get('type') not in {'web_search_20250305', 'web_search_20260209', 'web_search_20260318'} or tool.get('name') != 'web_search':
            raise BudgetBlocked('unbounded or unpriced server tool blocked')
        if searches:
            raise BudgetBlocked('multiple server search tools blocked')
        # Dynamic filtering executes server code with additional billing.
        # Use directly bounded search while retaining the source quality gates.
        tool['type'] = 'web_search_20250305'
        tool.pop('response_inclusion', None)
        tool.pop('allowed_callers', None)
        tool['max_uses'] = 1
        searches = 1
    if payload.get('mcp_servers') or payload.get('container'):
        raise BudgetBlocked('unpriced server execution blocked')
    input_price, output_price, context = PRICES[model]
    maximum_output = payload.get('max_tokens')
    if type(maximum_output) is not int or not 0 < maximum_output <= context:
        raise BudgetBlocked('missing finite output token ceiling')
    # Text tokens cannot exceed UTF-8 bytes; reserve extra protocol overhead.
    # Images/documents reserve a whole context rather than guessing pixel cost.
    initial = min(context, len(json.dumps(payload, ensure_ascii=False).encode()) + 8192)
    if _contains(payload, 'source'):
        initial = context
    # One-hour cache writes cost 2x base. Do not count on a cache hit.
    cache_factor = 2 if _contains(payload, 'cache_control') else 1
    amount = (initial + searches * context) * input_price * cache_factor
    amount += maximum_output * (searches + 1) * output_price
    amount += searches * 10_000
    return payload, amount


def actual_cost(model, response):
    usage = response.get('usage')
    if not isinstance(usage, dict) or 'input_tokens' not in usage or 'output_tokens' not in usage:
        raise BudgetBlocked('missing usage; keeping full daily reservation')
    def number(key, source=usage):
        value = source.get(key, 0)
        if type(value) is not int or value < 0:
            raise BudgetBlocked('invalid usage; keeping daily reservation')
        return value
    input_price, output_price, _ = PRICES[model]
    cache = usage.get('cache_creation') or {}
    writes = number('cache_creation_input_tokens')
    one_hour = number('ephemeral_1h_input_tokens', cache)
    five_min = number('ephemeral_5m_input_tokens', cache)
    if writes and one_hour + five_min != writes:
        # Missing TTL accounting: charge the more expensive 1-hour rate.
        one_hour, five_min = writes, 0
    total = Decimal(number('input_tokens') * input_price + number('output_tokens') * output_price)
    total += Decimal(five_min * input_price) * Decimal('1.25')
    total += Decimal(one_hour * input_price * 2)
    total += Decimal(number('cache_read_input_tokens') * input_price) * Decimal('0.1')
    server = usage.get('server_tool_use') or {}
    total += number('web_search_requests', server) * 10_000
    return int(total.to_integral_value(rounding=ROUND_CEILING))


def urlopen(url, data=None, *args, **kwargs):
    address = url.full_url if isinstance(url, urllib.request.Request) else str(url)
    host = urllib.parse.urlsplit(address).hostname or ''
    is_request = isinstance(url, urllib.request.Request)
    body = data if data is not None else (url.data if is_request else None)
    if host != 'api.anthropic.com':
        # No reviewed maximum price for these generation providers: block paid
        # submissions, still permit free image downloads and ordinary fetching.
        if body is not None and (host == 'fal.run' or host.endswith('.fal.run')
                or 'bytepluses.com' in host or 'volces.com' in host
                or host == 'api.openai.com'):
            raise BudgetBlocked('unpriced paid provider blocked by $3 daily budget')
        return _transport(url, data, *args, **kwargs)
    if urllib.parse.urlsplit(address).path != '/v1/messages':
        raise BudgetBlocked('unpriced Anthropic endpoint blocked')
    if not is_request:
        raise BudgetBlocked('paid request must declare headers and payload')
    if url.get_header('Anthropic-beta'):
        raise BudgetBlocked('unpriced beta feature blocked')
    payload, maximum = prepare(json.loads(body))
    ledger = shared_ledger()
    token = ledger.reserve(maximum, os.getenv('MODEL_BOT') or os.getenv('GITHUB_WORKFLOW') or 'manual')
    guarded = urllib.request.Request(address, data=json.dumps(payload).encode(),
                                    headers=dict(url.header_items()), method=url.get_method())
    # No automatic refund on HTTP errors, timeouts, cancellation, or malformed
    # responses: the provider may already have charged. A retry reserves again.
    with _transport(guarded, *args, **kwargs) as response:
        raw = response.read()
    try:
        actual = actual_cost(payload['model'], json.loads(raw))
        ledger.settle(token, actual)
        print(f'  daily $3 budget: request ${actual / 1e6:.4f} accounted')
    except Exception as exc:
        # Preserve a completed useful response. Unsettled money remains locked.
        print(f'  daily $3 budget: reservation retained ({type(exc).__name__})')
    return io.BytesIO(raw)


def install():
    if not getattr(urllib.request.urlopen, '_daily_budget', False):
        urlopen._daily_budget = True
        urllib.request.urlopen = urlopen


def install_runtime(target):
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(__file__, target / 'daily_budget.py')
    # Python normally swallows sitecustomize failures. A missing guard must
    # instead stop startup, including recovery subprocesses and legacy branches.
    (target / 'sitecustomize.py').write_text(
        'import os\ntry:\n    import daily_budget\n    daily_budget.install()\n'
        'except BaseException:\n    os._exit(78)\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['install'])
    parser.add_argument('--target', required=True)
    args = parser.parse_args()
    install_runtime(args.target)
