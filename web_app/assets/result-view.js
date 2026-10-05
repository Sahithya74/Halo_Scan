// Renders one analysis result. Shared by the clinician and patient pages so the output can
// never differ between them.
import { color, esc, fmtDate, label, LABELS } from './api.js';
import { countUp, enableAll } from './motion.js';

const ICON = {
  ring: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/></svg>',
  ruler: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 17 17 3l4 4L7 21z"/><path d="m7 13 2 2M10 10l2 2M13 7l2 2"/></svg>',
  chart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>',
  wave: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 12c2.5-6 5-6 7.5 0s5 6 7.5 0 4-4 5-2"/></svg>',
  radar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m12 3 8 6-3 10H7L4 9z"/><path d="m12 8 4 3-1.5 5h-5L8 11z"/></svg>',
  spark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8"/></svg>',
  image: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/></svg>',
  film: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M7 4v16M17 4v16M2 9h5M2 15h5M17 9h5M17 15h5"/></svg>',
  flask: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 2v6L4 18a2 2 0 0 0 2 3h12a2 2 0 0 0 2-3l-5-10V2M8 2h8"/></svg>',
  alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/></svg>',
  shield: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
  print: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9V2h12v7M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>',
};
export { ICON };

const pct = (v, d = 1) => `${(v * 100).toFixed(d)}%`;

function verdictBanner(r) {
  const c = r.classification;
  const meta = [
    r.patient_code ? `Patient <b>${esc(r.patient_code)}</b>` : '',
    `Input <b>${r.input_type === 'video' ? `${r.video?.duration_s ?? ''}s video` : 'photo'}</b>`,
    r.processing_ms != null ? `Analysed in <b>${(r.processing_ms / 1000).toFixed(1)}s</b>` : '',
    `<span>${fmtDate(r.timestamp)}</span>`,
  ].filter(Boolean).join('<span>·</span>');

  if (r.status === 'RECAPTURE_NEEDED') {
    return `<section class="verdict bad" data-reveal>
      <div class="kicker">Result</div>
      <div class="big"><div class="label">Recapture needed</div></div>
      <div class="stamps"><span class="stamp alert">${ICON.alert} IMAGE QUALITY TOO LOW</span></div>
      <div class="meta-row">${meta}</div></section>`;
  }
  if (r.status === 'NO_HALO_DETECTED' || !c) {
    return `<section class="verdict neutral" data-reveal>
      <div class="kicker">Halo ring analysis</div>
      <div class="big"><div class="label">${r.status === 'NO_HALO_DETECTED' ? 'No halo detected' : 'Halo detected'}</div></div>
      <div class="stamps">${r.decision_support.recommend_lab_confirmation
        ? `<span class="stamp alert">${ICON.flask} LAB CONFIRMATION RECOMMENDED</span>` : ''}
        ${!c && r.status === 'OK' ? '<span class="stamp">Model not trained — no classification</span>' : ''}</div>
      <div class="meta-row">${meta}</div></section>`;
  }
  return `<section class="verdict" style="--cls:${color(c.research_classification)}" data-reveal>
    <div class="kicker">Most likely research classification</div>
    <div class="big">
      <div class="label">${esc(label(c.research_classification))}</div>
      <div class="pct"><span data-count="${c.confidence * 100}">0</span><small>% confidence</small></div>
    </div>
    <div class="confidence-meter"><i data-width="${c.confidence * 100}"></i></div>
    <div class="stamps">
      <span class="stamp">${ICON.ring} HALO DETECTED</span>
      ${c.uncertain ? `<span class="stamp alert">${ICON.alert} UNCERTAIN</span>` : ''}
      ${r.decision_support.recommend_lab_confirmation ? `<span class="stamp alert">${ICON.flask} LAB CONFIRMATION REQUIRED</span>` : ''}
      <span class="stamp">${ICON.shield} NOT A DIAGNOSIS</span>
    </div>
    <div class="meta-row">${meta}</div>
  </section>`;
}

function donutCard(c) {
  const entries = Object.entries(c.class_probabilities).sort((a, b) => b[1] - a[1]);
  const R = 80, SW = 26, C = 2 * Math.PI * R;
  let offset = 0;
  const segs = entries.map(([cls, p]) => {
    const len = Math.max(0, C * p);
    const s = `<circle class="seg" data-cls="${cls}" data-p="${p}" cx="105" cy="105" r="${R}" fill="none"
      style="stroke:${color(cls)}" stroke-width="${SW}" stroke-dasharray="0 ${C}" data-len="${len}" data-c="${C}"
      stroke-dashoffset="${-offset}"></circle>`;
    offset += len;
    return s;
  }).join('');
  const winner = c.research_classification;
  return `<section class="card" data-tilt="3" data-reveal>
    <div class="card-title">${ICON.chart} Chances of each fluid <span class="right muted tiny">hover a slice</span></div>
    <div class="donut-row">
      <div class="donut" data-donut>
        <svg viewBox="0 0 210 210"><circle cx="105" cy="105" r="${R}" fill="none" stroke="var(--muted)" stroke-width="${SW}"/>${segs}</svg>
        <div class="center"><div><b data-donut-pct style="color:${color(winner)}">${pct(c.class_probabilities[winner], 0)}</b>
          <span data-donut-label>${esc(label(winner))}</span></div></div>
      </div>
      <div class="legend">
        ${entries.map(([cls, p]) => `<div class="legend-row ${cls === winner ? 'winner' : ''}">
          <span class="sw" style="background:${color(cls)}"></span><span>${esc(label(cls))}</span><span class="p">${pct(p)}</span>
          <span class="bar"><i style="background:${color(cls)}" data-width="${p * 100}"></i></span></div>`).join('')}
      </div>
    </div>
  </section>`;
}

function decisionAndModel(r) {
  const m = r.model_card;
  const sens = m && m.per_class_sensitivity ? Object.entries(m.per_class_sensitivity) : [];
  return `<section class="card" data-reveal>
    <div class="card-title">${ICON.flask} Decision support</div>
    <div class="decision"><p>${esc(r.decision_support.message)}</p><p class="disc">${esc(r.decision_support.disclaimer)}</p></div>
    ${m ? `<div class="model-card" style="margin-top:16px;">
      <div class="card-title" style="margin-bottom:6px;">${ICON.shield} Model card <span class="right muted tiny">${esc(m.model_version)}</span></div>
      <div style="display:flex;gap:22px;align-items:end;flex-wrap:wrap;">
        <div><div class="acc">${m.test_accuracy != null ? pct(m.test_accuracy) : '—'}</div><div class="muted tiny">measured test accuracy</div></div>
        <div><div class="acc" style="font-size:24px;">${m.macro_f1 != null ? m.macro_f1.toFixed(2) : '—'}</div><div class="muted tiny">macro F1</div></div>
        <div><div class="acc" style="font-size:24px;">${m.n_test_samples ?? '—'}</div><div class="muted tiny">test images</div></div>
      </div>
      ${sens.length ? `<div class="tiny muted" style="margin-top:8px;">Sensitivity per class: ${sens.map(([k, v]) => `${esc(label(k))} ${pct(v, 0)}`).join(' · ')}</div>` : ''}
      <div class="note">${esc(m.note)}</div></div>` : ''}
  </section>`;
}

function haloCard(r) {
  const h = r.halo, s = r.spreading;
  if (!h) return '';
  const tile = (v, unit, l) => `<div class="stat"><div class="v">${v}<small>${unit}</small></div><div class="l">${l}</div></div>`;
  return `<section class="card" data-reveal>
    <div class="card-title">${ICON.ruler} Halo ring analysis
      <span class="right">${h.detected ? '<span class="badge ok"><span class="dot"></span>Ring detected</span>' : '<span class="badge warn">No clear ring</span>'}</span></div>
    <div class="stats">
      ${tile(h.inner_radius.toFixed(0), 'px', 'Inner radius')}
      ${tile(h.outer_radius.toFixed(0), 'px', 'Outer radius')}
      ${tile(h.halo_width.toFixed(0), 'px', 'Ring width')}
      ${tile(h.circularity.toFixed(2), '', 'Circularity')}
      ${tile(h.symmetry_score.toFixed(2), '', 'Symmetry')}
      ${tile((h.confidence * 100).toFixed(0), '%', 'Detector confidence')}
      ${s ? tile(s.spread_radius_normalized.toFixed(2), '×', 'Spread vs pad') : ''}
      ${s ? tile(s.diffusion_index.toFixed(2), '', 'Diffusion index') : ''}
    </div>
    <div class="tiny muted" style="margin-top:10px;">Quality <span class="badge ${r.quality.status.toLowerCase()}">${r.quality.status}</span>
      score ${(r.quality.score * 100).toFixed(0)}% ${r.quality.reasons.length ? '· ' + r.quality.reasons.map(esc).join(' ') : ''}</div>
  </section>`;
}

function comparisonCard(r) {
  const cmp = r.comparison;
  if (!cmp) return '';
  const rows = Object.entries(cmp.class_similarity).sort((a, b) => b[1] - a[1]);
  return `<section class="card" data-reveal>
    <div class="card-title">${ICON.radar} Comparison with reference profiles
      <span class="right muted tiny">closest: <b style="color:${color(cmp.closest_class)}">${esc(label(cmp.closest_class))}</b></span></div>
    ${rows.map(([cls, v]) => `<div class="sim-row ${cls === cmp.closest_class ? 'closest' : ''}">
      <span>${esc(label(cls))}</span><span class="track"><i style="background:${color(cls)}" data-width="${v}"></i></span>
      <span class="num">${v.toFixed(0)}%</span></div>`).join('')}
    <div class="tiny muted" style="margin-top:8px;">How closely this sample's ring width, spread, diffusion, saturation, texture and
      circularity match each fluid's typical profile (from training data). Independent of the classifier — agreement between the
      two adds confidence; disagreement is a reason for caution.</div>
  </section>`;
}

function diagrams(r) {
  const v = r.visualizations || {};
  const isVideo = r.input_type === 'video';
  const tiles = [
    [v.source_image_jpeg_base64, 'jpeg', ICON.image, isVideo ? 'Analysed frame' : 'Analysed image', isVideo ? 'Best-quality frame from the video' : 'The photo as received'],
    [v.overlay_png_base64, 'png', ICON.ruler, 'Measurement diagram', 'Detected rings with measured radii'],
    [v.probability_chart_png_base64, 'png', ICON.chart, 'Prediction diagram', 'Probability of each fluid class'],
    [v.comparison_radar_png_base64, 'png', ICON.radar, 'Comparison radar', 'Sample vs class reference profiles'],
    [v.radial_profile_png_base64, 'png', ICON.wave, 'Radial intensity profile', 'Brightness from centre outward'],
    [v.feature_importance_png_base64, 'png', ICON.spark, 'Why this prediction', 'Top SHAP feature contributions'],
    [v.frame_timeline_png_base64, 'png', ICON.film, 'Video timeline', 'Prediction across sampled frames'],
  ].filter((t) => t[0]);
  if (!tiles.length) return '';
  return `<section class="card" data-reveal>
    <div class="card-title">${ICON.image} Graphical analysis <span class="right muted tiny">click any diagram to enlarge</span></div>
    <div class="viz-grid">${tiles.map(([b64, kind, icon, title, sub]) => `
      <figure class="viz" data-tilt="4" data-zoom data-caption="${esc(title)}">
        <img src="data:image/${kind};base64,${b64}" alt="${esc(title)}" loading="lazy">
        <figcaption>${icon}<span>${esc(title)}<small>${esc(sub)}</small></span></figcaption>
      </figure>`).join('')}</div>
  </section>`;
}

function videoCard(r) {
  const v = r.video;
  if (!v) return '';
  return `<section class="card" data-reveal>
    <div class="card-title">${ICON.film} Video analysis</div>
    <div class="stats" style="margin-bottom:14px;">
      <div class="stat"><div class="v">${v.duration_s}<small>s</small></div><div class="l">Duration</div></div>
      <div class="stat"><div class="v">${v.frames_used}<small>/ ${v.frames_sampled}</small></div><div class="l">Frames used</div></div>
      <div class="stat"><div class="v">${(v.frame_agreement * 100).toFixed(0)}<small>%</small></div><div class="l">Frames agreeing</div></div>
      <div class="stat"><div class="v">${(v.stability * 100).toFixed(0)}<small>%</small></div><div class="l">Stability</div></div>
    </div>
    <div class="frame-strip">${v.frames.map((f) => `
      <div class="frame ${f.research_classification ? '' : 'rejected'}" data-zoom data-caption="Frame at ${f.time_s}s"
           style="${f.research_classification ? `border-color:${color(f.research_classification)}` : ''}">
        <img src="data:image/jpeg;base64,${f.thumbnail_jpeg_base64}" alt="Frame at ${f.time_s}s">
        <div><span>${f.time_s}s</span><span style="color:${f.research_classification ? color(f.research_classification) : 'var(--text-3)'}">
          ${f.research_classification ? `${esc(label(f.research_classification))} ${pct(f.confidence, 0)}` : esc(f.quality_status === 'POOR' ? 'blurry' : 'no ring')}</span></div>
      </div>`).join('')}</div>
  </section>`;
}

function featuresCard(r) {
  const top = r.explainability?.top_features;
  if (!top?.length) return '';
  const max = Math.max(...top.map((f) => Math.abs(f.shap_value))) || 1;
  return `<section class="card" data-reveal>
    <div class="card-title">${ICON.spark} Top contributing measurements</div>
    ${top.map((f) => `<div class="sim-row"><span style="font-family:ui-monospace,Consolas,monospace;font-size:12px;">${esc(f.feature)}</span>
      <span class="track"><i style="background:${f.shap_value >= 0 ? 'var(--success)' : 'var(--danger)'}" data-width="${Math.abs(f.shap_value) / max * 100}"></i></span>
      <span class="num">${f.shap_value >= 0 ? '+' : ''}${f.shap_value.toFixed(3)}</span></div>`).join('')}
  </section>`;
}

function patientExplainer(r) {
  const c = r.classification;
  const what = !c ? 'The system could not classify this sample, so no fluid type is suggested.'
    : `The pattern looks most similar to a <b>${esc(label(c.research_classification))}</b> sample (${pct(c.confidence, 0)} confidence).`;
  return `<section class="card" data-reveal>
    <div class="card-title">${ICON.shield} What this means</div>
    <p style="margin:0 0 10px;">${what}</p>
    <p style="margin:0 0 10px;">This is a <b>screening aid, not a diagnosis</b>. Clear fluids such as CSF, saline and tears can make
      almost identical rings, so a photo alone cannot confirm what the fluid is.</p>
    <p style="margin:0;">${r.decision_support.recommend_lab_confirmation
      ? 'Your care team has been advised to confirm this with a laboratory test (beta-2 transferrin).'
      : 'Please discuss this result with your doctor or nurse.'}</p>
  </section>`;
}

function ensureLightbox() {
  let lb = document.querySelector('.lightbox');
  if (!lb) {
    lb = document.createElement('div');
    lb.className = 'lightbox';
    lb.innerHTML = '<img alt=""><p></p>';
    lb.addEventListener('click', () => lb.classList.remove('open'));
    document.body.append(lb);
  }
  return lb;
}

function wireInteractions(root, r) {
  root.querySelectorAll('[data-zoom]').forEach((el) => el.addEventListener('click', () => {
    const lb = ensureLightbox();
    lb.querySelector('img').src = el.querySelector('img').src;
    lb.querySelector('p').textContent = `${el.dataset.caption} — click anywhere to close`;
    lb.classList.add('open');
  }));

  const donut = root.querySelector('[data-donut]');
  if (donut && r.classification) {
    const pctEl = donut.querySelector('[data-donut-pct]');
    const lblEl = donut.querySelector('[data-donut-label]');
    const winner = r.classification.research_classification;
    const show = (cls, p) => { pctEl.textContent = pct(p, 0); pctEl.style.color = color(cls); lblEl.textContent = label(cls); };
    donut.querySelectorAll('circle.seg').forEach((seg) => {
      seg.addEventListener('mouseenter', () => show(seg.dataset.cls, Number(seg.dataset.p)));
      seg.addEventListener('mouseleave', () => show(winner, r.classification.class_probabilities[winner]));
    });
  }

  // Animate bars, donut and counters after first paint.
  requestAnimationFrame(() => requestAnimationFrame(() => {
    root.querySelectorAll('[data-width]').forEach((el) => { el.style.width = `${el.dataset.width}%`; });
    root.querySelectorAll('circle.seg').forEach((seg) => {
      seg.setAttribute('stroke-dasharray', `${seg.dataset.len} ${Number(seg.dataset.c) - Number(seg.dataset.len)}`);
    });
    root.querySelectorAll('[data-count]').forEach((el) => countUp(el, Number(el.dataset.count), { decimals: 1 }));
  }));
  enableAll(root);
}

/** audience: "clinician" | "patient" */
export function renderResult(container, r, { audience = 'clinician' } = {}) {
  const c = r.classification;
  container.innerHTML = `
    <div class="no-print" style="display:flex;justify-content:flex-end;margin-bottom:10px;">
      <button class="btn ghost sm" data-print>${ICON.print} Print / save PDF report</button></div>
    ${verdictBanner(r)}
    ${audience === 'patient' ? patientExplainer(r) : ''}
    <div class="grid-cols" style="grid-template-columns:repeat(auto-fit,minmax(340px,1fr));align-items:start;">
      ${c ? donutCard(c) : ''}
      ${decisionAndModel(r)}
    </div>
    ${haloCard(r)}
    ${diagrams(r)}
    ${videoCard(r)}
    <div class="grid-cols" style="grid-template-columns:repeat(auto-fit,minmax(340px,1fr));align-items:start;">
      ${comparisonCard(r)}
      ${audience === 'clinician' ? featuresCard(r) : ''}
    </div>
    <div class="tiny muted" style="text-align:center;">Analysis ${esc(r.analysis_id)} · classes: ${Object.values(LABELS).join(', ')}</div>`;
  container.querySelector('[data-print]').addEventListener('click', () => window.print());
  wireInteractions(container, r);
}
