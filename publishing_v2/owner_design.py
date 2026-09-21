"""Trusted owner-reviewed original artwork, never an autonomous rights decision.

This format is authored in the repository only after human review of exact
ChatGPT-generated illustrations. Library IDs record provenance; they are NOT
remote proof of ownership. External/reference photos must use the ordinary
licensed-image route. Neither the writer nor automatic publication accepts this
format. Pixels are decoded for validation, but never resized or rewritten.
"""
import hashlib
import io
import re
from datetime import datetime, timezone
from PIL import Image


def validate_owner_design(data, root):
    # Imported here to avoid a cycle: BundleError remains the public CLI error.
    from .bundle_api import BundleError
    review = data.get('owner_review', {})
    frames = data.get('media', [])
    if (not isinstance(review, dict) or not isinstance(frames, list)
            or not 1 <= len(frames) <= 10):
        raise BundleError('owner_review_required')
    reference = review.get('reference')
    if not isinstance(reference, str) or not 8 <= len(reference.strip()) <= 500:
        raise BundleError('owner_review_reference_required')
    try:
        reviewed = datetime.fromisoformat(review['reviewed_at'])
        expires = datetime.fromisoformat(data['expires_at'])
        if reviewed.tzinfo is None or not reviewed < expires or reviewed > datetime.now(timezone.utc):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise BundleError('invalid_owner_review_time') from None
    if not all(isinstance(f, dict) for f in frames):
        raise BundleError('invalid_owner_design_frame')
    hashes = [f.get('sha256') for f in frames]
    if (any(not isinstance(h, str) or not re.fullmatch(r'[0-9a-f]{64}', h) for h in hashes)
            or review.get('approved_media_sha256') != hashes):
        raise BundleError('owner_review_media_mismatch')
    if len(set(hashes)) != len(hashes):
        raise BundleError('Duplicate card in package')
    title = data.get('title')
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 100:
        raise BundleError('invalid_owner_design_title')
    media, assets = [], set()
    for frame in frames:
        provenance = frame.get('provenance')
        if (frame.get('kind') not in {'info', 'story'} or not isinstance(provenance, dict)
                or provenance.get('provider') != 'openai_imagegen'
                or provenance.get('usage') != 'illustration'
                or provenance.get('third_party_assets') is not False
                or frame.get('image') or frame.get('public_attribution')):
            raise BundleError('original_generated_illustration_required')
        ident = provenance.get('library_file_id')
        if not isinstance(ident, str) or not re.fullmatch(r'libfile_[0-9a-f]{32}', ident):
            raise BundleError('generated_asset_provenance_required')
        if ident in assets:
            raise BundleError('duplicate_generated_asset')
        assets.add(ident)
        if not isinstance(frame.get('path'), str):
            raise BundleError('invalid_owner_design_path')
        source = (root / frame['path']).resolve()
        if not source.is_relative_to(root) or source.suffix.lower() != '.png':
            raise BundleError('Unsupported owner design path')
        if not 0 < source.stat().st_size <= 20_000_000:
            raise BundleError('invalid_owner_design_size')
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != frame['sha256']:
            raise BundleError('Media changed after approval')
        try:
            with Image.open(io.BytesIO(raw)) as picture:
                w, h = picture.size
                if (picture.format != 'PNG' or getattr(picture, 'n_frames', 1) != 1
                        or not 512 <= w <= 4096 or not 900 <= h <= 8192
                        or abs(w * 16 - h * 9) > 16):
                    raise ValueError()
                picture.verify()
            # Verify PNG structure AND decode pixels to reject truncated streams.
            with Image.open(io.BytesIO(raw)) as picture:
                picture.load()
        except Exception:
            raise BundleError('invalid_owner_design_image') from None
        media.append((source, raw))
    identity = hashlib.sha256(('executivesaudi:' + ':'.join(hashes)).encode()).hexdigest()
    return identity, title, media
