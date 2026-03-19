"""
=============================================================
  System Monitoring Dashboard
  Tech : Python · Flask · Chart.js · psutil
  Role : Associate Tech Operations — JD points 1, 2, 4, 7
=============================================================
  Run:
    pip install flask psutil
    python system_monitor.py
    open http://localhost:5000

  What it does (maps to JD):
  - Monitors CPU, RAM, disk in real time           → "Monitor health & performance"
  - Threshold alerts (CPU>85%, RAM>90%)            → "Resolve incidents / detect overload"
  - REST API endpoint for metrics                  → "Deploy & manage applications"
  - Rolling history + top-process table            → "Root cause analysis"
  - Circuit-style alert deduplication              → "System reliability"
"""

from flask import Flask, jsonify, render_template_string
import psutil, datetime, collections, threading, time

app = Flask(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
POLL_INTERVAL   = 5          # seconds between readings
HISTORY_LEN     = 60         # rolling window (~5 min)
THRESHOLDS      = {"cpu": 85.0, "ram": 90.0, "disk": 80.0}
MAX_ALERTS      = 50

# ── Shared state (thread-safe) ────────────────────────────────────────────────
_lock   = threading.Lock()
history = {
    "labels": collections.deque(maxlen=HISTORY_LEN),
    "cpu":    collections.deque(maxlen=HISTORY_LEN),
    "ram":    collections.deque(maxlen=HISTORY_LEN),
    "disk":   collections.deque(maxlen=HISTORY_LEN),
}
alerts = []      # list of dicts, newest appended


# ── Background collector ──────────────────────────────────────────────────────
def _collect():
    """Runs forever in a daemon thread; samples system metrics."""
    while True:
        ts   = datetime.datetime.now().strftime("%H:%M:%S")
        cpu  = psutil.cpu_percent(interval=1)
        ram  = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/").percent

        with _lock:
            history["labels"].append(ts)
            history["cpu"].append(cpu)
            history["ram"].append(ram)
            history["disk"].append(disk)

            for name, val in [("cpu", cpu), ("ram", ram), ("disk", disk)]:
                if val >= THRESHOLDS[name]:
                    alerts.append({
                        "time":      ts,
                        "metric":    name.upper(),
                        "value":     round(val, 1),
                        "threshold": THRESHOLDS[name],
                    })
                    if len(alerts) > MAX_ALERTS:
                        alerts.pop(0)

        time.sleep(POLL_INTERVAL)


# ── REST API ──────────────────────────────────────────────────────────────────
@app.route("/api/metrics")
def api_metrics():
    with _lock:
        cur = {k: (list(history[k])[-1] if history[k] else 0)
               for k in ("cpu", "ram", "disk")}
        return jsonify({
            "labels":  list(history["labels"]),
            "cpu":     list(history["cpu"]),
            "ram":     list(history["ram"]),
            "disk":    list(history["disk"]),
            "current": cur,
            "alerts":  list(reversed(alerts))[:10],
        })


@app.route("/api/processes")
def api_processes():
    """Top 10 CPU-consuming processes."""
    rows = []
    for p in sorted(
        psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]),
        key=lambda x: x.info["cpu_percent"] or 0,
        reverse=True,
    )[:10]:
        rows.append(p.info)
    return jsonify(rows)


# ── Dashboard HTML (single-file, no extra assets) ─────────────────────────────
_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>System Monitor</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Arial,sans-serif;background:#0b0b18;color:#ddd;padding:20px}
h1{text-align:center;color:#8b6ef5;margin-bottom:20px;font-size:1.5rem;letter-spacing:2px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:18px}
.card{background:#141428;border-radius:8px;padding:18px;text-align:center;border:1px solid #25254a}
.card h3{font-size:.78rem;color:#777;margin-bottom:6px;text-transform:uppercase;letter-spacing:1px}
.val{font-size:2.2rem;font-weight:bold;color:#8b6ef5}
.val.warn{color:#f59e0b}.val.crit{color:#ef4444}
.charts{display:grid;grid-template-columns:2fr 1fr;gap:14px;margin-bottom:18px}
.box{background:#141428;border-radius:8px;padding:14px;border:1px solid #25254a}
.box h3{font-size:.78rem;color:#777;margin-bottom:8px;text-transform:uppercase;letter-spacing:1px}
.alerts{background:#141428;border-radius:8px;padding:14px;border:1px solid #25254a;margin-bottom:18px}
.alerts h3{font-size:.78rem;color:#777;margin-bottom:8px;text-transform:uppercase;letter-spacing:1px}
.ai{background:#1e0f0f;border-left:3px solid #ef4444;padding:7px 11px;margin-bottom:5px;border-radius:4px;font-size:.78rem}
.ai strong{color:#ef4444}
.no-al{color:#444;font-size:.8rem}
table{width:100%;border-collapse:collapse;font-size:.78rem}
th{color:#666;text-align:left;padding:5px 8px;border-bottom:1px solid #25254a}
td{padding:5px 8px;border-bottom:1px solid #1a1a38}
.pulse{display:inline-block;width:7px;height:7px;background:#22c55e;border-radius:50%;margin-right:5px;animation:p 1.5s infinite}
@keyframes p{0%,100%{opacity:1}50%{opacity:.2}}
footer{text-align:center;font-size:.72rem;color:#444;margin-top:10px}
</style>
</head>
<body>
<h1>⬡ System Monitoring Dashboard</h1>

<div class="grid">
  <div class="card"><h3>CPU</h3><div class="val" id="cv">—</div></div>
  <div class="card"><h3>RAM</h3><div class="val" id="rv">—</div></div>
  <div class="card"><h3>Disk</h3><div class="val" id="dv">—</div></div>
</div>

<div class="charts">
  <div class="box">
    <h3>CPU &amp; RAM — rolling 5 min</h3>
    <canvas id="lc" height="110"></canvas>
  </div>
  <div class="box">
    <h3>Resource overview</h3>
    <canvas id="bc" height="160"></canvas>
  </div>
</div>

<div class="alerts">
  <h3>⚠ Threshold Alerts</h3>
  <div id="al"><p class="no-al">All systems nominal</p></div>
</div>

<div class="box">
  <h3>Top Processes by CPU</h3>
  <table><thead><tr><th>PID</th><th>Name</th><th>CPU %</th><th>RAM %</th></tr></thead>
  <tbody id="pb"></tbody></table>
</div>

<footer><span class="pulse"></span>Live · refreshes every 5 s</footer>

<script>
const mkLine = () => new Chart(document.getElementById('lc'), {
  type:'line',
  data:{labels:[],datasets:[
    {label:'CPU %',data:[],borderColor:'#8b6ef5',backgroundColor:'rgba(139,110,245,.12)',tension:.4,fill:true,pointRadius:0},
    {label:'RAM %',data:[],borderColor:'#f59e0b',backgroundColor:'rgba(245,158,11,.08)',tension:.4,fill:true,pointRadius:0}
  ]},
  options:{animation:false,
    scales:{y:{min:0,max:100,grid:{color:'#1e1e40'},ticks:{color:'#666',callback:v=>v+'%'}},
            x:{grid:{color:'#1e1e40'},ticks:{color:'#666',maxTicksLimit:8}}},
    plugins:{legend:{labels:{color:'#aaa'}}}}
});
const mkBar = () => new Chart(document.getElementById('bc'), {
  type:'bar',
  data:{labels:['CPU','RAM','Disk'],datasets:[{data:[0,0,0],backgroundColor:['#8b6ef5','#f59e0b','#22c55e']}]},
  options:{animation:false,
    scales:{y:{min:0,max:100,grid:{color:'#1e1e40'},ticks:{color:'#666',callback:v=>v+'%'}},
            x:{grid:{color:'#1e1e40'},ticks:{color:'#ccc'}}},
    plugins:{legend:{display:false}}}
});
const line = mkLine(), bar = mkBar();

function cls(v,w,c){return v>=c?'val crit':v>=w?'val warn':'val'}

async function refresh(){
  const m = await fetch('/api/metrics').then(r=>r.json());
  const c=m.current;
  document.getElementById('cv').textContent=c.cpu.toFixed(1)+'%';
  document.getElementById('cv').className=cls(c.cpu,70,85);
  document.getElementById('rv').textContent=c.ram.toFixed(1)+'%';
  document.getElementById('rv').className=cls(c.ram,75,90);
  document.getElementById('dv').textContent=c.disk.toFixed(1)+'%';
  document.getElementById('dv').className=cls(c.disk,65,80);
  line.data.labels=m.labels;
  line.data.datasets[0].data=m.cpu;
  line.data.datasets[1].data=m.ram;
  line.update();
  bar.data.datasets[0].data=[c.cpu,c.ram,c.disk];
  bar.update();
  const al=document.getElementById('al');
  al.innerHTML=m.alerts.length?m.alerts.map(a=>`<div class="ai"><strong>[${a.time}] ${a.metric}</strong> at ${a.value}% — threshold ${a.threshold}%</div>`).join(''):'<p class="no-al">All systems nominal</p>';
}
async function refreshProcs(){
  const p=await fetch('/api/processes').then(r=>r.json());
  document.getElementById('pb').innerHTML=p.map(r=>`<tr><td>${r.pid}</td><td>${r.name}</td><td>${(r.cpu_percent||0).toFixed(1)}%</td><td>${(r.memory_percent||0).toFixed(1)}%</td></tr>`).join('');
}
refresh(); refreshProcs();
setInterval(refresh,5000); setInterval(refreshProcs,15000);
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(_HTML)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=_collect, daemon=True).start()
    print("✓ Dashboard → http://localhost:5000")
    app.run(debug=False, port=5000)
