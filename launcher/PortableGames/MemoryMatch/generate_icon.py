#!/usr/bin/env python3
"""Generate pixel-art icon.png for Memory Match."""

import os

from PIL import Image, ImageDraw

SIZE = 128
img = Image.new("RGBA", (SIZE, SIZE), (10, 14, 22, 255))
d = ImageDraw.Draw(img)

turq = (64, 224, 208, 255)
red = (255, 90, 90, 255)
green = (57, 255, 120, 255)
back = (28, 36, 52, 255)

d.rectangle([8, 8, SIZE - 9, SIZE - 9], outline=turq, width=3)
for x1, y1, x2, y2, col in [
    (22, 28, 52, 58, back),
    (68, 28, 98, 58, red),
    (22, 68, 52, 98, green),
    (68, 68, 98, 98, back),
]:
    d.rectangle([x1, y1, x2, y2], fill=col, outline=turq, width=2)

out = os.path.join(os.path.dirname(__file__), "icon.png")
img.save(out)
print("Wrote", out)
