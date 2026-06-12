"""
FPL Presentation Generator
Reads fpl_data.json (produced by fpl_analyse.py) and builds the Reveal.js + D3 presentation.

Usage:
    uv run fpl_export.py
    uv run fpl_export.py --input fpl_data.json --output fpl_presentation.html

Pipeline:
    fpl_fetch.py → fpl_raw.json → fpl_analyse.py → fpl_data.json → fpl_export.py → fpl_presentation.html
"""

import argparse
import json
import webbrowser

INPUT_DATA = "fpl_data.json"
OUTPUT_HTML = "docs/index.html"


# ── HTML template ──────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>FPL Season</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>👨🏻</text></svg>" />

  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@4.6.1/dist/reveal.css" />
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@4.6.1/dist/theme/black.css" />

  <style>
    :root {
      --bg:     #0e0e1a;
      --purple: #38003c;
      --teal:   #00d2be;
      --dim:    rgba(255,255,255,0.40);
      --mid:    rgba(255,255,255,0.65);
    }

    /* ── Global ── */
    .reveal, .reveal .slides { background: var(--bg); }
    .reveal .slides section  { background: var(--bg); height: 100%; }
    .reveal h2 { font-size: 1.15em; color: #fff; font-weight: 900; margin-bottom: .4em; text-transform: none; letter-spacing: 0; }

    /* ── Slide 1: Title ── */
    .title-league { font-size: 2em; font-weight: 900; color: #fff; line-height: 1.1; }
    .title-season { font-size: 1em; color: var(--teal); margin: .3em 0 1.2em; }
    .mgr-cards { display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; }
    .mgr-card  {
      background: rgba(255,255,255,.05); border-radius: 12px; padding: 18px 24px;
      border-left: 4px solid currentColor; min-width: 160px; text-align: left;
    }
    .mgr-card .medal { font-size: 1.6em; }
    .mgr-card .mname { font-size: .78em; font-weight: 700; color: #fff; margin: 5px 0 2px; }
    .mgr-card .tname { font-size: .62em; color: var(--dim); }
    .mgr-card .mpts  { font-size: 1.1em; font-weight: 900; margin-top: 8px; }

    /* ── Slide 2: Race ── */
    #race-controls { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
    .rbtn {
      background: var(--purple); color: #fff;
      border: 1px solid rgba(255,255,255,.2); border-radius: 6px;
      padding: 5px 14px; font-size: .78em; cursor: pointer; white-space: nowrap;
    }
    .rbtn:hover { background: #5a006a; }
    #gw-slider {
      flex: 1; -webkit-appearance: none; height: 3px;
      border-radius: 2px; background: rgba(255,255,255,.15); outline: none;
    }
    #gw-slider::-webkit-slider-thumb {
      -webkit-appearance: none; width: 13px; height: 13px;
      border-radius: 50%; background: var(--teal); cursor: pointer;
    }
    #gw-lbl { color: var(--dim); font-size: .72em; min-width: 72px; text-align: right; }

    /* D3 race elements */
    .bar-name   { font: 700 17px Arial, sans-serif; }
    .bar-val    { font: 900 17px "Arial Black", Arial, sans-serif; fill: rgba(255,255,255,.85); }
    .chip-tag   { font: 700 10px Arial, sans-serif; }
    .x-tick     { font: 11px Arial, sans-serif; fill: rgba(255,255,255,.3); }
    .grid-line  { stroke: rgba(255,255,255,.07); stroke-width: 1; }
    .gw-counter { font: 900 88px "Arial Black", Arial, sans-serif; fill: rgba(255,255,255,.09); }
    .total-lbl  { font: 600 14px Arial, sans-serif; fill: rgba(255,255,255,.28); }

    /* ── Slide 3: Podium ── */
    .podium-wrap { display: flex; align-items: flex-end; justify-content: center; gap: 14px; margin-top: .4em; }
    .podium-col  { display: flex; flex-direction: column; align-items: center; gap: 6px; }
    .podium-col .p-medal { font-size: 1.8em; }
    .podium-col .p-pts   { font-size: 1.2em; font-weight: 900; }
    .podium-col .p-name  { font-size: .72em; font-weight: 700; color: #fff; }
    .podium-col .p-team  { font-size: .58em; color: var(--dim); margin-top: 2px; }
    .podium-block { border-radius: 8px 8px 0 0; width: 150px; }

    /* ── Slide 4: Stats ── */
    .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: .4em; }
    .stat-card  { background: rgba(255,255,255,.05); border-radius: 10px; padding: 16px 18px; text-align: left; }
    .s-label    { font-size: .55em; color: var(--dim); text-transform: uppercase; letter-spacing: 1px; }
    .s-value    { font-size: 1.45em; font-weight: 900; color: #fff; margin: 3px 0 2px; }
    .s-sub      { font-size: .6em; color: var(--dim); }
    .s-row      { display: flex; align-items: center; gap: 7px; margin: 5px 0; font-size: .68em; }
    .s-dot      { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
    .s-val      { margin-left: auto; font-weight: 700; }

    /* ── Slide 5: Chips ── */
    #chip-wrap  { margin-top: .6em; }
    .cl-row     { margin-bottom: 18px; }
    .cl-who     { font-size: .65em; font-weight: 700; margin-bottom: 4px; }
    .cl-axis    { position: relative; height: 46px; }
    .cl-line    { position: absolute; left: 0; right: 0; top: 13px; height: 2px; background: rgba(255,255,255,.08); border-radius: 1px; }
    .cl-dot     { position: absolute; top: 0; transform: translateX(-50%); display: flex; flex-direction: column; align-items: center; gap: 2px; }
    .cl-circle  { width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: .5em; font-weight: 900; color: #000; }
    .cl-gwnum   { font-size: .42em; color: var(--dim); }
    .cl-gwtick  { position: absolute; top: 20px; transform: translateX(-50%); font-size: .4em; color: rgba(255,255,255,.18); }

    /* ── Slide 6: Top Players ── */
    .tp-slide       { display: flex !important; flex-direction: column; overflow: hidden; }
    .tp-scroll-wrap { overflow-y: auto; flex: 1; padding-right: 6px; }
    .tp-scroll-wrap::-webkit-scrollbar       { width: 4px; }
    .tp-scroll-wrap::-webkit-scrollbar-track { background: transparent; }
    .tp-scroll-wrap::-webkit-scrollbar-thumb { background: rgba(255,255,255,.18); border-radius: 2px; }
    .tp-grid  { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: .4em; }
    .tp-col   { background: rgba(255,255,255,.04); border-radius: 10px; padding: 10px 12px; }
    .tp-head  { font-size: .68em; font-weight: 700; border-bottom: 1px solid rgba(255,255,255,.08); padding-bottom: 6px; margin-bottom: 8px; }
    .tp-sub   { font-size: .55em; font-weight: 400; color: var(--dim); }
    .tp-card  { margin-bottom: 6px; padding-bottom: 6px; border-bottom: 1px solid rgba(255,255,255,.05); }
    .tp-card:last-child { margin-bottom: 0; padding-bottom: 0; border-bottom: none; }
    .tp-row1  { display: flex; align-items: center; gap: 5px; flex-wrap: wrap; }
    .tp-medal { font-size: .85em; flex-shrink: 0; }
    .tp-name  { font-size: .8em; font-weight: 700; color: #fff; }
    .tp-badge { font-size: .52em; color: rgba(255,255,255,.4); background: rgba(255,255,255,.08); padding: 1px 5px; border-radius: 3px; white-space: nowrap; }
    .tp-row2  { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; margin-top: 2px; }
    .tp-pts   { font-size: 1.05em; font-weight: 900; white-space: nowrap; }
    .tp-period { font-size: .55em; color: var(--dim); }
    /* Transfer in/out indicators */
    .tp-in    { color: #32cd32; font-weight: 700; }
    .tp-out   { color: #e8002d; font-weight: 700; }

    /* ── Slide 7: Race Decided ── */
    .dc-lead       { margin-top: .1em; }
    .dc-lead svg   { width: 100%; height: auto; display: block; }
    .dc-grid       { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-top: 6px; }
    .dc-card       { background: rgba(255,255,255,.04); border-radius: 8px; padding: 7px 10px; }
    .dc-card-title { font-size: .56em; color: var(--dim); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 2px; }
    .dc-card-sub   { font-size: .5em; color: rgba(255,255,255,.25); margin-bottom: 3px; font-style: italic; }
    .dc-extra      { font-size: .48em; color: rgba(255,255,255,.3); margin: -1px 0 1px 12px; }
    .dc-row        { display: flex; align-items: center; gap: 5px; margin: 2px 0 0; font-size: .64em; }
    .dc-dot        { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
    .dc-name       { flex: 1; color: rgba(255,255,255,.6); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .dc-val        { font-weight: 400; color: var(--dim); white-space: nowrap; margin-left: 4px; }
    .dc-bar-wrap   { height: 3px; background: rgba(255,255,255,.07); border-radius: 2px; margin-bottom: 2px; }
    .dc-mini-bar   { height: 100%; border-radius: 2px; transition: width .3s; }
    .dc-winner .dc-name { color: #fff !important; font-weight: 700; }
    .dc-winner .dc-val  { font-weight: 900; }
    .dc-verdict    { font-size: .62em; color: var(--dim); text-align: center; margin-top: 5px; line-height: 1.5; font-style: italic; }
  </style>
</head>
<body>

<div class="reveal">
 <div class="slides">

  <!-- ① Title ──────────────────────────────────────────────────────────── -->
  <section data-background-color="#0e0e1a">
    <p class="title-league" id="t-name"></p>
    <p class="title-season" id="t-season"></p>
    <p class="title-season" style="color:#e8b86d">Het seizoen van de snor 👨🏻</p>
  </section>

  <!-- ② Race ───────────────────────────────────────────────────────────── -->
  <section data-background-color="#0e0e1a" id="race-slide">
    <h2>📈 Puntenrace</h2>
    <div id="race-controls">
      <button class="rbtn" id="btn-play">▶ Start</button>
      <button class="rbtn" id="btn-restart">↺</button>
      <input type="range" id="gw-slider" min="0" value="0" />
      <span id="gw-lbl">GW 0</span>
    </div>
    <div id="race-svg-wrap"></div>
  </section>

  <!-- ③ Podium ─────────────────────────────────────────────────────────── -->
  <section data-background-color="#0e0e1a">
    <h2>🏆 Eindstand</h2>
    <div class="podium-wrap" id="podium"></div>
  </section>

  <!-- ④ Stats ──────────────────────────────────────────────────────────── -->
  <section data-background-color="#0e0e1a">
    <h2>📊 Het seizoen in cijfers</h2>
    <div class="stats-grid" id="stats-grid"></div>
  </section>

  <!-- ⑤ Chips ──────────────────────────────────────────────────────────── -->
  <section data-background-color="#0e0e1a">
    <h2>🃏 Chip tijdlijn</h2>
    <div id="chip-wrap"></div>
  </section>

  <!-- ⑥ Race Decided ─────────────────────────────────────────────────── -->
  <section data-background-color="#0e0e1a">
    <h2>🎯 Waar werd het seizoen beslist?</h2>
    <div class="dc-lead" id="dc-lead"></div>
    <div class="dc-grid" id="dc-grid"></div>
    <p class="dc-verdict" id="dc-verdict"></p>
  </section>

  <!-- ⑦ Top Players ────────────────────────────────────────────────────── -->
  <section class="tp-slide" data-background-color="#0e0e1a">
    <h2>⭐ Beste spelers van het seizoen</h2>
    <div class="tp-scroll-wrap">
      <div class="tp-grid" id="tp-grid"></div>
    </div>
  </section>

 </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/reveal.js@4.6.1/dist/reveal.js"></script>
<script>
// ── Embedded data ─────────────────────────────────────────────────────────────
const DATA = /*DATA_PLACEHOLDER*/;

const MEDALS = ['🥇','🥈','🥉','4','5'];

// ── Slide 1: Title ────────────────────────────────────────────────────────────
document.getElementById('t-name').textContent   = DATA.league.name;
document.getElementById('t-season').textContent = 'FPL ' + DATA.league.season;

// ── Slide 3: Podium ───────────────────────────────────────────────────────────
(function () {
  const order = [1, 0, 2], heights = [150, 190, 110];
  order.forEach((rank, col) => {
    const m = DATA.managers[rank];
    const el = document.createElement('div');
    el.className = 'podium-col';
    el.innerHTML = `
      <div class="p-medal">${MEDALS[rank]}</div>
      <div class="p-pts" style="color:${m.color}">${m.cumulative[m.cumulative.length-1]}</div>
      <div class="p-name">${m.name.split(' ')[0]}</div>
      <div class="p-team">${m.team_name}</div>
      <div class="podium-block" style="height:${heights[col]}px;background:${m.color}22;border-top:4px solid ${m.color}"></div>`;
    document.getElementById('podium').appendChild(el);
  });
})();

// ── Slide 4: Stats ────────────────────────────────────────────────────────────
(function () {
  const s = DATA.stats, mgrs = DATA.managers;
  const hitsRows  = mgrs.map(m => `<div class="s-row"><div class="s-dot" style="background:${m.color}"></div><span style="color:rgba(255,255,255,.85)">${m.name.split(' ')[0]}</span><span class="s-val" style="color:${m.color}">−${m.transfer_hits} pts</span></div>`).join('');
  const benchRows = mgrs.map(m => `<div class="s-row"><div class="s-dot" style="background:${m.color}"></div><span style="color:rgba(255,255,255,.85)">${m.name.split(' ')[0]}</span><span class="s-val" style="color:${m.color}">${m.bench_pts} pts</span></div>`).join('');
  document.getElementById('stats-grid').innerHTML = `
    <div class="stat-card"><div class="s-label">Beste Speelweek</div><div class="s-value">${s.best_gw.pts} pts</div><div class="s-sub">${s.best_gw.manager.split(' ')[0]} · ${s.best_gw.team} · GW ${s.best_gw.gw}</div></div>
    <div class="stat-card"><div class="s-label">Grootste Voorsprong</div><div class="s-value">${s.max_gap.pts} pts</div><div class="s-sub">in speelweek ${s.max_gap.gw}</div></div>
    <div class="stat-card"><div class="s-label">Transferstraf</div>${hitsRows}</div>
    <div class="stat-card"><div class="s-label">Punten op de Bank</div>${benchRows}</div>`;
})();

// ── Slide 5: Chip Timeline ────────────────────────────────────────────────────
(function () {
  const nGWs = Math.max(...DATA.managers.map(m => m.gw_nums.length));
  DATA.managers.forEach(m => {
    const row = document.createElement('div');
    row.className = 'cl-row';
    const who = document.createElement('div');
    who.className = 'cl-who';
    who.innerHTML = `<span style="color:${m.color}">${m.name.split(' ')[0]}</span> <span style="color:rgba(255,255,255,.35);font-weight:400">· ${m.team_name}</span>`;
    row.appendChild(who);
    const axis = document.createElement('div');
    axis.className = 'cl-axis';
    const line = document.createElement('div'); line.className = 'cl-line'; axis.appendChild(line);
    [1, 10, 20, 30, nGWs].forEach(gw => {
      const tick = document.createElement('div');
      tick.className = 'cl-gwtick';
      tick.style.left = ((gw-1)/(nGWs-1)*100) + '%';
      tick.textContent = gw;
      axis.appendChild(tick);
    });
    (m.chips || []).forEach(c => {
      const pct = ((c.event-1)/(nGWs-1)*100) + '%';
      const dot = document.createElement('div');
      dot.className = 'cl-dot'; dot.style.left = pct;
      dot.innerHTML = `<div class="cl-circle" style="background:${c.color}">${c.label}</div><div class="cl-gwnum">${c.event}</div>`;
      axis.appendChild(dot);
    });
    row.appendChild(axis);
    document.getElementById('chip-wrap').appendChild(row);
  });
})();

// ── Slide 6: Race Decided ─────────────────────────────────────────────────────
(function () {
  const mgrs   = DATA.managers;
  const nGWs   = Math.max(...mgrs.map(m => m.gw_nums.length));
  const sd     = DATA.stats.season_decided;
  const leader = mgrs[0];

  // ── Lead tracker SVG ────────────────────────────────────────────────────────
  const W = 860, H = 125, ML = 10, MR = 10, MT = 18, MB = 18;
  const cW = W - ML - MR, cH = H - MT - MB;
  const maxGap = Math.max(...mgrs.map(m =>
    Math.max(...m.gw_nums.map((_, i) => leader.cumulative[i] - m.cumulative[i]))
  )) || 1;

  const xS = i => ML + (i / (nGWs - 1)) * cW;
  const yS = v => MT + (v / maxGap) * cH;

  const NS = 'http://www.w3.org/2000/svg';
  function el(tag, attrs) {
    const e = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v));
    return e;
  }
  function txt(content, attrs) {
    const e = el('text', attrs);
    e.textContent = content;
    return e;
  }

  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, overflow: 'visible' });

  // Zero (leader) dashed line + label above it
  svg.appendChild(el('line', { x1: ML, x2: W - MR, y1: MT, y2: MT,
    stroke: 'rgba(255,255,255,.18)', 'stroke-dasharray': '4 3' }));
  svg.appendChild(txt('0 pts achter (leider)', { x: ML, y: MT - 5,
    'font-size': 8, fill: 'rgba(255,255,255,.35)' }));

  // Bottom axis label
  svg.appendChild(txt(`${maxGap} pts achter`, { x: ML, y: MT + cH + 14,
    'font-size': 8, fill: 'rgba(255,255,255,.2)' }));

  // GW axis ticks (skip GW1 — it overlaps the "pts behind" label at the left edge)
  [10, 20, 30, nGWs].forEach(gw => {
    svg.appendChild(txt(`GW${gw}`, { x: xS(gw - 1), y: H - 3,
      'text-anchor': 'middle', 'font-size': 9, fill: 'rgba(255,255,255,.25)' }));
  });

  // Manager lines + chip markers (draw lines first, then dots on top)
  mgrs.forEach(m => {
    const pts = m.gw_nums.map((_, i) => `${xS(i)},${yS(leader.cumulative[i] - m.cumulative[i])}`).join(' ');
    svg.appendChild(el('polyline', { points: pts, fill: 'none',
      stroke: m.color, 'stroke-width': 2, opacity: 0.9 }));
  });
  mgrs.forEach(m => {
    (m.chips || []).forEach(c => {
      const gi = m.gw_nums.indexOf(c.event);
      if (gi === -1) return;
      const cx = xS(gi), cy = yS(leader.cumulative[gi] - m.cumulative[gi]);
      svg.appendChild(el('circle', { cx, cy, r: 5, fill: c.color,
        stroke: '#0e0e1a', 'stroke-width': 1.5 }));
    });
  });

  document.getElementById('dc-lead').appendChild(svg);

  // ── Factor cards ────────────────────────────────────────────────────────────
  const avgPts = m => (m.gw_points.reduce((a, b) => a + b, 0) / m.gw_points.length).toFixed(1);

  const CARDS = [
    {
      title: '📊 Consistentie',
      sub: 'spreiding van GW-scores (lagere σ = stabieler)',
      values: sd.consistency,
      fmt:   v => v.toFixed(1) + ' σ',
      extra: (m, mi) => `avg ${avgPts(m)} · range ${Math.min(...m.gw_points)}–${Math.max(...m.gw_points)}`,
      winnerIsMin: true,
    },
    {
      title: '🃏 Chip Rendement',
      sub: 'gem. score op chip-GW\'s vs seizoensgemiddelde',
      values: sd.chip_returns,
      fmt:   v => (v >= 0 ? '+' : '') + v.toFixed(1) + ' pts/GW',
      winnerIsMin: false,
      stacked: true,
    },
    {
      title: '🎯 Aanvoerderschap',
      sub: 'totale bonuspunten van de aanvoerdersband',
      values: sd.captaincy,
      fmt:   v => `+${v} pts`,
      winnerIsMin: false,
      stacked: true,
    },
    {
      title: '⚠️ Fouten',
      sub: 'bank + transferstraf',
      values: sd.mistakes,
      fmt:   v => `${v} pts`,
      extra: (m) => `bench ${m.bench_pts} · hits ${m.transfer_hits}`,
      winnerIsMin: true,
    },
  ];

  const grid = document.getElementById('dc-grid');
  CARDS.forEach(card => {
    const winVal = card.winnerIsMin ? Math.min(...card.values) : Math.max(...card.values);
    const maxAbs = Math.max(...card.values.map(Math.abs)) || 1;
    const cardEl = document.createElement('div');
    cardEl.className = 'dc-card';
    let html = `<div class="dc-card-title">${card.title}</div>`;
    if (card.sub) html += `<div class="dc-card-sub">${card.sub}</div>`;
    mgrs.forEach((m, mi) => {
      const v      = card.values[mi];
      const winner = v === winVal;
      const barPct = Math.abs(v) / maxAbs * 100;
      const extra  = card.extra ? `<div class="dc-extra">${card.extra(m, mi)}</div>` : '';
      const valColor = winner ? m.color : 'var(--dim)';
      if (card.stacked) {
        html += `<div class="dc-row${winner ? ' dc-winner' : ''}">
          <div class="dc-dot" style="background:${m.color}"></div>
          <span class="dc-name">${m.name.split(' ')[0]}</span>
        </div>
        <div style="margin:-1px 0 2px 17px;font-size:.62em;font-weight:${winner?900:400};color:${valColor}">${card.fmt(v)}</div>
        ${extra}
        <div class="dc-bar-wrap"><div class="dc-mini-bar" style="width:${barPct}%;background:${m.color};opacity:${winner ? 1 : 0.35}"></div></div>`;
      } else {
        html += `<div class="dc-row${winner ? ' dc-winner' : ''}">
          <div class="dc-dot" style="background:${m.color}"></div>
          <span class="dc-name">${m.name.split(' ')[0]}</span>
          <span class="dc-val" style="color:${valColor}">${card.fmt(v)}</span>
        </div>
        ${extra}
        <div class="dc-bar-wrap"><div class="dc-mini-bar" style="width:${barPct}%;background:${m.color};opacity:${winner ? 1 : 0.35}"></div></div>`;
      }
    });
    cardEl.innerHTML = html;
    grid.appendChild(cardEl);
  });

  // ── Verdict ─────────────────────────────────────────────────────────────────
  document.getElementById('dc-verdict').textContent = sd.verdict;
})();

// ── Slide 7: Top Players ──────────────────────────────────────────────────────
(function () {
  const nGWs = Math.max(...DATA.managers.map(m => m.gw_nums.length));

  function fmtPeriod(p) {
    if (p.gws_owned === nGWs) return `<span style="color:var(--dim)">Heel seizoen · ${p.gws_in_xi} GW's in XI</span>`;
    const contiguous = p.gws_owned === (p.last_gw - p.first_gw + 1);
    if (!contiguous) return `<span style="color:var(--dim)">Owned ${p.gws_owned}/${nGWs} GW's · ${p.gws_in_xi} in XI</span>`;
    const inStr  = p.in_from_start ? 'Vanaf begin' : `<span class="tp-in">↑ GW ${p.first_gw}</span>`;
    const outStr = p.still_in      ? '→ einde'     : `<span class="tp-out">↓ GW ${p.last_gw}</span>`;
    return `<span style="color:var(--dim)">${inStr} ${outStr}</span> <span style="color:var(--dim)">${p.gws_in_xi} GW's in XI</span>`;
  }

  const grid = document.getElementById('tp-grid');
  DATA.managers.forEach(m => {
    const col = document.createElement('div');
    col.className = 'tp-col';
    col.innerHTML = `<div class="tp-head" style="color:${m.color}">${m.name.split(' ')[0]}<br><span class="tp-sub">${m.team_name}</span></div>`;

    (m.top_players || []).forEach((p, pi) => {
      const card = document.createElement('div');
      card.className = 'tp-card';
      card.style.fontSize = `${1 - pi * 0.07}em`;
      card.innerHTML = `
        <div class="tp-row1">
          <span class="tp-medal">${MEDALS[pi]}</span>
          <span class="tp-name">${p.name}</span>
          <span class="tp-badge">${p.team} · ${p.position}</span>
        </div>
        <div class="tp-row2">
          <span class="tp-pts" style="color:${m.color}">${p.total_pts} pts</span>
          <span class="tp-period">${fmtPeriod(p)}</span>
        </div>`;
      col.appendChild(card);
    });
    grid.appendChild(col);
  });
})();

// ── Slide 2: Bar-chart race (Flourish style) ─────────────────────────────
(function () {
  const managers = DATA.managers;
  const nGWs     = Math.max(...managers.map(m => m.gw_nums.length));

  // Speed: one gameweek takes MS_PER_GW ms — full 38-GW race ≈ 13 s at 340
  const MS_PER_GW = 800;

  // Flourish-style layout (unchanged)
  const ML = 130, MR = 75, MT = 44, MB = 62;
  const ROW_H = 110, BAR_H = 96;
  const CHART_W = 605;
  const CHART_H = managers.length * ROW_H;
  const SVG_W   = ML + CHART_W + MR;
  const SVG_H   = MT + CHART_H + MB;

  // Mutable x-scale; domain end is eased toward leader's pts * 1.1 each frame
  const x = d3.scaleLinear().range([0, CHART_W]);
  let curDomainEnd = 1;

  const svg = d3.select('#race-svg-wrap').append('svg')
    .attr('viewBox', `0 0 ${SVG_W} ${SVG_H}`)
    .style('width', '100%').style('height', 'auto');

  const g      = svg.append('g').attr('transform', `translate(${ML},${MT})`);
  const gridG  = g.append('g');
  const barsG  = g.append('g');
  const xAxisG = g.append('g');

  // Thin vertical baseline
  g.append('line').attr('class', 'grid-line')
    .attr('x1', 0).attr('x2', 0).attr('y1', 0).attr('y2', CHART_H)
    .attr('stroke', 'rgba(255,255,255,.18)');

  const gwCounter = svg.append('text').attr('class', 'gw-counter')
    .attr('x', SVG_W - 14).attr('y', SVG_H - 26)
    .attr('text-anchor', 'end').text('0');

  // ── Continuous value model ────────────────────────────────────────────────────
  // C(m, k): manager's cumulative points at end of GW k (k=0 → season start = 0)
  function C(m, k) {
    if (k <= 0) return 0;
    return m.cumulative[Math.min(k, m.cumulative.length) - 1];
  }

  // Linearly interpolate between GW boundaries for smooth bar growth
  function ptsAt(m, pos) {
    const g = Math.floor(pos), frac = pos - g;
    return C(m, g) + (C(m, g + 1) - C(m, g)) * frac;
  }

  function getSnap(pos) {
    return managers.map((m, i) => ({
      ...m, origIdx: i,
      pts: ptsAt(m, pos),
    })).sort((a, b) => b.pts - a.pts);
  }

  // ── Create persistent bar groups (one per manager, never recreated) ───────────
  const displayY = {};
  managers.forEach((_, i) => { displayY[i] = i * ROW_H + (ROW_H - BAR_H) / 2; });

  barsG.selectAll('.bg')
    .data(managers, (d, i) => i)
    .enter().append('g').attr('class', 'bg')
      .attr('data-idx', (d, i) => i)
      .attr('transform', (d, i) => `translate(0,${displayY[i]})`)
      .each(function (d) {
        const grp = d3.select(this);
        grp.append('rect').attr('class', 'bar-rect')
          .attr('height', BAR_H).attr('width', 0).attr('fill', d.color);
        grp.append('text').attr('class', 'bar-name')
          .attr('x', -12).attr('y', BAR_H / 2)
          .attr('text-anchor', 'end').attr('dominant-baseline', 'middle')
          .attr('fill', d.color).text(d.name.split(' ')[0]);
        grp.append('text').attr('class', 'bar-val')
          .attr('x', 8).attr('y', BAR_H / 2)
          .attr('dominant-baseline', 'middle').text('0');
      });

  // Cache element references — avoids D3 selector overhead per frame
  const barEls = {};
  barsG.selectAll('.bg').each(function () {
    const idx = +d3.select(this).attr('data-idx');
    barEls[idx] = {
      grp:  this,
      rect: this.querySelector('.bar-rect'),
      val:  this.querySelector('.bar-val'),
    };
  });

  // ── Core render — called every rAF frame (or immediately for controls) ────────
  // snap=true: set positions instantly (no easing); snap=false: lerp toward target
  function render(pos, snap) {
    const snapshot = getSnap(pos);
    const g = Math.floor(pos);

    // Ease x-domain end toward leader's pts * 1.1
    const frameMax  = Math.max(10, ...snapshot.map(s => s.pts));
    const targetEnd = frameMax * 1.1;
    curDomainEnd = snap ? targetEnd : curDomainEnd + (targetEnd - curDomainEnd) * 0.18;
    x.domain([0, curDomainEnd]);

    // Vertical grid lines + top x-axis tick labels
    const ticks = x.ticks(5);
    gridG.selectAll('.grid-line').data(ticks).join('line').attr('class', 'grid-line')
      .attr('x1', d => x(d)).attr('x2', d => x(d))
      .attr('y1', 0).attr('y2', CHART_H);
    xAxisG.selectAll('.x-tick').data(ticks).join('text').attr('class', 'x-tick')
      .attr('x', d => x(d)).attr('y', -12)
      .attr('text-anchor', 'middle').text(d => d);

    // Update each bar group
    snapshot.forEach((d, rank) => {
      const el = barEls[d.origIdx];
      const w  = Math.max(0, x(d.pts));

      el.rect.setAttribute('width', w);
      el.val.setAttribute('x', w + 10);
      el.val.textContent = Math.round(d.pts);

      // Smooth row reordering via per-frame lerp
      const targetY = rank * ROW_H + (ROW_H - BAR_H) / 2;
      displayY[d.origIdx] = snap
        ? targetY
        : displayY[d.origIdx] + (targetY - displayY[d.origIdx]) * 0.2;
      el.grp.setAttribute('transform', `translate(0,${displayY[d.origIdx]})`);
    });

    // GW counter — shows last completed GW (stays at 0 while GW 1 is animating)
    const dispGW = Math.floor(pos);
    gwCounter.text(dispGW);

    // Sync slider + label
    document.getElementById('gw-slider').value = dispGW;
    document.getElementById('gw-lbl').textContent = `GW ${dispGW} / ${nGWs}`;
  }

  // ── rAF playback engine ───────────────────────────────────────────────────────
  let pos = 0, raf = null, startTs = 0, startPos = 0;

  function play() {
    if (pos >= nGWs) { pos = 0; render(0, true); }
    startTs  = performance.now();
    startPos = pos;
    document.getElementById('btn-play').textContent = '⏸ Pauze';
    function tick(now) {
      pos = startPos + (now - startTs) / MS_PER_GW;
      if (pos >= nGWs) {
        pos = nGWs; render(pos, false);
        raf = null;
        document.getElementById('btn-play').textContent = '▶ Start';
        return;
      }
      render(pos, false);
      raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);
  }

  function pause() {
    if (raf) { cancelAnimationFrame(raf); raf = null; }
    document.getElementById('btn-play').textContent = '▶ Start';
  }

  // ── Bootstrap ────────────────────────────────────────────────────────────────
  document.getElementById('gw-slider').max = nGWs;
  render(0, true);

  // ── Controls ─────────────────────────────────────────────────────────────────
  document.getElementById('btn-play').addEventListener('click', () => raf ? pause() : play());
  document.getElementById('btn-restart').addEventListener('click', () => {
    pause(); pos = 0; render(0, true);
  });
  document.getElementById('gw-slider').addEventListener('input', function () {
    pause();
    pos = +this.value;
    render(pos, true);
  });

  Reveal.on('slidechanged', e => {
    if (e.currentSlide.id !== 'race-slide') { pause(); }
  });
})();

// ── Reveal init ───────────────────────────────────────────────────────────────
Reveal.initialize({
  hash: true, transition: 'slide', transitionSpeed: 'fast',
  controls: true, progress: true, center: false,
});
</script>
</body>
</html>
"""


# ── Generator ──────────────────────────────────────────────────────────────────

def generate_html(payload: dict) -> str:
    return HTML_TEMPLATE.replace(
        "/*DATA_PLACEHOLDER*/",
        json.dumps(payload, separators=(",", ":")),
    )


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="FPL presentation generator")
    parser.add_argument("--input",  default=INPUT_DATA,  help="Input JSON (default: %(default)s)")
    parser.add_argument("--output", default=OUTPUT_HTML, help="Output HTML (default: %(default)s)")
    args = parser.parse_args()

    print(f"Reading {args.input} …")
    with open(args.input) as f:
        payload = json.load(f)

    with open(args.output, "w") as f:
        f.write(generate_html(payload))
    print(f"Saved → {args.output}")

    webbrowser.open(args.output)


if __name__ == "__main__":
    main()
