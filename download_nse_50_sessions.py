import io,os,zipfile,time,json,re,csv
from datetime import date,timedelta,datetime
import requests
from zoneinfo import ZoneInfo

IST=ZoneInfo('Asia/Kolkata')
NOW_IST=datetime.now(IST)

LOOKBACK=460
RAW='data/raw'
AUX='data/aux'
MCAP=f'{AUX}/mcap'
INDEX=f'{AUX}/indices'
HOLIDAY_CACHE=f'{AUX}/nse_trading_holidays.json'

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


# ------------------------------------------------------------
# NSE OFFICIAL TRADING HOLIDAY CALENDAR
# ------------------------------------------------------------

def load_nse_holiday_calendar():
    calendar={}

    if os.path.exists(HOLIDAY_CACHE):
        try:
            old=json.load(open(HOLIDAY_CACHE,'r',encoding='utf8'))
            for y,info in old.items():
                if not str(y).isdigit():
                    continue
                year=int(y)
                calendar[year]={
                    'holidays':set(
                        datetime.strptime(x,'%Y-%m-%d').date()
                        for x in info.get('holidays',[])
                    ),
                    'special_sessions':set(
                        datetime.strptime(x,'%Y-%m-%d').date()
                        for x in info.get('special_sessions',[])
                    )
                }
        except Exception as e:
            print('WARNING: Could not read NSE holiday cache:',e)

    try:
        r=s.get(
            'https://www.nseindia.com/api/holiday-master?type=trading',
            timeout=30
        )
        r.raise_for_status()
        payload=r.json()
        rows=payload.get('CM',[])
        if not rows:
            raise RuntimeError('NSE holiday API returned no CM calendar')

        current_year=NOW_IST.year
        holidays=set()
        special_sessions=set()

        for row in rows:
            td=str(row.get('tradingDate','')).strip()
            if not td:
                continue

            d=datetime.strptime(td,'%d-%b-%Y').date()
            description=str(row.get('description',''))

            # NSE marks the special Muhurat session with *.
            if '*' in description and d.weekday()==6:
                special_sessions.add(d)
            elif d.weekday()<5:
                holidays.add(d)

        if not holidays and not special_sessions:
            raise RuntimeError('NSE CM holiday calendar was empty')

        calendar[current_year]={
            'holidays':holidays,
            'special_sessions':special_sessions
        }

        json.dump(
            {
                str(year):{
                    'holidays':sorted(
                        d.isoformat() for d in info['holidays']
                    ),
                    'special_sessions':sorted(
                        d.isoformat() for d in info['special_sessions']
                    )
                }
                for year,info in calendar.items()
            },
            open(HOLIDAY_CACHE,'w',encoding='utf8'),
            indent=2
        )

        print('NSE official holiday calendar loaded:',sorted(calendar.keys()))

    except Exception as e:
        print('WARNING: Could not refresh NSE holiday API:',e)

    return calendar


NSE_CALENDAR=load_nse_holiday_calendar()


def is_nse_equity_session(d):
    info=NSE_CALENDAR.get(d.year)

    # For an older year not returned by the current NSE API,
    # retain weekday filtering. Actual NSE download validation
    # still determines whether an exchange file exists.
    if info is None:
        return d.weekday()<5

    if d in info['special_sessions']:
        return True

    return d.weekday()<5 and d not in info['holidays']


def latest_completed_nse_session(now_ist):
    d=now_ist.date()

    if now_ist.hour < 18:
        d-=timedelta(days=1)

    while not is_nse_equity_session(d):
        d-=timedelta(days=1)

    return d


END=latest_completed_nse_session(NOW_IST)
print('Latest completed NSE session:',END)

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
    if is_nse_equity_session(d):
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
all_dates=[d for d in all_dates if is_nse_equity_session(d)]

if len(all_dates)<302:
    raise SystemExit(
        f'Need at least 302 NSE raw sessions for 50 output sessions '
        f'plus full 252-session lookback; found {len(all_dates)}'
    )

dates=all_dates[-50:]


def pr_member(d,member,out):
    if os.path.exists(out) and os.path.getsize(out)>100:
        return True

    try:
        r=s.get(
            f'https://nsearchives.nseindia.com/archives/equities/bhavcopy/pr/PR{d:%d%m%y}.zip',
            timeout=60
        )
        if r.status_code!=200:
            return False

        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            t=next(
                (x for x in z.namelist()
                 if x.lower().endswith(member.lower())),
                None
            )
            if not t:
                return False

            open(out,'wb').write(z.read(t))
            return True

    except Exception:
        return False

m=ix=0
missing_mcap=[]
missing_index=[]

for d in dates:
    if pr_member(
        d,
        f'mcap{d:%d%m%Y}.csv',
        f'{MCAP}/{d}.csv'
    ):
        m+=1
    else:
        missing_mcap.append(d.isoformat())

    time.sleep(.15)

    o=f'{INDEX}/{d}.csv'

    if os.path.exists(o) and os.path.getsize(o)>100:
        ix+=1
    else:
        try:
            r=s.get(
                f'https://nsearchives.nseindia.com/content/indices/ind_close_all_{d:%d%m%Y}.csv',
                timeout=45
            )
            if r.status_code==200 and len(r.content)>1000:
                open(o,'wb').write(r.content)
                ix+=1
            else:
                missing_index.append(d.isoformat())
        except Exception:
            missing_index.append(d.isoformat())

    time.sleep(.12)

print("Missing MCAP:",missing_mcap)
print("Missing INDEX:",missing_index)
print("Market-cap files:",m,"/ 50")
print("Index-close files:",ix,"/ 50")

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

if len(vrows)==50:
    json.dump(
        {'data':vrows},
        open(f'{AUX}/india_vix.json','w',encoding='utf8'),
        indent=2
    )
    print('India VIX from official NSE index-close files:',len(vrows),'rows')
else:
    raise SystemExit(f'Official NSE India VIX coverage incomplete: {len(vrows)}/50')


mp=f'{AUX}/nifty500.csv'

if not os.path.exists(mp) or os.path.getsize(mp)<100:
    try:
        r=s.get(
            'https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv',
            timeout=30
        )
        if r.status_code==200 and len(r.content)>1000:
            open(mp,'wb').write(r.content)
            print('NIFTY500 mapping downloaded')
    except Exception:
        pass

print('Official NSE auxiliary acquisition complete')
