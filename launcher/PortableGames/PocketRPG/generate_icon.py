#!/usr/bin/env python3
"""Generate pixel-art icon.png for Pocket RPG."""

import os

from PIL import Image, ImageDraw

SIZE = 128
img = Image.new("RGBA", (SIZE, SIZE), (10, 14, 22, 255))
d = ImageDraw.Draw(img)

turq = (64, 224, 208, 255)
green = (57, 255, 120, 255)
gold = (255, 220, 80, 255)
red = (255, 90, 90, 255)

d.rectangle([8, 8, SIZE - 9, SIZE - 9], outline=turq, width=3)
# hero sprite
d.rectangle([48, 44, 80, 84], fill=turq, outline=green)
d.rectangle([56, 36, 72, 48], fill=green)
# sword
d.rectangle([82, 50, 96, 58], fill=gold)
d.polygon([(96, 44), (108, 54), (96, 64)], fill=red)

out = os.path.join(os.path.dirname(__file__), "icon.png")
img.save(out)
print("Wrote", out)
