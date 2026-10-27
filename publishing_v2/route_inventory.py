"""Fail CI when executable routes change without an explicit inventory review.

This is change detection, not a security sandbox or proof of semantic safety.
Reviewers must inspect changed entry points before refreshing the baseline.
"""
import hashlib
import json
from pathlib import Path


def inventory(root):
    root=Path(root); result={}
    for path in sorted(root.rglob('*')):
        if not path.is_file():continue
        relative=path.relative_to(root)
        if any(part.startswith('.') and part!='.github' for part in relative.parts):continue
        if any(part in {'tests','node_modules','__pycache__','docs'} for part in relative.parts):continue
        executable=path.suffix in {'.py','.sh','.js','.mjs','.ts'}
        workflow=relative.parts[:2]==('.github','workflows') and path.suffix in {'.yml','.yaml'}
        if executable or workflow:
            result[relative.as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def verify(root, baseline):
    actual=inventory(root)
    changed=sorted(k for k in actual.keys()|baseline.keys() if actual.get(k)!=baseline.get(k))
    if changed:raise ValueError('Publication route review required: '+', '.join(changed))
    return len(actual)


if __name__=='__main__':
    count=verify(Path('.'),json.loads(Path('publishing_v2/route-inventory.json').read_text()))
    print(f'Executable route inventory verified: {count} files; no live calls')
