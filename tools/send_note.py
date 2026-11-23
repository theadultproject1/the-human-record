"""Send one letter that is not the enrolment letter.

The archive writes to people exactly once, when they are given their
number, and notify_author.py owns that letter. Sometimes a person needs
to be told something else: a testimony is held and why, a submission is
refused and why, a withdrawal is complete.

There was no way to do that. The Desk's ASK FOR A REWRITE opens the
steward's own mail client, which sends from the steward's personal
address — it exposes a private address to a stranger and arrives from a
domain with no SPF or DKIM for this institution, so it reads as spam.
This sends from the Record's own authenticated address instead, the same
one the enrolment letter uses.

    python tools/send_note.py letter.txt --email them@example.org
    python tools/send_note.py letter.txt --email them@example.org --send

The body is a plain text FILE, never typed on the command line: a letter
to someone who has just written down their life deserves to be read
twice before it is sent, and a shell is a bad place to compose. The
subject comes from the file's first line; everything after the first
blank line is the letter.

The no-reply footer is appended here, always, and cannot be forgotten:
the domain publishes a null MX and physically cannot receive mail, so
any letter that invites a reply tells a lie the DNS will enforce.

Sending is off unless --send is given, and a drill can never send.
Environment is the same as notify_author.py (AH_SMTP_*, AH_MAIL_FROM).

Standard library only.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ahlib
import brand
import notify_author

FOOTER = ("This address is not monitored, and {brand} receives no email. "
          "There is nothing to reply to; nothing you send here will reach "
          "a person.")


def main():
    args = sys.argv[1:]
    really = "--send" in args
    if really:
        args.remove("--send")
    to = None
    if "--email" in args:
        i = args.index("--email")
        if i + 1 >= len(args):
            print("--email needs an address")
            return 2
        to = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1 or not to:
        print(__doc__)
        return 2

    src = Path(args[0])
    if not src.is_file():
        print(f"no such letter file: {src}")
        return 2
    raw = src.read_text(encoding="utf-8").strip()
    if "\n" not in raw:
        print("the file needs a subject line, a blank line, then the letter.")
        return 2
    subject, _, body = raw.partition("\n")
    subject, body = subject.strip(), body.strip()
    if not subject or not body:
        print("the file needs a subject line, a blank line, then the letter.")
        return 2
    # Editing the letter and deleting the subject line is the easy mistake:
    # the first sentence then silently becomes the subject, and a person
    # receives a letter headed with half a paragraph. A subject is short.
    if len(subject) > 78 or subject.endswith("."):
        print("REFUSED: the first line does not look like a subject —")
        print(f"  {subject[:72]}…" if len(subject) > 72 else f"  {subject}")
        print("The file is: a SHORT subject line, a blank line, then the")
        print("letter. It looks like the subject line was deleted while")
        print("editing, which would send this sentence as the subject.")
        return 2

    body = notify_author._wrap(body) + "\n\n—\n\n" + \
        notify_author._wrap(FOOTER.format(brand=brand.BRAND))

    mode = ahlib.resolve_mode()
    print("=" * 68)
    print(f"To:      {to}")
    print(f"Subject: {subject}")
    print("=" * 68)
    print(body)
    print("=" * 68)

    if mode == "drill":
        print("DRILL: nothing sent, and nothing can be. A rehearsal must never")
        print("write to a living person. Read the letter above and move on.")
        return 0
    if not really:
        print("Dry run. Nothing was sent. Add --send when this reads true.")
        return 0
    ok = notify_author.send(to, subject, body)
    print("sent." if ok else "NOT sent.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
