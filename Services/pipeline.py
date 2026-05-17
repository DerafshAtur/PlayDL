import logging
from pathlib import Path

from aiogram.types import Message

from Services.downloader import DownloadError
from Services.search import fetch_app_title
from Utils.filename import sanitize_filename_stem
from Utils.html import bold, safe
from Utils.keyboards import delivery_keyboard, main_keyboard
from Utils.progress import DiskSizeProgress
from Utils.texts import (
    CONVERTING_TEXT,
    DELIVERY_PROMPT_TEXT,
    DOWNLOAD_TITLE,
    FAILED_TEXT,
)

logger = logging.getLogger(__name__)


async def _rename_apk_for_app(apk_path: Path, package_name: str) -> Path:
    title = await fetch_app_title(package_name)
    stem = sanitize_filename_stem(title or package_name, fallback=package_name)
    target = apk_path.with_name(f"{stem}.apk")
    if target == apk_path:
        return apk_path
    try:
        if target.exists():
            target.unlink()
        apk_path.rename(target)
    except OSError as exc:
        logger.warning("rename %s -> %s failed: %s", apk_path, target, exc)
        return apk_path
    return target


async def run_download_pipeline(
    *,
    event_message: Message,
    user_id: int,
    url: str,
    package_name: str,
    deps: dict,
) -> None:
    db = deps["db"]
    downloader = deps["downloader"]
    converter = deps["converter"]
    settings = deps["settings"]

    job_id = await db.create_job(user_id, package_name, url)
    package_label = bold(package_name)

    cache = await db.get_package_cache(package_name)
    cached_apk = None
    if cache and cache.get("apk_path"):
        candidate = Path(cache["apk_path"])
        if candidate.exists():
            cached_apk = candidate

    if cached_apk is not None:
        cached_apk = await _rename_apk_for_app(cached_apk, package_name)
        await db.set_package_apk(package_name, str(cached_apk))
        status_message = await event_message.answer(
            f"{DOWNLOAD_TITLE}\n\n{package_label}\n\n♻️ از کش استفاده شد"
        )
        await db.update_job(
            job_id, "ready", source_path=str(cached_apk), apk_path=str(cached_apk)
        )
        await status_message.edit_text(
            DELIVERY_PROMPT_TEXT, reply_markup=delivery_keyboard(job_id)
        )
        return

    status_message = await event_message.answer(
        f"{DOWNLOAD_TITLE}\n\n{package_label}\n\n📥 0 B  •  0 B/s"
    )

    download_dir = settings.download_dir / str(job_id)
    download_dir.mkdir(parents=True, exist_ok=True)
    download_progress: DiskSizeProgress | None = None

    try:
        download_progress = DiskSizeProgress(
            status_message, DOWNLOAD_TITLE, package_label, download_dir
        )
        download_progress.start()
        source_path = await downloader.download(url=url, package_name=package_name, job_id=job_id)
        await download_progress.stop()
        download_progress = None
        await db.update_job(job_id, "downloaded", source_path=str(source_path))

        await status_message.edit_text(CONVERTING_TEXT)
        apk_path = await converter.to_apk(source_path)
        apk_path = await _rename_apk_for_app(apk_path, package_name)
        await db.update_job(job_id, "ready", apk_path=str(apk_path))
        await db.set_package_apk(package_name, str(apk_path))

        await status_message.edit_text(
            DELIVERY_PROMPT_TEXT, reply_markup=delivery_keyboard(job_id)
        )
    except DownloadError as exc:
        if download_progress:
            await download_progress.stop()
        await db.update_job(job_id, "failed", error=str(exc))
        await status_message.edit_text(
            FAILED_TEXT.format(error=safe(exc)),
            reply_markup=main_keyboard(),
        )
    except Exception as exc:
        if download_progress:
            await download_progress.stop()
        await db.update_job(job_id, "failed", error=str(exc))
        await status_message.edit_text(
            FAILED_TEXT.format(error=safe(exc)),
            reply_markup=main_keyboard(),
        )
