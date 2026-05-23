# Configuration

All settings come from environment variables (loaded from `.env` via `pydantic-settings`). See `App/config.py` for the source of truth. A starter file lives at `.env.example`.

## Required

| Var | What |
|-----|------|
| `BOT_TOKEN` | Telegram bot token from BotFather. |

## Telegram API

| Var | Default | Notes |
|-----|---------|-------|
| `TELEGRAM_API_BASE_URL` | `https://api.telegram.org` | Point at a local Bot API server to lift the 50 MB upload limit. |
| `TELEGRAM_API_IS_LOCAL` | `false` | Must be `true` when using a local Bot API server. |

## MongoDB

| Var | Default |
|-----|---------|
| `MONGODB_URI` | `mongodb://localhost:27017` |
| `MONGODB_DB_NAME` | `playdl` |

Inside the docker-compose network the URI is overridden to `mongodb://mongo:27017`.

## Job runner

| Var | Default | Notes |
|-----|---------|-------|
| `MAX_PARALLEL_JOBS` | `4` | Global semaphore. 1–20. |

## Tools / paths

| Var | Default | Notes |
|-----|---------|-------|
| `TOOLS_DIR` | `tools` | Created at boot if missing. |
| `DOWNLOAD_DIR` | `storage/downloads` | Per-job subdir `<DOWNLOAD_DIR>/<job_id>/`. |
| `AUTO_INSTALL_TOOLS` | `true` | If true, bootstrap clones alltech-gplay and fetches APKEditor/uber-apk-signer jars at startup. |

## Downloader backend

| Var | Default | Notes |
|-----|---------|-------|
| `PLAY_DOWNLOADER_BACKEND` | `auto` | `auto` \| `alltech-gplay` \| `gplaydl` \| `apkeep` \| `custom`. |
| `PLAY_ARCH` | `arm64` | Passed to the backend as `-a`. |
| `MERGE_SPLITS` | `true` | Kept for backward compat. The bot now always re-merges with APKEditor; alltech-gplay's `-m` flag is no longer passed. |

### alltech-gplay

| Var | Default |
|-----|---------|
| `ALLTECH_GPLAY_PATH` | `tools/gplay-apk-downloader/gplay` |
| `ALLTECH_AUTO_AUTH` | `true` |
| `ALLTECH_AUTH_FILE` | `~/.gplay-auth.json` |

The bot will run `gplay auth` automatically once if the auth file is missing. On HTTP 401 from Google it deletes the auth file and re-authenticates up to twice (see `_alltech_run_with_auth_retry` in `Services/downloader.py`).

### apkeep

| Var | Default |
|-----|---------|
| `APKEEP_SOURCE` | (unset) |
| `APKEEP_EMAIL` | (unset) |
| `APKEEP_TOKEN` | (unset) |

### custom

| Var | Default |
|-----|---------|
| `PLAY_DOWNLOADER_CMD` | (unset) |

Template vars: `{url} {package} {output_dir} {arch}`.

## Conversion / signing

| Var | Default | Notes |
|-----|---------|-------|
| `APKEDITOR_JAR` | `tools/APKEditor.jar` | Auto-downloaded from latest GitHub release. |
| `APKS_TO_APK_CMD` | (unset) | Override APKEditor with your own command. Template vars: `{input} {output}`. |
| `AUTO_SIGN_APK` | `true` | If true, the merged APK is signed with uber-apk-signer. |
| `APKSIGNER_JAR` | `tools/uber-apk-signer.jar` | Auto-downloaded. |
| `SIGN_APK_CMD` | (unset) | Override uber-apk-signer with your own. Template vars: `{input} {output}`. |

The default APKEditor merge command is hardened:

```
java -jar APKEditor.jar m -i <input> -o <output> -extractNativeLibs true -clean-meta -f
```

`-extractNativeLibs true` is what prevents the "installs fine but crashes on launch" failure mode.

## NixFile (optional delivery target)

| Var | Default | Notes |
|-----|---------|-------|
| `NIXFILE_USERNAME` | (unset) | Disables NixFile delivery if blank. |
| `NIXFILE_PASS` | (unset) | |
| `NIXFILE_LOGIN_URL` | `https://panel.nixfile.com/auth/login` | |
| `NIXFILE_PANEL_URL` | `https://panel.nixfile.com` | |
| `NIXFILE_HEADLESS` | `true` | Set `false` only for local debugging. |
| `NIXFILE_UPLOAD_TIMEOUT` | `600` | Seconds. Cap for waiting on the upload card. |
| `NIXFILE_SESSION_FILE` | `storage/nixfile-session.json` | Cookies + localStorage cached here. |
| `NIXFILE_MAX_FILE_MB` | `100` | Hard cap before the bot refuses the upload. |
| `LIMIT_DAILY_IR` | `0` | Per-user daily NixFile upload quota. `0` = no limit. |

## Rubika (optional delivery target)

| Var | Default | Notes |
|-----|---------|-------|
| `RUBIKA_SESSION_NAME` | `playdl_rubika` | rubpy session filename (without `.rp`). |
| `RUBIKA_SESSION_DIR` | `storage` | Directory holding the `.rp` session file. Disables Rubika delivery if the file is missing. |
| `RUBIKA_MAX_FILE_MB` | `500` | Hard cap before the bot refuses the upload. |
| `RUBIKA_UPLOAD_TIMEOUT` | `900` | Seconds. Wraps the entire `send_message` call (init + all chunks + final ack). |

Generate the session once with `python session_rubika.py` (phone number + OTP). The resulting `.rp` file is the only persistent state — delete it to force a re-login.

The Rubika uploader rejects `.apk` extensions on user accounts, so the APK is zipped to `NitoNumber-1.zip` (compression `ZIP_STORED`, no recompression — the APK is already compressed) in a `tempfile.TemporaryDirectory` and the zip is what gets sent.

Internal tunables (not env-driven; edit `Services/rubika.py` if you need to):

| Constant | Default | Notes |
|----------|---------|-------|
| `RUBIKA_UPLOAD_CONCURRENCY` | `8` | Parallel chunk POSTs. Lower to 4 or 2 if the rubika DC rate-limits. |
| `RUBIKA_UPLOAD_CHUNK` | `1048576` (1 MB) | Chunk size for the patched uploader; matches stock rubpy. |
| `RUBIKA_ZIP_NAME` | `"NitoNumber-1.zip"` | Static filename sent to Rubika regardless of the source APK. |

## Storage hygiene

| Var | Default | Notes |
|-----|---------|-------|
| `DOWNLOADS_MAX_MB` | `500` | When the downloads dir exceeds this, the sweeper wipes it. |
| `DOWNLOADS_SWEEP_INTERVAL_S` | `3600` | Sweeper tick. |
| `NIXFILE_LINK_CHECK_INTERVAL_S` | `21600` | How often cached NixFile URLs are pinged for liveness. |
