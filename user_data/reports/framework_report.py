import atexit
from datetime import UTC, datetime
import html
import json
from pathlib import Path
from typing import Any

from pandas import DataFrame, concat

from evaluation.comparison_engine import compare_shadow_decisions


REPORT_COLUMNS = [
    "date",
    "close",
    "market_regime",
    "signal_score",
    "decision_confidence",
    "passive_decision",
    "shadow_real_decision",
    "shadow_engine_decision",
    "shadow_confidence",
    "shadow_regime",
    "shadow_signal_score",
]

_REPORT_FRAMES: dict[str, DataFrame] = {}
_REPORT_CONFIG: dict[str, Any] = {}
_REGISTERED = False


def _is_backtest(config: dict) -> bool:
    runmode = config.get("runmode")
    return getattr(runmode, "value", runmode) == "backtest"


def _reports_dir(config: dict) -> Path:
    user_data_dir = Path(config.get("user_data_dir", Path.cwd() / "user_data"))
    return user_data_dir / "reports"


def _safe_number(value: Any) -> Any:
    try:
        if value != value:
            return None
    except TypeError:
        return value

    return value


def _distribution(series) -> dict:
    cleaned = series.dropna()
    if cleaned.empty:
        return {
            "count": 0,
            "mean": None,
            "std": None,
            "min": None,
            "q25": None,
            "median": None,
            "q75": None,
            "max": None,
        }

    return {
        "count": int(cleaned.count()),
        "mean": _safe_number(float(cleaned.mean())),
        "std": _safe_number(float(cleaned.std())),
        "min": _safe_number(float(cleaned.min())),
        "q25": _safe_number(float(cleaned.quantile(0.25))),
        "median": _safe_number(float(cleaned.median())),
        "q75": _safe_number(float(cleaned.quantile(0.75))),
        "max": _safe_number(float(cleaned.max())),
    }


def _histogram(series, bins: int = 10) -> list[dict]:
    cleaned = series.dropna()
    if cleaned.empty:
        return []

    counts = cleaned.value_counts(bins=bins, sort=False)
    return [
        {
            "range": str(interval),
            "count": int(count),
        }
        for interval, count in counts.items()
    ]


def _market_regime_metrics(dataframe: DataFrame) -> dict:
    counts = dataframe["market_regime"].fillna("UNKNOWN").value_counts()
    total = int(counts.sum())

    return {
        "total_candles": total,
        "counts": {str(regime): int(count) for regime, count in counts.items()},
        "percentages": {
            str(regime): float(count / total) if total else 0.0
            for regime, count in counts.items()
        },
    }


def _shadow_metrics(dataframe: DataFrame) -> dict:
    total = compare_shadow_decisions(dataframe)
    by_pair = {
        pair: compare_shadow_decisions(pair_dataframe)
        for pair, pair_dataframe in dataframe.groupby("pair")
    }

    return {
        "total": total,
        "by_pair": by_pair,
    }


def _build_report(dataframe: DataFrame, config: dict) -> dict:
    generated_at = datetime.now(UTC).isoformat()
    shadow_metrics = _shadow_metrics(dataframe)

    return {
        "generated_at": generated_at,
        "strategy": config.get("strategy", "unknown"),
        "timeframe": config.get("timeframe", "unknown"),
        "pairs": sorted(dataframe["pair"].unique().tolist()),
        "candle_count": int(len(dataframe)),
        "market_regime": _market_regime_metrics(dataframe),
        "signal_score": {
            "distribution": _distribution(dataframe["signal_score"]),
            "histogram": _histogram(dataframe["signal_score"]),
        },
        "decision_confidence": {
            "distribution": _distribution(dataframe["decision_confidence"]),
            "histogram": _histogram(dataframe["decision_confidence"]),
        },
        "shadow_evaluation": shadow_metrics,
        "summary": {
            "dominant_regime": str(dataframe["market_regime"].mode().iloc[0])
            if not dataframe["market_regime"].mode().empty
            else "UNKNOWN",
            "average_signal_score": _safe_number(float(dataframe["signal_score"].mean())),
            "average_decision_confidence": _safe_number(
                float(dataframe["decision_confidence"].mean())
            ),
            "decision_engine_accuracy": shadow_metrics["total"]["decision_engine_accuracy"],
        },
    }


def _render_html(report: dict) -> str:
    pretty_json = html.escape(json.dumps(report, indent=2, ensure_ascii=False))
    regime_rows = "\n".join(
        f"<tr><td>{html.escape(regime)}</td><td>{count}</td>"
        f"<td>{report['market_regime']['percentages'][regime]:.2%}</td></tr>"
        for regime, count in report["market_regime"]["counts"].items()
    )
    shadow = report["shadow_evaluation"]["total"]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Framework Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2933; }}
    table {{ border-collapse: collapse; margin: 16px 0; min-width: 420px; }}
    th, td {{ border: 1px solid #d9e2ec; padding: 8px 10px; text-align: left; }}
    th {{ background: #f0f4f8; }}
    pre {{ background: #f7f9fb; padding: 16px; overflow: auto; }}
  </style>
</head>
<body>
  <h1>Framework Report</h1>
  <p><strong>Generated:</strong> {html.escape(report["generated_at"])}</p>
  <p><strong>Strategy:</strong> {html.escape(str(report["strategy"]))}</p>
  <p><strong>Candles:</strong> {report["candle_count"]}</p>

  <h2>Market Regime</h2>
  <table>
    <tr><th>Regime</th><th>Count</th><th>Share</th></tr>
    {regime_rows}
  </table>

  <h2>Signal Score</h2>
  <pre>{html.escape(json.dumps(report["signal_score"]["distribution"], indent=2))}</pre>

  <h2>Decision Confidence</h2>
  <pre>{html.escape(json.dumps(report["decision_confidence"]["distribution"], indent=2))}</pre>

  <h2>Shadow Evaluation</h2>
  <table>
    <tr><th>Metric</th><th>Value</th></tr>
    <tr><td>Decision Engine Accuracy</td><td>{shadow["decision_engine_accuracy"]:.4f}</td></tr>
    <tr><td>Avoided Losing Trades</td><td>{shadow["avoided_losing_trades"]}</td></tr>
    <tr><td>Missed Profitable Trades</td><td>{shadow["missed_profitable_trades"]}</td></tr>
    <tr><td>Real Simulated Return</td><td>{shadow["real_simulated_return"]:.6f}</td></tr>
    <tr><td>Engine Simulated Return</td><td>{shadow["engine_simulated_return"]:.6f}</td></tr>
    <tr><td>Return Difference</td><td>{shadow["return_difference"]:.6f}</td></tr>
  </table>

  <h2>Full JSON</h2>
  <pre>{pretty_json}</pre>
</body>
</html>
"""


def record_framework_report_data(dataframe: DataFrame, metadata: dict, config: dict) -> DataFrame:
    global _REGISTERED

    if not _is_backtest(config):
        return dataframe

    pair = metadata.get("pair", "UNKNOWN")
    available_columns = [column for column in REPORT_COLUMNS if column in dataframe]

    _REPORT_FRAMES[pair] = dataframe[available_columns].copy()
    _REPORT_CONFIG.update(config)

    if not _REGISTERED:
        atexit.register(flush_framework_report)
        _REGISTERED = True

    return dataframe


def flush_framework_report() -> None:
    if not _REPORT_FRAMES:
        return

    frames = []
    for pair, dataframe in _REPORT_FRAMES.items():
        pair_dataframe = dataframe.copy()
        pair_dataframe["pair"] = pair
        frames.append(pair_dataframe)

    combined = concat(frames, ignore_index=True)
    report = _build_report(combined, _REPORT_CONFIG)

    reports_dir = _reports_dir(_REPORT_CONFIG)
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    json_path = reports_dir / f"framework_report_{timestamp}.json"
    html_path = reports_dir / f"framework_report_{timestamp}.html"
    latest_json_path = reports_dir / "framework_report_latest.json"
    latest_html_path = reports_dir / "framework_report_latest.html"

    json_text = json.dumps(report, indent=2, ensure_ascii=False)
    html_text = _render_html(report)

    json_path.write_text(json_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    latest_json_path.write_text(json_text, encoding="utf-8")
    latest_html_path.write_text(html_text, encoding="utf-8")
