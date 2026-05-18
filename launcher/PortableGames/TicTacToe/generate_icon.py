#!/usr/bin/env python3
"""Generate pixel-art icon.png for Tic-Tac-Toe."""

import os

from PIL import Image, ImageDraw

SIZE = 128
img = Image.new("RGBA", (SIZE, SIZE), (10, 12, 20, 255))
d = ImageDraw.Draw(img)

turq = (64, 224, 208, 255)
white = (245, 250, 255, 255)
grid = (40, 55, 70, 255)

d.rectangle([8, 8, SIZE - 9, SIZE - 9], outline=turq, width=3)

# 3x3 grid
for i in range(1, 3):
    x = 32 + i * 28
    y = 32 + i * 28
    d.line([(x, 28), (x, 100)], fill=grid, width=3)
    d.line([(28, y), (100, y)], fill=grid, width=3)

# X top-left
d.line([(36, 36), (52, 52)], fill=turq, width=4)
d.line([(52, 36), (36, 52)], fill=turq, width=4)
# O center
d.ellipse([58, 58, 82, 82], outline=white, width=4)
# X bottom-right
d.line([(76, 76), (92, 92)], fill=turq, width=4)
d.line([(92, 76), (76, 92)], fill=turq, width=4)

out = os.path.join(os.path.dirname(__file__), "icon.png")
img.save(out)
print("Wrote", out)
