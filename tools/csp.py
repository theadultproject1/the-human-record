"""Content-Security-Policy for the generated sites. Stdlib only, forever.

Every script and style on every page is INLINE by design: one file, no
external requests, readable in any decade. A policy that said
'unsafe-inline' would therefore allow exactly what an attacker needs
and forbid nothing — theater. Instead the generators call page_csp()
on each finished page: it hashes every inline <script> and <style>
block (SHA-256, the CSP hash-source form) and emits a policy that
allows those exact blocks and nothing else. The browser then refuses
any script that is not byte-for-byte what the generator wrote —
including anything an escaping bug might one day let a testimony
smuggle in. The escaping is the lock; this is the second lock.

Two rules this design imposes on the generators, permanently:
  * No style="..." attributes — hashed style-src does not allow them.
    Use a class; the stylesheet is hashed as a whole.
  * No inline event handlers (onclick="...") and no javascript: URLs —
    hashed script-src does not allow them. Use addEventListener.
"""
import base64
import hashlib
import re

# The generators emit bare <script> and <style> tags only (no
# attributes), so these patterns match exactly what browsers hash.
_SCRIPT = re.compile(r"<script>(.*?)</script>", re.S)
_STYLE = re.compile(r"<style>(.*?)</style>", re.S)


def _hash_source(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return "'sha256-" + base64.b64encode(digest).decode("ascii") + "'"


def page_csp(html_text: str) -> str:
    """The complete CSP for one finished page."""
    scripts = _SCRIPT.findall(html_text)
    styles = _STYLE.findall(html_text)
    script_src = " ".join(_hash_source(s) for s in scripts) if scripts else "'none'"
    style_src = " ".join(_hash_source(s) for s in styles) if styles else "'none'"
    return ("default-src 'self'; "
            f"script-src {script_src}; "
            f"style-src {style_src}; "
            "base-uri 'none'; object-src 'none'; frame-ancestors 'none'")
