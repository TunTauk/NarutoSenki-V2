import re
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from pack_frames import build_atlas, pvr_ccz_bytes
from pvr_to_png import decode


class PackerTests(unittest.TestCase):
    def test_pixels_and_metadata_round_trip(self):
        frames = [('Idle_01', Image.new('RGBA', (3, 7), (12, 34, 56, 78))),
                  ('Attack_01', Image.new('RGBA', (11, 2), (255, 0, 19, 0))),
                  ('Walk_01', Image.new('RGBA', (4, 4), (5, 6, 7, 255)))]
        atlas, plist = build_atlas(frames, 'Hero.pvr.ccz')
        occupied = set()
        for name, image in frames:
            entry = plist['frames'][name]
            x, y, w, h = map(int, re.findall(r'\d+', entry['frame']))
            self.assertEqual(atlas.crop((x, y, x + w, y + h)).tobytes(), image.tobytes())
            self.assertEqual(entry['sourceSize'], '{%d,%d}' % image.size)
            pixels = {(px, py) for px in range(x, x + w) for py in range(y, y + h)}
            self.assertFalse(occupied & pixels)
            occupied |= pixels
        self.assertEqual(plist['metadata']['format'], 2)
        self.assertEqual(plist['metadata']['textureFileName'], 'Hero.pvr.ccz')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'Hero.pvr.ccz'
            path.write_bytes(pvr_ccz_bytes(atlas))
            w, h, pixels = decode(path)
        self.assertEqual((w, h), atlas.size)
        self.assertEqual(pixels, atlas.tobytes())

    def test_rejects_duplicate_names(self):
        image = Image.new('RGBA', (1, 1))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            build_atlas([('Idle', image), ('Idle', image)], 'Hero.png')

    def test_rejects_overflow(self):
        with self.assertRaisesRegex(ValueError, 'do not fit'):
            build_atlas([('Big', Image.new('RGBA', (65, 1)))], 'Hero.png', max_size=64)

    def test_deterministic_layout(self):
        frames = [('B', Image.new('RGBA', (2, 3))), ('A', Image.new('RGBA', (3, 2)))]
        first, first_plist = build_atlas(frames, 'Hero.png')
        second, second_plist = build_atlas(list(reversed(frames)), 'Hero.png')
        self.assertEqual(first_plist, second_plist)
        self.assertEqual(first.tobytes(), second.tobytes())


if __name__ == '__main__':
    unittest.main()
