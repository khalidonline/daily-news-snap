"""Manual owner-reviewed composites: provenance is explicit, never a license claim.

Source files and output bytes are sealed by the revocable manifest. This route
does not participate in autonomous image selection or grant site-wide rights.
"""
import hashlib
import io
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit
from PIL import Image


def validate_owner_composite(data, root):
    from .bundle_api import BundleError

    def require(ok, reason):
        if not ok:
            raise BundleError('Composite: ' + reason)

    def asset(row, *, final=False):
        require(isinstance(row, dict), 'invalid asset')
        relative = row.get('path')
        require(isinstance(relative, str) and bool(relative), 'missing path')
        path = (root / relative).resolve()
        require(path.is_relative_to(root) and path.suffix.lower() in {'.png','.jpg','.jpeg'}, 'unsafe path')
        require(path.is_file() and 0 < path.stat().st_size <= 20_000_000, 'invalid asset size')
        raw = path.read_bytes()
        sha = row.get('sha256')
        require(isinstance(sha, str) and bool(re.fullmatch('[0-9a-f]{64}',sha))
                and hashlib.sha256(raw).hexdigest()==sha, 'asset changed after approval')
        try:
            with Image.open(io.BytesIO(raw)) as picture:
                require(getattr(picture,'n_frames',1)==1, 'animated asset')
                if final:
                    require(picture.size==(1080,1920), 'final dimensions must be 1080x1920')
                picture.verify()
            with Image.open(io.BytesIO(raw)) as picture:
                picture.load()
        except (OSError, ValueError):
            raise BundleError('Composite: invalid image') from None
        return path,raw

    review=data.get('owner_review')
    require(isinstance(review,dict), 'owner review required')
    require(isinstance(review.get('reference'),str) and len(review['reference'].strip())>=8, 'review reference required')
    try:
        reviewed=datetime.fromisoformat(review['reviewed_at'])
        expiry=datetime.fromisoformat(data['expires_at'])
        require(reviewed.tzinfo is not None and expiry.tzinfo is not None
                and reviewed<=datetime.now(timezone.utc)<expiry, 'invalid review time')
    except (KeyError,ValueError,TypeError):
        raise BundleError('Composite: invalid review time') from None
    frames=data.get('media')
    require(isinstance(frames,list) and 1<=len(frames)<=2 and all(isinstance(f,dict) for f in frames), 'one or two cards required')
    hashes=[f.get('sha256') for f in frames]
    require(review.get('approved_media_sha256')==hashes and len(set(hashes))==len(hashes), 'output review mismatch')
    title=data.get('title')
    require(isinstance(title,str) and 1<=len(title.strip())<=100, 'invalid title')
    selected=[]; source_hashes=[]
    for frame in frames:
        require(frame.get('kind') in {'info','story'}, 'public editorial cards only')
        provenance=frame.get('provenance',{})
        require(isinstance(provenance,dict) and provenance.get('usage')=='mixed_editorial_composite'
                and type(provenance.get('generated_components')) is bool, 'explicit mixed provenance required')
        sources=frame.get('source_assets')
        require(isinstance(sources,list) and 1<=len(sources)<=10, 'source assets required')
        for source in sources:
            asset(source)
            try:
                url=urlsplit(source.get('source_url',''))
                valid=url.scheme=='https' and bool(url.hostname) and not url.username and not url.password
            except ValueError:
                valid=False
            require(valid, 'source URL required')
            require(source.get('rights_status')=='owner_accepted_editorial_use', 'owner editorial decision required')
            for key in ('description','owner_reference'):
                require(isinstance(source.get(key),str) and len(source[key].strip())>=8, key+' required')
            source_hashes.append(source['sha256'])
        selected.append(asset(frame,final=True))
    require(review.get('approved_source_sha256')==source_hashes, 'source review mismatch')
    identity=hashlib.sha256(('executivesaudi:'+':'.join(hashes)).encode()).hexdigest()
    return identity,title,selected
