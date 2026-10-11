#!/usr/bin/env python3
"""Pack PNG frames into a lossless Cocos2d format-2 atlas."""

import argparse
import plistlib
import struct
import sys
import zlib
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    raise SystemExit('Pillow is required. See character-art/README.md for setup.')


def power_of_two(value):
    return 1 << (value - 1).bit_length()


def layout(frames, padding, max_size):
    """Try power-of-two widths with deterministic shelf packing."""
    ordered = sorted(frames, key=lambda item: (-item[1].height, -item[1].width, item[0]))
    width = power_of_two(max(image.width for _, image in ordered) + 2 * padding)
    best = None
    while width <= max_size:
        x = y = padding
        shelf_height = 0
        positions = {}
        for name, image in ordered:
            if x + image.width + padding > width:
                x = padding
                y += shelf_height + padding
                shelf_height = 0
            positions[name] = (x, y)
            x += image.width + padding
            shelf_height = max(shelf_height, image.height)
        height = power_of_two(y + shelf_height + padding)
        if height <= max_size:
            candidate = (width * height, max(width, height), width, height, positions)
            if best is None or candidate[:4] < best[:4]:
                best = candidate
        width *= 2
    if best is None:
        raise ValueError(f'Frames do not fit within {max_size} x {max_size}; increase --max-size')
    return best[2:]


def build_atlas(frames, texture_name, padding=2, max_size=4096):
    if not frames:
        raise ValueError('No PNG frames found')
    if padding < 0 or max_size < 1:
        raise ValueError('Padding must be nonnegative and max size must be positive')
    names = [name for name, _ in frames]
    if len(set(names)) != len(names):
        raise ValueError('Duplicate frame names; each PNG basename must be unique')
    width, height, positions = layout(frames, padding, max_size)
    atlas = Image.new('RGBA', (width, height))
    entries = {}
    for name, image in sorted(frames, key=lambda item: item[0]):
        x, y = positions[name]
        # Copy all channels directly, including partially transparent pixels.
        atlas.paste(image, (x, y))
        w, h = image.size
        entries[name] = {
            'frame': '{{%d,%d},{%d,%d}}' % (x, y, w, h),
            'offset': '{0,0}',
            'rotated': False,
            'sourceColorRect': '{{0,0},{%d,%d}}' % (w, h),
            'sourceSize': '{%d,%d}' % (w, h),
        }
    return atlas, {
        'frames': entries,
        'metadata': {'format': 2, 'textureFileName': texture_name,
                     'realTextureFileName': texture_name,
                     'size': '{%d,%d}' % (width, height)},
    }


def pvr_ccz_bytes(image):
    """Encode legacy PVR v2 RGBA8888, then wrap it in unencrypted CCZ."""
    pixels = image.tobytes()
    header = struct.pack('<13I', 52, image.height, image.width, 0,
                         0x8012, len(pixels), 32, 0xFF, 0xFF00,
                         0xFF0000, 0xFF000000, 0x21525650, 1)
    pvr = header + pixels
    return struct.pack('>4sHHII', b'CCZ!', 0, 2, 0, len(pvr)) + zlib.compress(pvr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='Directory containing individual PNG frames (searched recursively)')
    parser.add_argument('--name', help='Atlas basename; defaults to the input directory name')
    parser.add_argument('-o', '--output-dir', type=Path)
    parser.add_argument('--padding', type=int, default=2, help='Gap between packed frames, not animation canvas padding')
    parser.add_argument('--max-size', type=int, default=4096)
    parser.add_argument('--pvr-ccz', action='store_true', help='Also generate a lossless PVR/CCZ texture; plist references it')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    try:
        if not args.input.is_dir():
            raise ValueError('Input must be a directory')
        name = args.name or args.input.resolve().name
        if not name or name in ('.', '..') or '/' in name or '\\' in name:
            raise ValueError('Atlas name must be a simple filename without directories')
        output = args.output_dir or Path(__file__).resolve().parent / 'packed' / name
        if output.resolve() == args.input.resolve() or args.input.resolve() in output.resolve().parents:
            raise ValueError('Output must be outside the input directory to avoid packing generated sheets')
        paths = sorted(p for p in args.input.rglob('*') if p.is_file() and p.suffix.lower() == '.png')
        frames = []
        for path in paths:
            with Image.open(path) as image:
                frames.append((path.stem, image.convert('RGBA')))
        png = output / (name + '.png')
        plist = output / (name + '.plist')
        ccz = output / (name + '.pvr.ccz')
        targets = [png, plist] + ([ccz] if args.pvr_ccz else [])
        if not args.overwrite:
            for target in targets:
                if target.exists():
                    raise FileExistsError(f'{target} already exists; use --overwrite')
        atlas, metadata = build_atlas(frames, ccz.name if args.pvr_ccz else png.name,
                                      args.padding, args.max_size)
        plist_data = plistlib.dumps(metadata, sort_keys=False)
        ccz_data = pvr_ccz_bytes(atlas) if args.pvr_ccz else None
        output.mkdir(parents=True, exist_ok=True)
        with png.open('wb' if args.overwrite else 'xb') as handle:
            atlas.save(handle, format='PNG')
        with plist.open('wb' if args.overwrite else 'xb') as handle:
            handle.write(plist_data)
        if ccz_data is not None:
            with ccz.open('wb' if args.overwrite else 'xb') as handle:
                handle.write(ccz_data)
        print(f'Packed {len(frames)} frames into {atlas.width} x {atlas.height}:')
        for target in targets:
            print(target)
        return 0
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
