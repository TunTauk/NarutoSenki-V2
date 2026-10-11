#!/usr/bin/env python3
"""Convert this project's unencrypted PVR v2 textures to PNG, without dependencies."""

import argparse
import plistlib
import struct
import sys
import zlib
from pathlib import Path


def decode(source):
    data = source.read_bytes()
    if source.name.endswith('.ccz'):
        if len(data) < 16 or data[:4] != b'CCZ!':
            raise ValueError('Expected an unencrypted CCZ! header')
        compression, version, reserved, size = struct.unpack('>HHII', data[4:16])
        if compression != 0 or version > 2 or reserved != 0:
            raise ValueError('Unsupported CCZ compression or header')
        data = zlib.decompress(data[16:])
        if len(data) != size:
            raise ValueError('CCZ decompressed size does not match its header')
    if len(data) < 52:
        raise ValueError('Truncated PVR header')
    header = struct.unpack('<13I', data[:52])
    length, height, width, mipmaps, flags, size, bits, red, green, blue, alpha, tag, surfaces = header
    if length != 52 or tag != 0x21525650:
        raise ValueError('Only legacy PVR v2 is supported')
    if surfaces != 1 or flags & (0x200 | 0x400 | 0x800 | 0x1000 | 0x4000):
        raise ValueError('Only a single, linear 2D texture is supported')
    layouts = {
        0x10: (16, (0xF000, 0x0F00, 0x00F0, 0x000F)),
        0x12: (32, (0xFF, 0xFF00, 0xFF0000, 0xFF000000)),
    }
    if layouts.get(flags & 0xFF) != (bits, (red, green, blue, alpha)):
        raise ValueError('Supported pixel formats: RGBA4444 and RGBA8888')
    if width < 1 or height < 1 or len(data) != length + size:
        raise ValueError('Invalid dimensions or PVR data length')
    stride = width * (bits // 8)
    pixels = data[length:length + stride * height]
    if len(pixels) != stride * height:
        raise ValueError('Truncated pixel data')
    if bits == 16:
        rgba = bytearray()
        for (pixel,) in struct.iter_unpack('<H', pixels):
            rgba.extend(((pixel >> 12) * 17, ((pixel >> 8) & 15) * 17,
                         ((pixel >> 4) & 15) * 17, (pixel & 15) * 17))
    else:
        rgba = pixels
    if flags & 0x10000:
        row_size = width * 4
        rgba = b''.join(rgba[y * row_size:(y + 1) * row_size]
                        for y in reversed(range(height)))
    return width, height, bytes(rgba)


def png_bytes(width, height, rgba):
    def chunk(kind, payload):
        return (struct.pack('>I', len(payload)) + kind + payload
                + struct.pack('>I', zlib.crc32(kind + payload)))
    stride = width * 4
    rows = b''.join(b'\x00' + rgba[y * stride:(y + 1) * stride]
                    for y in range(height))
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='+', type=Path, help='.pvr or .pvr.ccz files')
    parser.add_argument('-o', '--output', type=Path,
                        default=Path(__file__).resolve().parent / 'output')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    failed = False
    for source in args.inputs:
        name = source.name.removesuffix('.ccz').removesuffix('.pvr') + '.png'
        target = args.output / name
        try:
            plist_source = source.with_name(Path(name).with_suffix('.plist').name)
            plist_target = args.output / plist_source.name
            plist_data = None
            if plist_source.is_file():
                if plist_source.resolve() == plist_target.resolve():
                    raise ValueError('Choose a separate output directory to protect the original plist')
                with plist_source.open('rb') as original:
                    atlas = plistlib.load(original)
                metadata = atlas.setdefault('metadata', {})
                metadata['textureFileName'] = name
                if 'realTextureFileName' in metadata:
                    metadata['realTextureFileName'] = name
                plist_data = plistlib.dumps(atlas, sort_keys=False)
            outputs = [target] + ([plist_target] if plist_data is not None else [])
            if not args.overwrite:
                for path in outputs:
                    if path.exists():
                        raise FileExistsError(f'{path} already exists; use --overwrite to replace outputs')
            width, height, rgba = decode(source)
            with target.open('wb' if args.overwrite else 'xb') as output:
                output.write(png_bytes(width, height, rgba))
            if plist_data is not None:
                with plist_target.open('wb' if args.overwrite else 'xb') as output:
                    output.write(plist_data)
                print(f'{plist_source.name} -> {plist_target} (references {name})')
            else:
                print(f'No matching {plist_source.name}; converted texture only', file=sys.stderr)
            print(f'{source.name} -> {target} ({width} x {height})')
        except (OSError, ValueError, plistlib.InvalidFileException, zlib.error) as error:
            print(f'{source}: {error}', file=sys.stderr)
            failed = True
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
