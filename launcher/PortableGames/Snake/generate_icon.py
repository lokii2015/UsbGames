#!/usr/bin/env python3
"""Generate pixel-art icon.png for Snake."""

import os

try:
  from PIL import Image, ImageDraw
except ImportError:
  print("pip install pillow")
  raise

SIZE = 128
img = Image.new("RGBA", (SIZE, SIZE), (12, 14, 18, 255))
d = ImageDraw.Draw(img)

# border
d.rectangle([8, 8, SIZE - 9, SIZE - 9], outline=(57, 255, 20, 255), width=3)

# snake body (pixel blocks)
green = (57, 255, 20, 255)
dark = (20, 80, 12, 255)
blocks = [
  (40, 70), (56, 70), (72, 70), (88, 70),
  (88, 54), (88, 38),
]
for x, y in blocks:
  d.rectangle([x, y, x + 14, y + 14], fill=green, outline=dark)

# head highlight
d.rectangle([88, 38, 102, 52], fill=(120, 255, 90, 255), outline=dark)
# eyes
d.rectangle([94, 44, 97, 47], fill=(12, 14, 18, 255))
d.rectangle([94, 50, 97, 53], fill=(12, 14, 18, 255))

# apple
d.ellipse([34, 34, 54, 54], fill=(255, 45, 45, 255))
d.rectangle([42, 28, 45, 36], fill=(40, 120, 40, 255))

out = os.path.join(os.path.dirname(__file__), "icon.png")
img.save(out)
print("Wrote", out)
