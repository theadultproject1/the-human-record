"""Advisory screen for pending submissions (operational scratch).

Two jobs, both ADVISORY — this tool never assigns a number, never
rejects, never writes anywhere. It only raises signals for a human to
read in context. The founder's review is the deciding authority.

  1. Integrity — catch *automated / spam* submissions (the kind that
     would fraudulently consume a permanent Registry number): duplicates,
     links, spam phrasing, encoding junk, keyboard mash.

  2. Moderation — surface content that may harm *other people or the
     archive*, for a human to judge: possible slurs / hateful terms (from
     an operator-maintained wordlist), threats of violence toward others,
     and apparent full names of other people (POLICY.md asks that others
     be named by first name only). If the optional `better-profanity`
     package is installed, a strong-language advisory is added too.

Principles:
  * It targets automation and harm-to-others — NOT the author's feelings.
    It never flags a testimony for being sad, dark, grieving, regretful,
    short, foreign, or "AI-sounding". Author distress is the domain of the
    crisis-response protocol (POLICY.md), which offers care, not flags.
  * Every signal is advisory and reversible by a human. A flagged term may
    be quoted, reclaimed, or the very harm the author survived; a full name
    may be a public figure or a place; a "threat" may be past grief. Read
    before acting.
  * Coverage is partial and English-leaning (esp. slurs, threats, and
    Latin-script names). Missing something is expected; auto-blocking on it
    is not. Extend the wordlist and patterns for the languages you receive.
  * Pure standard library, forever (see ahlib.py).

An optional external-model advisor can be added without a dependency —
see llm_advisor(). Off by default; advisory; never archived.

CLI:  python tools/botscreen.py path/to/sitting.json [more.json ...]
"""
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ahlib

# Optional, advisory-only profanity detector. The durable core is stdlib-only
# (see ahlib.py); this operational screen may use an extra library IF the
# operator installs it, and works fine without it. Enable with:
#     pip install better-profanity
try:
    from better_profanity import profanity as _profanity
    _profanity.load_censor_words()
    _HAS_PROFANITY_LIB = True
except Exception:
    _HAS_PROFANITY_LIB = False

INFO, WATCH, FLAG = "info", "watch", "flag"
_RANK = {INFO: 0, WATCH: 1, FLAG: 2}

WORDLIST = Path(__file__).resolve().parent / "wordlists" / "flagged_terms.txt"

_URL_RE = re.compile(r"(https?://|www\.)\S+", re.IGNORECASE)
_BARE_DOMAIN_RE = re.compile(r"\b[a-z0-9-]+\.(com|net|org|io|ru|xyz|top|shop|biz|info)\b", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_LONG_DIGITS_RE = re.compile(r"\d{7,}")
_CRYPTO_RE = re.compile(r"\b(0x[a-f0-9]{16,}|bc1[a-z0-9]{20,}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b")
_SPAM_TOKENS = [
    "buy now", "free money", "click here", "limited offer", "act now",
    "make money", "work from home", "crypto", "forex", "casino", "viagra",
    "subscribe", "promo code", "discount", "telegram", "whatsapp me",
    "investment opportunity", "guaranteed", "% off",
]

# --- Moderation patterns (advisory, English-leaning) ---------------------
_VIOLENCE = (r"kill|murder|hurt|harm|shoot|stab|rape|beat|strangle|bomb|"
             r"attack|assault|slaughter|hunt down|track down")
# verb directly on a NON-reflexive target (self-harm targets are excluded on
# purpose — those belong to the crisis-response protocol, not moderation):
_THREAT_TARGET_RE = re.compile(
    r"\b(?:" + _VIOLENCE + r")\s+(?:you|him|her|them|u|y'?all|everyone|people)\b",
    re.IGNORECASE)
# first-person intent to commit violence, unless it is reflexive (…myself):
_THREAT_INTENT_RE = re.compile(
    r"\b(?:i\s*(?:will|'ll|am going to|'m going to|m going to|'m gonna|m gonna|gonna))\s+"
    r"(?:\w+\s+){0,3}?(?:" + _VIOLENCE + r")\b(?!\s+(?:myself|ourselves))",
    re.IGNORECASE)
# two consecutive Latin-script Title-Case words = a likely full name:
_NAME_RE = re.compile(r"\b([A-Z][a-z]{1,})\s+([A-Z][a-z]{1,})\b")
_NAME_STOP = {
    # honorifics / pronouny / articles
    "i", "a", "an", "the", "my", "mr", "mrs", "ms", "miss", "dr", "sir",
    "saint", "st", "lord", "god", "jesus", "christ", "allah",
    # family
    "mom", "mum", "mama", "dad", "papa", "mother", "father", "grandma",
    "grandpa", "granny", "nana", "uncle", "aunt", "auntie", "brother",
    "sister", "cousin", "son", "daughter", "grandmother", "grandfather",
    # place prefixes / common
    "new", "los", "san", "santa", "saint", "north", "south", "east", "west",
    "lake", "mount", "fort", "port", "cape", "united", "great",
    # calendar
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
    "sunday", "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    "christmas", "easter", "thanksgiving",
    # misc frequent
    "earth", "heaven", "hell", "world", "day", "one",
}


def _load_flagged_terms():
    terms = []
    try:
        for line in WORDLIST.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                terms.append(line.lower())
    except FileNotFoundError:
        pass
    return terms


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).strip().lower())


def _answers_texts(answers: dict) -> dict:
    out = {}
    for qid, a in (answers or {}).items():
        if isinstance(a, dict) and isinstance(a.get("text"), str):
            out[qid] = a["text"]
    return out


def _longest_char_run(s: str) -> int:
    best = run = 0
    prev = None
    for ch in s:
        run = run + 1 if ch == prev else 1
        prev = ch
        best = max(best, run)
    return best


def _longest_token_repeat(s: str) -> int:
    toks = s.split()
    best = run = 0
    prev = None
    for t in toks:
        run = run + 1 if t == prev and len(t) >= 2 else 1
        prev = t
        best = max(best, run)
    return best


def _control_char_count(s: str) -> int:
    n = 0
    for ch in s:
        if ch in "\t\n\r":
            continue
        cat = unicodedata.category(ch)
        if cat.startswith("C") or ch == "�":
            n += 1
    return n


def screen(answers: dict, chosen_name=None, existing_hashes=None, peers=None) -> dict:
    """Return an advisory report: {verdict, signals:[{code,severity,message}]}."""
    signals = []

    def sig(code, severity, message):
        signals.append({"code": code, "severity": severity, "message": message})

    texts = _answers_texts(answers)
    name_text = {"__name__": chosen_name} if isinstance(chosen_name, str) and chosen_name.strip() else {}
    all_fields = {**texts, **name_text}
    blob = " ".join(all_fields.values())
    low = blob.lower()

    # 1) Exact duplicate of an already-enrolled testimony.
    if existing_hashes:
        try:
            h = ahlib.hash_value(answers)
        except Exception:
            h = None
        if h and h in existing_hashes:
            sig("duplicate_enrolled", FLAG,
                "Content is byte-identical to a testimony already in the archive.")

    # 2) Duplicate of another pending submission (batch/bot pattern).
    if peers:
        mine = {q: _norm(t) for q, t in texts.items()}
        for peer in peers:
            ptexts = {q: _norm(t) for q, t in _answers_texts(peer).items()}
            shared = [q for q in mine if q in ptexts and mine[q] and mine[q] == ptexts[q]]
            if len(shared) >= 3:
                sig("duplicate_pending", FLAG,
                    f"Shares {len(shared)} identical answers with another pending submission "
                    f"(possible batch submission).")
                break

    # 3) Same text pasted across several different questions.
    seen = {}
    for qid, t in texts.items():
        nrm = _norm(t)
        if len(nrm) >= 8:
            seen.setdefault(nrm, []).append(qid)
    repeated = [qs for qs in seen.values() if len(qs) >= 3]
    if repeated:
        sig("cross_field_repetition", FLAG,
            "The same text is repeated across " + ", ".join(sorted(repeated[0])) + ".")
    elif any(len(qs) == 2 for qs in seen.values()):
        pair = next(qs for qs in seen.values() if len(qs) == 2)
        sig("cross_field_repetition", WATCH,
            "The same text appears in " + " and ".join(sorted(pair)) + ".")

    # 4) Links, contact details, payment identifiers — rare in testimony.
    url_hits = len(_URL_RE.findall(blob)) + len(_BARE_DOMAIN_RE.findall(blob))
    email_hits = len(_EMAIL_RE.findall(blob))
    crypto_hits = len(_CRYPTO_RE.findall(blob))
    phone_hits = len(_LONG_DIGITS_RE.findall(blob))
    if url_hits or crypto_hits:
        sev = FLAG if (url_hits + crypto_hits) >= 2 else WATCH
        sig("links", sev,
            f"Contains {url_hits} link(s), {crypto_hits} wallet-like string(s) — "
            f"uncommon in testimony, common in spam.")
    if email_hits or phone_hits:
        sig("contact_details", WATCH,
            f"Contains {email_hits} email(s) and {phone_hits} long digit-run(s) "
            f"(a testimony rarely needs contact details).")

    # 5) Promotional / spam phrasing.
    hits = [tok for tok in _SPAM_TOKENS if tok in low]
    if hits:
        sig("spam_phrasing", FLAG if len(hits) >= 2 else WATCH,
            "Promotional phrasing: " + ", ".join(f'“{h}”' for h in hits[:5]) + ".")

    # 6) Control characters / encoding junk (structural, script-neutral).
    ctrl = sum(_control_char_count(t) for t in all_fields.values())
    if ctrl:
        sig("encoding_junk", FLAG,
            f"{ctrl} control/replacement character(s) — often machine-generated paste.")

    # 7) Degenerate text: only clearly mechanical patterns, never language.
    for qid, t in texts.items():
        nospace = "".join(t.split())
        if len(nospace) >= 12 and _longest_char_run(t) >= 10:
            sig("char_mash", FLAG, f"{qid}: a run of >=10 identical characters (keyboard mash).")
        elif _longest_token_repeat(t) >= 5:
            sig("token_mash", FLAG, f"{qid}: one token repeated >=5 times.")
        elif len(nospace) >= 20 and len(set(nospace.lower())) <= 3:
            sig("low_diversity", WATCH, f"{qid}: very few distinct characters for its length.")

    # 8) MODERATION — possible slur / hateful term (operator wordlist).
    terms = _load_flagged_terms()
    found = [term for term in terms if re.search(r"\b" + re.escape(term) + r"\b", low)]
    if found:
        sig("hateful_term", FLAG,
            "Possible slur / hateful term for human review (may be quoted, reclaimed, "
            "or the harm the author is describing): " + ", ".join(f'“{t}”' for t in found[:5]) + ".")

    # 8b) MODERATION (optional) — strong language via better-profanity, if
    #     installed. Advisory WATCH only: raw language can be legitimate in
    #     honest testimony, so it is surfaced for a human, never auto-rejected.
    if _HAS_PROFANITY_LIB:
        prof_qs = [qid for qid, t in texts.items() if _profanity.contains_profanity(t)]
        if prof_qs:
            sig("profanity", WATCH,
                "Strong language / possible profanity (via better-profanity) in "
                + ", ".join(sorted(prof_qs)) + " — advisory; raw language can be honest "
                "testimony, so read before acting.")

    # 9) MODERATION — threat of violence toward another person (not self-harm).
    if _THREAT_TARGET_RE.search(blob) or _THREAT_INTENT_RE.search(blob):
        sig("threat", FLAG,
            "Possible threat of violence toward another person — for human review. "
            "(Self-directed distress is handled by the crisis-response protocol, not here.)")

    # 10) MODERATION — apparent full name of another person (POLICY: first name only).
    name_tokens = set(_norm(chosen_name).split()) if isinstance(chosen_name, str) else set()
    full_names = []
    for qid, t in texts.items():
        if qid == "q_name":
            continue
        for m in _NAME_RE.finditer(t):
            a, b = m.group(1), m.group(2)
            if a.lower() in _NAME_STOP or b.lower() in _NAME_STOP:
                continue
            if a.lower() in name_tokens or b.lower() in name_tokens:
                continue
            full_names.append(m.group(0))
    if full_names:
        uniq = list(dict.fromkeys(full_names))
        sig("full_name", WATCH,
            "Apparent full name(s) of another person — POLICY asks that others be named by "
            "first name only: " + ", ".join(f'“{n}”' for n in uniq[:5]) +
            ". Check before enrolling (may be a public figure or place name).")

    worst = max((_RANK[s["severity"]] for s in signals), default=-1)
    if worst == _RANK[FLAG]:
        verdict = "REVIEW — needs a human look"
    elif worst == _RANK[WATCH]:
        verdict = "Likely fine — minor signals to eyeball"
    else:
        verdict = "No signals"

    return {"verdict": verdict, "signals": signals}


def llm_advisor(text: str):
    """Optional external-model advisory. OFF unless configured; never archived.

    Set ALLHUMANS_LLM_ADVISOR to a command that reads the submission text on
    stdin and prints a short verdict on stdout. Advisory scratch only.
    """
    cmd = os.environ.get("ALLHUMANS_LLM_ADVISOR")
    if not cmd:
        return None
    try:
        r = subprocess.run(cmd, shell=True, input=text, capture_output=True,
                           text=True, timeout=30)
        out = (r.stdout or "").strip()
        return out or None
    except Exception as e:
        return f"(advisor unavailable: {e})"


def load_existing_hashes():
    hashes = set()
    if not ahlib.REGISTRY.exists():
        return hashes
    for d in ahlib.REGISTRY.iterdir():
        vdir = d / "versions"
        if not (d.is_dir() and vdir.exists()):
            continue
        for vf in vdir.glob("*.json"):
            try:
                v = json.loads(vf.read_text(encoding="utf-8"))
                if v.get("content_hash"):
                    hashes.add(v["content_hash"])
            except Exception:
                pass
    return hashes


def _main(argv):
    if not argv:
        print(__doc__)
        return 2
    sittings = []
    for p in argv:
        try:
            sittings.append((p, json.loads(Path(p).read_text(encoding="utf-8"))))
        except Exception as e:
            print(f"{p}: could not read — {e}")
    existing = load_existing_hashes()
    for i, (p, s) in enumerate(sittings):
        peers = [(o.get("answers") or {}) for j, (_, o) in enumerate(sittings) if j != i]
        rep = screen(s.get("answers") or {}, s.get("chosen_name"),
                     existing_hashes=existing, peers=peers)
        print(f"\n{p}")
        print(f"  verdict: {rep['verdict']}")
        for sg in rep["signals"]:
            print(f"    [{sg['severity']}] {sg['code']}: {sg['message']}")
        advice = llm_advisor(" ".join(_answers_texts(s.get('answers') or {}).values()))
        if advice:
            print(f"    [advisor] {advice}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
