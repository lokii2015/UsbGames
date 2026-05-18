#!/usr/bin/env python3
"""Generate pixel-art icon.png for Grid Defense."""

import os

from PIL import Image, ImageDraw

SIZE = 128
img = Image.new("RGBA", (SIZE, SIZE), (10, 14, 22, 255))
d = ImageDraw.Draw(img)

turq = (64, 224, 208, 255)
green = (57, 255, 120, 255)
red = (255, 90, 90, 255)
path = (32, 42, 58, 255)

d.rectangle([8, 8, SIZE - 9, SIZE - 9], outline=turq, width=3)
# path S
d.rectangle([20, 48, 100, 56], fill=path)
d.rectangle([92, 56, 100, 88], fill=path)
d.rectangle([20, 80, 100, 88], fill=path)
# tower
d.rectangle([36, 28, 56, 48], fill=turq, outline=green)
# enemy
d.rectangle([72, 40, 88, 52], fill=red)

out = os.path.join(os.path.dirname(__file__), "icon.png")
img.save(out)
print("Wrote", out)
