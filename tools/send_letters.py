"""Tell the humans, once their record is actually live.

The letter that says "you are Human #N" was a command the steward had to
remember to type, and the first one was forgotten. This sends it by
itself, but never before the page it points at exists.

The order matters and is the whole reason this is a separate tool.
enroll.py spends the number; the deploy publishes the page; only then is
the letter true. Sent at enrollment it would link a stranger to a 404
minutes after the most personal thing they have ever written.

So enrollment QUEUES a letter into custody and this sends it, checking
first that https://<domain>/<number> really answers. A queue that cannot
be flushed yet simply waits for the next run; nothing is lost, nothing
is sent twice.

    python tools/send_letters.py            # show what is waiting
    python tools/send_letters.py --send     # send what is due

Addresses live in the custody directory, never in the repository:
    <custody>/letters/pending/<number>.json
    <custody>/letters/sent/<number>.json

A drill can never send, exactly as notify_author.py refuses.
"""
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ahlib
import anchors
import brand
import notify_author


def letters_dir(which, create=False) -> Path:
    d = anchors.custody_dir(create=create) / "letters" / which
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def queue(number, email):
    """Called by enroll.py. Records who to write to, and never overwrites:
    a number is spent once, so a second queue for the same number means
    something is wrong and the first record of it is the one to trust."""
    d = letters_dir("pending", create=True)
    p = d / f"{int(number)}.json"
    if p.exists() or (letters_dir("sent") / p.name).exists():
        return False
    p.write_text(json.dumps({
        "registry_id": f"{int(number):09d}",
        "number": int(number),
        "email": email,
        "queued_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return True


def page_is_live(number, timeout=15):
    """Is the record actually published? The letter promises a permanent
    address; do not send it until that address answers."""
    url = f"https://{brand.DOMAIN}/{int(number)}"
    req = urllib.request.Request(url, method="GET",
                                 headers={"User-Agent": "the-human-record-upkeep"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return False


def main():
    args = sys.argv[1:]
    do_send = "--send" in args
    mode = ahlib.resolve_mode()

    try:
        pending = sorted(letters_dir("pending").glob("*.json"),
                         key=lambda p: int(p.stem))
    except FileNotFoundError:
        pending = []
    if not pending:
        print("no letters waiting.")
        return 0

    if mode == "drill":
        print(f"{len(pending)} letter(s) queued. A DRILL NEVER SENDS.")
        for p in pending:
            print("  would write to", json.loads(p.read_text(encoding="utf-8"))["email"])
        return 0

    sent_dir = letters_dir("sent", create=True)
    sent = held = 0
    for p in pending:
        rec = json.loads(p.read_text(encoding="utf-8"))
        n, to = rec["number"], rec["email"]
        if not page_is_live(n):
            print(f"#{n}: holding — https://{brand.DOMAIN}/{n} does not answer yet. "
                  f"Deploy, then run this again.")
            held += 1
            continue
        subject, body = notify_author.letter(n)
        if not do_send:
            print(f"#{n}: ready to write to {to} (run with --send)")
            continue
        if notify_author.send(to, subject, body):
            rec["sent_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            (sent_dir / p.name).write_text(
                json.dumps(rec, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8", newline="\n")
            p.unlink()
            sent += 1
            print(f"#{n}: sent to {to}")
        else:
            print(f"#{n}: NOT sent (mail is not configured); still queued")
            held += 1

    if do_send:
        print(f"{sent} sent, {held} still waiting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
