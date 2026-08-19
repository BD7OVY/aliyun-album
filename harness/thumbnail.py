"""
Thumbnail generation - deterministic image processing.

Uses Pillow to resize images to thumbnails.
Never touches the network or aligo.
"""
from pathlib import Path
from PIL import Image


def generate_thumbnail(src_path: str, out_dir: str, max_width=480, quality=85,
                       out_name: str | None = None) -> str:
    """
    Generate a thumbnail from a source image.
    Returns the thumbnail filename (not full path).

    - Resizes to max_width preserving aspect ratio
    - Converts to JPEG for consistent format and smaller size
    - Strips EXIF for privacy and size

    out_name: optional output filename (defaults to src stem + '.jpg').
              Pass a unique name (e.g. file_id + '.jpg') to avoid collisions.
    """
    src = Path(src_path)
    if not src.exists():
        raise FileNotFoundError(f'Source image not found: {src_path}')

    img = Image.open(src_path)
    img = img.convert('RGB')

    # Resize preserving aspect ratio
    w, h = img.size
    if w > max_width:
        ratio = max_width / w
        new_size = (max_width, int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # Output filename: same stem, .jpg extension (or explicit out_name)
    out_name = (out_name or (src.stem + '.jpg'))
    out_path = Path(out_dir) / out_name

    img.save(out_path, 'JPEG', quality=quality, optimize=True)

    return out_name


def get_image_dimensions(path: str) -> tuple:
    """Return (width, height) of an image file."""
    with Image.open(path) as img:
        return img.size
