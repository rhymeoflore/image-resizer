#!/usr/bin/env python3
"""
resize_images.py — Resize photographs to a required dimension and/or file size.

Usage:
    python resize_images.py <input> [options]

Examples:
    python resize_images.py photo.jpg --width 1920 --height 1080
    python resize_images.py photo.jpg --width 800                     # height auto-scaled
    python resize_images.py photo.jpg --max-size 500KB
    python resize_images.py photos/  --width 1280 --max-size 300KB --output-dir resized/
    python resize_images.py photo.jpg --width 1920 --height 1080 --no-crop
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:
    print("Missing dependency. Install it with:")
    print("  pip install Pillow")
    sys.exit(1)

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}


def parse_size(size_str: str) -> int:
    """Parse a human-readable size string like '500KB' or '2MB' into bytes."""
    size_str = size_str.strip().upper()
    if size_str.endswith("MB"):
        return int(float(size_str[:-2]) * 1024 * 1024)
    if size_str.endswith("KB"):
        return int(float(size_str[:-2]) * 1024)
    if size_str.endswith("B"):
        return int(size_str[:-1])
    return int(size_str)


def resize_to_dimensions(
    img: Image.Image, width: int | None, height: int | None, crop: bool
) -> Image.Image:
    """Resize image to the target dimensions, maintaining aspect ratio unless crop is enabled."""
    orig_w, orig_h = img.size

    if width and height:
        if crop:
            # Fill the exact dimensions by cropping excess
            img = ImageOps.fit(img, (width, height), method=Image.LANCZOS)
        else:
            # Fit within the box, preserving aspect ratio (no crop)
            img.thumbnail((width, height), Image.LANCZOS)
    elif width:
        ratio = width / orig_w
        new_h = max(1, int(orig_h * ratio))
        img = img.resize((width, new_h), Image.LANCZOS)
    elif height:
        ratio = height / orig_h
        new_w = max(1, int(orig_w * ratio))
        img = img.resize((new_w, height), Image.LANCZOS)

    return img


def compress_to_size(img: Image.Image, dest: Path, max_bytes: int, fmt: str) -> None:
    """Save the image, reducing JPEG/WebP quality iteratively until it fits max_bytes."""
    if fmt in ("JPEG", "WEBP"):
        quality = 95
        while quality >= 10:
            img.save(dest, format=fmt, quality=quality, optimize=True)
            if dest.stat().st_size <= max_bytes:
                return
            quality -= 5
        # Last resort: resize down by 10% at a time
        w, h = img.size
        while dest.stat().st_size > max_bytes and w > 1 and h > 1:
            w = max(1, int(w * 0.9))
            h = max(1, int(h * 0.9))
            img_small = img.resize((w, h), Image.LANCZOS)
            img_small.save(dest, format=fmt, quality=10, optimize=True)
    else:
        # PNG / BMP / TIFF — no quality knob; fall back to progressive resizing
        img.save(dest, format=fmt, optimize=True)
        w, h = img.size
        while dest.stat().st_size > max_bytes and w > 1 and h > 1:
            w = max(1, int(w * 0.9))
            h = max(1, int(h * 0.9))
            img_small = img.resize((w, h), Image.LANCZOS)
            img_small.save(dest, format=fmt, optimize=True)


def process_image(
    src: Path,
    dest: Path,
    width: int | None,
    height: int | None,
    max_bytes: int | None,
    crop: bool,
) -> None:
    img = Image.open(src)

    # Convert RGBA/P images to RGB when saving as JPEG
    output_format = img.format or "JPEG"
    if output_format.upper() in ("JPEG", "JPG"):
        output_format = "JPEG"
        if img.mode in ("RGBA", "P", "LA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

    if width or height:
        img = resize_to_dimensions(img, width, height, crop)

    dest.parent.mkdir(parents=True, exist_ok=True)

    if max_bytes:
        compress_to_size(img, dest, max_bytes, output_format)
    else:
        save_kwargs: dict = {"format": output_format}
        if output_format in ("JPEG", "WEBP"):
            save_kwargs["quality"] = 90
            save_kwargs["optimize"] = True
        img.save(dest, **save_kwargs)

    final_size = dest.stat().st_size
    print(f"  {src.name} → {dest.name}  {img.size[0]}×{img.size[1]}  ({final_size / 1024:.1f} KB)")


def collect_images(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(
        p for p in input_path.rglob("*") if p.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resize photographs to required dimensions and/or file size."
    )
    parser.add_argument("input", help="Path to an image file or a directory of images")
    parser.add_argument("--width", "-W", type=int, default=None, help="Target width in pixels")
    parser.add_argument("--height", "-H", type=int, default=None, help="Target height in pixels")
    parser.add_argument(
        "--max-size", "-s", default=None,
        help="Maximum output file size (e.g. 500KB, 2MB)"
    )
    parser.add_argument(
        "--output-dir", "-o", default=None,
        help="Directory to save resized images (default: overwrites originals)"
    )
    parser.add_argument(
        "--suffix", default="_resized",
        help="Suffix added to filenames when --output-dir is not set (default: _resized)"
    )
    parser.add_argument(
        "--no-crop", dest="crop", action="store_false",
        help="When both --width and --height are given, fit within the box instead of cropping"
    )
    parser.set_defaults(crop=True)
    args = parser.parse_args()

    if not args.width and not args.height and not args.max_size:
        parser.error("Specify at least one of --width, --height, or --max-size.")

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: '{input_path}' does not exist.")
        sys.exit(1)

    max_bytes = parse_size(args.max_size) if args.max_size else None
    images = collect_images(input_path)

    if not images:
        print("No supported image files found.")
        sys.exit(0)

    print(f"Processing {len(images)} image(s)...\n")

    for src in images:
        if args.output_dir:
            relative = src.relative_to(input_path) if input_path.is_dir() else Path(src.name)
            dest = Path(args.output_dir) / relative
        else:
            dest = src.with_stem(src.stem + args.suffix)

        try:
            process_image(src, dest, args.width, args.height, max_bytes, args.crop)
        except Exception as e:
            print(f"  ERROR processing {src.name}: {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
