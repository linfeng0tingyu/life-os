from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import zipfile


def package_release(project_root: Path, version: str) -> tuple[Path, Path]:
    source = project_root / "dist" / "LifeOS"
    executable = source / "LifeOS.exe"
    if not executable.is_file():
        raise FileNotFoundError(
            "dist/LifeOS/LifeOS.exe 不存在，请先运行 build_desktop.bat。"
        )

    output_dir = project_root / "release"
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"LifeOS-v{version}-windows-x64.zip"
    checksum = archive.with_suffix(f"{archive.suffix}.sha256")

    with zipfile.ZipFile(
        archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as bundle:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                bundle.write(path, Path("LifeOS") / path.relative_to(source))

    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    return archive, checksum


def main() -> int:
    parser = argparse.ArgumentParser(description="Package a Life OS Windows release")
    parser.add_argument("--version", default="0.1.0")
    arguments = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    archive, checksum = package_release(project_root, arguments.version)
    print(f"Release archive: {archive}")
    print(f"SHA-256 file: {checksum}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
