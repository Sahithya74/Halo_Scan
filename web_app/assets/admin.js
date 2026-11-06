import { api, color, esc, fmtDate, label, live, mountTopbar, openModal, requireUser, toast } from './api.js';
import { countUp, enableAll } from './motion.js';

const $ = (sel) => document.querySelector(sel);
const me = await requireUser(['admin']);
mountTopbar(me);

const LOADERS = { overview: loadOverview, users: loadUsers, audit: loadAudit };
let activeTab = 'overview';

document.querySelectorAll('#tabs button').forEach((btn) => btn.addEventListener('click', () => {
  document.querySelectorAll('#tabs button').forEach((b) => b.classList.toggle('active', b === btn));
  document.querySelectorAll('[data-panel]').forEach((p) => p.classList.toggle('hidden', p.dataset.panel !== btn.dataset.tab));
  activeTab = btn.dataset.tab;
  LOADERS[activeTab]();
}));

/** Last rendered content per section: live refreshes only touch the DOM when data changed. */
const rendered = {};
function changed(key, value) {
  const sig = JSON.stringify(value);
  if (rendered[key] === sig) return false;
  rendered[key] = sig;
  return true;
}

/* ---------- live activity feed ---------- */
const ACTIVITY = {
  login: ['↪', 'signed in'],
  logout: ['↩', 'signed out'],
  login_wrong_portal: ['!', 'used the wrong sign-in portal'],
  password_change: ['✱', 'changed their password'],
  patient_register: ['+', 'registered a patient'],
  patient_view: ['◐', 'opened a patient record'],
  analysis_run: ['◎', 'analysed a sample'],
  analysis_rejected: ['✕', 'submitted an image that was rejected'],
  user_create: ['⚙', 'created a staff account'],
  user_activate: ['⚙', 'activated an account'],
  user_deactivate: ['⚙', 'deactivated an account'],
  user_password_reset: ['⚙', 'reset a password'],
};
const QUIET = new Set(['patient_list']);  // logged on every search keystroke; still in the Audit tab

function ago(iso) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 10) return 'just now';
  if (s < 60) return `${Math.floor(s)} s ago`;
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  return fmtDate(iso);
}

let lastSeenAuditId = null;
function renderActivity(entries) {
  const shown = entries.filter((e) => !QUIET.has(e.action)).slice(0, 10);
  const newest = entries.length ? entries[0].id : 0;
  $('#activity-feed').innerHTML = shown.length ? shown.map((e) => {
    const failed = e.action.startsWith('login_failed');
    const [icon, text] = failed ? ['!', 'failed to sign in']
      : e.action === 'analysis_view' ? ['◉', e.role === 'patient' ? 'viewed their result' : 'opened a result']
      : ACTIVITY[e.action] || ['•', e.action.replace(/_/g, ' ')];
    const fresh = lastSeenAuditId !== null && e.id > lastSeenAuditId;
    return `<div class="activity-item ${fresh ? 'just-arrived' : ''}">
      <span class="activity-icon" style="${failed || !e.success ? 'color:var(--danger);' : ''}">${icon}</span>
      <span><span class="who">${esc(e.username || 'unknown')}</span> <span class="muted">${esc(e.role || '')}</span> ${esc(text)}</span>
      <span class="when">${ago(e.ts)}</span></div>`;
  }).join('') : '<div class="muted tiny">No activity yet.</div>';
  lastSeenAuditId = newest;
}

function showSecret(title, html) {
  $('#secret-title').textContent = title;
  $('#secret-body').innerHTML = html;
  openModal('secret-modal');
}

/* ---------- overview ---------- */
async function loadOverview({ background = false } = {}) {
  const [stats, audit] = await Promise.all([
    api('/api/admin/stats', { background }), api('/api/admin/audit?limit=40', { background }),
  ]);
  const r = stats.users_by_role;
  const total = Object.values(stats.analyses_by_result).reduce((a, b) => a + b, 0);
  const tiles = [
    ['Doctors', r.doctor || 0], ['Nurses', r.nurse || 0], ['Administrators', r.admin || 0],
    ['Patients', stats.patients], ['Analyses', total], ['Audit entries', audit.chain.entries_checked],
  ];
  const before = rendered.tiles ? Object.fromEntries(JSON.parse(rendered.tiles)) : null;
  if (changed('tiles', tiles)) {
    $('#overview-stats').innerHTML = tiles.map(([l, v]) => {
      const moved = before && before[l] !== v;
      return `<div class="stat ${moved ? 'just-arrived' : ''}" data-tilt="6"><div class="v" data-count="${v}">${before ? v : 0}</div><div class="l">${l}</div></div>`;
    }).join('');
    if (!before) document.querySelectorAll('#overview-stats [data-count]').forEach((el) => countUp(el, Number(el.dataset.count)));
  }

  renderActivity(audit.entries);

  const rows = Object.entries(stats.analyses_by_result).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...rows.map((x) => x[1]));
  if (changed('byResult', rows)) $('#by-result').innerHTML = rows.length ? rows.map(([k, n]) => `
    <div class="sim-row"><span>${esc(label(k))}</span>
      <span class="track"><i style="background:${color(k)};width:${(n / max) * 100}%"></i></span><span class="num">${n}</span></div>`).join('')
    : '<div class="muted tiny">No analyses recorded yet.</div>';

  const m = stats.model_card;
  const chain = audit.chain;
  if (!changed('cards', [m, chain.verified, chain.first_broken_id])) { enableAll(); return; }
  $('#model-card').innerHTML = m ? `
    <div style="display:flex;gap:22px;align-items:end;flex-wrap:wrap;">
      <div><div style="font-size:34px;font-weight:800;">${(m.test_accuracy * 100).toFixed(1)}%</div><div class="tiny muted">measured test accuracy</div></div>
      <div><div style="font-size:24px;font-weight:800;">${m.macro_f1.toFixed(2)}</div><div class="tiny muted">macro F1</div></div>
      <div><div style="font-size:24px;font-weight:800;">${m.n_test_samples}</div><div class="tiny muted">test images</div></div>
    </div>
    <div style="margin-top:12px;">${Object.entries(m.per_class_sensitivity).map(([k, v]) => `
      <div class="sim-row"><span>${esc(label(k))}</span><span class="track"><i style="background:${color(k)};width:${v * 100}%"></i></span>
      <span class="num">${(v * 100).toFixed(0)}%</span></div>`).join('')}</div>
    <div class="tiny muted">${esc(m.note)} Version ${esc(m.model_version)}, trained ${fmtDate(m.trained_on)}.</div>`
    : '<div class="badge warn">Model not trained</div>';

  $('#security-status').innerHTML = `
    <div style="display:grid;gap:10px;font-size:13.5px;">
      <div>${chain.verified ? '<span class="badge ok"><span class="dot"></span>Audit chain verified</span>' : `<span class="badge bad"><span class="dot"></span>Audit chain BROKEN at entry #${chain.first_broken_id}</span>`}</div>
      <div><b>Passwords:</b> Argon2id, 10+ chars, lockout after repeated failures</div>
      <div><b>Data at rest:</b> patient identifiers and results encrypted (Fernet / AES)</div>
      <div><b>Sessions:</b> HttpOnly, SameSite=Strict, CSRF-protected, idle timeout ${me.session_idle_minutes} min</div>
      <div><b>Access:</b> role-based; patients see only their own results</div>
    </div>`;
  enableAll();
}

/* ---------- users ---------- */
async function loadUsers({ background = false } = {}) {
  const users = await api('/api/admin/users', { background });
  if (!changed('users', users)) return;
  $('#users-table').innerHTML = `<tr><th>User</th><th>Role</th><th>Status</th><th>Last sign-in</th><th></th></tr>` + users.map((u) => {
    const locked = u.locked_until && new Date(u.locked_until) > new Date();
    const status = !u.active ? '<span class="badge bad">Deactivated</span>' : locked ? '<span class="badge warn">Locked</span>'
      : u.must_change_password ? '<span class="badge neutral">Awaiting first sign-in</span>' : '<span class="badge ok">Active</span>';
    return `<tr>
      <td><b>${esc(u.display_name || '')}</b><div class="tiny muted">${esc(u.username)}</div></td>
      <td style="text-transform:capitalize;">${esc(u.role)}</td><td>${status}</td>
      <td class="tiny">${u.last_login_at ? fmtDate(u.last_login_at) : '—'}</td>
      <td class="num" style="white-space:nowrap;">
        <button class="btn ghost sm" data-reset="${u.id}">Reset password</button>
        ${u.id === me.id ? '' : `<button class="btn ${u.active ? 'danger' : ''} sm" data-active="${u.id}" data-to="${!u.active}">${u.active ? 'Deactivate' : 'Activate'}</button>`}
      </td></tr>`;
  }).join('');
  document.querySelectorAll('[data-reset]').forEach((b) => b.addEventListener('click', async () => {
    try {
      const res = await api(`/api/admin/users/${b.dataset.reset}`, { method: 'PATCH', json: { reset_password: true } });
      showSecret('Password reset', `User: <b>${esc(res.user.username)}</b><br>Temporary password: <b>${esc(res.temporary_password)}</b>`);
      loadUsers();
    } catch (err) { toast(err.detail, 'error'); }
  }));
  document.querySelectorAll('[data-active]').forEach((b) => b.addEventListener('click', async () => {
    try {
      await api(`/api/admin/users/${b.dataset.active}`, { method: 'PATCH', json: { active: b.dataset.to === 'true' } });
      loadUsers();
    } catch (err) { toast(err.detail, 'error'); }
  }));
}

$('#user-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  const errEl = $('#user-error');
  errEl.classList.remove('show');
  try {
    const res = await api('/api/admin/users', { method: 'POST', json: Object.fromEntries(f) });
    e.target.reset();
    showSecret('Account created', `User: <b>${esc(res.user.username)}</b> (${esc(res.user.role)})<br>Temporary password: <b>${esc(res.temporary_password)}</b>`);
    loadUsers();
  } catch (err) {
    errEl.textContent = err.detail;
    errEl.classList.add('show');
  }
});

/* ---------- audit ---------- */
async function loadAudit({ background = false } = {}) {
  const { chain, entries } = await api('/api/admin/audit?limit=300', { background });
  if (!changed('audit', [chain, entries[0]?.id])) return;
  $('#chain-badge').innerHTML = chain.verified
    ? `<span class="badge ok"><span class="dot"></span>Chain verified · ${chain.entries_checked} entries</span>`
    : `<span class="badge bad"><span class="dot"></span>Tampering detected at #${chain.first_broken_id}</span>`;
  $('#audit-table').innerHTML = `<tr><th>#</th><th>Time</th><th>User</th><th>Action</th><th>Target</th><th>IP</th><th>Result</th></tr>` +
    entries.map((e) => `<tr><td class="tiny muted">${e.id}</td><td class="tiny">${fmtDate(e.ts)}</td>
      <td>${esc(e.username || '—')}<div class="tiny muted">${esc(e.role || '')}</div></td>
      <td><code>${esc(e.action)}</code>${e.detail ? `<div class="tiny muted">${esc(e.detail)}</div>` : ''}</td>
      <td class="tiny">${esc(e.target || '')}</td><td class="tiny">${esc(e.ip || '')}</td>
      <td>${e.success ? '<span class="badge ok">ok</span>' : '<span class="badge bad">denied</span>'}</td></tr>`).join('');
}

loadOverview();
enableAll();
// Everything the doctor/nurse and patient devices do shows up here within ~5 s.
live(() => LOADERS[activeTab]({ background: true }), 5000);
