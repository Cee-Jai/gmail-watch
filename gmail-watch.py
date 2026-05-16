#!/usr/bin/env python3
"""
gmail-watch — monitor Gmail inbox for new emails and send persistent desktop notifications.

First-time setup:
  gmail-watch --setup

Usage:
  gmail-watch [--interval SECONDS] [--quiet]
"""

import argparse
import configparser
import getpass
import imaplib
import os
import stat
import subprocess
import sys
import time
from datetime import datetime
from email import message_from_bytes
from email.header import decode_header

CONFIG_DIR  = os.path.expanduser("~/.config/gmail-watch")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config")
IMAP_HOST   = "imap.gmail.com"
IMAP_PORT   = 993
DEFAULT_INTERVAL = 60


# ── helpers ──────────────────────────────────────────────────────────────────

def decode_str(value):
    """Decode an encoded email header value to a plain string."""
    parts = decode_header(value or "")
    out = []
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            out.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(chunk)
    return "".join(out)


def fmt_time():
    return datetime.now().strftime("%H:%M:%S")


def desktop_notify(title: str, body: str):
    """Send a persistent desktop notification that stays until dismissed."""
    try:
        subprocess.run(
            [
                "notify-send",
                "--app-name", "gmail-watch",
                "--urgency", "critical",
                "--expire-time", "0",
                "--hint", "boolean:resident:true",
                "--hint", "boolean:transient:false",
                "--icon", "mail-unread",
                title,
                body,
            ],
            timeout=5, check=False
        )
    except FileNotFoundError:
        pass


# ── setup ────────────────────────────────────────────────────────────────────

def run_setup():
    print("=== gmail-watch setup ===")
    print("You need a Gmail App Password (not your regular password).")
    print("Get one at: Google Account → Security → 2-Step Verification → App Passwords\n")

    email = input("Gmail address: ").strip()
    password = getpass.getpass("App Password (16 chars, spaces OK): ").replace(" ", "")

    print("\nVerifying credentials...", end=" ", flush=True)
    try:
        conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        conn.login(email, password)
        conn.logout()
        print("OK")
    except imaplib.IMAP4.error as e:
        print(f"FAILED\nError: {e}")
        print("Check your email and App Password and try again.")
        sys.exit(1)

    os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)

    cfg = configparser.ConfigParser()
    cfg["gmail"] = {"email": email, "app_password": password}
    with open(CONFIG_FILE, "w") as f:
        cfg.write(f)
    # restrict to owner read/write only
    os.chmod(CONFIG_FILE, stat.S_IRUSR | stat.S_IWUSR)

    print(f"Credentials saved to {CONFIG_FILE} (mode 600)")
    print("\nRun  gmail-watch  to start monitoring.")


def load_config():
    if not os.path.exists(CONFIG_FILE):
        print("No config found. Run:  gmail-watch --setup")
        sys.exit(1)
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE)
    return cfg["gmail"]["email"], cfg["gmail"]["app_password"]


# ── monitor ──────────────────────────────────────────────────────────────────

def connect(email, password):
    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    conn.login(email, password)
    conn.select("INBOX")
    return conn


def fetch_unseen_ids(conn):
    _, data = conn.search(None, "UNSEEN")
    ids = data[0].split()
    return set(ids)


def fetch_email_preview(conn, msg_id):
    """Return (sender, subject) for a message ID."""
    try:
        _, data = conn.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
        raw = data[0][1]
        msg = message_from_bytes(raw)
        sender  = decode_str(msg.get("From", "Unknown"))
        subject = decode_str(msg.get("Subject", "(no subject)"))
        return sender, subject
    except Exception:
        return "Unknown", "(could not read)"


def monitor(email, password, interval, quiet):
    print(f"[gmail-watch] Connecting as {email}...")
    try:
        conn = connect(email, password)
    except Exception as e:
        print(f"Connection failed: {e}", file=sys.stderr)
        sys.exit(1)

    known_ids = fetch_unseen_ids(conn)
    print(f"[gmail-watch] Connected — {len(known_ids)} unread email(s) at start")
    print(f"[gmail-watch] Polling every {interval}s — press Ctrl+C to stop\n")

    while True:
        time.sleep(interval)
        try:
            # NOOP keeps the connection alive; reconnect if it drops
            conn.noop()
        except Exception:
            try:
                conn = connect(email, password)
            except Exception as e:
                print(f"[{fmt_time()}] Reconnect failed: {e} — retrying next interval")
                continue

        try:
            current_ids = fetch_unseen_ids(conn)
        except Exception as e:
            print(f"[{fmt_time()}] Fetch error: {e}")
            continue

        new_ids = current_ids - known_ids

        if new_ids:
            for msg_id in sorted(new_ids):
                sender, subject = fetch_email_preview(conn, msg_id)
                short_sender = sender.split("<")[0].strip() or sender
                msg = f"From: {short_sender}\n{subject[:80]}"
                print(f"[{fmt_time()}] New email — {short_sender}: {subject[:60]}")
                if not quiet:
                    desktop_notify("New Gmail", msg)
            known_ids = current_ids
        else:
            print(f"[{fmt_time()}] No new email ({len(current_ids)} unread)")


# ── entry point ───────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Monitor Gmail inbox for new emails.")
    p.add_argument("--setup", action="store_true", help="First-time credential setup")
    p.add_argument("--interval", type=int, default=DEFAULT_INTERVAL,
                   help=f"Poll interval in seconds (default: {DEFAULT_INTERVAL})")
    p.add_argument("--quiet", action="store_true",
                   help="No desktop notifications, terminal only")
    return p.parse_args()


def main():
    args = parse_args()
    if args.setup:
        run_setup()
        return
    email, password = load_config()
    monitor(email, password, args.interval, args.quiet)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[gmail-watch] Stopped.")
