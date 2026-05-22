"""Interactive Rubika session bootstrap.

Run once on the machine where the bot will live. Prompts for phone (+ OTP
and optional 2FA password if rubpy asks), then writes the session file
at storage/<RUBIKA_SESSION_NAME>.rp. The bot picks it up next start.

Usage:
    python session_rubika.py
    python session_rubika.py --phone 09xxxxxxxxx
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from rubpy import Client

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from App.config import Settings  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Create a Rubika session file for the bot.")
    p.add_argument("--phone", help="phone number (e.g. 09xxxxxxxxx). Prompts if omitted.")
    return p.parse_args()


async def amain() -> int:
    args = parse_args()
    os.environ.setdefault("BOT_TOKEN", "dummy")  # Settings needs it for validation.
    settings = Settings()
    settings.rubika_session_dir.mkdir(parents=True, exist_ok=True)
    session_name = str(settings.rubika_session_dir / settings.rubika_session_name)
    session_file = Path(session_name + ".rp")

    print(f"[i] session will be written to: {session_file}")
    if session_file.exists():
        print(f"[!] {session_file} already exists. Delete it first if you want a fresh login.")
        return 1

    phone = args.phone or input("Phone number (e.g. 09xxxxxxxxx): ").strip()
    if not phone:
        print("[!] phone is required.")
        return 2

    client = Client(session_name)
    print("[*] starting rubpy client (will prompt for OTP / 2FA password) ...")
    try:
        await client.start(phone_number=phone)
        me = await client.get_me()
        print("[+] logged in successfully:")
        print(f"    user_guid : {me.user.user_guid}")
        print(f"    name      : {getattr(me.user, 'first_name', '') or '?'}")
        print(f"    username  : @{getattr(me.user, 'username', '') or '?'}")
        print(f"[+] session file: {session_file}")
    except Exception as exc:  # noqa: BLE001
        print(f"[X] login failed: {type(exc).__name__}: {exc}")
        return 1
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
    return 0


def main() -> int:
    try:
        return asyncio.run(amain())
    except KeyboardInterrupt:
        print("[!] interrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
