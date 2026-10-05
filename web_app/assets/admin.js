import { api, color, esc, fmtDate, label, mountTopbar, openModal, requireUser, toast } from './api.js';
import { countUp, enableAll } from './motion.js';

const $ = (sel) => document.querySelector(sel);
const me = await requireUser(['admin']);
mountTopbar(me);

document.querySelectorAll('#tabs button').forEach((btn) => btn.addEventListener('click', () => {
  document.querySelectorAll('#tabs button').forEach((b) => b.classList.toggle('active', b === btn));
  document.querySelectorAll('[data-panel]').forEach((p) => p.classList.toggle('hidden', p.dataset.panel !== btn.dataset.tab));
  ({ overview: loadOverview, users: loadUsers, audit: loadAudit })[btn.dataset.tab]();
}));

function showSecret(title, html) {
  $('#secret-title').textContent = title;
  $('#secret-body').innerHTML = html;
  openModal('secret-modal');
}

/* ---------- overview ---------- */
async function loadOverview() {
  const [stats, audit] = await Promise.all([api('/api/admin/stats'), api('/api/admin/audit?limit=1')]);
  const r = stats.users_by_role;
  const total = Object.values(stats.analyses_by_result).reduce((a, b) => a + b, 0);
  const tiles = [
    ['Doctors', r.doctor || 0], ['Nurses', r.nurse || 0], ['Administrators', r.admin || 0],
    ['Patients', stats.patients], ['Analyses', total], ['Audit entries', audit.chain.entries_checked],
  ];
  $('#overview-stats').innerHTML = tiles.map(([l, v]) => `<div class="stat" data-tilt="6"><div class="v" data-count="${v}">0</div><div class="l">${l}</div></div>`).join('');
  document.querySelectorAll('#overview-stats [data-count]').forEach((el) => countUp(el, Number(el.dataset.count)));

  const rows = Object.entries(stats.analyses_by_result).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...rows.map((x) => x[1]));
  $('#by-result').innerHTML = rows.length ? rows.map(([k, n]) => `
    <div class="sim-row"><span>${esc(label(k))}</span>
      <span class="track"><i style="background:${color(k)};width:${(n / max) * 100}%"></i></span><span class="num">${n}</span></div>`).join('')
    : '<div class="muted tiny">No analyses recorded yet.</div>';

  const m = stats.model_card;
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

  const chain = audit.chain;
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
async function loadUsers() {
  const users = await api('/api/admin/users');
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
async function loadAudit() {
  const { chain, entries } = await api('/api/admin/audit?limit=300');
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
