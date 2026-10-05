// Pointer-driven motion. Everything is skipped when the user prefers reduced motion.
const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Cards with [data-tilt] lean toward the pointer in 3D, with a soft glare that follows it. */
export function enableTilt(root = document) {
  if (reduced) return;
  root.querySelectorAll('[data-tilt]:not([data-tilt-ready])').forEach((el) => {
    el.dataset.tiltReady = '1';
    const max = Number(el.dataset.tilt) || 6;
    if (getComputedStyle(el).position === 'static') el.style.position = 'relative';
    const glare = document.createElement('span');
    glare.className = 'tilt-glare';
    el.append(glare);
    el.addEventListener('pointermove', (e) => {
      const r = el.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width;
      const py = (e.clientY - r.top) / r.height;
      el.style.transition = 'transform .08s ease-out';
      el.style.transform = `perspective(900px) rotateX(${(0.5 - py) * max}deg) rotateY(${(px - 0.5) * max}deg) translateZ(0)`;
      el.style.setProperty('--gx', `${px * 100}%`);
      el.style.setProperty('--gy', `${py * 100}%`);
    });
    el.addEventListener('pointerleave', () => {
      el.style.transition = 'transform .5s cubic-bezier(.2,.8,.2,1)';
      el.style.transform = '';
    });
  });
}

/** Buttons with [data-magnetic] drift slightly toward the pointer. */
export function enableMagnetic(root = document) {
  if (reduced) return;
  root.querySelectorAll('[data-magnetic]:not([data-mag-ready])').forEach((el) => {
    el.dataset.magReady = '1';
    el.addEventListener('pointermove', (e) => {
      const r = el.getBoundingClientRect();
      const dx = e.clientX - (r.left + r.width / 2);
      const dy = e.clientY - (r.top + r.height / 2);
      el.style.transform = `translate(${dx * 0.12}px, ${dy * 0.18}px)`;
    });
    el.addEventListener('pointerleave', () => { el.style.transform = ''; });
  });
}

const io = 'IntersectionObserver' in window
  ? new IntersectionObserver((entries) => entries.forEach((en) => {
      if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); }
    }), { threshold: 0.12 })
  : null;

/** Elements with [data-reveal] fade/slide in as they scroll into view (staggered by order). */
export function enableReveal(root = document) {
  root.querySelectorAll('[data-reveal]:not(.in)').forEach((el, i) => {
    if (reduced || !io) { el.classList.add('in'); return; }
    el.style.transitionDelay = `${Math.min(i, 8) * 60}ms`;
    io.observe(el);
  });
}

/** Animates a number from 0 to `to` inside `el`. */
export function countUp(el, to, { decimals = 0, suffix = '', duration = 1100 } = {}) {
  if (reduced) { el.textContent = to.toFixed(decimals) + suffix; return; }
  const start = performance.now();
  const step = (now) => {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = (to * eased).toFixed(decimals) + suffix;
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

export function enableAll(root = document) {
  enableTilt(root);
  enableMagnetic(root);
  enableReveal(root);
}
