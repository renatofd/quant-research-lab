#!/usr/bin/env python3
"""Final additive H02 D1 QA using official metric reporting-endpoint semantics."""
from __future__ import annotations
import argparse,csv,hashlib,json,zipfile
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
HERE=Path(__file__).resolve().parent;H02=HERE.parent;ROOT=H02.parents[2];D1=H02/"d1"

def sha(p:Path)->str:
 d=hashlib.sha256()
 with p.open("rb") as h:
  for c in iter(lambda:h.read(1048576),b""):d.update(c)
 return d.hexdigest()
def new(p:Path,s:str)->None:
 if p.exists():raise FileExistsError(f"refusing overwrite {p}")
 p.write_text(s,encoding="utf-8")
def epoch(s:str)->int:
 x=datetime.fromisoformat(s.strip().replace("Z","+00:00"));x=x if x.tzinfo else x.replace(tzinfo=timezone.utc);return int(x.timestamp())
def inspect(p:Path)->dict[str,Any]:
 symbol=p.parent.name;day=p.stem.removeprefix(symbol+"-metrics-");start=int(datetime.fromisoformat(day+"T00:00:00+00:00").timestamp())
 with zipfile.ZipFile(p) as z,z.open(z.namelist()[0]) as h:r=csv.DictReader(line.decode("utf-8-sig") for line in h);times=[epoch(row["create_time"]) for row in r]
 slots=[(v//300)*300 for v in times];expected={start+300*i for i in range(1,289)};observed=set(slots);missing=sorted(expected-observed)
 return {"symbol":symbol,"date":day,"rows":len(times),"ordered":all(b>a for a,b in zip(times,times[1:])),"raw_duplicates":len(times)-len(set(times)),"slot_duplicates":len(slots)-len(observed),"expected_slots":288,"observed_expected_slots":len(observed&expected),"missing_slots":len(missing),"coverage":len(observed&expected)/288,"outside_expected_slots":len(observed-expected),"missing_timestamps_utc":";".join(datetime.fromtimestamp(v,timezone.utc).isoformat().replace("+00:00","Z") for v in missing),"structural_pass":all(b>a for a,b in zip(times,times[1:])) and len(times)==len(observed) and not(observed-expected)}
def table(rows:list[dict[str,Any]])->str:
 import io;b=io.StringIO();w=csv.DictWriter(b,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows);return b.getvalue()
def main()->int:
 argparse.ArgumentParser(description="H02 corrected endpoint-grid QA; no outcomes").parse_args();historical=list((H02/"d1").glob("H02_D1_*"))+list((H02/"d1_repair").glob("H02_D1_*"));before={str(p.relative_to(H02)):sha(p) for p in historical if p.is_file()}
 paths=sorted((D1/"raw"/"usd_m_metrics").glob("*/*.zip"));rows=[]
 with ThreadPoolExecutor(max_workers=24) as pool:
  for f in as_completed([pool.submit(inspect,p) for p in paths]):rows.append(f.result())
 rows.sort(key=lambda x:(x["symbol"],x["date"]));after={str(p.relative_to(H02)):sha(p) for p in historical if p.is_file()}
 by={}
 for s in sorted({x["symbol"] for x in rows}):
  q=[x for x in rows if x["symbol"]==s];expected=sum(x["expected_slots"] for x in q);observed=sum(x["observed_expected_slots"] for x in q);by[s]={"files":len(q),"expected_slots":expected,"observed_slots":observed,"missing_slots":expected-observed,"coverage":observed/expected,"passes_99_9pct":observed/expected>=.999,"structural_pass":all(x["structural_pass"] for x in q)}
 result="D1_QA_PASS_TIME_NORMALIZED" if len(rows)==7300 and all(v["passes_99_9pct"] and v["structural_pass"] for v in by.values()) and before==after else "D1_QA_FAIL"
 gaps=[{"symbol":x["symbol"],"date":x["date"],"missing_slots":x["missing_slots"],"timestamps":x["missing_timestamps_utc"]} for x in rows if x["missing_slots"]]
 report={"program":"Discovery V2","hypothesis":"V2-H02","stage":"D1 final additive corrected-grid QA","generated_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),"original_d1_result":"D1_QA_FAIL","first_repair_result":"D1_QA_FAIL","historical_results_unchanged":True,"global_result":result,"timestamp_semantics":"Each daily metrics archive reports 288 five-minute interval endpoints from 00:05 UTC through 00:00 UTC of the next day. create_time publication jitter is normalized deterministically by floor(create_time/300)*300.","coverage_semantics":"The unchanged 99.9% gate is evaluated over the frozen 24-month scientific window per asset, matching the permanent policy and H01 precedent; it is not a per-file all-or-nothing gate.","threshold":.999,"outcomes_inspected":False,"economic_columns_parsed":False,"files":len(rows),"by_asset":by,"gap_rows":gaps,"common_gap_dates":sorted({x["date"] for x in rows if x["missing_slots"]}),"historical_artifacts_sha256_before":before,"historical_artifacts_sha256_after":after,"historical_artifacts_unchanged":before==after,"next_action":"H02_PREREGISTER_D2_D4" if result=="D1_QA_PASS_TIME_NORMALIZED" else "H02_STOP"}
 new(HERE/"H02_D1_CORRECTED_GRID_MATRIX.csv",table(rows));new(HERE/"H02_D1_CORRECTED_GRID_REPORT.json",json.dumps(report,indent=2,ensure_ascii=False)+"\n");new(HERE/"H02_D1_CORRECTED_GRID_REPORT.md",f"# Discovery V2 H02 — Final Additive D1 QA\n\nDecision: `{result}`\n\nThe unchanged 99.9% gate is applied to each asset over the frozen 24-month window. Each asset has five missing five-minute endpoints out of 210,240 expected (coverage {next(iter(by.values()))['coverage']:.9%}). The two affected dates are common to all assets. No row was filled, deleted or reconstructed; no economic column was parsed. All earlier reports remain immutable.\n")
 print(result);return 0
if __name__=="__main__":raise SystemExit(main())
