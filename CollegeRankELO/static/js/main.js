// main.js — theme, nav, search, leaderboard, toasts.
(function initThemeIcon(){
  const paint = () => {
    const b = document.getElementById('themeToggle');
    if (b) b.textContent = document.documentElement.classList.contains('dark') ? '☀️' : '🌙';
  };
  paint();
  document.addEventListener('click', e => {
    const themeBtn = e.target.closest('#themeToggle');
    if (themeBtn) {
      document.documentElement.classList.toggle('dark');
      try {
        localStorage.setItem('theme',
          document.documentElement.classList.contains('dark') ? 'dark' : 'light');
      } catch (err) {}
      paint();
      return;
    }
    const t = document.getElementById('navToggle');
    const links = document.getElementById('navLinks');
    if (t && links) {
      if (t.contains(e.target)) {
        const open = links.classList.toggle('open');
        t.setAttribute('aria-expanded', open ? 'true' : 'false');
      } else if (!links.contains(e.target) || e.target.closest('a')) {
        if (links.classList.contains('open')) {
          links.classList.remove('open');
          t.setAttribute('aria-expanded', 'false');
        }
      }
    }
  });
  document.addEventListener('DOMContentLoaded', paint);
})();

// Global autocomplete on the home hero.
(function initGlobalSearch(){
  const input = document.getElementById('globalSearch');
  if (!input) return;
  const list = document.getElementById('globalSearchResults');
  let data = [];
  fetch('/api/colleges').then(r => r.json()).then(d => { data = d; }).catch(() => {});
  let debounce;
  input.addEventListener('input', () => {
    clearTimeout(debounce);
    debounce = setTimeout(() => {
      const q = input.value.trim().toLowerCase();
      if (!q || !data.length) { list.classList.remove('open'); list.innerHTML=''; return; }
      const hits = data.filter(c => (c.college_name||'').toLowerCase().includes(q) ||
        (c.city||'').toLowerCase().includes(q) ||
        (c.region||'').toLowerCase().includes(q)).slice(0, 8);
      list.innerHTML = hits.length
        ? hits.map(c => {
            const sub = c.is_ranked
              ? `Elo ${c.elo_rating} · ${escapeHtml(c.city||'')}`
              : `Directory · ${escapeHtml(c.region || c.country || 'India')}`;
            return `<li><a href="/college/${c.id}"><span>${escapeHtml(c.college_name)}</span><small>${sub}</small></a></li>`;
          }).join('')
        : `<li><a><span>No matches</span><small>try another spelling</small></a></li>`;
      list.classList.toggle('open', true);
    }, 120);
  });
  document.addEventListener('click', e => {
    if (!list.contains(e.target) && e.target !== input) list.classList.remove('open');
  });
  window.addEventListener('scroll', () => {
    if (list.classList.contains('open')) list.classList.remove('open');
  }, { passive: true });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') list.classList.remove('open');
  });
})();

const NAAC_ORDER = {'A++':7,'A+':6,'A':5,'B++':4,'B+':3,'B':2,'C':1};

function initLeaderboard(){
  const raw = (window.__COLLEGES__ || []).slice();
  const body = document.getElementById('lbBody');
  if (!body) return;
  const sCohort = document.getElementById('lbCohort');
  const sType = document.getElementById('lbType');
  const sCity = document.getElementById('lbCity');
  const sSort = document.getElementById('lbSort');
  const sSearch = document.getElementById('lbSearch');
  const prev = document.getElementById('prevPage');
  const next = document.getElementById('nextPage');
  const info = document.getElementById('pageInfo');
  const count = document.getElementById('lbCount');
  const empty = document.getElementById('lbEmpty');
  const cities = [...new Set(raw.map(c => c.city).filter(Boolean))].sort();
  cities.forEach(c => {
    const o = document.createElement('option'); o.textContent = c; sCity.appendChild(o);
  });

  let page = 1; const perPage = 15;

  function formatMoney(amount, currency) {
    if (amount == null) return '—';
    const sym = currency === 'USD' ? '$' : '₹';
    const loc = currency === 'USD' ? 'en-US' : 'en-IN';
    return sym + Number(amount).toLocaleString(loc);
  }

  function apply(){
    const q = (sSearch.value||'').trim().toLowerCase();
    const cohortVal = sCohort ? sCohort.value : '';
    let rows = raw.filter(c => {
      if (cohortVal && c.cohort !== cohortVal) return false;
      if (sType.value && c.type !== sType.value) return false;
      if (sCity.value && c.city !== sCity.value) return false;
      if (!q) return true;
      const matchName = (c.college_name||'').toLowerCase().includes(q);
      const matchCity = (c.city||'').toLowerCase().includes(q);
      const matchRegion = (c.region||'').toLowerCase().includes(q);
      const matchCourses = Array.isArray(c.courses) && c.courses.some(crs =>
        (crs.course_name||'').toLowerCase().includes(q) ||
        (crs.specialization||'').toLowerCase().includes(q)
      );
      return matchName || matchCity || matchRegion || matchCourses;
    });

    const key = sSort.value;
    const cmp = {
      elo_rating: (a,b) => (b.elo_rating||0) - (a.elo_rating||0),
      roi: (a,b) => (b.roi||0) - (a.roi||0),
      average_package: (a,b) => (b.average_package||0) - (a.average_package||0),
      placement_percentage: (a,b) => (b.placement_percentage||0) - (a.placement_percentage||0),
      annual_fee_asc: (a,b) => (a.annual_fee||0) - (b.annual_fee||0),
      naac: (a,b) => (NAAC_ORDER[b.naac_grade]||0) - (NAAC_ORDER[a.naac_grade]||0),
    }[key] || ((a,b) => (b.elo_rating||0)-(a.elo_rating||0));
    rows.sort(cmp);
    const pages = Math.max(1, Math.ceil(rows.length / perPage));
    if (page > pages) page = pages;
    if (page < 1) page = 1;
    const slice = rows.slice((page-1)*perPage, page*perPage);
    body.innerHTML = slice.length ? slice.map((c,i) => {
      const numCourses = Array.isArray(c.courses) ? c.courses.length : 0;
      const courseSnippet = numCourses > 0 ? ` · <span style="color:var(--accent,#4338ca)">${numCourses} programs</span>` : '';
      return `
      <tr>
        <td class="muted">${(page-1)*perPage + i + 1}</td>
        <td class="college-cell">
          <a href="/college/${c.id}">${escapeHtml(c.college_name)}</a>
          <small>${escapeHtml(c.city||'')} · ${escapeHtml(c.type||'')}${courseSnippet}</small>
        </td>
        <td><strong>${c.elo_rating}</strong></td>
        <td>${formatMoney(c.average_package, c.currency)}</td>
        <td>${c.placement_percentage==null?'—':c.placement_percentage+'%'}</td>
        <td>${formatMoney(c.annual_fee, c.currency)}</td>
        <td>${c.roi==null?'—':c.roi+'×'}</td>
        <td><span class="badge">${escapeHtml(c.naac_grade||'—')}</span></td>
      </tr>`;
    }).join('')
      : `<tr><td colspan="8" class="muted" style="text-align:center;padding:26px">No results.</td></tr>`;
    info.textContent = `Page ${page} / ${pages} · ${rows.length} result${rows.length===1?'':'s'}`;
    if (count) count.textContent = rows.length === raw.length ? `All colleges (${rows.length})` : `Filtered · ${rows.length} of ${raw.length}`;
    if (empty) empty.classList.toggle('hidden', rows.length > 0);
    prev.disabled = page <= 1; next.disabled = page >= pages;
  }
  let deb;
  sSearch.addEventListener('input', () => { clearTimeout(deb); deb = setTimeout(()=>{page=1;apply();}, 140); });
  [sCohort, sType, sCity, sSort].filter(Boolean).forEach(el => el.addEventListener('input', () => { page = 1; apply(); }));
  const clr = document.getElementById('lbClear');
  if (clr) clr.addEventListener('click', () => {
    sSearch.value=''; if (sCohort) sCohort.value=''; sType.value=''; sCity.value=''; sSort.value='elo_rating'; page=1; apply();
  });
  prev.addEventListener('click', () => { if (page>1){page--;apply();}});
  next.addEventListener('click', () => { page++; apply(); });
  apply();
}

function escapeHtml(s){
  return String(s ?? '').replace(/[&<>"']/g, m =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}

function toast(msg, kind='ok'){
  const main = document.querySelector('main.container');
  if (!main) return;
  const el = document.createElement('div');
  el.className = 'toast toast-' + (kind === 'error' ? 'error' : 'ok');
  el.setAttribute('role','status');
  el.textContent = msg;
  main.prepend(el);
  setTimeout(() => { el.style.opacity='0'; el.style.transition='opacity .3s'; setTimeout(()=>el.remove(), 320); }, 3400);
}
window.toast = toast;
