# Canonical form and hashing (spec v1)

Every hash in this archive is **SHA-256, lowercase hex**, computed
over the **canonical JSON** encoding of a value:

- UTF-8 bytes
- object keys sorted lexicographically
- no insignificant whitespace (separators `,` and `:`)
- non-ASCII characters encoded literally (not `\uXXXX`-escaped)
- no trailing newline

In Python: `json.dumps(value, sort_keys=True, ensure_ascii=False,
separators=(",", ":")).encode("utf-8")`.

## `content_hash` of a testimony version

SHA-256 of the canonical JSON of the version's **`answers` object
exactly as entered**. On withdrawal the `answers` object is removed
from the file but `content_hash` remains: it proves what was once
said without saying it.

## Event `hash` in the Registry log

Each line of `log/registry.log.jsonl` is one event object. Its
`hash` is SHA-256 of the canonical JSON of the event **with the
`hash` field absent**. Its `prev_hash` is the `hash` of the previous
line; the first line (GENESIS) uses 64 zeros. Any copy of the log
can therefore be verified independently, forever, with ~20 lines of
code in any language (`tools/verify.py` is the reference).

This file is part of schema v1 and changes constitutionally slowly.
