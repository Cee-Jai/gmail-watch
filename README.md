# gmail-watch

A command-line tool that monitors your Gmail inbox for new emails and sends a persistent desktop notification for each one — showing the sender and subject — that stays on screen until you dismiss it.

## Features

- Detects new unread emails in your inbox
- Shows sender and subject in the notification
- Sends a **persistent desktop notification** that won't auto-dismiss
- Credentials stored locally with `chmod 600` — never leaves your machine
- Reconnects automatically if the connection drops

## Requirements

- Python 3 (standard library only — no extra packages needed)
- `notify-send` (standard on most Linux desktops)
- A Gmail account with **2-Step Verification** enabled

## Installation

```bash
cp gmail-watch.py ~/.local/bin/gmail-watch
chmod +x ~/.local/bin/gmail-watch
```

## Getting your App Password

Gmail requires an App Password instead of your regular password for IMAP access.

1. Go to **myaccount.google.com**
2. Click **Security** in the left sidebar
3. Under *"How you sign in to Google"*, click **2-Step Verification** (enable it if not already on)
4. Scroll to the bottom → click **App passwords**
5. Enter a name (e.g. `gmail-watch`) → click **Create**
6. Copy the 16-character code Google shows you

## Setup

Run this once to save your credentials securely:

```bash
gmail-watch --setup
```

You'll be prompted for your Gmail address and App Password. The credentials are verified immediately and stored in `~/.config/gmail-watch/config` with `600` permissions (only readable by you).

## Usage

```bash
# Monitor inbox, polling every 60 seconds (default)
gmail-watch

# Poll every 30 seconds
gmail-watch --interval 30

# Terminal output only — no desktop notifications
gmail-watch --quiet
```

## Options

| Flag | Default | Description |
|---|---|---|
| `--setup` | — | First-time credential setup |
| `--interval` | `60` | Seconds between each poll |
| `--quiet` | off | Disable desktop notifications, print to terminal only |

## Example output

```
[gmail-watch] Connecting as you@gmail.com...
[gmail-watch] Connected — 3 unread email(s) at start
[gmail-watch] Polling every 60s — press Ctrl+C to stop

[09:14:01] No new email (3 unread)
[09:15:01] New email — John Doe: Meeting rescheduled to Friday
[09:16:01] New email — GitHub: [Cee-Jai/reddit-watch] New star
```

## Security

- Your App Password is stored only in `~/.config/gmail-watch/config` on your local machine
- The file is created with `600` permissions — no other user can read it
- Nothing is sent to any third-party service
