import io, os, zipfile, time, json, re
from datetime import date, timedelta, datetime
import requests

END=date.today(); LOOKBACK=390
RAW="data/raw"; AUX="data/aux"; MCAP=f"{AUX}/mcap"; INDEX=f"{AUX}/indices"
for p in (RAW,AUX,MCAP,INDEX): os.makedirs(p,exist_ok=True)
H={"User-Agent":"Mozilla/5.0 Chrome/131","Accept":"*/*","Referer":"https://www.nseindia.com/"}
s=requests.Session(); s.headers.update(H)
try:s.get("https://www.nseindia.com/",timeout=20)
except:pass

def get_one(d):
    out=f"{RAW}/{d}.csv"
    if os.path.exists(out) and os.path.getsize(out)>1000:return True
    urls=[
      f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{d:%d%m%Y}.csv",
      f"https://nsearchives.nseindia.com/content/historical/EQUITIES/{d:%Y}/{d:%b}".upper()+f"/cm{d:%d%b%Y}".upper()+"bhav.csv.zip",
      f"https://nsearchives.nseindia.com/archives/equities/bhavcopy/pr/PR{d:%d%m%y}.zip"]
    for u in urls:
      try:
        r=s.get(u,timeout=45)
        if r.status_code!=200 or len(r.content)<1000:continue
        b=r.content
        if u.endswith(".zip"):
          with zipfile.ZipFile(io.BytesIO(b)) as z:
            ns=[n for n in z.namelist() if n.lower().endswith(".csv")]
            if not ns:continue
            b=z.read(ns[0])
        if b"SYMBOL" in b[:15000].upper() or b"FININSTRMNT" in b[:15000].upper():
          open(out,"wb").write(b); return True
      except:pass
    return False

d=END-timedelta(days=LOOKBACK); n=0
while d<=END:
  if d.weekday()<5:
    n+=int(get_one(d)); time.sleep(.15)
  d+=timedelta(days=1)
print("Downloaded/retained NSE raw files:",n)

dates=[]
for p in os.listdir(RAW):
  if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.csv",p):
    try:dates.append(datetime.strptime(p[:10],"%Y-%m-%d").date())
    except:pass
dates=sorted(set(dates))[-50:]
if len(dates)<50:raise SystemExit(f"Need 50 raw sessions, found {len(dates)}")

def pr_member(d,member,out):
  if os.path.exists(out) and os.path.getsize(out)>100:return True
  try:
    u=f"https://nsearchives.nseindia.com/archives/equities/bhavcopy/pr/PR{d:%d%m%y}.zip"
    r=s.get(u,timeout=60)
    if r.status_code!=200:return False
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
      t=next((x for x in z.namelist() if x.lower().endswith(member.lower())),None)
      if not t:return False
      open(out,"wb").write(z.read(t)); return True
  except:return False

m=ix=0
for d in dates:
  m+=int(pr_member(d,f"mcap{d:%d%m%Y}.csv",f"{MCAP}/{d}.csv")); time.sleep(.15)
  o=f"{INDEX}/{d}.csv"
  if os.path.exists(o) and os.path.getsize(o)>100:ix+=1;continue
  try:
    r=s.get(f"https://nsearchives.nseindia.com/content/indices/ind_close_all_{d:%d%m%Y}.csv",timeout=45)
    if r.status_code==200 and len(r.content)>1000:open(o,"wb").write(r.content);ix+=1
  except:pass
  time.sleep(.12)
print("Market-cap files:",m,"/ 50"); print("Index-close files:",ix,"/ 50")

vp=f"{AUX}/india_vix.json"
if not os.path.exists(vp) or os.path.getsize(vp)<100:
  for u in [
    f"https://www.nseindia.com/api/historical/vixhistory?from={dates[0]:%d-%m-%Y}&to={dates[-1]:%d-%m-%Y}",
    f"https://www.nseindia.com/historicalOR/vixhistory?from={dates[0]:%d-%m-%Y}&to={dates[-1]:%d-%m-%Y}"]:
    try:
      r=s.get(u,timeout=45)
      if r.status_code==200 and len(r.content)>100:
        json.dump(r.json(),open(vp,"w",encoding="utf8")); print("India VIX downloaded"); break
    except:pass

mp=f"{AUX}/nifty500.csv"
if not os.path.exists(mp) or os.path.getsize(mp)<100:
  try:
    r=s.get("https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv",timeout=30)
    if r.status_code==200 and len(r.content)>1000:open(mp,"wb").write(r.content);print("NIFTY500 mapping downloaded")
  except:pass
print("Official NSE auxiliary acquisition complete")
