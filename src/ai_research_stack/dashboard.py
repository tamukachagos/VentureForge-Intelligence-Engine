from __future__ import annotations


def render_dashboard() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AI Research Stack</title>
  <style>
    :root {
      --bg: #f7f8fb;
      --panel: #ffffff;
      --ink: #121826;
      --muted: #657084;
      --line: #d8dee9;
      --accent: #1d6f5f;
      --warn: #a85f00;
      --bad: #a33131;
      --good: #176d3b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 14px;
      line-height: 1.4;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 18px 28px;
      background: var(--panel);
      border-bottom: 1px solid var(--line);
    }
    h1 {
      margin: 0;
      font-size: 20px;
      letter-spacing: 0;
    }
    main {
      display: grid;
      grid-template-columns: 280px 1fr;
      min-height: calc(100vh - 66px);
    }
    aside {
      padding: 22px;
      border-right: 1px solid var(--line);
      background: #fbfcfe;
    }
    section {
      padding: 22px 28px;
    }
    .metric {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      margin-bottom: 12px;
    }
    .metric strong {
      display: block;
      font-size: 22px;
      margin-top: 4px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }
    .panel h2 {
      margin: 0;
      padding: 14px 16px;
      font-size: 15px;
      border-bottom: 1px solid var(--line);
    }
    table {
      width: 100%;
      border-collapse: collapse;
    }
    th, td {
      text-align: left;
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }
    th {
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }
    .muted { color: var(--muted); }
    .status { font-weight: 650; color: var(--accent); }
    button {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: white;
      padding: 7px 10px;
      font: inherit;
      cursor: pointer;
    }
    button:hover { border-color: var(--accent); }
    @media (max-width: 860px) {
      main { grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <h1>AI Research Stack</h1>
    <button onclick="refresh()">Refresh</button>
  </header>
  <main>
    <aside>
      <div class="metric">
        <span class="muted">Daily Budget</span>
        <strong id="daily-budget">$15.00</strong>
      </div>
      <div class="metric">
        <span class="muted">Paid Data Month</span>
        <strong id="data-budget">$50.00</strong>
      </div>
      <div class="metric">
        <span class="muted">System Status</span>
        <strong id="system-status">Loading</strong>
      </div>
    </aside>
    <section>
      <div class="grid">
        <div class="metric"><span class="muted">Opportunities</span><strong id="opp-count">0</strong></div>
        <div class="metric"><span class="muted">Open Tasks</span><strong id="task-count">0</strong></div>
        <div class="metric"><span class="muted">Approvals</span><strong id="approval-count">0</strong></div>
      </div>
      <div class="panel">
        <h2>Opportunity Pipeline</h2>
        <table>
          <thead><tr><th>Opportunity</th><th>Stage</th><th>Score</th><th>Demand</th></tr></thead>
          <tbody id="opportunities"><tr><td colspan="4" class="muted">No opportunities yet.</td></tr></tbody>
        </table>
      </div>
    </section>
  </main>
  <script>
    async function refresh() {
      const [health, opportunities, tasks, budget] = await Promise.all([
        fetch('/health').then(r => r.json()),
        fetch('/api/opportunities').then(r => r.json()),
        fetch('/api/tasks').then(r => r.json()),
        fetch('/api/budget').then(r => r.json())
      ]);
      document.getElementById('system-status').textContent = health.status;
      document.getElementById('opp-count').textContent = opportunities.opportunities.length;
      document.getElementById('task-count').textContent = tasks.tasks.length;
      document.getElementById('approval-count').textContent = '0';
      document.getElementById('daily-budget').textContent = '$' + budget.daily_llm_cap.toFixed(2);
      document.getElementById('data-budget').textContent = '$' + budget.monthly_paid_data_cap.toFixed(2);
      const body = document.getElementById('opportunities');
      if (!opportunities.opportunities.length) {
        body.innerHTML = '<tr><td colspan="4" class="muted">No opportunities yet.</td></tr>';
        return;
      }
      body.innerHTML = opportunities.opportunities.map(opp => `
        <tr>
          <td>${escapeHtml(opp.title)}</td>
          <td><span class="status">${escapeHtml(opp.stage)}</span></td>
          <td>${opp.score ?? '-'}</td>
          <td>${escapeHtml(opp.demand ?? '-')}</td>
        </tr>
      `).join('');
    }
    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
      }[c]));
    }
    refresh();
  </script>
</body>
</html>
""".strip()

