"""
Manifest management - the single source of truth for gallery data.

Manifest structure (gallery/data.json):
{
  "version": 1,
  "updated_at": "...",
  "gallery": {"title": "...", "subtitle": "..."},
  "password_hash": "sha256hex",
  "photos": [
    {"id", "name", "size", "thumbnail", "share_url", "dimensions", "added_at"}
  ]
}
"""
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_PATH = Path(__file__).parent.parent / 'gallery' / 'data.json'


def hash_password(password: str) -> str:
    """SHA-256 hex hash of a password string."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def load_manifest() -> dict:
    """Load existing manifest, or return empty structure."""
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return new_manifest()


def new_manifest() -> dict:
    """Return a fresh empty manifest structure."""
    return {
        'version': 1,
        'updated_at': '',
        'gallery': {},
        'password_hash': '',
        'photos': [],
    }


def save_manifest(manifest: dict):
    """Write manifest to gallery/data.json."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    manifest['updated_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def diff_photos(existing: list, remote_files: list) -> dict:
    """
    Compare existing manifest photos with remote file list.
    Returns {'new': [...], 'removed': [...], 'unchanged': [...]}.
    """
    existing_ids = {p['id']: p for p in existing}
    remote_ids = {f['file_id']: f for f in remote_files}

    new = [f for fid, f in remote_ids.items() if fid not in existing_ids]
    removed = [existing_ids[fid] for fid in existing_ids if fid not in remote_ids]
    unchanged = [existing_ids[fid] for fid in existing_ids if fid in remote_ids]

    return {'new': new, 'removed': removed, 'unchanged': unchanged}


def add_photo(manifest: dict, file_info: dict, thumbnail_name: str,
              original: str = '', dimensions: tuple = None):
    """
    Add a photo entry to the manifest.
    original: relative path to the local original image (e.g. 'originals/<file_id>.jpg').
              Kept for backward-compat as 'share_url' too if provided.
    """
    entry = {
        'id': file_info['file_id'],
        'name': file_info['name'],
        'size': file_info.get('size', 0),
        'thumbnail': thumbnail_name,
        'original': original,
        'added_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }
    if dimensions:
        entry['dimensions'] = {'width': dimensions[0], 'height': dimensions[1]}
    manifest['photos'].append(entry)


def remove_photo(manifest: dict, photo_id: str):
    """Remove a photo entry from the manifest."""
    manifest['photos'] = [p for p in manifest['photos'] if p['id'] != photo_id]


def update_gallery_meta(manifest: dict, title: str, subtitle: str, password_hash: str):
    """Update gallery-level metadata in the manifest."""
    manifest['gallery'] = {'title': title, 'subtitle': subtitle}
    manifest['password_hash'] = password_hash


def get_photo_ids(manifest: dict) -> list:
    """Return list of all photo IDs in the manifest."""
    return [p['id'] for p in manifest['photos']]
