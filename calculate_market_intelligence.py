import glob
import os
import json
import numpy as np
import pandas as pd

RAW = "data/raw"
OUT = "data/market_intelligence.json"


def normalise_columns(df):
    df.columns = [
        str(c).replace("\ufeff", "").strip().upper()
        for c in df.columns
    ]
    return df


def first_existing(df, names):
    for name in names:
        if name in df.columns:
            return name
    return None


def read_file(path):
    try:
        df = pd.read_csv(
            path,
            low_memory=False,
            encoding="utf-8-sig"
        )
    except Exception as e:
        print("READ ERROR:", path, str(e))
        return None

    df = normalise_columns(df)

    # NSE legacy/full bhavcopy + current/UDiFF aliases
    symbol_col = first_existing(df, [
        "SYMBOL",
        "TCKRSYMB",
        "SECURITY",
        "FININSTRMNT"
    ])

    series_col = first_existing(df, [
        "SERIES",
        "SCTYSRS",
        "SCTY_SERIES"
    ])

    close_col = first_existing(df, [
        "CLOSE_PRICE",
        "CLOSE",
        "CLSPRIC",
        "PRICCLSGPRIC",
        "LAST_PRICE"
    ])

    prev_col = first_existing(df, [
        "PREV_CLOSE",
        "PRV_CLPR",
        "PRVSCLSGPRIC"
    ])

    volume_col = first_existing(df, [
        "TTL_TRD_QNTY",
        "TOTTRDQTY",
        "TOTALTRADGVOLUME",
        "VOLUME",
        "TtlTradgVol"
    ])

    open_col = first_existing(df, [
        "OPEN_PRICE",
        "OPEN",
        "OPNPRIC"
    ])

    high_col = first_existing(df, [
        "HIGH_PRICE",
        "HIGH",
        "HGHPRIC"
    ])

    low_col = first_existing(df, [
        "LOW_PRICE",
        "LOW",
        "LWPRIC"
    ])

    if symbol_col is None or close_col is None:
        print(
            "SKIP INVALID:",
            os.path.basename(path),
            "columns:",
            list(df.columns)[:25]
        )
        return None

    out = pd.DataFrame()

    out["SYMBOL"] = (
        df[symbol_col]
        .astype(str)
        .str.strip()
    )

    out["CLOSE"] = pd.to_numeric(
        df[close_col],
        errors="coerce"
    )

    if prev_col:
        out["PREV_CLOSE"] = pd.to_numeric(
            df[prev_col],
            errors="coerce"
        )
    else:
        out["PREV_CLOSE"] = np.nan

    if volume_col:
        out["VOLUME"] = pd.to_numeric(
            df[volume_col],
            errors="coerce"
        )
    else:
        out["VOLUME"] = 0

    if open_col:
        out["OPEN"] = pd.to_numeric(
            df[open_col],
            errors="coerce"
        )

    if high_col:
        out["HIGH"] = pd.to_numeric(
            df[high_col],
            errors="coerce"
        )

    if low_col:
        out["LOW"] = pd.to_numeric(
            df[low_col],
            errors="coerce"
        )

    if series_col:
        out["SERIES"] = (
            df[series_col]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        out = out[
            out["SERIES"].isin(["EQ", "BE", "BZ"])
        ].copy()

    out = out[
        out["SYMBOL"].notna()
        & (out["SYMBOL"] != "")
        & out["CLOSE"].notna()
    ].copy()

    if len(out) == 0:
        print(
            "SKIP EMPTY AFTER CLEANING:",
            os.path.basename(path)
        )
        return None

    return out


# ---------------------------------------------------------
# LOAD ALL NSE RAW FILES
# ---------------------------------------------------------

files = sorted(
    glob.glob(os.path.join(RAW, "*.csv"))
)

print("Raw CSV files found:", len(files))

if not files:
    raise SystemExit(
        "No NSE raw CSV files found in data/raw"
    )

frames = []

for path in files:
    x = read_file(path)

    if x is not None and len(x):
        filename = os.path.basename(path)

        # Expected filename: YYYY-MM-DD.csv
        try:
            session_date = pd.to_datetime(
                filename[:10]
            )
        except Exception:
            print(
                "DATE ERROR:",
                filename
            )
            continue

        x["DATE"] = session_date
        frames.append(x)

print("Valid NSE files:", len(frames))

if not frames:
    raise SystemExit(
        "No valid NSE raw files found after parsing"
    )


allx = pd.concat(
    frames,
    ignore_index=True
)

allx = allx.sort_values(
    ["DATE", "SYMBOL"]
)

# Remove accidental duplicate symbol/date rows
allx = allx.drop_duplicates(
    subset=["DATE", "SYMBOL"],
    keep="last"
)

session_dates = sorted(
    allx["DATE"].dropna().unique()
)

if len(session_dates) < 50:
    raise SystemExit(
        f"Only {len(session_dates)} valid NSE sessions found; "
        "50 completed sessions are required."
    )

dates = session_dates[-50:]

print(
    "Using 50 sessions:",
    pd.Timestamp(dates[0]).date(),
    "to",
    pd.Timestamp(dates[-1]).date()
)


# ---------------------------------------------------------
# PREPARE DAILY DATA
# ---------------------------------------------------------

daily = {}

for d in dates:
    daily[d] = (
        allx[allx["DATE"] == d]
        .copy()
    )


# ---------------------------------------------------------
# CALCULATE MARKET INTELLIGENCE
# ---------------------------------------------------------

rows = []

for i, d in enumerate(dates):

    cur = daily[d].copy()

    # Previous actual NSE session
    if i > 0:
        previous_date = dates[i - 1]
        previous = daily[previous_date][
            ["SYMBOL", "CLOSE", "VOLUME"]
        ].copy()

        previous = previous.rename(
            columns={
                "CLOSE": "PCLOSE",
                "VOLUME": "PVOL"
            }
        )

        cur = cur.merge(
            previous,
            on="SYMBOL",
            how="left"
        )

    else:
        cur["PCLOSE"] = cur["PREV_CLOSE"]
        cur["PVOL"] = np.nan

    # Prefer actual previous-session close.
    # Fall back to NSE PREV_CLOSE where necessary.
    cur["BASE_CLOSE"] = cur["PCLOSE"]

    cur.loc[
        cur["BASE_CLOSE"].isna(),
        "BASE_CLOSE"
    ] = cur.loc[
        cur["BASE_CLOSE"].isna(),
        "PREV_CLOSE"
    ]

    ret = (
        cur["CLOSE"] /
        cur["BASE_CLOSE"] -
        1
    )

    valid_ret = ret.replace(
        [np.inf, -np.inf],
        np.nan
    ).notna()

    adv = int(
        (ret[valid_ret] > 0).sum()
    )

    dec = int(
        (ret[valid_ret] < 0).sum()
    )

    unchanged = int(
        (ret[valid_ret] == 0).sum()
    )

    # -----------------------------------------------------
    # A/D RATIO
    # -----------------------------------------------------

    ad_ratio = (
        adv / dec
        if dec > 0
        else np.nan
    )

    # -----------------------------------------------------
    # TRIN / ARMS
    # -----------------------------------------------------

    up_volume = cur.loc[
        ret > 0,
        "VOLUME"
    ].fillna(0).sum()

    down_volume = cur.loc[
        ret < 0,
        "VOLUME"
    ].fillna(0).sum()

    if (
        adv > 0
        and dec > 0
        and up_volume > 0
        and down_volume > 0
    ):
        trin = (
            (adv / dec) /
            (up_volume / down_volume)
        )
    else:
        trin = np.nan

    # -----------------------------------------------------
    # +/- 4.5% MOVERS
    # -----------------------------------------------------

    up45 = int(
        (ret >= 0.045).sum()
    )

    down45 = int(
        (ret <= -0.045).sum()
    )

    # -----------------------------------------------------
    # 5-SESSION +20%
    # -----------------------------------------------------

    if i >= 5:

        date5 = dates[i - 5]

        old5 = daily[date5][
            ["SYMBOL", "CLOSE"]
        ].rename(
            columns={
                "CLOSE": "CLOSE_5D"
            }
        )

        temp = cur[
            ["SYMBOL", "CLOSE"]
        ].merge(
            old5,
            on="SYMBOL",
            how="left"
        )

        r5 = (
            temp["CLOSE"] /
            temp["CLOSE_5D"] -
            1
        )

        up20 = int(
            (r5 >= 0.20).sum()
        )

    else:
        up20 = 0

    # -----------------------------------------------------
    # EMA BREADTH
    # -----------------------------------------------------

    history = allx[
        allx["DATE"] <= d
    ].copy()

    ema20_count = 0
    ema50_count = 0
    ema200_count = 0

    ema_universe = 0

    for symbol, group in history.groupby(
        "SYMBOL"
    ):

        series = (
            group
            .sort_values("DATE")["CLOSE"]
            .dropna()
        )

        if len(series) < 20:
            continue

        price = float(
            series.iloc[-1]
        )

        ema20 = (
            series
            .ewm(
                span=20,
                adjust=False
            )
            .mean()
            .iloc[-1]
        )

        ema50 = (
            series
            .ewm(
                span=50,
                adjust=False
            )
            .mean()
            .iloc[-1]
        )

        ema200 = (
            series
            .ewm(
                span=200,
                adjust=False
            )
            .mean()
            .iloc[-1]
        )

        ema_universe += 1

        if price > ema20:
            ema20_count += 1

        if price > ema50:
            ema50_count += 1

        if price > ema200:
            ema200_count += 1

    if ema_universe:
        above20 = (
            ema20_count /
            ema_universe *
            100
        )

        above50 = (
            ema50_count /
            ema_universe *
            100
        )

        above200 = (
            ema200_count /
            ema_universe *
            100
        )

    else:
        above20 = np.nan
        above50 = np.nan
        above200 = np.nan

    # -----------------------------------------------------
    # STORE SESSION
    # -----------------------------------------------------

    rows.append({
        "session_date":
            str(pd.Timestamp(d).date()),

        "advances":
            adv,

        "declines":
            dec,

        "unchanged":
            unchanged,

        "ad_ratio":
            None
            if not np.isfinite(ad_ratio)
            else round(
                float(ad_ratio),
                4
            ),

        "trin":
            None
            if not np.isfinite(trin)
            else round(
                float(trin),
                4
            ),

        "up_4_5":
            up45,

        "down_4_5":
            down45,

        "up20_5d":
            up20,

        "universe":
            int(len(cur)),

        "ema_universe":
            int(ema_universe),

        "above_20_ema":
            None
            if not np.isfinite(above20)
            else round(
                float(above20),
                2
            ),

        "above_50_ema":
            None
            if not np.isfinite(above50)
            else round(
                float(above50),
                2
            ),

        "above_200_ema":
            None
            if not np.isfinite(above200)
            else round(
                float(above200),
                2
            )
    })


# ---------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------

if len(rows) != 50:
    raise SystemExit(
        f"Expected exactly 50 sessions, got {len(rows)}"
    )

for row in rows:
    if row["universe"] <= 0:
        raise SystemExit(
            "Validation failed: empty session "
            + row["session_date"]
        )

    if row["advances"] + row["declines"] + row["unchanged"] > row["universe"]:
        raise SystemExit(
            "Validation failed: breadth counts exceed universe "
            + row["session_date"]
        )


# ---------------------------------------------------------
# WRITE OUTPUT
# ---------------------------------------------------------

os.makedirs(
    "data",
    exist_ok=True
)

result = {
    "sessions": rows,
    "latest": rows[-1],
    "raw_files": len(files),
    "valid_raw_files": len(frames),
    "source": "NSE official bhavcopy files",
    "session_count": len(rows)
}

with open(
    OUT,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        result,
        f,
        indent=2
    )


print(
    "SUCCESS:",
    len(rows),
    "sessions calculated"
)

print(
    "Latest session:",
    rows[-1]["session_date"]
)

print(
    "Latest A/D:",
    rows[-1]["advances"],
    "/",
    rows[-1]["declines"]
)

print(
    "Latest TRIN:",
    rows[-1]["trin"]
)
