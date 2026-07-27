from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from .candidate_selector import CandidateSelector
    from .experiment_database import ExperimentDatabase
    from .parameter_space_analyzer import ParameterSpaceAnalyzer
except ImportError:
    from candidate_selector import CandidateSelector
    from experiment_database import ExperimentDatabase
    from parameter_space_analyzer import ParameterSpaceAnalyzer


class ComparisonReport:
    def __init__(
        self,
        database: ExperimentDatabase | None = None,
        selector: CandidateSelector | None = None,
        analyzer: ParameterSpaceAnalyzer | None = None,
    ) -> None:
        self.database = database or ExperimentDatabase()
        self.selector = selector or CandidateSelector(self.database)
        self.analyzer = analyzer or ParameterSpaceAnalyzer(self.database)

    def generate(
        self,
        output_path: Path | str | None = None,
        *,
        session_id: str | None = None,
        base_experiment_id: str | None = None,
        top_limit: int = 20,
    ) -> Path:
        output_path = Path(output_path or Path(__file__).resolve().parent / "comparison_report.html")
        experiments = (
            self.database.session_experiments(session_id)
            if session_id
            else self.database.list_experiments(status="completed")
        )
        completed = [item for item in experiments if item["status"] == "completed"]
        best = self.selector.select(limit=top_limit, session_id=session_id)
        base = self.database.get_experiment(base_experiment_id) if base_experiment_id else None
        analysis = self.analyzer.analyze(completed)

        payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "session_id": session_id,
            "base": base,
            "best": best,
            "experiments": completed,
            "analysis": analysis,
        }
        output_path.write_text(self._render(payload), encoding="utf-8")
        return output_path

    def _render(self, payload: dict[str, Any]) -> str:
        data = json.dumps(payload, ensure_ascii=False)
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AutoResearch Comparison Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
    h1, h2 {{ margin-bottom: 8px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 13px; }}
    th, td {{ border: 1px solid #d9e2ec; padding: 6px 8px; text-align: left; }}
    th {{ background: #f0f4f8; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(320px, 1fr)); gap: 18px; }}
    canvas {{ width: 100%; height: 220px; border: 1px solid #d9e2ec; }}
    code {{ white-space: pre-wrap; }}
  </style>
</head>
<body>
  <h1>AutoResearch Comparison Report</h1>
  <p id="summary"></p>
  <div class="grid">
    <canvas id="profitFactorEvolution"></canvas>
    <canvas id="drawdownEvolution"></canvas>
    <canvas id="profitFactorDistribution"></canvas>
    <canvas id="drawdownDistribution"></canvas>
  </div>
  <h2>Base Strategy</h2>
  <table id="baseTable"></table>
  <h2>Best Experiments</h2>
  <table id="bestTable"></table>
  <h2>Parameter Distribution</h2>
  <table id="parameterTable"></table>
  <h2>Search Convergence</h2>
  <table id="convergenceTable"></table>
  <script>
    const payload = {data};
    const experiments = payload.experiments || [];
    const best = payload.best || [];
    const base = payload.base;
    document.getElementById('summary').textContent =
      `${{experiments.length}} completed experiments analyzed.`;

    function metric(row, name) {{
      return Number((row.metrics || {{}})[name] || 0);
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
      values.forEach((value, index) => {{
        const x = 12 + index * (w - 24) / (values.length - 1);
        const y = h - 24 - ((value - min) / (max - min || 1)) * (h - 48);
        if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }});
      ctx.stroke();
    }}

    function drawBars(id, values, title) {{
      const clean = values.filter(Number.isFinite);
      const canvas = document.getElementById(id);
      const ctx = canvas.getContext('2d');
      canvas.width = canvas.clientWidth * devicePixelRatio;
      canvas.height = canvas.clientHeight * devicePixelRatio;
      ctx.scale(devicePixelRatio, devicePixelRatio);
      const w = canvas.clientWidth, h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);
      ctx.fillText(title, 12, 18);
      if (!clean.length) return;
      const min = Math.min(...clean), max = Math.max(...clean);
      const bins = 12, width = (max - min || 1) / bins;
      const counts = Array(bins).fill(0);
      clean.forEach(value => counts[Math.min(bins - 1, Math.floor((value - min) / width))]++);
      const highest = Math.max(...counts, 1);
      counts.forEach((count, index) => {{
        const barW = (w - 24) / bins;
        const barH = (h - 48) * count / highest;
        ctx.fillRect(12 + index * barW, h - 24 - barH, barW - 2, barH);
      }});
    }}

    function renderBase() {{
      document.getElementById('baseTable').innerHTML = base ? `
        <tr><th>ID</th><th>Profit Factor</th><th>Drawdown</th><th>Profit</th><th>Parameters</th></tr>
        <tr>
          <td>${{base.id}}</td>
          <td>${{metric(base, 'profit_factor').toFixed(4)}}</td>
          <td>${{metric(base, 'max_drawdown_abs').toFixed(4)}}</td>
          <td>${{metric(base, 'profit_total_abs').toFixed(4)}}</td>
          <td><code>${{JSON.stringify(base.parameters)}}</code></td>
        </tr>` : '<tr><td>No base experiment selected.</td></tr>';
    }}

    function renderBest() {{
      document.getElementById('bestTable').innerHTML = `
        <tr><th>ID</th><th>Score</th><th>Profit Factor</th><th>Expectancy</th><th>Drawdown</th><th>Sharpe</th><th>Parameters</th></tr>` +
        best.map(row => `
        <tr>
          <td>${{row.id}}</td>
          <td>${{Number(row.computed_score || row.score || 0).toFixed(4)}}</td>
          <td>${{metric(row, 'profit_factor').toFixed(4)}}</td>
          <td>${{metric(row, 'expectancy').toFixed(4)}}</td>
          <td>${{metric(row, 'max_drawdown_abs').toFixed(4)}}</td>
          <td>${{metric(row, 'sharpe').toFixed(4)}}</td>
          <td><code>${{JSON.stringify(row.parameters)}}</code></td>
        </tr>`).join('');
    }}

    function renderParameters() {{
      const counts = new Map();
      experiments.forEach(row => {{
        Object.entries(row.parameters || {{}}).forEach(([name, value]) => {{
          const key = `${{name}}=${{value}}`;
          counts.set(key, (counts.get(key) || 0) + 1);
        }});
      }});
      const rows = Array.from(counts.entries())
        .map(([key, count]) => [key.split('=')[0], key.split('=').slice(1).join('='), count])
        .sort((a, b) => b[2] - a[2])
        .slice(0, 50);
      document.getElementById('parameterTable').innerHTML =
        '<tr><th>Parameter</th><th>Value</th><th>Count</th></tr>' +
        rows.map(row => `<tr><td>${{row[0]}}</td><td>${{row[1]}}</td><td>${{row[2]}}</td></tr>`).join('');
    }}

    function renderConvergence() {{
      let bestProfitFactor = -Infinity;
      let bestDrawdown = Infinity;
      const rows = experiments.map((row, index) => {{
        bestProfitFactor = Math.max(bestProfitFactor, metric(row, 'profit_factor'));
        bestDrawdown = Math.min(bestDrawdown, metric(row, 'max_drawdown_abs'));
        return `<tr><td>${{index + 1}}</td><td>${{bestProfitFactor.toFixed(4)}}</td><td>${{bestDrawdown.toFixed(4)}}</td></tr>`;
      }});
      document.getElementById('convergenceTable').innerHTML =
        '<tr><th>Experiment</th><th>Best Profit Factor So Far</th><th>Best Drawdown So Far</th></tr>' +
        rows.join('');
    }}

    drawLine('profitFactorEvolution', experiments.map(row => metric(row, 'profit_factor')), 'Profit Factor evolution');
    drawLine('drawdownEvolution', experiments.map(row => metric(row, 'max_drawdown_abs')), 'Drawdown evolution');
    drawBars('profitFactorDistribution', experiments.map(row => metric(row, 'profit_factor')), 'Profit Factor distribution');
    drawBars('drawdownDistribution', experiments.map(row => metric(row, 'max_drawdown_abs')), 'Drawdown distribution');
    renderBase();
    renderBest();
    renderParameters();
    renderConvergence();
  </script>
</body>
</html>
"""
