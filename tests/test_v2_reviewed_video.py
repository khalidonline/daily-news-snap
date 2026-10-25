import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from PIL import Image
from publishing_v2.bundle_api import load_package, BundleError
from tests.test_v2_challenge_contract import movie_bytes, video_media
from publishing_v2.reviewed_video import validate_reviewed_video

def approved_package():
    root = Path(__file__).resolve().parents[1]
    path = root/'approved/wheels-video-20261025/manifest.json'
    if not path.exists(): pytest.skip('Owner-approved integration fixture not present')
    return root, json.loads(path.read_text())

def test_owner_approved_video_decodes_and_preserves_approved_audio():
    root, data = approved_package()
    identity, title, media = validate_reviewed_video(data, root)
    assert len(identity) == 64 and len(media) == 1
    assert hashlib.sha256(media[0][1]).hexdigest() == 'b010b8d4f46d91230cb6f29553e0cc5b980de6c351302db2b1d825b421cf7158'

def test_different_countdown_digit_cannot_pass_frame_review():
    root, data = approved_package()
    data['video_review']['frames'][1].update({k:v for k,v in data['video_review']['frames'][2].items() if k!='at'})
    with pytest.raises(BundleError, match='decoded frame differs'):
        validate_reviewed_video(data, root)

@pytest.mark.parametrize('mutation', ['hash', 'frames', 'approval', 'timing'])
def test_reviewed_video_incomplete_or_changed_evidence_blocks(mutation):
    root, data = approved_package()
    if mutation == 'hash': data['media'][0]['sha256']='0'*64
    if mutation == 'frames': data['video_review']['frames'].pop()
    if mutation == 'approval': data['video_review']['approved']=False
    if mutation == 'timing': data['challenge_contract']['presentation']['answer_at']=7
    with pytest.raises(BundleError): validate_reviewed_video(data, root)


def test_new_video_format_requires_editorial_frame_evidence(movie_bytes, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    raw = movie_bytes[True]
    (tmp_path/'video.mp4').write_bytes(raw)
    data = video_media(raw, tmp_path).snapshot
    data.update(format='reviewed-challenge-video-v1', approved=True,
        account='executivesaudi', title='توقع السعر',
        expires_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
        media=[{'kind':'info','path':'video.mp4','sha256':hashlib.sha256(raw).hexdigest()}])
    (tmp_path/'manifest.json').write_text(json.dumps(data))
    with pytest.raises(BundleError, match='Video review'):
        load_package('manifest.json')
