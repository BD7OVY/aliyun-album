"""
Sync orchestrator - the main harness entry point.

Flow:
  1. Load config + .env
  2. Connect to Aliyun Drive
  3. List image files in album folder
  4. Diff with existing manifest -> new / removed
  5. For each new file: download -> thumbnail -> share link -> add to manifest
  6. For each removed file: delete thumbnail + manifest entry
  7. Save manifest
  8. Validate output

Usage:
  python harness/sync.py              # normal sync
  python harness/sync.py --mock        # mock mode for testing without API
  python harness/sync.py --set-pass    # set gallery access password
"""
import sys
import os
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from harness import manifest
from harness.thumbnail import generate_thumbnail, get_image_dimensions

# ── Paths ────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / 'config.json'
ENV_PATH = ROOT / '.env'
THUMB_DIR = ROOT / 'gallery' / 'thumbnails'
ORIG_DIR = ROOT / 'gallery' / 'originals'


def load_env():
    """Load .env file into os.environ."""
    if not ENV_PATH.exists():
        return {}
    env = {}
    for line in ENV_PATH.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            k, v = line.split('=', 1)
            k = k.strip()
            v = v.strip()
            env[k] = v
            os.environ[k] = v
    return env


def load_config():
    """Load config.json."""
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def mock_sync(config):
    """Generate mock data for testing without Aliyun Drive access."""
    print('[MOCK] Generating test data...')

    # Start fresh so repeated mock runs do not accumulate
    manifest_data = manifest.new_manifest()
    manifest.update_gallery_meta(
        manifest_data,
        config['gallery']['title'],
        config['gallery']['subtitle'],
        config['gallery'].get('password_hash', '')
    )

    # Clean old mock thumbnails
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    for old in THUMB_DIR.glob('IMG_*.jpg'):
        try:
            old.unlink()
        except Exception:
            pass

    # Create mock photos data
    mock_photos = []
    colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#e67e22', '#34495e']

    for i in range(1, 13):
        mock_photos.append({
            'file_id': f'mock_{i:03d}',
            'name': f'IMG_{i:04d}.jpg',
            'size': 2000000 + i * 100000,
            'updated_at': f'2025-08-{i:02d}T10:00:00+08:00',
        })

    # Generate placeholder thumbnails using PIL
    from PIL import Image, ImageDraw, ImageFont

    for p in mock_photos:
        # Generate a colored placeholder thumbnail
        idx = int(p['file_id'].split('_')[1])
        color = colors[idx % len(colors)]

        img = Image.new('RGB', (480, 360), color)
        draw = ImageDraw.Draw(img)
        text = f'IMG_{idx:04d}'
        draw.text((180, 160), text, fill='white')

        thumb_name = f'IMG_{idx:04d}.jpg'
        img.save(THUMB_DIR / thumb_name, 'JPEG', quality=85)

        # Also keep a mock original so "view original" works in previews
        ORIG_DIR.mkdir(parents=True, exist_ok=True)
        img.save(ORIG_DIR / f'IMG_{idx:04d}.jpg', 'JPEG', quality=92)

        manifest.add_photo(
            manifest_data,
            p,
            thumb_name,
            original=f'originals/IMG_{idx:04d}.jpg',
            dimensions=(4032, 3024)
        )
        print(f'  [MOCK] Added {thumb_name}')

    manifest.save_manifest(manifest_data)
    print(f'[MOCK] Done. {len(mock_photos)} photos in manifest.')

    # Validate
    from harness.validate import validate_all
    validate_all()

    return 0


def real_sync(config):
    """Sync from Aliyun Drive."""
    from harness.aliyun_client import AliyunClient

    folder_id = config['aliyun'].get('folder_id', 'root')
    file_types = set(config['aliyun'].get('file_types', []))

    # 1. Connect (uses .env token, aligo cache, or QR-code login)
    print('[1/5] Connecting to Aliyun Drive...')
    client = AliyunClient()
    client.connect()
    print('  Connected.')

    # 2. List files
    print(f'[2/5] Listing images in folder "{folder_id}"...')
    remote_files = client.list_image_files(parent_file_id=folder_id, extensions=file_types)
    print(f'  Found {len(remote_files)} images.')

    # 3. Diff with manifest
    print('[3/5] Comparing with existing manifest...')
    existing_manifest = manifest.load_manifest()
    diff = manifest.diff_photos(existing_manifest['photos'], remote_files)
    print(f'  New: {len(diff["new"])}, Removed: {len(diff["removed"])}, Unchanged: {len(diff["unchanged"])}')

    # Update gallery meta
    manifest.update_gallery_meta(
        existing_manifest,
        config['gallery']['title'],
        config['gallery']['subtitle'],
        config['gallery'].get('password_hash', '')
    )

    # 4. Process new files
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    ORIG_DIR.mkdir(parents=True, exist_ok=True)
    if diff['new']:
        print(f'[4/5] Processing {len(diff["new"])} new files...')
        for i, f in enumerate(diff['new']):
            print(f'  [{i+1}/{len(diff["new"])}] {f["name"]}')

            # Download original -> keep locally as gallery/originals/<file_id><ext>
            local_path = client.download_to_temp(f['file_id'])
            ext = Path(f['name']).suffix.lower()
            orig_name = f"{f['file_id']}{ext}"
            orig_path = ORIG_DIR / orig_name
            if not orig_path.exists():
                shutil.copy2(local_path, orig_path)

            # Generate thumbnail (named by file_id -> never collides)
            thumb_name = generate_thumbnail(
                local_path,
                str(THUMB_DIR),
                max_width=config['gallery'].get('thumbnail_width', 480),
                quality=config['gallery'].get('thumbnail_quality', 85),
                out_name=f"{f['file_id']}.jpg",
            )

            # Get dimensions
            dims = get_image_dimensions(local_path)

            # Add to manifest (no share link - Aliyun blocks the share API since 2025)
            manifest.add_photo(existing_manifest, f, thumb_name,
                               original=f'originals/{orig_name}', dimensions=dims)

            # Cleanup temp file
            try:
                os.remove(local_path)
            except Exception:
                pass
    else:
        print('[4/5] No new files to process.')

    # 5. Remove deleted files
    if diff['removed']:
        print(f'[5/5] Removing {len(diff["removed"])} deleted files...')
        for p in diff['removed']:
            manifest.remove_photo(existing_manifest, p['id'])
            # Delete thumbnail
            thumb_path = THUMB_DIR / p['thumbnail']
            if thumb_path.exists():
                thumb_path.unlink()
            # Delete local original
            if p.get('original'):
                orig_path = ORIG_DIR / Path(p['original']).name
                if orig_path.exists():
                    orig_path.unlink()
            print(f'  Removed {p["name"]}')
    else:
        print('[5/5] No files to remove.')

    # Save manifest
    manifest.save_manifest(existing_manifest)
    print(f'\nSync complete. {len(existing_manifest["photos"])} photos in manifest.')

    # Validate
    from harness.validate import validate_all
    validate_all()

    return 0


def set_password(config):
    """Set or update the gallery access password."""
    import getpass
    pw = getpass.getpass('Enter gallery access password: ')
    if not pw:
        print('Password cannot be empty.')
        return 1

    pw_hash = manifest.hash_password(pw)
    config['gallery']['password_hash'] = pw_hash

    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    # Update manifest
    m = manifest.load_manifest()
    manifest.update_gallery_meta(m, config['gallery']['title'],
                                config['gallery']['subtitle'], pw_hash)
    manifest.save_manifest(m)

    print(f'Password set. Hash: {pw_hash[:16]}...')
    return 0


def main():
    config = load_config()
    args = sys.argv[1:]

    if '--mock' in args:
        return mock_sync(config)
    if '--set-pass' in args:
        return set_password(config)

    return real_sync(config)


if __name__ == '__main__':
    sys.exit(main())
