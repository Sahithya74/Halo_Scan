import { api, color, esc, fmtDate, label, live, mountTopbar, requireUser, toast } from './api.js';
import { enableAll } from './motion.js';
import { renderResult } from './result-view.js';

const $ = (sel) => document.querySelector(sel);
const me = await requireUser(['patient']);
mountTopbar(me);

api('/api/me/patient').then((p) => {
  $('#greeting').textContent = `Hello, ${p.name.split(' ')[0]}`;
  $('#patient-code').textContent = `Patient code ${p.patient_code} · only you and your care team can see these results.`;
}).catch(() => {});

const list = $('#my-list');
let known = null;     // analysis ids already listed
let selected = null;

async function open(id) {
  selected = id;
  const r = await api(`/api/analysis/${encodeURIComponent(id)}`);
  document.querySelectorAll('[data-analysis]').forEach((el) => el.classList.toggle('selected', el.dataset.analysis === id));
  renderResult($('#results'), r, { audience: 'patient' });
  $('#results').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderList(items, fresh) {
  if (!items.length) {
    list.innerHTML = '<div class="tiny muted">No results yet. They appear here automatically as soon as your care team analyses a sample.</div>';
    return;
  }
  list.innerHTML = items.map((a) => `
    <div class="patient-item ${a.analysis_id === selected ? 'selected' : ''} ${fresh.has(a.analysis_id) ? 'just-arrived' : ''}" data-analysis="${esc(a.analysis_id)}">
      <span class="avatar" style="background:${a.research_classification ? color(a.research_classification) : 'var(--text-3)'}">${a.input_type === 'video' ? '▶' : '◎'}</span>
      <div><div style="font-weight:700;">${esc(a.research_classification ? label(a.research_classification) : a.quality_status)}</div>
        <div class="meta">${fmtDate(a.timestamp)}${a.uncertain ? ' · uncertain' : ''}</div></div>
    </div>`).join('');
  list.querySelectorAll('[data-analysis]').forEach((el) => el.addEventListener('click', () => open(el.dataset.analysis)));
}

/** Lists results; a result added by the care team since the last check is announced and opened.
 *  Each result's details are fetched once, when shown — polling only reads the list. */
async function refresh({ background = false } = {}) {
  const items = await api('/api/me/analyses', { background });
  const ids = items.map((a) => a.analysis_id);
  const fresh = new Set(known ? ids.filter((id) => !known.has(id)) : []);
  if (known && !fresh.size && ids.length === known.size) return;
  known = new Set(ids);
  renderList(items, fresh);
  if (fresh.size) {
    toast(fresh.size === 1 ? 'New result from your care team' : `${fresh.size} new results from your care team`);
    await open(items[0].analysis_id);
  }
}

await refresh();
if (known.size) open([...known][0]);
enableAll();
live(() => refresh({ background: true }), 4000);
