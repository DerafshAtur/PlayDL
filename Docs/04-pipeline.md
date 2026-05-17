# Pipeline

End-to-end trace of one request, with the exact file/line responsibilities.

## 1. Inbound message

`Handlers/links.py :: GooglePlayLinkHandler.handle()`

- Validate scheme + host via `is_google_play_url`.
- Extract `?id=` via `extract_package_name`.
- Reject if `job_runner.user_busy(uid)` (one job per user at a time).
- Reject if `job_runner.available` is false (global queue full).
- Hand off to `JobRunner.run(uid, self._process(...))`.

## 2. Cache lookup

`_process()` first checks `db.get_package_cache(package_name)`. If a cached `apk_path` exists and the file is still on disk, the pipeline short-circuits straight to the delivery prompt.

## 3. Download

`Services/downloader.py :: PlayDownloader.download()`

- Creates `<DOWNLOAD_DIR>/<job_id>/`.
- Picks a backend via `_resolve_backend()`:
  - `auto` order: alltech-gplay → gplaydl → apkeep → custom.
- Runs the backend as a subprocess. For alltech-gplay this is `[<gplay-path> download <pkg> -a <arch> -o <out>]` (no `-m` — we always merge ourselves; see step 4).
- On HTTP 401 from Google, deletes the auth file and re-runs `gplay auth` (up to two retries).

`PlayDownloader._select_download_result()` inspects the output dir and returns one of:
- the single `.apk` if there was only one;
- the single `.apks` if there were no plain APKs;
- the directory itself if multiple APK files are present (likely splits).

Throughout this step, `DiskSizeProgress` polls the directory size every 1.5 s and edits the user-facing message with bytes-downloaded + bytes/sec.

## 4. Merge → single APK

`Services/converter.py :: ApksConverter.to_apk()`

If the downloader returned:

- a single `.apk` → use it as-is.
- a `.apks` (zip) → merge via APKEditor.
- a directory:
  - find all `*.apk` recursively (ignoring any `merged.apk` left over by upstream tools);
  - if there's a `base.apk` plus at least one non-base split, **always re-merge** from the dir containing `base.apk`. This is the fix for the historical "installs but crashes" bug — the bot no longer trusts pre-merged outputs from third-party tools because they routinely produced APKs with broken `extractNativeLibs` handling.
  - else fall back to picking the single APK or any pre-existing `merged.apk`.

The merge command itself:

```
java -jar APKEditor.jar m -i <splits-dir> -o <merged.apk> -extractNativeLibs true -clean-meta -f
```

Why each flag matters:
- `-extractNativeLibs true` — forces `android:extractNativeLibs="true"` in the merged manifest and stores `.so` files compressed. The OS extracts them at install time, which sidesteps the page-alignment requirements that split APKs assume. Without this flag, the merged APK installs but the linker can't `mmap` libraries at launch → instant crash.
- `-clean-meta` — strips the `META-INF/` signature block from the inputs so the next signing step starts from a clean slate.
- `-f` — overwrite any leftover `merged.apk`.

## 5. Sign

`ApksConverter._sign_if_configured()`

- If `SIGN_APK_CMD` is set, render and run it.
- Else if `AUTO_SIGN_APK=true` (default), run `uber-apk-signer.jar`:

```
java -jar uber-apk-signer.jar --apks <merged.apk> --overwrite --allowResign
```

`--overwrite` replaces the input file in place (size before/after is logged). uber-apk-signer also zipaligns before signing, so the resulting APK is install-ready.

Job is marked `ready` in Mongo, and the package cache is updated (`set_package_apk`).

## 6. Delivery prompt

`Handlers/links.py :: DeliveryCallback.handle()`

User taps Telegram (`deliver:tg:<id>`) or NixFile (`deliver:nx:<id>`).

### Telegram upload

`_deliver_telegram()`

- Spinner driven by `AnimatedProgress`.
- `event.message.answer_document(FSInputFile(apk_path, ...))`.
- Status message deleted, job marked `done`, delivery mode persisted.

### NixFile upload

`_deliver_nixfile()`

- Re-check Mongo cache: if a cached `nixfile_url` exists and `is_nixfile_url_alive()` says yes, return that link immediately.
- Otherwise quota check (`LIMIT_DAILY_IR`) and size check (`NIXFILE_MAX_FILE_MB`).
- `NixfileUploader.upload()` runs the Selenium flow in a worker thread:
  1. Reuse existing Chrome instance if alive.
  2. Try to restore session from `storage/nixfile-session.json`.
  3. Otherwise enter username → submit → password → submit, then save cookies + localStorage for next time.
  4. Navigate to `/media`.
  5. `send_keys(file_path)` into the file input.
  6. Poll the upload widget (Persian text + percentage) until the new card matching the uploaded file appears.
  7. Open the card's menu, click "کپی لینک". A `navigator.clipboard.writeText` hook captures the URL; DOM fallbacks also exist.
- `SnapshotProgress` streams the widget text + percent into the Telegram status message.
- The URL is stored via `db.set_package_nixfile`. The link checker will revisit it later and clear it if it dies.

## 7. Background hygiene

Two long-running tasks loop alongside polling (`Services/sweeper.py`):

- **downloads_sweeper** — every `DOWNLOADS_SWEEP_INTERVAL_S` it sums file sizes under `DOWNLOAD_DIR`; if total ≥ `DOWNLOADS_MAX_MB`, it wipes the directory. This is why long-lived cache should be moved out of `DOWNLOAD_DIR` if you ever change behavior.
- **nixfile_link_checker** — every `NIXFILE_LINK_CHECK_INTERVAL_S` it iterates every package with a cached NixFile URL and HEAD/GETs it. Dead links (404, Persian "deleted/expired" markers) are cleared from the cache.

## 8. Shutdown

`Main.main()` registers `_on_signal` for SIGINT/SIGTERM. The handler kills the chromedriver subprocess (so any in-flight Selenium HTTP call fails fast instead of looping) and calls `dp.stop_polling()`. The `finally` block then cancels background tasks, closes the aiogram session, and closes the Mongo client.
