"""Offline transport recovery: retries are reads, never uncertain mutations."""
import io
import urllib.error
from unittest.mock import patch
import pytest
from publishing_v2.bundle_api import request, BundleError, HTTPFailure


def failure(code):
    return urllib.error.HTTPError('https://example.test', code, 'private body', {}, None)


@pytest.mark.parametrize('error', [failure(502), failure(503), failure(504), OSError('private transport')])
def test_transient_get_recovers_without_mutation(error):
    with patch('urllib.request.urlopen', side_effect=[error, io.BytesIO(b'{"status":"POSTED"}')]) as opened, patch('time.sleep'):
        assert request('https://example.test/post/known', {}) == {'status': 'POSTED'}
    assert [call.args[0].get_method() for call in opened.call_args_list] == ['GET', 'GET']


def test_get_retries_are_bounded_and_sanitized():
    with patch('urllib.request.urlopen', side_effect=failure(503)) as opened, patch('time.sleep') as slept:
        with pytest.raises(HTTPFailure, match='503') as caught:
            request('https://example.test/post/known', {})
    assert opened.call_count == 3
    assert [call.args[0] for call in slept.call_args_list] == [1, 2]
    assert all(call.kwargs['timeout'] == 45 for call in opened.call_args_list)
    assert 'private' not in str(caught.value)


@pytest.mark.parametrize('method', ['POST', 'PUT', 'PATCH', 'DELETE'])
@pytest.mark.parametrize('error', [failure(503), OSError('private transport')])
def test_mutation_is_never_retried(method, error):
    with patch('urllib.request.urlopen', side_effect=error) as opened, patch('time.sleep') as slept:
        with pytest.raises(BundleError):
            request('https://example.test/post', {}, method, b'{}')
    assert opened.call_count == 1
    slept.assert_not_called()


@pytest.mark.parametrize('error', [failure(400), failure(401), failure(403), failure(404), ValueError('bad JSON')])
def test_nontransient_reads_stop_immediately(error):
    with patch('urllib.request.urlopen', side_effect=error) as opened, patch('time.sleep') as slept:
        with pytest.raises(BundleError):
            request('https://example.test/post/known', {})
    assert opened.call_count == 1
    slept.assert_not_called()


def test_get_with_body_is_not_retried():
    with patch('urllib.request.urlopen', side_effect=failure(503)) as opened, patch('time.sleep') as slept:
        with pytest.raises(HTTPFailure):
            request('https://example.test/post/known', {}, 'GET', b'{}')
    assert opened.call_count == 1
    slept.assert_not_called()
