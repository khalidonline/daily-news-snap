"""Read-only, dated cleanup evidence; never repairs, deletes or publishes.

This index covers tracked repository content, not remote Library or receipt
branches. Those stores must remain untouched by cleanup.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

PROTECTED_ROOTS = frozenset({'approved','cards','images','drafts','state','review',
                           'reviews','editorial','assets','fonts','evaluation'})
CODE_SUFFIXES = frozenset({'.py','.sh','.js','.mjs','.ts','.tsx','.jsx'})
OPERATIONAL_EXCEPTIONS = frozenset({
    '.github/workflows-disabled/story-approved-to-telegram.yml',
    '.github/workflows-disabled/story-approval-binding-ci.yml',
    'tests/test_story_approval_artifact_binding.py',
    'publishing_v2/route-inventory.json',
})


def checked_path(root, name):
    root = Path(root).resolve()
    path = Path(name)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('Unsafe preservation path: '+str(name))
    target = root/path
    if any(p.is_symlink() for p in [target, *target.parents] if p != root):
        raise ValueError('Symlink is not preservation evidence: '+str(name))
    if not target.resolve().is_relative_to(root):
        raise ValueError('Preservation path escapes root')
    return target


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def snapshot(root, tracked_paths):
    files = {}
    for name in sorted(tracked_paths):
        path = checked_path(root, name)
        relative = Path(name)
        if name in OPERATIONAL_EXCEPTIONS:
            continue
        if relative.parts[0] in PROTECTED_ROOTS or relative.suffix not in CODE_SUFFIXES:
            files[name] = sha256(path)
    return files


def verify(root, files):
    if not isinstance(files, dict) or not files:
        raise ValueError('Empty or invalid preservation index')
    for name, expected in files.items():
        if sha256(checked_path(root, name)) != expected:
            raise ValueError('Protected content changed: '+name)
    return len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', action='store_true', help='Print index only; does not save')
    parser.add_argument('--index', default='archive/content-preservation-20261031.json')
    args = parser.parse_args()
    root = Path.cwd()
    if args.snapshot:
        paths = subprocess.check_output(['git','ls-files','-z'], cwd=root).decode().split('\0')
        base = subprocess.check_output(['git','rev-parse','HEAD'], cwd=root).decode().strip()
        print(json.dumps({'version':1,'base_commit':base,
                          'operational_exceptions':sorted(OPERATIONAL_EXCEPTIONS),
                          'files':snapshot(root,[p for p in paths if p])},ensure_ascii=False,indent=2))
    else:
        record = json.loads(checked_path(root,args.index).read_text())
        print(f'Protected files unchanged: {verify(root,record["files"])}')


if __name__ == '__main__':
    main()
