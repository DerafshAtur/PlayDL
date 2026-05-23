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

User taps Telegram (`deliver:tg:<id>`), NixFile (`deliver:nx:<id>`), or Rubika (`deliver:rb:<id>`).

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

### Rubika upload

`_deliver_rubika()` (in `Handlers/links.py`)

1. Check `RubikaUploader.enabled` — false if the `.rp` session file is missing → user is told to ask the admin to run `python session_rubika.py`.
2. Size gate: refuse if the APK exceeds `RUBIKA_MAX_FILE_MB`.
3. Push the user into FSM state `RubikaDeliveryStates.waiting_username` and ask for `@username`. `GooglePlayLinkHandler` is gated by `StateFilter(None)`, so it doesn't intercept the reply.
4. `RubikaUsernameHandler` validates the username (alnum + underscore), clears the state, and calls `RubikaUploader.send_file(apk, username, caption)`.
5. `send_file()`:
   - `connect()` — idempotent. Runs `client.start()` once (mandatory; this is what populates `client.import_key`, the RSA signing key — `client.connect()` alone leaves it `None` and every API call crashes with `pkcs1_15.sign(None, ...)`). After `start()`, `_install_parallel_uploader()` swaps `client.connection.upload_file` for `_parallel_upload_file`.
   - `resolve_username()` — calls `client.get_object_by_username(username)` and pulls the GUID from `user`/`channel`.
   - Zip the APK to `NitoNumber-1.zip` in a `tempfile.TemporaryDirectory` off-thread via `asyncio.to_thread(_zip_file, ...)` (Rubika rejects `.apk` from user accounts).
   - `await asyncio.wait_for(client.send_message(...), timeout=RUBIKA_UPLOAD_TIMEOUT)` with `file_inline=str(zip_path)`, `type="File"`, and a progress callback that logs `[rubika] upload N% (X/Y bytes, R KB/s, +Δs)` every 5 %.
   - The patched `_parallel_upload_file` (in `Services/rubika.py`) reuses the stock rubpy init handshake (`request_send_file`), then `asyncio.gather`s up to `RUBIKA_UPLOAD_CONCURRENCY` chunk POSTs at once under a semaphore. Each worker opens its own aiofiles handle and seeks to its offset. Per-chunk retry (3 attempts, exponential backoff) is preserved. On `ERROR_TRY_AGAIN` from the server, an event short-circuits all workers and the outer `while` loop re-inits and restarts from chunk 1 — exactly matching stock rubpy semantics.
   - On timeout, the error log includes `last_pct` and `idle_for=Δs` so you can tell init-hang (`last_pct=-1`) from mid-upload stall (`last_pct=N, idle_for=big`) from a genuinely slow link (`last_pct=N, idle_for=small`).
6. On success, job is marked `done`, delivery mode persisted as `"rubika"`, and `_maybe_delete_after_upload` cleans the local APK if `KEEP_FILES=false`. Nothing is cached in Mongo for Rubika — every recipient gets a fresh send.

## 7. Background hygiene

Two long-running tasks loop alongside polling (`Services/sweeper.py`):

- **downloads_sweeper** — every `DOWNLOADS_SWEEP_INTERVAL_S` it sums file sizes under `DOWNLOAD_DIR`; if total ≥ `DOWNLOADS_MAX_MB`, it wipes the directory. This is why long-lived cache should be moved out of `DOWNLOAD_DIR` if you ever change behavior.
- **nixfile_link_checker** — every `NIXFILE_LINK_CHECK_INTERVAL_S` it iterates every package with a cached NixFile URL and HEAD/GETs it. Dead links (404, Persian "deleted/expired" markers) are cleared from the cache.

## 8. Shutdown

`Main.main()` registers `_on_signal` for SIGINT/SIGTERM. The handler kills the chromedriver subprocess (so any in-flight Selenium HTTP call fails fast instead of looping) and calls `dp.stop_polling()`. The `finally` block then cancels background tasks, closes the aiogram session, and closes the Mongo client.
