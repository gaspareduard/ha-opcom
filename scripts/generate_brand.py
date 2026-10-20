"""Generate the project's original chart/lightning icon using Pillow (dev only)."""

from pathlib import Path

from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1] / "custom_components/opcom_energy/brand"
for size, name in ((256, "icon.png"), (512, "icon@2x.png")):
    image = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((12, 12, 500, 500), radius=112, fill="#123047")
    draw.line(
        [(100, 335), (180, 270), (250, 304), (335, 200), (412, 168)],
        fill="#43D9BE",
        width=26,
        joint="curve",
    )
    draw.polygon(
        [(272, 79), (185, 233), (254, 233), (222, 369), (341, 195), (274, 195), (310, 79)],
        fill="#FFD267",
    )
    image.resize((size, size), Image.Resampling.LANCZOS).save(root / name)
