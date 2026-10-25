"""Optional. Make a ZIP file of random images to test the Bulk mode. Use: python3 scripts/load_test.py [number_of_images]"""
import io, random, sys, zipfile
from PIL import Image
n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
with zipfile.ZipFile("sample_bulk.zip", "w") as z:
    for i in range(n):
        im = Image.effect_noise((384, 384), 60).convert("RGB") if i % 2 else Image.new("RGB", (384, 384), tuple(random.randint(0, 255) for _ in range(3)))
        b = io.BytesIO(); im.save(b, "JPEG"); z.writestr(f"img_{i:03}.jpg", b.getvalue())
print(f"wrote sample_bulk.zip with {n} images — upload it in the Bulk tab")
