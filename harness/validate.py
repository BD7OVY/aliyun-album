"""
Output validation - checks gallery integrity after sync.

Verifies:
  1. data.json exists and parses as valid JSON
  2. Every thumbnail referenced in manifest exists on disk
  3. Every photo has a share_url (non-empty)
  4. No orphan thumbnail files (on disk but not in manifest)
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
MANIFEST_PATH = ROOT / 'gallery' / 'data.json'
THUMB_DIR = ROOT / 'gallery' / 'thumbnails'


def validate_all():
    """Run all validations. Returns list of issues (empty = all good)."""
    issues = []

    # 1. Manifest exists and is valid JSON
    if not MANIFEST_PATH.exists():
        issues.append('FAIL: gallery/data.json does not exist')
        _print_report(issues)
        return issues

    try:
        with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        issues.append(f'FAIL: data.json is not valid JSON: {e}')
        _print_report(issues)
        return issues

    photos = data.get('photos', [])
    print(f'[VALIDATE] {len(photos)} photos in manifest')

    # 2. Every thumbnail exists on disk
    manifest_thumbs = set()
    for p in photos:
        thumb = p.get('thumbnail', '')
        manifest_thumbs.add(thumb)
        thumb_path = THUMB_DIR / thumb
        if not thumb_path.exists():
            issues.append(f'MISSING thumbnail: {thumb} (photo: {p["name"]})')

    # 3. Every photo has a share_url
    for p in photos:
        if not p.get('share_url'):
            issues.append(f'EMPTY share_url for: {p["name"]}')

    # 4. Orphan thumbnails (on disk but not in manifest)
    if THUMB_DIR.exists():
        disk_thumbs = {f.name for f in THUMB_DIR.iterdir()
                       if f.is_file() and f.name != '.gitkeep'}
        orphans = disk_thumbs - manifest_thumbs
        for o in orphans:
            issues.append(f'ORPHAN thumbnail: {o} (not in manifest)')

    _print_report(issues)
    return issues


def _print_report(issues):
    if not issues:
        print('[VALIDATE] All checks passed.')
    else:
        print(f'[VALIDATE] {len(issues)} issue(s) found:')
        for i in issues:
            print(f'  - {i}')


if __name__ == '__main__':
    validate_all()
