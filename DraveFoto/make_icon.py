# Maakt assets/icon.png + assets/icon.ico voor DraveFoto (eigen ontwerp: stapel foto's met berg en zon). Pillow nodig.
import os
from PIL import Image, ImageDraw

HIER = os.path.dirname(os.path.abspath(__file__))
N = 512
img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((16, 16, N - 16, N - 16), radius=96, fill=(18, 20, 30, 255), outline=(111, 163, 214, 255), width=10)


def kaart(hoek, kleur):
    k = Image.new("RGBA", (300, 240), (0, 0, 0, 0))
    ImageDraw.Draw(k).rounded_rectangle((0, 0, 299, 239), radius=14, fill=kleur)
    return k.rotate(hoek, expand=True, resample=Image.BICUBIC)


for hoek, kleur in ((14, (90, 96, 120, 255)), (-8, (150, 156, 180, 255))):
    k = kaart(hoek, kleur)
    img.alpha_composite(k, ((N - k.width) // 2, (N - k.height) // 2 - 10))
d = ImageDraw.Draw(img)
x0, y0, x1, y1 = 96, 140, 416, 380
d.rounded_rectangle((x0, y0, x1, y1), radius=14, fill=(240, 240, 246, 255))
d.rectangle((x0 + 18, y0 + 18, x1 - 18, y1 - 50), fill=(111, 163, 214, 255))
d.ellipse((300, 175, 360, 235), fill=(255, 179, 71, 255))
d.polygon([(x0 + 18, y1 - 50), (190, 215), (250, 280), (290, 245), (x1 - 18, y1 - 50)], fill=(40, 70, 60, 255))
d.polygon([(190, 215), (172, 238), (208, 238)], fill=(240, 240, 246, 255))
os.makedirs(os.path.join(HIER, "assets"), exist_ok=True)
img.save(os.path.join(HIER, "assets", "icon.png"))
img.save(os.path.join(HIER, "assets", "icon.ico"), format="ICO",
         sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icoon klaar")
