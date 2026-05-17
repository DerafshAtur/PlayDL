from pathlib import Path

from aiogram.types import Message

from Services.downloader import DownloadError
from Utils.html import bold, safe
from Utils.keyboards import delivery_keyboard, main_keyboard
from Utils.progress import DiskSizeProgress
from Utils.texts import (
    CONVERTING_TEXT,
    DELIVERY_PROMPT_TEXT,
    DOWNLOAD_TITLE,
    FAILED_TEXT,
)


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
