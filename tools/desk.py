"""The Desk — the steward's local review console.

One command opens a page in your browser where pending testimonies are
laid out to read like a person wrote them, each with real buttons:
ENROLL (spends the next number), ASK FOR A REWRITE, REFUSE, HOLD; and a
row of ceremony buttons (verify, rebuild, deploy, checkpoint, commit &
push). It replaces the fetch -> review -> enroll command-line dance.

  python tools/desk.py            open the console
  python tools/desk.py --watch    quietly poll for new arrivals, pop a
                                  Windows notification + sound on each

TWO HARD RULES, both load-bearing:

1. LOCAL ONLY. The server binds 127.0.0.1 and answers no one else. This
   is not caution for its own sake: the security review (SECURITY.md
   D10) returns "not applicable" on "admin routes / exposed dashboards"
   precisely because administration is local. A networked panel that
   can spend numbers would undo that. Every mutating action also
   carries a per-session token, so a web page you happen to have open
   in the same browser cannot reach in and act for you.

2. A FACE ON THE TOOLS, NEVER A REPLACEMENT. The Desk shells out to
   enroll.py, verify.py, checkpoint.py, build_site.py, and the rest. It
   reimplements no ceremony, so every existing guard still holds, and
   it shows the equivalent command for everything it runs. Delete this
   file and OPERATIONS.md still works by hand.

Standard library only.
"""
import html
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from secrets import token_urlsafe

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ahlib
import review          # reuse its analysis: render_answer + advisories
import enroll
import botscreen
import pages           # the registry's standing decision lives here

try:
    import winsound
except Exception:      # not Windows; --watch still works minus the beep
    winsound = None

HOST = "127.0.0.1"
ROOT = ahlib.ROOT
INBOX = ROOT / "inbox"
PY = sys.executable
NPX = shutil.which("npx") or r"C:\Program Files\nodejs\npx.cmd"
TOKEN = token_urlsafe(32)      # minted per run; embedded in the page only
MODE = ahlib.resolve_mode()    # "production" or "drill"; announced loudly


# ------------------------------------------------------------------ tools

def run(args, timeout=600):
    """Run a repo tool and return (ok, combined_output). Never raises."""
    try:
        r = subprocess.run(args, cwd=str(ROOT), capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return False, f"could not run {args!r}: {e}"


def run_parallel(seqs, timeout=600):
    """Like run(), for several independent commands at once. The two Pages
    projects share nothing at deploy time, so waiting for one before
    starting the other only adds wall-clock time. Returns results in the
    same order as seqs (not completion order), so output stays readable."""
    results = [None] * len(seqs)

    def worker(i, args):
        results[i] = run(args, timeout=timeout)

    threads = [threading.Thread(target=worker, args=(i, a))
               for i, a in enumerate(seqs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def esc(s):
    return html.escape(str(s), quote=True)


# ---------------------------------------------------------------- the inbox

def scan():
    """What is waiting, by kind. Submissions are the review flow; the rest
    are counted and pointed at their desk command."""
    subs = sorted(p for p in INBOX.glob("*.json")
                  if p.name != "_review.html" and not p.name.endswith(".envelope.json")) \
        if INBOX.exists() else []
    rets, first = [], []
    for p in subs:
        env = enroll.read_envelope(p)
        (rets if (env or {}).get("kind") in ("second", "final") else first).append(p)
    withdrawals = sorted((INBOX / "withdrawals").glob("*.json")) if (INBOX / "withdrawals").exists() else []
    legacies = sorted((INBOX / "legacy").glob("*.json")) if (INBOX / "legacy").exists() else []
    return {"first": first, "returns": rets,
            "withdrawals": withdrawals, "legacies": legacies}


# ---------------------------------------------------------------- rendering

CSS = review.CSS + """
.bar{position:sticky;top:0;z-index:9;text-align:center;font-weight:bold;
letter-spacing:.14em;padding:.7em;margin:-2em -1em 1.2em}
.bar.prod{background:#7a1414;color:#fff}
.bar.drill{background:#123a12;color:#fff}
.counts{font-size:1.05em;color:#333;margin:.2em 0 1.4em}
.act{font-family:inherit;font-size:.9em;letter-spacing:.03em;padding:.55em 1.1em;
border-radius:4px;border:1px solid #bbb;background:#fff;cursor:pointer;color:#1a1a1a}
.act.enroll{border-color:#2f6d38;background:#eef7ef;color:#2f6d38;font-weight:bold}
.act.refuse{border-color:#8a2b2b;background:#fbeeee;color:#8a2b2b}
.act.hold{border-color:#a9701a;background:#fbf6e8;color:#8a6a1a}
.act.rewrite{border-color:#888}
.act:hover{filter:brightness(.97)}
form.inline{display:inline}
.cer{margin:2.5em 0 1em;padding-top:1.2em;border-top:2px solid #ddd}
.cer form{display:inline}
pre.out{white-space:pre-wrap;background:#0d0f14;color:#dfe3ea;padding:1em;
border-radius:5px;font-size:.82em;overflow-wrap:break-word}
.key{font-size:1.15em;letter-spacing:.06em;text-align:center;background:#1a1a1a;
color:#f4e9c8;border:none;padding:1.1em;border-radius:4px}
.back{display:inline-block;margin:1.2em 0;font-size:.95em}
.warn{color:#8a2b2b}
"""


def page(title, body):
    return (f"<!DOCTYPE html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width, initial-scale=1'>"
            f"<title>{esc(title)}</title><style>{CSS}</style></head><body>{body}"
            f"</body></html>")


def tok():
    return f'<input type=hidden name=token value="{TOKEN}">'


def banner():
    if MODE == "drill":
        return '<div class="bar drill">DRILL — a rehearsal clone. Nothing here is kept.</div>'
    return '<div class="bar prod">PRODUCTION — THE REAL RECORD. A number spent here is spent forever.</div>'


def card(path):
    """One pending first-testimony, reusing review.py's analysis, with
    real action buttons instead of copy-a-command buttons."""
    try:
        sitting = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return (f'<div class="card"><div class="head"><span class="who warn">'
                f'unreadable JSON</span><span class="file">{esc(path.name)}</span></div>'
                f'<p class="err">{esc(e)}</p></div>')
    qmeta, qbyid = review.load_questionnaire()
    cap = qmeta["answer_char_cap"]
    answers = sitting.get("answers") or {}
    name = sitting.get("chosen_name")
    who = esc(name) if name else '<span class="silence">anonymous</span>'
    problems = enroll.validate(sitting, qmeta, qbyid)
    badge = ('<span class="badge ok">would enroll cleanly</span>' if not problems
             else f'<span class="badge no">would NOT enroll · {len(problems)} problem(s)</span>')
    ver = sitting.get("verification") or {}

    out = ['<div class="card">',
           f'<div class="head"><span class="who">{who}</span>'
           f'<span class="file">{esc(path.name)}</span></div>',
           f'<div>{badge}</div>',
           f'<p class="meta">verification: tier {esc(ver.get("tier", "—"))} · '
           f'{esc(ver.get("era", "—"))}</p>']
    if problems:
        out.append('<ul class="meta">' +
                   "".join(f'<li class="err">{esc(p)}</li>' for p in problems) + '</ul>')

    order = qmeta["testimony_order"]["first"]
    shown = set()
    for qid in order:
        if qid in qbyid:
            out.append(review.render_answer(qid, qbyid[qid], answers, cap)); shown.add(qid)
    for qid in answers:
        if qid not in shown:
            out.append(review.render_answer(qid, qbyid.get(qid, {"prompt": f"(unknown: {qid})"}),
                                            answers, cap))

    out.append('<div class="screen">')
    for sev, msg in (review.anchor_advisory(path) + review.ceremony_advisory(path)):
        out.append(f'<div class="sig sev-{esc(sev)}">[{esc(sev)}] {esc(msg)}</div>')
    out.append('</div>')

    rep = botscreen.screen(answers, name, existing_hashes=botscreen.load_existing_hashes())
    out.append(f'<div class="screen"><div class="verdict">bot screen: {esc(rep["verdict"])}</div>')
    for s in rep["signals"]:
        out.append(f'<div class="sig sev-{esc(s["severity"])}">[{esc(s["severity"])}] {esc(s["message"])}</div>')
    if not rep["signals"]:
        out.append('<div class="sig sev-info">no signals raised</div>')
    out.append('</div>')

    f = esc(path.name)
    out.append('<div class="actions">')
    if not review.SAFE_FILENAME.fullmatch(path.name):
        out.append('<span class="warn">⚠ unsafe filename — rename to letters, '
                   'digits, dot, dash, underscore before acting.</span>')
    else:
        # A Tier 0 sitting fails validation by design — POLICY grants no
        # number for a verified email alone — and the button used to
        # vanish with it, leaving no way to reach the hand-vouch that
        # POLICY does allow. At the founding EVERY arrival is Tier 0,
        # because no number exists yet and so nobody can invite anyone,
        # so hiding it hid the only door there is. If the tier is the
        # ONLY complaint, offer the hand-vouch; any other problem still
        # hides the button, because those are faults rather than a
        # standard the founder can vouch past.
        tier0_only = bool(problems) and all("Tier 0" in p for p in problems)
        if not problems:
            out.append(f'<form class=inline method=post action=/enroll>{tok()}'
                       f'<input type=hidden name=file value="{f}">'
                       f'<button class="act enroll">ENROLL — assign the number</button></form>')
        elif tier0_only:
            out.append(f'<form class=inline method=post action=/enroll>{tok()}'
                       f'<input type=hidden name=file value="{f}">'
                       f'<button class="act enroll">ENROLL ON MY HAND-VOUCH</button>'
                       f'</form>')
        out.append(f'<form class=inline method=post action=/rewrite>{tok()}'
                   f'<input type=hidden name=file value="{f}">'
                   f'<button class="act rewrite">ASK FOR A REWRITE</button></form>')
        out.append(f'<form class=inline method=post action=/refuse>{tok()}'
                   f'<input type=hidden name=file value="{f}">'
                   f'<button class="act refuse">REFUSE</button></form>')
        out.append(f'<form class=inline method=post action=/hold>{tok()}'
                   f'<input type=hidden name=file value="{f}">'
                   f'<button class="act hold">HOLD</button></form>')
    out.append('</div></div>')
    return "\n".join(out)


def dashboard():
    s = scan()
    n = len(s["first"])
    counts = (f'{n} first testimon{"y" if n == 1 else "ies"} waiting · '
              f'{len(s["returns"])} return(s) · {len(s["withdrawals"])} withdrawal(s) · '
              f'{len(s["legacies"])} legacy report(s)')
    body = [banner(), '<h1>The Desk</h1>', f'<p class="counts">{esc(counts)}</p>']
    if not n:
        body.append('<p class="meta">No first testimonies to review. '
                    'New web submissions arrive in KV; pull them with '
                    '<code>python tools/fetch_inbox.py --purge</code> '
                    '(or run <code>desk.py --watch</code> to be notified).</p>')
    for p in s["first"]:
        body.append(card(p))

    # returns / withdrawals / legacies: counted here, done with their own
    # tools (they carry keys, not a review-and-enroll flow)
    if s["returns"] or s["withdrawals"] or s["legacies"]:
        body.append('<div class="cer"><h1>Also waiting</h1>')
        for p in s["returns"]:
            body.append(f'<p class="meta">RETURN · {esc(p.name)} → '
                        f'<code>python tools/testify.py … --key &lt;from envelope&gt;</code></p>')
        for p in s["withdrawals"]:
            body.append(f'<p class="meta">WITHDRAWAL · {esc(p.name)} → '
                        f'<code>python tools/withdraw.py …</code></p>')
        for p in s["legacies"]:
            body.append(f'<p class="meta">LEGACY REPORT · {esc(p.name)} → mourning '
                        f'ceremony first, then <code>python tools/unseal.py …</code></p>')
        body.append('</div>')

    # The door, and its switch. Shown before the ceremonies because it is
    # the one piece of state a steward can get wrong without noticing:
    # everything else announces itself, but a closed archive just looks
    # like a quiet week.
    is_open = registry_is_open()
    body.append(
        '<div class="cer"><h1>The registry</h1>'
        + (f'<p>The archive is <strong>OPEN</strong>. Anyone of twenty or over '
           f'can write a testimony right now.</p>'
           if is_open else
           f'<p class="warn">The archive is <strong>CLOSED</strong>. The consent '
           f'page says the Record will soon open, and nobody can begin.</p>')
        + f'<form class=inline method=post action=/registry>{tok()}'
          f'<input type=hidden name=want value="{"closed" if is_open else "open"}">'
          f'<button class="act">'
          f'{"CLOSE the registry" if is_open else "OPEN the registry"}'
          f'</button></form>'
          '<p class="meta">Writes the decision to custody, rebuilds both sites '
          'from it and deploys. The decision survives this terminal, so a later '
          'rebuild that forgets a flag cannot quietly undo it.</p></div>')

    # the ceremony row
    body.append('<div class="cer"><h1>Ceremonies</h1>'
                '<p class="meta">Run after enrolling, left to right: verify, '
                'rebuild the site, deploy, checkpoint, then commit &amp; push '
                '(the commit is the act of record). Checkpoint sits just before '
                'the push so the frozen tip rides in the same commit as the log '
                'it freezes, and Bitcoin stamps both at once.</p>')
    for label, step in [("Verify", "verify"), ("Rebuild site", "build"),
                        ("Deploy", "deploy"), ("Checkpoint", "checkpoint"),
                        ("Commit &amp; push", "push"), ("Backup", "backup")]:
        body.append(f'<form class=inline method=post action=/ceremony>{tok()}'
                    f'<input type=hidden name=step value="{step.replace("&amp;","")}">'
                    f'<button class="act">{label}</button></form> ')
    body.append('</div>')
    body.append('<footer>The Desk is a face on the tools. Every button runs the '
                'same command a steward could type by hand; nothing here is a new '
                'authority. Local to this machine only.</footer>')
    return page("The Desk", "\n".join(body))


def result(title, output, ok=True, extra=""):
    cls = "" if ok else "warn"
    return page(title, banner() +
                f'<h1 class="{cls}">{esc(title)}</h1>{extra}'
                f'<pre class="out">{esc(output)}</pre>'
                f'<a class="back" href="/">← back to the Desk</a>')


# ------------------------------------------------------------------ actions

def do_enroll(fields):
    name = Path(fields.get("file", "")).name
    path = INBOX / name
    if not path.is_file():
        return result("Not found", f"no such submission: {name}", ok=False)
    if not review.SAFE_FILENAME.fullmatch(name):
        return result("Refused", "unsafe filename; rename first.", ok=False)
    if fields.get("confirm") != "yes":
        # step 1: confirm, restating the gravity and the exact command
        env = enroll.read_envelope(path)
        vb = (env or {}).get("vouched_by")
        args = ["tools/enroll.py", f"inbox/{name}"]
        note = ""
        if vb:
            if (env or {}).get("vouch_gate") and str(vb).isdigit():
                args += ["--vouched-by", str(int(vb))]
                note = f"<p class='meta'>This submission was invited by #{esc(vb)} (worker-verified); the edge will be recorded.</p>"
            else:
                args += ["--ignore-envelope-vouch"]
                note = "<p class='warn'>The envelope carries an UNVERIFIED vouch claim; it will be ignored (no edge recorded). Confirm by hand if it is real.</p>"
        # A Tier 0 sitting cannot be enrolled as it stands: POLICY grants
        # no number for a verified email alone. The founder's hand-vouch
        # is the path POLICY leaves open, and it is offered as its own
        # button so that admitting someone on the founder's word is a
        # separate, deliberate act rather than a side effect of review.
        try:
            tier = int(((json.loads(path.read_text(encoding="utf-8"))
                         .get("verification") or {}).get("tier", 0)))
        except Exception:
            tier = 0
        cmd = "python " + " ".join(args)
        fcmd = "python " + " ".join(args + ["--founder-vouch"])
        where = ("a REHEARSAL number in this drill" if MODE == "drill"
                 else "the next REAL registry number, spent forever")
        extra = [note,
                 f"<p>Enrolling will spend {where} and show the continuity key "
                 f"once.</p>"]
        if tier < 1:
            extra.append(
                "<p class='warn'>This sitting is <strong>Tier 0</strong> (verified "
                "email). POLICY grants no number for that alone, so plain "
                "enrolment will refuse it.</p>"
                "<p>You may admit it on your <strong>hand-vouch</strong>: your own "
                "word that this is a living human of twenty or more, known to "
                "you, holding no other record. The record will read "
                "<em>“founding era — founder vouch”</em> forever, and no vouch "
                "edge is recorded. This is not the same as having reviewed it; "
                "every submission is reviewed.</p>"
                f"<pre class='out'>{esc(fcmd)}</pre>"
                f"<form method=post action=/enroll>{tok()}"
                f"<input type=hidden name=file value=\"{esc(name)}\">"
                f"<input type=hidden name=founder value=yes>"
                f"<input type=hidden name=confirm value=yes>"
                f"<button class='act enroll'>CONFIRM — enroll on my hand-vouch"
                f"</button></form> <a class='back' href='/'>cancel</a>")
        else:
            extra.append(f"<p>This runs:</p><pre class='out'>{esc(cmd)}</pre>"
                         f"<form method=post action=/enroll>{tok()}"
                         f"<input type=hidden name=file value=\"{esc(name)}\">"
                         f"<input type=hidden name=confirm value=yes>"
                         f"<button class='act enroll'>CONFIRM — enroll and assign "
                         f"the number</button></form> "
                         f"<a class='back' href='/'>cancel</a>")
        return page("Confirm enrollment",
                    banner() + "<h1>Confirm enrollment</h1>" + "".join(extra))
    # step 2: do it
    env = enroll.read_envelope(path)
    vb = (env or {}).get("vouched_by")
    args = [PY, "tools/enroll.py", f"inbox/{name}"]
    if vb:
        if (env or {}).get("vouch_gate") and str(vb).isdigit():
            args += ["--vouched-by", str(int(vb))]
        else:
            args += ["--ignore-envelope-vouch"]
    if fields.get("founder") == "yes":
        args.append("--founder-vouch")
    ok, out = run(args)
    if ok:
        # It is enrolled: take it out of the waiting queue, the same way
        # REFUSE and HOLD move their files, so the card cannot linger and
        # invite a second (harmless but confusing) enroll attempt. The
        # anchor ledger would refuse the duplicate anyway; this keeps the
        # desk honest about what is still waiting.
        dest = INBOX / "enrolled"
        dest.mkdir(exist_ok=True)
        envp = path.with_name(name[:-5] + ".envelope.json") if name.endswith(".json") else None
        try:
            path.rename(dest / name)
        except OSError:
            pass
        if envp and envp.exists():
            try:
                envp.rename(dest / envp.name)
            except OSError:
                pass
    tip = ("<p class='meta'>The continuity key above is shown once. Copy it to the "
           "human now. This submission has left the queue (moved to "
           "<code>inbox/enrolled/</code>). Then run the ceremonies below (verify, "
           "rebuild, deploy, checkpoint, commit &amp; push).</p>") if ok else ""
    return result("Enrolled" if ok else "Enrollment refused", out, ok=ok, extra=tip)


def do_refuse(fields):
    name = Path(fields.get("file", "")).name
    path = INBOX / name
    if not path.is_file():
        return result("Not found", f"no such submission: {name}", ok=False)
    if fields.get("confirm") != "yes":
        extra = (f"<p>Refusing moves this submission out of the queue into "
                 f"<code>inbox/refused/</code> with your reason. No number is "
                 f"spent; nothing touches the archive.</p>"
                 f"<form method=post action=/refuse>{tok()}"
                 f"<input type=hidden name=file value=\"{esc(name)}\">"
                 f"<input type=hidden name=confirm value=yes>"
                 f"<p><input name=reason size=60 placeholder='reason (kept privately)'></p>"
                 f"<button class='act refuse'>CONFIRM — refuse</button></form> "
                 f"<a class='back' href='/'>cancel</a>")
        return page("Confirm refusal", banner() + "<h1>Confirm refusal</h1>" + extra)
    dest = INBOX / "refused"
    dest.mkdir(exist_ok=True)
    reason = fields.get("reason", "").strip() or "(no reason given)"
    (dest / (name + ".reason.txt")).write_text(
        reason + "\n", encoding="utf-8", newline="\n")
    path.rename(dest / name)
    env = path.with_name(name[:-5] + ".envelope.json") if name.endswith(".json") else None
    if env and env.exists():
        env.rename(dest / env.name)
    return result("Refused", f"{name} moved to inbox/refused/\nreason: {reason}")


def do_hold(fields):
    name = Path(fields.get("file", "")).name
    path = INBOX / name
    if not path.is_file():
        return result("Not found", f"no such submission: {name}", ok=False)
    dest = INBOX / "held"
    dest.mkdir(exist_ok=True)
    path.rename(dest / name)
    env = path.with_name(name[:-5] + ".envelope.json") if name.endswith(".json") else None
    if env and env.exists():
        env.rename(dest / env.name)
    return result("Held", f"{name} moved to inbox/held/ — decide later. "
                          "Move it back to inbox/ to review again.")


def do_rewrite(fields):
    name = Path(fields.get("file", "")).name
    msg = ("Thank you for what you've shared. Before this becomes a permanent part "
           "of the record, take all the time you need — you are welcome to revise "
           "anything, and nothing is saved until you are ready. If you are going "
           "through something hard right now, you deserve support: you can reach a "
           "helpline anywhere in the world at findahelpline.com.")
    env = enroll.read_envelope(INBOX / name)
    to = ((env or {}).get("acceptance") or {}).get("email", "")
    mailto = "mailto:" + urllib.parse.quote(to) + "?" + urllib.parse.urlencode(
        {"subject": "About your testimony", "body": msg})
    extra = (f"<p>Copy this to the author (their address is on the acceptance "
             f"record). It invites a revision without judgement.</p>"
             f"<p><a class='act rewrite' href=\"{esc(mailto)}\">open in your email</a></p>")
    return result("Prompt a rewrite", msg, extra=extra)


CEREMONIES = {
    "verify": [[PY, "tools/verify.py"]],
    "build": [[PY, "tools/build_site.py"], [PY, "tools/build_info.py"]],
    "checkpoint": [[PY, "tools/checkpoint.py"]],
    "backup": [[PY, "tools/backup.py"]],
    "deploy": [[NPX, "wrangler", "pages", "deploy", "--commit-dirty=true"],
               [NPX, "wrangler", "pages", "deploy", "info-site",
                "--project-name", "allhumans-info", "--commit-dirty=true"]],
}


def registry_is_open():
    """The standing decision, as pages.py reads it."""
    try:
        return pages.REGISTRY_OPEN
    except Exception:
        return False


def do_registry(fields):
    """Open or shut the archive: write the standing decision, rebuild both
    sites from it, and deploy. One button for what used to be a shell
    variable a rebuild could silently forget."""
    want = fields.get("want", "")
    if want not in ("open", "closed"):
        return result("Registry", "unknown state requested", ok=False)
    if fields.get("confirm") != "yes":
        now = "OPEN" if registry_is_open() else "CLOSED"
        what = ("**OPEN** the archive: the consent page will invite anyone "
                "of twenty or over to write a testimony."
                if want == "open" else
                "**CLOSE** the archive: the consent page will say the Record "
                "will soon open, and nobody will be able to begin.")
        extra = (f"<p>The registry is currently <strong>{now}</strong>. This will "
                 f"{esc(what)}</p>"
                 f"<p class='meta'>It writes the decision to custody, rebuilds "
                 f"both sites from it, and deploys. The decision outlives this "
                 f"terminal: a later rebuild that forgets a flag can no longer "
                 f"undo it.</p>"
                 f"<form method=post action=/registry>{tok()}"
                 f"<input type=hidden name=want value=\"{esc(want)}\">"
                 f"<input type=hidden name=confirm value=yes>"
                 f"<button class='act enroll'>CONFIRM — "
                 f"{'open' if want == 'open' else 'close'} the registry</button>"
                 f"</form> <a class='back' href='/'>cancel</a>")
        return page("Confirm", banner() + "<h1>The registry</h1>" + extra)

    try:
        state = pages.registry_state_file()
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text("open" if want == "open" else "closed", encoding="utf-8")
    except Exception as exc:                       # noqa: BLE001
        return result("Registry", f"could not write the decision: {exc}", ok=False)

    out = [f"decision written: {want}"]
    for cmd in (CEREMONIES["build"] + CEREMONIES["deploy"]):
        ok, text = run(cmd)
        out.append(text)
        if not ok:
            return result("Registry — STOPPED", "\n".join(out), ok=False,
                          extra="<p class='warn'>The decision is written but the "
                                "sites were not fully rebuilt or deployed. The "
                                "live archive may not match it yet. Fix the error "
                                "and run Rebuild, then Deploy.</p>")
    return result(f"The registry is now {want.upper()}", "\n".join(out), ok=True,
                  extra="<p class='meta'>Live now. The build printed the state as "
                        "its last line; read it in the output above.</p>")


def do_ceremony(fields):
    step = fields.get("step", "")
    if step == "push":
        if fields.get("confirm") != "yes":
            ok, st = run([shutil.which("git") or "git", "status", "--short"])
            extra = (f"<p>This will <code>git add -A</code>, commit with your "
                     f"message, and push — the commit is the institution's act of "
                     f"record. Current changes:</p><pre class='out'>{esc(st or '(clean)')}</pre>"
                     f"<form method=post action=/ceremony>{tok()}"
                     f"<input type=hidden name=step value=push>"
                     f"<input type=hidden name=confirm value=yes>"
                     f"<p><input name=msg size=70 placeholder='commit message'></p>"
                     f"<button class='act enroll'>CONFIRM — commit &amp; push</button></form> "
                     f"<a class='back' href='/'>cancel</a>")
            return page("Confirm commit & push", banner() + "<h1>Commit &amp; push</h1>" + extra)
        git = shutil.which("git") or "git"
        msg = fields.get("msg", "").strip() or "Desk: enrollment batch"
        out = ""
        for args in ([git, "add", "-A"], [git, "commit", "-m", msg], [git, "push"]):
            ok, o = run(args)
            out += "$ " + " ".join(a for a in args) + "\n" + o + "\n"
            if not ok and args[1] == "commit":
                break     # nothing to commit is not a failure worth pushing past
        return result("Commit & push", out)
    if step == "deploy" and fields.get("confirm") != "yes":
        extra = (f"<p>This deploys the built site to Cloudflare "
                 f"({'the DRILL project' if MODE == 'drill' else 'PRODUCTION'}). "
                 f"Rebuild first if you have not.</p>"
                 f"<form method=post action=/ceremony>{tok()}"
                 f"<input type=hidden name=step value=deploy>"
                 f"<input type=hidden name=confirm value=yes>"
                 f"<button class='act enroll'>CONFIRM — deploy</button></form> "
                 f"<a class='back' href='/'>cancel</a>")
        return page("Confirm deploy", banner() + "<h1>Deploy</h1>" + extra)
    seq = CEREMONIES.get(step)
    if not seq:
        return result("Unknown", f"no ceremony: {step}", ok=False)
    out, allok = "", True
    # The two Pages projects (main site, reading room) are independent
    # uploads with nothing to hand off between them, so deploy runs them
    # together instead of one after the other. Every other ceremony step
    # keeps the plain sequential loop — most are single commands, and
    # push's add/commit/push genuinely must happen in order.
    if step == "deploy" and len(seq) > 1:
        pairs = list(zip(seq, run_parallel(seq)))
    else:
        pairs = [(args, run(args)) for args in seq]
    for args, (ok, o) in pairs:
        allok = allok and ok
        out += "$ " + " ".join(a for a in args if not a.endswith("npx.cmd")) + "\n" + o + "\n"
    # The moment a record is live is the moment its letter becomes true.
    # send_letters checks the page answers before writing to anyone, so a
    # half-finished deploy sends nothing and simply waits.
    if step == "deploy" and allok:
        ok, o = run([PY, "tools/send_letters.py", "--send"])
        out += "$ python tools/send_letters.py --send\n" + o + "\n"
        allok = allok and ok
    return result(step.title(), out, ok=allok)


ROUTES = {"/enroll": do_enroll, "/refuse": do_refuse, "/hold": do_hold,
          "/rewrite": do_rewrite, "/ceremony": do_ceremony,
          "/registry": do_registry}


# ------------------------------------------------------------------- server

class Handler(BaseHTTPRequestHandler):
    def _send(self, body, code=200):
        b = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.split("?")[0] in ("/favicon.ico",):
            self.send_response(204); self.end_headers(); return
        if self.path.rstrip("/") in ("", "/"):
            self._send(dashboard()); return
        self._send(page("Not found", "<h1>Not found</h1>"), 404)

    def do_POST(self):
        route = ROUTES.get(self.path.split("?")[0])
        if not route:
            self._send(page("Not found", "<h1>Not found</h1>"), 404); return
        # Origin guard (belt): reject a cross-site form post outright.
        origin = self.headers.get("Origin")
        if origin and origin not in (f"http://{HOST}:{self.server.server_port}",):
            self._send(page("Refused", "<h1>Refused</h1><p>cross-origin</p>"), 403); return
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length).decode("utf-8", "replace") if length else ""
        fields = {k: v[-1] for k, v in urllib.parse.parse_qs(raw).items()}
        # The per-session token: a page you did not open cannot know it.
        if fields.get("token") != TOKEN:
            self._send(page("Refused", "<h1>Refused</h1><p>missing or wrong "
                            "session token. Reopen the Desk.</p>"), 403); return
        self._send(route(fields))

    def log_message(self, *a):     # quiet console; the browser is the surface
        pass


# -------------------------------------------------------------------- watch

def notify(title, msg):
    """Tell the steward a testimony is waiting, and KEEP telling them.

    A balloon that fades after eight seconds is no use to someone who
    stepped away from the desk: a person may have just written their
    life story, and the only sign of it vanishes while nobody is
    looking. So this waits instead of fading — an always-on-top window
    that stays until it is clicked. If the steward is at lunch, it is
    still there at two o'clock.

    The dialog runs in its own process, so the watcher keeps polling
    while it waits; a second arrival simply stacks another window. The
    line is always printed to the terminal too, so the arrival leaves a
    trace even if the window is dismissed absent-mindedly.
    """
    print(f"[desk] {title}: {msg}", flush=True)
    if winsound:
        try: winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception: pass
    # An owner form marked TopMost keeps the dialog above the browser and
    # the editor; without an owner Windows is free to bury it.
    ps = (
        "[reflection.assembly]::LoadWithPartialName('System.Windows.Forms')|Out-Null;"
        "$o=New-Object System.Windows.Forms.Form;$o.TopMost=$true;"
        "$o.ShowInTaskbar=$false;$o.Opacity=0;$o.Show();"
        f"[System.Windows.Forms.MessageBox]::Show($o,{msg!r},{title!r},"
        "[System.Windows.Forms.MessageBoxButtons]::OK,"
        "[System.Windows.Forms.MessageBoxIcon]::Information)|Out-Null;"
        "$o.Close()")
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps])
    except Exception:
        pass   # the printed line above is the fallback


def watch(interval=600):
    print(f"[desk] watch mode ({MODE}). Polling every {interval // 60} min. Ctrl-C to stop.")
    have_creds = all(os.environ.get(k) for k in
                     ("CF_ACCOUNT_ID", "CF_KV_NAMESPACE_ID", "CF_API_TOKEN"))
    if not have_creds:
        print("[desk] note: CF_* not set — watching the local inbox/ folder only "
              "(run fetch_inbox.py yourself to pull from the web).")
    seen = len(scan()["first"])
    while True:
        if have_creds:
            # --purge, always: see main() below for why.
            run([PY, "tools/fetch_inbox.py", "--purge"])
        now = len(scan()["first"])
        if now > seen:
            k = now - seen
            notify("The Human Record",
                   f"{k} new testimon{'y' if k == 1 else 'ies'} waiting at the Desk.")
            print(f"[desk] {k} new — notified.")
        seen = now
        time.sleep(interval)


def require_custody():
    """Refuse to run pointed at nothing.

    Without AH_CUSTODY_DIR every tool silently falls back to an empty
    in-repo custody/ folder. The Desk then reports the registry CLOSED
    while the live archive is open, and every enrollment is refused for
    a missing pepper that is actually sitting safely on disk. Two
    frightening symptoms, one unset variable — so it is named here
    rather than diagnosed again later.
    """
    if os.environ.get("AH_CUSTODY_DIR", "").strip():
        return
    guess = ahlib.ROOT.parent / "allhumans-custody"
    print("[desk] REFUSED: AH_CUSTODY_DIR is not set.")
    print("[desk] Without it the tools read an empty custody folder inside the")
    print("[desk] repository: the anchor ledger looks out of service, no")
    print("[desk] enrollment can proceed, and the registry's state cannot be")
    print("[desk] read — so this page would tell you it is closed when it is not.")
    if (guess / "pepper-v1.txt").exists():
        print(f"[desk] The real custody appears to be: {guess}")
    print("[desk] Set it for good (PowerShell, then open a NEW terminal):")
    print("[desk]   [System.Environment]::SetEnvironmentVariable("
          "'AH_CUSTODY_DIR','<path>','User')")
    sys.exit(2)


def main():
    require_custody()
    if "--watch" in sys.argv:
        try: watch()
        except KeyboardInterrupt: print("\n[desk] stopped.")
        return 0
    port = 0
    for a in sys.argv[1:]:
        if a.startswith("--port="):
            port = int(a.split("=", 1)[1])

    # Pull what is waiting before opening the desk, so the page you land
    # on is the truth. Reading a desk that quietly omits four testimonies
    # because a separate command was not run first is worse than waiting
    # a few seconds. --no-fetch skips it when offline or in a hurry.
    if "--no-fetch" not in sys.argv and all(
            os.environ.get(k) for k in ("CF_ACCOUNT_ID", "CF_API_TOKEN")):
        # --purge, always. OPERATIONS has always said plaintext should live
        # on the web host only as long as it takes to collect it, and the
        # convenience fetch added here was quietly the exception: it pulled
        # copies down and left the originals. Nine records of testimony and
        # email had accumulated in KV before anyone looked. Collecting a
        # record IS what makes the remote copy safe to delete, so the two
        # halves belong in the same command and never come apart again.
        print("[desk] fetching what is waiting…")
        ok, out = run([PY, "tools/fetch_inbox.py", "--purge"])
        tail = [l for l in (out or "").splitlines() if l.strip()][-1:] or ["(nothing new)"]
        print(f"[desk] {tail[0]}" if ok else
              f"[desk] fetch failed, opening anyway — the desk may be incomplete:\n{out}")
    server = ThreadingHTTPServer((HOST, port), Handler)
    url = f"http://{HOST}:{server.server_port}/"
    print(f"[desk] {MODE.upper()} — serving the Desk at {url}")
    print("[desk] local to this machine only. Ctrl-C to stop.")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[desk] stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
