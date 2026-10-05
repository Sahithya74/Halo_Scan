import { api, closeModal, color, esc, fmtDate, initials, label, mountTopbar, openModal, requireUser, toast } from './api.js';
import { enableAll } from './motion.js';
import { renderResult } from './result-view.js';

const $ = (sel) => document.querySelector(sel);
const RECORD_SECONDS = 10;
const CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="4"><path d="M5 12l5 5L20 7"/></svg>';

const state = { patient: null, mode: 'photo', stream: null, captured: null, recorder: null, busy: false };

const me = await requireUser(['doctor', 'nurse']);
mountTopbar(me);
enableAll();

api('/api/health').then((h) => {
  const el = $('#model-status');
  el.className = `badge ${h.model_loaded ? 'ok' : 'warn'}`;
  el.innerHTML = `<span class="dot"></span>${h.model_loaded ? `Model ${esc(h.model_version)} ready` : 'Model not trained'}`;
});

/* ---------------- patients ---------------- */
let searchTimer;
async function loadPatients(q = '') {
  const list = $('#patient-list');
  try {
    const patients = await api(`/api/patients${q ? `?q=${encodeURIComponent(q)}` : ''}`);
    if (!patients.length) {
      list.innerHTML = `<div class="tiny muted" style="padding:10px;">${q ? 'No matching patients.' : 'No patients yet — register one.'}</div>`;
      return;
    }
    list.innerHTML = patients.map((p) => `
      <div class="patient-item ${state.patient?.id === p.id ? 'selected' : ''}" data-id="${p.id}">
        <span class="avatar">${esc(initials(p.name))}</span>
        <div><div style="font-weight:700;">${esc(p.name)}</div>
          <div class="meta">${esc(p.patient_code)} · MRN ${esc(p.mrn)}${p.sex ? ` · ${esc(p.sex)}` : ''}</div></div>
      </div>`).join('');
    list.querySelectorAll('.patient-item').forEach((el) => el.addEventListener('click', () => {
      selectPatient(patients.find((p) => p.id === Number(el.dataset.id)));
    }));
  } catch (err) {
    list.innerHTML = `<div class="form-error show">${esc(err.detail)}</div>`;
  }
}

async function selectPatient(p) {
  state.patient = p;
  document.querySelectorAll('.patient-item').forEach((el) => el.classList.toggle('selected', Number(el.dataset.id) === p.id));
  $('#patient-selected').classList.remove('hidden');
  updateAnalyzeButton();
  await loadPatientHistory();
}

async function loadPatientHistory() {
  const box = $('#patient-history');
  const items = await api(`/api/patients/${state.patient.id}/analyses`);
  if (!items.length) { box.innerHTML = '<div class="tiny muted">No analyses yet for this patient.</div>'; return; }
  box.innerHTML = items.slice(0, 8).map((a) => `
    <div class="patient-item" data-analysis="${esc(a.analysis_id)}" style="padding:8px;">
      <span class="dot" style="color:${a.research_classification ? color(a.research_classification) : 'var(--text-3)'};width:10px;height:10px;"></span>
      <div style="flex:1;"><div style="font-weight:700;font-size:13px;">${esc(a.research_classification ? label(a.research_classification) : a.quality_status)}
        ${a.confidence != null ? `<span class="muted">${(a.confidence * 100).toFixed(0)}%</span>` : ''}${a.uncertain ? ' <span class="badge warn">uncertain</span>' : ''}</div>
        <div class="meta">${fmtDate(a.timestamp)} · ${esc(a.input_type)}</div></div>
    </div>`).join('');
  box.querySelectorAll('[data-analysis]').forEach((el) => el.addEventListener('click', async () => {
    const r = await api(`/api/analysis/${encodeURIComponent(el.dataset.analysis)}`);
    renderResult($('#results'), r);
    $('#results').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }));
}

$('#patient-search').addEventListener('input', (e) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadPatients(e.target.value.trim()), 250);
});

$('#register-btn').addEventListener('click', () => {
  $('#register-form').reset();
  $('#register-form-wrap').classList.remove('hidden');
  $('#register-done').classList.add('hidden');
  $('#register-error').classList.remove('show');
  openModal('register-modal');
  $('#register-form [name=name]').focus();
});

$('#register-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  try {
    const res = await api('/api/patients', { method: 'POST', json: {
      name: f.get('name'), mrn: f.get('mrn'), dob: f.get('dob') || null, sex: f.get('sex') || null,
      create_login: f.get('create_login') === 'on',
    } });
    await loadPatients();
    selectPatient(res.patient);
    if (res.login) {
      $('#register-secret').innerHTML = `Patient: <b>${esc(res.patient.name)}</b> (${esc(res.patient.patient_code)})<br>
        Username: <b>${esc(res.login.username)}</b><br>Temporary password: <b>${esc(res.login.temporary_password)}</b>`;
      $('#register-form-wrap').classList.add('hidden');
      $('#register-done').classList.remove('hidden');
    } else {
      closeModal('register-modal');
      toast(`Registered ${res.patient.name}`);
    }
  } catch (err) {
    const el = $('#register-error');
    el.textContent = err.detail;
    el.classList.add('show');
  }
});

/* ---------------- capture ---------------- */
const video = $('#camera-video');

function show(id, visible) { $(id).classList.toggle('hidden', !visible); }

function setCaptured(blob, kind, filename) {
  state.captured = blob ? { blob, kind, filename } : null;
  show('#photo-preview', false);
  show('#video-preview', false);
  if (blob) {
    const url = URL.createObjectURL(blob);
    if (kind === 'video') { $('#video-preview').src = url; show('#video-preview', true); }
    else { $('#photo-preview').src = url; show('#photo-preview', true); }
    show('#camera-video', false);
    show('#guide', false);
    show('#camera-msg', false);
    $('#capture-status').innerHTML = `<span class="badge ok"><span class="dot"></span>${kind === 'video' ? 'Video' : 'Photo'} ready</span>
      <span class="muted">${(blob.size / 1024).toFixed(0)} KB · ${esc(filename)}</span>`;
  } else {
    $('#capture-status').textContent = 'Nothing captured yet.';
  }
  updateAnalyzeButton();
}

function updateAnalyzeButton() {
  const btn = $('#analyze-btn');
  btn.disabled = !(state.patient && state.captured) || state.busy;
  btn.textContent = !state.patient ? 'Select a patient first' : !state.captured ? 'Capture a sample first' : `Analyse ${state.captured.kind}`;
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    toast('Camera needs HTTPS or localhost. Use Upload instead.', 'error');
    return;
  }
  try {
    state.stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 960 } }, audio: false,
    });
    video.srcObject = state.stream;
    await video.play();
    setCaptured(null);
    show('#camera-video', true);
    show('#guide', true);
    show('#camera-msg', false);
    $('#shoot-btn').disabled = false;
    $('#cam-btn').textContent = 'Retake';
  } catch (err) {
    toast(`Camera unavailable: ${err.message}`, 'error');
  }
}

function stopCamera() {
  state.stream?.getTracks().forEach((t) => t.stop());
  state.stream = null;
  show('#camera-video', false);
  show('#guide', false);
  $('#shoot-btn').disabled = true;
  $('#cam-btn').textContent = 'Start camera';
}

function capturePhoto() {
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);
  canvas.toBlob((blob) => {
    stopCamera();
    $('#cam-btn').textContent = 'Retake';
    setCaptured(blob, 'photo', `capture-${Date.now()}.jpg`);
  }, 'image/jpeg', 0.92);
}

function pickRecorderType() {
  const options = ['video/mp4;codecs=avc1', 'video/mp4', 'video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm'];
  return options.find((t) => window.MediaRecorder && MediaRecorder.isTypeSupported(t)) || '';
}

function recordVideo() {
  if (state.recorder) { state.recorder.stop(); return; }  // second press = stop early
  const type = pickRecorderType();
  if (!window.MediaRecorder) { toast('Recording is not supported in this browser. Use Upload.', 'error'); return; }
  const chunks = [];
  const rec = new MediaRecorder(state.stream, type ? { mimeType: type, videoBitsPerSecond: 4_000_000 } : undefined);
  state.recorder = rec;
  rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  const ring = $('#countdown-ring');
  const C = 157.1;
  const started = performance.now();
  show('#rec-badge', true);
  show('#countdown', true);
  $('#shoot-btn').textContent = 'Stop';
  const tick = setInterval(() => {
    const elapsed = (performance.now() - started) / 1000;
    const left = Math.max(0, RECORD_SECONDS - elapsed);
    $('#countdown-num').textContent = Math.ceil(left);
    ring.setAttribute('stroke-dashoffset', String(C * (elapsed / RECORD_SECONDS)));
    if (left <= 0 && rec.state === 'recording') rec.stop();
  }, 100);
  rec.onstop = () => {
    clearInterval(tick);
    state.recorder = null;
    show('#rec-badge', false);
    show('#countdown', false);
    $('#shoot-btn').textContent = 'Record 10s';
    const mime = (rec.mimeType || type || 'video/webm').split(';')[0];
    const blob = new Blob(chunks, { type: mime });
    stopCamera();
    $('#cam-btn').textContent = 'Retake';
    setCaptured(blob, 'video', `capture-${Date.now()}.${mime.includes('mp4') ? 'mp4' : 'webm'}`);
  };
  rec.start(250);
}

$('#cam-btn').addEventListener('click', () => (state.stream ? stopCamera() : startCamera()));
$('#shoot-btn').addEventListener('click', () => (state.mode === 'video' ? recordVideo() : capturePhoto()));
$('#choose-btn').addEventListener('click', () => $('#file-input').click());
$('#file-input').addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (file) setCaptured(file, file.type.startsWith('video/') ? 'video' : 'photo', file.name);
});

document.querySelectorAll('#mode-tabs button').forEach((btn) => btn.addEventListener('click', () => {
  if (state.recorder) return;
  document.querySelectorAll('#mode-tabs button').forEach((b) => b.classList.toggle('active', b === btn));
  state.mode = btn.dataset.mode;
  const upload = state.mode === 'upload';
  show('#actions-camera', !upload);
  show('#actions-upload', upload);
  if (upload) stopCamera();
  $('#shoot-btn').textContent = state.mode === 'video' ? 'Record 10s' : 'Capture photo';
}));

/* ---------------- analysis ---------------- */
function stagesFor(kind) {
  const common = ['Quality check', 'Sample region located', 'Halo rings detected', 'Rings measured',
    'Features extracted', 'AI ensemble prediction', 'Comparison & confidence', 'Report generated'];
  return kind === 'video' ? ['Video decoded · frames sampled', ...common] : ['Image received', ...common];
}

function runStages(kind) {
  const names = stagesFor(kind);
  const box = $('#stages');
  box.classList.remove('hidden');
  box.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
      <span class="tiny muted" style="font-weight:700;">Processing on secure server</span><span class="timer" id="timer">0.0s</span></div>
    ${names.map((n, i) => `<div class="stage" data-i="${i}"><span class="bullet">${CHECK}</span>${n}</div>`).join('')}`;
  const start = performance.now();
  let i = 0;
  const per = kind === 'video' ? 1400 : 380;
  const mark = () => {
    box.querySelectorAll('.stage').forEach((el, j) => {
      el.classList.toggle('done', j < i);
      el.classList.toggle('active', j === i);
    });
  };
  mark();
  const stepTimer = setInterval(() => { if (i < names.length - 1) { i++; mark(); } }, per);
  const clock = setInterval(() => { $('#timer').textContent = `${((performance.now() - start) / 1000).toFixed(1)}s`; }, 100);
  return (ok) => {
    clearInterval(stepTimer);
    clearInterval(clock);
    if (ok) { i = names.length; mark(); }
    setTimeout(() => box.classList.add('hidden'), ok ? 1500 : 0);
  };
}

$('#analyze-btn').addEventListener('click', async () => {
  if (!state.patient || !state.captured || state.busy) return;
  state.busy = true;
  updateAnalyzeButton();
  $('#analyze-btn').textContent = 'Analysing…';
  const finish = runStages(state.captured.kind);
  const form = new FormData();
  form.append('patient_id', state.patient.id);
  form.append('file', state.captured.blob, state.captured.filename);
  try {
    const result = await api('/api/analyze', { method: 'POST', form });
    finish(true);
    renderResult($('#results'), result);
    $('#results').scrollIntoView({ behavior: 'smooth', block: 'start' });
    loadPatientHistory();
    const c = result.classification;
    toast(c ? `${label(c.research_classification)} · ${(c.confidence * 100).toFixed(0)}% confidence` : result.status.replaceAll('_', ' '));
  } catch (err) {
    finish(false);
    toast(err.detail || 'Analysis failed', 'error');
  } finally {
    state.busy = false;
    updateAnalyzeButton();
  }
});

window.addEventListener('pagehide', stopCamera);
loadPatients();
updateAnalyzeButton();
