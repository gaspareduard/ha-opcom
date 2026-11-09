"""Export the approved Blue Hour master to integration icon sizes (Pillow required)."""

from pathlib import Path

from PIL import Image

root = Path(__file__).resolve().parents[1]
source = root / "assets/branding/blue-hour-4096.png"
destination = root / "custom_components/opcom_energy/brand"

with Image.open(source) as master:
    image = master.convert("RGBA")
    for size, name in ((256, "icon.png"), (512, "icon@2x.png")):
        image.resize((size, size), Image.Resampling.LANCZOS).save(destination / name)
