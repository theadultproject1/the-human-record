"""The Legacy Key page (legacy.html): someone the author trusted comes
to report a death and open the sealed words.

Deliberately unlike every other gate: the visitor is likely grieving,
so the page asks for exactly three things — the record's number, the
six words, and one attestation — and it never says whether the words
were right. The worker checks FORMAT only and stores the report; the
key itself is verified at the steward's desk (the stretched fingerprint
is never published, so there is nothing online to guess against), the
mourning ceremony runs (a note to the record's enrollment email,
and a wait, so a living author can simply answer "I am alive"), and the
opening is a ceremony recorded in the log: the record is memorialized
and its seals open. If no key is ever brought, time opens them instead,
one hundred years after enrollment.

Some are opened by those we trust. The rest are opened by time itself.
"""
import brand
import pages


def render_legacy():
    parts = []
    parts.append('<div id="gate">')
    parts.append('<h1>Opening sealed words</h1>')
    parts.append(
        '<p class="meta">If someone you knew kept a record here and gave you '
        'their Legacy Key, six plain words, this is the place they meant it '
        'for. We are sorry you are the one carrying it.</p>')
    parts.append(
        '<p class="banner">What happens next: a person reads every report. '
        'If all is true, the record is marked a completed life, and the '
        'words its author sealed are opened for everyone who comes after, '
        'exactly as they intended.<br><em>Some are opened by those we '
        'trust. The rest are opened by time itself.</em></p>')
    parts.append(
        '<div class="q"><p class="prompt">Their record number is…</p>'
        '<textarea id="l_id" maxlength="9" placeholder="e.g. 2"></textarea></div>')
    parts.append(
        '<div class="q"><p class="prompt">The six words they left me are…</p>'
        '<p class="note">lowercase, separated by spaces, exactly as they were '
        'given</p>'
        '<textarea id="l_words" maxlength="120" '
        'placeholder="ember harvest quiet door lantern sparrow"></textarea></div>')
    parts.append(
        '<div class="q"><label class="seal"><input type="checkbox" id="l_attest"> '
        'I attest that this human has died. I was trusted with this key for '
        'this moment.</label></div>')
    parts.append('<p><button class="finish" id="send">BRING THE KEY</button></p>')
    parts.append('<p class="err" id="gate_err"></p>')
    parts.append('<p class="meta"><a href="index.html">Return to the lights</a></p>')
    parts.append('</div>')

    parts.append(
        '<div id="received">'
        '<h1>The key has been received</h1>'
        '<p>Thank you for carrying it. A person will read this report, as '
        'every one is.</p>'
        '<p>The <strong>mourning ceremony</strong> now begins: thirty days '
        'to verify the truthfulness of this statement. A note is written to '
        'the record\'s own address; if its author still lives, they simply '
        'answer, and nothing changes. When the thirty days have passed in '
        'silence, the seals open and the record is marked a completed life. '
        'Nothing more is needed from you.</p>'
        '<p class="meta">If the words were not quite right, nothing has been '
        'harmed; you are welcome to return and try again.</p>'
        '<p><a href="index.html">Return to the lights</a></p>'
        '</div>')

    parts.append(
        '<div id="fallback">'
        '<h2>The Record could not be reached. Nothing was lost</h2>'
        '<p>Nothing was sent, and nothing was lost. Please return and try '
        'again when the Record is back online.</p>'
        '</div>')

    body = "\n".join(parts)
    html_out = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
                '<title>Legacy Key · ' + brand.BRAND + '</title>\n'
                '<style>' + pages.WRITE_CSS + '</style>\n</head>\n<body>\n' + body
                + '\n' + pages.MODAL_JS + '\n' + LEGACY_JS + '\n</body>\n</html>')
    return html_out.replace('__BRAND__', brand.BRAND)


LEGACY_JS = """
<script>
(function(){
  var btn = document.getElementById('send');
  btn.addEventListener('click', function(){
    var err = document.getElementById('gate_err');
    err.textContent = '';
    var rid = document.getElementById('l_id').value.trim().replace(/^#/, '');
    var words = document.getElementById('l_words').value.trim().toLowerCase()
                  .replace(/[,\\s]+/g, ' ');
    if (!/^[0-9]{1,9}$/.test(rid)) { err.textContent = 'Please enter the record number, digits only.'; return; }
    if (!/^[a-z]+( [a-z]+){5}$/.test(words)) { err.textContent = 'The Legacy Key is exactly six words, separated by spaces.'; return; }
    if (!document.getElementById('l_attest').checked) { err.textContent = 'The attestation is the one thing we must ask of you.'; return; }
    ahConfirm({
      title: 'Bring the key?',
      lines: [
        'You are reporting that the human of record #' + rid + ' has died.',
        'A person will read this, their address will be written to, and a '
          + 'mourning ceremony will pass before the seals open.'
      ],
      ok: 'BRING THE KEY', cancel: 'Not yet'
    }).then(function(go){
      if (!go) return;
      btn.disabled = true;
      fetch('/api/legacy', {method:'POST',
          headers:{'content-type':'application/json'},
          body: JSON.stringify({ registry_id: rid, words: words, attested: true,
                                 submitted_at: new Date().toISOString() })})
        .then(function(r){ if (!r.ok) throw new Error('status ' + r.status); return r.json(); })
        .then(function(){
          document.getElementById('received').style.display = 'block';
          document.getElementById('gate').style.display = 'none';
          window.scrollTo(0, 0);
        })
        .catch(function(){
          btn.disabled = false;
          document.getElementById('fallback').style.display = 'block';
          document.getElementById('fallback').scrollIntoView({behavior: 'smooth'});
        });
    });
  });
})();
</script>
"""
