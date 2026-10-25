import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from PIL import Image
from publishing_v2.bundle_api import load_package, BundleError
from tests.test_v2_challenge_contract import movie_bytes, video_media


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
