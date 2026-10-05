// Shared API helper: same-origin cookies, CSRF header on writes, auth redirects.

export const LABELS = {
  csf_like: 'CSF-like', saline_like: 'Saline-like', saliva_like: 'Saliva-like',
  tear_like: 'Tear-like', nasal_mucus_like: 'Nasal mucus-like', other: 'Other / atypical',
};
export const color = (cls) => `var(--c-${cls in LABELS ? cls : 'other'})`;
export const label = (cls) => LABELS[cls] || cls || '—';

export class ApiError extends Error {
  constructor(status, detail) { super(detail); this.status = status; this.detail = detail; }
}

function csrfToken() {
  const m = document.cookie.match(/(?:^|; )halo_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : '';
}

export async function api(path, { method = 'GET', json, form } = {}) {
  const headers = {};
  let body;
  if (json !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(json); }
  if (form) body = form;
  if (method !== 'GET') headers['X-CSRF-Token'] = csrfToken();

  const resp = await fetch(path, { method, headers, body, credentials: 'same-origin' });
  let data = null;
  try { data = await resp.json(); } catch { /* empty body */ }

  if (!resp.ok) {
    const detail = (data && (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))) || resp.statusText;
    if (resp.status === 401 && !path.startsWith('/api/auth/login')) {
      location.href = '/?expired=1';
    } else if (resp.status === 403 && detail === 'password_change_required') {
      location.href = '/?change=1';
    }
    throw new ApiError(resp.status, detail);
  }
  return data;
}

export const HOME_FOR_ROLE = { admin: '/admin.html', doctor: '/clinician.html', nurse: '/clinician.html', patient: '/patient.html' };

/** Ensures a signed-in user with one of `roles`; otherwise redirects. Returns /api/auth/me. */
export async function requireUser(roles) {
  let me;
  try { me = await api('/api/auth/me'); } catch { return new Promise(() => {}); }
  if (me.must_change_password) { location.href = '/?change=1'; return new Promise(() => {}); }
  if (!roles.includes(me.role)) { location.href = HOME_FOR_ROLE[me.role] || '/'; return new Promise(() => {}); }
  return me;
}

export function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

export function initials(name) {
  return (name || '?').split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('');
}

export function toast(message, kind = 'info') {
  let stack = document.querySelector('.toast-stack');
  if (!stack) { stack = document.createElement('div'); stack.className = 'toast-stack'; document.body.append(stack); }
  const t = document.createElement('div');
  t.className = `toast ${kind === 'error' ? 'error' : ''}`;
  t.textContent = message;
  stack.append(t);
  setTimeout(() => t.remove(), 4200);
}

export function fmtDate(iso) {
  return new Date(iso).toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

/** Fills the shared top bar (name, role, logout). */
export function mountTopbar(me) {
  const name = me.display_name || me.username;
  document.querySelector('[data-user-name]').textContent = name;
  document.querySelector('[data-user-avatar]').textContent = initials(name);
  document.querySelector('[data-user-role]').textContent = me.role;
  document.querySelector('[data-logout]').addEventListener('click', async () => {
    try { await api('/api/auth/logout', { method: 'POST' }); } finally { location.href = '/'; }
  });
}

export function openModal(id) { document.getElementById(id).classList.add('open'); }
export function closeModal(id) { document.getElementById(id).classList.remove('open'); }
document.addEventListener('click', (e) => {
  const close = e.target.closest('[data-close-modal]');
  if (close) close.closest('.modal-backdrop').classList.remove('open');
  if (e.target.classList?.contains('modal-backdrop')) e.target.classList.remove('open');
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') document.querySelectorAll('.modal-backdrop.open, .lightbox.open').forEach((m) => m.classList.remove('open'));
});
