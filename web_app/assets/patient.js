import { api, color, esc, fmtDate, label, mountTopbar, requireUser } from './api.js';
import { enableAll } from './motion.js';
import { renderResult } from './result-view.js';

const $ = (sel) => document.querySelector(sel);
const me = await requireUser(['patient']);
mountTopbar(me);

api('/api/me/patient').then((p) => {
  $('#greeting').textContent = `Hello, ${p.name.split(' ')[0]}`;
  $('#patient-code').textContent = `Patient code ${p.patient_code} · only you and your care team can see these results.`;
}).catch(() => {});

async function open(id) {
  const r = await api(`/api/analysis/${encodeURIComponent(id)}`);
  document.querySelectorAll('[data-analysis]').forEach((el) => el.classList.toggle('selected', el.dataset.analysis === id));
  renderResult($('#results'), r, { audience: 'patient' });
  $('#results').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

const items = await api('/api/me/analyses');
const list = $('#my-list');
if (!items.length) {
  list.innerHTML = '<div class="tiny muted">No results yet.</div>';
} else {
  list.innerHTML = items.map((a) => `
    <div class="patient-item" data-analysis="${esc(a.analysis_id)}">
      <span class="avatar" style="background:${a.research_classification ? color(a.research_classification) : 'var(--text-3)'}">${a.input_type === 'video' ? '▶' : '◎'}</span>
      <div><div style="font-weight:700;">${esc(a.research_classification ? label(a.research_classification) : a.quality_status)}</div>
        <div class="meta">${fmtDate(a.timestamp)}${a.uncertain ? ' · uncertain' : ''}</div></div>
    </div>`).join('');
  list.querySelectorAll('[data-analysis]').forEach((el) => el.addEventListener('click', () => open(el.dataset.analysis)));
  open(items[0].analysis_id);
}
enableAll();
