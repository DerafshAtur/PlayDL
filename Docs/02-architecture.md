# Architecture

## Process model

Single Python process. `Main.py` builds the dispatcher, wires services into the aiogram DI container, and starts `dp.start_polling(bot)`. Two background tasks run alongside polling:

- `downloads_sweeper` — periodic disk-quota enforcement on `storage/downloads/`.
- `nixfile_link_checker` — periodic health check of cached NixFile URLs, clearing dead links.

Signal handlers (`SIGINT`, `SIGTERM`) force-kill the Selenium chromedriver subprocess and stop polling cleanly.

## Module responsibilities

### App/
- **App/main.py** — re-exports nothing useful; entry is `Main.py` at repo root.
- **App/bot.py** — builds the `aiogram.Bot` with an `AiohttpSession` pointed at either the public Telegram API or a local Bot API server (`TELEGRAM_API_IS_LOCAL=true`).
- **App/config.py** — `Settings` pydantic model. Loaded once at boot via `load_settings()`, which also ensures `tools_dir` and `download_dir` exist.

### Handlers/
- **start.py** — `/start` command. Upserts the user into Mongo and shows the main keyboard.
- **links.py** — the workhorse. Three handlers:
  - `SendLinkCallback` (the inline button)
  - `GooglePlayLinkHandler` (text messages): validates URL, extracts package, runs the full download/convert pipeline, asks user how to deliver.
  - `DeliveryCallback`: handles `deliver:tg:<id>` and `deliver:nx:<id>` callbacks; uploads to Telegram or to NixFile.
- **errors.py** — global aiogram error handler. Logs full traceback and sends a Persian-language fallback message to the user.

### Services/
- **commands.py** — thin `asyncio.create_subprocess_*` wrappers, `CommandError`, timeout enforcement (default 900s).
- **bootstrap.py** — `ensure_tools(settings)` runs at boot. Clones the `alltech-gplay` repo, builds its venv, ensures auth token, downloads latest `APKEditor.jar` and `uber-apk-signer.jar` from GitHub releases.
- **downloader.py** — `PlayDownloader` chooses a backend (alltech-gplay default), runs it, and `_select_download_result()` picks the right artifact from the output directory (single `.apk`, single `.apks`, or a directory of splits).
- **converter.py** — `ApksConverter.to_apk()` materializes a single installable APK. Merges split directories using APKEditor with `-extractNativeLibs true -clean-meta -f` (this is what makes the merged APK actually run, not just install — see [04-pipeline.md](04-pipeline.md)).
- **jobs.py** — `JobRunner`. Global semaphore (`MAX_PARALLEL_JOBS`) + per-user lock to prevent the same user spamming concurrent jobs.
- **nixfile.py** — Selenium-driven uploader for `panel.nixfile.com`. Persists session to disk so subsequent uploads skip login. Surfaces live progress via `progress_snapshot()` consumed by `SnapshotProgress`.
- **sweeper.py** — `downloads_sweeper` (disk GC) + `nixfile_link_checker` (link health).
- **extract.py** — pure helpers: `is_google_play_url`, `extract_package_name`.

### DataBase/
- **mongo.py** — `Database` wraps the async MongoDB client. Collections:
  - `users` — `{telegram_id, full_name, created_at, updated_at}`
  - `jobs` — `{_id (counter), user_id, package_name, url, status, source_path, apk_path, delivery_mode, error, timestamps}`
  - `package_cache` — `{_id=package_name, apk_path, nixfile_url, nixfile_uploaded_at, nixfile_checked_at}`
  - `counters` — atomic job-id sequence

### Utils/
- **keyboards.py** — inline keyboards (main menu, cancel, delivery picker, link button).
- **texts.py** — all Persian copy in one place.
- **progress.py** — three progress renderers that edit the same Telegram message:
  - `AnimatedProgress` — fake percentage tick for Telegram upload.
  - `DiskSizeProgress` — real bytes/sec from watching the download dir grow.
  - `SnapshotProgress` — reads `nixfile.progress_snapshot()` for the upload widget.
- **html.py** — `bold()` / `safe()` HTML escaping.

## Data flow (happy path)

```
user → Telegram → aiogram Dispatcher
                    │
                    ▼
           GooglePlayLinkHandler
                    │
       ┌────────────┴────────────┐
       ▼                         ▼
  Database.get_package_cache   JobRunner.run
       │                         │
       │ (miss)                  ▼
       │                  PlayDownloader.download
       │                         │  (subprocess: gplay/gplaydl/apkeep)
       │                         ▼
       │                  ApksConverter.to_apk
       │                         │  (java -jar APKEditor.jar m ...)
       │                         │  (java -jar uber-apk-signer.jar ...)
       │                         ▼
       └────────── set_package_apk in Mongo
                                 │
                                 ▼
                        DeliveryCallback
                       /                 \
                  tg upload            nixfile selenium upload
                      │                       │
                      ▼                       ▼
                   Telegram               panel.nixfile.com
```

## Concurrency model

- One asyncio loop. Subprocesses run via `asyncio.subprocess`.
- Selenium runs synchronously inside `asyncio.to_thread` guarded by an `asyncio.Lock` (one upload at a time per process).
- `JobRunner` semaphore caps total parallel downloads at `MAX_PARALLEL_JOBS`. Per-user `asyncio.Lock` prevents one user from queueing multiple jobs at once.
- Background tasks (`sweeper`, `link_checker`) are cancelled on shutdown via the `finally` block in `Main.main()`.
