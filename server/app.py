"""
Photo Upload Server - the photographer's upload entry.

Flow per photo:
    save to _inbox/ -> upload to Aliyun Drive -> thumbnail -> share link -> manifest

Then optionally auto-publishes to GitHub Pages (git add/commit/push).

Photographers NEVER touch the owner's Aliyun Drive account.
They only need this URL + upload code.

Usage:
    python server/app.py            # normal (real Aliyun Drive)
    python server/app.py --mock     # mock mode (no Aliyun connection, for testing)
"""
import sys
import os
import json
import uuid
import shutil
import socket
import threading
import subprocess
from pathlib import Path

# Make harness importable
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from flask import Flask, request, jsonify, render_template, send_from_directory

from harness import manifest
from harness.thumbnail import generate_thumbnail, get_image_dimensions

# ── Paths & config ───────────────────────────────────
INBOX = Path(__file__).parent / '_inbox'
THUMB_DIR = ROOT / 'gallery' / 'thumbnails'
ORIG_DIR = ROOT / 'gallery' / 'originals'
CONFIG_PATH = ROOT / 'config.json'
ENV_PATH = ROOT / '.env'

ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.heic'}
MAX_FILE_MB = 60

config = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
FOLDER_ID = config['aliyun'].get('folder_id', 'root')

# ── .env loading ─────────────────────────────────────
def load_env():
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip()
    return env

_env = load_env()
UPLOAD_CODE = _env.get('ALBUM_UPLOAD_CODE', '123456')
ADMIN_CODE = _env.get('ALBUM_ADMIN_CODE', 'admin123')
BASE_URL = config.get('site', {}).get('base_url', '')

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_MB * 1024 * 1024

# ── Aliyun client (lazy, shared) ─────────────────────
_client = None
_client_lock = threading.Lock()

def get_client():
    global _client
    with _client_lock:
        if _client is None:
            from harness.aliyun_client import AliyunClient
            c = AliyunClient()
            c.connect()
            _client = c
        return _client


def local_ip():
    """Best-effort LAN IP for showing the upload URL."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


# ── Core photo processing ────────────────────────────
def process_photo(file_path: Path, original_name: str, mock: bool) -> dict:
    """
    Upload one photo end-to-end.
    Flow: keep original locally (gallery/originals/) + backup to Aliyun Drive + thumbnail + manifest.
    Returns {'ok': True, 'file_id', 'name', 'thumbnail', 'original', 'size'} or {'ok': False, 'error'}.
    """
    try:
        ext = Path(original_name).suffix.lower()
        if ext not in ALLOWED_EXT:
            return {'ok': False, 'name': original_name, 'error': f'不支持的文件类型 {ext}'}

        if mock:
            file_id = f'mock_up_{uuid.uuid4().hex[:8]}'
        else:
            client = get_client()
            up = client.upload_file(str(file_path), parent_file_id=FOLDER_ID, name=original_name)
            file_id = client._attr(up, 'file_id', '')
            if not file_id:
                return {'ok': False, 'name': original_name, 'error': '上传到云盘失败：未返回 file_id'}

        # 1) Keep the original locally -> gallery/originals/<file_id><ext>
        ORIG_DIR.mkdir(parents=True, exist_ok=True)
        orig_name = f'{file_id}{ext}'
        orig_path = ORIG_DIR / orig_name
        if not orig_path.exists():
            shutil.copy2(file_path, orig_path)

        # 2) Thumbnail named by file_id -> never collides
        THUMB_DIR.mkdir(parents=True, exist_ok=True)
        thumb_name = f'{file_id}.jpg'
        thumb_path = THUMB_DIR / thumb_name
        if not thumb_path.exists():
            generate_thumbnail(str(file_path), str(THUMB_DIR), out_name=thumb_name,
                               max_width=config['gallery'].get('thumbnail_width', 480),
                               quality=config['gallery'].get('thumbnail_quality', 85))
        dimensions = None
        try:
            dimensions = get_image_dimensions(str(file_path))
        except Exception:
            pass

        # 3) Update manifest
        m = manifest.load_manifest()
        manifest.add_photo(
            m,
            {'file_id': file_id, 'name': original_name,
             'size': file_path.stat().st_size if file_path.exists() else 0},
            thumb_name,
            original=f'originals/{orig_name}',
            dimensions=dimensions,
        )
        manifest.save_manifest(m)

        return {'ok': True, 'file_id': file_id, 'name': original_name,
                'thumbnail': thumb_name, 'original': f'originals/{orig_name}',
                'size': file_path.stat().st_size if file_path.exists() else 0}
    except Exception as e:
        return {'ok': False, 'name': original_name, 'error': str(e)}


def publish_to_github(message: str):
    """git add/commit/push if a remote is configured. Runs in background thread."""
    def _run():
        try:
            r = subprocess.run(['git', 'remote'], cwd=str(ROOT), capture_output=True, text=True, timeout=30)
            if not r.stdout.strip():
                print('  [PUBLISH] No git remote configured - skip auto publish.')
                return
            subprocess.run(['git', 'add', '-A'], cwd=str(ROOT), capture_output=True, text=True, timeout=30)
            subprocess.run(['git', 'commit', '-m', message], cwd=str(ROOT), capture_output=True, text=True, timeout=30)
            p = subprocess.run(['git', 'push'], cwd=str(ROOT), capture_output=True, text=True, timeout=120)
            if p.returncode == 0:
                print(f'  [PUBLISH] Pushed to GitHub: {message}')
            else:
                print(f'  [PUBLISH] push failed: {p.stderr[-200:]}')
        except Exception as e:
            print(f'  [PUBLISH] error: {e}')
    threading.Thread(target=_run, daemon=True).start()


# ── Routes ───────────────────────────────────────────
@app.route('/')
def upload_page():
    return render_template('upload.html', max_mb=MAX_FILE_MB)


@app.route('/admin')
def admin_page():
    return render_template('admin.html')


@app.route('/upload', methods=['POST'])
def upload():
    """Single-file upload endpoint. Fields: file, code."""
    code = request.form.get('code', '')
    if not _secure_compare(code, UPLOAD_CODE):
        return jsonify({'ok': False, 'error': '上传码错误，请向管理员获取'}), 403

    f = request.files.get('file')
    if not f or not f.filename:
        return jsonify({'ok': False, 'error': '没有收到文件'}), 400

    original = Path(f.filename).name  # strip any path components
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_EXT:
        return jsonify({'ok': False, 'error': f'不支持的文件类型 {ext}'}), 400

    # Save to inbox with a unique temp name (keep extension)
    tmp_name = f'{uuid.uuid4().hex}{ext}'
    tmp_path = INBOX / tmp_name
    f.save(tmp_path)

    mock = request.args.get('mock') == '1' or '--mock' in sys.argv
    try:
        result = process_photo(tmp_path, original, mock)
        return jsonify(result), (200 if result.get('ok') else 500)
    finally:
        # Clean inbox
        try:
            tmp_path.unlink()
        except OSError:
            pass


@app.route('/api/status')
def api_status():
    code = request.args.get('code', '')
    if not _secure_compare(code, ADMIN_CODE):
        return jsonify({'ok': False, 'error': '管理密码错误'}), 403

    m = manifest.load_manifest()
    photos = m.get('photos', [])
    try:
        folder_id = config['aliyun'].get('folder_id', '')
    except Exception:
        folder_id = ''

    return jsonify({
        'ok': True,
        'photo_count': len(photos),
        'updated_at': m.get('updated_at', ''),
        'upload_url': f'http://{local_ip()}:{PORT}',
        'view_url': BASE_URL,
        'has_remote': bool(subprocess.run(['git', 'remote'], cwd=str(ROOT),
                                          capture_output=True, text=True, timeout=10).stdout.strip()),
        'folder_name': config['aliyun'].get('folder_name', ''),
    })


@app.route('/api/photos')
def api_photos():
    code = request.args.get('code', '')
    if not _secure_compare(code, ADMIN_CODE):
        return jsonify({'ok': False, 'error': '管理密码错误'}), 403

    n = int(request.args.get('n', 12))
    m = manifest.load_manifest()
    photos = m.get('photos', [])[-n:][::-1]  # newest first
    return jsonify({'ok': True, 'photos': photos})


@app.route('/thumbnails/<name>')
def thumb(name):
    return send_from_directory(str(THUMB_DIR), name)


@app.route('/api/publish', methods=['POST'])
def api_publish():
    code = request.form.get('code', '')
    if not _secure_compare(code, ADMIN_CODE):
        return jsonify({'ok': False, 'error': '管理密码错误'}), 403
    publish_to_github('upload: publish gallery')
    return jsonify({'ok': True, 'message': '发布任务已启动（后台执行）'})


def _secure_compare(a: str, b: str) -> bool:
    import hmac
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))


# ── Entry ────────────────────────────────────────────
PORT = 8091
if __name__ == '__main__':
    mock = '--mock' in sys.argv
    mode = 'MOCK (no Aliyun connection)' if mock else 'REAL (Aliyun Drive)'
    print('=' * 52)
    print('  培训照片上传服务')
    print(f'  模式: {mode}')
    print('=' * 52)
    ip = local_ip()
    print(f'  上传入口(给摄影师): http://{ip}:{PORT}/')
    print(f'  管理入口(给自己):   http://{ip}:{PORT}/admin')
    print(f'  本机入口:           http://127.0.0.1:{PORT}/')
    print('-' * 52)
    print('  上传码: 见 .env 的 ALBUM_UPLOAD_CODE')
    print('  管理码: 见 .env 的 ALBUM_ADMIN_CODE')
    print('  按 Ctrl+C 停止服务')
    print('=' * 52)
    app.run(host='0.0.0.0', port=PORT, threaded=True)
