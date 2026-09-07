import json, os, html
d=json.load(open("data/market_intelligence.json"))
rows=d["sessions"]
th=["Session Date","NSE Adv / Dec","A/D Ratio","TRIN","Breakout Follow-Through (%)","Large Cap Adv %","Mid Cap Adv %","Small Cap Adv %","Near 10% 52W High","India VIX","Up / Down 4.5%","Up 20% (5d)","> 20 EMA (%)","> 50 EMA (%)","> 200 EMA (%)"]
# Exact 15-column structure retained. Metrics not yet computed by the engine are explicitly marked unavailable.
body=""
for r in rows:
    vals=[
      r["session_date"],f'{r["advances"]} / {r["declines"]}',r["ad_ratio"] or "N/V",r["trin"] or "N/V",
      "N/V","N/V","N/V","N/V","N/V","N/V",
      f'{r["up_4_5"]} / {r["down_4_5"]}',r["up20_5d"],
      r["above_20_ema"] or "N/V",r["above_50_ema"] or "N/V",r["above_200_ema"] or "N/V"]
    body+="<tr>"+ "".join(f"<td>{html.escape(str(x))}</td>" for x in vals)+"</tr>"
table="<table><thead><tr>"+ "".join(f"<th>{html.escape(x)}</th>" for x in th)+"</tr></thead><tbody>"+body+"</tbody></table>"
latest=rows[-1]
doc=f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NSE All Share Institutional Terminal</title>
<style>
body{{font-family:Inter,Arial,sans-serif;background:#07111f;color:#e8eef7;margin:0;padding:24px}}
.card{{background:#0d1b2d;border:1px solid #24364d;border-radius:16px;padding:20px;margin-bottom:20px}}
h1{{margin:0 0 8px}} .muted{{color:#91a4ba;font-size:13px}}
.wrap{{overflow:auto}} table{{border-collapse:collapse;width:100%;font-size:12px}} th,td{{padding:9px 10px;border-bottom:1px solid #24364d;white-space:nowrap;text-align:right}} th:first-child,td:first-child{{text-align:left}} th{{position:sticky;top:0;background:#12243a}}
</style></head><body>
<div class="card"><h1>NSE All Share — Institutional Market Intelligence</h1>
<div class="muted">Rolling 50 completed NSE sessions • Raw Bhavcopy → calculations → dashboard</div></div>
<div class="card"><h2>Latest Session: {html.escape(latest["session_date"])}</h2>
<p>Advances <b>{latest["advances"]}</b> | Declines <b>{latest["declines"]}</b> | A/D <b>{latest["ad_ratio"]}</b> | TRIN <b>{latest["trin"]}</b></p>
<p>4.5% Up/Down <b>{latest["up_4_5"]}/{latest["down_4_5"]}</b> | +20% in 5D <b>{latest["up20_5d"]}</b></p></div>
<div class="card"><h2>50-Session Ledger</h2><div class="wrap">{table}</div></div>
<div class="card"><h2>Data Integrity</h2><p class="muted">Raw files are sourced by the downloader. Calculated fields are generated from security-level observations. Metrics not yet supported by the current raw acquisition layer are deliberately shown as N/V rather than fabricated.</p></div>
</body></html>"""
os.makedirs("output",exist_ok=True)
open("output/NSE_All_Share_Institutional_Terminal.html","w").write(doc)
print("Generated output/NSE_All_Share_Institutional_Terminal.html")
