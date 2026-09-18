// compare.js — handles the Compare page interactions.
document.getElementById('compareBtn').addEventListener('click', async () => {
  const a = document.getElementById('pickA').value;
  const b = document.getElementById('pickB').value;
  if (!a || !b) return toast('Select two colleges', 'error');
  if (a === b)  return toast('Pick two different colleges', 'error');

  const res = await fetch('/api/compare', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ a, b })
  });
  if (!res.ok) return toast('Compare failed', 'error');
  const d = await res.json(); render(d);
});

function render(d){
  const box = document.getElementById('compareResult');
  const win = d.winner;
  const rows = [
    ['Annual Fee',    fmt(d.a.annual_fee, '₹'), fmt(d.b.annual_fee, '₹'),      d.a.annual_fee < d.b.annual_fee ? 'A':'B'],
    ['Avg Package',   fmt(d.a.average_package, '₹'), fmt(d.b.average_package, '₹'), d.a.average_package > d.b.average_package ? 'A':'B'],
    ['Highest Pkg',   fmt(d.a.highest_package, '₹'), fmt(d.b.highest_package, '₹'), d.a.highest_package > d.b.highest_package ? 'A':'B'],
    ['Placement %',   d.a.placement_percentage + '%', d.b.placement_percentage + '%', d.a.placement_percentage > d.b.placement_percentage ? 'A':'B'],
    ['ROI',           d.a.roi, d.b.roi, d.a.roi > d.b.roi ? 'A':'B'],
    ['NAAC',          d.a.naac_grade, d.b.naac_grade, ''],
    ['Student Rating',d.a.student_rating, d.b.student_rating, d.a.student_rating > d.b.student_rating ? 'A':'B'],
    ['Old Elo',       d.old_elo.a, d.old_elo.b, ''],
    ['New Elo',       d.new_elo.a, d.new_elo.b, ''],
  ];
  box.innerHTML = `
    <div class="compare-grid">
      <div class="card compare-col ${win==='A'?'winner':''}"><h2>${d.a.college_name}</h2>
        <p class="muted">Weighted score: <strong>${d.score_a.total}</strong></p></div>
      <div class="card compare-col ${win==='B'?'winner':''}"><h2>${d.b.college_name}</h2>
        <p class="muted">Weighted score: <strong>${d.score_b.total}</strong></p></div>
    </div>
    <div class="card">
      <h3>Winner: ${win==='DRAW' ? 'Draw' : (win==='A' ? d.a.college_name : d.b.college_name)}</h3>
      ${rows.map(r => `
        <div class="compare-row">
          <span>${r[0]}</span>
          <span class="${r[3]==='A'?'win':''}">${r[1]}</span>
          <span class="${r[3]==='B'?'win':''}">${r[2]}</span>
        </div>`).join('')}
    </div>
    <div class="card"><h3>Weighted score breakdown</h3>
      <pre>${JSON.stringify({A: d.score_a, B: d.score_b, weights: d.weights}, null, 2)}</pre>
    </div>
    <div class="card"><h3>Radar comparison</h3><canvas id="cmpRadar" height="220"></canvas></div>
  `;
  box.classList.remove('hidden');
  drawCollegeRadar('cmpRadar', d.a, d.b);
  toast('Comparison saved. Elo updated.');
}

function fmt(n, prefix=''){ return prefix + Number(n).toLocaleString(); }
