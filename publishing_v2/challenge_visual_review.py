"""Exact-byte image-review evidence for NEW challenge sends, not semantic vision.

Diagnostics describe final photo crops, not template backgrounds. No helper
creates editorial pass flags or observations. A real source/crop/mobile review
is mandatory; complete, hash-bound prose cannot prove somebody looked.
"""
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile

from PIL import Image, ImageChops, ImageStat

TIMES = (0.5, 11.5)
OBSERVATIONS = ('subject', 'relevance', 'crop_visibility', 'brightness', 'spoiler_risk')
# Conservative prompts, NOT automatic aesthetic/identity/usefulness verdicts.
LOW_MEAN_LUMA = 65
DARK_PIXEL_LUMA = 40
HIGH_DARK_FRACTION = 0.60
HIGH_SIMILARITY = 0.94


def _require(ok, reason):
    if not ok:
        from .bundle_api import BundleError
        raise BundleError('Challenge image review: ' + reason)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _ref(spec):
    _require(isinstance(spec, dict) and isinstance(spec.get('path'), str)
             and re.fullmatch('[0-9a-f]{64}', str(spec.get('sha256', ''))), 'invalid asset reference')
    return {'path': spec['path'], 'sha256': spec['sha256']}


def _asset(spec, suffixes, maximum=100_000_000):
    ref = _ref(spec)
    name = ref['path']
    relative = PurePosixPath(name)
    _require(name and not relative.is_absolute() and '\\' not in name
             and all(p not in ('', '.', '..') for p in name.split('/')),
             'unsafe repository-local asset path')
    root = Path.cwd().resolve()
    path = root / name
    _require(path.suffix.lower() in suffixes and path.resolve().is_relative_to(root)
             and not any(p.is_symlink() for p in [path, *path.parents]), 'unsafe asset path or symlink')
    _require(0 < path.stat().st_size <= maximum, 'asset exceeds size limit')
    raw = path.read_bytes()
    _require(_sha(raw) == ref['sha256'], 'asset changed after image review')
    return raw


def _box(value):
    _require(isinstance(value, list) and len(value) == 4 and all(type(n) is int for n in value),
             'photo box must contain four finite integer coordinates')
    x1, y1, x2, y2 = value
    _require(0 <= x1 < x2 <= 1080 and 0 <= y1 < y2 <= 1920
             and x2-x1 >= 100 and y2-y1 >= 100, 'photo box outside video or too small')
    return value


def _context(media):
    data = getattr(media, 'snapshot', None)
    _require(isinstance(data, dict) and data.get('content_type') == 'challenge'
             and len(media) == 1 and Path(media[0][0]).suffix.lower() == '.mp4', 'one final challenge MP4 required')
    raw = media[0][1]
    review = data.get('video_review')
    _require(isinstance(review, dict) and review.get('video_sha256') == _sha(raw),
             'video review must bind final MP4 bytes')
    source_ref = _ref(review['source_manifest'])
    source = json.loads(_asset(source_ref, {'.json'}, 2_000_000))
    _require(isinstance(source, dict) and isinstance(source.get('media'), list), 'source manifest media required')
    sources = []
    for frame in source['media']:
        _require(isinstance(frame, dict) and isinstance(frame.get('source_assets'), list),
                 'source manifest source_assets required')
        sources.extend(_ref(s) for s in frame['source_assets'])
    _require(len(sources) == 2 and len({s['path'] for s in sources}) == 2
             and len({s['sha256'] for s in sources}) == 2, 'exactly two distinct source photographs required')
    for spec in sources:
        image = Image.open(io.BytesIO(_asset(spec, {'.png', '.jpg', '.jpeg', '.webp'})))
        image.verify()
    return raw, review, source_ref, sources


def _diagnostics(media, photos, context):
    raw, review, _, sources = context
    _require(isinstance(photos, list) and len(photos) == 2 and all(isinstance(p, dict) for p in photos),
             'both photographs must be reviewed once')
    refs = [_ref(p['source']) for p in photos]
    _require(refs == sources, 'photographs must cover exact source-manifest order once')
    boxes = [_box(p['box']) for p in photos]
    from .design_contract import SETTINGS
    geometry = json.loads(SETTINGS.read_bytes())['challenges']['approved_template_v2']['geometry']
    expected_boxes = [_box(geometry[key]) for key in ('left_photo', 'right_photo')]
    _require(boxes == expected_boxes, 'photo boxes must match current master geometry in source order')
    a, b = boxes
    _require(min(a[2], b[2]) <= max(a[0], b[0]) or min(a[3], b[3]) <= max(a[1], b[1]),
             'photo boxes must not overlap')
    frames = review.get('frames')
    _require(isinstance(frames, list) and all(isinstance(f, dict) for f in frames), 'reviewed decoded frames required')
    selected = []
    for at in TIMES:
        matches = [f for f in frames if f.get('at') == at]
        _require(len(matches) == 1, 'exact reviewed frames at 0.5 and 11.5 seconds required')
        selected.append(matches[0])
    result = {'photos': [{'source': s, 'box': box, 'crops': []} for s, box in zip(sources, boxes)],
              'pair_metrics': []}
    with tempfile.TemporaryDirectory(prefix='challenge-photo-review-') as tmp:
        movie = Path(tmp)/'final.mp4'
        movie.write_bytes(raw)
        for frame, at in zip(selected, TIMES):
            frozen = Image.open(io.BytesIO(_asset(frame, {'.png'}))).convert('RGB')
            output = Path(tmp)/f'{at}.png'
            subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-ss', str(at), '-i', str(movie),
                            '-frames:v', '1', '-threads', '1', str(output)],
                           check=True, capture_output=True, timeout=90)
            with Image.open(output) as decoded:
                actual = decoded.convert('RGB')
            _require(actual.size == frozen.size == (1080, 1920)
                     and actual.tobytes() == frozen.tobytes(), 'decoded frame differs from reviewed frame')
            crops = [actual.crop(box) for box in boxes]
            for photo, crop in zip(result['photos'], crops):
                gray = crop.convert('L')
                photo['crops'].append({'at': at, 'rgb_sha256': _sha(crop.tobytes()),
                    'mean_luma': round(ImageStat.Stat(gray).mean[0], 6),
                    'dark_fraction': round(sum(gray.histogram()[:DARK_PIXEL_LUMA])/(crop.width*crop.height), 6)})
            thumbs = [crop.resize((32, 32), Image.Resampling.BILINEAR) for crop in crops]
            difference = ImageChops.difference(*thumbs)
            similarity = round(1-sum(ImageStat.Stat(difference).mean)/(3*255), 6)
            result['pair_metrics'].append({'at': at, 'similarity': similarity})
    return result


def image_review_diagnostics(media, photos):
    """Return bound crop hashes/metrics ONLY. Caller must actually review assets.

    photos is [{source:{path,sha256}, box:[x1,y1,x2,y2]}, ...], matching the
    source manifest order. Does not manufacture a passed report or any prose.
    """
    return _guard(lambda: _diagnostics(media, photos, _context(media)))


def _note(value, label, seen):
    _require(isinstance(value, str), label + ' substantive observation required')
    normalized = ' '.join(value.casefold().split())
    _require(len(normalized) >= 32 and len(normalized.split()) >= 6
             and len(set(normalized.split())) >= 5
             and normalized not in seen, label + ' substantive, non-copied observation required')
    seen.add(normalized)


def _validate(media):
    context = _context(media)
    raw, review, source_ref, sources = context
    report = json.loads(_asset(review['image_review'], {'.json'}, 1_000_000))
    _require(isinstance(report, dict) and type(report.get('version')) is int and report['version'] == 1,
             'version 1 report required')
    _require(report.get('video_sha256') == _sha(raw) and report.get('source_manifest') == source_ref
             and report.get('source_assets') == sources, 'stale video or source-manifest coverage')
    _require(report.get('assessment') == 'passed' and isinstance(report.get('reviewer'), str)
             and report['reviewer'].strip() and type(report.get('mobile_width')) is int
             and report['mobile_width'] == 390, 'passed reviewer assessment at mobile_width 390 required')
    seen = set()
    _note(report.get('mobile_layout'), 'mobile layout', seen)
    photos = report.get('photos')
    actual = _diagnostics(media, photos, context)
    for supplied, measured in zip(photos, actual['photos']):
        _require(supplied.get('assessment') == 'passed', 'photo assessment must be passed')
        crops = supplied.get('crops')
        _require(isinstance(crops, list) and len(crops) == len(TIMES)
                 and all(isinstance(c, dict) and all(type(c.get(k)) in (int, float)
                         and math.isfinite(c[k]) for k in ('mean_luma', 'dark_fraction')) for c in crops),
                 'numeric finite crop diagnostics required')
        _require(crops == measured['crops'], 'crop hashes or diagnostics changed')
        notes = supplied.get('observations')
        _require(isinstance(notes, dict), 'per-photo observations required')
        for key in OBSERVATIONS:
            _note(notes.get(key), key, seen)
        if any(c['mean_luma'] < LOW_MEAN_LUMA or c['dark_fraction'] > HIGH_DARK_FRACTION
               for c in measured['crops']):
            _note(supplied.get('low_light_resolution'), 'low-light resolution', seen)
    metrics = report.get('pair_metrics')
    _require(isinstance(metrics, list) and len(metrics) == len(TIMES)
             and all(isinstance(m, dict) and type(m.get('similarity')) in (int, float)
                     and math.isfinite(m['similarity']) for m in metrics), 'numeric finite pair diagnostics required')
    _require(metrics == actual['pair_metrics'], 'pair similarity metrics changed')
    pair = report.get('pair')
    _require(isinstance(pair, dict) and pair.get('assessment') == 'passed', 'pair assessment required')
    _note(pair.get('distinct_information'), 'pair distinct information', seen)
    _note(pair.get('answer_spoiler'), 'pair answer spoiler', seen)
    if any(p['similarity'] >= HIGH_SIMILARITY for p in actual['pair_metrics']):
        _note(pair.get('similarity_resolution'), 'high-similarity resolution', seen)


def _guard(action):
    try:
        return action()
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError,
            subprocess.SubprocessError, Image.DecompressionBombError):
        _require(False, 'incomplete or invalid image review evidence; no publication')


def validate_challenge_images(media):
    """Require v1 evidence for a new challenge; historical reconciliation skips it."""
    return _guard(lambda: _validate(media))
