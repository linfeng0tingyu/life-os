from __future__ import annotations

from pathlib import Path

from PIL import Image


CANVAS_SIZE = 1024
ICON_CONTENT_SIZE = 1000
VISIBLE_ALPHA_THRESHOLD = 8
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
LOGO_SOURCE = (
    "design-assets/logo-concepts/"
    "life-os-logo-02a-ref-a-full-landscape-contained.png"
)


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    source_path = project_root / LOGO_SOURCE
    output_dir = project_root / "packaging" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "life-os.ico"

    if not source_path.is_file():
        raise FileNotFoundError(f"Logo source does not exist: {source_path}")

    with Image.open(source_path) as source:
        logo = source.convert("RGBA")
    visible_alpha = logo.getchannel("A").point(
        lambda value: 255 if value >= VISIBLE_ALPHA_THRESHOLD else 0
    )
    alpha_bounds = visible_alpha.getbbox()
    if alpha_bounds is None:
        raise ValueError("Logo source is fully transparent.")
    logo = logo.crop(alpha_bounds)
    logo.thumbnail(
        (ICON_CONTENT_SIZE, ICON_CONTENT_SIZE), Image.Resampling.LANCZOS
    )

    image = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    offset = ((CANVAS_SIZE - logo.width) // 2, (CANVAS_SIZE - logo.height) // 2)
    image.alpha_composite(logo, offset)

    image.save(output_path, format="ICO", sizes=[(size, size) for size in ICON_SIZES])
    print(f"Generated desktop icon: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
