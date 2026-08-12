"""The institution's public identity — its display name, address, and
the words it calls itself by. The ONE place these live.

--------------------------------------------------------------------
For whoever comes after us — read this before you rename anything.
--------------------------------------------------------------------

There are two names here, and the difference is the whole point.

1. The BIRTH-NAME. The founding documents — the Constitution and the
   genesis event — were written as "the AllHumans Registry". They are
   immutable: hash-anchored in the log and checked by tools/verify.py,
   exactly like every testimony. They can NEVER be edited; that is not
   a limitation, it is the guarantee that makes the archive trustworthy
   (a founder who could quietly rewrite the founding text could quietly
   rewrite anything). So "AllHumans" and "Registry" live forever in the
   founding record. That is the institution's legal birth-name, and it
   stays. See NAMING.md for the annotation that explains this in public.

2. The PUBLIC NAME. What the living website calls the institution, and
   the web address it answers at, are *presentation*, not *record*.
   They may change — a rebrand, a new domain — without touching a
   single fingerprint. Those changeable strings are BRAND and DOMAIN
   below, and every generated page reads them from here.

So: to rename the public institution, change BRAND (and, if the domain
moves, DOMAIN) and rebuild the site. Do NOT hunt through the pages, and
do NOT try to change the name in the Constitution or the log — you
cannot, and you should not. The birth-name endures; the public name is
a one-line decision.

Two vocabulary rules the site follows, kept consistent everywhere:
  - The institution is called "the Archive" in living text (the
    founding docs' word "Registry" is preserved only where immutable).
  - A human holds a "number" — never an "ID". Internally the field is
    still `registry_id` (frozen in schema v1); that is wire format, not
    a word any human reads.

Standard library only; imported by the site generators.
"""

import os


def _env_override(name: str, default: str) -> str:
    """A rehearsal may override identity via the environment; unset
    always means production. A set-but-unusable value stops the build,
    it never silently falls back."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    val = raw.strip()
    if not val or any(c.isspace() for c in val):
        raise SystemExit(
            f"{name}={raw!r} is not a usable value. Unset it for the "
            "production default, or set a real one.")
    return val


# Public display name. Change the default here to rename the
# institution's brand, then rebuild. (Legal note: as of this writing
# the public name is under review — do not treat any value here as
# final until cleared.) AH_BRAND overrides for rehearsals only.
BRAND = _env_override("AH_BRAND", "The Human Record")

# Public web address (no scheme). AH_DOMAIN overrides for rehearsals.
DOMAIN = _env_override("AH_DOMAIN", "thehumanrecord.earth")
if "." not in DOMAIN:
    raise SystemExit(f"AH_DOMAIN={DOMAIN!r} does not look like a domain.")

# Where the Archive answers enrolled humans.
CONTACT_EMAIL = "enroll@" + DOMAIN

# The reading room's own subdomain (the "how it works / documents" hub).
INFO_URL = "https://info." + DOMAIN

# The donation destination — the ONE place the URL lives, read by every
# page that mentions donations. It MUST point at a real, claimed
# collective; the Stewardship copy commits the institution to a public
# ledger (Open Collective), so the honest choice is a collective whose
# books anyone can read. AH_DONATE_URL overrides for rehearsals.
# TODO(founder): create the collective and set the true slug here; until
# then this link has no live destination.
_DONATE_PLACEHOLDER = "https://opencollective.com/the-human-record"
DONATE_URL = _env_override("AH_DONATE_URL", _DONATE_PLACEHOLDER)

# True only once a real destination exists. The placeholder answers 404,
# and a prominent button to nowhere is worse than no button at all -
# especially at the end of the writing ceremony, where a person has just
# left their life story and is feeling something. The sentence saying the
# Record is donation-funded is always shown, because it is true; the
# button appears when there is somewhere for it to go.
DONATE_READY = DONATE_URL != _DONATE_PLACEHOLDER
