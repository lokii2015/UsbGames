#!/usr/bin/env python3
"""Generate pixel-art icon.png for Pixel Chomp."""

import os

from PIL import Image, ImageDraw

SIZE = 128
img = Image.new("RGBA", (SIZE, SIZE), (10, 14, 22, 255))
d = ImageDraw.Draw(img)

turq = (64, 224, 208, 255)
yellow = (255, 230, 80, 255)
red = (255, 90, 90, 255)
blue = (64, 160, 255, 255)

d.rectangle([8, 8, SIZE - 9, SIZE - 9], outline=turq, width=3)
# maze lines
for x in range(24, 104, 20):
    d.rectangle([x, 24, x + 12, 104], fill=(32, 48, 88, 255))
for y in range(24, 104, 20):
    d.rectangle([24, y, 104, y + 12], fill=(32, 48, 88, 255))
# chomper
d.pieslice([44, 44, 84, 84], 30, 330, fill=yellow)
d.polygon([(64, 64), (84, 50), (84, 78)], fill=(10, 14, 22, 255))
# ghost
d.ellipse([88, 72, 108, 96], fill=red)
d.rectangle([88, 88, 108, 100], fill=red)

out = os.path.join(os.path.dirname(__file__), "icon.png")
img.save(out)
print("Wrote", out)
