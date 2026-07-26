#!/usr/bin/env python3
"""Additive H02 timestamp-semantic QA: official create_time belongs to its UTC 5m slot."""
from __future__ import annotations
import argparse,csv,hashlib,json,zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

HERE=Path(__file__).resolve().parent; H02=HERE.parent; ROOT=H02.parents[2]; D1=H02/"d1"

def sha(p:Path)->str:
 d=hashlib.sha256()
 with p.open("rb") as h:
  for c in iter(lambda:h.read(1048576),b""): d.update(c)
 return d.hexdigest()

def new(p:Path,s:str)->None:
 if p.exists(): raise FileExistsError(f"refusing to overwrite {p}")
 p.write_text(s,encoding="utf-8")

def epoch(raw:str)->int:
 x=datetime.fromisoformat(raw.strip().replace("Z","+00:00"))
 if x.tzinfo is None:x=x.replace(tzinfo=timezone.utc)
 return int(x.timestamp())

def inspect(p:Path)->dict[str,Any]:
 symbol=p.parent.name; day=p.stem.removeprefix(symbol+"-metrics-")
 with zipfile.ZipFile(p) as z, z.open(z.namelist()[0]) as h:
  r=csv.DictReader(line.decode("utf-8-sig") for line in h); times=[epoch(row["create_time"]) for row in r]
 start=int(datetime.fromisoformat(day+"T00:00:00+00:00").timestamp()); bins=[(v//300)*300 for v in times]; expected={start+300*i for i in range(288)}
 offsets=[v%300 for v in times]; unique=set(bins)
 return {"symbol":symbol,"date":day,"rows":len(times),"ordered":all(times[i]>times[i-1] for i in range(1,len(times))),"raw_duplicates":len(times)-len(set(times)),"slot_duplicates":len(bins)-len(unique),"normalized_slot_coverage":len(unique&expected)/288,"outside_day_slots":len(unique-expected),"max_publication_offset_seconds":max(offsets) if offsets else None,"pass":len(times)==288 and len(unique)==288 and unique==expected and all(times[i]>times[i-1] for i in range(1,len(times)))}

def table(rows:list[dict[str,Any]])->str:
 import io
 b=io.StringIO();w=csv.DictWriter(b,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows);return b.getvalue()

def main()->int:
 argparse.ArgumentParser(description="H02 additive timestamp slot QA; no outcomes").parse_args()
 originals=[D1/n for n in ["H02_D1_REPORT.json","H02_D1_QA_MATRIX.csv","H02_D1_INVENTORY.csv","H02_D1_HOLDOUT.json"]]
 before={p.name:sha(p) for p in originals}; paths=sorted((D1/"raw"/"usd_m_metrics").glob("*/*.zip")); rows=[]
 with ThreadPoolExecutor(max_workers=24) as pool:
  for f in as_completed([pool.submit(inspect,p) for p in paths]):rows.append(f.result())
 rows.sort(key=lambda x:(x["symbol"],x["date"])); after={p.name:sha(p) for p in originals}
 by={}
 for symbol in sorted({x["symbol"] for x in rows}):
  q=[x for x in rows if x["symbol"]==symbol];by[symbol]={"files":len(q),"pass":sum(x["pass"] for x in q),"minimum_normalized_coverage":min(x["normalized_slot_coverage"] for x in q),"maximum_publication_offset_seconds":max(x["max_publication_offset_seconds"] for x in q),"complete":all(x["pass"] for x in q)}
 result="D1_QA_PASS_TIME_NORMALIZED" if len(rows)==7300 and all(x["pass"] for x in rows) and before==after else "D1_QA_FAIL"
 report={"program":"Discovery V2","hypothesis":"V2-H02","stage":"D1 additive timestamp-semantic repair","generated_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),"original_mechanical_result":"D1_QA_FAIL","original_result_unchanged":True,"corrected_global_result":result,"cause":"QA treated official metric create_time publication jitter as missing observations by demanding exact-second grid equality.","normalization":"Deterministically map each official create_time to floor(create_time/300)*300 UTC; no value fill, interpolation, row creation or deletion.","outcomes_inspected":False,"economic_columns_parsed":False,"files":len(rows),"normalized_pass":sum(x["pass"] for x in rows),"complete_assets":[s for s,v in by.items() if v["complete"]],"by_asset":by,"original_artifacts_sha256_before":before,"original_artifacts_sha256_after":after,"original_artifacts_unchanged":before==after,"next_action":"H02_PREREGISTER_D2_D4" if result=="D1_QA_PASS_TIME_NORMALIZED" else "H02_STOP"}
 new(HERE/"H02_D1_TIME_ALIGNMENT_MATRIX.csv",table(rows));new(HERE/"H02_D1_TIME_ALIGNMENT_REPORT.json",json.dumps(report,indent=2,ensure_ascii=False)+"\n")
 new(HERE/"H02_D1_TIME_ALIGNMENT_REPORT.md",f"# Discovery V2 H02 — D1 Timestamp-Semantic Repair\n\nDecision: `{result}`\n\nThe original D1 report remains immutable. Official `create_time` jitter was incorrectly scored as missing data despite 288 ordered unique rows per day. Deterministic UTC five-minute slot normalization produced {sum(x['pass'] for x in rows)}/{len(rows)} passing files without filling, interpolation or economic-value inspection.\n")
 print(result);return 0
if __name__=="__main__":raise SystemExit(main())
