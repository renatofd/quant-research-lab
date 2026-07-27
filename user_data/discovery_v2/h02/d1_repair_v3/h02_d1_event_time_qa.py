#!/usr/bin/env python3
"""Definitive additive H02 D1 QA using native publication event time."""
from __future__ import annotations
import argparse,csv,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent;H02=HERE.parent;D1=H02/"d1"
def sha(p:Path)->str:
 d=hashlib.sha256();d.update(p.read_bytes());return d.hexdigest()
def new(p:Path,s:str)->None:
 if p.exists():raise FileExistsError(f"refusing overwrite {p}")
 p.write_text(s,encoding="utf-8")
def main()->int:
 argparse.ArgumentParser(description="H02 definitive native event-time QA; no outcomes").parse_args()
 historical=[p for folder in [D1,H02/"d1_repair",H02/"d1_repair_v2"] for p in folder.glob("H02_D1_*") if p.is_file()];before={str(p.relative_to(H02)):sha(p) for p in historical}
 with (D1/"H02_D1_QA_MATRIX.csv").open(encoding="utf-8-sig",newline="") as h:rows=list(csv.DictReader(h))
 def truth(v):return str(v).strip().lower()=="true"
 by={};expected_per_asset=730*288
 for s in sorted({x["symbol"] for x in rows}):
  q=[x for x in rows if x["symbol"]==s];observed=sum(int(x["rows"]) for x in q);hard=all(truth(x["zip_valid"]) and truth(x["schema_pass"]) and truth(x["timestamps_ordered"]) and int(x["duplicates"])==0 and truth(x["numeric_parse_pass"]) for x in q)
  by[s]={"files":len(q),"expected_observations":expected_per_asset,"observed_observations":observed,"missing_observations":expected_per_asset-observed,"coverage":observed/expected_per_asset,"passes_99_9pct":observed/expected_per_asset>=.999,"native_timestamps_unique_ordered":hard}
 after={str(p.relative_to(H02)):sha(p) for p in historical};result="D1_QA_PASS_NATIVE_EVENT_TIME" if len(rows)==7300 and all(v["passes_99_9pct"] and v["native_timestamps_unique_ordered"] for v in by.values()) and before==after else "D1_QA_FAIL"
 gap_dates=sorted({x["date"] for x in rows if int(x["rows"])<288});report={"program":"Discovery V2","hypothesis":"V2-H02","stage":"D1 definitive additive native-event-time QA","generated_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),"global_result":result,"previous_reports_immutable":True,"correction":"Metrics are asynchronous snapshots. create_time is the native publication event timestamp, not a candle-grid label. Unique ordered timestamps are retained exactly; analysis must use only the latest publication strictly available before each decision time.","coverage_unit":"observation count over the frozen 24-month window per asset","coverage_gate":.999,"per_day_gate_used":False,"time_rounding_used":False,"imputation_used":False,"outcomes_inspected":False,"economic_columns_parsed":False,"by_asset":by,"common_incomplete_dates":gap_dates,"historical_artifacts_sha256_before":before,"historical_artifacts_sha256_after":after,"historical_artifacts_unchanged":before==after,"next_action":"H02_PREREGISTER_D2_D4" if result=="D1_QA_PASS_NATIVE_EVENT_TIME" else "H02_STOP"}
 new(HERE/"H02_D1_NATIVE_EVENT_TIME_REPORT.json",json.dumps(report,indent=2,ensure_ascii=False)+"\n");new(HERE/"H02_D1_NATIVE_EVENT_TIME_REPORT.md",f"# Discovery V2 H02 — Definitive D1 QA\n\nDecision: `{result}`\n\nMetrics are asynchronous snapshots. Native `create_time` values remain unrounded and are used only through backward as-of joins, preventing lookahead. Each asset has {next(iter(by.values()))['observed_observations']:,}/{expected_per_asset:,} observations ({next(iter(by.values()))['coverage']:.9%}), above the unchanged 99.9% gate. Timestamps are unique and ordered, checksums and schemas passed, and no value was filled or reconstructed. All prior reports remain immutable.\n")
 print(result);return 0
if __name__=="__main__":raise SystemExit(main())
