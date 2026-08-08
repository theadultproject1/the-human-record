# The Human Record

**A permanent archive of ordinary human testimony.**

Every person may hold one number and leave at most three testimonies in
a lifetime — each answering the same fixed questions, each unchanged
once entered, kept for as long as there are people to keep it. Not for
being rich, or famous. Simply for being here.

The archive is at **[thehumanrecord.earth](https://thehumanrecord.earth)**.

**This repository is how you check that it is telling the truth.**

---

## Check it yourself, in about a minute

You need Python 3.10 or newer. Nothing else — no packages to install,
no accounts, no network. Every tool here is standard library only, so
this still runs on a machine built decades from now.

```
git clone https://github.com/theadultproject1/the-human-record
cd the-human-record
python tools/verify.py
```

It should print `OK`, then how many events and enrollments the chain
proves and how many checkpoints are anchored. If it prints anything
else, something is wrong and you have found it — not us.

**What that one command actually proves:**

- **Nothing was altered.** Every entry is chained to the one before by
  SHA-256. Change a single character anywhere in the history and the
  chain breaks from that point on.
- **No number was ever reused.** The sequence is public and auditable
  end to end.
- **The founding documents still say what they said.** The first line
  of the log records the SHA-256 of the Constitution, the questionnaire
  and the schemas. Edit any of them and verification fails for every
  clone on earth, permanently.
- **Withdrawals were honoured.** When an author withdraws, the words go
  and a signed marker stays. You can see that it happened.

## And proof we did not simply rewrite the whole chain

A chain proves integrity. It cannot prove *priority* — the author of a
chain could, in principle, rebuild it from scratch. So the tip of the
log is frozen into `checkpoints/` and stamped into the **Bitcoin**
blockchain through OpenTimestamps. Those `.ots` receipts are in this
repository.

That means the record's state at a given moment is fixed in something
we do not control and cannot revise. History rewritten after a stamp
fails against the public record, no matter who rewrote it — including
us.

## The testimonies are not here, and that is deliberate

You will find no one's words in this repository. The log carries only
**fingerprints** — one-way hashes. Anyone can look at a fingerprint;
nobody can read the words back out of it.

So this repository lets you prove every promise about the archive
without holding a single line of anyone's testimony. The words
themselves are read on the website, page by page, human by human, as
their authors intended. Complete copies go only to preservation
partners under formal agreements.

An author's continuity key is not here either, and never will be: it is
created in the writer's own browser, and the institution has never held
a copy. We cannot recover one. We say so plainly rather than pretend
otherwise.

## The institution's own words

Read them in this order if you are arriving cold:

| Document | What it is |
|---|---|
| [MISSION.md](MISSION.md) | why this exists |
| [CONSTITUTION.md](CONSTITUTION.md) | the immutable rules, ratified 2026-07-05 |
| [POLICY.md](POLICY.md) | the deliberately changeable rules, with their change log |
| [PRIVACY.md](PRIVACY.md) | what is held, what is never held, what happens to your email |
| [ARCHITECTURE.md](ARCHITECTURE.md) | how it is built to outlive its builders |
| [LICENSING.md](LICENSING.md) | who owns what — authors own their words |
| [NAMING.md](NAMING.md) | the public name, the founding name, and why they differ |
| [questions/v1.md](questions/v1.md) | the questionnaire every testimony answers |
| [schema/CANONICAL.md](schema/CANONICAL.md) | the hashing rules, precise enough to reimplement in any language |

The Constitution cannot be amended by any individual. `CONSTITUTION.md`
and the questionnaire are anchored by hash in the log's first line;
they are finished documents.

## What is not in this repository, and why

Honesty about the gaps is part of the point, so here they are:

- **The testimonies**, as above — by ratified design.
- **The operator's runbook and security audit.** They describe how the
  machine is run and where its weaknesses are. Neither is needed to
  verify anything here; both would be useful mainly to someone
  attacking the archive. Everything they would prove, `verify.py`
  proves without them.
- **Deployment configuration and the anchoring workflow.** These belong
  to the operator's own hosting account. The receipts the workflow
  produces *are* here, in `checkpoints/` — and the receipt is the
  proof, not the script that fetched it.
- **The film** shown on the website: brand work under different terms,
  and a large video in a repository people clone to check text.

Nothing withheld is required to check a single claim on this page. If
you find one that is, that is a bug in our reasoning and we want to
know.

## Reporting a problem

If you find a flaw — in the code, the reasoning, or a promise we have
not kept — please tell us privately first, through this repository's
**Security** tab → *Report a vulnerability*. See
[SECURITY.md](SECURITY.md).

## Licence

The code is **Apache-2.0**. The founding documents are dedicated to the
public domain. **The testimonies belong to the humans who wrote them**
and are licensed to nobody — see [LICENSING.md](LICENSING.md).

---

*One life. One number. One permanent place in history — because you
were here.*
