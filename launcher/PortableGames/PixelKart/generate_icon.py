#!/usr/bin/env python3
"""Generate pixel-art icon.png for Pixel Kart."""

import os

from PIL import Image, ImageDraw

SIZE = 128
img = Image.new("RGBA", (SIZE, SIZE), (10, 14, 22, 255))
d = ImageDraw.Draw(img)

turq = (64, 224, 208, 255)
orange = (255, 160, 60, 255)
track = (42, 48, 58, 255)
white = (220, 235, 230, 255)

d.rectangle([8, 8, SIZE - 9, SIZE - 9], outline=turq, width=3)
# track oval
d.ellipse([24, 36, 104, 108], outline=track, width=8)
# kart body
d.polygon([(88, 72), (52, 88), (52, 56)], fill=orange, outline=white)
d.rectangle([70, 66, 82, 78], fill=turq)

out = os.path.join(os.path.dirname(__file__), "icon.png")
img.save(out)
print("Wrote", out)
