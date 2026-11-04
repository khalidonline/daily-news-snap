"""Provider HTTP failures retain accounting without leaking response text."""
import json

import pytest

from daily_budget import Ledger
from publishing_v2.autopilot.agents import Agents
from test_daily_budget import MemoryStore


def fail_request(status, body):
    store = MemoryStore()
    ledger = Ledger(store, limit_micro_usd=None)
    calls = []

    def transport(method, url, headers, payload):
        calls.append(payload)
        return {'status_code': status, 'body': body}

    agent = Agents(env={'ANTHROPIC_API_KEY': 'secret-api-key',
                        'PACKAGE_ID': 'test-http-failure'},
                   ledger=ledger, transport=transport)
    with pytest.raises(RuntimeError) as caught:
        agent.run('fixed_information_writer', {'private_prompt': 'do not disclose me'})
    assert len(calls) == 1
    assert agent.receipts == []
    entries = [entry for _, row in store.rows.values() for entry in row['entries'].values()]
    assert len(entries) == 1
    assert entries[0]['status'] == 'reserved'
    assert entries[0]['charged_micro_usd'] == entries[0]['reserved_micro_usd'] > 0
    return caught.value


@pytest.mark.parametrize(('status', 'error_type'), [
    (401, 'authentication_error'), (429, 'rate_limit_error'), (529, 'overloaded_error')])
def test_http_error_preserves_safe_diagnostic_without_retry_or_settlement(status, error_type):
    error = fail_request(status, {'type': 'error', 'error': {'type': error_type,
        'message': 'secret-api-key and do not disclose me'}, 'request_id': 'req_011TEST12345678'})
    assert type(error).__name__ == 'ProviderHTTPError'
    assert str(error) == f'agent_http_{status}'
    assert error.diagnostic == {'status': status, 'role': 'fixed_information_writer',
        'model': 'claude-sonnet-5', 'error_type': error_type, 'request_id': 'req_011TEST12345678'}
    assert 'secret-api-key' not in json.dumps(vars(error))
    assert 'do not disclose me' not in repr(error)


@pytest.mark.parametrize('body', [
    {'error': {'type': 'secret-api-key', 'message': 'private text'},
     'request_id': 'req_bad\nsecret-api-key', 'prompt': 'private text'},
    {'error': {'type': {'nested': 'secret-api-key'}}, 'request_id': ['secret-api-key']},
    {'error': 'secret-api-key', 'request_id': 'secret-api-key'},
    {'error': {'type': 'authentication_error'}, 'request_id': 'req_' + 'a' * 1000},
    ['secret-api-key'], 'secret-api-key', None,
])
def test_untrusted_body_fields_are_omitted_not_serialized(body):
    error = fail_request(401, body)
    diagnostic = getattr(error, 'diagnostic', None)
    assert isinstance(diagnostic, dict)
    assert set(diagnostic) <= {'status', 'role', 'model', 'error_type'}
    assert 'secret-api-key' not in json.dumps(vars(error))
    assert 'private text' not in json.dumps(vars(error))


def test_missing_provider_metadata_is_not_fabricated():
    error = fail_request(529, {})
    assert getattr(error, 'diagnostic', None) == {
        'status': 529, 'role': 'fixed_information_writer', 'model': 'claude-sonnet-5'}


def test_exact_writer_estimate_never_reserves_or_calls_and_matches_real_bound():
    store=MemoryStore();ledger=Ledger(store,limit_micro_usd=None)
    calls=[]
    def transport(*args):
        calls.append(args);return {'status_code':429,'body':{}}
    agent=Agents(env={'ANTHROPIC_API_KEY':'offline','PACKAGE_ID':'test-estimate'},ledger=ledger,transport=transport)
    estimate=agent.estimate_fixed_writer({'test':'input'})
    assert not calls and not agent.receipts and store.rows=={}
    with pytest.raises(RuntimeError):agent.run('fixed_information_writer',{'test':'input'})
    _,row=store.read(__import__('daily_budget').day_key(ledger.now()))
    assert next(iter(row['entries'].values()))['reserved_micro_usd']==estimate
