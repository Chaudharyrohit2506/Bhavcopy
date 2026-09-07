import io,os,zipfile,time,json,re,csv
from datetime import date,timedelta,datetime
import requests

END=date.today()
# Keep enough exchange sessions for a full 252-session 52-week lookback
# plus the 50-session output ledger and a safety buffer.
LOOKBACK=460
RAW='data/raw'
AUX='data/aux'
MCAP=f'{AUX}/mcap'
INDEX=f'{AUX}/indices'
for p in (RAW,AUX,MCAP,INDEX):
    os.makedirs(p,exist_ok=True)

H={
    'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36',
    'Accept':'*/*',
    'Accept-Language':'en-US,en;q=0.9',
    'Referer':'https://www.nseindia.com/',
    'Origin':'https://www.nseindia.com',
    'Connection':'keep-alive'
}
s=requests.Session()
s.headers.update(H)
try:
    s.get('https://www.nseindia.com/',timeout=20)
except Exception:
    pass

def get_one(d):
    out=f'{RAW}/{d}.csv'
    if os.path.exists(out) and os.path.getsize(out)>1000:
        return True
    urls=[
        f'https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{d:%d%m%Y}.csv',
        f'https://nsearchives.nseindia.com/content/historical/EQUITIES/{d:%Y}/{d:%b}'.upper()+f'/cm{d:%d%b%Y}'.upper()+'bhav.csv.zip',
        f'https://nsearchives.nseindia.com/archives/equities/bhavcopy/pr/PR{d:%d%m%y}.zip'
    ]
    for u in urls:
        try:
            r=s.get(u,timeout=45)
            if r.status_code!=200 or len(r.content)<1000:
                continue
            b=r.content
            if u.endswith('.zip'):
                with zipfile.ZipFile(io.BytesIO(b)) as z:
                    ns=[n for n in z.namelist() if n.lower().endswith('.csv')]
                    if not ns:
                        continue
                    b=z.read(ns[0])
            if b'SYMBOL' in b[:15000].upper() or b'FININSTRMNT' in b[:15000].upper():
                open(out,'wb').write(b)
                return True
        except Exception:
            pass
    return False

d=END-timedelta(days=LOOKBACK)
n=0
while d<=END:
    if d.weekday()<5:
        n+=int(get_one(d))
        time.sleep(.15)
    d+=timedelta(days=1)

print('Downloaded/retained NSE raw files:',n)

dates=[]
for p in os.listdir(RAW):
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}\.csv',p):
        try:
            dates.append(datetime.strptime(p[:10],'%Y-%m-%d').date())
        except Exception:
            pass
all_dates=sorted(set(dates))
if len(all_dates)<302:
    raise SystemExit(f'Need at least 302 NSE raw sessions for 50 output sessions plus full 252-session lookback; found {len(all_dates)}')
dates=all_dates[-50:]

def pr_member(d,member,out):
    if os.path.exists(out) and os.path.getsize(out)>100:
        return True
    try:
        r=s.get(f'https://nsearchives.nseindia.com/archives/equities/bhavcopy/pr/PR{d:%d%m%y}.zip',timeout=60)
        if r.status_code!=200:
            return False
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            t=next((x for x in z.namelist() if x.lower().endswith(member.lower())),None)
            if not t:
                return False
            open(out,'wb').write(z.read(t))
            return True
    except Exception:
        return False

m=ix=0
for d in dates:
    m+=int(pr_member(d,f'mcap{d:%d%m%Y}.csv',f'{MCAP}/{d}.csv'))
    time.sleep(.15)
    o=f'{INDEX}/{d}.csv'
    if os.path.exists(o) and os.path.getsize(o)>100:
        ix+=1
        continue
    try:
        r=s.get(f'https://nsearchives.nseindia.com/content/indices/ind_close_all_{d:%d%m%Y}.csv',timeout=45)
        if r.status_code==200 and len(r.content)>1000:
            open(o,'wb').write(r.content)
            ix+=1
    except Exception:
        pass
    time.sleep(.12)

print('Market-cap files:',m,'/ 50')
print('Index-close files:',ix,'/ 50')
if m != 50:
    raise SystemExit(f'Official NSE market-cap coverage incomplete: {m}/50')
if ix != 50:
    raise SystemExit(f'Official NSE index-close coverage incomplete: {ix}/50')

vrows=[]
for d in dates:
    p=f'{INDEX}/{d}.csv'
    try:
        with open(p,'r',encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                name=str(row.get('Index Name','')).strip().upper()
                if name=='INDIA VIX':
                    close=row.get('Closing Index Value')
                    if close not in (None,'','-'):
                        vrows.append({
                            'DATE':d.isoformat(),
                            'CLOSE':float(str(close).replace(',',''))
                        })
                    break
    except Exception:
        pass

if len(vrows) == 50:
    json.dump({'data':vrows},open(f'{AUX}/india_vix.json','w',encoding='utf8'),indent=2)
    print('India VIX from official NSE index-close files:',len(vrows),'rows')
else:
    raise SystemExit(f'Official NSE India VIX coverage incomplete: {len(vrows)}/50')

mp=f'{AUX}/nifty500.csv'
if not os.path.exists(mp) or os.path.getsize(mp)<100:
    try:
        r=s.get('https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv',timeout=30)
        if r.status_code==200 and len(r.content)>1000:
            open(mp,'wb').write(r.content)
            print('NIFTY500 mapping downloaded')
    except Exception:
        pass

print('Official NSE auxiliary acquisition complete')
