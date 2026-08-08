# Resolve a REAL Python interpreter for the test scripts. Sourced, never
# executed. Sets $PY, safe to call quoted ("$PY") or not ($PY).
#
# Why probing: on Windows, `python3` (and sometimes `python`) is a
# Microsoft Store STUB that prints an install hint and exits nonzero
# instead of running Python — so the name existing proves nothing; only
# an actual `import sys` does. $PYTHON always wins when set (keep it a
# single word, or a name on PATH).
#
# The archive's tools never source this: they are INVOKED BY Python and
# carry no shell. This file exists so the safety net runs on every
# steward's machine, whatever their OS calls the interpreter.
if [ -n "${PYTHON:-}" ]; then
  PY="$PYTHON"
elif python3 -c 'import sys' >/dev/null 2>&1; then
  PY=python3
elif python -c 'import sys' >/dev/null 2>&1; then
  PY=python
elif py -3 -c 'import sys' >/dev/null 2>&1; then
  # the Windows launcher takes two words; a function keeps $PY one word
  ah_py() { py -3 "$@"; }
  PY=ah_py
else
  echo "no working Python found (tried python3, python, py -3): set PYTHON" >&2
  exit 2
fi
