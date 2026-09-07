import glob,os,json,re
import numpy as np,pandas as pd
RAW="data/raw";AUX="data/aux";OUT="data/market_intelligence.json"
def cols(df):df.columns=[str(c).replace("\ufeff","").strip().upper() for c in df.columns];return df
def pick(df,names):
  return next((n for n in names if n in df.columns),None)
def rawfile(p):
  try:df=cols(pd.read_csv(p,low_memory=False,encoding="utf-8-sig"))
  except:return None
  sy=pick(df,["SYMBOL","TCKRSYMB","SECURITY"]);cl=pick(df,["CLOSE_PRICE","CLOSE","CLSPRIC","PRICCLSGPRIC","LAST_PRICE"])
  pc=pick(df,["PREV_CLOSE","PRV_CLPR","PRVSCLSGPRIC"]);vo=pick(df,["TTL_TRD_QNTY","TOTTRDQTY","TOTALTRADGVOLUME","VOLUME","TTL_TRD_QNTY"])
  se=pick(df,["SERIES","SCTYSRS"])
  if not sy or not cl:return None
  x=pd.DataFrame({"SYMBOL":df[sy].astype(str).str.strip().str.upper(),"CLOSE":pd.to_numeric(df[cl],errors="coerce"),
                  "PREV_CLOSE":pd.to_numeric(df[pc],errors="coerce") if pc else np.nan,
                  "VOLUME":pd.to_numeric(df[vo],errors="coerce") if vo else 0})
  if se:x=x[df[se].astype(str).str.strip().str.upper().isin(["EQ","BE","BZ"])].copy()
  return x[x.CLOSE.notna() & x.SYMBOL.ne("")].copy()
fs=sorted(glob.glob(f"{RAW}/*.csv"));frames=[]
for p in fs:
  x=rawfile(p)
  if x is not None:
    x["DATE"]=pd.Timestamp(os.path.basename(p)[:10]);frames.append(x)
if not frames:raise SystemExit("No valid NSE raw files found")
allx=pd.concat(frames,ignore_index=True).drop_duplicates(["DATE","SYMBOL"],keep="last").sort_values(["DATE","SYMBOL"])
dates=sorted(allx.DATE.unique())[-50:]
if len(dates)!=50:raise SystemExit(f"Expected exactly 50 sessions, got {len(dates)}")
daily={d:allx[allx.DATE==d].copy() for d in dates}

def mcap(d):
  p=f"{AUX}/mcap/{pd.Timestamp(d).date()}.csv"
  if not os.path.exists(p):return None
  try:x=cols(pd.read_csv(p,low_memory=False,encoding="utf-8-sig"))
  except:return None
  sy=pick(x,["SYMBOL","TCKRSYMB","SECURITY"]);mc=next((c for c in x.columns if ("MARKET" in c and "CAP" in c) or "MCAP" in c or "MKT_CAP" in c),None)
  if not sy or not mc:return None
  z=pd.DataFrame({"SYMBOL":x[sy].astype(str).str.strip().str.upper(),"MCAP":pd.to_numeric(x[mc],errors="coerce")}).dropna()
  if z.MCAP.median()>1e7:z.MCAP/=1e7
  return z.drop_duplicates("SYMBOL")
def vix():
  p=f"{AUX}/india_vix.json"
  if not os.path.exists(p):return {}
  try:o=json.load(open(p,encoding="utf8"))
  except:return {}
  a=o.get("data",o) if isinstance(o,dict) else o;out={}
  if isinstance(a,list):
    for r in a:
      if not isinstance(r,dict):continue
      dt=next((r[k] for k in r if str(k).upper() in ("EOD_TIMESTAMP","DATE","DATE1","TIMESTAMP")),None)
      cl=next((r[k] for k in r if "CLOSE" in str(k).upper()),None)
      if dt is not None and cl is not None:
        try:out[str(pd.to_datetime(dt).date())]=float(str(cl).replace(",",""))
        except:pass
  return out
def industry():
  p=f"{AUX}/nifty500.csv"
  if not os.path.exists(p):return {}
  try:x=cols(pd.read_csv(p,low_memory=False,encoding="utf-8-sig"))
  except:return {}
  sy=pick(x,["SYMBOL"]);ind=pick(x,["INDUSTRY"])
  return dict(zip(x[sy].astype(str).str.strip().str.upper(),x[ind].astype(str).str.strip())) if sy and ind else {}
def sector(i):
  z=str(i).upper()
  mp=[("Financials",["FINANCIAL","BANK","INSURANCE","NBFC"]),("Information Technology",["IT","SOFTWARE"]),
      ("Healthcare",["PHARMA","HEALTHCARE"]),("Energy",["ENERGY","OIL","GAS"]),("Materials",["METALS","CEMENT","CHEMICAL","FERTIL"]),
      ("Industrials",["INDUSTRIAL","CONSTRUCTION","CAPITAL GOODS"]),("Consumer",["CONSUMER","FMCG","RETAIL"]),
      ("Automobile",["AUTOMOBILE","AUTO"]),("Telecom",["TELECOM"]),("Media",["MEDIA"]),("Textiles",["TEXTILE"]),
      ("Realty",["REALTY"]),("Services",["SERVICES"]),("Utilities",["POWER","UTILITY"])]
  for s,k in mp:
    if any(q in z for q in k):return s
  return "Other"
def idxfile(d):
  p=f"{AUX}/indices/{pd.Timestamp(d).date()}.csv"
  if not os.path.exists(p):return {}
  try:x=cols(pd.read_csv(p,low_memory=False,encoding="utf-8-sig"))
  except:return {}
  n=pick(x,["INDEX_NAME","INDEX NAME","INDEX","INDEXNAME"]);c=pick(x,["CLOSE","CLOSE_PRICE","CLOSING_INDEX_VALUE"])
  if not n or not c:return {}
  out={}
  for _,r in x.iterrows():
    try:out[str(r[n]).strip().upper()]=float(str(r[c]).replace(",",""))
    except:pass
  return out
vx=vix();imap=industry();ix={d:idxfile(d) for d in dates}
aliases={"NIFTY AUTO":"Automobile","NIFTY BANK":"Financials","NIFTY FINANCIAL SERVICES":"Financials","NIFTY FMCG":"Consumer",
"NIFTY IT":"Information Technology","NIFTY MEDIA":"Media","NIFTY METAL":"Materials","NIFTY PHARMA":"Healthcare",
"NIFTY PSU BANK":"Financials","NIFTY PRIVATE BANK":"Financials","NIFTY REALTY":"Realty","NIFTY OIL AND GAS":"Energy",
"NIFTY HEALTHCARE":"Healthcare","NIFTY CONSUMER DURABLES":"Consumer","NIFTY TELECOM":"Telecom","NIFTY CONSUMER SERVICES":"Services"}
def sec40(i):
  if i<40:return {}
  a,b=ix.get(dates[i-40],{}),ix.get(dates[i],{});o={}
  for name,sec in aliases.items():
    def f(m):
      for k,v in m.items():
        if k==name or name in k:return v
    x,y=f(a),f(b)
    if x and y:o[sec]=round((y/x-1)*100,2)
  return o

rows=[]
for i,d in enumerate(dates):
  c=daily[d].copy()
  if i:c=c.merge(daily[dates[i-1]][["SYMBOL","CLOSE","VOLUME"]].rename(columns={"CLOSE":"PC","VOLUME":"PV"}),on="SYMBOL",how="left")
  else:c["PC"]=c.PREV_CLOSE
  c["BASE"]=c.PC.fillna(c.PREV_CLOSE);ret=c.CLOSE/c.BASE-1;v=ret.replace([np.inf,-np.inf],np.nan).notna()
  adv=int((ret[v]>0).sum());dec=int((ret[v]<0).sum());un=int((ret[v]==0).sum());adr=adv/dec if dec else np.nan
  uv=c.loc[ret>0,"VOLUME"].fillna(0).sum();dv=c.loc[ret<0,"VOLUME"].fillna(0).sum();tr=(adr/(uv/dv)) if adr and uv and dv else np.nan
  up45=int((ret>=.045).sum());dn45=int((ret<=-.045).sum())
  up20=0
  if i>=5:
    q=c[["SYMBOL","CLOSE"]].merge(daily[dates[i-5]][["SYMBOL","CLOSE"]].rename(columns={"CLOSE":"C5"}),on="SYMBOL",how="left")
    up20=int(((q.CLOSE/q.C5-1)>=.20).sum())
  e20=e50=e200=den=0
  for _,g in allx[allx.DATE<=d].groupby("SYMBOL"):
    s=g.sort_values("DATE").CLOSE.dropna()
    if len(s)<20:continue
    px=s.iloc[-1];den+=1
    e20+=int(px>s.ewm(span=20,adjust=False).mean().iloc[-1]);e50+=int(px>s.ewm(span=50,adjust=False).mean().iloc[-1]);e200+=int(px>s.ewm(span=200,adjust=False).mean().iloc[-1])
  mc=mcap(d);large=mid=small=None
  if mc is not None and len(mc)>=250:
    rk=dict(zip(mc.sort_values("MCAP",ascending=False).SYMBOL,range(1,len(mc)+1)));rr=c.SYMBOL.str.upper().map(rk)
    large_mask=rr<=100; mid_mask=(rr>=101)&(rr<=250); small_mask=(rr>=251)&(rr<=500)
    large=round(float((ret[large_mask]>0).sum()/large_mask.sum()*100),2) if large_mask.sum() else None
    mid=round(float((ret[mid_mask]>0).sum()/mid_mask.sum()*100),2) if mid_mask.sum() else None
    small=round(float((ret[small_mask]>0).sum()/small_mask.sum()*100),2) if small_mask.sum() else None
  near=0
  for _,g in allx[allx.DATE<=d].groupby("SYMBOL"):
    s=g.sort_values("DATE").CLOSE.dropna()
    if len(s)>=20 and s.iloc[-1]>=.9*s.tail(252).max():near+=1
  pen={}
  for sym in c.SYMBOL.unique():
    sec=sector(imap.get(str(sym).upper(),""))
    if sec=="Other":continue
    s=allx[(allx.SYMBOL==sym)&(allx.DATE<=d)].sort_values("DATE").CLOSE
    if len(s)>=56:
      pen.setdefault(sec,[0,0]);pen[sec][1]+=1;pen[sec][0]+=int(s.iloc[-1]>s.iloc[-56:-1].max())
  pen={k:round(a/b*100,2) for k,(a,b) in pen.items() if b}
  rows.append({"session_date":str(pd.Timestamp(d).date()),"advances":adv,"declines":dec,"unchanged":un,
    "ad_ratio":None if not np.isfinite(adr) else round(float(adr),4),"trin":None if not np.isfinite(tr) else round(float(tr),4),
    "up_4_5":up45,"down_4_5":dn45,"up20_5d":up20,"universe":len(c),"ema_universe":den,
    "above_20_ema":round(e20/den*100,2) if den else None,"above_50_ema":round(e50/den*100,2) if den else None,
    "above_200_ema":round(e200/den*100,2) if den else None,"large_cap_adv_pct":large,"mid_cap_adv_pct":mid,"small_cap_adv_pct":small,
    "near_10pct_52w_high":near,"near_10pct_52w_high_pct":round(near/len(c)*100,2) if len(c) else None,
    "india_vix":vx.get(str(pd.Timestamp(d).date())),"breakout_follow_through_pct":None,
    "sector_40d_returns":sec40(i),"sector_55d_high_penetration":pen})
# Breakout follow-through: for each ledger session, evaluate 55-session highs and whether
# the breakout close is retained two completed sessions later. The last two sessions are
# naturally unavailable for T+2 and remain N/V rather than being estimated.
all_dates=sorted(allx.DATE.unique())
for r in rows:
  d=pd.Timestamp(r["session_date"])
  try:i=all_dates.index(d)
  except ValueError:continue
  if i<55 or i+2>=len(all_dates):continue
  outcomes=[]
  for j in range(55,i):
    a=all_dates[j];b=all_dates[j+2]
    prior=allx[allx.DATE<a].groupby("SYMBOL").CLOSE.max()
    t=daily.get(a,allx[allx.DATE==a]).set_index("SYMBOL").CLOSE
    f=daily.get(b,allx[allx.DATE==b]).set_index("SYMBOL").CLOSE
    common=t.index.intersection(prior.index).intersection(f.index)
    br=t.loc[common]>prior.loc[common]
    if br.any():outcomes += list((f.loc[common[br]]>=t.loc[common[br]]).values)
  r["breakout_follow_through_pct"]=round(float(np.mean(outcomes)*100),2) if outcomes else None

# Latest 50-stock RVOL table.
rv=[];d=dates[-1];mc=mcap(d)
if mc is not None:
  for sym,g in allx.groupby("SYMBOL"):
    g=g[g.DATE<=d].sort_values("DATE")
    if len(g)<25:continue
    z=g.tail(25);base=z.head(20).VOLUME.mean();last=z.tail(5).VOLUME.mean()
    if base<=0:continue
    m=mc.loc[mc.SYMBOL==str(sym).upper(),"MCAP"];m=float(m.iloc[0]) if len(m) else np.nan
    if pd.notna(m) and 300<m<31000:
      p=float(z.CLOSE.iloc[-1]);old=float(g.tail(41).CLOSE.iloc[0]) if len(g)>=41 else np.nan
      rv.append({"symbol":str(sym),"weekly_rvol_pct":round(last/base*100,2),"last_40d_return_pct":round((p/old-1)*100,2) if old else None,"current_price":round(p,2),"market_cap_cr":round(m,2),"sector":sector(imap.get(str(sym).upper(),""))})
rv=sorted(rv,key=lambda x:x["weekly_rvol_pct"],reverse=True)[:50]
s40=sorted([{"sector":k,"return_40d_pct":v} for k,v in rows[-1]["sector_40d_returns"].items()],key=lambda x:x["return_40d_pct"],reverse=True)
s55=sorted([{"sector":k,"penetration_pct":v} for k,v in rows[-1]["sector_55d_high_penetration"].items()],key=lambda x:x["penetration_pct"],reverse=True)
res={"sessions":rows,"latest":rows[-1],"high_rvol_stocks":rv,"sector_40d_ranking":s40,"sector_55d_high_ranking":s55,
"data_coverage":{"raw_sessions":50,"mcap_files":sum(os.path.exists(f"{AUX}/mcap/{pd.Timestamp(d).date()}.csv") for d in dates),
"index_files":sum(os.path.exists(f"{AUX}/indices/{pd.Timestamp(d).date()}.csv") for d in dates),"vix_rows":len(vx),"nifty500_sector_map":bool(imap)}}
os.makedirs("data",exist_ok=True);json.dump(res,open(OUT,"w",encoding="utf8"),indent=2)
print("SUCCESS:",len(rows),"sessions calculated");print("Latest:",rows[-1]["session_date"],"A/D",rows[-1]["advances"],"/",rows[-1]["declines"],"VIX",rows[-1]["india_vix"])
