"""Generate hub SVG icons: .venv/bin/python scripts/icons.py hub.

Requires Pillow and hub npm dependencies (Sharp renders the SVG source).
Dashboard generation remains available only via an explicit dashboard/all argument.

Font-free geometric marks keep output independent of installed system fonts.
Maskable marks fit entirely inside the central 80%-diameter safe circle.
"""
from pathlib import Path
import argparse
import io
import re
import subprocess

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


def generate_hub() -> None:
    """Render the SVG source; never write to dashboard unless explicitly selected."""
    brand = ROOT / "assets/brand/hub"
    target = ROOT / "hub/public"
    source = (brand / "mark.svg").read_text()
    def raster(svg, size):
        render = subprocess.run(["node", "-e", "const sharp=require(require.resolve('sharp',{paths:[process.argv[1]]}));let b=[];process.stdin.on('data',c=>b.push(c));process.stdin.on('end',async()=>{try{process.stdout.write(await sharp(Buffer.concat(b)).resize(Number(process.argv[2]),Number(process.argv[2])).png().toBuffer())}catch(e){console.error(e);process.exit(1)}})", str(ROOT / "hub"), str(size * SCALE)], input=svg.encode(), capture_output=True, check=True)
        return Image.open(io.BytesIO(render.stdout)).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    def colored(svg, color):
        return re.sub(r'color="#[0-9a-fA-F]+"', f'color="{color}"', svg)
    inner = source[source.index(">") + 1:source.rindex("</svg>")]
    app = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" color="#f5f2e9"><path fill="#22211e" d="M0 0h24v24H0z"/><g transform="translate(3 3) scale(.75)">' + inner + '</g></svg>\n'
    (brand / "app-icon.svg").write_text(app)
    for size in (16, 32, 48, 96):
        raster(app, size).save(target / f"favicon-{size}x{size}.png")
    for name, size in (("apple-touch-icon.png", 180), ("icon-192.png", 192), ("icon-512.png", 512), ("icon-512-maskable.png", 512)):
        raster(app, size).save(target / name)
    raster(app, 512).save(target / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    (target / "mark.svg").write_text(source)
    (target / "safari-pinned-tab.svg").write_text(colored(source, "#000000"))
    (target / "favicon.svg").write_text(source.replace('>' , '><style>@media(prefers-color-scheme:dark){svg{color:#f5f2e9}}</style>', 1))
    sheet = Image.new("RGB", (1120, 960), "#efeee9")
    draw = ImageDraw.Draw(sheet)
    draw.text((24, 16), "PLAINSIGHT MEDIA / actual-size marks / 16, 32, 48, 192 px", fill="#22211e")
    for row, concept in enumerate(sorted((brand / "concepts").glob("*.svg"))):
        svg = concept.read_text()
        for theme, bg, fg, offset in (("light", "#ffffff", "#22211e", 0), ("dark", "#22211e", "#f5f2e9", 552)):
            x, y = 8 + offset, 48 + row * 300
            draw.rectangle((x, y, x + 544, y + 288), fill=bg)
            draw.text((x + 16, y + 12), f"{concept.stem} / {theme}", fill=fg)
            for size, dx in ((16, 32), (32, 104), (48, 200), (192, 328)):
                im = raster(colored(svg, fg), size)
                im.save(concept.with_name(f"{concept.stem}-{theme}-{size}.png"))
                sheet.paste(im, (x + dx, y + 52 + (192-size)//2), im)
                draw.text((x + dx, y + 256), str(size), fill=fg)
    sheet.save(brand / "concepts/contact-sheet.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", nargs="?", choices=("hub", "dashboard", "all"), default="hub")
    args = parser.parse_args()
    if args.app in ("hub", "all"):
        generate_hub()
    if args.app in ("dashboard", "all"):
        generate("dashboard")
