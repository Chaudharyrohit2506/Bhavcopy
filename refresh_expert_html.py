from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import re

DATA = Path("data/market_intelligence.json")
HTML = Path("output/NSE_All_Share_Institutional_Terminal.html")
MARKER = re.compile(r"<!-- NSE_HTML_REFRESH: .*? -->", re.S)

if not DATA.exists():
    raise SystemExit("FAIL: data/market_intelligence.json not found")
if not HTML.exists():
    raise SystemExit("FAIL: output/NSE_All_Share_Institutional_Terminal.html not found")

data = json.loads(DATA.read_text(encoding="utf-8"))
rows = data.get("sessions", [])
coverage = data.get("data_coverage", {})
latest = rows[-1] if rows else None

if len(rows) != 50:
    raise SystemExit(f"FAIL: expected 50 sessions, got {len(rows)}")

required_coverage = {
    "raw_sessions": 50,
    "mcap_files": 50,
    "index_files": 50,
    "vix_rows": 50,
}
for key, expected in required_coverage.items():
    actual = coverage.get(key)
    if actual != expected:
        raise SystemExit(f"FAIL: {key} coverage is {actual}, expected {expected}")

if not latest:
    raise SystemExit("FAIL: no latest session")
if latest.get("session_date") is None:
    raise SystemExit("FAIL: latest session date missing")

if latest.get("breakout_follow_through_pct") is None:
    raise SystemExit("FAIL: latest breakout follow-through is missing")

html = HTML.read_text(encoding="utf-8")

# Safety checks: the 8 AM job must never overwrite the expert dashboard
# with an older/basic template.
for required in (
    "Expert Market View",
    "Exact 15-column structure",
    "T-day HIGH breakout",
    "T-day CLOSE confirmation",
):
    if required not in html:
        raise SystemExit(f"FAIL: expert dashboard signature missing: {required}")

now = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S IST")
marker = (
    f'<!-- NSE_HTML_REFRESH: generated {now} | '
    f'latest verified session {latest["session_date"]} | '
    f'50-session coverage validated -->'
)

html = MARKER.sub("", html).rstrip()
html = html.replace("</body>", marker + "\n</body>", 1)

HTML.write_text(html + "\n", encoding="utf-8")

print("SUCCESS: Expert HTML refresh validated")
print(f"Latest verified NSE session: {latest['session_date']}")
print(f"50-session coverage: PASS")
print(f"MCAP/Index/VIX coverage: 50/50/50")
print(f"Breakout Follow-Through: {latest['breakout_follow_through_pct']}%")
print(f"HTML timestamp: {now}")
