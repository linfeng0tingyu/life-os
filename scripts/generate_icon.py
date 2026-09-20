from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


CANVAS_SIZE = 1024
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    output_dir = project_root / "packaging" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "life-os.ico"

    image = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), "#F5F3ED")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (64, 64, 960, 960),
        radius=188,
        fill="#F5F3ED",
        outline="#DCDCD4",
        width=28,
    )
    draw.ellipse(
        (220, 220, 804, 804),
        fill="#FBFAF6",
        outline="#3F625F",
        width=42,
    )
    draw.arc(
        (305, 305, 719, 719),
        start=32,
        end=310,
        fill="#729B99",
        width=42,
    )
    draw.ellipse((655, 660, 765, 770), fill="#B95549")

    image.save(output_path, format="ICO", sizes=[(size, size) for size in ICON_SIZES])
    print(f"Generated desktop icon: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
