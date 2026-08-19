"""
Aliyun Drive client wrapper - deterministic API access layer.

All Aliyun Drive interaction goes through this module.
The rest of the harness never touches aligo directly.
"""
import os
import time
import json
import tempfile
from pathlib import Path

# ── Retry config ──────────────────────────────────────
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


class AliyunClient:
    """Wraps aligo for Aliyun Drive operations. Single entry point for all API calls."""

    def __init__(self, refresh_token: str | None = None):
        self.refresh_token = refresh_token
        self._ali = None
        self._drive_id = None

    # ── Connection ───────────────────────────────────
    def connect(self, auth_token: str | None = None):
        """
        Authenticate with Aliyun Drive.

        If auth_token is provided, use it directly.
        Otherwise delegate to auth.py, which supports .env, cache, or QR login.
        """
        from aligo import Aligo

        if auth_token:
            self._ali = Aligo(refresh_token=auth_token)
        else:
            from harness import auth
            self._ali = auth.get_aligo_client()
            # Persist the working token back to .env if we got one via QR/cache
            try:
                cache_token = auth.get_refresh_token()
                if cache_token and not auth._token_from_env():
                    auth.save_refresh_token_to_env(cache_token)
            except Exception:
                pass

        # Grab drive id for API calls that need it
        try:
            info = self._ali.get_personal_info()
            if hasattr(info, 'personal_drive_info'):
                self._drive_id = info.personal_drive_info.drive_id
            elif isinstance(info, dict):
                self._drive_id = info.get('personal_drive_info', {}).get('drive_id')
        except Exception:
            # drive_id is optional for basic operations
            pass

    # ── File listing ─────────────────────────────────
    def list_image_files(self, parent_file_id='root', extensions=None):
        """
        List image files in a folder. Returns list of dicts:
            [{file_id, name, size, updated_at, thumbnail_url}, ...]
        Handles pagination automatically.
        """
        if extensions is None:
            extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.heic'}

        results = []
        next_marker = None

        while True:
            kwargs = dict(parent_file_id=parent_file_id)
            if next_marker:
                kwargs['marker'] = next_marker

            resp = self._safe_call(self._ali.get_file_list, **kwargs)

            # aligo returns either a list or a paginated object
            if isinstance(resp, list):
                items = resp
                next_marker = None
            else:
                items = getattr(resp, 'items', []) or getattr(resp, 'file_list', resp)
                if isinstance(resp, list):
                    items = resp
                next_marker = getattr(resp, 'next_marker', None)

            for f in items:
                name = self._attr(f, 'name', '')
                ext = Path(name).suffix.lower()
                file_type = self._attr(f, 'type', '')
                if file_type == 'file' and ext in extensions:
                    results.append({
                        'file_id': self._attr(f, 'file_id', ''),
                        'name': name,
                        'size': self._attr(f, 'size', 0),
                        'updated_at': self._attr(f, 'updated_at', ''),
                        'category': self._attr(f, 'category', ''),
                        'thumbnail_url': self._attr(f, 'thumbnail', ''),
                        'url': self._attr(f, 'url', ''),
                    })

            if not next_marker:
                break

        return results

    # ── Download ──────────────────────────────────────
    def download_to_temp(self, file_id: str) -> str:
        """Download a file to a temp path. Returns the local path."""
        tmp = tempfile.mkdtemp(prefix='aliyun_album_')
        self._safe_call(self._ali.download_file, file_id=file_id, local_folder=tmp)

        # aligo downloads to tmp/<filename>
        files = list(Path(tmp).iterdir())
        if not files:
            raise RuntimeError(f'Download produced no files for file_id={file_id}')
        return str(files[0])

    # ── Share link ────────────────────────────────────
    def create_share_link(self, file_id: str) -> dict:
        """
        Create a permanent share link for a single file.
        Returns {'share_url': str, 'share_id': str}.
        """
        share = self._safe_call(
            self._ali.share_file,
            file_id=file_id,
            expiration='forever',
        )

        return {
            'share_url': self._attr(share, 'share_url', ''),
            'share_id': self._attr(share, 'share_id', ''),
        }

    def batch_create_share_links(self, file_ids: list) -> dict:
        """Create share links for multiple files. Returns {file_id: share_url}."""
        mapping = {}
        for fid in file_ids:
            try:
                result = self.create_share_link(fid)
                mapping[fid] = result['share_url']
            except Exception as e:
                print(f'  [WARN] share failed for {fid}: {e}')
        return mapping

    # ── Utilities ─────────────────────────────────────
    def _safe_call(self, fn, **kwargs):
        """Call an aligo method with retry logic."""
        last_err = None
        for attempt in range(MAX_RETRIES):
            try:
                return fn(**kwargs)
            except Exception as e:
                last_err = e
                if attempt < MAX_RETRIES - 1:
                    print(f'  [RETRY {attempt+1}/{MAX_RETRIES}] {e}')
                    time.sleep(RETRY_DELAY * (attempt + 1))
        raise last_err

    @staticmethod
    def _attr(obj, key, default=None):
        """Get attribute from object or dict, defensive."""
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)
