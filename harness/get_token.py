"""
Helper to obtain and save an Aliyun Drive refresh token.

Usage:
  python harness/get_token.py

This will:
  1. Look for ALIYUN_REFRESH_TOKEN in .env
  2. Try to read from existing aligo cache
  3. Otherwise start aligo QR-code login (scan with Aliyun Drive app)
  4. Save the token to .env for future sync runs
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from harness import auth


def main():
    try:
        token = auth.get_refresh_token()
        print('\n[OK] Refresh token already available:')
        print(f'     {token[:16]}...{token[-8:]}')
        auth.save_refresh_token_to_env(token)
        return 0
    except RuntimeError:
        # No env/cache token -> use QR login
        ali = auth.get_aligo_client()
        # After login, pull token from cache and save
        token = auth.get_refresh_token()
        print('\n[OK] Logged in successfully.')
        print(f'     Token: {token[:16]}...{token[-8:]}')
        auth.save_refresh_token_to_env(token)
        return 0
    except Exception as e:
        print(f'[ERROR] {e}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
