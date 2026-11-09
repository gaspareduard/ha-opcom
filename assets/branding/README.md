# Blue Hour icon

Approved project icon: cobalt blue rounded tile, white lightning bolt and scheduling dial, with a peach time-window accent.

`blue-hour-4096.png` is the 4096 × 4096 RGBA master, upscaled with Lanczos resampling from the approved 1254 × 1254 AI-generated concept. The transparent rounded corners are normalized for clean exports. It is an upscaled raster, not a native 4K or vector render.

Regenerate the 256px and 512px integration icons with:

```sh
uv run --no-project --python 3.14 --with pillow python scripts/generate_brand.py
```

The master is kept outside the integration package. The icon is independent of the official OPCOM brand.
