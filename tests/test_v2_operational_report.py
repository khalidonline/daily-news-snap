import copy
import json
from datetime import datetime, timezone

from publishing_v2.autopilot import report

NOW = datetime(2026, 11, 4, 9, tzinfo=timezone.utc)
AT = NOW.isoformat()


def snapshot():
    return {'packages': [{'package_id': 'p', 'status': 'published',
             'expected_story_cards': 1,
             'story': {'observed_at': AT, 'data': {'1': {'status': 'POSTED', 'post_id': 's', 'placement': 'STORY'}}},
             'saved_story': {'observed_at': AT, 'data': {'identity': 'p', 'status': 'POSTED', 'post_id': 'a', 'confirmed_at': AT}}}]}



def test_separate_destinations_without_mutating_inputs():
    data = snapshot(); before = copy.deepcopy(data)
    result = report.operational_report(data, NOW)
    assert data == before
    p = result['packages'][0]
    assert p['story']['status'] == p['saved_story']['status'] == 'confirmed'
    assert p['story']['confirmed_at'] is None
    assert p['story']['observed_at'] == AT


def test_partial_story_and_saved_identity_mismatch_are_unresolved():
    data = snapshot(); data['packages'][0]['expected_story_cards'] = 2
    data['packages'][0]['saved_story']['data']['identity'] = 'other'
    p = report.operational_report(data, NOW)['packages'][0]
    assert p['story']['status'] == p['saved_story']['status'] == 'unresolved'
    assert p['status'] == 'published'  # state claim retained separately, not trusted as confirmation


def test_pending_saved_story_does_not_erase_confirmed_story():
    data = snapshot(); data['packages'][0]['saved_story']['data']['status'] = 'SENDING'
    p = report.operational_report(data, NOW)['packages'][0]
    assert p['story']['status'] == 'confirmed'
    assert p['saved_story']['status'] == 'unresolved'


def test_group_requires_complete_card_evidence():
    data = snapshot(); p = data['packages'][0]; p['expected_story_cards'] = 2
    p['story']['data'] = {'_group': {'status': 'POSTED', 'post_id': 'g', 'identity': 'p'},
        '1': {'status': 'POSTED', 'post_id': 'g', 'media_id': 'm1'},
        '2': {'status': 'POSTED', 'post_id': 'g', 'media_id': 'm2'}}
    assert report.operational_report(data, NOW)['packages'][0]['story']['status'] == 'confirmed'
    p['story']['data']['2']['status'] = 'SENDING'
    assert report.operational_report(data, NOW)['packages'][0]['story']['status'] == 'unresolved'


def test_cli_read_only_never_calls_sender(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'snapshot.json'; path.write_text(json.dumps(snapshot()))
    monkeypatch.setattr(report, 'request', lambda *a, **k: (_ for _ in ()).throw(AssertionError('network')))
    monkeypatch.setattr(report, 'GitHubJournal', lambda *a, **k: (_ for _ in ()).throw(AssertionError('journal')))
    assert report.main(['--read-only', str(path), '--now', AT, '--format', 'json']) == 0
    assert json.loads(capsys.readouterr().out)['read_only'] is True


def test_arabic_render_only_covers_operations():
    result = report.operational_report(snapshot(), NOW)
    assert 'cost' not in result
    text = report.render_operational(result)
    assert 'Story' in text and 'Saved Story' in text
    assert '$' not in text and 'تكلفة' not in text
    assert 'غير معلومة' in report.render_operational(report.operational_report({}, NOW))


def test_group_rejects_duplicate_or_non_string_media_ids():
    for bad in ['m1', True, 123, []]:
        data = snapshot(); p = data['packages'][0]; p['expected_story_cards'] = 2
        p['story']['data'] = {'_group': {'identity': 'p', 'status': 'POSTED', 'post_id': 'g'},
            '1': {'status': 'POSTED', 'post_id': 'g', 'media_id': 'm1'},
            '2': {'status': 'POSTED', 'post_id': 'g', 'media_id': bad}}
        assert report.operational_report(data, NOW)['packages'][0]['story']['status'] == 'unresolved'


def test_non_group_story_rejects_duplicate_post_ids():
    data = snapshot(); p = data['packages'][0]; p['expected_story_cards'] = 2
    p['story']['data']['2'] = copy.deepcopy(p['story']['data']['1'])
    assert report.operational_report(data, NOW)['packages'][0]['story']['status'] == 'unresolved'


def test_render_labels_stale_receipt_observations():
    data = snapshot(); data['packages'][0]['story']['observed_at'] = '2026-11-03T09:00:00Z'
    text = report.render_operational(report.operational_report(data, NOW))
    assert 'قراءة قديمة' in text


def test_destination_identity_requires_nonempty_string():
    for bad in [None, '', [], ['p'], 123]:
        data = snapshot(); p = data['packages'][0]; p['package_id'] = bad
        p['saved_story']['data']['identity'] = bad
        p['expected_story_cards'] = 2
        p['story']['data'] = {'_group': {'identity': bad, 'status': 'POSTED', 'post_id': 'g'},
            '1': {'status': 'POSTED', 'post_id': 'g', 'media_id': 'm1'},
            '2': {'status': 'POSTED', 'post_id': 'g', 'media_id': 'm2'}}
        result = report.operational_report(data, NOW)['packages'][0]
        assert result['story']['status'] == result['saved_story']['status'] == 'unresolved'


def test_report_uses_saudi_date_and_never_infers_observation_time():
    data = snapshot()
    for at in [None, 'bad', '2026-11-05T00:00:00Z']:
        data['packages'][0]['story']['observed_at'] = at
        assert report.operational_report(data, NOW)['packages'][0]['story']['observed_at'] is None
    assert report.operational_report({}, datetime(2026, 11, 4, 21, tzinfo=timezone.utc))['day'] == '2026-11-05'
