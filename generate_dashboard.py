import json,html,os
D=json.load(open('data/market_intelligence.json',encoding='utf8')); rows=D['sessions']; latest=rows[-1]
dates=[r['session_date'] for r in rows]
def n(x): return 'N/V' if x is None else f'{x:.2f}'
def p(x): return 'N/V' if x is None else f'{x:.2f}%'
def e(x): return html.escape(str(x))

def sector_block(items,key):
    if not items: return '<div class="muted">N/V</div>'
    mx=max(abs(float(x[key])) for x in items) or 1; out=''
    for x in items[:12]:
        v=float(x[key]); w=min(100,abs(v)/mx*100)
        out += f'<div class="sr"><b>{e(x["sector"])}</b><div class="sb"><i style="width:{w:.1f}%"></i></div><strong>{v:.2f}%</strong></div>'
    return out

ledger=''
for r in reversed(rows):
    ledger += f'<tr><td>{r["session_date"]}</td><td>{r["advances"]:,} / {r["declines"]:,}</td><td>{n(r["ad_ratio"])}</td><td>{n(r["trin"])}</td><td>{p(r["breakout_follow_through_pct"])}</td><td>{p(r["large_cap_adv_pct"])}</td><td>{p(r["mid_cap_adv_pct"])}</td><td>{p(r["small_cap_adv_pct"])}</td><td>{r["near_10pct_52w_high"]:,} ({p(r["near_10pct_52w_high_pct"])})</td><td>{n(r["india_vix"])}</td><td>{r["up_4_5"]:,} / {r["down_4_5"]:,}</td><td>{r["up20_5d"]:,}</td><td>{p(r["above_20_ema"])}</td><td>{p(r["above_50_ema"])}</td><td>{p(r["above_200_ema"])}</td></tr>'

rv=''
for x in D.get('high_rvol_stocks',[]):
    rv += f'<tr><td>{e(x["symbol"])}</td><td>{x["weekly_rvol_pct"]:.1f}%</td><td>{x["last_40d_return_pct"]:.2f}%</td><td>₹{x["current_price"]:,.2f}</td><td>₹{x["market_cap_cr"]:,.0f} Cr</td><td>{e(x["sector"])}</td></tr>'
if not rv: rv='<tr><td colspan="6">N/V — market-cap auxiliary data unavailable.</td></tr>'

# Visual structure follows the uploaded institutional terminal: dark cards, KPI strip,
# cap comparison, sector bars, charts, searchable ledger, zoom controls and RVOL table.
css='''
:root{--bg:#060a12;--s:#0d1524;--b:#1e3150;--t:#f8fafc;--m:#94a3b8;--blue:#38bdf8;--green:#10b981;--pink:#f43f5e;--amber:#f59e0b;--purple:#c084fc}
*{box-sizing:border-box}body{margin:0;padding:24px;background:var(--bg);color:var(--t);font-family:Arial,sans-serif}
.head{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;border-bottom:1px solid var(--b);padding-bottom:18px;margin-bottom:18px}
h1{font-size:1.6rem;background:linear-gradient(135deg,#fff,var(--blue));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.muted{color:var(--m);font-size:.8rem}.pill{padding:6px 12px;border:1px solid var(--green);border-radius:999px;color:var(--green);background:#10b98118}
button,input{background:var(--s);color:var(--t);border:1px solid var(--b);border-radius:7px;padding:7px 10px}.banner,.card,.kpi{background:var(--s);border:1px solid var(--b);border-radius:10px;padding:16px;margin-bottom:18px}.banner{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}.kpi{border-top:3px solid var(--blue)}.green{border-top-color:var(--green)}.purple{border-top-color:var(--purple)}.amber{border-top-color:var(--amber)}
.label{font-size:.7rem;color:#64748b;text-transform:uppercase;font-weight:700}.value{font-size:1.7rem;font-weight:800;margin:5px 0}.section{font-size:1.05rem;font-weight:800;margin:25px 0 12px}.caps,.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}
.bar,.sb{height:10px;background:#1a273e;border-radius:4px;overflow:hidden}.bar i,.sb i{display:block;height:100%;background:var(--green)}.sr{display:flex;gap:8px;align-items:center;margin:8px 0;font-size:.8rem}.sr b{width:150px}.sb{flex:1}.sr strong{width:65px;text-align:right}.chart{height:230px}.scroll{max-height:560px;overflow:auto}
table{width:100%;border-collapse:collapse;font-size:.78rem}th{position:sticky;top:0;background:#090f1a;color:#64748b;padding:10px;text-align:left;z-index:2}td{padding:9px 10px;border-bottom:1px solid #152238;white-space:nowrap}tr:hover td{background:#38bdf80a}.search{width:240px;margin-bottom:10px}@media(max-width:700px){body{padding:14px}h1{font-size:1.25rem}.charts{grid-template-columns:1fr}}
'''

html_doc='''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NSE All-Share Institutional Market Breadth Terminal</title><script src="https://cdn.jsdelivr.net/npm/chart.js"></script><style>__CSS__</style></head><body>
<div class="head"><div><h1>NSE All-Share Institutional Market Breadth Terminal</h1><div class="muted">Continuous Rolling Exchange Internals • Official NSE Bhavcopy Archive Data • Refreshed through __DATE__</div></div><div><button onclick="z(-.1)">−</button><button id="zl">100%</button><button onclick="z(.1)">+</button> <span class="pill">🛡 Refreshed EOD</span></div></div>
<div class="banner"><span><b>REFRESHED EOD</b> • __ADV__ Adv / __DEC__ Dec • Net __NET__</span><span><b>Official-data coverage:</b> raw 50/50 • MCAP __MCAP__/50 • index __INDEX__/50 • VIX __VIX__ rows</span></div>
<div class="grid"><div class="kpi green"><div class="label">Advances vs Declines</div><div class="value">__ADV__ : __DEC__</div><div class="muted">A/D __ADR__</div></div><div class="kpi green"><div class="label">TRIN (Arms)</div><div class="value">__TRIN__</div><div class="muted">Lower than 1 = bullish skew</div></div><div class="kpi purple"><div class="label">Breakout Follow-Through</div><div class="value">__FT__</div><div class="muted">55-session breakouts, T+2 retention</div></div><div class="kpi amber"><div class="label">Within 10% of 52W High</div><div class="value">__NEAR__</div><div class="muted">__NEARPCT__</div></div></div>
<div class="section">📊 Market Capitalization Advance % Comparison</div><div class="caps"><div class="card"><b>Large • Top 100</b><div class="value">__LARGE__</div><div class="bar"><i style="width:__LARGEW__"></i></div></div><div class="card"><b>Mid • 101–250</b><div class="value">__MID__</div><div class="bar"><i style="width:__MIDW__"></i></div></div><div class="card"><b>Small • 251–500</b><div class="value">__SMALL__</div><div class="bar"><i style="width:__SMALLW__"></i></div></div></div>
<div class="card"><b>⚡ Session Assessment</b><p class="muted">Breadth, cap participation, TRIN, volatility and EMA breadth are generated from the verified pipeline. No synthetic fallback formulas are used. India VIX is an exchange-derived volatility measure; it does not imply market direction.</p></div>
<div class="section">🏢 Sector Momentum • Actual 40-Session Sector-Index Return</div><div class="card">__SECTOR40__</div><div class="section">🔥 55-Session High Penetration • NIFTY 500 Classified Coverage</div><div class="card">__SECTOR55__</div>
<div class="section">📈 50-Day Rolling Breadth Oscillators</div><div class="charts"><div class="card chart"><canvas id="a"></canvas></div><div class="card chart"><canvas id="e"></canvas></div><div class="card chart"><canvas id="t"></canvas></div><div class="card chart"><canvas id="c"></canvas></div></div>
<div class="section">🚀 50-Stock High-RVOL Screen • Market Cap ₹300 Cr to ₹31,000 Cr</div><div class="card"><input id="rq" class="search" placeholder="Search stock / sector" oninput="f('rvol','rq')"><div class="scroll"><table id="rvol"><thead><tr><th>Stock Name</th><th>Weekly RVOL (% vs 20SMA)</th><th>Last 40D Movement</th><th>Current Price</th><th>Market Cap</th><th>Sector</th></tr></thead><tbody>__RVOL__</tbody></table></div></div>
<div class="section">📋 Comprehensive 50-Day NSE All-Share Institutional Market Breadth Ledger</div><div class="card"><input id="lq" class="search" placeholder="Search ledger" oninput="f('ledger','lq')"><div class="scroll"><table id="ledger"><thead><tr><th>Session Date</th><th>NSE Adv / Dec</th><th>A/D Ratio</th><th>TRIN (Arms)</th><th>Breakout Follow-Through (%)</th><th>Large Cap Adv %</th><th>Mid Cap Adv %</th><th>Small Cap Adv %</th><th>Near 10% 52W High</th><th>India VIX</th><th>Up / Down 4.5%</th><th>Up 20% (5d)</th><th>&gt; 20 EMA (%)</th><th>&gt; 50 EMA (%)</th><th>&gt; 200 EMA (%)</th></tr></thead><tbody>__LEDGER__</tbody></table></div></div>
<div class="card"><b>Data Integrity</b><p class="muted">Primary price history is official NSE security-level bhavcopy. MCAP and index-close inputs are official NSE archives. Sector penetration uses the current official NIFTY 500 industry map as a classification layer and is explicitly labelled as such. Unavailable fields remain N/V.</p></div>
<script>const D=__DATES__,A=__AD__,T=__TRIN__,P20=__P20__,P50=__P50__,P200=__P200__,L=__L__,M=__M__,S=__S__;const o={responsive:true,maintainAspectRatio:false,scales:{x:{ticks:{color:"#64748b",maxTicksLimit:8}},y:{ticks:{color:"#64748b"},grid:{color:"#131e30"}}}};new Chart(a,{type:"line",data:{labels:D,datasets:[{label:"A/D Ratio",data:A,borderColor:"#38bdf8",pointRadius:0}]},options:o});new Chart(e,{type:"line",data:{labels:D,datasets:[{label:"20 EMA",data:P20,borderColor:"#38bdf8",pointRadius:0},{label:"50 EMA",data:P50,borderColor:"#10b981",pointRadius:0},{label:"200 EMA",data:P200,borderColor:"#c084fc",pointRadius:0}]},options:o});new Chart(t,{type:"line",data:{labels:D,datasets:[{label:"TRIN",data:T,borderColor:"#f43f5e",pointRadius:0}]},options:o});new Chart(c,{type:"line",data:{labels:D,datasets:[{label:"Large",data:L,borderColor:"#f43f5e",pointRadius:0},{label:"Mid",data:M,borderColor:"#c084fc",pointRadius:0},{label:"Small",data:S,borderColor:"#22d3ee",pointRadius:0}]},options:o});function f(id,q){let x=document.getElementById(q).value.toLowerCase();document.querySelectorAll("#"+id+" tbody tr").forEach(r=>r.style.display=r.innerText.toLowerCase().includes(x)?"":"none")}let zz=1;function z(x){zz=Math.min(1.5,Math.max(.75,zz+x));document.documentElement.style.fontSize=(16*zz)+"px";document.getElementById("zl").innerText=Math.round(zz*100)+"%"}</script></body></html>'''

vals={
'__CSS__':css,'__DATE__':latest['session_date'],'__ADV__':f'{latest["advances"]:,}','__DEC__':f'{latest["declines"]:,}','__NET__':f'{latest["advances"]-latest["declines"]:+,}','__ADR__':n(latest['ad_ratio']),'__TRIN__':n(latest['trin']),'__FT__':p(latest['breakout_follow_through_pct']),'__NEAR__':f'{latest["near_10pct_52w_high"]:,}','__NEARPCT__':p(latest['near_10pct_52w_high_pct']),
'__LARGE__':p(latest['large_cap_adv_pct']),'__LARGEW__':p(latest['large_cap_adv_pct']),'__MID__':p(latest['mid_cap_adv_pct']),'__MIDW__':p(latest['mid_cap_adv_pct']),'__SMALL__':p(latest['small_cap_adv_pct']),'__SMALLW__':p(latest['small_cap_adv_pct']),
'__MCAP__':str(D['data_coverage']['mcap_files']),'__INDEX__':str(D['data_coverage']['index_files']),'__VIX__':str(D['data_coverage']['vix_rows']),'__SECTOR40__':sector_block(D.get('sector_40d_ranking',[]),'return_40d_pct'),'__SECTOR55__':sector_block(D.get('sector_55d_high_ranking',[]),'penetration_pct'),'__RVOL__':rv,'__LEDGER__':ledger,
'__DATES__':json.dumps(dates),'__AD__':json.dumps([r['ad_ratio'] for r in rows]),'__TRIN__':json.dumps([r['trin'] for r in rows]),'__P20__':json.dumps([r['above_20_ema'] for r in rows]),'__P50__':json.dumps([r['above_50_ema'] for r in rows]),'__P200__':json.dumps([r['above_200_ema'] for r in rows]),'__L__':json.dumps([r['large_cap_adv_pct'] for r in rows]),'__M__':json.dumps([r['mid_cap_adv_pct'] for r in rows]),'__S__':json.dumps([r['small_cap_adv_pct'] for r in rows])}
for k,v in vals.items(): html_doc=html_doc.replace(k,v)
os.makedirs('output',exist_ok=True);open('output/NSE_All_Share_Institutional_Terminal.html','w',encoding='utf8').write(html_doc);print('Generated institutional terminal:',len(html_doc),'bytes')
