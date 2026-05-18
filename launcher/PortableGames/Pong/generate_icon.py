#!/usr/bin/env python3
import os
from PIL import Image, ImageDraw

SIZE = 128
img = Image.new("RGBA", (SIZE, SIZE), (10, 14, 22, 255))
d = ImageDraw.Draw(img)
turq = (64, 224, 208, 255)
gold = (255, 230, 120, 255)
coral = (255, 120, 90, 255)
d.rectangle([8, 8, SIZE - 9, SIZE - 9], outline=turq, width=3)
d.rectangle([18, 36, 30, 92], fill=turq)
d.rectangle([98, 36, 110, 92], fill=coral)
d.ellipse([56, 58, 72, 74], fill=gold)
out = os.path.join(os.path.dirname(__file__), "icon.png")
img.save(out)
print("Wrote", out)
