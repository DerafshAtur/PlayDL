import logging
import shutil
from contextlib import suppress
from pathlib import Path

from App.config import Settings
from Services.commands import CommandError, run_process

logger = logging.getLogger(__name__)


class File2LinkError(Exception):
    pass


def _max_bytes(settings: Settings) -> int:
    return int(settings.nixfile_max_file_mb) * 1024 * 1024


def _cleanup_parts(dest_dir: Path, stem: str) -> None:
    patterns = (f"{stem}.rar", f"{stem}.part*.rar", f"{stem}.r[0-9]*")
    for pattern in patterns:
        for path in dest_dir.glob(pattern):
            with suppress(Exception):
                path.unlink()


def _collect_parts(dest_dir: Path, stem: str) -> list[Path]:
    parts = sorted(dest_dir.glob(f"{stem}.part*.rar"))
    if parts:
        return parts
    legacy = sorted(dest_dir.glob(f"{stem}.r[0-9]*"))
    head = dest_dir / f"{stem}.rar"
    if head.exists() and legacy:
        return [head, *legacy]
    if head.exists():
        return [head]
    return []


async def package_for_upload(
    source: Path,
    dest_dir: Path,
    settings: Settings,
) -> list[Path]:
    if not source.exists():
        raise File2LinkError(f"فایل پیدا نشد: {source}")

    dest_dir.mkdir(parents=True, exist_ok=True)
    max_bytes = _max_bytes(settings)
    size = source.stat().st_size
    logger.info("file2link: source=%s size=%d limit=%d", source, size, max_bytes)

    if size <= max_bytes:
        return [source]

    rar_path = settings.rar_path or "rar"
    if not (Path(rar_path).exists() or shutil.which(rar_path)):
        raise File2LinkError(
            f"ابزار rar پیدا نشد (RAR_PATH={rar_path}). برای فشرده‌سازی فایل‌های بزرگ، rar را نصب کن."
        )

    stem = source.stem or "archive"
    _cleanup_parts(dest_dir, stem)
    archive = dest_dir / f"{stem}.rar"

    try:
        await run_process(
            [rar_path, "a", "-ep1", "-y", "-idq", str(archive), str(source)],
            cwd=dest_dir,
        )
    except CommandError as exc:
        raise File2LinkError(f"فشرده‌سازی rar ناموفق بود: {exc}") from exc

    if not archive.exists():
        raise File2LinkError("فایل rar ساخته نشد.")

    if archive.stat().st_size <= max_bytes:
        logger.info("file2link: single rar fits limit (%d bytes)", archive.stat().st_size)
        return [archive]

    archive.unlink()
    max_mb = max(1, settings.nixfile_max_file_mb)
    logger.info("file2link: splitting into %dMB volumes", max_mb)

    try:
        await run_process(
            [rar_path, "a", "-ep1", "-y", "-idq", f"-v{max_mb}m", str(archive), str(source)],
            cwd=dest_dir,
        )
    except CommandError as exc:
        raise File2LinkError(f"تقسیم rar ناموفق بود: {exc}") from exc

    parts = _collect_parts(dest_dir, stem)
    if not parts:
        raise File2LinkError("هیچ بخش rar تولید نشد.")
    logger.info("file2link: produced %d parts", len(parts))
    return parts
