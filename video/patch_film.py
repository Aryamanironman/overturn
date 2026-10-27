"""One-off patch: add explanation and motion to the OVERTURN film template."""

from pathlib import Path

path = Path(__file__).with_name("film.html")
s = path.read_text(encoding="utf-8")

CSS = """
.verdict-stamp{position:absolute;right:0;bottom:-6px;border:5px solid var(--green);color:var(--green);
  padding:2px 16px 8px;font:400 56px/0.95 var(--display);letter-spacing:-.02em;transform:rotate(-2deg);
  opacity:0;visibility:hidden;z-index:2}
.evidence-strip{display:flex;flex-wrap:wrap;gap:8px;margin-top:24px;max-width:1520px}
.evidence-chip{font:13px/1.4 var(--mono);color:#344551;background:#ffffff;border:1px solid var(--rule);padding:6px 9px}
.agent-loop{display:flex;align-items:center;flex-wrap:wrap;gap:10px;margin-top:26px}
.agent-chip{font:600 15px/1.3 var(--sans);border:1px solid var(--rule);background:#fff;padding:8px 12px;color:#344551}
.agent-chip[data-agent="Reconciler"]{border-color:var(--blue);color:var(--blue)}
.agent-chip[data-agent="Critic"]{border-color:var(--amber);color:var(--amber)}
.agent-chip[data-agent="Advocate"]{border-color:var(--red);color:var(--red)}
.agent-chip[data-agent="Reporter"]{border-color:var(--green);color:var(--green)}
.arrow{font:16px var(--mono);color:var(--muted)}
.loopback{font:12px/1.3 var(--mono);color:var(--blue);border:1px dashed var(--blue);padding:6px 8px}
.sponsors{display:flex;gap:26px;flex-wrap:wrap;margin-top:30px;font:600 13px/1.3 var(--sans);
  letter-spacing:.16em;text-transform:uppercase;color:#8fa0ad}
#case-tag{position:absolute;top:48px;right:140px;font:600 12px/1.4 var(--sans);
  letter-spacing:.16em;text-transform:uppercase;color:var(--muted);z-index:5}
"""
s = s.replace(
    ".frame{position:relative;z-index:1;max-width:1680px}",
    ".frame{position:relative;z-index:1;max-width:1680px}" + CSS,
)

s = s.replace(
    '<div id="spine-label">ONE LEDGER</div>',
    '<div id="spine-label">ONE EVIDENCE FILE</div>\n'
    '  <div id="case-tag">CASE CLM-2026-0915 · NORTHBRIDGE HEALTH</div>',
)

s = s.replace(
    "  let body = '';\n  switch (scene.layout) {",
    """  const evidence = (scene.evidence || []).map(item => `<span class="evidence-chip">${esc(item)}</span>`).join('');
  const evidenceHtml = evidence ? `<div class="evidence-strip">${evidence}</div>` : '';
  const stampHtml = scene.stamp ? `<div class="verdict-stamp">${esc(scene.stamp)}</div>` : '';
  const sponsorItems = (scene.sponsors || []).map(item => `<span>${esc(item)}</span>`).join('');
  const sponsorsHtml = sponsorItems ? `<div class="sponsors">${sponsorItems}</div>` : '';
  let body = '';
  switch (scene.layout) {""",
)

s = s.replace(
    "    case 'number':",
    """    case 'loop':
      body = `<h2 class="big">${lines(scene.big)}</h2>
        <div class="agent-loop">
          <span class="agent-chip" data-agent="Planner">Planner</span><span class="arrow">→</span>
          <span class="agent-chip" data-agent="Reconciler">Reconciler</span><span class="arrow">→</span>
          <span class="agent-chip" data-agent="Critic">Critic</span><span class="arrow">→</span>
          <span class="agent-chip" data-agent="Advocate">Advocate</span><span class="arrow">→</span>
          <span class="agent-chip" data-agent="Reporter">Reporter</span>
          <span class="loopback">re-query ⟲</span>
        </div>`;
      break;
    case 'number':""",
)

s = s.replace(
    '<div class="score">${esc(scene.big)}</div>',
    '<div class="score" data-score="${esc(scene.big)}">0</div>',
)

s = s.replace(
    '<div class="frame">${kicker}${body}</div>',
    '<div class="frame">${kicker}${body}${evidenceHtml}${stampHtml}${sponsorsHtml}</div>',
)

s = s.replace(
    "  if (scene.layout === 'question') {",
    """  const chips = el.querySelectorAll('.evidence-chip');
  if (chips.length) {
    tl.fromTo(chips, {autoAlpha:0, y:10}, {autoAlpha:1, y:0, duration:0.45, stagger:0.08, ease:'power2.out'}, start + 0.55);
  }
  const stampEl = el.querySelector('.verdict-stamp');
  if (stampEl) {
    const stampAt = voiceAt + (scene.stampAt || 2.6);
    tl.fromTo(stampEl, {autoAlpha:0, scale:1.35, rotation:-10},
      {autoAlpha:1, scale:1, rotation:-2, duration:0.5, ease:'back.out(1.6)'}, stampAt);
  }
  if (scene.layout === 'loop') {
    tl.fromTo(el.querySelectorAll('.agent-chip'), {autoAlpha:0, y:14},
      {autoAlpha:1, y:0, duration:0.35, stagger:0.14, ease:'power2.out'}, start + 0.35);
    tl.fromTo(el.querySelector('.loopback'), {autoAlpha:0, x:-12},
      {autoAlpha:1, x:0, duration:0.45, ease:'power2.out'}, start + 1.35);
  }
  const sponsorEls = el.querySelectorAll('.sponsors span');
  if (sponsorEls.length) {
    tl.fromTo(sponsorEls, {autoAlpha:0}, {autoAlpha:1, duration:0.5, stagger:0.1}, start + 0.6);
  }

  if (scene.layout === 'question') {""",
)

s = s.replace(
    """  if (scene.layout === 'score') {
    const ring = el.querySelector('#ring-story');
    if (ring) tl.to(ring, {attr:{'stroke-dashoffset':1495.4 * 0.15}, duration:1.8, ease:'power2.out'}, start + 0.35);
  }""",
    """  if (scene.layout === 'score') {
    const ring = el.querySelector('#ring-story');
    if (ring) tl.to(ring, {attr:{'stroke-dashoffset':1495.4 * 0.15}, duration:1.8, ease:'power2.out'}, start + 0.35);
    const scoreEl = el.querySelector('.score');
    const target = Number(scene.big);
    if (scoreEl && target) {
      const counter = {v:0};
      tl.to(counter, {v:target, duration:1.3, ease:'power2.out',
        onUpdate: () => { scoreEl.textContent = String(Math.round(counter.v)); }}, start + 0.4);
    }
  }""",
)

s = s.replace(
    """  if (scene.layout === 'mark') {
    tl.to('#signature-story', {autoAlpha:1, duration:0.7, ease:'power2.out'}, S.total - 1.35);
  }""",
    """  if (scene.layout === 'mark') {
    tl.to('#case-tag', {autoAlpha:0, duration:0.4}, start);
    tl.to('#signature-story', {autoAlpha:1, duration:0.7, ease:'power2.out'}, S.total - 1.35);
  }""",
)

path.write_text(s, encoding="utf-8")
print("patched film.html")
