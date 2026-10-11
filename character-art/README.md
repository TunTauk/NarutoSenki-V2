# Editable character images

This directory keeps the converter and extracted images separate from game resources.
The converter requires Python 3.9 or newer, with no additional packages or paid tools.
It supports the unencrypted PVR v2 RGBA4444 and RGBA8888 formats used by this repository.
It does not support encrypted CCZ files, PVRTC textures, or PVR v3 from other projects.

From the repository root, convert a character sheet:

```sh
python3 character-art/pvr_to_png.py \
  projects/NarutoSenki/Resources/Unit/Ninja/Naruto/Naruto.pvr.ccz
```

The results are `character-art/output/Naruto.png` and `Naruto.plist` when a matching
plist exists beside the source texture. The copied plist references the generated PNG;
frame names, rectangles, offsets, and rotation data are preserved. If no plist exists,
the converter reports this and produces only the PNG. Open the PNG in your image editor.
The original texture and plist are untouched. Use a separate output directory.
Pass multiple input paths to convert
multiple sheets, `-o path/to/output` to choose an output directory, and `--overwrite`
to replace existing outputs. Both PNGs and plists are protected by default.

To extract individual animation frames with Node.js/npm installed:

```sh
npx texture-unpacker \
  -s character-art/output/Naruto.png \
  -f plist \
  -d character-art/output/Naruto.plist \
  -o character-art/frames/Naruto
```

PNG files contain the finished pixels, not the original artist's layers.
Save your future edits in your editor's native format as well as exporting PNGs.
The converter only converts to PNG. Use the packer below to build game assets.

## Pad frames for animation editing

Use the local Pillow environment described below, then run:

```sh
character-art/.venv/bin/python character-art/pad_frames.py character-art/frames/Naruto
```

The script groups names ending in `_NUMBER` into animations, for example
`Naruto_Idle_001.png` goes into `character-art/padded/Naruto/Naruto_Idle/`.
Names without that pattern go into a shared `frames` group. Every image within
each group receives the group's largest width and height, with transparent padding
and no scaling. Import one group's PNG sequence into LibreSprite.

The default `--anchor center` aligns the centers of the original canvases, matching
the zero-offset frame canvases used by the packer. Odd size differences are rounded
down to whole pixels. It does not detect the character's feet or undo any alignment
changes introduced by an editor. Use `--anchor bottom-center` for a shared baseline
or `--anchor top-left` to preserve a top-left origin.

Use `--group all` to put every frame on one shared canvas in an `all` subdirectory.
Other options: `--size 400 160` sets an explicit final canvas, `--margin 8` adds
extra space on all sides, `-o DIRECTORY` sets output, and `--overwrite` replaces
existing outputs. Canvases too small for any frame and its margin are rejected.
Input files remain unchanged; output must be outside the input directory.

`padding.json` records original dimensions and each frame's position inside the
padded canvas. Keep it to help restore original canvases before repacking. The
packer does not consume this manifest automatically. Do not crop edited artwork
back to the original size if you drew into the added padding; that requires an
intentional update to the game's frame alignment.

## Pack edited frames

The packer requires Pillow. Set up a local environment from the repository root:

```sh
python3 -m venv character-art/.venv
character-art/.venv/bin/python -m pip install -r character-art/requirements.txt
```

Export each animation from your editor as individual transparent PNGs, keeping
the frame names used by the character XML. Combine all of the character's frames
in an input folder. Subdirectories are supported, but PNG basenames must be unique.

```sh
character-art/.venv/bin/python character-art/pack_frames.py \
  character-art/frames/Naruto --name Naruto
```

This produces `character-art/packed/Naruto/Naruto.png` and `Naruto.plist`.
The plist uses Cocos2d format 2 and frame names without the `.png` extension.
The game supports this pair directly. Animation timing remains in the character XML.

To also produce a compressed texture:

```sh
character-art/.venv/bin/python character-art/pack_frames.py \
  character-art/frames/Naruto --name Naruto --pvr-ccz --overwrite
```

This also creates `Naruto.pvr.ccz`, and the plist references that texture instead
of the PNG. The PNG remains available as a preview. The compressed texture uses
lossless RGBA8888; it may be larger than original RGBA4444 textures, but preserves
every input pixel without further color quantization.

Use `-o DIRECTORY` to choose output, `--max-size 8192` to allow larger sheets,
and `--overwrite` to replace existing outputs. Output must be outside the input
directory. The packer copies pixels without scaling, trimming, or rotating frames,
and creates one power-of-two sheet using shelf packing. It favors predictable,
verifiable output over the smallest possible atlas. `--padding` controls gaps
between frames on the atlas; it does not add a shared animation canvas.

The input canvas is preserved with a zero frame offset. If you added editor-only
padding to your frames, restore the original canvases before packing, or prepare
consistent canvas anchors for use in the game. The packer does not recover original
alignment metadata from a previous plist. Game resources are never installed or
replaced automatically; test generated files in the game before using them.
