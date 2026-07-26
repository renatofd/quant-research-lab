from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .experiment_database import ExperimentDatabase
    from .ranking_engine import RankingEngine
except ImportError:
    from experiment_database import ExperimentDatabase
    from ranking_engine import RankingEngine


class HTMLDashboard:
    def __init__(
        self,
        database: ExperimentDatabase | None = None,
        ranking: RankingEngine | None = None,
    ) -> None:
        self.database = database or ExperimentDatabase()
        self.ranking = ranking or RankingEngine(self.database)

    def generate(
        self,
        output_path: Path | str | None = None,
        *,
        limit: int = 100,
    ) -> Path:
        output_path = Path(output_path or Path(__file__).resolve().parent / "dashboard.html")
        top = self.ranking.rank(limit=limit)
        completed = self.database.list_experiments(status="completed")
        payload = {
            "top": top,
            "strategy_rankings": self.ranking.strategy_rankings(limit=limit),
            "completed": completed,
            "status_counts": self._status_counts(),
        }
        output_path.write_text(self._render(payload), encoding="utf-8")
        return output_path

    def _status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for experiment in self.database.list_experiments():
            counts[experiment["status"]] = counts.get(experiment["status"], 0) + 1
        return counts

    def _render(self, payload: dict[str, Any]) -> str:
        data = json.dumps(payload, ensure_ascii=False)
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Freqtrade Experiment Dashboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
    header {{ display: flex; align-items: baseline; gap: 16px; margin-bottom: 18px; }}
    input, select {{ padding: 6px 8px; margin-right: 8px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 16px; font-size: 13px; }}
    th, td {{ border: 1px solid #d9e2ec; padding: 6px 8px; text-align: left; }}
    th {{ background: #f0f4f8; cursor: pointer; }}
    .charts {{ display: grid; grid-template-columns: repeat(2, minmax(320px, 1fr)); gap: 18px; }}
    canvas {{ width: 100%; height: 220px; border: 1px solid #d9e2ec; }}
    h2 {{ margin-top: 28px; }}
  </style>
</head>
<body>
  <header>
    <h1>Experiment Dashboard</h1>
    <span id="summary"></span>
  </header>
  <div>
    <input id="filter" placeholder="Filter experiment, pair, parameter..." />
    <select id="sort">
      <option value="computed_score">Score composto</option>
      <option value="profit_factor">Profit Factor</option>
      <option value="expectancy">Expectancy</option>
      <option value="max_drawdown_abs">Drawdown</option>
      <option value="profit_total_abs">Lucro liquido</option>
      <option value="sharpe">Sharpe</option>
    </select>
  </div>
  <div class="charts">
    <canvas id="profitFactor"></canvas>
    <canvas id="drawdown"></canvas>
    <canvas id="winrate"></canvas>
    <canvas id="scoreEvolution"></canvas>
  </div>
  <h2>Top 100 Experiments</h2>
  <table id="table"></table>
  <h2>Best Strategy Plugins</h2>
  <table id="strategyTable"></table>
  <h2>Best Parameter Combinations</h2>
  <table id="parameterTable"></table>
  <script>
    const payload = {data};
    const topRows = payload.top || [];
    const strategyRows = payload.strategy_rankings || [];
    const completed = payload.completed || [];
    const filter = document.getElementById('filter');
    const sort = document.getElementById('sort');
    document.getElementById('summary').textContent =
      `${{completed.length}} completed experiments`;

    function metric(row, name) {{
      if (name === 'computed_score') return row.computed_score || row.score || 0;
      return Number((row.metrics || {{}})[name] || 0);
    }}

    function strategyName(row) {{
      return row.strategy_plugin || (row.parameters || {{}}).strategy_plugin || row.strategy_name || 'UNKNOWN';
    }}

    function renderTable() {{
      const query = filter.value.toLowerCase();
      const sortKey = sort.value;
      const rows = topRows
        .filter(row => JSON.stringify(row).toLowerCase().includes(query))
        .sort((a, b) => metric(b, sortKey) - metric(a, sortKey));
      const table = document.getElementById('table');
      table.innerHTML = `
        <tr>
          <th>ID</th><th>Strategy</th><th>Status</th><th>Score</th><th>Profit Factor</th>
          <th>Expectancy</th><th>Profit</th><th>Sharpe</th><th>Drawdown</th>
          <th>Trades</th><th>Win Rate</th><th>Parameters</th>
        </tr>` + rows.map(row => `
        <tr>
          <td>${{row.id}}</td>
          <td>${{strategyName(row)}}</td>
          <td>${{row.status}}</td>
          <td>${{metric(row, 'computed_score').toFixed(4)}}</td>
          <td>${{metric(row, 'profit_factor').toFixed(4)}}</td>
          <td>${{metric(row, 'expectancy').toFixed(4)}}</td>
          <td>${{metric(row, 'profit_total_abs').toFixed(4)}}</td>
          <td>${{metric(row, 'sharpe').toFixed(4)}}</td>
          <td>${{metric(row, 'max_drawdown_abs').toFixed(4)}}</td>
          <td>${{metric(row, 'total_trades')}}</td>
          <td>${{metric(row, 'winrate').toFixed(4)}}</td>
          <td><code>${{JSON.stringify(row.parameters)}}</code></td>
        </tr>`).join('');
    }}

    function renderStrategyTable() {{
      const table = document.getElementById('strategyTable');
      table.innerHTML = `
        <tr>
          <th>Strategy</th><th>Best Experiment</th><th>Score</th><th>Profit Factor</th>
          <th>Drawdown</th><th>Win Rate</th><th>Expectancy</th><th>Sharpe</th>
          <th>Trades</th><th>Experiments</th><th>Best Parameters</th>
        </tr>` + strategyRows.map(row => `
        <tr>
          <td>${{row.strategy_plugin}}</td>
          <td>${{row.best_experiment_id}}</td>
          <td>${{Number(row.score || 0).toFixed(4)}}</td>
          <td>${{Number(row.profit_factor || 0).toFixed(4)}}</td>
          <td>${{Number(row.drawdown || 0).toFixed(4)}}</td>
          <td>${{Number(row.winrate || 0).toFixed(4)}}</td>
          <td>${{Number(row.expectancy || 0).toFixed(4)}}</td>
          <td>${{Number(row.sharpe || 0).toFixed(4)}}</td>
          <td>${{Number(row.total_trades || 0)}}</td>
          <td>${{Number(row.experiments || 0)}}</td>
          <td><code>${{JSON.stringify(row.best_parameters)}}</code></td>
        </tr>`).join('');
    }}

    function histogram(values, bins = 12) {{
      const clean = values.filter(v => Number.isFinite(v));
      if (!clean.length) return [];
      const min = Math.min(...clean), max = Math.max(...clean);
      const width = (max - min || 1) / bins;
      const counts = Array(bins).fill(0);
      clean.forEach(v => counts[Math.min(bins - 1, Math.floor((v - min) / width))]++);
      return counts.map((count, i) => ({{ label: (min + i * width).toFixed(2), count }}));
    }}

    function drawBars(id, values, title) {{
      const canvas = document.getElementById(id);
      const ctx = canvas.getContext('2d');
      canvas.width = canvas.clientWidth * devicePixelRatio;
      canvas.height = canvas.clientHeight * devicePixelRatio;
      ctx.scale(devicePixelRatio, devicePixelRatio);
      const w = canvas.clientWidth, h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);
      ctx.fillText(title, 12, 18);
      const data = histogram(values);
      const max = Math.max(1, ...data.map(d => d.count));
      const barW = (w - 24) / Math.max(1, data.length);
      data.forEach((d, i) => {{
        const bh = (h - 48) * d.count / max;
        ctx.fillRect(12 + i * barW, h - 24 - bh, barW - 2, bh);
      }});
    }}

    function drawLine(id, values, title) {{
      const canvas = document.getElementById(id);
      const ctx = canvas.getContext('2d');
      canvas.width = canvas.clientWidth * devicePixelRatio;
      canvas.height = canvas.clientHeight * devicePixelRatio;
      ctx.scale(devicePixelRatio, devicePixelRatio);
      const w = canvas.clientWidth, h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);
      ctx.fillText(title, 12, 18);
      if (values.length < 2) return;
      const min = Math.min(...values), max = Math.max(...values);
      ctx.beginPath();
      values.forEach((v, i) => {{
        const x = 12 + i * (w - 24) / (values.length - 1);
        const y = h - 24 - ((v - min) / (max - min || 1)) * (h - 48);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }});
      ctx.stroke();
    }}

    function renderCharts() {{
      drawBars('profitFactor', completed.map(r => metric(r, 'profit_factor')), 'Profit Factor distribution');
      drawBars('drawdown', completed.map(r => metric(r, 'max_drawdown_abs')), 'Drawdown distribution');
      drawBars('winrate', completed.map(r => metric(r, 'winrate')), 'Win Rate distribution');
      drawLine('scoreEvolution', completed.map(r => r.score || 0), 'Score evolution');
    }}

    function renderParameterComparison() {{
      const groups = new Map();
      completed.forEach(row => {{
        Object.entries(row.parameters || {{}}).forEach(([name, value]) => {{
          const key = `${{name}}=${{value}}`;
          if (!groups.has(key)) {{
            groups.set(key, {{ name, value, count: 0, score: 0, profitFactor: 0, drawdown: 0 }});
          }}
          const item = groups.get(key);
          item.count += 1;
          item.score += metric(row, 'computed_score');
          item.profitFactor += metric(row, 'profit_factor');
          item.drawdown += metric(row, 'max_drawdown_abs');
        }});
      }});

      const rows = Array.from(groups.values())
        .filter(item => item.count >= 2)
        .map(item => ({{
          ...item,
          avgScore: item.score / item.count,
          avgProfitFactor: item.profitFactor / item.count,
          avgDrawdown: item.drawdown / item.count,
        }}))
        .sort((a, b) => b.avgScore - a.avgScore)
        .slice(0, 50);

      document.getElementById('parameterTable').innerHTML = `
        <tr>
          <th>Parameter</th><th>Value</th><th>Experiments</th>
          <th>Average Score</th><th>Average Profit Factor</th><th>Average Drawdown</th>
        </tr>` + rows.map(row => `
        <tr>
          <td>${{row.name}}</td>
          <td>${{row.value}}</td>
          <td>${{row.count}}</td>
          <td>${{row.avgScore.toFixed(4)}}</td>
          <td>${{row.avgProfitFactor.toFixed(4)}}</td>
          <td>${{row.avgDrawdown.toFixed(4)}}</td>
        </tr>`).join('');
    }}

    filter.addEventListener('input', renderTable);
    sort.addEventListener('change', renderTable);
    renderTable();
    renderStrategyTable();
    renderCharts();
    renderParameterComparison();
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate experiment HTML dashboard.")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    output = HTMLDashboard().generate(args.output, limit=args.limit)
    print(output)


if __name__ == "__main__":
    main()
