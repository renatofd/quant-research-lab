#!/usr/bin/env python3
"""Frozen V2-H02 crowding research instrument. Never places orders."""
from __future__ import annotations
import argparse,bisect,csv,hashlib,json,math,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];H01=HERE.parent/"h01";sys.path.insert(0,str(H01))
from h01_carry_research import read_funding,read_kline_family,months_between,ts,iso
PROTOCOL=HERE/"H02_D2_D4_PREREGISTRATION.json";D1=HERE/"d1_repair_v4"/"H02_D1_REQUIRED_FIELDS_REPORT.json";SEAL=HERE/"H02_EXPERIMENT_SEAL.json";OPEN=HERE/"H02_HOLDOUT_OPENING.json";RESULTS=HERE/"results";WEEK=604800
def sha(p:Path)->str:d=hashlib.sha256();d.update(p.read_bytes());return d.hexdigest()
def load(p:Path):return json.loads(p.read_text(encoding="utf-8-sig"))
def new(p:Path,s:str):
 if p.exists():raise FileExistsError(f"refusing overwrite {p}")
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding="utf-8")
def metric_time(s:str)->int:
 x=datetime.fromisoformat(s.replace("Z","+00:00"));x=x if x.tzinfo else x.replace(tzinfo=timezone.utc);return int(x.timestamp())
def metrics(symbol:str,months:set[str]):
 out=[]
 for p in sorted((HERE/"d1"/"raw"/"usd_m_metrics"/symbol).glob("*.zip")):
  if p.stem[-10:-3] not in months:continue
  with zipfile.ZipFile(p) as z,z.open(z.namelist()[0]) as h:
   for r in csv.DictReader(line.decode("utf-8-sig") for line in h):out.append((metric_time(r["create_time"]),float(r["sum_open_interest_value"]),float(r["sum_taker_long_short_vol_ratio"])))
 return sorted(out)
def pct_rank(values:list[float],x:float)->float:
 return (sum(v<x for v in values)+.5*sum(v==x for v in values))/len(values)
def build_records(protocol:dict[str,Any],month_start:str,month_end:str):
 months=months_between(month_start,month_end);by={}
 for symbol in protocol["universe"]:
  ms=metrics(symbol,months);mt=[x[0] for x in ms];fund=read_funding(symbol,months);perp=read_kline_family(symbol,"usd_m_perp_klines_5m",months);records=[]
  for i,(t,rate) in enumerate(fund[:-1]):
   next_t,next_rate=fund[i+1];entry=t+300;exit_t=next_t+300
   if entry not in perp or exit_t not in perp:continue
   a=bisect.bisect_left(mt,t)-1;b=bisect.bisect_left(mt,t-86400)-1
   if a<0 or b<0 or ms[a][1]<=0 or ms[b][1]<=0:continue
   growth=math.log(ms[a][1]/ms[b][1]);flow=ms[a][2];short=(perp[entry][0]-perp[exit_t][0])/perp[entry][0]+next_rate-.002
   records.append({"asset":symbol,"time":t,"funding":rate,"oi_growth":growth,"flow":flow,"short_net":short})
  by[symbol]=records
 grouped={}
 for rows in by.values():
  for r in rows:grouped.setdefault(r["time"],[]).append(r)
 valid=[]
 for t,rows in grouped.items():
  if len(rows)<8:continue
  fs=[r["funding"] for r in rows];ois=[r["oi_growth"] for r in rows]
  for r in rows:r["fund_rank"]=pct_rank(fs,r["funding"]);r["oi_rank"]=pct_rank(ois,r["oi_growth"]);valid.append(r)
 return valid
def boot(values:list[dict[str,Any]],field="short_net",seed=4202,n=10000):
 if not values:return {"n":0,"mean":None,"ci95":[None,None],"p":None}
 weeks=sorted({x["time"]//WEEK for x in values});s=np.array([sum(x[field] for x in values if x["time"]//WEEK==w) for w in weeks]);c=np.array([sum(1 for x in values if x["time"]//WEEK==w) for w in weeks]);rng=np.random.default_rng(seed);d=rng.integers(0,len(weeks),(n,len(weeks)));m=s[d].sum(1)/c[d].sum(1);v=np.array([x[field] for x in values]);return {"n":len(v),"mean":float(v.mean()),"ci95":[float(np.quantile(m,.025)),float(np.quantile(m,.975))],"p":float((1+sum(m<=0))/(n+1))}
def diffboot(crowd:list[dict[str,Any]],base:list[dict[str,Any]],seed=4202,n=10000):
 if not crowd or not base:return {"n_crowd":len(crowd),"n_baseline":len(base),"mean":None,"ci95":[None,None],"p":None}
 weeks=sorted({x["time"]//WEEK for x in crowd+base});cs=np.array([sum(x["short_net"] for x in crowd if x["time"]//WEEK==w) for w in weeks]);cc=np.array([sum(1 for x in crowd if x["time"]//WEEK==w) for w in weeks]);bs=np.array([sum(x["short_net"] for x in base if x["time"]//WEEK==w) for w in weeks]);bc=np.array([sum(1 for x in base if x["time"]//WEEK==w) for w in weeks]);rng=np.random.default_rng(seed);d=rng.integers(0,len(weeks),(n,len(weeks)));den1=cc[d].sum(1);den2=bc[d].sum(1);mask=(den1>0)&(den2>0);m=cs[d].sum(1)[mask]/den1[mask]-bs[d].sum(1)[mask]/den2[mask];point=np.mean([x["short_net"] for x in crowd])-np.mean([x["short_net"] for x in base]);return {"n_crowd":len(crowd),"n_baseline":len(base),"mean":float(point),"ci95":[float(np.quantile(m,.025)),float(np.quantile(m,.975))],"p":float((1+sum(m<=0))/(len(m)+1))}
def holm(ps):
 out=[None]*len(ps);o=sorted((p,i) for i,p in enumerate(ps) if p is not None);run=0
 for k,(p,i) in enumerate(o):run=max(run,min(1,(len(o)-k)*p));out[i]=run
 return out
def classify(records,kind,universe):
 bytime={(r["asset"],r["time"]):r for r in records};crowd=[];base=[]
 for r in records:
  high=r["funding"]>0 and r["fund_rank"]>=.75
  if kind=="PRIMARY":g=r["oi_growth"];rank=r["oi_rank"]
  elif kind=="OI_SHIFT_30D":
   q=bytime.get((r["asset"],r["time"]-30*86400));g=q["oi_growth"] if q else -math.inf;rank=q["oi_rank"] if q else -math.inf
  else:
   i=universe.index(r["asset"]);q=bytime.get((universe[(i+1)%len(universe)],r["time"]));g=q["oi_growth"] if q else -math.inf;rank=q["oi_rank"] if q else -math.inf
  if high and g>0 and rank>=.75 and r["flow"]>1:crowd.append(r)
  elif high:base.append(r)
 return crowd,base
def analyze(records,protocol,stage):
 u=protocol["universe"];crowd,base=classify(records,"PRIMARY",u);agg=boot(crowd);inc=diffboot(crowd,base);cfg=protocol[stage];assets=[]
 for s in u:assets.append({"asset":s,**boot([x for x in crowd if x["asset"]==s])})
 ap=holm([x["p"] for x in assets]);[x.update(holm_p=p) for x,p in zip(assets,ap)]
 blocks=[]
 for a,b in cfg["temporal_blocks"]:blocks.append({"window":[a,b],**boot([x for x in crowd if ts(a+"T00:00:00Z")<=x["time"]<=ts(b+"T23:59:59Z")])})
 bp=holm([x["p"] for x in blocks]);[x.update(holm_p=p) for x,p in zip(blocks,bp)]
 controls=[]
 for kind in ["OI_SHIFT_30D","OI_CYCLIC_ASSET"]:
  c,b=classify(records,kind,u);controls.append({"id":kind,**diffboot(c,b)})
 cp=holm([x["p"] for x in controls]);[x.update(holm_p=p) for x,p in zip(controls,cp)]
 sufficient=sum(x["n"]>=cfg["minimum_events_per_asset"] for x in assets);positive=sum((x["mean"] or -99)>0 for x in assets);sig=sum((x["mean"] or -99)>0 and (x["holm_p"] or 1)<.05 for x in assets);posb=sum((x["mean"] or -99)>0 for x in blocks);sigb=sum((x["mean"] or -99)>0 and (x["holm_p"] or 1)<.05 for x in blocks)
 gates={"sample":len(crowd)>=cfg["minimum_crowding_events"] and sufficient>=cfg["minimum_assets"],"net":agg["mean"] is not None and agg["mean"]>0 and agg["ci95"][0]>0 and agg["p"]<.05,"incremental":inc["mean"] is not None and inc["mean"]>0 and inc["ci95"][0]>0 and inc["p"]<.05,"cross_asset":positive>=8 and sig>=5,"temporal":posb==3 and sigb>=2,"controls":all(not((x["mean"] or -99)>0 and (x["holm_p"] or 1)<.05) for x in controls)}
 return {"stage":stage.upper(),"decision":"PASS" if all(gates.values()) else "FAIL","gates":gates,"crowding":agg,"incremental_vs_funding_only":inc,"assets":assets,"temporal":blocks,"controls":controls,"summary":{"crowding_events":len(crowd),"baseline_events":len(base),"sufficient_assets":sufficient,"positive_assets":positive,"significant_assets":sig}}
def seal():
 p=load(PROTOCOL);d=load(D1);assert not p["outcomes_inspected"] and d["global_result"]=="D1_QA_PASS_REQUIRED_FIELDS";new(SEAL,json.dumps({"state":"SEALED_BEFORE_OUTCOMES","protocol_sha256":sha(PROTOCOL),"instrument_sha256":sha(Path(__file__)),"d1_sha256":sha(D1),"created_utc":datetime.now(timezone.utc).isoformat()},indent=2)+"\n");print("SEALED")
def verify():
 s=load(SEAL);assert s["protocol_sha256"]==sha(PROTOCOL) and s["instrument_sha256"]==sha(Path(__file__)) and s["d1_sha256"]==sha(D1)
def run_d2():
 verify();p=load(PROTOCOL);r=analyze(build_records(p,"2024-07","2025-12"),p,"d2");r.update(protocol_sha256=sha(PROTOCOL),holdout_opened=False);new(RESULTS/"d2"/"D2_REPORT.json",json.dumps(r,indent=2)+"\n");print(r["decision"])
def run_d3():
 verify();d2=load(RESULTS/"d2"/"D2_REPORT.json");new(OPEN,json.dumps({"state":"OPENED_ONCE","d2_sha256":sha(RESULTS/"d2"/"D2_REPORT.json"),"protocol_sha256":sha(PROTOCOL),"opened_utc":datetime.now(timezone.utc).isoformat()},indent=2)+"\n");p=load(PROTOCOL);r=analyze(build_records(p,"2026-01","2026-06"),p,"d3");new(RESULTS/"d3"/"D3_REPORT.json",json.dumps(r,indent=2)+"\n");final="CONFIRMED_READY_FOR_PROSPECTIVE_CONFIRMATION" if d2["decision"]=="PASS" and r["decision"]=="PASS" else "REJECTED";d4={"stage":"D4","d2":d2["decision"],"d3":r["decision"],"final":final,"bot_authorized":False};new(RESULTS/"d4"/"D4_REPORT.json",json.dumps(d4,indent=2)+"\n");print(final)
def main():
 a=argparse.ArgumentParser(description="Frozen H02 crowding research; no orders");a.add_argument("command",choices=["seal","run-d2","run-d3-d4"]);x=a.parse_args();return {"seal":seal,"run-d2":run_d2,"run-d3-d4":run_d3}[x.command]()
if __name__=="__main__":main()
