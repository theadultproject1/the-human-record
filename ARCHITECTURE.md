# The Human Record — Architecture

*How the archive is built. `MISSION.md` explains why;
`CONSTITUTION.md` sets the rules; this document explains how.
Supersedes the face-mosaic architecture
(`drafts/ARCHITECTURE-facemosaic-2026-07.md`), whose serving and
scaling analysis remains valid where referenced.*

---

## First principle: the archive is the asset

Everything follows from Article VIII. The canonical archive is a
set of plain-text files in open, documented formats. The website,
any database, any API, any search index is a **view generated from
the archive** — regenerable at any time, by anyone, in any decade,
with whatever technology then exists. Data flows one way:
archive → views, never views → archive.

Consequences: the archive format is the only interface that must
survive 100 years, so it gets the most design care and changes
constitutionally slowly. Everything else is replaceable plumbing
and should be as boring as possible.

## The canonical archive format (schema v1)

One directory per Registry number:

```
registry/
  000000002/
    entry.json          # the permanent Registry entry
    versions/
      1.json            # testimony version 1 (immutable once entered)
      2.json            # testimony version 2 (if entered)
      3.json            # testimony version 3 (if entered)
log/
  registry.log.jsonl    # append-only event log (see below)
schema/
  entry.v1.json         # published JSON Schemas
  version.v1.json
  event.v1.json
questions/
  v1.json               # the fixed questionnaire, by stable question id
```

**`entry.json`** — permanent, append-only in spirit (fields are
added by events, never removed): `registry_id`, `enrolled_at`,
`verification` (level + era), `status` (`active` | `memorialized`),
`chosen_name` (optional, may be a pseudonym — anonymity is a
first-class mode), coarse birth era/place if offered.

**`versions/N.json`** — one testimony sitting: `entered_at`,
`answers` keyed by stable question id, each answer carrying a
`visibility` of `public` or `sealed_until_death`; a `status` of
`entered` or `withdrawn`; and a `content_hash` (SHA-256 of the
canonical answer payload) plus signature.

**Withdrawal** replaces the file's `answers` with nothing and sets
`status: withdrawn`, keeping `entered_at`, `withdrawn_at`, and the
original `content_hash`. The hash proves what was once said without
saying it; the words are genuinely gone from every copy. Deposit
agreements with external archives must carry these tombstone
semantics (withdrawn content is replaced in their copies too).

**The three-version rule (Article IV)** is enforced structurally:
the directory admits files `1.json`–`3.json` only, and the event
log makes any tampering evident. A withdrawn version's slot stays
spent.

**Sealed answers** are stored encrypted in the public archive (or
held back from it entirely — decision needed before Human #10, not
before Human #2), and enter the public record only on
memorialization.

## The Registry log

An append-only, hash-chained event log — the institution's spine:

```
ENROLLED | VERSION_ENTERED | VERSION_WITHDRAWN |
MEMORIALIZED | VERIFICATION_CHANGED | STATUS_ANNOTATED
```

Each event: timestamp, registry id, event data, hash of the
previous event, signature. This is Certificate Transparency's
design without a blockchain. It makes the constitutional promises
*provable*, not just stated: numbers never reused, versions never
altered, withdrawals recorded. Root hashes get published externally
(timestamped, multiple venues) so any copy of the archive can be
independently verified forever.

That external publication is implemented as **checkpoints**
(`tools/checkpoint.py` → `checkpoints/`, schema
`schema/checkpoint.v1.json`): each checkpoint freezes the log tip —
one hash committing to the entire history — and is anchored in the
repository host's dated commits and, via OpenTimestamps, in Bitcoin
(a decentralized attestation no party can backdate, used here purely
as a timestamp notary — the "deliberately rejected: blockchain"
ruling below concerns storing the archive on one, not witnessing
hashes with one). The chain alone makes tampering evident *within* a
copy; checkpoints settle *between* copies — whichever matches the
earliest anchored tip is the original. `verify.py` checks every
checkpoint against the chain; the anchors themselves are verified by
their own tools (`git log`, `ots verify`) and their loss can only
remove witnesses, never harm the archive.

## Distribution and custody (ratified 2026-07-06)

**The repository never contains testimony text.** It is the public
transparency instrument: code, Constitution, schemas, the event log,
and the verification tools — nothing else. The log carries only
fingerprints, so anyone may clone it and prove every promise
(numbers never reused, testimonies never altered, withdrawals
recorded) without holding a single word of testimony.

Testimonies are **browsable through the official website**, page by
page, human by human. The complete archive is **distributed only to
trusted preservation partners** as snapshots under formal deposit
agreements (which carry the tombstone semantics of Article V). The
canonical archive itself lives on the operator's custody copies.

This is a policy of what the institution distributes, not a claim
that public pages cannot be scraped; the licensing terms (see
`LICENSING.md`) govern that. What it guarantees is that no one —
scraper, dataset builder, or model trainer — receives the corpus
*from us* in bulk, while verifiability remains total and public.

## Uniqueness machinery — a second private organ (added 2026-07-09)

One human, one record is enforced where numbers are spent — the desk —
by a private **anchor ledger** specified in `schema/ANCHORS.md` and
implemented in `tools/anchors.py` (stdlib only, like everything).

**Construction.** Each enrollment's contact identifiers (email now,
phone when that tier exists) are normalized by frozen versioned rules
and stored only as HMAC-SHA256 fingerprints under a secret pepper.
Fingerprints are staged at enrollment and periodically **sealed into
hash-chained batches** — never one batch per enrollment — so even a
leak of ledger *and* pepper yields anchor→batch-window only
(k-anonymity at sealing granularity), never anchor→registry-number.
`tools/enroll.py` exits fatally on any sealed-or-staged match;
overrides for honest collisions are recorded privately.

**Why desk-side only.** The pepper never touches third-party
infrastructure: the web worker does no anchor checking and never
could. This costs nothing — a duplicate *submission* is free to land
in KV; only a duplicate *number* matters, and numbers are only ever
spent at the desk. No endpoint anywhere answers "is this identity
enrolled" (responses are byte-identical either way).

**Witnessing.** Every public checkpoint records the ledger's batch
count and tip hash (`anchor_ledger` in `checkpoint.v1` entries), so
the same git + OpenTimestamps machinery that freezes the archive
proves, decades on, that no batch was ever rewritten — without one
anchor ever being public. `tools/verify.py` cross-checks when custody
is present and skips silently on public clones.

**Custody and succession.** The custody directory (`AH_CUSTODY_DIR`,
outside the repository) holds the pepper, the anchor ledger, the
retained agreements (`agreements/`), the vouch edges (`edges/`,
number→number only), and the private ops log. A steward who does not
inherit pepper + ledger + agreements cannot enforce uniqueness:
handover is a ceremony, and the pepper is verified against its
fingerprint published in `schema/ANCHORS.md`.

**Self-serve vouching (built 2026-07-12).** Voucher-initiated only: an
enrolled human proves their continuity key (the same client-side gate
as the return page), the browser mints the code, and only its SHA-256
travels (`vouchtok:{hash}` in KV, single-use, 30-day TTL; a fence of at
most three live invitations via `vouchby:{rid}:{hash}` marks with
the same 30-day TTL - the rolling-year quota itself is spent only
at enrollment, from the custody edge file, exactly as numbers are
spent only at approval). KV's eventual
consistency permits races — acceptable because the desk re-checks
quotas and duplicate use from the custody edge file at review; any
future fully-automated era must re-solve this. The founder's
hand-vouch bridges until these pages land, binding the same anchors,
leaving no uniqueness holes.

## MVP — the path to Human #2

For the first hundreds of humans, the entire backend is:

**A git repository containing the transparency log and tools, a
private custody copy holding the registry, and a static site
generator.**

Git already is a signed, append-only, hash-chained, replicated
log — it *is* the MVP transparency log. (Per the distribution
ruling above, the repository carries the log and never the
testimony text; committing the log update *is* the public act of
record for each enrollment.) The generator (one small,
dependency-light program; plain HTML output, readable with CSS off)
renders `registry/` into pages at `thehumanrecord.earth/{number}`, plus
the random-human button and the ceremony/enrollment explanation.
Static hosting behind a CDN. No database. No queue. No accounts.
No servers to keep alive.

Enrollment at this stage is founder-mediated ceremony: the
questionnaire is completed, the entry is reviewed, the number is
assigned by appending to the log, the files are committed, the site
regenerates. Slow is acceptable — slow is *in the mission*.

**Assignment is manual in timing, automatic in value.** A human
decides *when* someone enters; the system decides *what number*
they receive — always the next in sequence, never chosen by anyone.
No gaps, no vanity numbers, no favors: the ordering is provable
from the log, and ego is removed from the numbering forever. This
holds at every scale — the ceremony may one day be self-serve, but
no operator, founder included, will ever pick a number.

**Human #2 therefore requires exactly four things:**

1. The questionnaire ratified (the draft of ten questions is in
   `drafts/SOUL-RECORD.md`; questions are constitutionally hard to
   change after ratification, so this is the remaining big
   decision).
2. Schema v1 frozen and published.
3. The repository initialized: three master documents, schemas,
   empty registry, log with its genesis event.
4. The generator + the public site serving the result, with entry
   #2 — the Founder — as the first record.

## Growth path — when machinery is added, and why not before

- **~100s of humans:** flat files + git + static site. Moderation
  is the founder reading every testimony before commit.
- **~10,000s:** self-serve enrollment appears: a small API and
  Postgres for accounts, drafts, and the review queue. The archive
  stays canonical — approval *writes to the archive*, the database
  is operational scratch space. Numbers are assigned only at
  approval, so fakes never consume numbers. Verification Tier 1
  (phone) arrives here.
- **~1,000,000s:** the pipeline is the product: ML-assisted text
  triage with human review, crisis-language screening with a humane
  response path (a page asking about regret will receive
  disclosures — policy written before launch, not after), vouching
  (Tier 2), proper CT-style log service, institutional deposits,
  audio testimony as an equal citizen.
- **Scale ceiling:** 100M testimonies ≈ 200 GB of text. The
  complete archive fits on one hard drive forever. There is no
  scaling problem in this product; there is only a stewardship
  problem.

## Verification (summary; full design in drafts/PERSONHOOD doc)

Tier 0 email → may write a draft. Tier 1 phone → may receive a
number. Tier 2 vouched-by-a-verified-human → covers those the phone
tier excludes, and makes verification an act of human connection.
Tier 3 documented (opt-in, never required). Every record displays
the tier of its era ("verified to the standard of its era").
Integrity defenses that cost nothing: the deliberately slow
ceremony, review-before-number, and time itself — fake records
stay inert for decades while real ones accrete life.

**Domain-free schema identifiers (decided 2026-07-17).** The
immutable v1 schemas identify themselves by URN
(`urn:humanrecord:schema:entry:v1` and siblings), never by URL.
Deliberate: those files are hash-anchored in the genesis event, so
whatever they contain is permanent - and a rented domain does not
belong in the immutable set. A URN is a valid absolute URI that never
needs to resolve, so the institution's front door (whatever address it
answers at, in any decade) is decoupled from its founding documents
forever.

## Preservation

Lots of copies keep stuff safe: scheduled deposits with the
Internet Archive and university/national libraries under formal
agreements (with tombstone semantics for withdrawals); cold copies
in century-rated vaults; jurisdictional diversity. The withdrawal
cascade — remove content, write tombstone, propagate to deposits,
regenerate views — is built and tested from day one, because
retrofitting erasure into a permanence system is the one rewrite
this architecture must never need.

## Deliberately rejected

Blockchain (a signed hash-chained log gives provable never-reuse
without the baggage). Database-first design (the archive is
canonical; databases are views). Dynamic rendering (static files
serve a century better than any framework). Frameworks generally
(every dependency is a bet that someone else's code outlives us).
Faces as the primary record (see `drafts/` — the pivot to testimony
removed biometric-law exposure, the scraping problem, and most
moderation risk, and made the archive small enough to preserve
forever).
