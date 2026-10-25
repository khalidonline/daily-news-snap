"""Fail-closed challenge delivery contract; never generates or repairs media.

Stream/audio checks are automated. Countdown, answer, typography and palette
are explicit reviews of the final video, hash-bound, not inferred from a still.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile
import unicodedata


def _normal(text):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', str(text))
                           if not unicodedata.combining(c) and c != 'ـ').split())


def is_challenge(title, data=None):
    data = data or {}
    markers = ('توقع السعر', 'توقع المكان', 'من بدا اول', 'اعلى او اقل',
               'نزل بالسوق', 'تحدي', 'challenge', 'wheels-')
    searchable = _normal(str(title) + ' ' + str(data.get('title', '')) + ' ' +
                         ' '.join(str(f.get('path', '')) for f in data.get('media', [])
                                  if isinstance(f, dict))).lower()
    return (data.get('content_type') == 'challenge' or 'challenge_contract' in data
            or any(marker in searchable for marker in markers))


def _fail(reason):
    from .bundle_api import BundleError
    raise BundleError('Challenge: ' + reason)


def validate_challenge(title, media):
    data = getattr(media, 'snapshot', {})
    if not is_challenge(title, data):
        return
    if not data or data.get('content_type') != 'challenge':
        _fail('explicit challenge manifest required; never send a still as a fallback')
    if len(media) != 1 or Path(media[0][0]).suffix.lower() != '.mp4':
        _fail('one final MP4 with audio, countdown and answer required')
    raw = media[0][1]
    digest = hashlib.sha256(raw).hexdigest()
    contract = data.get('challenge_contract', {})
    if not isinstance(contract, dict) or contract.get('version') != 1:
        _fail('final-video checklist missing')
    review = contract.get('final_video_review', {})
    checks = ('audio_audible', 'countdown_visible_and_running', 'answer_reveal_correct',
              'brand_colors_match', 'safe_area_checked', 'sharing_cta_visible',
              'no_diacritics', 'text_readable')
    if (not isinstance(review, dict) or review.get('sha256') != digest
            or not isinstance(review.get('reference'), str) or not review['reference'].strip()
            or any(review.get(check) is not True for check in checks)):
        _fail('review every required feature on the exact final video; stale reviews rejected')
    # A revision inherits the approved timing/audio contract. A layout edit
    # cannot silently change those settings. Paths are repo-local, hash-bound.
    previous = contract.get('previous')
    if previous is not None:
        try:
            root = Path.cwd().resolve()
            path = (root / previous['path']).resolve()
            if not path.is_relative_to(root): raise ValueError()
            old_bytes = path.read_bytes()
            if hashlib.sha256(old_bytes).hexdigest() != previous['sha256']: raise ValueError()
            old = json.loads(old_bytes)['challenge_contract']
            if contract.get('presentation') != old.get('presentation'): raise ValueError()
        except (OSError, ValueError, KeyError, TypeError):
            _fail('revision must preserve the approved presentation contract')
    try:
        # Probe the bytes being uploaded, NOT a possibly changed path or preview.
        with tempfile.TemporaryDirectory(prefix='challenge-review-') as tmp:
            movie = Path(tmp) / 'final.mp4'
            movie.write_bytes(raw)
            result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams',
                '-show_format', '-of', 'json', str(movie)], check=True,
                capture_output=True, timeout=60)
            probe = json.loads(result.stdout)
            videos = [s for s in probe['streams'] if s.get('codec_type') == 'video']
            audios = [s for s in probe['streams'] if s.get('codec_type') == 'audio']
            duration = float(probe['format']['duration'])
            if (len(videos) != 1 or len(audios) != 1 or videos[0].get('width') != 1080
                    or videos[0].get('height') != 1920 or not 5 <= duration <= 60):
                _fail('final video must be 1080x1920, 5–60s, with an audio stream')
            presentation = contract['presentation']
            start, end, answer = (float(presentation[k]) for k in
                                  ('countdown_start', 'countdown_end', 'answer_at'))
            if not (0 <= start < end <= answer < duration):
                _fail('countdown and answer timing invalid')
            if not presentation.get('audio_reference'):
                _fail('approved audio reference required')
            sound = subprocess.run(['ffmpeg', '-nostdin', '-v', 'info', '-i', str(movie),
                '-map', '0:a:0', '-af', 'volumedetect', '-f', 'null', '-'],
                check=True, capture_output=True, timeout=90)
            match = re.search(r'mean_volume:\s*(-?\d+(?:\.\d+)?|-inf) dB', sound.stderr.decode())
            if not match or not math.isfinite(float(match[1])) or float(match[1]) < -50:
                _fail('audio missing or effectively silent')
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        _fail('final-video verification unavailable or invalid; no upload')
