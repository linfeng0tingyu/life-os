from __future__ import annotations

import base64
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from werkzeug.datastructures import FileStorage

from life_os.runtime import RuntimePaths

from .common import NotFoundError, ValidationError, parse_life_date


MAX_IMAGE_BYTES = 5 * 1024 * 1024
ASSET_NAME_PATTERN = re.compile(r"^[0-9a-f]{32}\.(?:png|jpg|gif|webp)$")
ASSET_URL_PATTERN = re.compile(
    r"/api/journal/assets/(?P<date>\d{4}-\d{2}-\d{2})/"
    r"(?P<name>[0-9a-f]{32}\.(?:png|jpg|gif|webp))"
)


@dataclass(frozen=True, slots=True)
class JournalAsset:
    date: str
    filename: str
    original_name: str
    mime_type: str
    size: int

    @property
    def url(self) -> str:
        return f"/api/journal/assets/{self.date}/{self.filename}"


class JournalAssetService:
    @staticmethod
    def save(
        paths: RuntimePaths, value_date: str, upload: FileStorage
    ) -> JournalAsset:
        target = parse_life_date(value_date).isoformat()
        original_name = (upload.filename or "image").strip() or "image"
        data = upload.stream.read(MAX_IMAGE_BYTES + 1)
        if not data:
            raise ValidationError("请选择非空图片文件。")
        if len(data) > MAX_IMAGE_BYTES:
            raise ValidationError("单张图片不能超过 5 MB。")
        extension, mime_type = JournalAssetService._detect_image(data)
        filename = f"{uuid4().hex}.{extension}"
        directory = paths.attachments_dir / "journal" / target
        JournalAssetService._assert_contained(paths, directory)
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / filename
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".journal-image-",
                suffix=".tmp",
                dir=directory,
                delete=False,
            ) as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
                temporary = Path(handle.name)
            os.replace(temporary, destination)
        except OSError as exc:
            raise ValidationError("图片无法写入运行时附件目录。") from exc
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink(missing_ok=True)
        return JournalAsset(
            date=target,
            filename=filename,
            original_name=original_name[:200],
            mime_type=mime_type,
            size=len(data),
        )

    @staticmethod
    def asset_path(
        paths: RuntimePaths, value_date: str, filename: str
    ) -> Path:
        target = parse_life_date(value_date).isoformat()
        if not ASSET_NAME_PATTERN.fullmatch(filename):
            raise NotFoundError("日记图片不存在。")
        path = paths.attachments_dir / "journal" / target / filename
        JournalAssetService._assert_contained(paths, path)
        if not path.is_file():
            raise NotFoundError("日记图片不存在。")
        return path

    @staticmethod
    def export_markdown(
        paths: RuntimePaths, value_date: str, content: str
    ) -> Path:
        target = parse_life_date(value_date).isoformat()

        exported = JournalAssetService.render_self_contained(paths, content)

        directory = paths.exports_dir / "journal"
        JournalAssetService._assert_contained(paths, directory)
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"{target}.md"
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{target}.",
                suffix=".tmp",
                dir=directory,
                delete=False,
            ) as handle:
                handle.write(exported)
                if exported and not exported.endswith("\n"):
                    handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
                temporary = Path(handle.name)
            os.replace(temporary, destination)
        except OSError as exc:
            raise ValidationError("日记无法写入运行时导出目录。") from exc
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink(missing_ok=True)
        return destination

    @staticmethod
    def render_self_contained(paths: RuntimePaths, content: str) -> str:

        def embed(match: re.Match[str]) -> str:
            asset_path = JournalAssetService.asset_path(
                paths, match.group("date"), match.group("name")
            )
            mime_type = JournalAssetService.mime_type(asset_path.suffix)
            encoded = base64.b64encode(asset_path.read_bytes()).decode("ascii")
            return f"data:{mime_type};base64,{encoded}"

        try:
            exported = ASSET_URL_PATTERN.sub(embed, content)
        except OSError as exc:
            raise ValidationError("日记图片无法读取，导出已停止。") from exc
        return exported

    @staticmethod
    def mime_type(suffix: str) -> str:
        return {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(suffix.lower(), "application/octet-stream")

    @staticmethod
    def _detect_image(data: bytes) -> tuple[str, str]:
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png", "image/png"
        if data.startswith(b"\xff\xd8\xff"):
            return "jpg", "image/jpeg"
        if data.startswith((b"GIF87a", b"GIF89a")):
            return "gif", "image/gif"
        if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            return "webp", "image/webp"
        raise ValidationError("仅支持 PNG、JPEG、GIF 或 WebP 图片。")

    @staticmethod
    def _assert_contained(paths: RuntimePaths, path: Path) -> None:
        try:
            path.resolve(strict=False).relative_to(paths.home.resolve(strict=False))
        except ValueError as exc:
            raise ValidationError("日记附件路径无效。") from exc
