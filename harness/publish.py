"""
Publish orchestrator - turn photos from the Baidu Netdisk collection link
into the online gallery.

Workflow:
  1. Scan incoming/ for image files (download them from the netdisk first)
  2. Hash each file (SHA-1) -> dedupe against existing manifest
  3. Copy original into gallery/originals/<hash>_<name>
  4. Generate thumbnail gallery/thumbnails/<hash>.jpg
  5. Add entry to gallery/data.json
  6. Move processed files into incoming/done/ (kept for reference)
  7. Validate output

Exit codes:
  0 = OK (maybe nothing new)
  1 = error
  2 = nothing to publish (no new photos) -> caller can skip git push

Usage:
  python harness/publish.py
"""
import sys
import json
import shutil
import hashlib
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from harness import manifest
from harness.thumbnail import generate_thumbnail, get_image_dimensions

# Register HEIC/HEIF support so iPhone photos work (requires pillow-heif)
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

# ── Paths ────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / 'config.json'
INCOMING_DIR = ROOT / 'incoming'
DONE_DIR = INCOMING_DIR / 'done'
THUMB_DIR = ROOT / 'gallery' / 'thumbnails'
ORIG_DIR = ROOT / 'gallery' / 'originals'

# Image extensions we can process (HEIC needs pillow-heif)
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.heic', '.heif'}
# Files that look like images but we cannot process (e.g. zip, raw)
SKIP_HINT = {'.zip', '.rar', '.7z', '.cr2', '.nef', '.arw', '.dng', '.tiff', '.tif', '.mov', '.mp4'}


def load_config():
    """Load config.json."""
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def file_hash(path: Path) -> str:
    """SHA-1 hex digest of file content (dedupe key)."""
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def scan_incoming() -> dict:
    """
    Scan incoming/ for files.
    Returns {'images': [Path], 'skipped': [(Path, reason)]}.
    """
    images, skipped = [], []
    if not INCOMING_DIR.exists():
        return {'images': images, 'skipped': skipped}

    for f in sorted(INCOMING_DIR.iterdir()):
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        if ext in IMAGE_EXTS:
            images.append(f)
        elif ext in SKIP_HINT:
            skipped.append((f, f'unsupported format ({ext}) - upload as JPG/PNG'))
        else:
            skipped.append((f, f'not an image ({ext or "no extension"})'))
    return {'images': images, 'skipped': skipped}


def main():
    config = load_config()

    # 1. Scan
    print('[1/5] Scanning incoming/ folder...')
    found = scan_incoming()
    if not found['images']:
        print('  No new photos found in incoming/.')
        if found['skipped']:
            for f, reason in found['skipped']:
                print(f'  [SKIP] {f.name} - {reason}')
        print('\nNothing to publish.')
        return 2
    if found['skipped']:
        for f, reason in found['skipped']:
            print(f'  [SKIP] {f.name} - {reason}')
    print(f'  Found {len(found["images"])} photo(s) to process.')

    # 2. Group identical files by content hash.
    #    Per group pick the BEST filename (shortest) as primary - so a copy
    #    named "IMG_0001(1).jpg" never shadows the original "IMG_0001.jpg".
    #    Note: on Windows, Path sorting is case-insensitive, so we must NOT
    #    rely on sorted() order for choosing the primary file.
    print('[2/5] Hashing files (dedupe)...')
    groups = {}
    for f in found['images']:
        try:
            h = file_hash(f)
        except OSError as e:
            print(f'  [SKIP] {f.name} - READ ERROR: {e}')
            continue
        groups.setdefault(h, []).append(f)

    to_process = []
    for h, files in groups.items():
        primary = min(files, key=lambda p: (len(p.name), p.name.lower()))
        to_process.append((h, primary))
        for dup in files:
            if dup is not primary:
                shutil.move(str(dup), str(DONE_DIR / dup.name))
                print(f'  [DUP] {dup.name} - same photo as {primary.name}, skipped')
    print(f'  {len(to_process)} unique photo(s) after dedupe.')

    # 3. Load manifest + keep gallery meta (title/subtitle/password)
    print('[3/5] Loading gallery manifest...')
    m = manifest.load_manifest()
    manifest.update_gallery_meta(
        m,
        config['gallery']['title'],
        config['gallery']['subtitle'],
        config['gallery'].get('password_hash', '')
    )
    existing_ids = {p['id'] for p in m['photos']}

    # 4. Process unique new files
    print('[4/5] Processing photos...')
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    ORIG_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)

    new_items = []
    for h, f in to_process:
        photo_id = h[:12]
        if photo_id in existing_ids:
            print(f'  [DUP] {f.name} - already in gallery, skip')
            shutil.move(str(f), str(DONE_DIR / f.name))
            continue
        new_items.append((h, f))

    if not new_items:
        print('\nNo new photos after dedupe - nothing to publish.')
        return 2

    added, failed = 0, 0
    for i, (h, f) in enumerate(new_items, 1):
        photo_id = h[:12]
        try:
            # Copy original (unique name: <hash>_<original name>)
            orig_name = f'{h[:12]}_{f.name}'
            orig_path = ORIG_DIR / orig_name
            if not orig_path.exists():
                shutil.copy2(f, orig_path)

            # Generate thumbnail (named by hash -> never collides)
            thumb_name = generate_thumbnail(
                str(f),
                str(THUMB_DIR),
                max_width=config['gallery'].get('thumbnail_width', 480),
                quality=config['gallery'].get('thumbnail_quality', 85),
                out_name=f'{h[:12]}.jpg',
            )
            dims = get_image_dimensions(str(f))
        except Exception as e:
            print(f'  [{i}/{len(new_items)}] {f.name} - IMAGE ERROR: {e}')
            if orig_path.exists():
                orig_path.unlink()
            failed += 1
            continue

        manifest.add_photo(
            m,
            {'file_id': photo_id, 'name': f.name, 'size': f.stat().st_size},
            thumb_name,
            original=f'originals/{orig_name}',
            dimensions=dims,
        )
        existing_ids.add(photo_id)
        added += 1
        print(f'  [{i}/{len(new_items)}] Added {f.name}')

        # Archive processed file
        shutil.move(str(f), str(DONE_DIR / f.name))

    # 5. Save + validate
    print('[5/5] Saving manifest...')
    manifest.save_manifest(m)

    from harness.validate import validate_all
    issues = validate_all()

    print(f'\nDone. Added {added}, failed {failed}. '
          f'Total {len(m["photos"])} photos in gallery.')
    if issues or failed:
        print('  Issues found - review output above.')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
