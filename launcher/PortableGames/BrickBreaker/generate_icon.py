#!/usr/bin/env python3
"""Generate pixel-art icon.png for Brick Breaker."""

import os

from PIL import Image, ImageDraw

SIZE = 128
img = Image.new("RGBA", (SIZE, SIZE), (10, 14, 22, 255))
d = ImageDraw.Draw(img)

turq = (64, 224, 208, 255)
gold = (255, 230, 120, 255)
red = (255, 90, 90, 255)
orange = (255, 160, 60, 255)

d.rectangle([8, 8, SIZE - 9, SIZE - 9], outline=turq, width=3)
# bricks
for i, col in enumerate([red, orange, turq]):
    d.rectangle([24 + i * 28, 20, 48 + i * 28, 36], fill=col)
# paddle
d.rectangle([36, 96, 92, 108], fill=turq)
# ball
d.ellipse([58, 72, 72, 86], fill=gold)

out = os.path.join(os.path.dirname(__file__), "icon.png")
img.save(out)
print("Wrote", out)
