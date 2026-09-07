import os, io, zipfile, time
from datetime import date, timedelta
import requests
import pandas as pd

END = date.today()
START_LOOKBACK_DAYS = 390
RAW = "data/raw"
os.makedirs(RAW, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
    "Accept": "*/*",
    "Referer": "https://www.nseindia.com/"
}

session = requests.Session()
session.headers.update(HEADERS)
try:
    session.get("https://www.nseindia.com/", timeout=20)
except Exception:
    pass

def urls(d):
    ddmmyyyy = d.strftime("%d%m%Y")
    ddMONyyyy = d.strftime("%d%b%Y").upper()
    return [
        f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{ddmmyyyy}.csv",
        f"https://nsearchives.nseindia.com/content/historical/EQUITIES/{d.strftime('%Y')}/{d.strftime('%b').upper()}/cm{ddMONyyyy}bhav.csv.zip",
        f"https://nsearchives.nseindia.com/archives/equities/bhavcopy/pr/PR{d.strftime('%d%m%y')}.zip",
    ]

def get_one(d):
    out = os.path.join(RAW, f"{d.isoformat()}.csv")
    if os.path.exists(out) and os.path.getsize(out) > 1000:
        return True
    for u in urls(d):
        try:
            r = session.get(u, timeout=45)
            if r.status_code != 200 or len(r.content) < 1000:
                continue
            content = r.content
            if u.endswith(".zip"):
                z = zipfile.ZipFile(io.BytesIO(content))
                csvs = [n for n in z.namelist() if n.lower().endswith(".csv")]
                if not csvs:
                    continue
                content = z.read(csvs[0])
            if b"SYMBOL" in content[:5000].upper() or b"FININSTRMNT" in content[:10000].upper():
                open(out, "wb").write(content)
                return True
        except Exception:
            continue
    return False

# Download enough history for 50 sessions plus EMA/high/lookback calculations.
d = END - timedelta(days=START_LOOKBACK_DAYS)
ok = 0
while d <= END:
    if d.weekday() < 5:
        ok += int(get_one(d))
        time.sleep(0.15)
    d += timedelta(days=1)

print("Downloaded/retained files:", ok)
