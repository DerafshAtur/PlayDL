# PlayDL — Overview

PlayDL is a Persian-language Telegram bot that downloads apps from Google Play, merges split APKs into a single installable APK, optionally signs it, and delivers it through one of three channels: a Telegram document, a hosted link on NixFile, or a direct file send to a Rubika `@username` from the bot-owned Rubika account.

## What it does

1. User sends a Google Play URL (`https://play.google.com/store/apps/details?id=<package>`).
2. Bot extracts the package name and queues a job.
3. A downloader backend (`alltech-gplay` / `gplaydl` / `apkeep` / custom) fetches the app from Google Play servers.
4. `ApksConverter` merges split APKs into one `.apk` using `APKEditor.jar`.
5. Optional: `uber-apk-signer.jar` signs the APK so Android accepts it for installation.
6. User chooses delivery: direct Telegram upload, NixFile (Selenium), or Rubika (rubpy with parallel-chunk upload patch).
7. Result cached in MongoDB. Future requests for the same package short-circuit through the cache.

## Tech stack

- **Python 3.13**, `asyncio`, `aiogram 3.28` for the Telegram side.
- **MongoDB** (`pymongo` async client) for user state, jobs, and package cache.
- **APKEditor** (Java) — split-APK merging.
- **uber-apk-signer** (Java) — automatic signing.
- **Selenium + Chrome** — NixFile browser automation.
- **rubpy** — Rubika user-account client, with an in-tree parallel-chunk uploader monkey-patch.
- **pydantic-settings** — configuration via `.env`.

## Source layout

```
App/        bot + config + entrypoint glue
Handlers/   aiogram routers (start, links, errors)
Services/   downloader, converter, jobs queue, nixfile uploader, rubika uploader, sweeper, bootstrap
DataBase/   MongoDB wrapper
Utils/      keyboards, texts, html, progress renderers
Main.py     async main, signal handling, polling loop
```

## Document map

- [01-overview.md](01-overview.md) — this file.
- [02-architecture.md](02-architecture.md) — components, data flow, responsibilities.
- [03-configuration.md](03-configuration.md) — every env var and what it does.
- [04-pipeline.md](04-pipeline.md) — download → merge → sign → deliver, end to end.
- [05-deployment.md](05-deployment.md) — Docker, compose, ops, troubleshooting.
