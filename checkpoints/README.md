# Checkpoints — the archive's anchors in time

This directory is how anyone, in any decade, can prove the archive's
history was never rewritten — without trusting us.

## What is in here

- **`<date>-<tip12>.tip`** — a checkpoint: the hash of the newest log
  event on that date. Because every event's hash commits to every event
  before it, this one hash stands for the entire history up to that
  moment. A checkpoint file is frozen forever.
- **`<date>-<tip12>.tip.ots`** — the OpenTimestamps receipt for that
  checkpoint: a cryptographic proof that the checkpoint existed by a
  certain date, attested in the Bitcoin blockchain.
- **`checkpoints.jsonl`** — the ledger: one line per checkpoint, with
  its timestamp, how many events it froze, and which anchors hold it.

We anchor the **checkpoint file**, never the log itself: the log is
append-only, so a receipt over the log would be stale one event later.
A checkpoint never changes, so its receipt stays valid forever.

## How to verify (two independent steps)

**1. Verify the chain and the checkpoints — no internet, no
dependencies.** From the repository root:

    python tools/verify.py

This recomputes every event hash, walks the chain, and confirms every
checkpoint in the ledger matches the history you are holding. It is
standard-library Python on purpose, so it can be reimplemented in any
language by anyone (rules in `schema/CANONICAL.md`).

**2. Verify the Bitcoin attestation — one small tool, one command.**

    pip install opentimestamps-client
    ots verify checkpoints/<date>-<tip12>.tip.ots

`ots verify` answers with a date: *"Bitcoin block N attests existence
as of ~date"*. That date comes from Bitcoin's proof-of-work — nobody,
the operator of this archive included, can forge it or backdate it.

Then close the loop yourself: the hash inside the `.tip` file is the
same tip hash your own run of `tools/verify.py` computed. If they
match, the history in your hands is the history that existed at that
attested date. If anyone ever rewrote it, the hashes cannot match —
whichever copy matches the earliest anchored checkpoint is the
original.

## Pending receipts

A fresh receipt starts **pending**: the OpenTimestamps calendars hold
the commitment until a Bitcoin block confirms it, usually within
hours. A GitHub Action (`.github/workflows/anchor.yml`) stamps every
new checkpoint the moment the log grows, and each month upgrades
pending receipts to full Bitcoin attestations — no human in the loop.
A pending receipt is already a commitment; upgrading just completes
the proof so verification needs nothing but the file and Bitcoin.

## The quiet second anchor

Every commit of this directory is itself an anchor: the repository
host dates it, and every clone in the world becomes a witness. Losing
any anchor service can never harm the archive — anchors only add
witnesses, and the archive's truth never depends on any one of them.
