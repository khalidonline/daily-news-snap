"""Narrow owner-authorized challenge-video route with decoded-frame evidence.

Ordinary/unreviewed manual MP4s remain blocked. No production or repair here.
"""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
from PIL import Image, ImageChops, ImageStat


def validate_reviewed_video(data, root):
    from .bundle_api import BundleError
    def require(ok, message):
        if not ok: raise BundleError('Video review: ' + message)
    def asset(spec, suffix):
        path = (root/spec['path']).resolve()
        require(path.is_relative_to(root) and path.suffix.lower() in suffix, 'invalid asset path')
        require(0 < path.stat().st_size <= 100_000_000, 'invalid asset size')
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == spec['sha256'], 'asset changed after review')
        return path, raw
    def run(args):
        return subprocess.run(args, check=True, capture_output=True, timeout=90).stdout
    try:
        review = data.get('video_review', {})
        require(review.get('approved') is True and bool(review.get('authorization')), 'editorial evidence required')
        require(data.get('content_type') == 'challenge' and len(data['media']) == 1, 'one challenge video required')
        movie, raw = asset(data['media'][0], {'.mp4'})
        require(review.get('video_sha256') == hashlib.sha256(raw).hexdigest(), 'review does not bind final MP4')
        source_path, source_bytes = asset(review['source_manifest'], {'.json'})
        source = json.loads(source_bytes)
        require(source.get('approved') is True and source.get('account') == 'executivesaudi', 'source approval required')
        require(source.get('format') == 'owner-generated-design-v1', 'reviewed original artwork required')
        from .owner_design import validate_owner_design
        _, _, source_media = validate_owner_design(source, root)
        require(len(source_media) == 1, 'one approved source card required')
        audio, _ = asset(review['audio_reference'], {'.mp4', '.m4a', '.wav'})
        require(bool(review['audio_reference'].get('authorization')), 'audio authorization required')
        presentation = data['challenge_contract']['presentation']
        require((presentation.get('countdown_start'), presentation.get('countdown_end'),
                 presentation.get('answer_at')) == (3, 8, 8), 'preserve approved 3/8/8 timing')
        times = [0.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 11.5]
        frames = review['frames']
        require([f.get('at') for f in frames] == times, 'review intro, all five digits, and answer hold')
        probe = json.loads(run(['ffprobe','-v','error','-show_format','-of','json',str(movie)]))
        require(abs(float(probe['format']['duration'])-12) < .05, 'preserve 12-second duration')
        # Decoded PCM must equal the approved reference, with no audio shift.
        def pcm(path):
            return run(['ffmpeg','-v','error','-nostdin','-i',str(path),'-map','0:a:0',
                        '-f','s16le','-ar','48000','-ac','1','-'])
        require(pcm(movie) == pcm(audio), 'audio differs from approved reference or timing')
        with tempfile.TemporaryDirectory(prefix='reviewed-challenge-') as temp:
            for i, frame in enumerate(frames):
                _, reference = asset(frame, {'.png'})
                out = Path(temp)/f'{i}.png'
                run(['ffmpeg','-v','error','-nostdin','-ss',str(frame['at']),'-i',str(movie),
                     '-frames:v','1','-threads','1',str(out)])
                with Image.open(io.BytesIO(reference)) as expected, Image.open(out) as actual:
                    require(expected.size == actual.size == (1080,1920), 'decoded frame dimensions')
                    diff = ImageChops.difference(expected.convert('RGB'),actual.convert('RGB'))
                    require(max(ImageStat.Stat(diff).mean) <= 2, 'decoded frame differs from reviewed frame')
        digest = hashlib.sha256(raw).hexdigest()
        identity = hashlib.sha256(('executivesaudi:'+digest).encode()).hexdigest()
        return identity, str(data['title']), [(movie,raw)]
    except BundleError:
        raise
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        raise BundleError('Video review: incomplete or invalid evidence; no publication') from None
