#!/usr/bin/env python3
"""Generate pixel-art icon.png for Space Command."""

import os

from PIL import Image, ImageDraw

SIZE = 128
img = Image.new("RGBA", (SIZE, SIZE), (10, 14, 22, 255))
d = ImageDraw.Draw(img)

turq = (64, 224, 208, 255)
green = (57, 255, 120, 255)
red = (255, 90, 90, 255)

d.rectangle([8, 8, SIZE - 9, SIZE - 9], outline=turq, width=3)
# ship
d.polygon([(64, 28), (48, 72), (80, 72)], fill=turq)
d.polygon([(64, 40), (56, 58), (72, 58)], fill=green)
# enemies
d.rectangle([28, 36, 44, 50], fill=red)
d.rectangle([84, 36, 100, 50], fill=red)
# laser
d.rectangle([62, 74, 66, 96], fill=green)

out = os.path.join(os.path.dirname(__file__), "icon.png")
img.save(out)
print("Wrote", out)
