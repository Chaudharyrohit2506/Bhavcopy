import glob,os,json
import numpy as np,pandas as pd

RAW='data/raw'
AUX='data/aux'
OUT='data/market_intelligence.json'

def cols(df):
    df.columns=[str(c).replace('\ufeff','').strip().upper() for c in df.columns]
    return df

def pick(df,names):
    return next((n for n in names if n in df.columns),None)

def rawfile(p):
    try:
        df=cols(pd.read_csv(p,low_memory=False,encoding='utf-8-sig'))
    except Exception:
        return None
    sy=pick(df,['SYMBOL','TCKRSYMB','SECURITY'])
    cl=pick(df,['CLOSE_PRICE','CLOSE','CLSPRIC','PRICCLSGPRIC','LAST_PRICE'])
    pc=pick(df,['PREV_CLOSE','PRV_CLPR','PRVSCLSGPRIC'])
    av=pick(df,['AVG_PRICE','VWAP','AVERAGE_PRICE'])
    hi=pick(df,['HIGH_PRICE','HIGH','HGHPRIC','HIGH_PRICE_VALUE'])
    vo=pick(df,['TTL_TRD_QNTY','TOTTRDQTY','TOTALTRADGVOLUME','VOLUME'])
    se=pick(df,['SERIES','SCTYSRS'])
    if not sy or not cl:
        return None
    x=pd.DataFrame({
        'SYMBOL':df[sy].astype(str).str.strip().str.upper(),
        'CLOSE':pd.to_numeric(df[cl],errors='coerce'),
        'PREV_CLOSE':pd.to_numeric(df[pc],errors='coerce') if pc else np.nan,
        'AVG_PRICE':pd.to_numeric(df[av],errors='coerce') if av else np.nan,
        'HIGH':pd.to_numeric(df[hi],errors='coerce') if hi else pd.to_numeric(df[cl],errors='coerce'),
        'VOLUME':pd.to_numeric(df[vo],errors='coerce') if vo else 0
    })
    if se:
        x=x[df[se].astype(str).str.strip().str.upper().isin(['EQ','BE','BZ'])].copy()
    return x[x.CLOSE.notna()&x.SYMBOL.ne('')].copy()

frames=[]
for p in sorted(glob.glob(f'{RAW}/*.csv')):
    x=rawfile(p)
    if x is not None:
        try:
            x['DATE']=pd.Timestamp(os.path.basename(p)[:10])
        except Exception:
            continue
        frames.append(x)

if not frames:
    raise SystemExit('No valid NSE raw files found')

allx=pd.concat(frames,ignore_index=True).drop_duplicates(['DATE','SYMBOL'],keep='last').sort_values(['DATE','SYMBOL'])
all_dates=np.array(sorted(allx.DATE.unique()))
dates=all_dates[-50:]
if len(dates)!=50:
    raise SystemExit(f'Expected exactly 50 sessions, got {len(dates)}')

daily={d:g for d,g in allx.groupby('DATE',sort=False)}

def mcap(d):
    p=f'{AUX}/mcap/{pd.Timestamp(d).date()}.csv'
    if not os.path.exists(p):
        return None
    try:
        x=cols(pd.read_csv(p,low_memory=False,encoding='utf-8-sig'))
    except Exception:
        return None
    sy=pick(x,['SYMBOL','TCKRSYMB','SECURITY'])
    mc=next((c for c in x.columns if ('MARKET' in c and 'CAP' in c) or 'MCAP' in c or 'MKT_CAP' in c),None)
    if not sy or not mc:
        return None
    z=pd.DataFrame({
        'SYMBOL':x[sy].astype(str).str.strip().str.upper(),
        'MCAP':pd.to_numeric(x[mc],errors='coerce')
    }).dropna()
    if z.MCAP.median()>1e7:
        z.MCAP/=1e7
    return z.drop_duplicates('SYMBOL')

def vix():
    p=f'{AUX}/india_vix.json'
    if not os.path.exists(p):
        return {}
    try:
        o=json.load(open(p,encoding='utf8'))
    except Exception:
        return {}
    a=o.get('data',o) if isinstance(o,dict) else o
    out={}
    if isinstance(a,list):
        for r in a:
            if not isinstance(r,dict):
                continue
            dt=r.get('DATE') or r.get('EOD_TIMESTAMP') or r.get('DATE1') or r.get('TIMESTAMP')
            cl=r.get('CLOSE') or r.get('Closing Index Value')
            if dt is not None and cl is not None:
                try:
                    out[str(pd.to_datetime(dt,yearfirst=True).date())]=float(str(cl).replace(',',''))
                except Exception:
                    pass
    return out

def industry():
    p=f'{AUX}/nifty500.csv'
    if not os.path.exists(p):
        return {}
    try:
        x=cols(pd.read_csv(p,low_memory=False,encoding='utf-8-sig'))
    except Exception:
        return {}
    sy=pick(x,['SYMBOL'])
    ind=pick(x,['INDUSTRY'])
    return dict(zip(x[sy].astype(str).str.strip().str.upper(),x[ind].astype(str).str.strip())) if sy and ind else {}

def sector(i):
    z=str(i).upper()
    mp=[
        ('Financials',['FINANCIAL','BANK','INSURANCE','NBFC']),
        ('Information Technology',['IT','SOFTWARE']),
        ('Healthcare',['PHARMA','HEALTHCARE']),
        ('Energy',['ENERGY','OIL','GAS']),
        ('Materials',['METALS','CEMENT','CHEMICAL','FERTIL']),
        ('Industrials',['INDUSTRIAL','CONSTRUCTION','CAPITAL GOODS']),
        ('Consumer',['CONSUMER','FMCG','RETAIL']),
        ('Automobile',['AUTOMOBILE','AUTO']),
        ('Telecom',['TELECOM']),
        ('Media',['MEDIA']),
        ('Textiles',['TEXTILE']),
        ('Realty',['REALTY']),
        ('Services',['SERVICES']),
        ('Utilities',['POWER','UTILITY'])
    ]
    for s,k in mp:
        if any(q in z for q in k):
            return s
    return 'Other'

def idxfile(d):
    p=f'{AUX}/indices/{pd.Timestamp(d).date()}.csv'
    if not os.path.exists(p):
        return {}
    try:
        x=cols(pd.read_csv(p,low_memory=False,encoding='utf-8-sig'))
    except Exception:
        return {}
    n=pick(x,['INDEX_NAME','INDEX NAME','INDEX','INDEXNAME'])
    c=pick(x,['CLOSE','CLOSE_PRICE','CLOSING_INDEX_VALUE','CLOSING INDEX VALUE','CLOSING_INDEX_VALUE'])
    if not n or not c:
        return {}
    out={}
    for _,r in x.iterrows():
        try:
            out[str(r[n]).strip().upper()]=float(str(r[c]).replace(',',''))
        except Exception:
            pass
    return out

vx=vix()
imap=industry()
ix={d:idxfile(d) for d in dates}

aliases={
    'NIFTY AUTO':'Automobile',
    'NIFTY BANK':'Financials',
    'NIFTY FINANCIAL SERVICES':'Financials',
    'NIFTY FMCG':'Consumer',
    'NIFTY IT':'Information Technology',
    'NIFTY MEDIA':'Media',
    'NIFTY METAL':'Materials',
    'NIFTY PHARMA':'Healthcare',
    'NIFTY PSU BANK':'Financials',
    'NIFTY PRIVATE BANK':'Financials',
    'NIFTY REALTY':'Realty',
    'NIFTY OIL AND GAS':'Energy',
    'NIFTY HEALTHCARE':'Healthcare',
    'NIFTY CONSUMER DURABLES':'Consumer',
    'NIFTY TELECOM':'Telecom',
    'NIFTY CONSUMER SERVICES':'Services'
}

def sec40(i):
    if i<40:
        return {}
    a,b=ix.get(dates[i-40],{}),ix.get(dates[i],{})
    o={}
    for name,sec in aliases.items():
        x=a.get(name)
        y=b.get(name)
        if x is None:
            for k,v in a.items():
                if name in k:
                    x=v
                    break
        if y is None:
            for k,v in b.items():
                if name in k:
                    y=v
                    break
        if x and y:
            o[sec]=round((y/x-1)*100,2)
    return o

close_p=allx.pivot(index='DATE',columns='SYMBOL',values='CLOSE').sort_index()
avg_p=allx.pivot(index='DATE',columns='SYMBOL',values='AVG_PRICE').sort_index()
ema20=close_p.ewm(span=20,adjust=False).mean()
ema50=close_p.ewm(span=50,adjust=False).mean()
ema200=close_p.ewm(span=200,adjust=False).mean()
high252=close_p.rolling(252,min_periods=20).max()
prev_close=close_p.shift(1)
prev_avg=avg_p.shift(1)

mcaps={d:mcap(d) for d in dates}
cap_rank={}
for d,mc in mcaps.items():
    cap_rank[d]=(dict(zip(mc.sort_values('MCAP',ascending=False).SYMBOL,range(1,len(mc)+1))) if mc is not None and len(mc)>=250 else None)

rows=[]
for i,d in enumerate(dates):
    c=daily[d]

    # NSE's historical A/D methodology is based on average price.
    # Use AVG_PRICE when available; fall back to CLOSE only where AVG_PRICE is unavailable.
    breadth_base=c.SYMBOL.map(prev_avg.loc[d]) if i else c.PREV_CLOSE
    breadth_price=c.AVG_PRICE.where(c.AVG_PRICE.notna(),c.CLOSE)
    breadth_ret=breadth_price/breadth_base-1
    breadth_valid=breadth_ret.replace([np.inf,-np.inf],np.nan).notna()
    br=breadth_ret[breadth_valid]

    adv=int((br>0).sum())
    dec=int((br<0).sum())
    un=int((br==0).sum())
    adr=adv/dec if dec else np.nan

    # TRIN uses the same breadth classification and corresponding traded volume.
    vv=c.VOLUME.fillna(0)
    uv=float(vv[breadth_ret>0].sum())
    dv=float(vv[breadth_ret<0].sum())
    tr=adr/(uv/dv) if adr and uv and dv else np.nan

    # Price-momentum metrics remain close-to-close metrics.
    base=c.SYMBOL.map(prev_close.loc[d]) if i else c.PREV_CLOSE
    ret=c.CLOSE/base-1
    valid=ret.replace([np.inf,-np.inf],np.nan).notna()
    rv=ret[valid]

    up45=int((rv>=.045).sum())
    dn45=int((rv<=-.045).sum())
    up20=0
    if i>=5:
        c5=c.SYMBOL.map(close_p.loc[dates[i-5]])
        up20=int(((c.CLOSE/c5-1)>=.20).sum())

    px=close_p.loc[d]
    e20v=ema20.loc[d]
    e50v=ema50.loc[d]
    e200v=ema200.loc[d]
    m20=px.notna()&e20v.notna()
    m50=px.notna()&e50v.notna()
    m200=px.notna()&e200v.notna()
    a20=round(float((px[m20]>e20v[m20]).mean()*100),2) if m20.any() else None
    a50=round(float((px[m50]>e50v[m50]).mean()*100),2) if m50.any() else None
    a200=round(float((px[m200]>e200v[m200]).mean()*100),2) if m200.any() else None

    large=mid=small=None
    rk=cap_rank.get(d)
    if rk is not None:
        rr=c.SYMBOL.map(rk)
        for lab,mask in [
            ('large',(rr<=100)),
            ('mid',(rr>=101)&(rr<=250)),
            ('small',(rr>=251)&(rr<=500))
        ]:
            if mask.sum():
                val=round(float((ret[mask]>0).sum()/mask.sum()*100),2)
                if lab=='large': large=val
                elif lab=='mid': mid=val
                else: small=val

    h=high252.loc[d]
    nm=px.notna()&h.notna()
    near=int((px[nm]>=.9*h[nm]).sum()) if nm.any() else 0

    rows.append({
        'session_date':str(pd.Timestamp(d).date()),
        'advances':adv,
        'declines':dec,
        'unchanged':un,
        'ad_ratio':None if not np.isfinite(adr) else round(float(adr),4),
        'trin':None if not np.isfinite(tr) else round(float(tr),4),
        'up_4_5':up45,
        'down_4_5':dn45,
        'up20_5d':up20,
        'universe':len(c),
        'ema_universe':int(m20.sum()),
        'above_20_ema':a20,
        'above_50_ema':a50,
        'above_200_ema':a200,
        'large_cap_adv_pct':large,
        'mid_cap_adv_pct':mid,
        'small_cap_adv_pct':small,
        'near_10pct_52w_high':near,
        'near_10pct_52w_high_pct':round(near/len(c)*100,2) if len(c) else None,
        'india_vix':vx.get(str(pd.Timestamp(d).date())),
        'breakout_follow_through_pct':None,
        'sector_40d_returns':sec40(i),
        'sector_27pct_return_penetration':{},
        'sector_55d_high_penetration':{},
        'ad_methodology':'NSE average-price methodology'
    })

# T-DAY BREAKOUT FOLLOW-THROUGH
# A stock is a T-day breakout when its T-session HIGH exceeds the
# highest HIGH of the preceding 55 completed sessions.
# Follow-through is confirmed on T itself when the CLOSE also finishes
# above that same prior-55-session high. No T+1/T+2 data is used.
high_p=allx.pivot(index='DATE',columns='SYMBOL',values='HIGH').sort_index()
prior55_high=high_p.shift(1).rolling(55,min_periods=55).max()
t_day_cross=high_p>prior55_high
t_day_follow=close_p>prior55_high

for r,d in zip(rows,dates):
    pos=int(np.searchsorted(all_dates,d))
    if pos<55:
        r['breakout_follow_through_pct']=None
        continue

    cross=t_day_cross.iloc[pos]
    follow=t_day_follow.iloc[pos]
    valid=cross.notna()&follow.notna()

    denom=int(cross[valid].sum())
    numer=int((cross[valid]&follow[valid]).sum())

    # A session with zero T-day breakouts is a valid 0.00%, not blank.
    r['breakout_follow_through_pct']=round(numer/denom*100,2) if denom else 0.0

# SECTOR STOCK-CONCENTRATION METRICS
# 1) 27% Return Percentage: share of stocks in each sector with a
#    >= +27% return over the latest 40 completed sessions.
# 2) 55-Day High Penetration: share of stocks in each sector whose
#    latest-session HIGH reaches at least 97% of the highest HIGH in
#    the preceding 55 completed sessions.
sector_map=pd.Series({s:sector(imap.get(s,'')) for s in close_p.columns})
pos=len(all_dates)-1
if pos>=55:
    valid_symbols=close_p.columns.intersection(sector_map.index)

    # 40-session stock return threshold: close(T) vs close(T-40).
    px40=close_p.iloc[pos]
    old40=close_p.iloc[pos-40] if pos>=40 else pd.Series(index=close_p.columns,dtype=float)
    ret40=(px40/old40-1)*100
    qualifies27=ret40>=27.0
    valid27=ret40.notna() & sector_map.notna()
    pen27={}
    for sec,g in qualifies27[valid27].groupby(sector_map[valid27]):
        if str(sec)!='Other':
            denom=int(valid27.groupby(sector_map[valid27]).sum().get(sec,0))
            numer=int(g.sum())
            pen27[str(sec)]=round(numer/denom*100,2) if denom else 0.0
    rows[-1]['sector_27pct_return_penetration']=pen27

    # Relaxed 55-session high threshold: latest HIGH >= 97% of
    # preceding 55-session highest HIGH.
    pxh=high_p.iloc[pos]
    prior55_high_sector=high_p.iloc[pos-55:pos].max()
    threshold55=prior55_high_sector*0.97
    qualifies55=pxh>=threshold55
    valid55=qualifies55.notna() & prior55_high_sector.notna() & sector_map.notna()
    pen55={}
    for sec,g in qualifies55[valid55].groupby(sector_map[valid55]):
        if str(sec)!='Other':
            denom=int(valid55.groupby(sector_map[valid55]).sum().get(sec,0))
            numer=int(g.sum())
            pen55[str(sec)]=round(numer/denom*100,2) if denom else 0.0
    rows[-1]['sector_55d_high_penetration']=pen55

rv=[]
latest=dates[-1]
mc=mcaps.get(latest)
if mc is not None:
    mcmap=mc.set_index('SYMBOL')['MCAP']
    eligible=set(mcmap[(mcmap>300)&(mcmap<31000)].index)
    hist=allx[allx.SYMBOL.isin(eligible)].sort_values(['SYMBOL','DATE'])

    for sym,g in hist.groupby('SYMBOL',sort=False):
        g=g[g.DATE<=latest]
        if len(g)<25:
            continue

        z=g.tail(25)
        base=z.head(20).VOLUME.mean()
        last=z.tail(5).VOLUME.mean()

        if not np.isfinite(base) or base<=0:
            continue

        p=float(z.CLOSE.iloc[-1])
        old=float(g.tail(41).CLOSE.iloc[0]) if len(g)>=41 else np.nan

        rv.append({
            'symbol':str(sym),
            'weekly_rvol_pct':round(last/base*100,2),
            'rvol_20sma_volume':round(float(base),2),
            'rvol_5sma_volume':round(float(last),2),
            'last_40d_return_pct':round((p/old-1)*100,2) if np.isfinite(old) and old else None,
            'current_price':round(p,2),
            'market_cap_cr':round(float(mcmap[sym]),2),
            'sector':sector(imap.get(str(sym),''))
        })

rv=sorted(rv,key=lambda x:x['weekly_rvol_pct'],reverse=True)[:50]

s27=sorted(
    [{'sector':k,'return_27pct_penetration':v} for k,v in rows[-1]['sector_27pct_return_penetration'].items()],
    key=lambda x:x['return_27pct_penetration'],
    reverse=True
)
s55=sorted(
    [{'sector':k,'penetration_pct':v} for k,v in rows[-1]['sector_55d_high_penetration'].items()],
    key=lambda x:x['penetration_pct'],
    reverse=True
)

res={
    'sessions':rows,
    'latest':rows[-1],
    'high_rvol_stocks':rv,
    'sector_27pct_return_ranking':s27,
    'sector_55d_high_ranking':s55,
    'data_coverage':{
        'raw_sessions':50,
        'mcap_files':sum(m is not None for m in mcaps.values()),
        'index_files':sum(bool(x) for x in ix.values()),
        'vix_rows':len(vx),
        'nifty500_sector_map':bool(imap),
        'ad_methodology':'NSE average-price methodology from official NSE bhavcopy fields'
    }
}

os.makedirs('data',exist_ok=True)
json.dump(res,open(OUT,'w',encoding='utf8'),indent=2)

print('SUCCESS:',len(rows),'sessions calculated')
print(
    'Latest:',rows[-1]['session_date'],
    'A/D',rows[-1]['advances'],'/',rows[-1]['declines'],
    'VIX',rows[-1]['india_vix'],
    'INDEX_FILES',res['data_coverage']['index_files'],
    'VIX_ROWS',res['data_coverage']['vix_rows'],
    'HIGH_RVOL',len(rv)
)
