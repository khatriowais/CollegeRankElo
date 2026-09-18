// main.js — theme toggle, live search, leaderboard filtering & pagination.
(function initTheme(){
  const saved = localStorage.getItem('theme');
  if (saved === 'dark') document.documentElement.classList.add('dark');
  document.addEventListener('click', e => {
    if (e.target && e.target.id === 'themeToggle') {
      document.documentElement.classList.toggle('dark');
      localStorage.setItem('theme',
        document.documentElement.classList.contains('dark') ? 'dark' : 'light');
    }
  });
})();

// Global autocomplete on the home hero.
(async function initGlobalSearch(){
  const input = document.getElementById('globalSearch');
  if (!input) return;
  const list = document.getElementById('globalSearchResults');
  const res = await fetch('/api/colleges'); const data = await res.json();
  input.addEventListener('input', () => {
    const q = input.value.trim().toLowerCase();
    if (!q) { list.classList.remove('open'); return; }
    const hits = data.filter(c => c.college_name.toLowerCase().includes(q)).slice(0, 8);
    list.innerHTML = hits.map(c =>
      `<li><a href="/college/${c.id}">${c.college_name} <small style="color:var(--muted)">· Elo ${c.elo_rating}</small></a></li>`).join('');
    list.classList.toggle('open', hits.length > 0);
  });
  document.addEventListener('click', e => {
    if (!list.contains(e.target) && e.target !== input) list.classList.remove('open');
  });
})();

const NAAC_ORDER = {'A++':7,'A+':6,'A':5,'B++':4,'B+':3,'B':2,'C':1};

function initLeaderboard(){
  const data = (window.__COLLEGES__ || []).slice();
  const body = document.getElementById('lbBody');
  const sType = document.getElementById('lbType');
  const sCity = document.getElementById('lbCity');
  const sSort = document.getElementById('lbSort');
  const sSearch = document.getElementById('lbSearch');
  const prev = document.getElementById('prevPage');
  const next = document.getElementById('nextPage');
  const info = document.getElementById('pageInfo');
  const cities = [...new Set(data.map(c => c.city))].sort();
  sCity.insertAdjacentHTML('beforeend',
    cities.map(c => `<option>${c}</option>`).join(''));

  let page = 1; const perPage = 15;

  function apply(){
    let rows = data.filter(c =>
      (!sType.value || c.type === sType.value) &&
      (!sCity.value || c.city === sCity.value) &&
      (!sSearch.value || c.college_name.toLowerCase().includes(sSearch.value.toLowerCase())));
    const key = sSort.value;
    const cmp = {
      elo_rating: (a,b) => b.elo_rating - a.elo_rating,
      roi: (a,b) => b.roi - a.roi,
      average_package: (a,b) => b.average_package - a.average_package,
      placement_percentage: (a,b) => b.placement_percentage - a.placement_percentage,
      annual_fee_asc: (a,b) => a.annual_fee - b.annual_fee,
      naac: (a,b) => (NAAC_ORDER[b.naac_grade]||0) - (NAAC_ORDER[a.naac_grade]||0),
    }[key];
    rows.sort(cmp);
    const pages = Math.max(1, Math.ceil(rows.length / perPage));
    if (page > pages) page = pages;
    const slice = rows.slice((page-1)*perPage, page*perPage);
    body.innerHTML = slice.map((c,i) => `
      <tr>
        <td>${(page-1)*perPage + i + 1}</td>
        <td><a href="/college/${c.id}">${c.college_name}</a> <small style="color:var(--muted)">${c.city}</small></td>
        <td><strong>${c.elo_rating}</strong></td>
        <td>₹${c.average_package.toLocaleString()}</td>
        <td>${c.placement_percentage}%</td>
        <td>₹${c.annual_fee.toLocaleString()}</td>
        <td>${c.roi}</td>
        <td><span class="badge">${c.naac_grade}</span></td>
      </tr>`).join('');
    info.textContent = `Page ${page} / ${pages} · ${rows.length} results`;
  }
  [sType,sCity,sSort,sSearch].forEach(el => el.addEventListener('input', () => { page = 1; apply(); }));
  prev.addEventListener('click', () => { if (page>1){page--;apply();}});
  next.addEventListener('click', () => { page++; apply(); });
  apply();
}

function toast(msg, kind='ok'){
  const el = document.createElement('div');
  el.className = 'toast toast-' + kind; el.textContent = msg;
  document.querySelector('main.container').prepend(el);
  setTimeout(() => el.remove(), 3500);
}
window.toast = toast;
