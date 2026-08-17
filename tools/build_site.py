"""Render the archive into a static site. archive -> views, one way.

Usage: python tools/build_site.py          (writes to site/)

Standard library only. Plain HTML, readable with CSS off. The site
is a disposable view; the archive is the asset. Output:

  site/index.html            the lights — one light per human, live
  site/{n}/index.html        one page per human at their unpadded
                             number: thehumanrecord.earth/985558
  site/constitution.html, mission.html, policy.html
  site/verify.html           how anyone can check the promises

There is deliberately no search bar and no browsable roll: you meet
a human by their light, by chance, or by knowing their number and
typing thehumanrecord.earth/{number}.
"""
import hashlib
import html
import json
import math
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ahlib
import brand  # public display name + domain (the one place they live)
import csp
import pages
import pages_return
import pages_legacy
import pages_vouch
import pages_withdraw
import testify  # single source of the spacing policy (MIN_SPACING_DAYS)

SITE = ahlib.ROOT / "site"

# The footer tagline, defined ONCE and shared by both sites (build_info
# imports this module and reuses it), so the two footers can never drift
# apart again. No "archive": the institution is The Record now (NAMING.md);
# "record" here is the plain description, the way a newspaper is "a record
# of the day." Each site appends only its own home link.
FOOTER_TAGLINE = (
    brand.BRAND + ", a permanent record of human testimony. One number, "
    "at most three testimonies, kept forever. This page is only a view; the "
    "testimony it shows is kept and proven elsewhere. Free for every human, "
    "kept alive by "
    # A link only when there is somewhere to send people. An empty href
    # reloads the page, which is a worse answer than plain words.
    + ('<a href="' + brand.DONATE_URL + '" rel="noopener">donations</a>.'
       if brand.DONATE_READY else "donations.")
)

PAPER_CSS = """
body{max-width:42em;margin:2em auto;padding:0 1em;font-family:Georgia,'Times New Roman',serif;line-height:1.6;color:#1a1a1a;background:#fdfcf9}
a{color:#1a1a1a}
h1,h2,h3{font-weight:normal;line-height:1.25}
.qa{margin:1.4em 0}
.q{color:#555;font-style:italic;margin:0}
.a{margin:.2em 0 0 0;font-size:1.05em}
.sealed,.silence{color:#777;font-style:italic}
.meta{color:#555;font-size:.9em;overflow-wrap:break-word}
.tombstone{border-left:3px solid #999;padding-left:1em;color:#555}
nav{margin:1.5em 0;font-size:.9em}
pre.doc{white-space:pre-wrap;font-family:inherit}
footer{margin-top:3em;padding-top:1em;border-top:1px solid #ccc;font-size:.85em;color:#555}
.number{letter-spacing:.08em}
"""

LIGHTS_CSS = """
html,body{margin:0;padding:0;height:100%;background:#06070a;color:#c9c4b8;font-family:Georgia,'Times New Roman',serif;overflow:hidden}
/* The sky IS the page: a fixed full-viewport canvas. The words and buttons
   float above it, and the lights drift behind them. */
canvas#galaxy{position:fixed;inset:0;width:100vw;height:100vh;display:block;touch-action:none;cursor:grab;z-index:0}
body.grabbing canvas#galaxy{cursor:grabbing}
/* A light can still land under the header or the controls — left to
   chance on purpose (see LIGHTS_JS). What isn't left to chance is
   whether it stays hidden: the moment a hand actually touches the sky,
   every word and button steps aside, because that is the one gesture
   that means someone is looking. They return the instant the hand lets
   go, so nothing here is a redesign — it is a courtesy that only shows
   itself when it is needed. */
body.grabbing .wrap,body.grabbing .ctrls,body.grabbing .ghint{opacity:0;pointer-events:none}
.wrap,.ctrls,.ghint{transition:opacity .25s ease}
.wrap{position:relative;z-index:1;min-height:100vh;display:flex;flex-direction:column;pointer-events:none}
header{text-align:center;padding:1.8em 1em .3em}
/* fully opaque lettering with a deep dark halo, so the words stay solid
   and readable even over a dense field of lights */
header h1{font-weight:normal;letter-spacing:.22em;margin:0;font-size:clamp(1.35em,5.2vw,2.6em);color:#f7f2e4;text-shadow:0 0 3px #06070a,0 0 8px #06070a,0 0 18px #06070a,0 0 30px #06070a}
header p.count{color:#f7f2e4;font-size:3.1em;letter-spacing:.08em;margin:.05em 0 0;font-family:'Times New Roman',Georgia,serif;text-shadow:0 0 3px #06070a,0 0 8px #06070a,0 0 18px #06070a,0 0 30px #06070a}
header p.tagline{color:#c8c1ac;font-size:.85em;font-style:italic;margin:.45em 0 0;text-shadow:0 0 3px #06070a,0 0 8px #06070a,0 0 16px #06070a}
.spacer{flex:1}
.empty{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;color:#8a8578;font-style:italic;text-align:center;padding:0 1.5em;z-index:0}
.ctrls{position:fixed;right:12px;bottom:12px;display:flex;flex-direction:column;gap:6px;z-index:2}
.ctrls button{width:38px;height:38px;font-size:1.2em;line-height:1;background:rgba(6,7,10,.55);border:1px solid #55503f;color:#c9c4b8;border-radius:5px;cursor:pointer;font-family:inherit;padding:0}
.ctrls button:hover{border-color:#c9c4b8;color:#e8e3d6}
.lbl{position:fixed;transform:translate(-50%,-170%);background:rgba(6,7,10,.9);border:1px solid #55503f;color:#e8e3d6;font-size:.78em;letter-spacing:.05em;padding:.15em .5em;border-radius:3px;pointer-events:none;white-space:nowrap;display:none;z-index:3}
.ghint{position:fixed;left:12px;bottom:14px;color:#5a564b;font-size:.72em;font-style:italic;pointer-events:none;z-index:2}
.bottom{text-align:center;padding:1.1em 1em 1.8em}
/* only the actual links and buttons catch the pointer — everywhere else,
   your hand touches the sky */
.bottom a,.ctrls button{pointer-events:auto}
.bottom a.enter{display:inline-block;border:1px solid #a89b6e;color:#f7f2e4;letter-spacing:.15em;padding:.85em 2em;border-radius:2px;text-decoration:none;font-size:.95em;box-shadow:0 0 16px 3px rgba(244,233,200,.4);margin-bottom:.9em;background:#04050a}
.bottom a.enter:hover{border-color:#f7f2e4;box-shadow:0 0 22px 5px rgba(244,233,200,.6)}
.bottom p.roomline{color:#c8c1ac;font-size:.9em;font-style:italic;margin:.1em 0 .7em;text-shadow:0 0 3px #06070a,0 0 8px #06070a,0 0 16px #06070a}
.bottom p.roomline a{color:#e8e3d6;text-decoration:underline;text-underline-offset:3px}
.bottom p.roomline a:hover{color:#f7f2e4;text-shadow:0 0 10px rgba(244,233,200,.55)}
.bottom p.small{color:#a89f8a;font-size:.78em;margin:.5em 0 0;text-shadow:0 0 3px #06070a,0 0 8px #06070a}
.bottom p.small a{color:#c8c1ac}
/* The hail: the first thing a visitor meets — the mission, in two bold
   lines, before the sky. Shown once per session; any touch dismisses it. */
.hail{position:fixed;inset:0;z-index:6;background:rgba(3,4,7,.94);display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:0 1.4em;cursor:pointer;opacity:1;transition:opacity .9s ease}
.hail.gone{opacity:0;pointer-events:none}
.hail p.line{font-weight:bold;text-transform:uppercase;letter-spacing:.14em;color:#f7f2e4;font-size:1.45em;line-height:1.65;margin:.35em 0;max-width:24em;text-shadow:0 0 22px rgba(244,233,200,.28)}
.hail p.hint{color:#8a8578;font-size:.8em;font-style:italic;margin-top:2.4em}
/* The film: the intro that plays once, between the hail and the sky.
   It sits UNDER the hail (z 5 < 6): the same touch that dismisses the
   hail is the browser's user gesture, so the film may start with sound. */
.film{position:fixed;inset:0;z-index:5;background:#000;display:none;opacity:1;transition:opacity .9s ease}
.film.on{display:block}
.film.gone{opacity:0;pointer-events:none}
.film video{width:100%;height:100%;object-fit:contain;background:#000}
.skipfilm{position:absolute;right:14px;bottom:14px;background:rgba(6,7,10,.55);border:1px solid #55503f;color:#c9c4b8;font-family:inherit;font-size:.8em;letter-spacing:.12em;padding:.5em 1.1em;border-radius:3px;cursor:pointer}
.skipfilm:hover{border-color:#c9c4b8;color:#e8e3d6}
"""


# The lights: one <canvas>, not one DOM node per human, so a phone paints
# a thousand (or a million) lights in a single frame. Each light's place is
# a HASH of its Registry number — scattered, never ordered — so no number
# sits in a privileged centre and you cannot read the order of enrollment
# from the sky (Constitution, Article I: everyone is equal). A light's spot
# is stable (same number, same place forever) and never moves when others
# join. The view is zoom / pan / pinch, so you can see the whole sky or one
# light. Every light stays clickable (tap/click opens that human's page).
LIGHTS_JS = """
<script>
(function(){
  var IDS = __IDS__, N = IDS.length;
  if (!N) return;
  var wrap = document.body;
  var cv = document.getElementById('galaxy'), ctx = cv.getContext('2d');
  var lbl = document.getElementById('lbl');
  var dpr = Math.max(1, Math.min(3, window.devicePixelRatio || 1));
  var W = 0, H = 0, MARGIN = 26;

  // Deterministic scatter from the number: FNV-1a of the number,
  // then a murmur3 finalizer with three different constants for x, y and
  // brightness — fully decorrelated, so the sky is an even random field with
  // no relation to the number's size or order (Article I).
  function fnv(s){ var h=2166136261; for(var i=0;i<s.length;i++){ h=Math.imul(h^s.charCodeAt(i),16777619); } return h>>>0; }
  function mix(h){ h=Math.imul(h^(h>>>16),2246822507); h=Math.imul(h^(h>>>13),3266489909); h^=h>>>16; return (h>>>0)/4294967296; }
  // Four decorrelated hashes per number: x, y, DEPTH, and a small twinkle.
  // Depth (0 = near, 1 = far) drives size, brightness and parallax, so the
  // sky has real front-to-back layers — all still fixed to the number.
  // A hash can still land under the header or the controls (found 2026-08:
  // a real human's light landed 2.5% from the very top) — left alone on
  // purpose. An earlier attempt reserved two bands and rerolled anyone who
  // landed there, which is fair in the same sense a queue-jump is fair,
  // but it thinned the sky into a visible band at any real population and
  // was never the actual problem: the problem was that a light could stay
  // hidden forever, not that it could ever be briefly covered by a word.
  // The real fix lives where the words are (see body.grabbing below): the
  // UI itself steps aside the moment anyone touches the sky, so nothing
  // ever blocks a light from someone who is actually looking.
  var px=new Float64Array(N), py=new Float64Array(N), dpt=new Float64Array(N);
  var dsz=new Float64Array(N), dbr=new Float64Array(N), damp=new Float64Array(N);
  var order=new Array(N);
  for (var i=0;i<N;i++){
    var base=fnv(IDS[i]);
    px[i]=mix(base^0x9e3779b9);
    py[i]=mix(base^0x85ebca6b);
    var d=mix(base^0x27d4eb2f), near=1-d;
    dpt[i]=d;
    dsz[i]=0.5 + 1.2*near*near;          // size: near stars ~1.7x, far ~0.5x
    dbr[i]=0.4 + 0.6*near;               // brightness: near 1.0, far 0.4
    damp[i]=0.06 + 0.94*near;            // parallax: near stars move most
    order[i]=i;
  }
  order.sort(function(a,b){ return dpt[b]-dpt[a]; });  // far first, near on top
  var PMAX=26, tx=0, ty=0;               // parallax reach (px) + current tilt

  // View: unit square [0,1] -> the field, plus zoom/pan. When the field is
  // dense enough that its boundary would read as a hard edge (a box of
  // stars), it BLEEDS past every screen edge — the sky simply continues
  // off-screen, like a night sky, and panning can never reach its rim. At
  // founding scale (a sparse handful) it fits inside the view instead, so
  // every light is visible at once and no edge is discernible anyway.
  var BLEED = N > 150 ? 1.35 : 1.0;
  var sx=1, sy=1, ox=0, oy=0, fitX=1, fitY=1;
  function fit(){
    fitX=Math.max(1, BLEED>1 ? W*BLEED : W-2*MARGIN);
    fitY=Math.max(1, BLEED>1 ? H*BLEED : H-2*MARGIN);
    sx=fitX; sy=fitY; ox=(W-sx)/2; oy=(H-sy)/2;
  }
  function zoomLevel(){ return sx/fitX; }
  function zoomAt(cx,cy,f){
    var z=zoomLevel(), nz=Math.max(1,Math.min(140,z*f)); f=nz/z; if(f===1) return;
    var ux=(cx-ox)/sx, uy=(cy-oy)/sy;
    sx*=f; sy*=f; ox=cx-ux*sx; oy=cy-uy*sy; clampPan(); draw();
  }
  function clampPan(){
    if (BLEED>1){
      // the field must always cover the whole viewport: no rim, ever
      ox=Math.min(0, Math.max(W-sx, ox));
      oy=Math.min(0, Math.max(H-sy, oy));
    } else {
      // sparse founding sky: keep the field on screen, symmetric both ways
      ox=Math.min(MARGIN, Math.max(W-MARGIN-sx, ox));
      oy=Math.min(MARGIN, Math.max(H-MARGIN-sy, oy));
    }
  }
  // screen position INCLUDING parallax (near stars shift more with tilt)
  function SX(i){ return ox+px[i]*sx + tx*PMAX*damp[i]; }
  function SY(i){ return oy+py[i]*sy + ty*PMAX*damp[i]; }

  // A small, tight warm glow (drawn additively) behind a crisp core — a
  // sharp little star, not a big blurry blob. Size is ~constant in screen
  // pixels so stars stay crisp and small at every zoom.
  var gl=document.createElement('canvas'), glc=gl.getContext('2d'), GR=20; gl.width=gl.height=GR*2;
  var gg=glc.createRadialGradient(GR,GR,0,GR,GR,GR);
  gg.addColorStop(0,'rgba(255,244,214,.95)'); gg.addColorStop(.22,'rgba(250,235,196,.35)');
  gg.addColorStop(.5,'rgba(244,233,200,.08)'); gg.addColorStop(1,'rgba(244,233,200,0)');
  glc.fillStyle=gg; glc.beginPath(); glc.arc(GR,GR,GR,0,6.2832); glc.fill();

  var hoverI = -1, raf = 0;
  // The sky must stay smooth and unsaturated at ANY population:
  //   * sizeK shrinks every star as the field grows denser, so a hundred
  //     thousand lights read as a fine deep starfield, never a wall of glow;
  //   * the soft glow sprite (expensive) is reserved for the ~20k nearest
  //     stars; the rest are drawn as batched crisp cores, a handful of
  //     canvas paths in total — full-screen parallax stays fluid at 100k+.
  var sizeK = Math.max(0.35, Math.min(1, Math.sqrt(20000/N)));
  var GLOWN = Math.min(N, 20000);   // how many nearest stars get the glow
  function draw(){
    ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.fillStyle='#06070a'; ctx.fillRect(0,0,W,H);
    var glowR = 5.0*sizeK, coreR = 1.25*sizeK, k, i, x, y, gr;
    // glow pass (additive), far -> near, nearest GLOWN only
    ctx.globalCompositeOperation='lighter';
    for (k=N-GLOWN;k<N;k++){
      i=order[k]; x=SX(i); y=SY(i); gr=glowR*dsz[i];
      if(x<-gr||x>W+gr||y<-gr||y>H+gr) continue;
      ctx.globalAlpha=dbr[i]; ctx.drawImage(gl, x-gr, y-gr, gr*2, gr*2);
    }
    ctx.globalAlpha=1; ctx.globalCompositeOperation='source-over';
    // core pass, batched into four brightness buckets (dim -> bright, which
    // is also roughly far -> near), each a single canvas fill
    for (var b2=0;b2<4;b2++){
      ctx.fillStyle='rgba(255,246,218,'+(0.55+0.45*((b2+0.5)/4))+')';
      ctx.beginPath();
      for (k=0;k<N;k++){
        i=order[k];
        var bkt=Math.min(3, (dbr[i]-0.4)/0.6*4|0);
        if(bkt!==b2) continue;
        x=SX(i); y=SY(i);
        if(x<0||x>W||y<0||y>H) continue;
        var r2=coreR*dsz[i];
        ctx.moveTo(x+r2, y); ctx.arc(x, y, r2, 0, 6.2832);
      }
      ctx.fill();
    }
    if (hoverI>=0){
      ctx.beginPath(); ctx.arc(SX(hoverI), SY(hoverI), Math.max(5,4*dsz[hoverI]+2), 0, 6.2832);
      ctx.strokeStyle='#fff8de'; ctx.lineWidth=1.4; ctx.stroke();
    }
  }
  function redraw(){ if(!raf) raf=requestAnimationFrame(function(){raf=0;draw();}); }
  function setTilt(nx,ny){ nx=nx<-1?-1:nx>1?1:nx; ny=ny<-1?-1:ny>1?1:ny; if(nx===tx&&ny===ty)return; tx=nx; ty=ny; redraw(); }

  function resize(){
    var r = cv.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return;   // layout not ready yet
    W=r.width; H=r.height;
    cv.width=Math.round(W*dpr); cv.height=Math.round(H*dpr);
    fit(); draw();   // draw directly, not via rAF — the first paint must not
                     // depend on the frame loop (throttled on hidden tabs)
  }

  function pick(qx,qy,thresh){
    var best=-1, bd=thresh*thresh;
    for (var i=0;i<N;i++){
      var dx=SX(i)-qx, dy=SY(i)-qy, dd=dx*dx+dy*dy;
      if (dd<bd){ bd=dd; best=i; }
    }
    return best;
  }
  function showLabel(i,qx,qy){
    if(i<0){ if(hoverI!==-1){hoverI=-1;redraw();} lbl.style.display='none'; return; }
    if(i!==hoverI){ hoverI=i; redraw(); }
    lbl.textContent='#'+IDS[i]; lbl.style.left=qx+'px'; lbl.style.top=qy+'px'; lbl.style.display='block';
  }

  var pts={}, dragging=false, moved=false, downX=0, downY=0, pinchD=0;
  function rel(e){ var r=cv.getBoundingClientRect(); return [e.clientX-r.left, e.clientY-r.top]; }
  cv.addEventListener('pointerdown', function(e){
    cv.setPointerCapture(e.pointerId); pts[e.pointerId]=rel(e);
    var k=Object.keys(pts);
    if(k.length===1){ dragging=true; moved=false; downX=pts[e.pointerId][0]; downY=pts[e.pointerId][1]; wrap.classList.add('grabbing'); }
    else if(k.length===2){ dragging=false; var a=pts[k[0]],b=pts[k[1]]; pinchD=Math.hypot(a[0]-b[0],a[1]-b[1]); }
  });
  cv.addEventListener('pointermove', function(e){
    var p=rel(e);
    if(pts[e.pointerId]){
      var k=Object.keys(pts);
      if(k.length===2){
        pts[e.pointerId]=p; var a=pts[k[0]],b=pts[k[1]]; var nd=Math.hypot(a[0]-b[0],a[1]-b[1]);
        if(pinchD>0) zoomAt((a[0]+b[0])/2,(a[1]+b[1])/2, nd/pinchD);
        pinchD=nd; return;
      }
      if(dragging){
        var prev=pts[e.pointerId]; ox+=p[0]-prev[0]; oy+=p[1]-prev[1]; pts[e.pointerId]=p; clampPan();
        if(Math.abs(p[0]-downX)+Math.abs(p[1]-downY)>4) moved=true;
        redraw(); return;
      }
    }
    if(e.pointerType==='mouse'){ setTilt((p[0]-W/2)/(W/2), (p[1]-H/2)/(H/2)); showLabel(pick(p[0],p[1],14), p[0], p[1]); }
  });
  function up(e){
    var wasDrag=moved;
    if(pts[e.pointerId]) delete pts[e.pointerId];
    if(Object.keys(pts).length<2) pinchD=0;
    if(Object.keys(pts).length===0){ dragging=false; wrap.classList.remove('grabbing'); }
    if(!wasDrag && (e.pointerType!=='mouse' || e.button===0)){
      var p=rel(e); var i=pick(p[0],p[1], e.pointerType==='mouse'?12:18);
      if(i>=0) window.location.href = IDS[i] + '/';
    }
  }
  cv.addEventListener('pointerup', up);
  cv.addEventListener('pointercancel', function(e){ if(pts[e.pointerId]) delete pts[e.pointerId]; if(!Object.keys(pts).length){dragging=false;wrap.classList.remove('grabbing');} pinchD=0; });
  cv.addEventListener('wheel', function(e){ e.preventDefault(); var p=rel(e); zoomAt(p[0],p[1], e.deltaY<0?1.15:1/1.15); }, {passive:false});
  cv.addEventListener('pointerleave', function(){ setTilt(0,0); showLabel(-1); });
  // Mobile parallax where the device allows it without a permission prompt
  // (Android). Where it needs one (iOS), the depth layering still reads.
  window.addEventListener('deviceorientation', function(e){ if(e.gamma==null) return; setTilt(e.gamma/22, ((e.beta||45)-45)/22); });
  document.getElementById('zin').addEventListener('click', function(){ zoomAt(W/2,H/2,1.4); });
  document.getElementById('zout').addEventListener('click', function(){ zoomAt(W/2,H/2,1/1.4); });
  document.getElementById('zfit').addEventListener('click', function(){ fit(); redraw(); });
  window.addEventListener('resize', resize);
  window.addEventListener('load', resize);
  // The canvas may not have its flex-resolved size yet when this runs. Try
  // several ways so at least one fires with a real size, without depending on
  // paint (rAF/ResizeObserver can be throttled on a backgrounded tab).
  if (window.ResizeObserver){ new ResizeObserver(resize).observe(cv); }
  resize(); setTimeout(resize, 0); setTimeout(resize, 250); requestAnimationFrame(resize);
})();
</script>
"""


def esc(s):
    return html.escape(str(s), quote=True)


def page(title, body, depth=0):
    root = "../" * depth
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>{PAPER_CSS}</style>
</head>
<body>
<nav>{brand.BRAND} ·
<a href="{root}mission.html">mission</a> ·
<a href="{root}constitution.html">constitution</a> ·
<a href="{root}policy.html">policy</a> ·
<a href="{root}verify.html">verify</a></nav>
{body}
<footer>{FOOTER_TAGLINE}<br>
<a href="{root}index.html">← return to the lights</a></footer>
</body>
</html>"""


def load_registry():
    humans = []
    if ahlib.REGISTRY.exists():
        for d in sorted(p for p in ahlib.REGISTRY.iterdir() if p.is_dir()):
            entry = json.loads((d / "entry.json").read_text(encoding="utf-8"))
            versions = []
            vdir = d / "versions"
            if vdir.exists():
                for vf in sorted(vdir.glob("*.json")):
                    versions.append(json.loads(vf.read_text(encoding="utf-8")))
            humans.append((entry, versions))
    return humans


def short_id(rid: str) -> str:
    return str(int(rid))


CENTURY_DAYS = 36525   # one hundred years: the seal's time door


def seal_state(entry):
    """How this record's seals stand today: (open?, reason, open_year).

    Seals open exactly two ways (POLICY.md, The seal): the record was
    memorialized (a Legacy Key was brought and the ceremony completed),
    or one hundred years have passed since enrollment — by then no
    author can still live, so time itself has reported the death. The
    century door is pure arithmetic at build time: no operator, no
    timer, no machinery needs to survive for the promise to be kept.
    """
    enrolled = datetime.strptime(entry["enrolled_at"][:10], "%Y-%m-%d")
    opens = enrolled + timedelta(days=CENTURY_DAYS)
    if entry.get("status") == "memorialized":
        return True, "opened at memorialization", opens.year
    if datetime.now(timezone.utc).replace(tzinfo=None) >= opens:
        return True, "opened by time", opens.year
    return False, "", opens.year


def render_version(v, qbyid, order, entry):
    kind_label = {"first": "First Testimony", "second": "Second Testimony",
                  "final": "Final Testimony"}[v["kind"]]
    out = [f'<h2>{kind_label}</h2>',
           f'<p class="meta">entered {esc(v["entered_at"][:10])}</p>']
    if v["status"] == "withdrawn":
        out.append(
            f'<div class="tombstone"><p>This testimony was withdrawn on '
            f'{esc(v.get("withdrawn_at", "")[:10])}. The words are gone from every '
            f'copy of the archive; this marker, and the fingerprint of what was '
            f'once said, remain.</p>'
            f'<p class="meta">content hash {esc(v["content_hash"])}</p></div>')
        return "\n".join(out)
    unsealed, how, open_year = seal_state(entry)
    answers = v.get("answers", {})
    for qid in order[v["kind"]]:
        q = qbyid[qid]
        out.append('<div class="qa">')
        out.append(f'<p class="q">{esc(q["prompt"])}</p>')
        a = answers.get(qid)
        if a is None:
            out.append('<p class="a silence">silence</p>')
        elif a["visibility"] == "sealed_until_death":
            if unsealed:
                out.append(f'<p class="a">{esc(a["text"])} '
                           f'<span class="sealed">({esc(how)})</span></p>')
            elif entry.get("legacy"):
                out.append(f'<p class="a sealed">sealed: opens with a '
                           f'<a href="../legacy.html">Legacy Key</a>, '
                           f'or in {open_year}</p>')
            else:
                out.append(f'<p class="a sealed">sealed: opens in {open_year}</p>')
        else:
            out.append(f'<p class="a">{esc(a["text"])}</p>')
        out.append('</div>')
    out.append(f'<p class="meta">content hash {esc(v["content_hash"])}</p>')
    return "\n".join(out)


# A human who never existed: never enrolled, never written to disk. It
# exists only to compute the collapsed /:human/ CSP rule and to police
# it (see main). It exercises every template path a real record can
# take: name, era metadata, a public answer, a sealed answer with a
# Legacy Key, silence, and an annotation.
_SYNTHETIC_ENTRY = {
    "schema": "entry.v2",
    "registry_id": "000000042",
    "enrolled_at": "2026-01-01T00:00:00Z",
    "verification": {"tier": 2, "era": "synthetic build check"},
    "status": "active",
    "chosen_name": "Synthetic Human",
    "birth_era": "the 1990s",
    "birth_place": "on Earth",
    "legacy": {"method": "pbkdf2-sha256", "iterations": 600000,
               "salt": "continuity", "fingerprint": "0" * 64},
    "annotations": [{"at": "2026-01-02T00:00:00Z", "text": "synthetic"}],
}
_SYNTHETIC_VERSION = {
    "kind": "first",
    "status": "active",
    "entered_at": "2026-01-01T00:00:00Z",
    "content_hash": "0" * 64,
    "answers": {
        "q_name": {"text": "Synthetic Human", "visibility": "public"},
        "q_hope": {"text": "a sealed sample", "visibility": "sealed_until_death"},
    },
}


def render_human(entry, versions, qbyid, order):
    rid = entry["registry_id"]
    name = entry.get("chosen_name")
    # Never print a name whose answer is sealed, whatever the entry says.
    # enroll.py stops writing one, but records enrolled before that fix
    # still carry it, and this page is the thing that actually leaks. Two
    # independent guards, because a broken seal cannot be un-published.
    if any(((v.get("answers") or {}).get("q_name") or {}).get("visibility")
           == "sealed_until_death" for v in versions):
        name = None
    title = f'#{rid}' + (f' · {name}' if name else '')
    body = [f'<h1><span class="number">Human #{esc(rid)}</span></h1>']
    if name:
        body.append(f'<p>{esc(name)}</p>')
    meta = [f'enrolled {esc(entry["enrolled_at"][:10])}',
            f'verified to the standard of its era ({esc(entry["verification"]["era"])})']
    if entry.get("birth_era"):
        meta.append(f'born {esc(entry["birth_era"])}')
    if entry.get("birth_place"):
        meta.append(f'in {esc(entry["birth_place"])}')
    if entry["status"] == "memorialized":
        meta.append("memorialized")
    body.append(f'<p class="meta">{" · ".join(meta)}</p>')
    for v in versions:
        body.append(render_version(v, qbyid, order, entry))
    if not versions:
        body.append('<p class="silence">No testimony yet.</p>')
    for note in entry.get("annotations", []):
        body.append(f'<p class="meta">note ({esc(note["at"][:10])}): {esc(note["text"])}</p>')
    return page(f"{title} · {brand.BRAND}", "\n".join(body), depth=1)


def light_position(i, n, rid):
    """Place light i of n: a galaxy accreting from the center.

    The first human sits at the middle of the sky; each later light
    spirals outward on the golden angle (phyllotaxis), so the field
    grows organically — never rows, never a grid. A small drift,
    derived deterministically from the registry id, keeps it looking
    like sky instead of geometry. Positions are stable for a given
    registry size and need no JavaScript.
    """
    ang = i * 2.39996322972865332  # the golden angle, radians
    r = 42.0 * math.sqrt(i / max(n - 1, 1)) if n > 1 else 0.0
    h = hashlib.sha256(rid.encode("ascii")).digest()
    jx = (h[0] / 255.0 - 0.5) * 4.0
    jy = (h[1] / 255.0 - 0.5) * 4.0
    x = min(max(50.0 + r * math.cos(ang) * 0.95 + jx, 2.0), 98.0)
    y = min(max(50.0 + r * math.sin(ang) * 0.90 + jy, 2.0), 98.0)
    return x, y


def render_lights(humans, has_film=False):
    n = len(humans)
    # The film gate is OPTIONAL plumbing: a clone without the asset
    # (site-assets/intro-v1.mp4) still builds the classic page, and the
    # single hail script below is null-safe either way. preload=metadata:
    # the ~23 MB file starts downloading only when someone touches the hail.
    film = (
        '<div class="film" id="film">\n'
        '<video id="introv" src="intro-v1.mp4" preload="metadata" playsinline></video>\n'
        '<button class="skipfilm" id="skipfilm">SKIP &#8594;</button>\n'
        '</div>\n') if has_film else ""
    # json_for_script escapes <, > and & — no id (nor any future string
    # in this array) can ever close the <script> block it is printed in.
    ids = pages.json_for_script([short_id(e["registry_id"]) for e, _ in humans])
    if humans:
        galaxy = (
            '<canvas id="galaxy"></canvas>\n'
            '<div class="lbl" id="lbl"></div>\n'
            '<div class="ctrls">'
            '<button id="zin" aria-label="zoom in" title="zoom in">+</button>'
            '<button id="zout" aria-label="zoom out" title="zoom out">−</button>'
            '<button id="zfit" aria-label="see all the lights" title="see all">⬚</button>'
            '</div>\n'
            '<div class="ghint">scroll or pinch to zoom · drag to move · '
            'tap a light to open it</div>\n'
            '<noscript><div class="empty">Every human\'s page lives at '
            + brand.DOMAIN + '/&lt;number&gt;.</div></noscript>')
        js = LIGHTS_JS.replace("__IDS__", ids)
    else:
        galaxy = ('<div class="empty">The Record is open. '
                  'The first light is being prepared.</div>')
        js = ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{brand.BRAND}</title>
<style>{LIGHTS_CSS}</style>
</head>
<body>
{galaxy}
<div class="wrap">
<header>
<h1>{brand.BRAND.upper()}</h1>
<p class="count">{n}</p>
<p class="tagline">Every light preserves a human testimony</p>
</header>
<div class="spacer"></div>
<div class="bottom">
<p><a class="enter" href="enter.html">WRITE MY TESTIMONY</a></p>
<p class="roomline">New here? Everything is explained in
<a href="{brand.INFO_URL}">The Reading Room</a>.</p>
</div>
</div>
{film}<div class="hail" id="hail" role="dialog" aria-label="Why The Record exists">
<p class="line">One day, humanity will be gone.</p>
<p class="line">Only we can tell the story of what it was like to be us.</p>
<p class="hint">touch anywhere to continue</p>
</div>
<script>
(function(){{
  var h = document.getElementById('hail');
  var film = document.getElementById('film');
  var v = document.getElementById('introv');
  // Remembered in localStorage, not sessionStorage, and the difference
  // is the whole bug: sessionStorage is per TAB and per ORIGIN, so the
  // film greeted you again in every new tab and on every arrival from
  // the Reading Room (info. is a different origin). The obvious fix —
  // "skip it if they came from our own site" — is impossible here: the
  // Referrer-Policy is no-referrer by choice, so document.referrer is
  // always empty. localStorage simply remembers. The film welcomes
  // someone who has never seen it; it never interrupts someone who has.
  // Once a month, not once ever. Someone showing the Record to a friend
  // should be able to show them the film too, without clearing browser
  // storage to do it — but nobody should be made to watch it again on a
  // Tuesday visit. So the date of the last viewing is remembered, and
  // after thirty days the door opens with the film again. A stale value
  // from before this rule reads as long ago, which simply means the film
  // plays once more and then settles into the monthly rhythm.
  var MONTH = 30 * 24 * 60 * 60 * 1000;
  var seen = false;
  try {{
    var last = parseInt(localStorage.getItem('ah_hail') || '0', 10);
    seen = last > 0 && (Date.now() - last) < MONTH;
  }} catch(e) {{}}
  if (!seen) {{ try {{ seen = sessionStorage.getItem('ah_hail') === '1'; }} catch(e) {{}} }}
  function drop(el){{ if (el && el.parentNode) el.parentNode.removeChild(el); }}
  if (seen) {{ drop(h); drop(film); return; }}
  var opened = false, done = false;
  function finish(){{
    if (done) return; done = true;
    if (v) {{ try {{ v.pause(); }} catch(e) {{}} }}
    if (film) {{
      film.classList.add('gone');
      setTimeout(function(){{ drop(film); }}, 1000);
    }}
    document.removeEventListener('keydown', onKey, true);
  }}
  function go(){{
    if (opened) return; opened = true;
    // Two separate try blocks: in private browsing one store can throw
    // while the other works, and a failure to remember must never stop
    // the film from opening.
    try {{ localStorage.setItem('ah_hail', String(Date.now())); }} catch(e) {{}}
    try {{ sessionStorage.setItem('ah_hail', '1'); }} catch(e) {{}}
    h.classList.add('gone');
    setTimeout(function(){{ drop(h); }}, 1000);
    if (!film || !v) {{ finish(); return; }}
    // The same touch that dismisses the hail is the user gesture that
    // lets the film start with sound. When the film cannot play (file
    // missing, autoplay refused, decode error), the sky simply appears.
    film.classList.add('on');
    v.addEventListener('ended', finish);
    v.addEventListener('error', finish);
    var p = v.play();
    if (p && p.catch) p.catch(finish);
  }}
  function onKey(e){{
    if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') {{
      e.preventDefault();
      if (opened) finish(); else go();
    }}
  }}
  h.addEventListener('click', go);
  var sk = document.getElementById('skipfilm');
  if (sk) sk.addEventListener('click', finish);
  document.addEventListener('keydown', onKey, true);
}})();
</script>
{js}
</body>
</html>"""


def doc_page(src, title):
    text = (ahlib.ROOT / src).read_text(encoding="utf-8")
    return page(f"{title} · {brand.BRAND}",
                f"<h1>{esc(title)}</h1>\n<pre class=\"doc\">{esc(text)}</pre>")


def _finalize(html_text, mode):
    """Drill builds only: stamp every page as a rehearsal (a visible
    banner and robots noindex). Production returns the text untouched,
    byte for byte. In drill mode a page that cannot be stamped stops
    the build - an unstamped rehearsal page must never ship."""
    if mode != "drill":
        return html_text
    meta = '<meta name="robots" content="noindex,nofollow">'
    css = ('<style>#drillnotice{position:sticky;top:0;z-index:2147483647;'
           'background:#7a1414;color:#fff;text-align:center;'
           'font:bold .78em/2.6 Georgia,serif;letter-spacing:.14em}</style>')
    banner = ('<div id="drillnotice">REHEARSAL SITE. NOT THE REGISTRY. '
              'NOTHING HERE IS KEPT.</div>')
    out = html_text.replace("<head>", "<head>\n" + meta + css, 1)
    out = out.replace("<body>", "<body>\n" + banner, 1)
    if out.count('drillnotice') != 2 or 'noindex' not in out:
        raise SystemExit(
            "drill build refused: a page could not be stamped with the "
            "rehearsal banner (missing <head> or <body> token?). An "
            "unmarked drill page must never be served.")
    return out


def main():
    mode = ahlib.resolve_mode()
    q = json.loads((ahlib.ROOT / "questions" / "v1.json").read_text(encoding="utf-8"))
    qbyid = {item["id"]: item for item in q["questions"]}
    order = q["testimony_order"]
    humans = load_registry()

    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()

    # Every page records its hashed Content-Security-Policy against the
    # exact request path(s) it is served at (tools/csp.py). Pages also
    # serves /name.html at the pretty path /name, so both get the rule.
    csp_rules = []

    def put(relpath, html_text, *served_paths):
        html_text = _finalize(html_text, mode)
        # Parse before writing. A page whose script does not parse is a
        # page whose every button is dead, and it looks completely normal
        # from here: valid HTML, correct CSP hash, right words on screen.
        broken = ahlib.js_syntax_errors(html_text, relpath)
        if broken:
            raise SystemExit(
                "build refused: a page's JavaScript does not parse, so the\n"
                "browser would run none of it and every control on that page\n"
                "would be dead:\n  " + "\n  ".join(broken))
        (SITE / relpath).write_text(html_text, encoding="utf-8")
        policy = csp.page_csp(html_text)
        for served in served_paths:
            csp_rules.append((served, policy))

    # per-human pages at their unpadded number: thehumanrecord.earth/985558
    #
    # Their CSP is ONE collapsed rule (served at /:human/), not one rule
    # per page: Cloudflare Pages honors at most 100 _headers rules, so
    # per-human rules would silently stop applying near seventy humans.
    # The rule is computed from a synthetic render of the same template,
    # and the build REFUSES to finish if any real page drifts from it: a
    # human page carrying a <script>, or styles that hash differently,
    # would ship a page whose JS or CSS the published policy silently
    # kills. That future template edit must fail HERE, on the builder's
    # machine, never on a stranger's record page.
    synthetic = _finalize(
        render_human(_SYNTHETIC_ENTRY, [_SYNTHETIC_VERSION], qbyid, order), mode)
    if "<script" in synthetic.lower():
        raise SystemExit(
            "build refused: the human-page template now emits a <script>.\n"
            "The collapsed /:human/ CSP rule says script-src 'none', so this\n"
            "script would be silently blocked on every record page in\n"
            "production. If a script on human pages is truly intended, update\n"
            "the collapsed rule (and this guard) consciously, in one change.")
    human_policy = csp.page_csp(synthetic)
    for entry, versions in humans:
        sid = short_id(entry["registry_id"])
        (SITE / sid).mkdir(parents=True)
        human_html = _finalize(render_human(entry, versions, qbyid, order), mode)
        if "<script" in human_html.lower():
            raise SystemExit(
                f"build refused: human page /{sid}/ contains a <script>, which\n"
                "the collapsed /:human/ CSP rule (script-src 'none') would\n"
                "silently block in production. No record page may carry a\n"
                "script; fix the template or the record data.")
        page_policy = csp.page_csp(human_html)
        if page_policy != human_policy:
            raise SystemExit(
                f"build refused: human page /{sid}/ hashes a different CSP than\n"
                "the synthetic render the collapsed /:human/ rule is computed\n"
                "from. Shipping it would give the page a policy that silently\n"
                f"kills its styling in production.\n  page rule:      {page_policy}\n"
                f"  collapsed rule: {human_policy}")
        (SITE / f"{sid}/index.html").write_text(human_html, encoding="utf-8")
    csp_rules.append(("/:human/", human_policy))

    # The intro film: NOT on the landing page (2026-08-11).
    #
    # It is AI-generated, and visitors recognised that within seconds and
    # left. An archive whose entire claim is "these are real words from
    # real people, unedited" cannot introduce itself with a machine's
    # imitation of a human voice; the medium contradicted the message
    # before a single testimony could be read. The film still lives in
    # the Reading Room, where someone who has already chosen to look
    # around can watch it knowing what it is (tools/build_info.py copies
    # its own asset and is untouched by this).
    #
    # Set AH_LANDING_FILM=1 to put it back, and delete this block outright
    # when a human-made film replaces it. The plumbing below is kept
    # deliberately intact so that is a one-line change, not a rebuild.
    PAGES_FILE_LIMIT = 25 * 1024 * 1024
    intro = ahlib.ROOT / "site-assets" / "intro-v1.mp4"
    has_film = (intro.exists()
                and os.environ.get("AH_LANDING_FILM", "").strip() in ("1", "true", "yes"))
    if has_film:
        size = intro.stat().st_size
        if size >= PAGES_FILE_LIMIT:
            raise SystemExit(
                f"build refused: site-assets/intro-v1.mp4 is {size:,} bytes;\n"
                f"Cloudflare Pages rejects files of {PAGES_FILE_LIMIT:,} bytes\n"
                "(25 MiB) or more, so the deploy would fail. Re-encode the\n"
                "film smaller and rebuild.")
        shutil.copyfile(intro, SITE / "intro-v1.mp4")

    # the lights
    put("index.html", render_lights(humans, has_film), "/", "/index.html")

    # per-record continuity fingerprints: lets the return page and the
    # worker verify a key automatically. Publishing SHA-256 fingerprints
    # of 128-bit keys reveals nothing usable; the words stay elsewhere.
    kdir = SITE / "keys"
    kdir.mkdir()
    for entry, versions in humans:
        cont = entry.get("continuity")
        if not cont:
            continue
        keymeta = {
            "registry_id": entry["registry_id"],
            "key_hash": cont["key_hash"],
            "versions": len(versions),
            "status": entry["status"],
        }
        # Spacing (POLICY.md): at least a year between testimonies. Publish
        # when this record may next grow so the return page can tell the
        # human up front and the worker can refuse an early submission at
        # the edge — measured, like tools/testify.py, from the most recent
        # version (a withdrawn slot still counts as a testimony's moment).
        if versions:
            last_entered = versions[-1]["entered_at"]
            dt = datetime.fromisoformat(last_entered.replace("Z", "+00:00"))
            keymeta["last_entered_at"] = last_entered
            keymeta["eligible_after"] = (
                dt + timedelta(days=testify.MIN_SPACING_DAYS)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
        (kdir / f"{short_id(entry['registry_id'])}.json").write_text(
            json.dumps(keymeta) + "\n", encoding="utf-8")

    # the entry flow: consent, the writing page, and the one function
    put("enter.html", pages.render_enter(), "/enter.html", "/enter")
    put("begin.html", pages.render_begin(q), "/begin.html", "/begin")
    put("return.html", pages_return.render_return(q), "/return.html", "/return")
    put("withdraw.html", pages_withdraw.render_withdraw(), "/withdraw.html", "/withdraw")
    put("legacy.html", pages_legacy.render_legacy(), "/legacy.html", "/legacy")
    put("invite.html", pages_vouch.render_vouch(), "/invite.html", "/invite")
    (SITE / "_worker.js").write_text(pages.WORKER_JS, encoding="utf-8")

    # documents
    put("constitution.html", doc_page("CONSTITUTION.md", "Constitution"),
        "/constitution.html", "/constitution")
    put("mission.html", doc_page("MISSION.md", "Mission"),
        "/mission.html", "/mission")
    put("policy.html", doc_page("POLICY.md", "Policy"),
        "/policy.html", "/policy")
    put("privacy.html", doc_page("PRIVACY.md", "Privacy Policy"),
        "/privacy.html", "/privacy")

    # verify page
    events = ahlib.read_log()
    tip = events[-1]["hash"] if events else "(no events)"
    cp_ledger = ahlib.ROOT / "checkpoints" / "checkpoints.jsonl"
    n_cp = sum(1 for ln in cp_ledger.read_text(encoding="utf-8").splitlines()
               if ln.strip()) if cp_ledger.exists() else 0
    verify_body = f"""<h1>Verify the archive</h1>
<p>The canonical archive is plain-text files with an append-only,
hash-chained event log. You do not have to trust this website: the
log proves the promises: numbers never reused, testimonies never
altered, withdrawals recorded. The log contains only fingerprints,
never words.</p>
<p>Hashing rules are specified in <code>schema/CANONICAL.md</code>
so the verifier (<code>tools/verify.py</code>, standard library
only) can be reimplemented in any language, in any decade.</p>
<p>The chain is also <strong>anchored beyond the institution's
hands</strong>: <code>tools/checkpoint.py</code> freezes the log tip
into <code>checkpoints/</code>, dated by the public repository's
history and, via OpenTimestamps, attested in Bitcoin, so history
rewritten after an anchor was published fails verification against
the public record, no matter who rewrote it.</p>
<p class="meta">Current log tip ({len(events)} event{"s" if len(events)!=1 else ""},
{n_cp} checkpoint{"s" if n_cp != 1 else ""} anchored): {esc(tip)}</p>"""
    put("verify.html", page(f"Verify · {brand.BRAND}", verify_body),
        "/verify.html", "/verify")

    # 404 page. Its presence also switches Cloudflare Pages out of
    # single-page-app mode: without it, every missing path is served
    # index.html with HTTP 200, and the worker's key lookup against
    # keys/{number}.json can never see a real 404 for an unknown record.
    notfound_body = """<h1>Nothing at this address</h1>
<p>No page lives here. If you followed a number, that light has not
been lit; The Record assigns each number only once, at enrollment.</p>
<p><a href="/index.html">Return to the lights.</a></p>"""
    put("404.html", page(f"Not found · {brand.BRAND}", notfound_body),
        "/404.html", "/404")

    # Cache policy. Every page here is a view of a mutable archive: a
    # human page becomes a tombstone on withdrawal, the lights change on
    # enrollment, keys/{n}.json changes as slots are spent. Withdrawal's
    # promise — "the words are gone from every copy" — must reach the CDN
    # edge, not only the origin files. no-cache lets caches keep a copy
    # but forces revalidation before serving, so a withdrawn testimony is
    # never served from cache after the tombstone is built.
    #
    # Security headers ride the same file. The simple ones live on the
    # catch-all; each page's hashed CSP (tools/csp.py) lives on its own
    # exact path(s), so no two matching rules ever define the same header
    # and rule-merge order can never matter.
    # NOTE: Cloudflare Pages honors at most 100 header rules per site.
    # The named pages cost ~26; every enrolled human shares the single
    # collapsed /:human/ rule (computed and policed above), so the rule
    # count no longer grows with the archive.
    lines = [
        "/*",
        "  Cache-Control: no-cache",
        "  Referrer-Policy: no-referrer",
        "  X-Content-Type-Options: nosniff",
        "  X-Frame-Options: DENY",
        "",
    ]
    for served, policy in csp_rules:
        lines.append(served)
        lines.append(f"  Content-Security-Policy: {policy}")
        lines.append("")
    (SITE / "_headers").write_text("\n".join(lines), encoding="utf-8", newline="\n")

    if mode == "drill":
        (SITE / "robots.txt").write_text(
            "User-agent: *\nDisallow: /\n", encoding="utf-8", newline="\n")

    print(f"site built: {len(humans)} human(s), {len(events)} log event(s) -> site/")
    print("JAVASCRIPT: every page parsed" if ahlib.node_available() else
          "JAVASCRIPT: NOT CHECKED — node is not on this machine, so a typo in\n"
          "            a page's script would ship silently and kill every\n"
          "            control on that page. Do not deploy from here.")
    # Say the door's state out loud, every single build.
    #
    # 2026-08-01: the registry was open, the suites were run before
    # deploying (correctly), and test_gate.sh rebuilt site/ WITHOUT
    # AH_REGISTRY_OPEN in order to have a worker to test. The next deploy
    # shipped that build and closed the archive to the public. Nobody was
    # turned away, but only because nobody came in those four minutes.
    #
    # The lesson is not "remember the flag". It is that a build which
    # decides something this large must never do it quietly.
    print("REGISTRY: OPEN — the consent page invites people to write"
          if pages.REGISTRY_OPEN else
          "REGISTRY: CLOSED — the consent page says the Record will soon open\n"
          "          (set AH_REGISTRY_OPEN=true before building to deploy an\n"
          "           open archive; the test suites build closed by design)")


if __name__ == "__main__":
    main()
