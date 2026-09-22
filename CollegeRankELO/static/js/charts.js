// charts.js — all Chart.js rendering (theme-aware).
let __charts = {};
function chartTheme(){
  const dark = document.documentElement.classList.contains('dark');
  return {
    tick: dark ? '#9aa6bd' : '#64748b',
    grid: dark ? 'rgba(148,163,184,.14)' : 'rgba(100,116,139,.14)',
    bar: dark ? '#818cf8' : '#4338ca',
  };
}
function kill(id){
  if (__charts[id]) { try { __charts[id].destroy(); } catch(e){} delete __charts[id]; }
}

async function drawTopEloChart(canvasId){
  const el = document.getElementById(canvasId);
  if (!el || typeof Chart === 'undefined') return;
  kill(canvasId);
  let rows = [];
  try {
    const res = await fetch('/api/leaderboard');
    rows = await res.json();
  } catch(e){ return; }
  if (!rows || !rows.length) return;

  const t = chartTheme();
  const isMobile = window.innerWidth < 680;
  // On mobile: show top 10 as horizontal bars (crystal-clear labels without rotation).
  // On desktop/tablet: show top 20 as vertical bars.
  const limit = isMobile ? 10 : 20;
  const topRows = rows.slice(0, limit);

  if (isMobile) {
    const minRating = Math.max(0, Math.floor(Math.min(...topRows.map(r => r.elo_rating || 1500)) - 100));
    __charts[canvasId] = new Chart(el, {
      type: 'bar',
      data: {
        labels: topRows.map((r, i) => {
          const name = r.college_name || '';
          return name.length > 20 ? name.slice(0, 19) + '…' : name;
        }),
        datasets: [{
          label: 'Elo',
          data: topRows.map(r => r.elo_rating),
          backgroundColor: topRows.map((_, i) => i < 3 ? '#f59e0b' : t.bar),
          borderRadius: 6,
          barPercentage: 0.76,
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: items => topRows[items[0].dataIndex].college_name,
              label: item => `Elo rating: ${item.raw}`
            }
          }
        },
        scales: {
          x: {
            min: minRating,
            ticks: { color: t.tick, font: { size: 10 } },
            grid: { color: t.grid }
          },
          y: {
            ticks: { color: t.tick, font: { size: 10, weight: '600' } },
            grid: { display: false }
          }
        }
      }
    });
  } else {
    __charts[canvasId] = new Chart(el, {
      type: 'bar',
      data: {
        labels: topRows.map(r => r.college_name.length > 24 ? r.college_name.slice(0, 22) + '…' : r.college_name),
        datasets: [{
          label: 'Elo',
          data: topRows.map(r => r.elo_rating),
          backgroundColor: topRows.map((_, i) => i < 3 ? '#f59e0b' : t.bar),
          borderRadius: 7,
          maxBarThickness: 28
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: items => topRows[items[0].dataIndex].college_name,
              label: item => `Elo: ${item.raw}`
            }
          }
        },
        scales: {
          x: {
            ticks: { autoSkip: true, maxRotation: 45, minRotation: 20, font: { size: 10 }, color: t.tick },
            grid: { display: false }
          },
          y: {
            ticks: { color: t.tick },
            grid: { color: t.grid }
          }
        }
      }
    });
  }
}

// Re-draw chart on window resize (e.g. mobile orientation change)
let __chartResizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(__chartResizeTimer);
  __chartResizeTimer = setTimeout(() => {
    if (document.getElementById('topEloChart')) {
      drawTopEloChart('topEloChart');
    }
  }, 250);
});

function drawEloHistoryChart(id, history, name){
  const el = document.getElementById(id);
  if (!el || typeof Chart === 'undefined') return;
  kill(id);
  const t = chartTheme();
  const labels = (history||[]).map(h => (h.t||'').slice(0,10));
  const data = (history||[]).map(h => h.r);
  __charts[id] = new Chart(el, {
    type: 'line',
    data: { labels: labels.length ? labels : ['Start'],
      datasets: [{ label: (name||'College') + ' Elo',
        data: data.length ? data : [1500],
        borderColor: t.bar, backgroundColor: 'rgba(99,102,241,.16)',
        tension: .35, fill: true, pointRadius: 2.5, borderWidth: 2.5 }]},
    options: { responsive:true,
      plugins:{ legend:{ display:false } },
      scales:{ x:{ ticks:{ color:t.tick, maxTicksLimit:8 }, grid:{display:false} },
               y:{ ticks:{ color:t.tick }, grid:{color:t.grid} } } }
  });
}

function drawCollegeRadar(id, c, other){
  const el = document.getElementById(id);
  if (!el || typeof Chart === 'undefined' || !c) return;
  kill(id);
  const t = chartTheme();
  const datasets = [{
    label: c.college_name || 'College',
    data: radarValues(c),
    borderColor: t.bar, backgroundColor: 'rgba(99,102,241,.22)', pointRadius: 2
  }];
  if (other) datasets.push({
    label: other.college_name || 'Other', data: radarValues(other),
    borderColor: '#f97316', backgroundColor: 'rgba(249,115,22,.20)', pointRadius: 2
  });
  __charts[id] = new Chart(el, {
    type: 'radar',
    data: { labels: ['Elo','Package','Placement','ROI','Rating','NAAC'], datasets },
    options: { responsive:true,
      plugins:{ legend:{ position:'bottom', labels:{ color:t.tick, boxWidth:12 } } },
      scales: { r: { beginAtZero:true, suggestedMax:100,
        ticks:{ display:false }, grid:{ color:t.grid },
        angleLines:{ color:t.grid }, pointLabels:{ color:t.tick, font:{size:11} } } } }
  });
}

function radarValues(c){
  const naacMap = {'A++':100,'A+':90,'A':80,'B++':70,'B+':60,'B':50,'C':40};
  return [
    Math.max(0, Math.min(100, ((c.elo_rating||1500) - 1200) / 8)),
    Math.max(0, Math.min(100, (c.average_package||0) / 20000)),
    Math.max(0, Math.min(100, c.placement_percentage||0)),
    Math.max(0, Math.min(100, (c.roi||0) * 5)),
    Math.max(0, Math.min(100, (c.student_rating || 0) * 20)),
    naacMap[c.naac_grade] || 50,
  ];
}
