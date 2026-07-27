#!/usr/bin/env python3
"""V2-H02 D1 official metrics acquisition and structural QA only."""
from __future__ import annotations
import argparse,csv,hashlib,json,re,shutil,urllib.request,zipfile
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath
from typing import Any

HERE=Path(__file__).resolve().parent; H02=HERE.parent; ROOT=H02.parents[2]
D0=H02/"d0"/"H02_D0_MANIFEST.csv"; RAW=HERE/"raw"/"usd_m_metrics"; BASE="https://data.binance.vision/"
UA="DiscoveryV2-H02-D1-AcquireQA/1.0"
HEADER=["create_time","symbol","sum_open_interest","sum_open_interest_value","count_toptrader_long_short_ratio","sum_toptrader_long_short_ratio","count_long_short_ratio","sum_taker_long_short_vol_ratio"]

def sha(path:Path)->str:
 d=hashlib.sha256()
 with path.open("rb") as h:
  for c in iter(lambda:h.read(1048576),b""): d.update(c)
 return d.hexdigest()

def new(path:Path,text:str)->None:
 if path.exists(): raise FileExistsError(f"refusing to overwrite {path}")
 path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text,encoding="utf-8")

def get(url:str,dest:Path)->None:
 dest.parent.mkdir(parents=True,exist_ok=True); tmp=dest.with_suffix(dest.suffix+".part")
 with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":UA}),timeout=90) as r,tmp.open("wb") as h: shutil.copyfileobj(r,h)
 tmp.replace(dest)

def wanted(path:Path)->str:
 m=re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?.+",path.read_text(encoding="ascii").strip())
 if not m: raise ValueError(f"invalid checksum {path}")
 return m.group(1).lower()

def acquire(row:dict[str,str])->dict[str,Any]:
 s,day=row["symbol"],row["date"]; z=RAW/s/f"{s}-metrics-{day}.zip"; c=z.with_suffix(".zip.CHECKSUM")
 zu=BASE+row["archive_key"]; cu=BASE+row["checksum_key"]; reused=z.exists() and c.exists()
 if not c.exists(): get(cu,c)
 expected=wanted(c)
 if not z.exists() or sha(z)!=expected: get(zu,z)
 actual=sha(z)
 return {"symbol":s,"date":day,"archive":str(z.relative_to(ROOT)).replace("\\","/"),"checksum":str(c.relative_to(ROOT)).replace("\\","/"),"bytes":z.stat().st_size,"expected_sha256":expected,"actual_sha256":actual,"checksum_match":expected==actual,"reused_valid":reused and expected==actual,"archive_url":zu,"checksum_url":cu}

def epoch(raw:str)->int:
 t=raw.strip()
 if t.isdigit():
  v=int(t)
  return v//1000000 if v>=100000000000000 else v//1000 if v>=100000000000 else v
 parsed=datetime.fromisoformat(t.replace("Z","+00:00"))
 if parsed.tzinfo is None: parsed=parsed.replace(tzinfo=timezone.utc)
 return int(parsed.timestamp())

def inspect(item:dict[str,Any])->dict[str,Any]:
 p=ROOT/item["archive"]; out={"symbol":item["symbol"],"date":item["date"],"zip_valid":False,"schema_pass":False,"rows":0,"timestamps_ordered":False,"duplicates":None,"coverage":0.0,"numeric_parse_pass":False,"qa_pass":False,"notes":None}
 try:
  with zipfile.ZipFile(p) as z:
   members=[m for m in z.infolist() if m.filename.lower().endswith(".csv") and not m.is_dir()]
   if len(members)!=1 or PurePosixPath(members[0].filename).is_absolute() or ".." in PurePosixPath(members[0].filename).parts: out["notes"]="unsafe or ambiguous ZIP members"; return out
   with z.open(members[0]) as h:
    r=csv.reader(line.decode("utf-8-sig") for line in h); header=[re.sub(r"[^a-z0-9]+","_",v.strip().lower()).strip("_") for v in next(r)]
    out["schema_pass"]=header==HEADER
    if not out["schema_pass"]: out["notes"]="unexpected schema:"+",".join(header); return out
    times=[]; numeric=True
    for row in r:
     if len(row)!=len(header): numeric=False; continue
     try:
      times.append(epoch(row[0])); [float(v) for v in row[2:]]
     except ValueError: numeric=False
    out.update(zip_valid=True,rows=len(times),timestamps_ordered=all(times[i]>times[i-1] for i in range(1,len(times))),duplicates=len(times)-len(set(times)),numeric_parse_pass=numeric)
    start=int(datetime.fromisoformat(item["date"]+"T00:00:00+00:00").timestamp()); expected={start+300*i for i in range(288)}; observed=set(times)
    out["coverage"]=len(expected&observed)/288; inside=all(start<=v<start+86400 for v in times)
    out["qa_pass"]=all([out["zip_valid"],out["schema_pass"],out["timestamps_ordered"],out["duplicates"]==0,out["numeric_parse_pass"],inside,out["coverage"]>=0.999]); return out
 except (OSError,zipfile.BadZipFile,UnicodeError,csv.Error) as e: out["notes"]=f"{type(e).__name__}: {e}"; return out

def table(rows:list[dict[str,Any]])->str:
 import io
 b=io.StringIO(); w=csv.DictWriter(b,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows); return b.getvalue()

def main()->int:
 p=argparse.ArgumentParser(description="V2-H02 D1 acquisition and structural QA; no outcomes"); p.add_argument("run",nargs="?",default="run"); p.add_argument("--workers",type=int,default=16); a=p.parse_args()
 for name in ("H02_D1_REPORT.json","H02_D1_QA_MATRIX.csv","H02_D1_INVENTORY.csv","H02_D1_HOLDOUT.json"):
  if (HERE/name).exists(): raise FileExistsError(f"D1 already produced {name}")
 hold={"program":"Discovery V2","hypothesis":"V2-H02","state":"SEALED","development":["2024-07-01T00:00:00Z","2025-12-31T23:59:59.999Z"],"historical_holdout":["2026-01-01T00:00:00Z","2026-06-30T23:59:59.999Z"],"outcome_calculation_permitted":False,"created_before_any_metrics_zip_open":True}
 new(HERE/"H02_D1_HOLDOUT.json",json.dumps(hold,indent=2)+"\n")
 with D0.open(encoding="utf-8-sig",newline="") as h: manifest=list(csv.DictReader(h))
 inventory=[]
 with ThreadPoolExecutor(max_workers=a.workers) as pool:
  for f in as_completed([pool.submit(acquire,row) for row in manifest]): inventory.append(f.result())
 inventory.sort(key=lambda x:(x["symbol"],x["date"]))
 if not all(x["checksum_match"] for x in inventory): raise RuntimeError("checksum failure")
 qa=[]
 with ThreadPoolExecutor(max_workers=a.workers) as pool:
  for f in as_completed([pool.submit(inspect,row) for row in inventory]): qa.append(f.result())
 qa.sort(key=lambda x:(x["symbol"],x["date"])); by={}
 for s in sorted({x["symbol"] for x in qa}):
  q=[x for x in qa if x["symbol"]==s]; by[s]={"files":len(q),"qa_pass":sum(x["qa_pass"] for x in q),"minimum_coverage":min(x["coverage"] for x in q),"complete":all(x["qa_pass"] for x in q)}
 complete=[s for s,v in by.items() if v["complete"]]; result="D1_QA_PASS" if len(complete)>=8 and len(inventory)==7300 and all(x["checksum_match"] for x in inventory) else "D1_QA_FAIL"
 report={"program":"Discovery V2","hypothesis":"V2-H02","stage":"D1 acquisition and structural QA","generated_utc":datetime.now().astimezone().isoformat(),"mechanical_result":result,"outcomes_inspected":False,"economic_analysis_executed":False,"inventory_rows":len(inventory),"checksum_matches":sum(x["checksum_match"] for x in inventory),"bytes":sum(x["bytes"] for x in inventory),"qa_rows":len(qa),"qa_pass":sum(x["qa_pass"] for x in qa),"complete_assets":complete,"by_asset":by,"criteria":{"objects_7300":len(inventory)==7300,"checksums_100pct":all(x["checksum_match"] for x in inventory),"at_least_8_complete_assets":len(complete)>=8,"holdout_sealed":True,"no_outcome_inspection":True},"next_action":"H02_PREREGISTER_D2_D4" if result=="D1_QA_PASS" else "H02_STOP_OR_DATA_LIMITATION_REVIEW"}
 new(HERE/"H02_D1_INVENTORY.csv",table(inventory)); new(HERE/"H02_D1_QA_MATRIX.csv",table(qa)); new(HERE/"H02_D1_REPORT.json",json.dumps(report,indent=2,ensure_ascii=False)+"\n")
 new(HERE/"H02_D1_REPORT.md",f"# Discovery V2 H02 — D1\n\nDecision: `{result}`\n\n- files: {len(inventory)}\n- checksum matches: {sum(x['checksum_match'] for x in inventory)}\n- QA pass: {sum(x['qa_pass'] for x in qa)}/{len(qa)}\n- complete assets: {len(complete)}/10\n- outcomes inspected: no\n- holdout: sealed\n")
 print(result); return 0
if __name__=="__main__": raise SystemExit(main())
