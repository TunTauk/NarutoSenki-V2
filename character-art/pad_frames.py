#!/usr/bin/env python3
"""Add transparent canvas padding to PNG animation frames without scaling."""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    raise SystemExit('Pillow is required. See character-art/README.md for setup.')


def animation_name(stem):
    # Naruto_Idle_001 -> Naruto_Idle. Unknown names share a fallback group.
    match = re.fullmatch(r'(.+)_\d+', stem)
    return match.group(1) if match else 'frames'


def pad_image(image, canvas_size, anchor='center'):
    width, height = canvas_size
    if width < image.width or height < image.height:
        raise ValueError(f'Canvas {width} x {height} would clip frame {image.width} x {image.height}')
    if anchor == 'center':
        x, y = (width - image.width) // 2, (height - image.height) // 2
    elif anchor == 'bottom-center':
        x, y = (width - image.width) // 2, height - image.height
    elif anchor == 'top-left':
        x = y = 0
    else:
        raise ValueError(f'Unknown anchor: {anchor}')
    result = Image.new('RGBA', (width, height))
    result.paste(image.convert('RGBA'), (x, y))
    return result, (x, y)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='PNG frames directory (searched recursively)')
    parser.add_argument('-o', '--output-dir', type=Path)
    parser.add_argument('--group', choices=['animation', 'all'], default='animation')
    parser.add_argument('--anchor', choices=['center', 'bottom-center', 'top-left'], default='center')
    parser.add_argument('--margin', type=int, default=0, help='Extra transparent space around the shared canvas')
    parser.add_argument('--size', nargs=2, type=int, metavar=('WIDTH', 'HEIGHT'), help='Explicit final canvas dimensions')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    try:
        if not args.input.is_dir():
            raise ValueError('Input must be a directory')
        if args.margin < 0 or (args.size and min(args.size) < 1):
            raise ValueError('Margin must be nonnegative; canvas dimensions must be positive')
        output = args.output_dir or Path(__file__).resolve().parent / 'padded' / args.input.resolve().name
        if output.resolve() == args.input.resolve() or args.input.resolve() in output.resolve().parents:
            raise ValueError('Output must be outside the input directory to protect original frames')
        groups = defaultdict(list)
        for path in sorted(args.input.rglob('*')):
            if path.is_file() and path.suffix.lower() == '.png':
                group = animation_name(path.stem) if args.group == 'animation' else 'all'
                with Image.open(path) as image:
                    groups[group].append((path, image.convert('RGBA')))
        if not groups:
            raise ValueError('No PNG frames found')
        jobs = []
        destinations = set()
        for group, frames in sorted(groups.items()):
            minimum = (max(image.width for _, image in frames), max(image.height for _, image in frames))
            size = tuple(args.size) if args.size else tuple(n + 2 * args.margin for n in minimum)
            if any(actual < needed + 2 * args.margin for actual, needed in zip(size, minimum)):
                raise ValueError(f'{group}: canvas {size} is too small for frames and margin')
            for source, image in frames:
                relative = Path(group) / source.name
                if relative in destinations:
                    raise ValueError(f'Duplicate output filename: {relative}')
                destinations.add(relative)
                # Position in the inner canvas, then retain the requested margin on every side.
                inner_size = tuple(n - 2 * args.margin for n in size)
                inner, position = pad_image(image, inner_size, args.anchor)
                x, y = (n + args.margin for n in position)
                jobs.append((source, image, relative, size, (x, y)))
        manifest_path = output / 'padding.json'
        targets = [output / job[2] for job in jobs] + [manifest_path]
        if not args.overwrite:
            for target in targets:
                if target.exists():
                    raise FileExistsError(f'{target} already exists; use --overwrite')
        manifest = {'version': 1, 'anchor': args.anchor, 'group': args.group,
                    'margin': args.margin, 'frames': []}
        for source, image, relative, size, (x, y) in jobs:
            padded = Image.new('RGBA', size)
            padded.paste(image, (x, y))
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('wb' if args.overwrite else 'xb') as handle:
                padded.save(handle, format='PNG')
            manifest['frames'].append({'source': source.relative_to(args.input).as_posix(),
                                       'output': relative.as_posix(), 'original_size': list(image.size),
                                       'canvas_size': list(size), 'position': [x, y]})
        with manifest_path.open('w' if args.overwrite else 'x') as handle:
            json.dump(manifest, handle, indent=2)
            handle.write('\n')
        for group, frames in sorted(groups.items()):
            size = next(job[3] for job in jobs if job[2].parent.name == group)
            print(f'{group}: {len(frames)} frames, {size[0]} x {size[1]} -> {output / group}')
        print(f'Original sizes and padding positions saved to {manifest_path}')
        return 0
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
