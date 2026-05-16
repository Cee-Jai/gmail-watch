#!/usr/bin/env python3
"""
gmail-watch — monitor one or more Gmail inboxes with persistent desktop notifications.

Setup an account:
  gmail-watch --setup --account personal
  gmail-watch --setup --account work

Monitor:
  gmail-watch                        # all configured accounts
  gmail-watch --account personal     # one account only
  gmail-watch --interval 30          # custom poll interval
  gmail-watch --list                 # show configured accounts
"""

import argparse
import configparser
import getpass
import imaplib
import os
import stat
import subprocess
import sys
import threading
import time
from datetime import datetime
from email import message_from_bytes
from email.header import decode_header

CONFIG_DIR    = os.path.expanduser("~/.config/gmail-watch")
IMAP_HOST     = "imap.gmail.com"
IMAP_PORT     = 993
DEFAULT_INTERVAL = 60


# ── helpers ──────────────────────────────────────────────────────────────────

def decode_str(value):
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


# ── config ───────────────────────────────────────────────────────────────────

def config_path(account: str) -> str:
    return os.path.join(CONFIG_DIR, f"{account}.conf")


def list_accounts() -> list[str]:
    if not os.path.isdir(CONFIG_DIR):
        return []
    return [f[:-5] for f in os.listdir(CONFIG_DIR) if f.endswith(".conf")]


def load_account(account: str) -> tuple[str, str]:
    path = config_path(account)
    if not os.path.exists(path):
        print(f"No config for account '{account}'. Run:  gmail-watch --setup --account {account}")
        sys.exit(1)
    cfg = configparser.ConfigParser()
    cfg.read(path)
    return cfg["gmail"]["email"], cfg["gmail"]["app_password"]


def run_setup(account: str):
    print(f"=== gmail-watch setup — account: {account} ===")
    print("You need a Gmail App Password (not your regular password).")
    print("Get one at: myaccount.google.com/apppasswords\n")

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
        sys.exit(1)

    os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)
    path = config_path(account)
    cfg = configparser.ConfigParser()
    cfg["gmail"] = {"email": email, "app_password": password}
    with open(path, "w") as f:
        cfg.write(f)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)

    print(f"Saved to {path} (mode 600)")
    accounts = list_accounts()
    print(f"\nConfigured accounts: {', '.join(accounts)}")
    print("Run  gmail-watch  to monitor all accounts.")


# ── monitor ──────────────────────────────────────────────────────────────────

def connect(email, password):
    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    conn.login(email, password)
    conn.select("INBOX")
    return conn


def fetch_unseen_ids(conn):
    _, data = conn.search(None, "UNSEEN")
    return set(data[0].split())


def fetch_email_preview(conn, msg_id):
    try:
        _, data = conn.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
        msg = message_from_bytes(data[0][1])
        sender  = decode_str(msg.get("From", "Unknown"))
        subject = decode_str(msg.get("Subject", "(no subject)"))
        return sender, subject
    except Exception:
        return "Unknown", "(could not read)"


def monitor_account(account: str, email: str, password: str, interval: int, quiet: bool):
    label = f"[{account}]"
    print(f"{label} Connecting as {email}...")
    try:
        conn = connect(email, password)
    except Exception as e:
        print(f"{label} Connection failed: {e}", file=sys.stderr)
        return

    known_ids = fetch_unseen_ids(conn)
    print(f"{label} Connected — {len(known_ids)} unread at start")

    while True:
        time.sleep(interval)
        try:
            conn.noop()
        except Exception:
            try:
                conn = connect(email, password)
            except Exception as e:
                print(f"[{fmt_time()}] {label} Reconnect failed: {e}")
                continue

        try:
            current_ids = fetch_unseen_ids(conn)
        except Exception as e:
            print(f"[{fmt_time()}] {label} Fetch error: {e}")
            continue

        new_ids = current_ids - known_ids
        if new_ids:
            for msg_id in sorted(new_ids):
                sender, subject = fetch_email_preview(conn, msg_id)
                short_sender = sender.split("<")[0].strip() or sender
                print(f"[{fmt_time()}] {label} New email — {short_sender}: {subject[:60]}")
                if not quiet:
                    desktop_notify(
                        f"New Gmail ({account})",
                        f"From: {short_sender}\n{subject[:80]}"
                    )
            known_ids = current_ids
        else:
            print(f"[{fmt_time()}] {label} No new email ({len(current_ids)} unread)")


# ── entry point ───────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Monitor Gmail inboxes for new emails.")
    p.add_argument("--setup", action="store_true", help="Set up an account")
    p.add_argument("--account", default=None,
                   help="Account name/label (default: 'default'). Use different names for multiple accounts.")
    p.add_argument("--list", action="store_true", help="List configured accounts")
    p.add_argument("--interval", type=int, default=DEFAULT_INTERVAL,
                   help=f"Poll interval in seconds (default: {DEFAULT_INTERVAL})")
    p.add_argument("--quiet", action="store_true", help="No desktop notifications")
    return p.parse_args()


def main():
    args = parse_args()

    if args.list:
        accounts = list_accounts()
        if accounts:
            print("Configured accounts:", ", ".join(accounts))
        else:
            print("No accounts configured. Run:  gmail-watch --setup --account <name>")
        return

    if args.setup:
        account = args.account or "default"
        run_setup(account)
        return

    # determine which accounts to monitor
    if args.account:
        accounts = [args.account]
    else:
        accounts = list_accounts()
        if not accounts:
            print("No accounts configured. Run:  gmail-watch --setup --account <name>")
            sys.exit(1)

    print(f"[gmail-watch] Monitoring {len(accounts)} account(s): {', '.join(accounts)}")
    print(f"[gmail-watch] Polling every {args.interval}s — press Ctrl+C to stop\n")

    if len(accounts) == 1:
        email, password = load_account(accounts[0])
        monitor_account(accounts[0], email, password, args.interval, args.quiet)
    else:
        threads = []
        for account in accounts:
            email, password = load_account(account)
            t = threading.Thread(
                target=monitor_account,
                args=(account, email, password, args.interval, args.quiet),
                daemon=True,
            )
            t.start()
            threads.append(t)
        for t in threads:
            t.join()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[gmail-watch] Stopped.")
