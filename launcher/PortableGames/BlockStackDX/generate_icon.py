#!/usr/bin/env python3
"""Generate pixel-art icon.png for BlockStack DX."""

import os

from PIL import Image, ImageDraw

SIZE = 128
img = Image.new("RGBA", (SIZE, SIZE), (10, 14, 22, 255))
d = ImageDraw.Draw(img)

turq = (64, 224, 208, 255)
green = (57, 255, 120, 255)
purple = (180, 120, 255, 255)
gold = (255, 230, 120, 255)

d.rectangle([8, 8, SIZE - 9, SIZE - 9], outline=turq, width=3)
# stacked blocks
blocks = [
    (28, 88, 44, 104, purple),
    (48, 72, 64, 88, turq),
    (68, 56, 84, 72, green),
    (48, 88, 64, 104, gold),
    (68, 88, 84, 104, turq),
]
for x1, y1, x2, y2, col in blocks:
    d.rectangle([x1, y1, x2, y2], fill=col)
    d.rectangle([x1 + 2, y1 + 2, x2 - 2, y2 - 4], fill=tuple(min(255, c + 40) for c in col[:3]) + (255,))

out = os.path.join(os.path.dirname(__file__), "icon.png")
img.save(out)
print("Wrote", out)
