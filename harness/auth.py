"""
Authentication helper for Aliyun Drive.

Three ways to get a refresh token (tried in order):
  1. ALIYUN_REFRESH_TOKEN in .env
  2. Existing aligo cache file (~/.aligo/*.json)
  3. Interactive QR-code login via aligo (first time only)

This keeps token handling out of sync.py and aliyun_client.py.
"""
import os
import json
from pathlib import Path


ROOT = Path(__file__).parent.parent
ENV_FILE = ROOT / '.env'
ALIGO_DIR = Path.home() / '.aligo'


def _load_env() -> dict:
    """Parse .env file into os.environ."""
    if not ENV_FILE.exists():
        return {}
    for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, val = line.split('=', 1)
        key = key.strip()
        val = val.strip().strip('"\'')
        os.environ[key] = val
    return dict(os.environ)


def _token_from_env() -> str | None:
    """Return refresh token from .env if present."""
    token = os.environ.get('ALIYUN_REFRESH_TOKEN', '').strip()
    if token:
        return token
    # Also accept common variant names
    for key in ('REFRESH_TOKEN', 'ALIYUN_TOKEN', 'ALIPAN_REFRESH_TOKEN'):
        token = os.environ.get(key, '').strip()
        if token:
            return token
    return None


def _token_from_aligo_cache() -> str | None:
    """Try to read refresh_token from any aligo cache file."""
    if not ALIGO_DIR.exists():
        return None
    # aligo stores cache as JSON files named after the auth name
    for path in sorted(ALIGO_DIR.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            token = data.get('refresh_token') or data.get('token', {}).get('refresh_token')
            if token:
                return token
        except Exception:
            continue
    return None


def _interactive_login() -> 'Aligo':
    """Let aligo handle QR-code login and return an authenticated client."""
    from aligo import Aligo
    print('[AUTH] No refresh token found. Starting aligo QR-code login...')
    print('       Please scan the QR code with the Aliyun Drive app.')
    return Aligo()  # aligo will print QR text and wait for scan


def get_refresh_token(prefer_env: bool = True) -> str:
    """
    Resolve a refresh token string.

    Order:
      1. .env ALIYUN_REFRESH_TOKEN
      2. aligo persistent cache
      3. raise RuntimeError (callers should use get_aligo_client for QR login)
    """
    _load_env()

    if prefer_env:
        token = _token_from_env()
        if token:
            print('[AUTH] Using refresh token from .env')
            return token

    token = _token_from_aligo_cache()
    if token:
        print('[AUTH] Using refresh token from aligo cache')
        return token

    raise RuntimeError(
        'No refresh token found.\n'
        'Options:\n'
        '  1. Set ALIYUN_REFRESH_TOKEN in .env\n'
        '  2. Run "python harness/get_token.py" to log in via QR code once.\n'
        '  3. Run sync and let it prompt for QR-code login.'
    )


def get_aligo_client(prefer_env: bool = True) -> 'Aligo':
    """
    Return an authenticated aligo.Aligo client.

    Order:
      1. .env ALIYUN_REFRESH_TOKEN
      2. aligo persistent cache (Aligo() reads it automatically)
      3. QR-code login (interactive, first time)
    """
    _load_env()

    if prefer_env:
        token = _token_from_env()
        if token:
            from aligo import Aligo
            print('[AUTH] Logging in with refresh token from .env')
            return Aligo(refresh_token=token)

    # Aligo() with no args will use cache if available, otherwise show QR code
    return _interactive_login()


def save_refresh_token_to_env(token: str) -> None:
    """Append or update ALIYUN_REFRESH_TOKEN in .env."""
    lines = []
    found = False
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
            if line.strip().startswith('ALIYUN_REFRESH_TOKEN='):
                lines.append(f'ALIYUN_REFRESH_TOKEN={token}')
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f'ALIYUN_REFRESH_TOKEN={token}')
    ENV_FILE.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'[AUTH] Saved ALIYUN_REFRESH_TOKEN to {ENV_FILE}')
