# Deployment

## Docker (recommended)

All docker assets live under `Docker/`: `Docker/Dockerfile`, `Docker/docker-compose.yml`, `Docker/Dockerfile.dockerignore`. Build context is the repo root (compose sets `context: ..`). The image is `python:3.13-slim` plus:

- OpenJDK 17 (for `APKEditor.jar` and `uber-apk-signer.jar`)
- Google Chrome stable + system libs (for the Selenium NixFile flow)
- `git`, `wget`, `unzip`, `tini`
- The bot's Python dependencies

Selenium 4 ships its own driver manager, so chromedriver is fetched at runtime — no manual install.

### Quick start

```bash
cp .env.example .env
# edit .env: BOT_TOKEN at minimum, plus NIXFILE_* if you want NixFile delivery
docker compose -f Docker/docker-compose.yml up -d --build
docker compose -f Docker/docker-compose.yml logs -f bot
```

Tip: `export COMPOSE_FILE=Docker/docker-compose.yml` if you don't want the `-f` flag on every command.

What happens:
1. Compose starts MongoDB and waits for its healthcheck.
2. The `bot` container builds, then runs `python -u Main.py`.
3. On first boot, `ensure_tools()` clones `alltech-gplay`, builds its venv, and downloads the latest `APKEditor.jar` and `uber-apk-signer.jar` into the `tools/` volume.
4. First Play Store download triggers `gplay auth`. If you have automated-auth issues, exec into the container and run it manually:
   ```bash
   docker compose exec bot python /app/tools/gplay-apk-downloader/gplay auth
   ```

### Volumes

| Volume | Mount | Purpose |
|--------|-------|---------|
| `mongo_data` | `/data/db` | MongoDB datafiles. |
| `downloads` | `/app/storage/downloads` | Per-job working dirs. Wiped automatically when over quota. |
| `tools` | `/app/tools` | APKEditor + uber-apk-signer jars + cloned `alltech-gplay`. Survives image rebuilds. |
| `nixfile_session` | `/app/storage` | Persists `nixfile-session.json` and the rubpy `.rp` session so re-deploys don't force fresh logins. |
| `alltech_auth` | `/root` | Holds `.gplay-auth.json`. |

### shm_size

Chrome needs `--disable-dev-shm-usage` *and* a real `/dev/shm`. We allocate `shm_size: 2gb` in compose. Lower it if you must.

### Architecture caveats

- The Chrome `.deb` package only ships `amd64`. On ARM hosts (Apple Silicon, Raspberry Pi 4/5) you'll need to swap to `chromium` from Debian repos or use a different base image. The rest of the stack is arch-agnostic.

## Bare metal / venv

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
# fill in BOT_TOKEN and friends
python Main.py
```

System requirements:
- Python 3.13+
- Java 17+ (or `apt install openjdk-17-jre-headless`)
- Git (for `alltech-gplay` clone)
- MongoDB reachable at `MONGODB_URI`
- Chrome + matching shared libs if you want NixFile delivery

## Local Bot API server (lift the 50 MB cap)

Telegram's hosted Bot API caps document uploads at 50 MB. To deliver larger APKs through Telegram, run a [local Bot API server](https://github.com/tdlib/telegram-bot-api) and point the bot at it:

```env
TELEGRAM_API_BASE_URL=http://telegram-bot-api:8081
TELEGRAM_API_IS_LOCAL=true
```

Add that service to your compose stack. Without it, fall back to NixFile or Rubika delivery for big files (and lower the matching `*_MAX_FILE_MB` accordingly).

## Rubika session bootstrap

Rubika delivery needs a one-time interactive login to mint the rubpy `.rp` session. Inside the container (or on the host venv):

```bash
python session_rubika.py
```

Enter the bot account's phone number, then the OTP rubika sends to that account. The script writes `storage/<RUBIKA_SESSION_NAME>.rp` (default `storage/playdl_rubika.rp`). The session survives restarts because `storage/` is on the `nixfile_session` volume.

If the session is later revoked you'll see `Rubika session is invalid or revoked` on the next upload — delete the `.rp` file and re-run the script.

## Operations

### Logs

All logging goes to stdout in the standard `asctime | level | name | message` format. `docker compose -f Docker/docker-compose.yml logs -f bot` is the standard tail. Notable prefixes:
- `[nixfile]` — Selenium uploader. Debug artifacts (screenshots, page source) land in `storage/nixfile-debug/` on every failure.
- `[rubika]` — rubpy uploader. Look for `parallel uploader installed`, `zipped to NitoNumber-1.zip`, `upload N% (... KB/s ...)`, and `TIMEOUT after Xs, last_pct=N, idle_for=Δs` on failures.
- `downloads_sweeper` / `nixfile_link_checker` — background tasks.

### Disk

Three things eat disk:
1. Per-job downloads (`storage/downloads/<job_id>/`). Capped by `DOWNLOADS_MAX_MB`.
2. The Mongo `package_cache` collection. `apk_path` entries may outlive the disk file; the cache code re-checks existence before serving from cache.
3. `tools/` is small (~30 MB jars + alltech repo venv).

If you want to force a re-download for a single package (e.g. you upgraded the merger and want to invalidate stale outputs):

```bash
docker compose -f Docker/docker-compose.yml exec mongo mongosh playdl --eval \
  'db.package_cache.deleteOne({_id:"com.example.app"})'
```

### Restart hygiene

The container traps SIGTERM cleanly (`tini` is PID 1). On restart:
- In-flight downloads are lost — relaunch them by re-sending the link.
- Selenium session survives via the `nixfile_session` volume.
- Mongo state survives.

### Common failures

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `gplay auth` fails on first run | Google account challenge requires interactive auth | Set `NIXFILE_HEADLESS=false` doesn't help here — instead run `gplay auth` interactively, copy the resulting `~/.gplay-auth.json` into the `alltech_auth` volume. |
| `APKEditor.jar پیدا نشد` | Auto-install blocked or `tools/` volume not writable | `AUTO_INSTALL_TOOLS=true` and check perms on the `tools` volume. |
| `جلسه مرورگر قطع شد` | Chrome OOM-killed | Raise `shm_size` in compose. |
| App installs but crashes on launch | Pre-fix merge artifact still cached | Wipe the `downloads` volume and the matching `package_cache` row, then re-request. The current merge command uses `-extractNativeLibs true` and this no longer happens for fresh runs. |
| `سقف روزانه آپلود` | `LIMIT_DAILY_IR` exhausted for that user | Either raise the limit or use Telegram delivery. |
| `Rubika غیرفعال است` | `.rp` session file missing | Run `python session_rubika.py` and restart the bot. |
| Rubika `upload timed out at N% after Xs` | DC slow / single-conn capped | Drop `RUBIKA_UPLOAD_CONCURRENCY` to 4 if you also see "Server requested reinitialization"; otherwise raise `RUBIKA_UPLOAD_TIMEOUT`. |
| Rubika `Bad Request: message is not modified` | Same text/markup edit | Already swallowed by `_safe_edit_text` in `Handlers/links.py`. If you see it again it's from a different `edit_text` site — wrap it the same way. |

### Updating

```bash
git pull
docker compose -f Docker/docker-compose.yml build bot
docker compose -f Docker/docker-compose.yml up -d
```

The `tools` and `downloads` volumes persist, so jar updates only happen if the auto-installer notices they're missing (which is rare). To force-refresh the jars, delete them from the `tools` volume before restarting:

```bash
docker compose -f Docker/docker-compose.yml exec bot rm /app/tools/APKEditor.jar /app/tools/uber-apk-signer.jar
docker compose -f Docker/docker-compose.yml restart bot
```
