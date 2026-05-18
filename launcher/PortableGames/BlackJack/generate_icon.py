#!/usr/bin/env python3
import os
from PIL import Image, ImageDraw

SIZE = 128
img = Image.new("RGBA", (SIZE, SIZE), (12, 28, 18, 255))
d = ImageDraw.Draw(img)
gold = (255, 220, 80, 255)
felt = (18, 72, 42, 255)
red = (220, 60, 70, 255)
d.rectangle([8, 8, SIZE - 9, SIZE - 9], outline=gold, width=3)
d.rectangle([20, 24, SIZE - 21, SIZE - 22], fill=felt)
d.rectangle([36, 48, 68, 88], fill=(245, 245, 250, 255), outline=gold, width=2)
d.rectangle([44, 56, 56, 68], fill=red)
d.rectangle([72, 48, 104, 88], fill=(245, 245, 250, 255), outline=gold, width=2)
d.rectangle([82, 56, 94, 68], fill=(30, 30, 40, 255))
out = os.path.join(os.path.dirname(__file__), "icon.png")
img.save(out)
print("Wrote", out)
