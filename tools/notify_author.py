"""Tell a human their testimony is in, and where it will live.

Usage:
    python tools/notify_author.py 2 --email someone@example.org
        show exactly what would be sent, and to whom. Sends nothing.

    python tools/notify_author.py 2 --email someone@example.org --send
        actually send it.

Run this AFTER the record is deployed, so the address in the letter
already answers. `enroll.py` prints the exact command; the Desk offers
it as a button.

The Record is one-way (POLICY, and the founder's ruling of 2026-07-23):
it writes to a human, and no one can write back. So this letter says
plainly that the address is unmonitored, and it never invites a reply.

WHAT THIS DELIBERATELY DOES NOT CONTAIN
  * the continuity key — it was born in the author's browser and the
    institution has never held it. We can remind them to keep it; we
    can never resend it.
  * anything they did not already tell us.

Sending is off unless --send is given, and a drill can never send at
all: a rehearsal must not email a living person. Enrollment never
depends on this — a number is spent at the desk, and a letter that
fails to send is a letter you send again, not a number half spent.

Configuration (any send-only SMTP provider; nothing here is
provider-specific):

    AH_SMTP_HOST    e.g. smtp.resend.com
    AH_SMTP_PORT    default 587 (STARTTLS)
    AH_SMTP_USER    the username the provider gives you
    AH_SMTP_PASS    the password/API key. NEVER commit this
    AH_MAIL_FROM    the visible sender, e.g.
                    The Human Record <noreply@thehumanrecord.earth>

Until a provider is chosen, run without --send and send the printed
text by hand from the steward's own address. The letter is the same
either way.

Standard library only.
"""
import os
import smtplib
import ssl
import sys
import textwrap
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ahlib
import brand

# "Human #2", not "#000000002": NAMING.md is explicit that a human holds
# a *number* — Human #2 — and that the padded nine-digit form is wire
# format no human ever reads.
SUBJECT = "You are Human #{number} in {brand}"

BODY = """Your testimony has been entered into {brand}.

You are Human #{number}.

Your words are kept exactly as you wrote them. They will not be
edited, and they will not be rewritten. From today they live at:

    {url}

Don't forget, your continuity key is what grants you the possibility
to one day write your second and final testimony. {brand} has never
held a copy of it and cannot recover it for you.

Thank you for being part of the record of what it was like to be
human.

—

This address is not monitored, and {brand} receives no email. There is
nothing to reply to; nothing you send here will reach a person.
"""


def _wrap(text, width=72):
    """Re-wrap after substitution, so a longer brand name can never leave
    a ragged line in a letter a person keeps."""
    out = []
    for para in text.split("\n\n"):
        if para.startswith("    ") or para.strip() == "—":
            out.append(para)              # the address block, and the rule
            continue
        out.append(textwrap.fill(" ".join(para.split()), width=width))
    return "\n\n".join(out)


def letter(number):
    n = int(number)
    url = f"https://{brand.DOMAIN}/{n}"
    return (SUBJECT.format(number=n, brand=brand.BRAND),
            _wrap(BODY.format(number=n, brand=brand.BRAND, url=url)))


def send(to_addr, subject, body):
    host = os.environ.get("AH_SMTP_HOST", "").strip()
    user = os.environ.get("AH_SMTP_USER", "").strip()
    password = os.environ.get("AH_SMTP_PASS", "")
    sender = os.environ.get("AH_MAIL_FROM", "").strip()
    port = int(os.environ.get("AH_SMTP_PORT", "587") or 587)
    missing = [n for n, v in (("AH_SMTP_HOST", host), ("AH_SMTP_USER", user),
                              ("AH_SMTP_PASS", password), ("AH_MAIL_FROM", sender))
               if not v]
    if missing:
        print("cannot send: missing " + ", ".join(missing))
        print("(see this file's docstring; the letter above can be sent by hand)")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_addr
    # The Record cannot receive mail; say so in the headers too, so a
    # mail client does not offer a reply that would vanish.
    msg["Reply-To"] = sender
    msg["Auto-Submitted"] = "auto-generated"
    msg.set_content(body)

    with smtplib.SMTP(host, port, timeout=30) as s:
        s.starttls(context=ssl.create_default_context())
        s.login(user, password)
        s.send_message(msg)
    return True


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    number = args[0]
    if not number.lstrip("0").isdigit():
        print(f"not a registry number: {number!r}")
        return 2
    to_addr = None
    for i, a in enumerate(args):
        if a == "--email" and i + 1 < len(args):
            to_addr = args[i + 1].strip()
    if not to_addr or "@" not in to_addr:
        print("give the author's address: --email someone@example.org")
        return 2
    really = "--send" in args

    mode = ahlib.resolve_mode()
    subject, body = letter(number)

    print("=" * 68)
    print(f"To:      {to_addr}")
    print(f"Subject: {subject}")
    print("-" * 68)
    print(body)
    print("=" * 68)

    if mode == "drill":
        print("DRILL: nothing sent, and nothing can be. A rehearsal must never")
        print("write to a living person. Read the letter above and move on.")
        return 0
    if not really:
        print("Dry run. Nothing was sent. Add --send when this reads true.")
        return 0
    try:
        ok = send(to_addr, subject, body)
    except Exception as exc:                      # noqa: BLE001 - report, never raise
        print(f"send FAILED: {exc.__class__.__name__}: {exc}")
        print("The number is spent and the record is live regardless. Send the")
        print("letter above by hand, or fix the setting and run this again.")
        return 1
    print("sent." if ok else "not sent.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
