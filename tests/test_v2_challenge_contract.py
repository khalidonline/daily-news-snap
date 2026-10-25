import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from publishing_v2.bundle_api import BundleError, publish, publish_group
from tests.test_v2_bundle import Client, Journal
from publishing_v2.bundle_api import ApprovedMedia
from publishing_v2.challenge_contract import validate_challenge
import json
import subprocess


@pytest.fixture(scope='module')
def movie_bytes(tmp_path_factory):
    root = tmp_path_factory.mktemp('movies')
    result = {}
    for audio in (True, False):
        path = root / ('sound.mp4' if audio else 'silent.mp4')
        args = ['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=white:s=1080x1920:r=1']
        if audio:
            args += ['-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100']
        subprocess.run(args + ['-t', '5', '-c:v', 'libx264', '-threads', '1',
                              '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', str(path)],
                       check=True, capture_output=True, timeout=60)
        result[audio] = path.read_bytes()
    return result


def video_media(raw, tmp_path):
    review = dict.fromkeys(('audio_audible', 'countdown_visible_and_running',
        'answer_reveal_correct', 'brand_colors_match', 'safe_area_checked',
        'sharing_cta_visible', 'no_diacritics', 'text_readable'), True)
    review.update(sha256=hashlib.sha256(raw).hexdigest(), reference='Test-only human review fixture')
    data = {'content_type': 'challenge', 'challenge_contract': {'version': 1,
        'final_video_review': review, 'presentation': {'countdown_start': 0,
            'countdown_end': 3, 'answer_at': 4, 'audio_reference': 'test-sine'}}}
    # Generated test clip verifies streams only. Human flags are not evidence
    # that this test fixture visually contains a countdown or an answer.
    return ApprovedMedia([(tmp_path/'video.mp4', raw)],
        Path.cwd()/'test-manifest.json', data)


@pytest.mark.parametrize('check', ['audio_audible', 'countdown_visible_and_running',
    'answer_reveal_correct', 'brand_colors_match', 'safe_area_checked',
    'sharing_cta_visible', 'no_diacritics', 'text_readable'])
def test_missing_final_video_review_item_blocks(check, tmp_path):
    media = video_media(b'not-needed', tmp_path)
    del media.snapshot['challenge_contract']['final_video_review'][check]
    with pytest.raises(BundleError, match='review every'):
        validate_challenge('توقع السعر', media)


def test_stale_review_rejected(tmp_path):
    media = video_media(b'old', tmp_path)
    media[0] = (media[0][0], b'new')
    with pytest.raises(BundleError, match='stale'):
        validate_challenge('توقع السعر', media)


def test_actual_audio_required_even_if_checklist_claims_it(movie_bytes, tmp_path):
    media = video_media(movie_bytes[False], tmp_path)
    with pytest.raises(BundleError, match='audio stream'):
        validate_challenge('توقع السعر', media)


def test_valid_review_and_actual_streams_pass(movie_bytes, tmp_path):
    validate_challenge('توقع السعر', video_media(movie_bytes[True], tmp_path))


def test_explicit_challenge_cannot_hide_behind_generic_title(tmp_path):
    media = video_media(b'x', tmp_path)
    media[0] = (tmp_path/'card.png', b'x')
    with pytest.raises(BundleError, match='MP4'):
        validate_challenge('عنوان عادي', media)


def test_revision_cannot_silently_drop_old_presentation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    media = video_media(b'x', tmp_path)
    old = {'challenge_contract': {'presentation': {'audio_reference': 'original'}}}
    raw = json.dumps(old).encode()
    (tmp_path/'old.json').write_bytes(raw)
    media.snapshot['challenge_contract']['previous'] = {
        'path': 'old.json', 'sha256': hashlib.sha256(raw).hexdigest()}
    with pytest.raises(BundleError, match='preserve'):
        validate_challenge('توقع السعر', media)


@pytest.mark.parametrize('title', ['توقع السعر', 'توقّع السعر: كفرات أبل', 'من بدأ أول', 'توقع المكان', 'أعلى أو أقل', 'نزل بالسوق؟'])
def test_static_challenge_never_reaches_upload(title):
    client, journal = Client(), Journal()
    with pytest.raises(BundleError, match='Challenge'):
        publish(client, journal, title, [(Path('card.png'), b'png')])
    assert client.sent == []
    assert journal.state == {}


def test_group_cannot_bypass_challenge_contract():
    client, journal = Client(), Journal()
    with pytest.raises(BundleError, match='Challenge'):
        publish_group(client, journal, 'توقع السعر', [(Path('a.png'), b'a'), (Path('b.png'), b'b')], 'a'*64)
    assert client.sent == []


def test_completed_challenge_is_not_recreated():
    client, journal = Client(), Journal()
    journal.state = {'1': {'status': 'POSTED', 'post_id': 'existing'}}
    publish(client, journal, 'توقع السعر', [(Path('card.png'), b'png')])
    assert client.sent == []
