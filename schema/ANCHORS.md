# Identity anchors — the uniqueness spec (anchors v1)

*Frozen and versioned like `CANONICAL.md`: any future era must be able
to reimplement this from the text alone, in any language. Changes come
only by adding new versions (`em2`, `ph1`, …) beside the old — an
anchor once written is never re-derived.*

One human, one record. The Registry keeps that promise with **identity
anchors**: durable contact identifiers the era's machinery already
touches, stored **only as keyed one-way fingerprints** in a private
ledger, and checked before any number is ever assigned. The public
archive, the git repository, and the website never contain an anchor
— only the count of batches and a tip hash are witnessed publicly
(see Checkpoints below).

## What is an anchor — and what never is

- `em1` — the enrollment email (mandatory in every era: it is the
  reply channel).
- `ph1` — a verified phone number (reserved; used when the phone tier
  exists).
- Future types by governance, added beside these, never replacing.

**Never collected, by standing privacy commitment (POLICY.md):** no
birth names, no dates of birth, no birthplaces beyond the coarse
optional public field, no government identifiers, no biometrics, no IP
addresses, no device fingerprints. The safest data is data never held;
hashing low-entropy birth facts gives false privacy.

## Canonical anchor strings

- Email (`em1`): Unicode NFC → strip surrounding whitespace →
  lowercase → in the local part, remove one `+tag` suffix (everything
  from the first `+` to the `@`) → fold the domain `googlemail.com`
  to `gmail.com` (one mailbox namespace, one anchor) → if the domain
  is `gmail.com`, remove all `.` from the local part. Canonical
  string: `em1|{local}@{domain}`.
- Phone (`ph1`, reserved): digits only (E.164, no `+`, no spaces).
  Canonical string: `ph1|{digits}`.

## Fingerprints

`HMAC-SHA256(pepper, canonical_string)` in lowercase hex, where the
canonical string is UTF-8 encoded. Plain SHA-256 is rejected: emails
and phone numbers are low-entropy and dictionary-attackable; the
secret pepper is what makes a leaked ledger unlinkable noise.

A stored anchor line is `{type}:{hmac_hex}`, e.g. `em1:3f9a…`.

## The pepper (v1)

- 256 bits, hex, generated once by `tools/anchors.py init`
  (`secrets.token_hex(32)`).
- Lives ONLY in operator custody: the file named by
  `AH_ANCHOR_PEPPER_FILE` (default `{custody}/pepper-v1.txt`), plus a
  paper copy in the century vault, named in the succession papers —
  the same custody class as the archive itself.
- NEVER in this repository, never on the web host, never in KV,
  never in environment values checked into any config.
- **Cannot be rotated**: plaintext anchors are never retained, so a
  new pepper could not re-derive old fingerprints. If pepper and
  ledger both leak, the ledger becomes a yes/no membership oracle for
  candidate contacts at batch granularity — accepted, because
  retaining plaintext to allow re-peppering is strictly worse.
- Its SHA-256 fingerprint is published below at ceremony time so any
  successor can prove they hold the true pepper. The fingerprint is
  computed over the **canonical hex string** (whitespace-stripped,
  ASCII), never over raw file bytes — a pepper re-typed from the
  paper vault copy must fingerprint identically regardless of line
  endings.
- Every sealed batch records the fingerprint of the pepper it was
  built under; the tools refuse loudly when the pepper in service
  does not match the ledger, because a wrong pepper would silently
  answer "free" for every membership question.

### Published pepper fingerprints

| version | SHA-256 of pepper file content | published |
|---------|--------------------------------|-----------|
| v1 | `dc12242cb8856ac872c8d0952576d4d40c29a6ce56057b73263e757d1e1131d1` | 2026-07-12 |

## The ledger

Two private files under the custody directory (`AH_CUSTODY_DIR`;
never in the repository — the in-repo `custody/` fallback is
gitignored and for drills only):

- `anchors/staged.jsonl` — bare anchor lines (`em1:{hmac}`), written
  by `tools/enroll.py` at each enrollment. No registry ids, no
  timestamps, no metadata — and the file is rewritten **sorted and
  unique on every write**: insertion order is linkage, so it is
  destroyed at write time, not just at sealing.
- `anchors/ledger.jsonl` — sealed batches, hash-chained exactly like
  the public log. One line per batch:

```
{"schema": "anchorbatch.v1", "seq": 0, "sealed_at": "…Z",
 "count": N, "anchors": ["em1:…", … lexicographically sorted],
 "pepper": "…64 hex… (fingerprint of the pepper in service)",
 "prev_hash": "…64 hex… (64 zeros for the first batch)",
 "hash": "…64 hex…"}
```

`hash` = SHA-256 of the canonical JSON (schema/CANONICAL.md) of the
line with its `hash` field absent — the same rule as `event.v1`.

**Sealing** (`tools/anchors.py seal`) folds the staged lines into one
sorted batch: a leaked ledger plus pepper yields anchor→batch-window
only — k-anonymity at batch granularity, never
anchor→registry-number. Seal periodically (monthly, or every ~25
enrollments), NEVER per enrollment; single-anchor batches are refused
without `--allow-small`, and `backfill` seals small only for the
founding batch 0. **Backfill anchors only ENROLLED humans**, named
explicitly by the founder — an acceptance record alone is a draft,
and anchoring it would refuse that person's real enrollment later. Sealing is crash-safe: staged lines already present
in a sealed batch are filtered before sealing, so an interrupted seal
re-run never writes the same anchors twice.

**Membership** (the only question the ledger answers) is checked over
sealed ∪ staged. The staging window between seals is the only
unwitnessed span; it is kept small.

## Checkpoints witness the ledger

When custody is configured, `tools/checkpoint.py` includes
`{"anchor_ledger": {"batches": N, "tip_hash": …}}` in each public
checkpoint. The private organ is thereby frozen by the same git (and
optional OpenTimestamps) machinery as the archive: a steward decades
on can prove no batch was ever rewritten, without any anchor ever
being public. `tools/verify.py` cross-checks this when custody is
present and skips it silently on public clones.

## Vouch edges (who vouched for whom)

`edges/vouch-edges.jsonl` in custody, one line per vouch:
`{"schema": "vouchedge.v1", "voucher": "0000000NN", "vouchee":
"0000000NN", "ts": "…Z"}` — registry number to registry number ONLY,
never names, never contact identifiers. It is the one deliberately
kept private relational record (POLICY.md): permanent unless
governance orders minimization or destruction; no timed auto-deletion
(a century institution cannot depend on a deletion firing in year 47).

## Enforcement

`tools/enroll.py` — the only tool that ever spends a number, in every
era — refuses to enroll while any anchor on the submission matches the
ledger. Overrides exist for honest collisions (shared family email,
recycled phone): `--anchor-override "reason"`, recorded privately in
`ops-log.jsonl` in custody, never public. The web worker never checks
anchors and never holds the pepper: dedup only ever needs to gate
where numbers are spent, and that is the desk.
