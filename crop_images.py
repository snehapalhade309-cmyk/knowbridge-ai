"""
Crop title page and thank-you page from uploaded screenshots
"""
from PIL import Image
import os

IMG1 = r"C:/Users/HP/.gemini/antigravity/brain/4684a6a9-6148-493a-9a59-bc18fbbe16e8/.user_uploaded/media_1794285340949_7b87dae9.jpg"
IMG4 = r"C:/Users/HP/.gemini/antigravity/brain/4684a6a9-6148-493a-9a59-bc18fbbe16e8/.user_uploaded/media_1794286138288_25275dc9.jpg"

OUT = r"c:\Users\HP\Downloads\KKK"

# ── Image 1: crop TITLE page (top section of first screenshot) ──────────────
img1 = Image.open(IMG1)
w1, h1 = img1.size
print(f"IMG1 size: {w1} x {h1}")

# Title page is roughly top 38% of the screenshot (before "HIDDEN PROBLEM" dark bar)
title_bottom = int(h1 * 0.365)
title_crop = img1.crop((0, 55, w1, title_bottom))   # skip phone status bar top
title_crop.save(os.path.join(OUT, "crop_title.jpg"), quality=95)
print(f"Saved crop_title.jpg  ({title_crop.size})")

# ── Image 4: crop THANK YOU section (bottom portion of last screenshot) ─────
img4 = Image.open(IMG4)
w4, h4 = img4.size
print(f"IMG4 size: {w4} x {h4}")

# Thank you starts at roughly 65% down in this image
ty_top = int(h4 * 0.595)
ty_crop = img4.crop((0, ty_top, w4, h4))
ty_crop.save(os.path.join(OUT, "crop_thankyou.jpg"), quality=95)
print(f"Saved crop_thankyou.jpg  ({ty_crop.size})")
