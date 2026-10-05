import { api, HOME_FOR_ROLE } from './api.js';
import { enableAll } from './motion.js';

const HINTS = {
  staff: 'Clinical staff: capture and analyse samples for your patients.',
  patient: 'Patients: view your own results using the login your care team gave you.',
  admin: 'College administrators: manage staff accounts and review the audit log.',
};
let portal = 'staff';

const $ = (sel) => document.querySelector(sel);
const showError = (id, msg) => { const el = $(id); el.textContent = msg; el.classList.remove('show'); void el.offsetWidth; el.classList.add('show'); };

document.querySelectorAll('.portal').forEach((btn) => btn.addEventListener('click', () => {
  document.querySelectorAll('.portal').forEach((b) => b.classList.toggle('active', b === btn));
  portal = btn.dataset.portal;
  $('#portal-hint').textContent = HINTS[portal];
  $('#login-form [name=username]').focus();
}));

$('.pw-toggle').addEventListener('click', (e) => {
  const input = $('#login-form [name=password]');
  input.type = input.type === 'password' ? 'text' : 'password';
  e.target.textContent = input.type === 'password' ? 'show' : 'hide';
});

function showChangePanel() {
  $('#signin-panel').classList.add('hidden');
  $('#change-panel').classList.remove('hidden');
  $('#change-form [name=current_password]').focus();
}

$('#login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = new FormData(e.target);
  const btn = $('#login-btn');
  btn.disabled = true;
  btn.textContent = 'Verifying…';
  try {
    const me = await api('/api/auth/login', {
      method: 'POST', json: { username: form.get('username'), password: form.get('password'), portal },
    });
    if (me.must_change_password) {
      $('#change-form [name=current_password]').value = form.get('password');
      showChangePanel();
      $('#change-form [name=new_password]').focus();
    } else {
      location.href = HOME_FOR_ROLE[me.role];
    }
  } catch (err) {
    showError('#login-error', err.detail || 'Sign-in failed.');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Sign in securely';
  }
});

$('#change-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  if (f.get('new_password') !== f.get('repeat')) { showError('#change-error', 'The new passwords do not match.'); return; }
  try {
    await api('/api/auth/change-password', {
      method: 'POST', json: { current_password: f.get('current_password'), new_password: f.get('new_password') },
    });
    const me = await api('/api/auth/me');
    location.href = HOME_FOR_ROLE[me.role];
  } catch (err) {
    showError('#change-error', err.detail || 'Could not change password.');
  }
});

// Halo rings drift gently away from the pointer (parallax).
const stage = document.querySelector('[data-parallax]');
if (stage && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  window.addEventListener('pointermove', (e) => {
    const x = (e.clientX / innerWidth - 0.5) * -26;
    const y = (e.clientY / innerHeight - 0.5) * -26;
    stage.style.translate = `${x}px ${y}px`;
  });
}

// Initial state: already signed in? forced password change? expired session?
(async () => {
  const params = new URLSearchParams(location.search);
  if (params.has('expired')) showError('#login-error', 'Your session ended. Please sign in again.');
  try {
    const me = await fetch('/api/auth/me', { credentials: 'same-origin' });
    if (me.ok) {
      const user = await me.json();
      if (user.must_change_password) showChangePanel();
      else if (!params.has('expired')) location.href = HOME_FOR_ROLE[user.role];
    }
  } catch { /* offline: stay on the form */ }
})();

enableAll();
