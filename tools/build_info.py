"""Render the reading room: info.<domain> -> info-site/

Usage: python tools/build_info.py

The main site is the experience — the lights, the records, joining.
This subdomain is where everything is explained and every official
document lives: how it works, what makes a testimony permanent, the
FAQ, and the full text of the governing documents. Standard library
only, plain HTML, readable with CSS off, no worker, no API — the
reading room has no moving parts at all.
"""
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ahlib
import brand  # public display name + domain (the one place they live)
import build_site  # shared drill stamping (_finalize) + mode discipline
import csp

OUT = ahlib.ROOT / "info-site"
MAIN = "https://" + brand.DOMAIN

CSS = """
body{max-width:44em;margin:2em auto;padding:0 1em 4em;font-family:Georgia,'Times New Roman',serif;line-height:1.65;color:#1a1a1a;background:#fdfcf9}
a{color:#1a1a1a}
h1{font-weight:normal;letter-spacing:.14em;font-size:1.3em}
h2{font-weight:normal;line-height:1.25;margin-top:2.2em;padding-top:1.2em;border-top:1px solid #e0dcd0}
h3{font-weight:normal;font-style:italic;margin-bottom:.3em}
/* A contents list, not a paragraph of links. Nine entries separated by
   middots ran together into a grey wall that nobody reads: the eye had
   no line to follow and no place to rest. Given its own lines inside a
   quiet panel, it can be scanned in a second. Two columns where there
   is room, one on a phone, because a narrow column of two-word links
   is worse than a list. */
nav.toc{font-size:.95em;margin:1.2em 0 2.6em;padding:1.05em 1.3em;background:#f7f5ee;border:1px solid #e6e1d3;border-radius:2px}
nav.toc ul{list-style:none;margin:0;padding:0;columns:2;column-gap:2.2em}
nav.toc li{margin:.34em 0;break-inside:avoid}
nav.toc a{color:#3a3428;text-decoration:none;border-bottom:1px solid #ded8c8}
nav.toc a:hover{border-bottom-color:#8a8264;color:#1a1a1a}
@media(max-width:34em){nav.toc ul{columns:1}}
.meta{color:#555;font-size:.9em}
pre.doc{white-space:pre-wrap;font-family:inherit;font-size:.97em}
dt{font-style:italic;margin-top:1.4em}
dd{margin:.3em 0 0 0}
footer{margin-top:3em;padding-top:1em;border-top:1px solid #ccc;font-size:.85em;color:#555}
.lights{display:inline-block;border:1px solid #8a8264;background:#06070a;color:#e8e3d6;letter-spacing:.12em;padding:.7em 1.6em;border-radius:2px;text-decoration:none;font-size:.9em}
ul.docs li{margin:.6em 0}
p.golights{margin-top:3em}
/* The introduction, offered rather than imposed: a link on a reading
   page, opening over it, closable at any second. The Record's own front
   door plays this film once a month; here it plays whenever it is
   asked, because someone showing it to a friend should never have to
   wait for a calendar. */
p.watch{margin:.8em 0 1.1em}
a.watch{display:inline-block;border:1px solid #8a8264;background:#06070a;color:#e8e3d6;letter-spacing:.1em;padding:.6em 1.3em;border-radius:2px;text-decoration:none;font-size:.85em}
a.watch:hover{background:#0d0f14}
.filmwrap{position:fixed;inset:0;z-index:50;background:#000;display:none}
.filmwrap.on{display:block}
.filmwrap video{width:100%;height:100%;object-fit:contain;background:#000}
button.skipfilm{position:absolute;right:14px;bottom:14px;background:rgba(6,7,10,.6);border:1px solid #55503f;color:#c9c4b8;font-family:inherit;font-size:.8em;letter-spacing:.12em;padding:.5em 1.1em;border-radius:3px;cursor:pointer}
button.skipfilm:hover{border-color:#c9c4b8;color:#e8e3d6}
"""


def esc(s):
    return html.escape(str(s), quote=True)


def page(title, description, body):
    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{esc(description)}">
<title>{esc(title)}</title>
<style>{CSS}</style>
</head>
<body>
{body}
<footer>{build_site.FOOTER_TAGLINE}<br>
<a href="index.html">← back to the reading room</a></footer>
</body>
</html>"""
    return html_out.replace("__BRAND__", brand.BRAND)


def doc_page(src, title, description):
    text = (ahlib.ROOT / src).read_text(encoding="utf-8")
    body = (f'<h1>{esc(title)}</h1>\n'
            f'<p class="meta">The authoritative text lives in the public '
            f'repository, where it is protected by cryptographic '
            f'verification. This page is a reading copy.</p>\n'
            f'<pre class="doc">{esc(text)}</pre>')
    return page(f"{title} · __BRAND__", description, body)


INDEX_BODY = """
<h1>__BRAND__ · THE READING ROOM</h1>
<p>The Record itself lives at <a href="MAIN_URL">allhumans.world</a>:
a dark sky of lights, one for every human who chose to stamp their
passage on Earth. This page explains how it works, what keeps its
promises, and where every official document lives.</p>

<p class="watch"><a class="watch" href="#" id="watchfilm">▶ WATCH THE INTRODUCTION</a></p>

<div class="filmwrap" id="filmwrap">
<video id="introv" src="intro-v1.mp4" preload="none" playsinline></video>
<button class="skipfilm" id="skipfilm">SKIP &#8594;</button>
</div>

<nav class="toc">
<ul>
<li><a href="truth.html">how to verify the truth</a></li>
<li><a href="#what">what is __BRAND__?</a></li>
<li><a href="#joining">how joining works</a></li>
<li><a href="#key">the keys and invitation</a></li>
<li><a href="#forever">what makes a testimony stamped forever?</a></li>
<li><a href="#withdrawal">withdrawal</a></li>
<li><a href="#stewardship">stewardship</a></li>
<li><a href="#documents">the documents</a></li>
<li><a href="#faq">FAQ</a></li>
</ul>
</nav>

<h2 id="what">What is __BRAND__?</h2>
<p>__BRAND__ was created to preserve humanity's testimony for those who
come after us.</p>
<p>Every human experiences life differently. Some find joy, some
grief, some purpose, some doubt. Most of those experiences disappear
with them.</p>
<p>This institution exists so they don't have to.</p>
<p>__BRAND__ is a permanent archive of human testimony: a place where
every person may leave, in their own words, what it was like to live
their life. Not what history says about them, not what others
remember, but what they themselves chose to leave behind.</p>
<p>It is built on a simple belief:</p>
<p class="belief"><em>Only humanity can tell the story of what it was
like to be human.</em></p>
<p>Every testimony is preserved equally. There are no followers, no
popularity, no advertisements, no recommendation algorithm, and no
rankings. The first testimony and the millionth are treated exactly
the same.</p>
<p>This is not social media.</p>
<p>It is humanity speaking for itself.</p>

<h2 id="joining">How joining works</h2>
<p>You read the principles and accept them, provide an email address
where The Record can answer you, then you can write your First
Testimony: ten
fixed questions, each answer limited to 400 characters. Only your name
is mandatory, along with any two questions of your choice. The
questions never change; that is what makes The Record a comparable
record of humanity across generations.</p>
<p>Your submission is then read by a person and verified according to
the standards of the founding era before a Number is assigned. Numbers
are given in sequence, never chosen, never reused. Your light is added
to the sky, and your page appears at allhumans.world/&lt;your number&gt;.</p>
<p>This is deliberately unhurried. Slow is part of the mission.</p>
<p>At least one year must pass between testimonies. Reflection takes
time; the question of what has changed in you is only honest once life
itself has changed.</p>

<h2 id="key">The Keys &amp; Invitation</h2>
<p><strong>The continuity key</strong> is created in your browser and
shown to you once. It is your only proof of return: your Second and
Final Testimonies, and withdrawal, all require it. If it is lost, no
one can replace it.</p>
<p><strong>The Legacy Key</strong> is six plain words, given to you
only if you seal an answer. You pass them to someone you trust; one
day that person brings the words back, reports your death, and your
sealed answers open. If the key is never used, your seals open by
themselves one hundred years after you enrolled.</p>
<p><strong>An invitation</strong> is a one-time code an enrolled human
can create for someone they know in person: they prove their key, give
their word that you are a real living human, and hand it to you to
enter with your testimony. Who invited whom is held privately by
The Record, one number behind another, and is never published; the
invitation carries no number, so neither of you is revealed to the
other or to anyone.</p>

<h2 id="forever">What makes my testimony stamped forever?</h2>
<p>Not a promise, a structure. Five layers, each one checkable by
anyone:</p>
<p><strong>1. A fingerprint of your words.</strong> The moment your
testimony is entered, its exact text is hashed (SHA-256). Change one
letter and the fingerprint no longer matches. Your record carries
that fingerprint forever, so any copy of your testimony, anywhere,
can be proven word-for-word authentic, or exposed as altered.</p>
<p><strong>2. A chained public log.</strong> Every event in
The Record's life, every enrollment, every testimony, every
withdrawal, is a link in a hash chain, where each entry contains
the fingerprint of the one before it. Rewriting history would break
every link that follows. The log is public and contains only
fingerprints, never words, so anyone can verify the chain without
the archive itself.</p>
<p><strong>3. Independent verification.</strong> The verification
tools are published with the archive's public repository, are
deliberately simple, and are specified precisely enough to be
rewritten in any programming language, in any decade. You do not
have to trust __BRAND__; you can check it.</p>
<p><strong>4. A timestamp beyond anyone's control.</strong> The
chain's newest fingerprint, which stands for everything before it,
is regularly frozen into a public checkpoint and stamped into
Bitcoin's timeline through OpenTimestamps: a dated attestation
witnessed by thousands of independent computers that no one, not a
hacker, not a government, not __BRAND__ itself, can forge or
backdate. If anyone ever rewrote the archive's history, their copy
would fail against these public anchors. This protects your words
even from their own custodian.</p>
<p><strong>5. Many copies, formally kept.</strong> The canonical
archive is plain text in open formats, no database, no framework,
nothing whose disappearance could hurt it, and complete snapshots
are deposited with trusted preservation institutions under formal
agreements. The entire archive at a hundred million testimonies fits
on a single hard drive.</p>
<p>We cannot honestly promise "forever." We promise that every
reasonable technical, legal and institutional effort will be made,
and that trust here is built on verification, not on promises.</p>

<h2 id="withdrawal">Withdrawal</h2>
<p>Your words always belong to you. You may withdraw any testimony
with your continuity key: the words are removed from the canonical
archive and from cooperating preservation partners, the page becomes
a marker recording that a testimony once existed and was withdrawn,
and the fingerprint remains: proof of what was once said, without
saying it. Your number stays yours; a withdrawn testimony's
slot stays spent; and copies made by others before withdrawal are
beyond anyone's recall; permanence and honesty cut both ways.</p>

<h2 id="stewardship">Stewardship: what it costs, and who pays</h2>
<p>__BRAND__ is free, for every human, always. There is no fee to
enter The Record, no fee to be read, and there will never be
advertising; the Constitution forbids turning the archive into a
market for attention.</p>
<p>The institution is kept alive by <strong>donations</strong>,
through <a href="__DONATE_URL__"
rel="noopener">Open Collective</a>, chosen because its ledger is
public: every donation received and every dollar spent is visible to
anyone, the same way The Record's own log is. An institution that
asks for trust through verification should publish its books the
same way.</p>
<p><strong>A donation buys nothing.</strong> No donor names on
records, no priority in review, no markings, no tiers. A donation
never touches the archive in any way. Every human is equal within
The Record, including the generous ones.</p>

<h2 id="documents">The documents</h2>
<p>The institution is governed in writing. Reading copies live here;
the authoritative texts live in the public repository, protected by
the verification described above.</p>
<ul class="docs">
<li><a href="mission.html">The Mission</a>: why __BRAND__ exists.</li>
<li><a href="constitution.html">The Constitution</a>: the immutable
rules (Version 1, ratified 2026-07-05). Cannot be amended.</li>
<li><a href="policy.html">The Policy</a>: the deliberately changeable
rules: eligibility, spacing, verification standards, the
crisis-response protocol, distribution.</li>
<li><a href="questionnaire.html">The Questionnaire</a>: the fixed
questions every testimony answers (Version 1, ratified 2026-07-05).</li>
<li><a href="architecture.html">The Architecture</a>: how the archive
is built to outlive its builders.</li>
<li><a href="licensing.html">Licensing</a>: who owns what: you own
your words; __BRAND__ is the steward.</li>
<li><a href="MAIN_URL/verify.html">Verify the archive</a>: the live
fingerprint of The Record's event log, updated with every
enrollment.</li>
</ul>

<h2 id="faq">FAQ</h2>
<dl>
<dt>Who can join?</dt>
<dd>Any human at least 20 years old. The Record preserves
considered adult testimony, not childhood snapshots.</dd>

<dt>Can I share my invitation publicly?</dt>
<dd>You can, but you should not. An invitation is your word about one
person you know in real life; a stranger is someone you cannot give
that word for. It works once, for whoever grabs it first, and your
word stands behind that person forever. If you want to bring
strangers here, share The Record itself: its door is open to every
human, and every submission is read by a person either way.</dd>

<dt>What does it cost?</dt>
<dd>Nothing. __BRAND__ is free for every human, always, and carries
no advertising. It is kept alive by donations with a
<a href="#stewardship">public ledger</a>, and a donation buys
nothing: no marks, no priority, no exceptions.</dd>

<dt>Do I have to use my real name?</dt>
<dd>We encourage the name by which you are genuinely known, but
anonymity is a first-class mode. A record may be published under its
number and a chosen name only, and your location may be as coarse as
"on Earth."</dd>

<dt>Can I edit my testimony after it is published?</dt>
<dd>Never. A testimony, once entered, is never modified; that is
what makes every record trustworthy. The way your words change is
the way a life changes: your Second and Final Testimonies, at least
a year apart, answering the same questions from further down the
road.</dd>

<dt>Why only three testimonies?</dt>
<dd>Three is fixed by the Constitution and will not change. The
limit is the craft: it makes each sitting a distillation rather than
a feed, and it makes every human's record comparable to every
other's: first light, middle passage, last word.</dd>

<dt>Why can't I choose my number?</dt>
<dd>Numbers are assigned by the system in sequence, never chosen,
never changed, never reused. A human decides <em>when</em> someone
enters; the system decides <em>what number</em> they receive. That
removes ego from the numbering forever, and makes the order of the
archive provable rather than stated.</dd>

<dt>Who reads my testimony before it appears?</dt>
<dd>A person reads every testimony, in this era. The review protects the
Record from machines and spam, never from honesty: no testimony is
refused for being dark or sorrowful, no report is ever made to
anyone, and no flag of any kind is stored on your record.</dd>

<dt>What does "sealed until my death" mean?</dt>
<dd>Any individual answer can be sealed when you write it. A sealed
answer is not shown on your page. It opens when someone you trust
brings your Legacy Key and reports your death, or by itself one
hundred years after you enrolled. It is a way to tell the future
something you are not ready to tell the present.</dd>

<dt>What if I lose my continuity key?</dt>
<dd>It cannot be recovered or reissued, not by us, not by anyone;
that is precisely what makes it proof. Your existing testimony
stays. Without the key you cannot add your remaining testimonies;
withdrawal remains possible through a founder-verified process,
recorded permanently in the public log.</dd>

<dt>Can someone find my testimony by searching my name?</dt>
<dd>No. There is no search. Someone finds your record only if you
share your number with them, or if your light, among all the
others, happens to be the one they touch.</dd>

<dt>What happens to my email address?</dt>
<dd>It never appears in the public record and is never part of the
archive. It is kept privately as part of your agreement with
__BRAND__ and used only to answer you: your review outcome, your
number.</dd>

<dt>What happens when I die?</dt>
<dd>Your record is memorialized: it remains in The Record exactly
as you left it, marked as memorialized, and any answers you sealed
are revealed. Memorialization is a status of a record; the archive
exists for the living and the dead alike.</dd>

<dt>How do I know this will still exist in a hundred years?</dt>
<dd>See <a href="#forever">what makes a testimony stamped
forever</a>; the honest answer is structure plus stewardship, not
promises. Plain text, open formats, public verification, and formal
deposits with preservation institutions are the four layers doing
that work.</dd>
</dl>

<p class="golights"><a class="lights" href="MAIN_URL">GO TO THE LIGHTS</a></p>

<script>
(function(){
  var link = document.getElementById('watchfilm');
  var wrap = document.getElementById('filmwrap');
  var v = document.getElementById('introv');
  var skip = document.getElementById('skipfilm');
  if (!link || !wrap || !v) return;
  function close(){
    try { v.pause(); v.currentTime = 0; } catch(e) {}
    wrap.classList.remove('on');
    document.removeEventListener('keydown', onKey, true);
  }
  function onKey(e){ if (e.key === 'Escape') { e.preventDefault(); close(); } }
  link.addEventListener('click', function(e){
    e.preventDefault();
    // The click IS the gesture a browser requires before sound may play,
    // which is why this opens from a link rather than starting by itself.
    // preload is 'none' until then: nobody downloads twenty-three
    // megabytes for a page they came to read.
    wrap.classList.add('on');
    document.addEventListener('keydown', onKey, true);
    var p = v.play();
    if (p && p.catch) p.catch(close);
  });
  v.addEventListener('ended', close);
  v.addEventListener('error', close);
  if (skip) skip.addEventListener('click', close);
})();
</script>
"""


TRUTH_BODY = """
<h1>How to verify the truth</h1>

<p class="meta">Written for someone with no technical background. If you
would rather see the commands, they are at the bottom.</p>

<p>__BRAND__ makes some large promises. Your words will never be
edited. Your number will never be given to anyone else. Nothing will be
quietly deleted or rewritten later. Anyone can say those things. This
page is about why you do not have to take our word for them.</p>

<h2>The short version</h2>

<p>Every promise __BRAND__ makes can be checked by a stranger, using a
copy of the archive that we do not control and cannot edit. If we ever
broke one of those promises, even by a single letter, even years from
now, the check would fail publicly, on every copy in the world. Not
because we confessed, but because the mathematics stopped agreeing.</p>

<h2>How that works, without the jargon</h2>

<h3>1. Every testimony leaves a mark that only it could leave</h3>

<p>When someone writes a testimony, the Record takes a kind of
fingerprint of it. Think of an ink stain: those exact words, and no
others, could have made that exact shape.</p>

<p>Anyone can look at the stain. Nobody can read the words back out of
it, because it only works in one direction. But bring the true words
back and they fit it perfectly. So the stain proves the words are
unchanged without ever revealing them.</p>

<h3>2. Every mark is tied to the one before it</h3>

<p>Those fingerprints are kept in a single list, and each entry is tied
to the entry above it. Change one, whether a name, a comma or a date,
and every entry below it stops matching. You cannot quietly correct one line in
the middle. The damage shows immediately, and it shows to everyone, not
only to us.</p>

<h3>3. So we cannot simply rewrite the whole list</h3>

<p>That is the obvious next question, and it is the right one. If we
control the list, what stops us rebuilding the entire thing to hide
something?</p>

<p>This: at regular moments we take a fingerprint of the whole list and
place it in the <strong>Bitcoin</strong> blockchain, a public ledger
spread across the world that nobody can edit, least of all us. It is
the closest thing the internet has to carving a date into stone in a
public square.</p>

<p>That fixes what the Record contained at that moment. If we rewrote
history afterwards, the rewritten version would no longer match the
stone. Anyone checking would see it. <strong>We cannot backdate.</strong></p>

<h3>4. The instructions are public, so someone else can check our work</h3>

<p>The whole method is published openly: the code, the rules, and the
list of fingerprints. Not a description of it; the actual thing. Anyone can
take a copy and run the check themselves, on their own computer,
without asking us and without us knowing.</p>

<p>That is the part that matters. A promise you have to trust is a
promise. A promise anyone can test is something better.</p>

<h2>What this does <em>not</em> prove</h2>

<p>We would rather say this plainly than let you discover it later.</p>

<ul>
<li><strong>It does not prove anyone told the truth about their own
life.</strong> The Record proves that words were not altered after they
were written. Whether a person was honest with the future is between
them and the future.</li>
<li><strong>It does not make the archive impossible to destroy.</strong>
Nothing is. It makes tampering <em>detectable</em>, and it makes copies
easy to keep, which is how things actually survive centuries.</li>
<li><strong>It does not mean nothing can go wrong.</strong> It means
that if something does, it cannot be hidden.</li>
</ul>

<h2>You do not have to check this yourself</h2>

<p>Almost nobody will, and that is fine. The protection does not come
from every reader running a check. It comes from the fact that
<em>anyone can</em>: a journalist, a researcher, a suspicious
stranger, someone in eighty years who has never heard of us. An
institution that can be checked at any moment by anyone tends to behave
as though it is being checked.</p>

<p>You are trusting mathematics and daylight, rather than our good
intentions. That is the whole idea.</p>

<h2>If you would like to check it yourself</h2>

<p>You will need a computer with Python on it. There is nothing to
install and no account to make. Everything lives in
<a href="https://github.com/theadultproject1/the-human-record">the
public repository</a>, on GitHub, which is simply a website where code
and files are published openly so anyone can copy them.</p>

<p>Open a terminal and run these three lines. The first copies the
whole archive to your computer; the last one checks it.</p>

<pre class="doc">git clone https://github.com/theadultproject1/the-human-record
cd the-human-record
python tools/verify.py</pre>

<p>If it prints <strong>OK</strong>, everything on this page held at the
moment you ran it: nothing altered, no number reused, the founding
documents unchanged, every withdrawal recorded. If it prints anything
else, you have found something, and we would want to know. There is a
private way to tell us, described in that repository.</p>

<p class="golights"><a class="lights" href="MAIN_URL">GO TO THE LIGHTS</a></p>
"""


def main():
    mode = ahlib.resolve_mode()
    import shutil
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()

    # Same header discipline as the main site (tools/csp.py): simple
    # headers on the catch-all, each page's hashed CSP on its own paths.
    csp_rules = []

    def put(name, html_text):
        html_text = build_site._finalize(html_text, mode)
        broken = ahlib.js_syntax_errors(html_text, name)
        if broken:
            raise SystemExit(
                "build refused: a page's JavaScript does not parse, so the\n"
                "browser would run none of it:\n  " + "\n  ".join(broken))
        (OUT / name).write_text(html_text, encoding="utf-8")
        policy = csp.page_csp(html_text)
        served = [f"/{name}", f"/{name[:-len('.html')]}"]
        if name == "index.html":
            served.append("/")
        for s in served:
            csp_rules.append((s, policy))

    put("index.html",
        page("__BRAND__ · how it works, and what makes a testimony permanent",
             "How __BRAND__ works: joining, the continuity key, "
             "what makes a testimony stamped forever, withdrawal, the official "
             "documents, and the FAQ.",
             INDEX_BODY.replace("MAIN_URL", MAIN).replace("allhumans.world", brand.DOMAIN).replace("__DONATE_URL__", brand.DONATE_URL)))

    put("truth.html",
        page("How to verify the truth · __BRAND__",
             "Why you do not have to take __BRAND__ at its word: the "
             "fingerprints, the chain, the Bitcoin timestamp, and the "
             "public code, explained without jargon.",
             TRUTH_BODY.replace("MAIN_URL", MAIN)))

    # The film, beside the page that explains why any of it can be
    # trusted. Copied rather than linked across from the main site: the
    # Reading Room's own Content-Security-Policy allows media only from
    # itself, and loosening a security header is a worse price to pay
    # than a duplicated file.
    film = ahlib.ROOT / "site-assets" / "intro-v1.mp4"
    if film.exists():
        shutil.copyfile(film, OUT / "intro-v1.mp4")

    docs = [
        ("MISSION.md", "mission.html", "The Mission",
         "Why __BRAND__ exists: a permanent archive of human testimony."),
        ("CONSTITUTION.md", "constitution.html", "The Constitution",
         "The immutable rules of __BRAND__ (Version 1, ratified 2026-07-05)."),
        ("POLICY.md", "policy.html", "The Policy",
         "The deliberately changeable rules of __BRAND__."),
        ("PRIVACY.md", "privacy.html", "The Privacy Policy",
         "What The Record holds, what it never holds, and what your email is used for."),
        ("questions/v1.md", "questionnaire.html", "The Questionnaire",
         "The fixed questions every __BRAND__ testimony answers (Version 1)."),
        ("ARCHITECTURE.md", "architecture.html", "The Architecture",
         "How the __BRAND__ archive is built to outlive its builders."),
        ("LICENSING.md", "licensing.html", "Licensing",
         "Who owns what in __BRAND__: authors own their words."),
    ]
    for src, out_name, title, desc in docs:
        put(out_name, doc_page(src, title, desc))

    lines = [
        "/*",
        "  Cache-Control: no-cache",
        "  Referrer-Policy: no-referrer",
        "  X-Content-Type-Options: nosniff",
        "  X-Frame-Options: DENY",
        "",
    ]
    for served, policy in csp_rules:
        lines.append(served)
        lines.append(f"  Content-Security-Policy: {policy}")
        lines.append("")
    (OUT / "_headers").write_text("\n".join(lines), encoding="utf-8", newline="\n")

    if mode == "drill":
        (OUT / "robots.txt").write_text(
            "User-agent: *\nDisallow: /\n", encoding="utf-8", newline="\n")

    # Counted from what was actually written, not from a sum kept by
    # hand: the hand-kept one was already wrong the moment a page was
    # added, and a build that misreports itself is a small lie told on
    # every run.
    print(f"reading room built: {len(list(OUT.glob('*.html')))} page(s) "
          f"-> info-site/")


if __name__ == "__main__":
    main()
