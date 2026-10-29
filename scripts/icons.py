"""Generate both apps' icon build inputs locally: .venv/bin/python scripts/icons.py.

Font-free geometric marks keep output independent of installed system fonts.
Maskable marks fit entirely inside the central 80%-diameter safe circle.
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SCALE = 4
MARKS = {
    "hub": ("#101112", "#fbbf24", [(170, 136), (300, 136), (348, 184), (348, 256), (300, 304), (226, 304), (226, 376), (170, 376)]),
    "dashboard": ("#0b1428", "#3b82f6", [(174, 136), (344, 136), (344, 192), (230, 192), (230, 236), (324, 236), (324, 292), (230, 292), (230, 376), (174, 376)]),
}


def artwork(app: str, maskable: bool = False) -> Image.Image:
    background, accent, points = MARKS[app]
    image = Image.new("RGB", (512 * SCALE, 512 * SCALE), background)
    draw = ImageDraw.Draw(image)
    # Reduced mark has ample padding even under circular platform masks.
    factor = 0.85 if maskable else 1
    def coords(vertices):
        return [((256 + (x - 256) * factor) * SCALE,
                 (256 + (y - 256) * factor) * SCALE) for x, y in vertices]
    draw.polygon(coords(points), fill=accent)
    if app == "hub":
        draw.rectangle(coords([(226, 192), (292, 248)]), fill=background)
    return image


def generate(app: str) -> None:
    target = ROOT / app / "public"
    target.mkdir(parents=True, exist_ok=True)
    image = artwork(app)
    for name, size in [("favicon-16x16.png", 16), ("favicon-32x32.png", 32),
                       ("apple-touch-icon.png", 180), ("icon-192.png", 192),
                       ("icon-512.png", 512)]:
        image.resize((size, size), Image.Resampling.LANCZOS).save(target / name)
    image.resize((512, 512), Image.Resampling.LANCZOS).save(
        target / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    artwork(app, True).resize((512, 512), Image.Resampling.LANCZOS).save(
        target / "icon-512-maskable.png")
    points = MARKS[app][2]
    path = "M " + " L ".join(f"{x} {y}" for x, y in points) + " Z"
    if app == "hub":
        path += " M 226 192 H 292 V 248 H 226 Z"
    (target / "safari-pinned-tab.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
        f'<path fill="black" fill-rule="evenodd" d="{path}"/></svg>\n', encoding="utf-8")


if __name__ == "__main__":
    for app in MARKS:
        generate(app)
