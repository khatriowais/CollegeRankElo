// compare.js — handles the Compare page interactions.
(function(){
  const btn = document.getElementById('compareBtn');
  if (!btn) return;
  btn.addEventListener('click', runCompare);

  const cohortFilter = document.getElementById('cohortFilter');
  if (cohortFilter) {
    cohortFilter.addEventListener('change', () => {
      const ch = cohortFilter.value;
      ['pickA', 'pickB'].forEach(id => {
        const sel = document.getElementById(id);
        if (!sel) return;
        const opts = sel.querySelectorAll('option');
        opts.forEach(opt => {
          if (!opt.value) return; // Keep placeholder
          const optCh = opt.getAttribute('data-cohort');
          if (ch === 'all' || optCh === ch) {
            opt.hidden = false;
            opt.disabled = false;
          } else {
            opt.hidden = true;
            opt.disabled = true;
          }
        });
        // If current selection is now hidden, reset it
        const curOpt = sel.selectedOptions[0];
        if (curOpt && curOpt.disabled) sel.value = '';
      });
    });
    // Trigger initial filter
    cohortFilter.dispatchEvent(new Event('change'));
  }

  ['pickA','pickB'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', () => {
      // Prevent picking the same college twice.
      const a = document.getElementById('pickA').value;
      const b = document.getElementById('pickB').value;
      if (a && a === b) toast('Pick two different colleges', 'error');
    });
  });

  async function runCompare(){
    const a = document.getElementById('pickA').value;
    const b = document.getElementById('pickB').value;
    if (!a || !b) return toast('Select two colleges first', 'error');
    if (a === b)  return toast('Pick two different colleges', 'error');

    btn.disabled = true;
    const old = btn.textContent; btn.textContent = 'Comparing…';
    const box = document.getElementById('compareResult');
    box.classList.remove('hidden');
    box.innerHTML = `<div class="card"><div class="skeleton" style="height:26px;width:45%"></div><div class="skeleton" style="height:14px;margin-top:10px"></div><div class="skeleton" style="height:14px;margin-top:8px;width:70%"></div></div>`;
    try {
      const res = await fetch('/api/compare', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ a, b })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || 'Compare failed');
      }
      const d = await res.json(); render(d);
      toast('Comparison saved — Elo updated.');
    } catch (e) {
      box.innerHTML = `<div class="card"><div class="empty">⚠️ ${escapeHtml(e.message)}. Please try again.</div></div>`;
      toast(e.message, 'error');
    } finally {
      btn.disabled = false; btn.textContent = old;
    }
  }

  function render(d){
    const box = document.getElementById('compareResult');
    const win = d.winner;
    const winnerName = win==='DRAW' ? 'It’s a draw' : (win==='A' ? d.a.college_name : d.b.college_name) + ' wins';
    const deltaA = (d.new_elo.a - d.old_elo.a).toFixed(1);
    const deltaB = (d.new_elo.b - d.old_elo.b).toFixed(1);
    const cmpWin = (x, y, higherWins=true) => {
      if (x == null || y == null || x === y) return '';
      return (x > y) === higherWins ? 'A' : 'B';
    };
    const sym = (d.a.currency === 'USD' || d.b.currency === 'USD') ? '$' : '₹';
    const loc = (d.a.currency === 'USD' || d.b.currency === 'USD') ? 'en-US' : 'en-IN';
    const pct = v => v == null ? '—' : v + '%';
    const mult = v => v == null ? '—' : v + '×';
    const rating = v => v == null ? '—' : v + ' / 5';
    const rows = [
      ['Annual fee',      fmt(d.a.annual_fee, sym, loc),      fmt(d.b.annual_fee, sym, loc),      cmpWin(d.a.annual_fee, d.b.annual_fee, false)],
      ['Avg package',     fmt(d.a.average_package, sym, loc), fmt(d.b.average_package, sym, loc), cmpWin(d.a.average_package, d.b.average_package)],
      ['Highest package', fmt(d.a.highest_package, sym, loc), fmt(d.b.highest_package, sym, loc), cmpWin(d.a.highest_package, d.b.highest_package)],
      ['Placement %',     pct(d.a.placement_percentage),      pct(d.b.placement_percentage),      cmpWin(d.a.placement_percentage, d.b.placement_percentage)],
      ['ROI',             mult(d.a.roi),                      mult(d.b.roi),                      cmpWin(d.a.roi, d.b.roi)],
      ['NAAC',            d.a.naac_grade || '—',              d.b.naac_grade || '—',              ''],
      ['Student rating',  rating(d.a.student_rating),         rating(d.b.student_rating),         cmpWin(d.a.student_rating, d.b.student_rating)],
      ['Elo before',      d.old_elo.a,                        d.old_elo.b,                        ''],
      ['Elo after',       `${d.new_elo.a} (${signed(deltaA)})`, `${d.new_elo.b} (${signed(deltaB)})`, ''],
    ];
    const maxScore = Math.max(d.score_a.total, d.score_b.total, 1);

    // Build courses comparison
    const coursesA = Array.isArray(d.a.courses) ? d.a.courses : [];
    const coursesB = Array.isArray(d.b.courses) ? d.b.courses : [];

    box.innerHTML = `
      <div class="banner"><span class="trophy">${win==='DRAW' ? '🤝' : '🏆'}</span>
        <div><strong style="font-size:1.08rem">${escapeHtml(winnerName)}</strong><br />
        <span class="muted small">Weighted ${d.score_a.total} vs ${d.score_b.total} · Expected win prob ${(d.expected.a*100).toFixed(1)}% vs ${(d.expected.b*100).toFixed(1)}%</span></div>
        <span style="margin-left:auto">${win==='DRAW' ? '<span class="pill pill-draw">Draw</span>' : '<span class="pill pill-win">Decisive</span>'}</span>
      </div>
      <div class="compare-grid">
        <div class="card compare-col ${win==='A'?'winner':''}">
          ${win==='A' ? '<span class="pill pill-win winner-ribbon">Winner</span>' : ''}
          <div class="muted small"><strong>COLLEGE A</strong></div>
          <h2 style="margin-top:4px">${escapeHtml(d.a.college_name)}</h2>
          <div class="score-big">${d.score_a.total}</div>
          <div class="muted small">weighted score</div>
          <div class="meter"><i style="width:${(d.score_a.total/maxScore*100).toFixed(1)}%"></i></div>
          <p class="muted small">Elo ${d.old_elo.a} → <strong>${d.new_elo.a}</strong> (${signed(deltaA)})</p>
          <a class="btn btn-sm" href="/college/${d.a.id}">Open profile →</a>
        </div>
        <div class="card compare-col ${win==='B'?'winner':''}">
          ${win==='B' ? '<span class="pill pill-win winner-ribbon">Winner</span>' : ''}
          <div class="muted small"><strong>COLLEGE B</strong></div>
          <h2 style="margin-top:4px">${escapeHtml(d.b.college_name)}</h2>
          <div class="score-big">${d.score_b.total}</div>
          <div class="muted small">weighted score</div>
          <div class="meter orange"><i style="width:${(d.score_b.total/maxScore*100).toFixed(1)}%"></i></div>
          <p class="muted small">Elo ${d.old_elo.b} → <strong>${d.new_elo.b}</strong> (${signed(deltaB)})</p>
          <a class="btn btn-sm" href="/college/${d.b.id}">Open profile →</a>
        </div>
      </div>
      <div class="card">
        <h3>Metric-by-metric</h3>
        <div class="compare-row" style="color:var(--muted);font-weight:700"><span>Metric</span><span>A</span><span>B</span></div>
        ${rows.map(r => `
          <div class="compare-row">
            <span class="k">${r[0]}</span>
            <span class="v ${r[3]==='A'?'win':''}">${escapeHtml(String(r[1]))} ${r[3]==='A'?'●':''}</span>
            <span class="v ${r[3]==='B'?'win':''}">${escapeHtml(String(r[2]))} ${r[3]==='B'?'●':''}</span>
          </div>`).join('')}
      </div>

      ${(coursesA.length > 0 || coursesB.length > 0) ? `
      <div class="card" style="margin-top:14px">
        <h3>📚 Degree Programs & Courses Breakdown</h3>
        <div class="two-col" style="gap:20px">
          <div>
            <h4>${escapeHtml(d.a.college_name)} (${coursesA.length} courses)</h4>
            <ul style="padding-left:18px;margin:8px 0;font-size:0.9rem">
              ${coursesA.map(c => `<li><strong>${escapeHtml(c.course_name)}</strong> (${escapeHtml(c.duration||'')}): <span style="color:var(--accent,#4338ca)">${fmt(c.annual_fee, sym, loc)}/yr</span></li>`).join('')}
            </ul>
          </div>
          <div>
            <h4>${escapeHtml(d.b.college_name)} (${coursesB.length} courses)</h4>
            <ul style="padding-left:18px;margin:8px 0;font-size:0.9rem">
              ${coursesB.map(c => `<li><strong>${escapeHtml(c.course_name)}</strong> (${escapeHtml(c.duration||'')}): <span style="color:var(--accent,#4338ca)">${fmt(c.annual_fee, sym, loc)}/yr</span></li>`).join('')}
            </ul>
          </div>
        </div>
      </div>` : ''}

      <div class="two-col" style="margin-top:14px">
        <div class="card"><h3>Score breakdown</h3>${breakdownBars(d.score_a, d.score_b, d.weights)}</div>
        <div class="card"><h3>Radar comparison</h3><canvas id="cmpRadar" height="230"></canvas></div>
      </div>
    `;
    box.classList.remove('hidden');
    box.scrollIntoView({behavior:'smooth', block:'start'});
    if (window.drawCollegeRadar) drawCollegeRadar('cmpRadar', d.a, d.b);
  }

  function breakdownBars(sa, sb, weights){
    const keys = [['roi','ROI'],['placement','Placement'],['package','Package'],['fees','Fees'],['naac','NAAC']];
    return keys.map(([k,label]) => {
      const w = Math.round((weights[k]||0)*100);
      const va = sa[k] ?? 0, vb = sb[k] ?? 0;
      const mx = Math.max(va, vb, 1);
      return `<div style="margin:10px 0"><div style="display:flex;justify-content:space-between;font-size:.84rem"><strong>${label} <span class="muted">· ${w}%</span></strong><span class="muted">${va} vs ${vb}</span></div>
        <div class="meter"><i style="width:${(va/mx*100).toFixed(1)}%"></i></div>
        <div class="meter orange" style="margin-top:4px"><i style="width:${(vb/mx*100).toFixed(1)}%"></i></div></div>`;
    }).join('');
  }

  function signed(n){ n = Number(n); return (n >= 0 ? '+' : '') + n; }
  function fmt(n, prefix='₹', loc='en-IN'){ return n == null ? '—' : prefix + Number(n).toLocaleString(loc); }
  function escapeHtml(s){
    return String(s ?? '').replace(/[&<>"']/g, m =>
      ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  }
})();
