# On the names of this institution

*This is the public annotation that explains the institution's names:
what the founding documents say, what came before them, and which words
are fixed forever versus free to change.*

---

## The name, and the founding before the founding

The founding documents read **The Human Record**. That is the
institution's name, ratified in the genesis event and immutable from
that moment on.

It was not the first name. The institution was first founded on
2026-07-05 as *"the AllHumans Registry."* Before any human enrolled -
while the registry held zero records and no testimony existed - a
trademark conflict forced the public name to change, and rather than
carry a dead name in its immutable founding documents forever, the
founder re-founded the still-empty archive under its final name on
2026-07-17. Nothing was lost, because nothing yet existed to
lose; nothing was hidden, because the first founding is archived in
`checkpoints/pre-refounding/` - its genesis event and its Bitcoin
timestamp receipt - where anyone, in any decade, can verify exactly
what the archive was before the re-founding: one genesis line and
nothing else. The re-founding is also recorded in
`founder/FOUNDER_INTENT.md`.

This door closed permanently the moment the first human enrolled. The
founding documents will never change again, for the same reason the
change was honest: immutability protects testimony, and now testimony
exists.

## The public name - free to change anyway

What the living website calls the institution, and the address it
answers at, remain *presentation*, not *record*. They may change - a
rebrand, a new domain - without touching a single fingerprint. Those
changeable strings live in exactly one place: `tools/brand.py`
(`BRAND`, `DOMAIN`). The founding record now happens to match the
public name; if the public name ever moves again, this annotation is
where the bridge gets written.

## The words we use

- **"The Record."** In living text the institution is called *The
  Record* - capital The, the natural short form of The Human Record -
  or by its full name. Each human holds *a record*, lowercase: the
  container that carries at most three testimonies. What a human
  writes is *a testimony*: you write a testimony; your record keeps
  it. So: "your record grows," but "your testimony has been
  received." The founding word *"Registry"* remains in the
  Constitution as the functional word for the register of records,
  and in wire format.
- **"A number," never "an ID."** A human holds a *number* - Human #2 -
  never an "ID." The internal data field is still `registry_id` and
  the folder is still `registry/`; that is wire format and directory
  structure, frozen in schema v1, and no human ever reads it. Names
  humans read, and names machines read, are allowed to differ.
- **The schema $ids are URNs** (`urn:humanrecord:schema:entry:v1` and
  siblings): identifiers, not addresses, so the immutable set names no
  rented domain. See ARCHITECTURE.md for the reasoning.

## Domains

The institution answers at `thehumanrecord.earth`. The first public
address, `allhumans.world`, is kept and redirects, forever: a century
archive never breaks a link.
