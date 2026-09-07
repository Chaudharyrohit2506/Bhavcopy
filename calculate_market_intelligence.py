import glob, os, json
import numpy as np
import pandas as pd

RAW="data/raw"
OUT="data/market_intelligence.json"

def read_file(p):
    df=pd.read_csv(p)
    df.columns=[str(c).strip().upper() for c in df.columns]
    # Common NSE full-bhavcopy aliases
    ren={
      "FININSTRMID":"ISIN","FININSTRMNT_ID":"ISIN","SECURITY":"SYMBOL",
      "TCKRSYMB":"SYMBOL","SYMBOL":"SYMBOL","CLOSE_PRICE":"CLOSE",
      "CLSPRIC":"CLOSE","PRV_CLPR":"PREV_CLOSE","PRVSCLSGPRIC":"PREV_CLOSE",
      "TOTTRDQTY":"VOLUME","TtlTradgVol":"VOLUME"
    }
    for a,b in ren.items():
        if a in df.columns and b not in df.columns: df[b]=df[a]
    if "SYMBOL" not in df or "CLOSE" not in df: return None
    for c in ["CLOSE","PREV_CLOSE","VOLUME","OPEN","HIGH","LOW"]:
        if c in df: df[c]=pd.to_numeric(df[c],errors="coerce")
    if "SERIES" in df:
        df=df[df["SERIES"].astype(str).str.upper().isin(["EQ","BE","BZ"])].copy()
    return df[["SYMBOL"]+[c for c in ["ISIN","CLOSE","PREV_CLOSE","VOLUME","OPEN","HIGH","LOW"] if c in df]].dropna(subset=["CLOSE"])

files=sorted(glob.glob(RAW+"/*.csv"))
frames=[]
for p in files:
    try:
        x=read_file(p)
        if x is not None and len(x): 
            x["DATE"]=pd.to_datetime(os.path.basename(p)[:10])
            frames.append(x)
    except Exception as e:
        print("skip",p,e)

if not frames: raise SystemExit("No valid NSE raw files found")
allx=pd.concat(frames,ignore_index=True).sort_values(["SYMBOL","DATE"])
dates=sorted(allx.DATE.unique())[-50:]

# Reindex each symbol on actual observed sessions; calculate metrics using history.
rows=[]
for d in dates:
    cur=allx[allx.DATE==d].copy()
    prev=allx[allx.DATE<d].sort_values("DATE").groupby("SYMBOL").tail(1)[["SYMBOL","CLOSE","VOLUME"]].rename(columns={"CLOSE":"PCLOSE","VOLUME":"PVOL"})
    cur=cur.merge(prev,on="SYMBOL",how="left")
    ret=cur.CLOSE/cur.PCLOSE-1
    adv=(ret>0).sum(); dec=(ret<0).sum()
    av=cur.loc[ret>0,"VOLUME"].sum(); dv=cur.loc[ret<0,"VOLUME"].sum()
    adr=adv/dec if dec else np.nan
    trin=(adr)/(av/dv) if dv else np.nan
    # 4.5% movers
    up45=(ret>=.045).sum(); dn45=(ret<=-.045).sum()
    # 5-session +20%
    prior5=allx[allx.DATE<d].sort_values("DATE").DATE.unique()
    p5=prior5[-5] if len(prior5)>=5 else None
    p40=prior5[-40] if len(prior5)>=40 else None
    p5df=allx[allx.DATE==p5][["SYMBOL","CLOSE"]].rename(columns={"CLOSE":"C5"}) if p5 is not None else pd.DataFrame()
    p40df=allx[allx.DATE==p40][["SYMBOL","CLOSE"]].rename(columns={"CLOSE":"C40"}) if p40 is not None else pd.DataFrame()
    z=cur.merge(p5df,on="SYMBOL",how="left") if len(p5df) else cur.assign(C5=np.nan)
    z["r5"]=z.CLOSE/z.C5-1
    up20=(z.r5>=.20).sum()
    z=z.merge(p40df,on="SYMBOL",how="left") if len(p40df) else z.assign(C40=np.nan)
    z["r40"]=z.CLOSE/z.C40-1
    # EMA breadth on security histories
    ema20=ema50=ema200=0
    for sym,g in allx[allx.DATE<=d].groupby("SYMBOL"):
        s=g.sort_values("DATE").CLOSE
        if len(s)>=200:
            e20=s.ewm(span=20,adjust=False).mean().iloc[-1]
            e50=s.ewm(span=50,adjust=False).mean().iloc[-1]
            e200=s.ewm(span=200,adjust=False).mean().iloc[-1]
            px=s.iloc[-1]
            ema20 += px>e20; ema50 += px>e50; ema200 += px>e200
    n=len(cur)
    rows.append({
      "session_date":str(pd.Timestamp(d).date()),
      "advances":int(adv),"declines":int(dec),
      "ad_ratio":None if not np.isfinite(adr) else round(float(adr),4),
      "trin":None if not np.isfinite(trin) else round(float(trin),4),
      "up_4_5":int(up45),"down_4_5":int(dn45),"up20_5d":int(up20),
      "universe":int(n),
      "above_20_ema":round(ema20/n*100,2) if n else None,
      "above_50_ema":round(ema50/n*100,2) if n else None,
      "above_200_ema":round(ema200/n*100,2) if n else None,
    })

os.makedirs("data",exist_ok=True)
json.dump({"sessions":rows,"latest":rows[-1],"raw_files":len(files)},open(OUT,"w"),indent=2)
print("Calculated",len(rows),"sessions")
