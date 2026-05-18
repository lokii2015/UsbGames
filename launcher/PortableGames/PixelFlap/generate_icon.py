#!/usr/bin/env python3
"""Generate pixel-art icon.png for Pixel Flap."""

import os

from PIL import Image, ImageDraw

SIZE = 128
img = Image.new("RGBA", (SIZE, SIZE), (10, 14, 22, 255))
d = ImageDraw.Draw(img)

turq = (64, 224, 208, 255)
green = (57, 255, 120, 255)
pipe = (32, 48, 58, 255)

d.rectangle([8, 8, SIZE - 9, SIZE - 9], outline=turq, width=3)
# pipes
d.rectangle([72, 8, 92, 48], fill=pipe, outline=turq)
d.rectangle([72, 72, 92, 112], fill=pipe, outline=turq)
# bird / drone
d.rectangle([28, 52, 52, 68], fill=turq)
d.rectangle([52, 56, 68, 66], fill=green)
d.rectangle([20, 58, 28, 64], fill=pipe)
d.rectangle([60, 58, 64, 62], fill=(255, 255, 255, 255))

out = os.path.join(os.path.dirname(__file__), "icon.png")
img.save(out)
print("Wrote", out)
