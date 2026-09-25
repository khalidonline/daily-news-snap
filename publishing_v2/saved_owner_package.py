"""Explicit preparation and sealed-file delivery; never regenerate during delivery."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from .autopilot.policy import seal, verify_seal

def save_reviewed(package, paths, output):
    output=Path(output).resolve()
    names=[str(Path(p).resolve().relative_to(output)) for p in paths]
    record={'format':'saved-owner-v1','package':package,'paths':names,'approval':seal(package,paths)}
    target=output/'reviewed-package.json'
    target.write_text(json.dumps(record,ensure_ascii=False,indent=2))
    return target

def publish_saved(manifest, expected_title):
    manifest=Path(manifest).resolve(); record=json.loads(manifest.read_text())
    if record.get('format')!='saved-owner-v1' or record['package']['title']!=expected_title:
        raise ValueError('saved_package_identity_mismatch')
    paths=[(manifest.parent/p).resolve() for p in record['paths']]
    if any(not p.is_relative_to(manifest.parent) or not p.is_file() for p in paths):
        raise ValueError('saved_media_missing_or_unsafe')
    verify_seal(record['package'],paths,record['approval'],datetime.now(timezone.utc))
    from .autopilot.runtime import publish_package
    return publish_package(record['package'],paths)

def preparation_requested(title):
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['prepare','publish'],default='publish')
    parser.add_argument('--manifest',type=Path)
    args=parser.parse_args()
    if args.mode=='prepare': return True
    if not args.manifest: parser.error('publish requires --manifest; restore the saved reviewed artifact, never regenerate')
    print(json.dumps(publish_saved(args.manifest,title),ensure_ascii=False))
    return False
