"""The entry flow pages: consent (enter.html), the First Testimony
writing page (begin.html), and the site's single serverless function
(_worker.js). Standard library only on this side.

Founding-era pipeline:
  consent page — the author gives their email (Tier-0 verification)
  and makes the five affirmations (age 20+, one-record-only, the
  principles); the acceptance record (email, affirmations, timestamp)
  is stored the moment they proceed.
  writing page — ten questions; on completion, one confirmation
  ("sealed in history"), then the sitting + acceptance POST to
  /api/submit, which the worker stores in Cloudflare KV.
  review desk — tools/fetch_inbox.py pulls submissions into inbox/,
  tools/review.py renders them, the founder enrolls or replies with
  a rewrite prompt. Numbers are spent only at enrollment.

Front-of-funnel gate (bot/flood protection for the review desk; it
never assigns a number and never touches the archive): the writing
page fetches an HMAC-signed, server-timed ceremony token on load and
solves a small proof-of-work in the background; on submission the
worker verifies the token, refuses submissions faster than a human
could write, checks the proof-of-work, a hidden honeypot, per-IP and
global rate limits, a substance floor (name + two answers), and the
oath. The secret lives only in the worker env, never in the repo.
Defenses target automation and volume only — never the author's
words, feelings, or language (that stays advisory, in botscreen.py).

If the API is unreachable (local preview, outage), the writing page
falls back to download-and-email so no testimony is ever lost.
"""
import html
import json
import os
import sys
from pathlib import Path

import brand  # public display name + domain (the one place they live)

ENROLL_EMAIL = brand.CONTACT_EMAIL
NAME_CAP = 30
ANSWER_MIN = 10   # a given answer must be at least this many characters (POLICY.md)

# The Legacy Key wordlist (frozen forever — see the file's header). A
# Legacy Key is six of these words: deliberately UNLIKE the hex
# continuity key, so the two can never be confused, and shaped to be
# spoken aloud, written on paper, and handed to a person.
LEGACY_WORDS = [w for w in
                (Path(__file__).resolve().parent / "wordlists" /
                 "legacy_words.txt").read_text(encoding="utf-8").splitlines()
                if w and not w.startswith("#")]
LEGACY_WORD_COUNT = 6
LEGACY_PBKDF2_ITERS = 600000   # key-stretching: each guess costs 600k hashes

# Founding pause: while False, the consent page's BEGIN button is greyed
# and inert ("the registry opens soon") so no one fills out a First
# Testimony before enrollment is ready. Driven by the environment so a
# rehearsal never edits a file: unset means CLOSED (production default);
# opening the real registry is the deliberate act of exporting
# AH_REGISTRY_OPEN=true for the production build. Anything except
# 'true'/'false' stops the build.
def registry_state_file():
    """Where the operator's standing decision is kept: in custody, never
    in the repository, because it is this machine's operating stance and
    not part of the record. A clone that has no custody has no stance and
    therefore stays shut."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import anchors
    return anchors.custody_dir(create=False) / "registry-open"


def _registry_open() -> bool:
    # The environment still wins, because a drill must be able to force
    # its own answer without touching anything the operator relies on.
    raw = os.environ.get("AH_REGISTRY_OPEN")
    if raw is not None:
        v = raw.strip().lower()
        if v == "true":
            return True
        if v == "false":
            return False
        raise SystemExit(
            f"AH_REGISTRY_OPEN={raw!r} is neither 'true' nor 'false'. "
            "A misspelled value stops the build; it never guesses.")
    # Otherwise the standing decision, written by the Desk. Before this
    # existed the state lived only in a shell variable, so any rebuild
    # that forgot it closed the archive silently — which is exactly what
    # happened on 2026-08-01, from running the test suites in the correct
    # order. A decision this large should survive a forgotten flag.
    try:
        state = registry_state_file()
        if state.exists():
            return state.read_text(encoding="utf-8").strip().lower() == "open"
    except Exception:
        pass
    return False        # no environment, no custody, no stance: shut


REGISTRY_OPEN = _registry_open()


def json_for_script(value) -> str:
    """JSON destined for an inline <script> block. Beyond json.dumps,
    escape <, > and & (valid JSON string escapes), so no value can ever
    smuggle '</script>' or a comment-opener into the document — the
    parser closes a script block on those bytes no matter what the
    surrounding JavaScript is doing."""
    return (json.dumps(value, separators=(",", ":"))
            .replace("&", "\\u0026")
            .replace("<", "\\u003c")
            .replace(">", "\\u003e"))

DARK_CSS = """
html,body{margin:0;padding:0;background:#06070a;color:#c9c4b8;font-family:Georgia,'Times New Roman',serif;line-height:1.65}
.page{max-width:38em;margin:0 auto;padding:3em 1.2em 4em}
h1{font-weight:normal;letter-spacing:.18em;font-size:1.15em;color:#e8e3d6;text-align:center;margin:0 0 2.2em}
h2{font-weight:normal;letter-spacing:.12em;font-size:.95em;color:#e8e3d6;margin:2.4em 0 .8em;text-transform:uppercase}
p,li{font-size:.97em}
ul{padding-left:1.2em}
li{margin:.45em 0}
a{color:#c9c4b8}
.rule{border:none;border-top:1px solid #2a2c33;margin:2em 0}
.aura{display:inline-block;background:none;border:1px solid #8a8264;color:#e8e3d6;font-family:inherit;font-size:1em;letter-spacing:.15em;padding:.85em 2em;border-radius:2px;text-decoration:none;box-shadow:0 0 14px 2px rgba(244,233,200,.35);cursor:pointer}
.aura:hover{border-color:#e8e3d6;box-shadow:0 0 20px 4px rgba(244,233,200,.55)}
.aura[aria-disabled="true"]{opacity:.35;box-shadow:none;cursor:not-allowed}
details.sect{border-top:1px solid #2a2c33}
details.sect summary{cursor:pointer;font-weight:normal;letter-spacing:.12em;font-size:.95em;color:#e8e3d6;text-transform:uppercase;padding:1.05em 0;outline:none}
details.sect summary::marker{color:#8a8264}
details.sect summary:hover{color:#fff}
details.sect[open]{padding-bottom:.9em}
.checks label{display:block;margin:.9em 0;cursor:pointer}
.checks input{margin-right:.7em}
.center{text-align:center;margin-top:2.5em}
.gohome{margin-top:3.2em}
.needed{background:#151313;border:1px solid #5a5240;color:#e0d9c6;padding:.65em .95em;border-radius:2px;margin:1.3em 0}
.needed .plainnote{color:#b6ae9b}
.agree{margin-top:.5em;font-size:.8em}
.quiet{color:#8a8578;font-size:.85em}
input[type=email]{width:100%;box-sizing:border-box;background:#0d0f14;border:1px solid #8a8264;color:#e8e3d6;font-family:inherit;font-size:1em;padding:.7em;border-radius:2px;box-shadow:0 0 14px 2px rgba(244,233,200,.28)}
input[type=email]:focus{outline:none;border-color:#e8e3d6;box-shadow:0 0 20px 4px rgba(244,233,200,.5)}
"""

WRITE_CSS = """
body{max-width:42em;margin:2em auto;padding:0 1em 4em;font-family:Georgia,'Times New Roman',serif;line-height:1.6;color:#1a1a1a;background:#fdfcf9}
h1{font-weight:normal;letter-spacing:.06em}
h2{font-weight:normal}
a{color:#1a1a1a}
.q{margin:2em 0}
.q p.prompt{font-style:italic;color:#333;margin:0 0 .4em}
.q p.note{color:#777;font-size:.85em;margin:0 0 .4em}
textarea{width:100%;box-sizing:border-box;font-family:inherit;font-size:1em;line-height:1.5;padding:.6em;border:1px solid #bbb;background:#fff;min-height:5.5em;border-radius:2px}
textarea#q_name{min-height:2.4em}
input#vouch_code{width:100%;box-sizing:border-box;font-family:inherit;font-size:1em;line-height:1.5;padding:.6em;border:1px solid #bbb;background:#fff;border-radius:2px;letter-spacing:.04em}
.checks label{display:block;margin:.8em 0;cursor:pointer;padding-left:1.9em;text-indent:-1.9em}
.checks input{margin-right:.7em;vertical-align:middle}
.under{display:flex;justify-content:space-between;color:#777;font-size:.8em;margin-top:.25em}
.seal{cursor:pointer}
.help{color:#777;font-size:.82em;font-style:italic;margin:.35em 0 0}
.finish{display:inline-block;border:1px solid #444;background:none;font-family:inherit;font-size:1em;letter-spacing:.1em;padding:.8em 1.8em;cursor:pointer;border-radius:2px;text-decoration:none}
.finish:hover{background:#f0ede4}
button.finish:disabled{opacity:.4;cursor:not-allowed}
button.finish:disabled:hover{background:none}
#fallback,#received{display:none;margin-top:2.5em;border-top:1px solid #ccc;padding-top:1.5em}
.hidden{display:none}
.offscreen{position:absolute;left:-9999px;top:-9999px;width:1px;height:1px;overflow:hidden}
.plainnote{font-style:normal;color:#777;font-size:.85em}
.wv{display:block;margin:.6em 0;cursor:pointer}
pre{white-space:pre-wrap;background:#f4f2ea;border:1px solid #ddd;padding:1em;font-size:.8em;overflow-wrap:break-word}
pre.key{font-size:1.15em;letter-spacing:.06em;text-align:center;background:#1a1a1a;color:#f4e9c8;border:none;padding:1.2em}
.meta{color:#555;font-size:.9em}
.err{color:#8a2222}
.banner{background:#f4ecd8;border:1px solid #d8c89a;padding:.8em 1em;font-size:.9em}
.pagetimer{background:#f4ecd8;border:1px solid #d8c89a;color:#7a5c12;padding:.55em .9em;font-size:.9em;margin:0 0 1.4em;border-radius:2px}
/* The ceremony pop-up: The Record's own black/beige/gold, so the
   solemn moments never fall back to the browser's grey OS box. */
.ah-modal-ov{position:fixed;inset:0;background:rgba(6,7,10,.72);display:flex;align-items:center;justify-content:center;z-index:9999;padding:1.2em}
.ah-modal{max-width:30em;width:100%;background:#06070a;color:#c9c4b8;border:1px solid #8a8264;border-radius:4px;padding:1.6em 1.6em 1.4em;font-family:Georgia,'Times New Roman',serif;line-height:1.6;box-shadow:0 0 44px 8px rgba(0,0,0,.6)}
.ah-modal h2{color:#e8e3d6;font-weight:normal;letter-spacing:.08em;margin:0 0 .8em;font-size:1.12em}
.ah-modal p{margin:.6em 0;font-size:.95em;color:#c9c4b8}
.ah-modal-row{display:flex;gap:.8em;justify-content:flex-end;margin-top:1.5em;flex-wrap:wrap}
.ah-modal-btn{font-family:inherit;font-size:.9em;letter-spacing:.08em;padding:.7em 1.4em;border-radius:2px;cursor:pointer;background:none}
.ah-modal-no{border:1px solid #55503f;color:#c9c4b8}
.ah-modal-no:hover{border-color:#c9c4b8}
.ah-modal-yes{border:1px solid #8a8264;color:#e8e3d6;box-shadow:0 0 12px 1px rgba(244,233,200,.28)}
.ah-modal-yes:hover{border-color:#e8e3d6;box-shadow:0 0 18px 3px rgba(244,233,200,.45)}
"""

# A shared, accessible confirmation pop-up in The Record's own colours,
# replacing every native confirm() in the ceremony (begin / return /
# withdraw). Returns a Promise<bool>. Content is developer-controlled
# plain text (opts.lines), so no user input is ever interpolated.
MODAL_JS = """
<script>
window.ahConfirm = function(opts){
  return new Promise(function(resolve){
    var ov = document.createElement('div'); ov.className = 'ah-modal-ov';
    var box = document.createElement('div'); box.className = 'ah-modal';
    box.setAttribute('role','dialog'); box.setAttribute('aria-modal','true');
    var h = document.createElement('h2'); h.textContent = opts.title || 'Please confirm';
    box.appendChild(h); box.setAttribute('aria-label', opts.title || 'Please confirm');
    (opts.lines || []).forEach(function(t){
      var p = document.createElement('p'); p.textContent = t; box.appendChild(p);
    });
    var row = document.createElement('div'); row.className = 'ah-modal-row';
    var no = document.createElement('button'); no.type='button';
    no.className='ah-modal-btn ah-modal-no'; no.textContent = opts.cancel || 'Not yet';
    var yes = document.createElement('button'); yes.type='button';
    yes.className='ah-modal-btn ah-modal-yes'; yes.textContent = opts.ok || 'Continue';
    row.appendChild(no); row.appendChild(yes); box.appendChild(row);
    ov.appendChild(box); document.body.appendChild(ov);
    var prev = document.activeElement;
    function close(v){
      document.removeEventListener('keydown', onKey, true);
      if (ov.parentNode) ov.parentNode.removeChild(ov);
      if (prev && prev.focus) { try { prev.focus(); } catch(e){} }
      resolve(v);
    }
    function onKey(e){
      if (e.key === 'Escape'){ e.preventDefault(); close(false); }
      else if (e.key === 'Tab'){ e.preventDefault();
        (document.activeElement === yes ? no : yes).focus(); }
      else if (e.key === 'Enter'){ e.preventDefault(); close(true); }
    }
    no.addEventListener('click', function(){ close(false); });
    yes.addEventListener('click', function(){ close(true); });
    ov.addEventListener('click', function(e){ if (e.target === ov) close(false); });
    document.addEventListener('keydown', onKey, true);
    yes.focus();
  });
};
</script>
"""

CONSENT_BODY = """
<h1>BEFORE WRITING YOUR TESTIMONY</h1>

<p>Welcome to __BRAND__.</p>

<p>By entering The Record, you are choosing to leave a permanent
testimony about your life for future generations.</p>

<p>Write honestly. You are not writing to impress today's world.
You are writing to be understood by tomorrow's. Write so that
someone living 300 years from now could understand what it meant
to be you.</p>

<p>Please read the following carefully before continuing.</p>

<details class="sect">
<summary>What you should know</summary>
<ul>
<li>Participation is completely voluntary.</li>
<li>You own your words. Your testimony always belongs to you.
__BRAND__ is only the steward responsible for preserving it.</li>
<li>You may answer as many or as few questions as you wish. Every
question is optional.</li>
<li>We encourage you to use the name by which you are genuinely
known (your real name or at least your real first name).
Authenticity is more important than anonymity.</li>
<li>Any other person mentioned in your testimony should be
identified by <strong>first name only</strong>. Never include
another person's full name. Tell your story without exposing
someone else's identity.</li>
</ul>
</details>

<details class="sect">
<summary>Permanence</summary>
<ul>
<li>Once a testimony is published, it can never be edited.</li>
<li>Each person may publish a maximum of <strong>three</strong>
testimonies during their lifetime.</li>
<li>There must be a minimum of <strong>one year</strong> between
each testimony.</li>
<li>Every testimony is permanent once published.</li>
</ul>
</details>

<details class="sect">
<summary>Your number</summary>
<ul>
<li>Every human receives <strong>one</strong> permanent number.</li>
<li>Numbers are assigned sequentially by the system and can
never be chosen, changed, or reused.</li>
<li>Duplicate registrations are not permitted. To keep one light per
human, the contact points you enroll with are kept privately, only
as one-way keyed fingerprints, never published, never in the archive,
and checked before any number is ever assigned. If you already
have a record, your continuity key is the way back to it; a second
number will be refused.</li>
<li>Your number belongs to you for life, even if your
testimony is later withdrawn.</li>
</ul>
</details>

<details class="sect">
<summary>Withdrawal</summary>
<ul>
<li>You may request to withdraw any testimony.</li>
<li>If withdrawn: the testimony will no longer be publicly
displayed; your number will never be reused; a permanent
record will show that a testimony once existed and was
withdrawn.</li>
<li>Please understand that copies created before your withdrawal
may continue to exist outside The Record itself. __BRAND__ can
update the canonical archive and cooperating preservation partners,
but cannot erase privately held copies.</li>
</ul>
</details>

<details class="sect">
<summary>Privacy</summary>
<ul>
<li>You choose how much you reveal.</li>
<li>Your location may be as specific or as general as you wish.</li>
<li>Certain answers may be sealed according to __BRAND__ policy.</li>
<li>The Record does <strong>not</strong> include a public search
by name.</li>
<li>Your number is yours to keep private or share with anyone
you choose.</li>
<li>Another person can only find your testimony if you share your
number with them, or if their cursor lands on your light by
accident.</li>
</ul>

</details>

<details class="sect">
<summary>The Record</summary>
<p>The Record is <strong>not</strong> social media. There are:
no likes, no comments, no followers, no rankings, no
advertisements, no recommendation algorithm.</p>
<p>Every human is equal within The Record.</p>
</details>

<details class="sect">
<summary>Our promise</summary>
<p>__BRAND__ exists to preserve authentic human testimony for as
long as possible. We cannot honestly promise "forever." We can
promise that every reasonable technical, legal and institutional
effort will be made to preserve The Record for future
generations.</p>
<p>Trust is built through transparency, cryptographic verification,
independent preservation, and open governance, not through
promises alone.</p>
</details>

<hr class="rule">
<h2>Your email: where The Record answers you</h2>
<p>Your email is how The Record reaches you: it is where the
outcome of your submission's review and your number will
be sent. It never appears in the public record.
An email alone never grants a number. Before a number is assigned,
your submission is read by a person and verified to the standard of
this era.</p>
<p class="quiet">Already among the lights? Your record grows at the
<a href="return.html">return page</a>. It never needs a second
number.</p>
<p><input type="email" id="email" autocomplete="email"
placeholder="you@example.org" required></p>

<hr class="rule">
<h2>Before you continue</h2>
<p>By entering The Record, you confirm that:</p>
<div class="checks">
<label><input type="checkbox"> I have read and understood the principles listed above.</label>
<label><input type="checkbox"> I am 20 years of age or older.</label>
<label><input type="checkbox"> This is my only record. I have never enrolled before, and I understand that every human may hold exactly one, forever.</label>
<label><input type="checkbox"> I understand the withdrawal policy.</label>
<label><input type="checkbox"> I freely choose to participate.</label>
</div>
<p class="quiet">When you continue, your acceptance of these
principles (your email, your confirmations, and the time) is
recorded as the agreement between you and __BRAND__.</p>

__BEGIN_BLOCK__
<p class="center quiet"><a href="index.html">return to the lights</a></p>
"""

CONSENT_JS = """
<script>
(function(){
  var boxes = document.querySelectorAll('.checks input');
  var email = document.getElementById('email');
  var btn = document.getElementById('begin');
  var OPEN = __REGISTRY_OPEN__;
  function ready(){
    if (!OPEN) return false;
    if (!email.value || !email.checkValidity()) return false;
    for (var i = 0; i < boxes.length; i++) if (!boxes[i].checked) return false;
    return true;
  }
  function update(){ btn.setAttribute('aria-disabled', ready() ? 'false' : 'true'); }
  for (var i = 0; i < boxes.length; i++) boxes[i].addEventListener('change', update);
  email.addEventListener('input', update);
  // Returning to this page (Back from Privacy, from the return page, from
  // anywhere) can silently restore the checkboxes and the email field —
  // browsers do this without firing change/input, so everything LOOKS
  // filled in while the button's own computed state never got told to
  // look again. pageshow fires on every arrival, fresh or restored, and
  // is the one hook meant for exactly this: re-check, don't trust memory.
  window.addEventListener('pageshow', update);
  btn.addEventListener('click', function(e){
    if (btn.getAttribute('aria-disabled') === 'true') { e.preventDefault(); return; }
    var labels = document.querySelectorAll('.checks label');
    var affirmed = [];
    for (var i = 0; i < labels.length; i++) affirmed.push(labels[i].textContent.trim());
    var acceptance = {
      email: email.value.trim(),
      affirmed: affirmed,
      accepted_at: new Date().toISOString(),
      page: 'enter-v1'
    };
    try { sessionStorage.setItem('ah_acceptance', JSON.stringify(acceptance)); } catch(err) {}
    // A fresh acceptance means a fresh sitting, so the previous
    // ceremony's "finished" mark no longer applies. Without this the
    // writing page greets the next person with "This page has closed"
    // and offers them nothing: a family on one laptop, a library
    // machine, or a phone handed over with "your turn" all hit a wall.
    // The mark still does its real job, which is refusing to resurrect
    // a ceremony whose keys were already shown and wiped.
    try { sessionStorage.removeItem('ah_ceremony_done'); } catch(err) {}
    try {
      fetch('/api/accept', {method:'POST', keepalive:true,
        headers:{'content-type':'application/json'},
        body: JSON.stringify(acceptance)});
    } catch(err) {}
  });
  update();
})();
</script>
"""

HELP_LINE = ('If writing this stirs more than memories, help exists, '
             'worldwide: <a href="https://findahelpline.com" '
             'rel="noreferrer noopener">https://findahelpline.com</a>')

WRITE_JS_TEMPLATE = """
<script>
(function(){
  var CAP = __CAP__, NAME_CAP = __NAME_CAP__, MIN_ANSWER = __MIN_ANSWER__;
  var acceptance = null;
  try { acceptance = JSON.parse(sessionStorage.getItem('ah_acceptance') || 'null'); } catch(e) {}
  if (!acceptance || !acceptance.email) {
    document.getElementById('noaccept').style.display = 'block';
  }

  var finishBtn = document.getElementById('finish');
  var floorNote = document.getElementById('floor_note');

  // --- Ceremony token + proof of work (the anti-flood gate) ------------
  // On load, fetch a server-signed start token and quietly solve its
  // proof-of-work in the background while the author writes. Both are
  // handed back at submission. A human notices none of this.
  var ceremony = null, powNonce = null, tokenReady = false, powReady = false;

  function leadingZeroBits(bytes){
    var n = 0;
    for (var i = 0; i < bytes.length; i++){
      if (bytes[i] === 0){ n += 8; continue; }
      n += Math.clz32(bytes[i]) - 24; break;
    }
    return n;
  }
  function solvePow(seed, bits){
    return new Promise(function(resolve, reject){
      if (!(window.crypto && crypto.subtle && crypto.subtle.digest)) {
        return reject(new Error('no webcrypto'));
      }
      var nonce = 0;
      function step(){
        (function loop(){
          if (nonce % 256 === 0) {   // yield to the page every 256 tries
            return crypto.subtle.digest('SHA-256', new TextEncoder().encode(seed + '.' + nonce))
              .then(function(buf){
                if (leadingZeroBits(new Uint8Array(buf)) >= bits) return resolve('' + nonce);
                nonce++; setTimeout(step, 0);
              });
          }
          return crypto.subtle.digest('SHA-256', new TextEncoder().encode(seed + '.' + nonce))
            .then(function(buf){
              if (leadingZeroBits(new Uint8Array(buf)) >= bits) return resolve('' + nonce);
              nonce++; loop();
            });
        })();
      }
      step();
    });
  }
  // The gate is fetched with retries, because one bad moment on the
  // network used to cost the author their whole testimony: tokenReady
  // stayed false forever, the button stayed disabled forever, and the
  // email fallback that was supposed to catch exactly this sat behind
  // the button that could not be pressed.
  var gateFailed = false;
  function openGate(attempt){
    fetch('/api/ceremony', { cache: 'no-store' })
      .then(function(r){ return r.json(); })
      .then(function(t){
        if (!t || !t.ok) throw new Error('gate closed');
        ceremony = t; tokenReady = true;
        var bits = t.pow_bits || 0;
        if (bits > 0) {
          solvePow(t.seed, bits).then(function(n){
            powNonce = n; powReady = true; updateFinish();
          }).catch(function(){ gateFailed = true; updateFinish(); });
        } else { powReady = true; }
        updateFinish();
      })
      .catch(function(){
        if (attempt < 3) { setTimeout(function(){ openGate(attempt + 1); }, 1500 * attempt); }
        else { gateFailed = true; updateFinish(); }
      });
  }
  openGate(1);

  // Wait for the gate at the moment of submission rather than gating the
  // button on it. Resolves true when the ceremony is ready, false when it
  // is not coming, so the caller can take the email path instead of
  // leaving someone stranded with a button that never lights.
  function gateReady(waitMs){
    if (tokenReady && powReady) return Promise.resolve(true);
    if (gateFailed) return Promise.resolve(false);
    return new Promise(function(resolve){
      var waited = 0;
      (function poll(){
        if (tokenReady && powReady) return resolve(true);
        if (gateFailed || waited >= waitMs) return resolve(false);
        waited += 250; setTimeout(poll, 250);
      })();
    });
  }

  // Preselect the browser's language, as a courtesy and nothing more: the
  // author can change it, and the archive records what they chose, never
  // what the browser assumed.
  (function(){
    var sel = document.getElementById('lang_tag');
    if (!sel) return;
    var want = (navigator.language || '').toLowerCase().split('-')[0];
    for (var i = 0; i < sel.options.length; i++){
      if (sel.options[i].value === want){ sel.selectedIndex = i; break; }
    }
  })();

  var areas = document.querySelectorAll('textarea');
  for (var i = 0; i < areas.length; i++) (function(ta){
    var cap = ta.id === 'q_name' ? NAME_CAP : CAP;
    var counter = document.getElementById(ta.id + '_count');
    function tick(){ counter.textContent = ta.value.length + ' / ' + cap; }
    ta.addEventListener('input', tick);
    ta.addEventListener('input', updateFinish);
    tick();
  })(areas[i]);

  // The way out, guarded. Nothing on this page is saved anywhere until
  // the final confirmation, so a stray click on "return to the lights"
  // would silently destroy an hour of writing. Ask only if there is
  // something to lose; an untouched page just lets you go.
  var leave = document.getElementById('leave');
  if (leave) leave.addEventListener('click', function(ev){
    var written = false;
    for (var i = 0; i < areas.length; i++){
      if (areas[i].value.trim().length){ written = true; break; }
    }
    if (written && !window.confirm(
        'Nothing you have written has been sent yet, and leaving this page '
        + 'will lose it. Return to the lights?')) {
      ev.preventDefault();
    }
  });

  // Two questions are answered in a word and no more: a name, and where
  // you live. "Paris" is a complete and truthful answer, and the floor
  // used to reject it, which turned an honest reply into an error. They
  // are exempt from the minimum and do not count toward the two, because
  // the two are about testimony, not identity.
  var SHORT_OK = { q_name: 1, q_place: 1 };
  // Substance floor: name + at least two answers, each a real few words.
  function answeredCount(){
    var n = 0;
    for (var i = 0; i < areas.length; i++){
      if (SHORT_OK[areas[i].id]) continue;
      if (areas[i].value.trim().length >= MIN_ANSWER) n++;
    }
    return n;
  }
  function updateFinish(){
    var nameOK = document.getElementById('q_name').value.trim().length > 0;
    var enough = answeredCount() >= 2;
    // The button turns on what the AUTHOR controls and nothing else. It
    // used to also wait on the anti-flood gate, so a failed token fetch
    // or a browser without WebCrypto left a finished testimony behind a
    // button that would never light, with no way to reach the email
    // fallback built for exactly that. The gate is now waited for at the
    // moment of submission, where it can be explained or routed around.
    finishBtn.disabled = !(nameOK && enough);
    // Always say where they stand, and count out loud. "Two answers: 1 of
    // 2" tells someone what to do; a greyed button tells them nothing.
    var n = answeredCount();
    if (!nameOK) floorNote.textContent =
      'Still needed: your name, and any two answers (' + n + ' of 2 so far).';
    else if (!enough) floorNote.textContent =
      'Still needed: ' + (2 - n) + (n === 1 ? ' more answer' : ' answers')
      + ' of a few words (' + n + ' of 2 so far). Any questions you choose; '
      + 'the rest are kept as silence.';
    else if (gateFailed) floorNote.textContent =
      'Ready. The ceremony gate did not answer, so completing will offer you '
      + 'an email copy of your testimony; nothing you wrote is lost.';
    else if (!tokenReady || !powReady) floorNote.textContent =
      'Ready. Your testimony can be completed whenever you are (a moment of '
      + 'preparation is still finishing in the background).';
    else floorNote.textContent =
      'Ready. Your testimony can be completed whenever you are.';
  }

  function makeKey(){
    var b = new Uint8Array(16);
    crypto.getRandomValues(b);
    var hex = Array.prototype.map.call(b, function(x){
      return ('0' + x.toString(16)).slice(-2); }).join('');
    return 'ah1-' + hex.match(/.{4}/g).join('-');
  }
  function sha256hex(s){
    return crypto.subtle.digest('SHA-256', new TextEncoder().encode(s))
      .then(function(buf){
        return Array.prototype.map.call(new Uint8Array(buf), function(x){
          return ('0' + x.toString(16)).slice(-2); }).join('');
      });
  }

  // --- The Legacy Key: six plain words for the hands you trust ---------
  var LWORDS = __LEGACY_WORDS__, LN = LWORDS.length, LCOUNT = __LEGACY_COUNT__;
  var LITERS = __LEGACY_ITERS__;
  function makeLegacyKey(){
    // unbiased sampling: reject values past the largest multiple of LN
    var words = [], limit = 65536 - (65536 % LN), b = new Uint16Array(1);
    while (words.length < LCOUNT){
      crypto.getRandomValues(b);
      if (b[0] < limit) words.push(LWORDS[b[0] % LN]);
    }
    return words.join(' ');
  }
  function legacyFingerprint(words, saltHex){
    // PBKDF2 key-stretching: each guess at the six words costs 600,000
    // hashes — the gate against brute force, growing compute included.
    var enc = new TextEncoder();
    return crypto.subtle.importKey('raw', enc.encode(words),
        {name:'PBKDF2'}, false, ['deriveBits'])
      .then(function(k){ return crypto.subtle.deriveBits(
        {name:'PBKDF2', hash:'SHA-256', salt: enc.encode(saltHex), iterations: LITERS}, k, 256); })
      .then(function(buf){
        return Array.prototype.map.call(new Uint8Array(buf), function(x){
          return ('0' + x.toString(16)).slice(-2); }).join('');
      });
  }
  function sealedCount(){
    var boxes = document.querySelectorAll('.sealbox'), n = 0;
    for (var i = 0; i < boxes.length; i++)
      if (boxes[i].checked && document.getElementById(boxes[i].id.replace('_seal','')).value.trim()) n++;
    return n;
  }
  // the seal explainer appears the first time anyone seals anything
  (function(){
    var boxes = document.querySelectorAll('.sealbox');
    for (var i = 0; i < boxes.length; i++)
      boxes[i].addEventListener('change', function(){
        if (this.checked) document.getElementById('seal_explain').style.display = 'block';
      });
  })();
  function revealLegacy(words){
    document.getElementById('thelegacy').textContent = words;
    document.getElementById('copylegacy').addEventListener('click', function(){
      var self = this;
      navigator.clipboard.writeText(words).then(function(){
        self.textContent = 'COPIED';
        setTimeout(function(){ self.textContent = 'COPY MY KEY'; }, 2000);
      });
    });
    var f = 'Legacy Key: to be opened by someone I trust\\n'
      + '===========================================\\n\\n'
      + words + '\\n\\n'
      + 'These six words belong with a person, not a machine: the one\\n'
      + 'who should open my sealed words when I am gone. Bring them to\\n'
      + '__BRAND__ and report my death; my sealed answers will open and\\n'
      + 'my record will be marked a completed life. This key does\\n'
      + 'nothing while I live. If it is never used, my seals open on\\n'
      + 'their own one hundred years after my enrollment.\\n\\n'
      + 'Some are opened by those we trust.\\n'
      + 'The rest are opened by time itself.\\n';
    var blob = new Blob([f], {type: 'text/plain'});
    var dl = document.getElementById('savelegacy');
    dl.href = URL.createObjectURL(blob);
    dl.download = 'legacy-key-to-be-opened-by-someone-i-trust.txt';
  }

  function buildSitting(){
    var name = document.getElementById('q_name').value.trim();
    if (!name) return { error: 'Your name is the one required answer.' };
    if (name.length > NAME_CAP) return { error: 'Your name can hold at most ' + NAME_CAP + ' characters.' };
    var answers = {}, answered = 0;
    for (var i = 0; i < areas.length; i++) {
      var ta = areas[i];
      var text = ta.value.trim();
      if (!text) continue;
      if (!SHORT_OK[ta.id] && text.length < MIN_ANSWER) {
        // Name the question and hand back the field itself, so the page
        // can take the writer to it. Being told an answer is too short,
        // with nine boxes on screen and no clue which one, is how a
        // person gives up on a form.
        var lbl = ta.previousElementSibling;
        var which = (lbl && lbl.textContent ? '“' + lbl.textContent.trim() + '”' : 'One of your answers');
        return { error: which + ' needs at least ' + MIN_ANSWER
          + ' characters, a few words. You are always free to leave a question '
          + 'blank instead; it is kept as silence.', focus: ta };
      }
      var sealed = document.getElementById(ta.id + '_seal').checked;
      answers[ta.id] = { text: text, visibility: sealed ? 'sealed_until_death' : 'public' };
      if (!SHORT_OK[ta.id] && text.length >= MIN_ANSWER) answered++;
    }
    if (answered < 2) return { error:
      'Please answer at least two questions so there is a testimony to keep. Any two you choose.' };
    // chosen_name is the PUBLIC display name. If the author sealed their
    // name answer, they have asked for it not to be shown, so no public
    // name leaves the browser at all: the sealed answer still travels and
    // still opens one day, but nothing here can be printed on a heading
    // by mistake. The seal is honoured before the words are even sent.
    var nameSealed = document.getElementById('q_name_seal').checked;
    // "other" and "not saying" both travel as nothing: the record then
    // says the language is unknown, which is true, rather than naming one.
    var langSel = document.getElementById('lang_tag');
    var lang = langSel ? langSel.value : '';
    if (lang === 'other') lang = '';
    return { sitting: {
      chosen_name: nameSealed ? undefined : name,
      language: lang || undefined,
      verification: { tier: 0, era: 'founding era, verified email' },
      answers: answers
    }};
  }

  function revealKey(key){
    document.getElementById('thekey').textContent = key;
    document.getElementById('copykey').addEventListener('click', function(){
      var self = this;
      navigator.clipboard.writeText(key).then(function(){
        self.textContent = 'COPIED';
        setTimeout(function(){ self.textContent = 'COPY MY KEY'; }, 2000);
      });
    });
    var keyfile = '__BRAND__ continuity key\\n========================\\n\\n' +
      key + '\\n\\nThis key is the only proof that a testimony is yours.\\n' +
      'It is required to enter your Second and Final Testimonies\\n' +
      'and to withdraw. It was shown once and is stored nowhere,\\n' +
      'not by __BRAND__, not by anyone. Keep this file somewhere\\n' +
      'that will survive as long as you do.\\n';
    var blob = new Blob([keyfile], {type: 'text/plain'});
    var dl = document.getElementById('savekey');
    dl.href = URL.createObjectURL(blob);
    dl.download = '__BRANDSLUG__-continuity-key.txt';
  }

  function showFallback(sitting, key, legacyWords){
    if (legacyWords){
      document.getElementById('flegacywrap').style.display = 'block';
      document.getElementById('flegacy').textContent = legacyWords;
    }
    var jsonText = JSON.stringify(sitting, null, 2);
    var blob = new Blob([jsonText], {type: 'application/json'});
    var dl = document.getElementById('download');
    dl.href = URL.createObjectURL(blob);
    dl.download = 'my-first-testimony.json';
    document.getElementById('fjson').textContent = jsonText;
    document.getElementById('fkey').textContent = key;
    document.getElementById('fallback').style.display = 'block';
    document.getElementById('fallback').scrollIntoView({behavior: 'smooth'});
  }

  // --- The keys live on screen for ten minutes, then the page closes ---
  // Shown once means shown once: a visible countdown, a wipe the moment
  // the page is left (so the back button restores nothing), and a closed
  // state for any return. Ten minutes is deliberate: cutting someone off
  // mid-copy would destroy a key forever, so the window is generous.
  var CLOSE_SECONDS = 600;
  function wipeKeys(){
    ['thekey','thelegacy','fkey','flegacy'].forEach(function(id){
      var el = document.getElementById(id); if (el) el.textContent = '';
    });
    ['savekey','savelegacy','download'].forEach(function(id){
      var el = document.getElementById(id);
      if (el && el.href && el.href.indexOf('blob:') === 0){
        URL.revokeObjectURL(el.href); el.removeAttribute('href');
      }
    });
  }
  function showEnded(){
    ['writing','received','legacyscreen','closing','fallback'].forEach(function(id){
      var el = document.getElementById(id); if (el) el.style.display = 'none';
    });
    document.getElementById('ended').style.display = 'block';
    window.scrollTo(0,0);
  }
  function markDone(){ try { sessionStorage.setItem('ah_ceremony_done','1'); } catch(e){} }
  function isDone(){ try { return sessionStorage.getItem('ah_ceremony_done') === '1'; } catch(e){ return false; } }
  function startCloseTimer(){
    // Anchored to the CLOCK, not to ticks: browsers freeze timers on a
    // hidden page, so minutes away must still count. Remaining time is
    // recomputed from the real time on every update, and checked again
    // the instant the page becomes visible; past the deadline, it closes
    // at once.
    var deadline = Date.now() + CLOSE_SECONDS*1000;
    var els = document.querySelectorAll('.pagetimer');
    var closed = false;
    function tick(){
      if (closed) return;
      var left = Math.max(0, Math.ceil((deadline - Date.now())/1000));
      var m = Math.floor(left/60), s = left%60;
      for (var i=0;i<els.length;i++)
        els[i].textContent = 'For your safety, this page closes itself in '
          + m + ':' + (s<10?'0':'') + s + '.';
      if (left <= 0){
        closed = true; wipeKeys(); window.location.replace('index.html');
        return;
      }
      setTimeout(tick, 1000);
    }
    document.addEventListener('visibilitychange', function(){
      if (document.visibilityState === 'visible') tick();
    });
    tick();
  }
  // leaving the page, any way at all, wipes the keys (the testimony text
  // on the outage screen is spared: losing words is worse than any leak);
  // returning shows the closed page instead of the ceremony
  window.addEventListener('pagehide', function(){ wipeKeys(); });
  window.addEventListener('pageshow', function(e){ if (e.persisted && isDone()) { wipeKeys(); showEnded(); } });
  if (isDone()) { showEnded(); return; }

  function received(key, legacyWords){
    var to = acceptance && acceptance.email ? acceptance.email : 'your email';
    document.getElementById('rec_email').textContent = to;
    revealKey(key);
    document.getElementById('received').style.display = 'block';
    document.getElementById('writing').style.display = 'none';
    markDone();
    startCloseTimer();
    if (legacyWords){
      // the Legacy Key gets its own quiet screen, after this one
      document.getElementById('contwrap').style.display = 'block';
      document.getElementById('contbtn').addEventListener('click', function(){
        document.getElementById('received').style.display = 'none';
        revealLegacy(legacyWords);
        document.getElementById('legacyscreen').style.display = 'block';
        document.getElementById('closing').style.display = 'block';
        window.scrollTo(0,0);
      });
    } else {
      document.getElementById('closing').style.display = 'block';
    }
    window.scrollTo(0,0);
  }

  finishBtn.addEventListener('click', function(){
    var errbox = document.getElementById('errors');
    errbox.textContent = '';
    var built = buildSitting();
    if (built.error) {
      errbox.textContent = built.error;
      // Go to the problem, not to the top of the page. Scrolling away
      // from the field that needs fixing is the opposite of help.
      if (built.focus) {
        try {
          built.focus.scrollIntoView({ behavior: 'smooth', block: 'center' });
          built.focus.focus({ preventScroll: true });
        } catch (e) { built.focus.focus(); }
      } else {
        window.scrollTo(0, 0);
      }
      return;
    }
    var vcode = document.getElementById('vouch_code').value.trim().toLowerCase();
    if (vcode && !/^vh1-[0-9a-f]{4}(-[0-9a-f]{4}){2}$/.test(vcode)) {
      errbox.textContent = 'That invitation does not look right (vh1-xxxx-xxxx-xxxx). '
        + 'Check it with the person who gave it to you, or leave the field empty.';
      window.scrollTo(0,0); return;
    }
    var btn = this;
    ahConfirm({
      title: 'Seal this in history?',
      lines: [
        'Once you continue, your testimony becomes a permanent part of the '
          + 'record. It can never be edited, only withdrawn.',
        'By continuing you affirm this is your first and only time '
          + 'testifying, and that these are your own words.'
      ],
      ok: 'SEAL IT IN HISTORY', cancel: 'Not yet'
    }).then(function(go){
      if (!go) return;
    btn.disabled = true;
    // Give the gate up to twenty seconds to finish what it started on
    // load. On a slow phone the proof of work is simply still running;
    // waiting here is honest, and refusing to submit is not.
    var waiting = btn.textContent;
    if (!(tokenReady && powReady)) btn.textContent = 'PREPARING YOUR CEREMONY…';
    gateReady(20000).then(function(open){
      btn.textContent = waiting;
      if (!open) {
        // The gate never came. The testimony is finished and must not be
        // held hostage to it: hand over the email path with the words and
        // the keys intact, exactly as a server outage is handled below.
        var k = makeKey();
        var lw = sealedCount() > 0 ? makeLegacyKey() : null;
        btn.disabled = false;
        showFallback(built.sitting, k, lw);
        return;
      }
      submitNow();
    });
    function submitNow(){
    var key = makeKey();
    var legacyWords = sealedCount() > 0 ? makeLegacyKey() : null;
    sha256hex(key).then(function(keyHash){
      built.sitting.continuity = { method: 'sha256-preimage', key_hash: keyHash };
      // sealed words get a Legacy Key; only its stretched fingerprint
      // travels (salted with the continuity fingerprint, already public)
      var lp = legacyWords ? legacyFingerprint(legacyWords, keyHash)
                           : Promise.resolve(null);
      return lp.then(function(lfp){
      if (lfp) built.sitting.legacy = { method: 'pbkdf2-sha256',
        iterations: LITERS, salt: 'continuity', fingerprint: lfp,
        wordlist: 'eff-short-2', words: LCOUNT };
      var payload = JSON.stringify({
        acceptance: acceptance, sitting: built.sitting,
        vouch_code: vcode || undefined,   // optional; the worker resolves it
        website: document.getElementById('website').value,   // honeypot: humans leave empty
        ceremony: ceremony ? { ts: ceremony.ts, seed: ceremony.seed,
                               sig: ceremony.sig, nonce: powNonce } : null,
        submitted_at: new Date().toISOString() });
      return fetch('/api/submit', {method:'POST',
          headers:{'content-type':'application/json'}, body: payload})
        .then(function(r){ return r.json().then(function(j){ return { status: r.status, j: j }; }); })
        .then(function(res){
          if (res.status === 200 && res.j && res.j.ok) {
            received(key, legacyWords);
            return;
          }
          var msg = (res.j && res.j.error) || '';
          // Anything the author can fix or outwait stays INLINE, with their
          // words kept on the page: too fast, rate limited, token expired,
          // incomplete content. The email fallback is only for real outages.
          if (res.status === 429 || res.status === 403 || res.status === 400) {
            btn.disabled = false;
            errbox.textContent = /take your time|too fast/i.test(msg)
              ? 'Please take a moment longer; a testimony is meant to be unhurried. Your words are safe, try again shortly.'
              : (msg ? msg.charAt(0).toUpperCase() + msg.slice(1) : 'Please review your testimony and try again.');
            window.scrollTo(0,0);
            return;
          }
          // Gate down or server trouble: offer the email path so no testimony is lost.
          btn.disabled = false;
          showFallback(built.sitting, key, legacyWords);
        })
        .catch(function(){ btn.disabled = false; showFallback(built.sitting, key, legacyWords); });
      });
    }).catch(function(){
      btn.disabled = false;
      errbox.textContent = 'Your browser could not generate a secure key. Please try a current browser.';
      window.scrollTo(0,0);
    });
    }
    });
  });
})();
</script>
"""

# The site's single serverless function (Cloudflare Pages advanced
# mode: this file is deployed as site/_worker.js). It stores
# acceptances and submissions in the KV namespace bound as
# SUBMISSIONS and serves every other path as a static asset.
WORKER_JS = """// The archive's only moving part.
// Stores acceptance records and testimony submissions in KV
// (binding: SUBMISSIONS). Everything else is static files.
//
// Front-of-funnel gate (protects the review desk from automated floods;
// it never assigns a number and never touches the archive — a person
// still reads every submission before any number is spent):
//   * GET /api/ceremony issues an HMAC-signed, server-timed start token
//     carrying a proof-of-work seed. The secret (CEREMONY_SECRET) lives
//     only in the Worker env, never in the repo.
//   * /api/submit verifies the token server-side (client clocks are never
//     trusted), refuses submissions faster than a human could write,
//     checks the proof of work, a hidden honeypot, per-IP + global rate
//     limits, a substance floor (name + two answers), and the oath.
// Bot defenses target automation and volume ONLY — never the author's
// words, feelings, language, or the darkness of what they carry.
//
// Flood/cost control (the D5 review, 2026-07-25): EVERY endpoint that can
// write to KV passes through limited() first, which spends the day's global
// budget before any per-address counter, so the number of KV writes this
// worker can be made to perform is bounded no matter how many addresses a
// flooder holds. Where a caller can be authenticated (return, withdraw,
// vouch), the limiter runs only after that proof, so a stranger's flood
// costs nothing at all. Every cap is an env var; the true first fence is
// the Cloudflare rate-limit rule in OPERATIONS.md §8.
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!url.pathname.startsWith('/api/')) {
      return env.ASSETS.fetch(request);
    }
    // The one GET endpoint: a signed ceremony-start token. The server
    // stamps its own time and a proof-of-work seed, signs both, and the
    // page hands the token back at submission.
    if (url.pathname === '/api/ceremony') {
      if (request.method !== 'GET') return jsonResp({ ok: false, error: 'GET only' }, 405);
      const secret = env.CEREMONY_SECRET;
      if (!secret) return jsonResp({ ok: false, error: 'gate not configured' }, 503);
      const ts = Date.now();
      const sb = new Uint8Array(16); crypto.getRandomValues(sb);
      const seed = [...sb].map((x) => x.toString(16).padStart(2, '0')).join('');
      const sig = await hmacHex(secret, ts + '.' + seed);
      return jsonResp({ ok: true, ts, seed, sig,
        pow_bits: intEnv(env.CEREMONY_POW_BITS, 14),
        min_seconds: intEnv(env.CEREMONY_MIN_SECONDS, 45) });
    }
    if (request.method !== 'POST') {
      return jsonResp({ ok: false, error: 'POST only' }, 405);
    }
    const kind = url.pathname === '/api/accept' ? 'accept'
               : url.pathname === '/api/submit' ? 'sub'
               : url.pathname === '/api/return' ? 'ret'
               : url.pathname === '/api/withdraw' ? 'withdraw'
               : url.pathname === '/api/legacy' ? 'legacy'
               : url.pathname === '/api/vouch' ? 'vouch' : null;
    if (!kind) return jsonResp({ ok: false, error: 'unknown endpoint' }, 404);
    let body, raw;
    try { body = await request.json(); raw = JSON.stringify(body); }
    catch (e) { return jsonResp({ ok: false, error: 'bad json' }, 400); }
    if (raw.length > 30000) return jsonResp({ ok: false, error: 'too large' }, 413);

    if (kind === 'vouch') {
      // Self-serve vouching (POLICY.md, Tier 2). The voucher proves their
      // continuity key exactly as the return page does; the code was born
      // in their browser and ONLY its SHA-256 travels. The worker stores
      // that fingerprint as a single-use token (30 days) plus a one-year
      // quota mark. The desk re-checks quota and use from the custody
      // edge file at review: this gate is the era's first fence, not the
      // law. The quota is enforced but never returned as a number.
      if (!(/^[0-9]{1,9}$/.test(body.registry_id || '') &&
            /^ah1-[0-9a-f]{4}(-[0-9a-f]{4}){7}$/.test(body.key || '') &&
            /^[0-9a-f]{64}$/.test(body.code_hash || '') &&
            body.attested === true)) {
        return jsonResp({ ok: false, error: 'incomplete vouch' }, 400);
      }
      const vres = await env.ASSETS.fetch(
        new URL('/keys/' + Number(body.registry_id) + '.json', request.url));
      if (!vres.ok ||
          !(vres.headers.get('content-type') || '').includes('json')) {
        return jsonResp({ ok: false, error: 'unknown record' }, 404);
      }
      const vmeta = await vres.json();
      const vdig = await crypto.subtle.digest('SHA-256',
        new TextEncoder().encode(body.key));
      const vkh = [...new Uint8Array(vdig)]
        .map((x) => x.toString(16).padStart(2, '0')).join('');
      if (vkh !== vmeta.key_hash) {
        return jsonResp({ ok: false, error: 'key does not open this record' }, 403);
      }
      if (vmeta.status === 'memorialized') {
        return jsonResp({ ok: false, error: 'this record is memorialized' }, 403);
      }
      // Only now, with a real key proven, may this cost KV anything.
      if (await limited(env, 'vch', clientIp(request),
                        intEnv(env.VOUCH_GLOBAL_PER_DAY, 300),
                        intEnv(env.VOUCH_IP_PER_HOUR, 20))) {
        return jsonResp({ ok: false, error: 'please try again later' }, 429);
      }
      const vrid = String(Number(body.registry_id));
      const marks = await env.SUBMISSIONS.list({ prefix: 'vouchby:' + vrid + ':' });
      if (marks.keys.length >= 3) {
        return jsonResp({ ok: false, error: 'no code can be minted right now' }, 403);
      }
      await env.SUBMISSIONS.put('vouchtok:' + body.code_hash,
        JSON.stringify({ by: vrid, minted_at: new Date().toISOString() }),
        { expirationTtl: 2592000 });
      // The mark lives exactly as long as the invitation itself: the
      // fence holds at most three LIVE invitations. The rolling-year
      // quota is spent only at ENROLLMENT, from the custody edge file
      // (like numbers: only approval spends; a failed submission costs
      // the inviter nothing).
      await env.SUBMISSIONS.put('vouchby:' + vrid + ':' + body.code_hash, '1',
        { expirationTtl: 2592000 });
      return jsonResp({ ok: true });
    }

    // --- Front-of-funnel gate: first-testimony submissions only ---------
    if (kind === 'sub') {
      const gate = await submissionGate(request, env, body);
      if (gate) return gate;   // a refusal (or a silent honeypot accept)
    }
    const plausibleEmail = (e) => typeof e === 'string' && /^[^\\s@]+@[^\\s@]+$/.test(e);
    if (kind === 'accept' && !(plausibleEmail(body.email) && body.affirmed && body.affirmed.length === 5)) {
      return jsonResp({ ok: false, error: 'incomplete acceptance' }, 400);
    }
    // The acceptance endpoint is the front of the funnel: it cannot carry
    // a ceremony token (that is minted on the writing page), so it is the
    // one KV-write path without the proof-of-work gate. Flood control is
    // therefore its own responsibility — a per-IP hourly cap and a global
    // daily cap, the same shape as the submission gate, so no one can run
    // up KV writes or bury the review desk with junk acceptances. It never
    // touches the archive; this is availability and cost protection only.
    if (kind === 'accept') {
      // This is the one endpoint nobody can authenticate — it IS the front
      // door — so the day's budget is deliberately generous, and the edge
      // rule is what stands in front of it.
      if (await limited(env, 'acc', clientIp(request),
                        intEnv(env.ACCEPT_GLOBAL_PER_DAY, 1000),
                        intEnv(env.ACCEPT_IP_PER_HOUR, 10))) {
        return jsonResp({ ok: false, error: 'please try again later' }, 429);
      }
    }
    const validAnswers = (s) => {
      if (!(s && s.answers && s.answers.q_name && s.answers.q_name.text &&
            s.answers.q_name.text.length <= 30)) return false;
      for (const k in s.answers) {
        const a = s.answers[k];
        if (!a || typeof a.text !== 'string' || a.text.length > 400 ||
            (a.visibility !== 'public' && a.visibility !== 'sealed_until_death')) {
          return false;
        }
      }
      return true;
    };
    // Substance floor: a record needs the name plus at least two answers
    // that are actually answered — a few words each. Any question the
    // author chooses; a given answer must be 10..400 chars (a thinner one
    // is a slip or a bot, and is not counted). The name is identity, not
    // testimony, so it never counts toward the two.
    // A name and a place are answered in one word and are still complete
    // answers. They are exempt from the floor and are not counted toward
    // the two, exactly as the writing page has it: if these two rules
    // ever disagree, a person is told their testimony is fine and then
    // refused by the worker with no way to see why.
    const SHORT_OK = { q_name: 1, q_place: 1 };
    const substanceOK = (s) => {
      const a = (s && s.answers) || {};
      let count = 0;
      for (const k in a) {
        if (SHORT_OK[k]) continue;
        const t = ((a[k] && a[k].text) || '').trim();
        if (t.length === 0) continue;
        if (t.length < 10) return false;
        count++;
      }
      return count >= 2;
    };
    if (kind === 'sub') {
      const c = body.sitting && body.sitting.continuity;
      const acc = body.acceptance;
      // The oath: all five affirmations, one of which is "this is my
      // only Registry record". The substance floor: name + at least two
      // answers, each a real few-word answer (10..400 chars). Neither
      // dictates WHICH questions — sovereignty keeps every answer optional
      // (POLICY.md); a record simply needs some testimony in it.
      if (!(validAnswers(body.sitting) && acc && plausibleEmail(acc.email) &&
            acc.affirmed && acc.affirmed.length === 5 && substanceOK(body.sitting) &&
            c && c.method === 'sha256-preimage' && /^[0-9a-f]{64}$/.test(c.key_hash || ''))) {
        return jsonResp({ ok: false, error: 'incomplete submission' }, 400);
      }
      // Sealed answers require a Legacy Key fingerprint (the writing page
      // always provides one) — a seal that could NEVER open by a trusted
      // hand, only by the century, must at least be deliberate (email path).
      const anySealed = Object.keys(body.sitting.answers).some(function(k){
        return body.sitting.answers[k].visibility === 'sealed_until_death'; });
      const lg = body.sitting.legacy;
      if (anySealed &&
          !(lg && lg.method === 'pbkdf2-sha256' && lg.iterations === 600000 &&
            /^[0-9a-f]{64}$/.test(lg.fingerprint || ''))) {
        return jsonResp({ ok: false, error: 'incomplete submission' }, 400);
      }
      if (!anySealed && lg !== undefined) {
        return jsonResp({ ok: false, error: 'incomplete submission' }, 400);
      }
      // A vouch code (optional). If the author carries one it must be
      // real: the worker resolves it to the voucher's number ITSELF and
      // never trusts a typed claim. The raw code is not stored, and the
      // desk still confirms the edge at enrollment (--vouched-by).
      if (body.vouch_code !== undefined && body.vouch_code !== '') {
        const vc = String(body.vouch_code).trim().toLowerCase();
        if (!/^vh1-[0-9a-f]{4}(-[0-9a-f]{4}){2}$/.test(vc)) {
          return jsonResp({ ok: false, error: 'That invitation does not look right. '
            + 'Check it with the person who gave it to you, or leave the field empty.' }, 400);
        }
        const cdig = await crypto.subtle.digest('SHA-256',
          new TextEncoder().encode(vc));
        const chash = [...new Uint8Array(cdig)]
          .map((x) => x.toString(16).padStart(2, '0')).join('');
        const tok = await env.SUBMISSIONS.get('vouchtok:' + chash);
        if (!tok) {
          const used = await env.SUBMISSIONS.get('vouchused:' + chash);
          return jsonResp({ ok: false, error: used
            ? 'That invitation has already been used. Each one works once; '
              + 'ask the person who invited you to create a new one.'
            : 'That invitation is not valid. It may be mistyped or older than '
              + '30 days. Check it, or leave the field empty.' }, 400);
        }
        const tinfo = JSON.parse(tok);
        body.vouched_by = tinfo.by;
        body.vouch_gate = { code_hash: chash, minted_at: tinfo.minted_at,
                            verified_at: new Date().toISOString() };
        delete body.vouch_code;
        raw = JSON.stringify(body);
        await env.SUBMISSIONS.delete('vouchtok:' + chash);
        await env.SUBMISSIONS.put('vouchused:' + chash,
          JSON.stringify({ by: tinfo.by, used_at: new Date().toISOString() }),
          { expirationTtl: 7776000 });
      }
    }
    if (kind === 'legacy') {
      // A death report: a record's number + its six-word Legacy Key + a
      // human attestation. The worker verifies FORMAT only and stores it
      // for the steward — key verification is a desk ceremony (the
      // stretched fingerprint is deliberately not published, and the
      // mourning ceremony runs before anything opens). The response
      // is byte-identical for right and wrong words: no oracle, ever.
      if (!(/^[0-9]{1,9}$/.test(body.registry_id || '') &&
            typeof body.words === 'string' &&
            /^[a-z]+( [a-z]+){5}$/.test(body.words.trim().toLowerCase()) &&
            body.attested === true)) {
        return jsonResp({ ok: false, error: 'incomplete report' }, 400);
      }
      // A death report cannot be authenticated here (verifying the words
      // would make this an oracle), so like /api/accept it leans on the
      // caps and the edge rule.
      if (await limited(env, 'leg', clientIp(request),
                        intEnv(env.LEGACY_GLOBAL_PER_DAY, 500),
                        intEnv(env.LEGACY_IP_PER_HOUR, 3))) {
        return jsonResp({ ok: false, error: 'please try again later' }, 429);
      }
    }
    if (kind === 'ret') {
      if (!(validAnswers(body.sitting) &&
            /^[0-9]{1,9}$/.test(body.registry_id || '') &&
            (body.kind === 'second' || body.kind === 'final') &&
            /^ah1-[0-9a-f]{4}(-[0-9a-f]{4}){7}$/.test(body.key || ''))) {
        return jsonResp({ ok: false, error: 'incomplete return' }, 400);
      }
      // The system verifies the key itself, against the record's
      // published fingerprint. A wrong key opens nothing.
      const metaRes = await env.ASSETS.fetch(
        new URL('/keys/' + Number(body.registry_id) + '.json', request.url));
      // A host may answer a missing file with a fallback page instead of
      // a 404 (Pages' SPA mode does); only a JSON body is a fingerprint.
      if (!metaRes.ok ||
          !(metaRes.headers.get('content-type') || '').includes('json')) {
        return jsonResp({ ok: false, error: 'unknown record' }, 404);
      }
      const meta = await metaRes.json();
      const digest = await crypto.subtle.digest('SHA-256',
        new TextEncoder().encode(body.key));
      const keyHash = [...new Uint8Array(digest)]
        .map((x) => x.toString(16).padStart(2, '0')).join('');
      if (keyHash !== meta.key_hash) {
        return jsonResp({ ok: false, error: 'key does not open this record' }, 403);
      }
      if (meta.status === 'memorialized' || meta.versions >= 3) {
        return jsonResp({ ok: false, error: 'record can no longer grow' }, 403);
      }
      const expected = meta.versions === 1 ? 'second' : 'final';
      if (body.kind !== expected) {
        return jsonResp({ ok: false, error: 'expected ' + expected + ' testimony' }, 400);
      }
      // Spacing (POLICY.md): at least a year between testimonies. The date
      // is published in the record's fingerprint; a closer sitting is
      // refused here so no one writes a whole testimony only to be turned
      // away at review. A waiver, when granted, is an operator act.
      if (meta.eligible_after && Date.now() < Date.parse(meta.eligible_after)) {
        return jsonResp({ ok: false, error: 'There is at least a year between testimonies. '
          + 'Experience life and come back after ' + meta.eligible_after.slice(0, 10) + '.' }, 403);
      }
      // Every check above is free of KV. Only a proven key spends the
      // budget — and a returning author cannot flood the desk with
      // unique, permanent entries.
      if (await limited(env, 'ret', clientIp(request),
                        intEnv(env.RETURN_GLOBAL_PER_DAY, 300),
                        intEnv(env.RETURN_IP_PER_HOUR, 5))) {
        return jsonResp({ ok: false, error: 'please try again later' }, 429);
      }
    }
    if (kind === 'withdraw') {
      // A withdrawal request. The worker cannot touch the append-only
      // archive; it authenticates the request against the record's
      // published fingerprint and stores it for a steward to complete
      // with tools/withdraw.py. The key opens nothing on its own.
      if (!(/^[0-9]{1,9}$/.test(body.registry_id || '') &&
            (body.version === 1 || body.version === 2 || body.version === 3) &&
            /^ah1-[0-9a-f]{4}(-[0-9a-f]{4}){7}$/.test(body.key || ''))) {
        return jsonResp({ ok: false, error: 'incomplete withdrawal' }, 400);
      }
      const metaRes = await env.ASSETS.fetch(
        new URL('/keys/' + Number(body.registry_id) + '.json', request.url));
      if (!metaRes.ok ||
          !(metaRes.headers.get('content-type') || '').includes('json')) {
        return jsonResp({ ok: false, error: 'unknown record' }, 404);
      }
      const meta = await metaRes.json();
      const digest = await crypto.subtle.digest('SHA-256',
        new TextEncoder().encode(body.key));
      const keyHash = [...new Uint8Array(digest)]
        .map((x) => x.toString(16).padStart(2, '0')).join('');
      if (keyHash !== meta.key_hash) {
        return jsonResp({ ok: false, error: 'key does not open this record' }, 403);
      }
      if (body.version > meta.versions) {
        return jsonResp({ ok: false, error: 'no such testimony to withdraw' }, 400);
      }
      // The KV key is deterministic (duplicates collapse), but the write
      // OPERATIONS are not free; a proven key still cannot hammer them.
      if (await limited(env, 'wdr', clientIp(request),
                        intEnv(env.WITHDRAW_GLOBAL_PER_DAY, 300),
                        intEnv(env.WITHDRAW_IP_PER_HOUR, 5))) {
        return jsonResp({ ok: false, error: 'please try again later' }, 429);
      }
    }
    // Withdrawals and death reports are idempotent: repeated requests for
    // the same record collapse onto ONE deterministic KV key, so a flurry
    // of clicks (or a bot) can never flood the review desk with duplicates.
    // Every other kind stays unique per submission.
    const key = kind === 'withdraw'
      ? 'withdraw:' + Number(body.registry_id) + ':' + body.version
      : kind === 'legacy'
      ? 'legacy:' + Number(body.registry_id)
      : kind + ':' + new Date().toISOString() + ':' + crypto.randomUUID();
    // A death report is a SIGNAL to begin the mourning ceremony, not
    // evidence in itself — so the FIRST report for a record stands, and
    // later ones are answered exactly the same way but never stored.
    // Last-write-wins would let a stranger quietly overwrite a grieving
    // family's genuine report: record numbers are public, and the words
    // are deliberately not verified here (verifying them would make this
    // an oracle). The steward's ceremony is identical either way — write
    // to the enrollment email, wait thirty days — so nothing is lost by
    // keeping the first, and a real report can no longer be erased.
    if (kind === 'legacy') {
      let already = null;
      try { already = await env.SUBMISSIONS.get(key); } catch (e) {}
      if (already) return jsonResp({ ok: true });
    }
    // The store can fail (quota, a bad hour at the edge). Say so plainly
    // and let the page offer the email path: an unhandled throw here would
    // return 500 for EVERY endpoint, and a human who just wrote their
    // testimony deserves better than a blank error.
    try {
      await env.SUBMISSIONS.put(key, raw);
    } catch (e) {
      return jsonResp({ ok: false, error: 'The Record could not store this right now. '
        + 'Your words are still on this page — please try again in a moment, '
        + 'or use the email fallback below.' }, 503);
    }
    return jsonResp({ ok: true });
  }
};

// The bot/flood gate for first-testimony submissions. Returns a Response
// to STOP (a refusal, or a byte-identical honeypot accept), or null to let
// the submission continue to the normal structural checks. It never spends
// a number and never writes to the archive.
async function submissionGate(request, env, body) {
  // 1. Honeypot: a field no human ever sees or fills. If it is filled,
  //    answer exactly as we answer success and store NOTHING — the flooder
  //    gets no signal to tune against, and no garbage reaches the desk.
  if (body.website) return jsonResp({ ok: true });

  // 2. The gate must be configured. A misconfigured gate fails CLOSED and
  //    loudly — it must never quietly degrade into no gate at all.
  const secret = env.CEREMONY_SECRET;
  if (!secret) return jsonResp({ ok: false, error: 'The Record is not accepting submissions right now' }, 503);

  // 3. Ceremony token: server-signed and server-TIMED. The elapsed writing
  //    time is measured against the signed server timestamp, so a spoofed
  //    client clock cannot fake having taken time.
  const c = body.ceremony || {};
  if (typeof c.ts !== 'number' || typeof c.seed !== 'string' ||
      !(await hmacEqual(secret, c.ts + '.' + c.seed, c.sig))) {
    return jsonResp({ ok: false, error: 'invalid ceremony token. Please reload and begin again' }, 403);
  }
  const elapsed = Date.now() - c.ts;
  const minMs = intEnv(env.CEREMONY_MIN_SECONDS, 45) * 1000;
  const maxMs = intEnv(env.CEREMONY_MAX_SECONDS, 86400) * 1000;
  if (elapsed < 0 || elapsed > maxMs) {
    return jsonResp({ ok: false, error: 'this ceremony has expired. Please reload and begin again' }, 403);
  }
  if (elapsed < minMs) {
    return jsonResp({ ok: false, error: 'too fast. Please take your time; a testimony is meant to be unhurried, and your words are safe' }, 429);
  }

  // 4. Proof of work: the page quietly found a nonce so SHA-256(seed.nonce)
  //    has N leading zero bits, while the author writes. One hash to check.
  //
  //    On the honest cost of this fence: the page solves it through
  //    WebCrypto, one awaited digest at a time, yielding to the browser so
  //    the page never freezes — a few thousand hashes a second, fewer on an
  //    old phone. A flooder uses native code, millions a second. So every
  //    bit added here costs an old phone in a poor country far more than it
  //    costs the attacker, and this archive is for that phone. Fourteen bits
  //    (~16k hashes) stays under a few seconds on weak hardware and is
  //    invisible beside the forty-five-second floor it runs behind. It is a
  //    speed bump, not a wall; the wall is the edge rule (OPERATIONS.md §8).
  //    CEREMONY_POW_BITS raises it without a deploy if that ever changes.
  const powBits = intEnv(env.CEREMONY_POW_BITS, 14);
  if (powBits > 0) {
    if (typeof c.nonce !== 'string' ||
        leadingZeroBits(await sha256Bytes(c.seed + '.' + c.nonce)) < powBits) {
      return jsonResp({ ok: false, error: 'challenge unmet. Please reload and begin again' }, 403);
    }
  }
  // 4b. (Optional drop-in) A hosted challenge could verify here instead of,
  //     or alongside, the self-hosted proof of work — e.g. Cloudflare
  //     Turnstile. Self-hosted is the DEFAULT (no third-party dependency,
  //     best permanence fit); this stays commented until deliberately chosen:
  //   if (env.TURNSTILE_SECRET) {
  //     const ok = await verifyTurnstile(env.TURNSTILE_SECRET, body.turnstile,
  //                  request.headers.get('CF-Connecting-IP'));
  //     if (!ok) return jsonResp({ ok: false, error: 'challenge unmet' }, 403);
  //   }

  // 5. Rate limits protect the review desk: a per-IP hourly cap and a global
  //    daily cap. Approximate (KV is eventually consistent) — the desk stays
  //    the authority; this is flood control, not law.
  // A valid ceremony token had to be minted, held for the minimum time and
  // its challenge solved before a single KV write is risked here.
  const fence = await limited(env, 'sub', clientIp(request),
                              intEnv(env.CEREMONY_GLOBAL_PER_DAY, 300),
                              intEnv(env.CEREMONY_IP_PER_HOUR, 3));
  if (fence === 'global') {
    return jsonResp({ ok: false, error: 'The Record is receiving many testimonies today. Your words are safe on this page. Please try again soon' }, 429);
  }
  if (fence === 'ip') {
    return jsonResp({ ok: false, error: 'this connection has sent several testimonies recently. Please try again later' }, 429);
  }
  return null;   // gate passed — continue to the normal structural checks
}

function intEnv(v, d) { const n = parseInt(v, 10); return Number.isFinite(n) && n >= 0 ? n : d; }

function clientIp(request) { return request.headers.get('CF-Connecting-IP') || 'local'; }

// Flood control, in ONE shape for every endpoint that writes to KV.
//
// The GLOBAL ceiling is consulted FIRST, and that order is the whole point.
// over() writes as it counts, so once the day's ceiling is reached this
// function stops writing to KV altogether — for every address, familiar or
// brand new. The old order (per-IP first) let anyone with a fresh address
// force one KV write per request, forever: a never-seen address always
// starts under its own cap, so the write happened before the daily ceiling
// ever got a say, and IPv6 hands out fresh addresses by the billion. That
// was unbounded writes, and an exhausted KV quota takes every endpoint down
// with it.
//
// The price of this order is honest and worth naming: refused attempts also
// spend the day's budget, so a determined flooder can use up a day's
// submissions. That is a BOUNDED, self-healing outage — it resets at
// midnight UTC, costs nothing, and touches no record — and the Cloudflare
// rate-limit rule (OPERATIONS.md §8) is what keeps a flood from reaching
// the worker at all. Where an endpoint can authenticate the caller, the
// limiter is called only AFTER that check, so a stranger's flood spends
// nothing and the budget belongs to people who actually hold a key.
//
// Both counts are approximate: KV is eventually consistent, so a tight
// burst can slip past. The desk remains the authority; this is cost and
// availability protection, never law.
// Returns which fence stopped this request — 'global' or 'ip' — or null
// when it may pass. The caller needs the difference to tell the truth: a
// global ceiling is the archive's busy day, not this visitor's fault, and
// must never be worded as though they had done something.
async function limited(env, tag, ip, globalMax, ipMax) {
  const now = Date.now();
  const day = Math.floor(now / 86400000);
  const hour = Math.floor(now / 3600000);
  if (await over(env, 'rl:' + tag + ':global:' + day, globalMax, 90000)) return 'global';
  if (await over(env, 'rl:' + tag + ':ip:' + ip + ':' + hour, ipMax, 3700)) return 'ip';
  return null;
}

async function over(env, key, limit, ttl) {
  let cur = 0;
  // A counter that cannot be read must never refuse a human: if KV is
  // unreachable the payload write below is what reports it, plainly.
  try { cur = parseInt(await env.SUBMISSIONS.get(key), 10) || 0; }
  catch (e) { return false; }
  if (cur >= limit) return true;
  // A lost tick is harmless — the count is approximate by design.
  try { await env.SUBMISSIONS.put(key, String(cur + 1), { expirationTtl: ttl }); }
  catch (e) {}
  return false;
}

async function hmacHex(secret, msg) {
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(msg));
  return [...new Uint8Array(sig)].map((x) => x.toString(16).padStart(2, '0')).join('');
}

async function hmacEqual(secret, msg, hex) {
  if (typeof hex !== 'string') return false;
  const want = await hmacHex(secret, msg);
  if (want.length !== hex.length) return false;
  let diff = 0;
  for (let i = 0; i < want.length; i++) diff |= want.charCodeAt(i) ^ hex.charCodeAt(i);
  return diff === 0;
}

async function sha256Bytes(str) {
  return new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str)));
}

function leadingZeroBits(bytes) {
  let n = 0;
  for (let i = 0; i < bytes.length; i++) {
    if (bytes[i] === 0) { n += 8; continue; }
    n += Math.clz32(bytes[i]) - 24;
    break;
  }
  return n;
}

function jsonResp(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status, headers: { 'content-type': 'application/json' }
  });
}
"""


def render_enter():
    if REGISTRY_OPEN:
        begin_block = ('<p class="center">\n'
                       '<a id="begin" class="aura" href="begin.html" aria-disabled="true">'
                       'BEGIN MY FIRST TESTIMONY</a>\n</p>\n'
                       '<p class="center quiet agree">By clicking BEGIN MY FIRST '
                       'TESTIMONY you agree to the '
                       '<a href="privacy.html" target="_blank" '
                       'rel="noopener">Privacy Policy</a>.</p>')
    else:
        begin_block = ('<p class="center">\n'
                       '<a id="begin" class="aura" aria-disabled="true">'
                       'THE RECORD WILL SOON OPEN</a>\n</p>\n'
                       '<p class="center quiet">The Record is not yet open for new '
                       'testimonies. You are welcome to read everything and prepare. '
                       'Please return soon to leave yours.</p>')
    body = CONSENT_BODY.replace('__BEGIN_BLOCK__', begin_block)
    js = CONSENT_JS.replace('__REGISTRY_OPEN__', 'true' if REGISTRY_OPEN else 'false')
    html_out = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
                '<title>Before writing your testimony · ' + brand.BRAND + '</title>\n'
                '<style>' + DARK_CSS + '</style>\n</head>\n<body>\n'
                '<div class="page">' + body + '</div>\n' + js +
                '\n</body>\n</html>')
    return html_out.replace('__BRAND__', brand.BRAND)


def render_begin(qmeta):
    cap = qmeta["answer_char_cap"]
    qbyid = {item["id"]: item for item in qmeta["questions"]}
    parts = []
    parts.append('<div id="writing">')
    parts.append('<h1>My First Testimony</h1>')
    parts.append('<p class="banner hidden" id="noaccept">This page '
                 'works after the <a href="enter.html">Before writing your testimony</a> page, '
                 'where the principles are accepted and your email is given. '
                 'Please start there.</p>')
    # The requirement, on its own, in plain sight. It used to sit in the
    # middle of a grey paragraph beside the character caps, so a person
    # met a greyed-out button and had to hunt for the reason. What a form
    # demands should be the easiest thing on it to find.
    parts.append('<p class="needed">To complete a testimony you need '
                 '<strong>your name and any two answers</strong>, each a few '
                 'words (%d characters or more). Everything else is optional.</p>'
                 % ANSWER_MIN)
    parts.append('<p class="meta">Take your time. An unanswered question is '
                 'recorded as silence. Each answer may hold at most %d '
                 'characters, the cap is the craft; your name holds at most %d. '
                 'Nothing leaves this page until the final confirmation.</p>'
                 % (cap, NAME_CAP))
    parts.append('<p class="err" id="errors"></p>')
    # Honeypot: a field no human sees or fills. Off-screen, not hidden by
    # display:none (some bots skip those), aria-hidden and out of tab order.
    # The .offscreen class carries the old inline style: the hashed CSP
    # forbids style attributes, and the stylesheet is hashed as a whole.
    parts.append('<div aria-hidden="true" class="offscreen">'
                 '<label>Leave this field empty'
                 '<input type="text" id="website" name="website" tabindex="-1" '
                 'autocomplete="off" value=""></label></div>')
    # The two identity questions are answered in a word and are exempt from
    # the floor, so filling them moves no counter. Said here, beside the
    # question itself, because a counter that ignores an answer you just
    # typed reads as broken rather than as designed.
    #
    # These marks are the SITE's furniture and can be reworded freely. The
    # prompts and notes beneath them cannot: questions/v1.json is hashed
    # into the GENESIS event and stamped into Bitcoin, so changing a word
    # of a question makes verify.py fail on the founding anchor.
    NOT_COUNTED = {"q_name": "(required)",
                   "q_place": "(optional but doesn't count as an answer)"}
    for qid in qmeta["testimony_order"]["first"]:
        q = qbyid[qid]
        qcap = NAME_CAP if qid == "q_name" else cap
        parts.append('<div class="q">')
        mark = NOT_COUNTED.get(qid)
        parts.append('<p class="prompt">%s%s</p>'
                     % (html.escape(q["prompt"]),
                        ' <span class="plainnote">%s</span>' % mark if mark else ''))
        if q.get("note"):
            parts.append('<p class="note">%s</p>' % html.escape(q["note"]))
        # dir=auto so an author writing Arabic, Hebrew or Persian gets a
        # right-to-left box the moment they type, with nothing configured.
        parts.append('<textarea id="%s" maxlength="%d" dir="auto"></textarea>'
                     % (qid, qcap))
        parts.append('<div class="under"><label class="seal">'
                     '<input type="checkbox" id="%s_seal" class="sealbox"> '
                     'seal this answer until my death'
                     '</label><span id="%s_count"></span></div>' % (qid, qid))
        if qid in ("q_hardest", "q_regret"):
            parts.append('<p class="help">%s</p>' % HELP_LINE)
        parts.append('</div>')
    parts.append(
        '<div class="banner hidden" id="seal_explain">'
        '<strong>What sealing means.</strong> A sealed answer is never shown '
        'on any page, never published, and never included in anything the '
        'archive distributes. It is hidden from the world, not from the '
        'archive: the steward reads it once when your testimony is reviewed, '
        'and it is kept in readable form afterwards. It has to be. The '
        'promise below, that every seal opens after one hundred years, is '
        'only keepable if the archive can still open it; words locked so '
        'that no one but you could ever read them would simply be lost the '
        'day your key was. <strong>If something must never be read by '
        'anyone, do not write it here.</strong> It opens when someone you '
        'trust brings your '
        '<strong>Legacy Key</strong>, six plain words you will receive '
        'after you finish, and reports your death. If the key is never '
        'used, every seal opens on its own one hundred years after '
        'enrollment.<br>'
        '<em>Some are opened by those we trust. '
        'The rest are opened by time itself.</em></div>')
    # Asked, never guessed. Language detection is a library the archive will
    # not carry, and a wrong guess is worse than no answer: it would tell a
    # screen reader to pronounce someone's words in the wrong tongue. The
    # browser's own setting is only the default; the author decides.
    parts.append(
        '<div class="q" id="langq">'
        '<p class="prompt">I AM WRITING IN '
        '<span class="plainnote">(so your words are read and spoken '
        'correctly)</span></p>'
        '<select id="lang_tag">'
        + "".join('<option value="%s">%s</option>' % (t, n) for t, n in [
            ("", "not saying"), ("en", "English"), ("fr", "Français"),
            ("es", "Español"), ("pt", "Português"), ("de", "Deutsch"),
            ("it", "Italiano"), ("nl", "Nederlands"), ("pl", "Polski"),
            ("ru", "Русский"), ("uk", "Українська"), ("tr", "Türkçe"),
            ("ar", "العربية"), ("he", "עברית"), ("fa", "فارسی"),
            ("hi", "हिन्दी"), ("bn", "বাংলা"), ("ur", "اردو"),
            ("zh", "中文"), ("ja", "日本語"), ("ko", "한국어"),
            ("vi", "Tiếng Việt"), ("th", "ไทย"), ("id", "Bahasa Indonesia"),
            ("sw", "Kiswahili"), ("other", "another language"),
        ]) +
        '</select>'
        '</div>')
    parts.append(
        '<div class="q" id="vouchq">'
        '<p class="prompt">MY INVITATION '
        '<span class="plainnote">(optional)</span></p>'
        '<p class="note">If a human already in The Record invited you, '
        'enter the invitation they gave you. If not, leave this empty; a '
        'person will verify your submission another way.</p>'
        '<input type="text" id="vouch_code" maxlength="18" '
        'placeholder="vh1-xxxx-xxxx-xxxx" autocomplete="off" spellcheck="false">'
        '</div>')
    # Beside the button it governs, not paragraphs above it. A disabled
    # button with its reason elsewhere is a locked door with the notice
    # on another wall.
    parts.append('<p class="needed" id="floor_note"></p>')
    parts.append('<p><button class="finish" id="finish" disabled>COMPLETE MY TESTIMONY</button></p>')
    # Every other page offers a way back; this one held people until they
    # finished or closed the tab. A door out is not an invitation to leave,
    # it is what makes staying a choice. It asks first if anything has been
    # written, because nothing here is saved until the final confirmation.
    parts.append('<p class="center quiet"><a href="index.html" id="leave">'
                 'return to the lights</a></p>')
    parts.append('</div>')
    parts.append(
        '<div id="received">'
        '<p class="pagetimer"></p>'
        '<h1>Your testimony has been received</h1>'
        # "If it is accepted" left the obvious question unanswered: accepted
        # by whom, and against what? Read on this screen it sounds like a
        # judgement of the life just written. Say what the reading is
        # actually for, and say the rest out loud too, because the person
        # who most needs to hear it is the one who just wrote the hardest
        # thing they carry and is now waiting to be told it did not qualify.
        '<p>Every testimony is read by a person, as every testimony is in '
        'this era. That reading is to keep out machines, spam and second '
        'records, nothing else. <strong>No testimony is ever refused for '
        'being dark, heavy, plain, or short.</strong></p>'
        '<p>When yours is confirmed, your number is assigned in sequence, '
        'your light is added, and your number is sent to '
        '<strong id="rec_email"></strong>. If anything needs another pass, '
        'you will hear at the same address.</p>'
        '<h2>YOUR CONTINUITY KEY</h2>'
        '<p>Shown once, now, never again. It was created in your browser a '
        'moment ago; The Record holds only its fingerprint, not the key. It '
        'is the only proof that this record is yours: you will need it to '
        'enter your Second and Final Testimonies, and to withdraw. If it is '
        'lost, it cannot be recovered or reissued, not by us, not by anyone. '
        'Write it down, save it in more than one place, tell no one.</p>'
        '<pre class="key" id="thekey"></pre>'
        '<p><button class="finish" id="copykey">'
        'COPY MY KEY</button> '
        '<a id="savekey" class="finish" href="#">DOWNLOAD MY KEY</a></p>'
        '<p id="contwrap" class="hidden">'
        '<button class="finish" id="contbtn">CONTINUE TO LEGACY KEY</button></p>'
        '</div>')
    parts.append(
        '<div id="legacyscreen" class="hidden">'
        '<p class="pagetimer"></p>'
        '<h1>YOUR LEGACY KEY</h1>'
        '<p>You sealed words today. These six words are how they will one '
        'day open. The key does nothing while you live. Give it to the '
        'person who should open your sealed words when you are gone, on '
        'paper or in a spoken promise. If it is never used, your seals open '
        'on their own one hundred years after enrollment.</p>'
        '<pre class="key" id="thelegacy"></pre>'
        '<p><button class="finish" id="copylegacy">'
        'COPY MY KEY</button> '
        '<a id="savelegacy" class="finish" href="#">DOWNLOAD MY KEY</a></p>'
        '</div>')
    parts.append(
        '<div id="ended" class="hidden">'
        '<h1>This page has closed</h1>'
        '<p>For your safety, keys are shown only once and are never kept '
        'here. If you wrote yours down, all is well. If you left before '
        'saving your continuity key, it cannot be shown again.</p>'
        '<p class="center quiet">Is someone else writing on this computer? '
        '<a href="enter.html">Begin a new testimony</a>.</p>'
        '<p class="center gohome"><a class="aura" href="index.html">'
        'RETURN TO THE LIGHTS</a></p>'
        '</div>')
    parts.append(
        '<div id="closing" class="hidden">'
        '<p>__BRAND__ is free, for every human, always. It is kept alive by '
        'donations. A donation buys nothing here: no marks, no priority, '
        'no tiers.</p>'
        + ('<p class="center"><a class="finish" href="' + brand.DONATE_URL + '" '
           'rel="noopener">HELP KEEP THE LIGHTS ON</a></p>'
           if brand.DONATE_READY else '')
        # The way home is the last thing a person sees, and it was a line
        # of small text they had to hunt for. It is the brightest thing on
        # the screen now, because after writing your testimony the archive
        # should feel like it is holding a door open for you.
        + '<p class="center gohome"><a class="aura" href="index.html">'
        'RETURN TO THE LIGHTS</a></p>'
        '</div>')
    parts.append(
        '<div id="fallback">'
        '<h2>The Record could not be reached. Nothing was lost</h2>'
        '<p>Your testimony is safe on this page. Download it now, and submit '
        'it again when the Record is back online. The Record sends and '
        'receives no email; nothing leaves this page but the file you save.</p>'
        '<p><a id="download" class="finish" href="#">DOWNLOAD MY TESTIMONY</a></p>'
        '<h2>Your continuity key, shown once, only here</h2>'
        '<p>The file above carries only the key\'s fingerprint. The key '
        'itself is below, on your screen only. Save it before you leave '
        'this page: it is required for your Second and Final Testimonies '
        'and can never be recovered.</p>'
        '<pre class="key" id="fkey"></pre>'
        '<div id="flegacywrap" class="hidden">'
        '<h2>Your Legacy Key, shown once, only here</h2>'
        '<p>You sealed words: these six words are the key that opens them '
        'when you are gone. Save them with the same care.</p>'
        '<pre class="key" id="flegacy"></pre></div>'
        '<pre id="fjson"></pre>'
        '</div>')
    body = "\n".join(parts)
    js = (WRITE_JS_TEMPLATE
          .replace("__CAP__", str(cap))
          .replace("__NAME_CAP__", str(NAME_CAP))
          .replace("__MIN_ANSWER__", str(ANSWER_MIN))
          .replace("__LEGACY_WORDS__", json_for_script(LEGACY_WORDS))
          .replace("__LEGACY_COUNT__", str(LEGACY_WORD_COUNT))
          .replace("__LEGACY_ITERS__", str(LEGACY_PBKDF2_ITERS))
          )
    html_out = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
                '<title>My First Testimony · ' + brand.BRAND + '</title>\n'
                '<style>' + WRITE_CSS + '</style>\n</head>\n<body>\n' + body + '\n'
                + MODAL_JS + '\n' + js + '\n</body>\n</html>')
    slug = brand.BRAND.lower().replace(' ', '-')
    return (html_out.replace('__BRAND__', brand.BRAND)
                    .replace('__BRANDSLUG__', slug))
