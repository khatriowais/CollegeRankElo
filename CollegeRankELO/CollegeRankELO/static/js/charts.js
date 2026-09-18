// charts.js — all Chart.js rendering.
const BLUE = '#2563eb', LIGHT = '#93c5fd';

async function drawTopEloChart(canvasId){
  const res = await fetch('/api/leaderboard'); const rows = (await res.json()).slice(0,20);
  new Chart(document.getElementById(canvasId), {
    type: 'bar',
    data: {
      labels: rows.map(r => r.college_name),
      datasets: [{ label: 'Elo', data: rows.map(r => r.elo_rating),
                   backgroundColor: BLUE, borderRadius: 6 }]
    },
    options: { responsive: true,
      plugins: { legend: { display: false } },
      scales: { x: { ticks: { autoSkip:false, maxRotation:70, minRotation:60, font:{size:9} } } }
    }
  });
}

function drawEloHistoryChart(id, history, name){
  new Chart(document.getElementById(id), {
    type: 'line',
    data: {
      labels: history.map(h => h.t.slice(0,10)),
      datasets: [{ label: name + ' Elo', data: history.map(h => h.r),
                   borderColor: BLUE, backgroundColor: 'rgba(37,99,235,.15)',
                   tension: .3, fill: true }]
    }
  });
}

function drawCollegeRadar(id, c, other){
  const datasets = [{
    label: c.college_name,
    data: radarValues(c),
    borderColor: BLUE, backgroundColor: 'rgba(37,99,235,.25)'
  }];
  if (other) datasets.push({
    label: other.college_name, data: radarValues(other),
    borderColor: '#f97316', backgroundColor: 'rgba(249,115,22,.25)'
  });
  new Chart(document.getElementById(id), {
    type: 'radar',
    data: { labels: ['Elo','Package','Placement','ROI','Rating','NAAC'], datasets },
    options: { scales: { r: { beginAtZero:true, suggestedMax:100 } } }
  });
}

function radarValues(c){
  const naacMap = {'A++':100,'A+':90,'A':80,'B++':70,'B+':60,'B':50,'C':40};
  return [
    Math.min(100, (c.elo_rating - 1200) / 8),
    Math.min(100, c.average_package / 20000),
    c.placement_percentage,
    Math.min(100, c.roi * 5),
    (c.student_rating || 0) * 20,
    naacMap[c.naac_grade] || 50,
  ];
}
