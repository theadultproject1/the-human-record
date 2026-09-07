"""Check for arrivals once, tell the steward, and exit.

Usage:
    python tools/watchdesk.py            # fetch, notify if anything new
    python tools/watchdesk.py --email    # also send an email
    python tools/watchdesk.py --install  # print the scheduled-task command

WHY THIS EXISTS, AND WHY IT IS NOT `desk.py --watch`
`desk.py --watch` polls forever in a terminal, which means it stops
watching the moment that terminal closes, the machine reboots, or nobody
remembers to start it. On 2026-08-01 four testimonies arrived and nothing
told anyone, because no terminal was open. A person who has just written
their life story is waiting for a number; "the steward happened to have a
window open" is not a system.

So this runs ONCE and exits, and Windows is asked to run it on a
schedule. No process to leave running, nothing to remember, and it
survives a reboot.

It is deliberately not clever. It fetches, counts what is waiting, and if
that count has grown since the last run it says so. The count is kept in
the custody directory, so it survives reboots too.

Standard library only.
"""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ahlib
import anchors
import desk

PY = sys.executable or "python"
ROOT = ahlib.ROOT


def waiting_now():
    """How many first testimonies are sitting at the desk."""
    return len(desk.scan()["first"])


def seen_file():
    return anchors.custody_dir(create=True) / "desk-last-seen"


def read_seen():
    try:
        return int(seen_file().read_text(encoding="utf-8").strip())
    except Exception:
        return 0


def write_seen(n):
    try:
        seen_file().write_text(str(n), encoding="utf-8")
    except Exception:
        pass


def email_steward(subject, body):
    """Reuse the letter machinery's SMTP settings; a steward who has
    configured outbound mail for authors has already configured it for
    themselves."""
    to = os.environ.get("AH_STEWARD_EMAIL", "").strip()
    if not to:
        return False, "AH_STEWARD_EMAIL is not set"
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import notify_author
    try:
        ok = notify_author.send(to, subject, body)
        return ok, "sent" if ok else "not sent"
    except Exception as exc:                       # noqa: BLE001
        return False, f"{exc.__class__.__name__}: {exc}"


def install_hint():
    task = "TheHumanRecord-Desk"
    cmd = f'"{PY}" "{ROOT / "tools" / "watchdesk.py"}" --email'
    print("Run this once, in PowerShell, to check every hour:")
    print()
    print(f'  schtasks /Create /TN "{task}" /SC HOURLY /F \\')
    print(f'    /TR \'{cmd}\'')
    print()
    print("Then FIX THE LAPTOP DEFAULTS, or it will not run unplugged:")
    print()
    print(f'  $s = New-ScheduledTaskSettingsSet -StartWhenAvailable '
          f'-AllowStartIfOnBatteries \\')
    print(f'         -DontStopIfGoingOnBatteries '
          f'-ExecutionTimeLimit (New-TimeSpan -Minutes 10)')
    print(f'  Set-ScheduledTask -TaskName "{task}" -Settings $s')
    print()
    print("Task Scheduler creates tasks with DisallowStartIfOnBatteries=True,")
    print("so on a laptop the watcher is silently deaf whenever it is")
    print("unplugged, and skipped runs are never made up. Those two lines are")
    print("not optional on a portable machine.")
    print()
    print("It runs whether or not a terminal is open, and survives a reboot.")
    print(f'To stop it later:  schtasks /Delete /TN "{task}" /F')
    print(f'To run it now:     schtasks /Run /TN "{task}"')
    print()
    print("The task inherits your USER environment variables, so")
    print("AH_CUSTODY_DIR, the CF_* credentials and the AH_SMTP_* settings")
    print("must be set at User scope (not just in one terminal) or it will")
    print("wake up unable to see anything.")


def main():
    if "--install" in sys.argv:
        install_hint()
        return 0
    if not os.environ.get("AH_CUSTODY_DIR", "").strip():
        print("watchdesk: AH_CUSTODY_DIR is not set; nothing can be read.")
        return 2

    if all(os.environ.get(k) for k in ("CF_ACCOUNT_ID", "CF_API_TOKEN")):
        # --purge, always: this runs unattended every hour, so it is
        # the single biggest reason plaintext would pile up on the web host.
        # Having the local copy is what makes deleting the remote one safe.
        subprocess.run([PY, str(ROOT / "tools" / "fetch_inbox.py"), "--purge"],
                       capture_output=True, text=True)

    now, before = waiting_now(), read_seen()
    write_seen(now)
    if now <= before:
        print(f"watchdesk: {now} waiting, nothing new.")
        return 0

    k = now - before
    what = "testimony" if k == 1 else "testimonies"
    line = f"{k} new {what} waiting at the Desk ({now} in total)."
    print("watchdesk: " + line)
    desk.notify("The Human Record", line)

    if "--email" in sys.argv:
        ok, how = email_steward(
            f"{k} new {what} at The Human Record",
            line + "\n\nOpen the Desk to read them:\n"
                   "    python tools/desk.py\n\n"
                   "It will fetch anything else waiting as it opens.\n")
        print(f"watchdesk: email {how}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
