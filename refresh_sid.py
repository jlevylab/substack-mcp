#!/usr/bin/env python3
"""
refresh_sid.py - Update the Substack MCP session cookie (SUBSTACK_SID) in
~/.claude.json with one command, instead of hand-editing JSON.

Why this exists: Substack has no API tokens; the MCP server authenticates by
replaying your browser's `substack.sid` session cookie. That cookie is httpOnly
and Chrome now app-bound-encrypts its cookie store, so it can't be pulled
automatically. But refreshing it can still be one step:

    1. Chrome DevTools -> Application -> Cookies -> https://substack.com
       -> click `substack.sid` -> copy the Value.
    2. Run:  python refresh_sid.py         (reads the value from your clipboard)
       or:   python refresh_sid.py "<value>"

Then reload MCP servers in Claude Code (or restart the session) so the
substack server picks up the new cookie.

The script rewrites ONLY the SUBSTACK_SID value via a targeted regex, so the
rest of your (large) .claude.json is left byte-for-byte unchanged, and it makes
a timestamped backup first.
"""
import os
import re
import sys
import shutil
import subprocess
from datetime import datetime

CONFIG = os.path.join(os.path.expanduser("~"), ".claude.json")


def get_clipboard() -> str:
    """Return clipboard text on Windows via PowerShell Get-Clipboard."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            capture_output=True, text=True, timeout=10,
        )
        return (out.stdout or "").strip()
    except Exception:
        return ""


def normalize(sid: str) -> str:
    """Accept either the raw (url-encoded 's%3A...') or decoded ('s:...') form
    and return the url-encoded form the server stores."""
    sid = sid.strip().strip('"').strip("'")
    if sid.startswith("s%3A"):
        return sid  # already url-encoded
    if sid.startswith("s:"):
        # url-encode the reserved chars Substack uses in the sid
        return sid.replace("%", "%25").replace(":", "%3A").replace("+", "%2B").replace("/", "%2F")
    return sid


def looks_like_sid(sid: str) -> bool:
    return (sid.startswith("s%3A") or sid.startswith("s:")) and len(sid) > 40


def main() -> int:
    sid = sys.argv[1] if len(sys.argv) > 1 else get_clipboard()
    if not sid:
        print("No SID provided and clipboard was empty.")
        print("Copy the substack.sid cookie value, then run this again.")
        return 1

    sid = normalize(sid)
    if not looks_like_sid(sid):
        print(f"That doesn't look like a substack.sid value:\n  {sid[:60]}...")
        print("Expected it to start with 's%3A' (or 's:') and be long.")
        return 1

    if not os.path.isfile(CONFIG):
        print(f"Config not found: {CONFIG}")
        return 1

    with open(CONFIG, "r", encoding="utf-8") as f:
        text = f.read()

    pattern = r'("SUBSTACK_SID":\s*")([^"]*)(")'
    m = re.search(pattern, text)
    if not m:
        print("Could not find a SUBSTACK_SID entry in .claude.json.")
        print("Is the substack MCP server configured? Aborting without changes.")
        return 1

    if m.group(2) == sid:
        print("The stored SID already matches the new value. Nothing to do.")
        return 0

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"{CONFIG}.bak-{stamp}"
    shutil.copy2(CONFIG, backup)

    new_text = text[:m.start()] + m.group(1) + sid + m.group(3) + text[m.end():]
    tmp = CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(new_text)
    os.replace(tmp, CONFIG)

    print("Updated SUBSTACK_SID in .claude.json")
    print(f"  old: {m.group(2)[:24]}...")
    print(f"  new: {sid[:24]}...")
    print(f"  backup: {backup}")
    print()
    print("Now reload MCP servers in Claude Code (or restart the session)")
    print("so the substack server picks up the refreshed cookie.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
