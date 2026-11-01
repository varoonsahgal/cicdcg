/* Pipeline Academy · shared behaviour: theme, nav, progress, copy buttons,
   image zoom, hint/solution styling, per-lab completion tracking, quiz scoring. */
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const KEY = 'pipeline-academy';
  const store = { get(k, d) { try { return JSON.parse(localStorage.getItem(KEY + ':' + k)) ?? d; } catch { return d; } }, set(k, v) { try { localStorage.setItem(KEY + ':' + k, JSON.stringify(v)); } catch {} } };

  /* theme */
  const root = document.documentElement;
  const applyTheme = t => { if (t) root.setAttribute('data-theme', t); else root.removeAttribute('data-theme'); };
  applyTheme(store.get('theme', null) || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : null));
  $('#theme')?.addEventListener('click', () => { const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark'; applyTheme(next); store.set('theme', next); });

  /* mobile nav */
  const menu = $('.menu-btn'), nav = $('.nav');
  menu?.addEventListener('click', () => { const open = nav.classList.toggle('open'); menu.setAttribute('aria-expanded', open); });

  /* reading progress */
  const bar = $('#readbar');
  const onScroll = () => { if (!bar) return; const h = document.documentElement; const max = h.scrollHeight - h.clientHeight; bar.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + '%'; };
  addEventListener('scroll', onScroll, { passive: true }); onScroll();

  /* copy buttons on code blocks */
  $$('pre').forEach(pre => {
    const b = document.createElement('button'); b.className = 'copy'; b.type = 'button'; b.textContent = 'Copy';
    b.addEventListener('click', async () => { try { await navigator.clipboard.writeText(pre.innerText.replace(/\nCopy$/, '')); b.textContent = 'Copied'; b.classList.add('ok'); setTimeout(() => { b.textContent = 'Copy'; b.classList.remove('ok'); }, 1400); } catch { b.textContent = 'Select & copy'; } });
    pre.appendChild(b);
  });

  /* screenshots: click to zoom */
  $$('img.shot').forEach(img => {
    img.addEventListener('click', () => {
      if (img.classList.contains('zoomed')) { img.classList.remove('zoomed'); $('.dim')?.remove(); return; }
      const dim = document.createElement('div'); dim.className = 'dim'; dim.addEventListener('click', () => { img.classList.remove('zoomed'); dim.remove(); });
      document.body.appendChild(dim); img.classList.add('zoomed');
    });
  });
  addEventListener('keydown', e => { if (e.key === 'Escape') { $$('img.shot.zoomed').forEach(i => i.classList.remove('zoomed')); $('.dim')?.remove(); } });

  /* completion tracking: a lab page marks itself done when the reader
     reaches its "What you learned" section; the nav shows a star. */
  const page = document.body.dataset.page;
  const done = store.get('done', {});
  const paintDone = () => $$('.nav a[data-lab]').forEach(a => a.classList.toggle('is-done', !!done[a.dataset.lab]));
  paintDone();
  if (page && /^lab/.test(page)) {
    const target = $$('h2').find(h => /what you learned/i.test(h.textContent));
    if (target && 'IntersectionObserver' in window) {
      new IntersectionObserver((es, io) => { if (es.some(e => e.isIntersecting)) { done[page] = Date.now(); store.set('done', done); paintDone(); io.disconnect(); } }, { threshold: .2 }).observe(target);
    }
  }

  /* quiz scoring: each quiz <details> opened counts as "checked" */
  const quiz = $$('details.reveal.quiz');
  if (quiz.length) {
    const sc = document.createElement('p'); sc.className = 'quiz-score';
    quiz[0].parentNode.insertBefore(sc, quiz[0]);
    const paint = () => { const n = quiz.filter(q => q.open).length; sc.textContent = n ? `${n} of ${quiz.length} answers revealed` : `${quiz.length} questions · answer in your head first, then reveal`; };
    quiz.forEach(q => q.addEventListener('toggle', paint)); paint();
  }

  /* masthead ember / packet animation */
  const cv = $('canvas.mast-fx');
  if (cv && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const ctx = cv.getContext('2d'); let w, h, ps = [];
    const size = () => { w = cv.width = cv.offsetWidth * devicePixelRatio; h = cv.height = cv.offsetHeight * devicePixelRatio; };
    const spawn = () => ({ x: -20, y: h * (0.2 + Math.random() * 0.7), v: (0.6 + Math.random() * 1.2) * devicePixelRatio, r: (1 + Math.random() * 2) * devicePixelRatio, c: ['#22C55E', '#38BDF8', '#F59E0B'][Math.floor(Math.random() * 3)], a: 0.25 + Math.random() * 0.5 });
    size(); addEventListener('resize', size);
    for (let i = 0; i < 40; i++) { const p = spawn(); p.x = Math.random() * w; ps.push(p); }
    const frame = () => {
      ctx.clearRect(0, 0, w, h);
      ps.forEach(p => { p.x += p.v; if (p.x > w + 20) Object.assign(p, spawn()); ctx.globalAlpha = p.a; ctx.fillStyle = p.c; ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2); ctx.fill(); ctx.globalAlpha = p.a * 0.35; ctx.fillRect(p.x - p.r * 12, p.y - p.r * 0.4, p.r * 12, p.r * 0.8); });
      requestAnimationFrame(frame);
    };
    frame();
  }

  /* pipeline strip demo in the hero: cycles through states */
  const strip = $('.strip[data-demo]');
  if (strip) {
    const st = $$('.stage', strip); let i = 0, failAt = 2, tick = 0;
    setInterval(() => {
      tick++;
      st.forEach((s, k) => { s.classList.remove('run', 'ok', 'bad'); if (k < i) s.classList.add('ok'); if (k === i) s.classList.add(i === failAt && tick % 2 === 0 ? 'bad' : 'run'); });
      if (i === failAt && tick % 2 === 0) { setTimeout(() => { i = 0; }, 1400); i = 99; return; }
      i = i >= st.length - 1 ? 0 : i + 1;
    }, 1100);
  }
})();
