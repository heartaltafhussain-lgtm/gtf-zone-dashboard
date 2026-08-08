#!/usr/bin/env python3
"""
GTF Demand & Supply Zone Scanner - NSE All Stocks
GTF 'Trading in the Zone' course rules based institutional scanner.
Downloads daily EOD data for NSE stocks via yfinance, detects D&S zones,
scores them out of 10, and outputs CSV for the dashboard.

Run: python scanner.py
Output: reports/zone_report_YYYY-MM-DD.csv
"""

import os
import sys
import datetime
import time
import warnings
warnings.filterwarnings('ignore')

import yfinance as yf
import pandas as pd
import numpy as np

# ========== CONFIGURATION ==========
REPORTS_DIR = "reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

# GTF Parameters (from Trading in the Zone course)
ATR_PERIOD = 14
IMPULSE_MULT = 1.0        # Minimum impulse body (xATR)
EXPLOSIVE_MULT = 1.8      # Explosive move threshold (xATR)
BASE_MAX_BODY = 0.55      # Max body size for base candle (xATR)
BASE_MAX_RANGE = 1.30     # Max range for base candle (xATR)
BASE_MAX_PCT = 55.0       # Max body % of range for base
MAX_BASES = 8             # Max consecutive base candles
MIN_HT_ATR = 0.15         # Minimum zone height (xATR)
MAX_HT_ATR = 2.5          # Maximum zone height (xATR)
GAP_MIN_PCT = 0.3         # Significant gap %
FRESH_BARS = 60           # ~3 trading months
MID_BARS = 120            # ~6 trading months
MIN_SCORE = 5.0           # Minimum score to include in report

# Index mapping for stocks
NIFTY50 = {"RELIANCE","TCS","HDFCBANK","ICICIBANK","BHARTIARTL","SBIN","INFY",
    "LICI","ITC","LT","HINDUNILVR","MARUTI","KOTAKBANK","AXISBANK","ASIANPAINT",
    "BAJFINANCE","HCLTECH","SUNPHARMA","TATAMOTORS","TITAN","ONGC","NTPC","POWERGRID",
    "M&M","TATASTEEL","WIPRO","ULTRACEMCO","ADANIENT","ADANIPORTS","JSWSTEEL",
    "COALINDIA","NESTLEIND","GRASIM","BAJAJFINSV","DRREDDY","CIPLA","EICHERMOT",
    "BRITANNIA","HDFCLIFE","DIVISLAB","TECHM","APOLLOHOSP","SBILIFE","HEROMOTOCO",
    "BAJAJ-AUTO","HINDALCO","TATACONSUM","INDUSINDBK","BPCL","SHREECEM"}

BANKNIFTY = {"HDFCBANK","ICICIBANK","SBIN","KOTAKBANK","AXISBANK","BANDHANBNK",
    "IDFCFIRSTB","FEDERALBNK","RBLBANK","KARURVYSYA","CUB","BANKBARODA","PNB",
    "CANBK","INDUSINDBK","YESBANK","IDBI","UNIONBANK","AUBANK"}

NIFTYIT = {"TCS","INFY","HCLTECH","WIPRO","TECHM","LTTS","TATAELXSI","KPITTECH",
    "MPHASIS","COFORGE","OFSS","CYIENT","ZENSARTEC"}

NIFTY100 = {"UPL","VEDL","DABUR","PIDILITIND","SIEMENS","GODREJCP","DMART","ZOMATO",
    "IRCTC","DLF","NAUKRI","PFC","RECLTD","BANDHANBNK","BIOCON","TORNTPHARM","GAIL",
    "IOC","YESBANK","PNB","BANKBARODA","CANBK","UNIONBANK","INDIGO","TATAPOWER",
    "ABB","LUPIN","AUROPHARMA","GLAND","LAURUSLABS","ALKEM","IPCA","NATCOPHARM",
    "TORNTPOWER","BEL","HAL","RVNL","IRFC","CONCOR","TATACHEM","DEEPAKNTR",
    "AARTIIND","NAVINFLUOR","SRF","GUJGASLTD","IGL","MGL","ATGL","PETRONET",
    "CAMS","CDSL","MCX","BSE","IEX","ANGELONE","IDFCFIRSTB","FEDERALBNK",
    "CHOLAFIN","M&MFIN","SHRIRAMFIN","LICHSGFIN","THERMAX","BHEL","JINDALSTEL",
    "SAIL","NMDC","JUBLFOOD","DEVYANI","AMARAJABAT","EXIDEIND","BOSCHLTD",
    "MOTHERSON","BALKRISIND","MRF","CEATLTD","APOLLOTYRE","TVSMOTOR","ASHOKLEY",
    "BHARATFORG","MANAPPURAM","MUTHOOTFIN","ADANIGREEN","NHPC","POLYCAB","HAVELLS",
    "VOLTAS","VBL","COLPAL","PAGEIND","KPRMILL","TRENT","ABFRL","ADANIPOWER",
    "NYKAA","POLICYBZR","PAYTM","DELHIVERY"}


def get_index(sym):
    """Return primary index membership for a symbol"""
    s = sym.replace('.NS','').upper()
    if s in NIFTY50: return "NIFTY50"
    if s in BANKNIFTY: return "BANKNIFTY"
    if s in NIFTYIT: return "NIFTYIT"
    if s in NIFTY100: return "NIFTY100"
    return "NIFTYMID"


def load_nse_symbols():
    """Load NSE symbols from nse_stocks.txt file.
    Format: each line can be a symbol or comma-separated symbols.
    Lines starting with # are comments.
    Returns list of symbols with .NS suffix for yfinance."""
    symfile = "nse_stocks.txt"
    symbols = []
    if os.path.exists(symfile):
        with open(symfile, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # Split by comma and clean
                parts = [p.strip().upper() for p in line.split(',')]
                for p in parts:
                    if p and not p.startswith('#'):
                        if not p.endswith('.NS'):
                            p = p + '.NS'
                        symbols.append(p)
    if not symbols:
        print("[WARN] nse_stocks.txt not found or empty! Using default Nifty 100...")
        fallback = list(NIFTY50) + list(NIFTY100)
        symbols = list(set(s + '.NS' for s in fallback))
    # Remove duplicates
    return list(dict.fromkeys(symbols))


def body(h):
    """Candle body size"""
    return abs(h['Close'] - h['Open'])


def is_bull(h):
    return h['Close'] > h['Open']


def is_bear(h):
    return h['Close'] < h['Open']


def calc_atr(df, period=14):
    """Calculate Average True Range"""
    h, l, c = df['High'], df['Low'], df['Close']
    tr = pd.concat([
        h - l,
        (h - c.shift()).abs(),
        (l - c.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def detect_zones(df):
    """
    Detect GTF Demand & Supply zones on a price dataframe.
    Returns list of zone dicts with scoring and status.
    """
    zones = []
    df = df.copy()
    df['atr'] = calc_atr(df, ATR_PERIOD)

    if len(df) < 60:
        return zones

    for i in range(MAX_BASES + 5, len(df) - 1):
        a = df.iloc[i]
        a_atr = a['atr']

        if pd.isna(a_atr) or a_atr <= 0:
            continue

        # Count consecutive base candles before current impulse
        bc = 0
        for bi in range(1, MAX_BASES + 1):
            if i - bi < 0:
                break
            b = df.iloc[i - bi]
            bb = body(b)
            br = max(b['High'] - b['Low'], 0.001)
            is_base_candle = (
                bb <= a_atr * BASE_MAX_BODY
                and (br <= a_atr * BASE_MAX_RANGE or bb / br * 100 <= BASE_MAX_PCT)
            )
            if is_base_candle:
                bc += 1
            else:
                break

        # Allow single-candle V-base
        if bc < 1:
            imp = abs(a['Close'] - a['Open'])
            if i >= 1 and imp > 0 and body(df.iloc[i-1]) <= imp * 0.6:
                bc = 1
            else:
                continue

        # Get base zone high/low (wicks and bodies)
        bslice = df.iloc[i - bc : i]
        wH = bslice['High'].max()
        wL = bslice['Low'].min()
        bH = bslice[['Open', 'Close']].max(axis=1).max()
        bL = bslice[['Open', 'Close']].min(axis=1).min()

        # Check for impulse breakout (leg-out)
        bull_imp = (
            a['Close'] > a['Open']
            and body(a) >= a_atr * IMPULSE_MULT
            and a['Close'] > wH
        )
        bear_imp = (
            a['Close'] < a['Open']
            and body(a) >= a_atr * IMPULSE_MULT
            and a['Close'] < wL
        )

        if not (bull_imp or bear_imp):
            continue

        is_demand = bull_imp

        # Proximal and Distal lines
        prox = bH if is_demand else bL
        dist = wL if is_demand else wH

        # GTF exceptional distal marking for reversals:
        # Check leg-in candle before base
        if i - bc - 1 >= 0:
            leg_in = df.iloc[i - bc - 1]
            if is_demand and is_bear(leg_in):
                # DBR reversal - distal to lowest wick of leg-in
                dist = min(dist, leg_in['Low'])
            if (not is_demand) and is_bull(leg_in):
                # RBD reversal - distal to highest wick of leg-in
                dist = max(dist, leg_in['High'])

        # Include current impulse candle's extreme
        if is_demand:
            dist = min(dist, a['Low'])
        else:
            dist = max(dist, a['High'])

        # Zone height validation
        ht = abs(prox - dist)
        if not (a_atr * MIN_HT_ATR <= ht <= a_atr * MAX_HT_ATR):
            continue

        # Pattern classification (DBR/RBR for Demand, RBD/DBD for Supply)
        pat = "RBR" if is_demand else "DBD"
        if i - bc - 1 >= 0:
            lib = is_bull(df.iloc[i - bc - 1])
            libe = is_bear(df.iloc[i - bc - 1])
            pat = ("DBR" if libe else "RBR") if is_demand else ("RBD" if lib else "DBD")

        # ========== GTF SCORING (/10) ==========
        bars_ago = len(df) - 1 - i
        age_days = bars_ago  # approximate

        # Freshness /7
        freshness = 3.0 if bars_ago <= FRESH_BARS else 1.5 if bars_ago <= MID_BARS else 0.0

        # Strength (Explosive moves + gap) /2
        ec = 0
        if body(a) >= a_atr * EXPLOSIVE_MULT:
            ec = 1
            if i - 1 >= 0 and body(df.iloc[i-1]) >= a_atr * EXPLOSIVE_MULT:
                ec = 2
        gap_up = False
        gap_dn = False
        big_gap = False
        if i - 1 >= 0:
            prev = df.iloc[i-1]
            gap_up = (a['Open'] - prev['High']) >= a['Close'] * GAP_MIN_PCT / 100
            gap_dn = (prev['Low'] - a['Open']) >= a['Close'] * GAP_MIN_PCT / 100
            big_gap = abs(a['Open'] - prev['Close']) >= a['Close'] * GAP_MIN_PCT * 2 / 100
        strength = 2.0 if ec >= 2 else (
            2.0 if ec == 1 and (gap_up if is_demand else gap_dn) and big_gap
            else 1.0 if ec == 1 else 0.0
        )

        # Time @ Base /2
        base_score = 2.0 if 1 <= bc <= 3 else 1.0 if 4 <= bc <= 5 else 0.0

        # Bonus /3
        bonus = 0.0

        # EMA20 alignment bonus
        if i >= 20:
            try:
                ema20 = df['Close'].iloc[i-20:i+1].ewm(span=20).mean().iloc[-1]
                if (is_demand and dist > ema20) or (not is_demand and dist < ema20):
                    bonus += 0.5
            except Exception:
                pass

        # Pro-gap bonus
        if (is_demand and gap_up) or (not is_demand and gap_dn):
            bonus += 0.5 if big_gap else 0.25

        # Closing strength bonus
        rng = a['High'] - a['Low']
        if rng > 0:
            close_pos = ((a['Close'] - a['Low']) / rng) if is_demand else ((a['High'] - a['Close']) / rng)
            bonus += min(1.0, max(0, close_pos))

        bonus = min(3.0, bonus)

        # Total score
        score = freshness + strength + base_score + bonus
        score = min(10.0, max(0.0, round(score * 10) / 10))

        if score < MIN_SCORE:
            continue

        # ========== ZONE STATUS vs CURRENT PRICE ==========
        last = df.iloc[-1]
        ztop = max(prox, dist)
        zbot = min(prox, dist)
        status = ""
        gap_pct = 0.0

        in_zone = (last['Low'] <= ztop and last['Low'] >= zbot) or (
            last['Close'] <= ztop and last['Close'] >= zbot
        )
        near_zone = (
            abs(last['Close'] - ztop) / ztop < 0.005
            or abs(last['Close'] - zbot) / zbot < 0.005
        )
        swept = (is_demand and last['Close'] < zbot) or (
            (not is_demand) and last['Close'] > ztop
        )

        if in_zone:
            status = "IN ZONE"
            gap_pct = 0.0
        elif near_zone:
            status = "NEAR"
            if is_demand:
                gap_pct = round((last['Close'] - ztop) / ztop * 100, 2)
            else:
                gap_pct = round((zbot - last['Close']) / zbot * 100, 2)
        elif swept:
            status = "SWEPT"
            if is_demand:
                gap_pct = round(-(zbot - last['Close']) / zbot * 100, 2)
            else:
                gap_pct = round((last['Close'] - ztop) / ztop * 100, 2)
        else:
            # Zone active but price not near - skip for dashboard
            continue

        age_m = max(1, round(bars_ago / 20))  # ~20 trading days per month
        formed_dt = df.index[i]

        zones.append({
            'symbol': '',  # filled later
            'company': '',
            'sector': '',
            'index': '',
            'price_date': str(df.index[-1].date()),
            'zone_formed': f"{formed_dt.year}-{formed_dt.month:02d}",
            'age_m': age_m,
            'ltp': round(float(last['Close']), 2),
            'today_low': round(float(last['Low']), 2),
            'zone_top': round(float(ztop), 2),
            'zone_bottom': round(float(zbot), 2),
            'gap_pct': gap_pct,
            'score': score,
            'type': "DEMAND" if is_demand else "SUPPLY",
            'pattern': pat,
            'status': status,
            'base_candles': bc,
            'freshness': round(freshness,1),
            'strength_p': round(strength,1),
            'base_p': round(base_score,1),
            'bonus_p': round(bonus,1),
        })

    return zones


def main():
    today = datetime.date.today()
    date_str = today.strftime("%Y-%m-%d")
    print(f"[{datetime.datetime.now():%H:%M:%S}] ========================================")
    print(f"[{datetime.datetime.now():%H:%M:%S}] GTF D&S Zone Scanner starting for {date_str}")
    print(f"[{datetime.datetime.now():%H:%M:%S}] ========================================")

    symbols = load_nse_symbols()
    print(f"[{datetime.datetime.now():%H:%M:%S}] Loaded {len(symbols)} NSE symbols")

    end = today + datetime.timedelta(days=1)
    start = today - datetime.timedelta(days=400)  # ~13 months of data

    all_rows = []
    done = 0
    fail = 0
    info_fail = 0

    for idx, sym in enumerate(symbols):
        try:
            tk = yf.Ticker(sym)
            df = tk.history(start=start, end=end, auto_adjust=True, progress=False)
            if len(df) < 60:
                done += 1
                continue

            # Get company metadata (best-effort, don't fail if no info)
            comp = sym.replace('.NS', '')
            sector = "OTHER"
            try:
                info = tk.info
                comp = info.get('longName') or info.get('shortName') or comp
                sector = info.get('sector') or "OTHER"
            except Exception:
                info_fail += 1

            zones = detect_zones(df)

            for z in zones:
                z['symbol'] = sym.replace('.NS', '')
                z['company'] = str(comp).replace(',', ' ').replace('"', "'").replace('\n', ' ')
                z['sector'] = str(sector).upper() if sector else "OTHER"
                z['index'] = get_index(sym)
                all_rows.append(z)

            done += 1
            if done % 25 == 0:
                print(
                    f"[{datetime.datetime.now():%H:%M:%S}] "
                    f"Progress: {done}/{len(symbols)} "
                    f"(failed={fail}, info-miss={info_fail}) "
                    f"→ {len(all_rows)} zones found so far..."
                )

            # Small courtesy delay to avoid rate limits
            if idx % 50 == 49:
                time.sleep(1)

        except Exception as e:
            fail += 1
            if fail <= 5:
                print(f"[{datetime.datetime.now():%H:%M:%S}] [WARN] {sym}: {str(e)[:80]}")
            continue

    print(f"\n[{datetime.datetime.now():%H:%M:%S}] ========================================")
    print(f"[{datetime.datetime.now():%H:%M:%S}] SCAN COMPLETE!")
    print(f"[{datetime.datetime.now():%H:%M:%S}]   Stocks scanned : {done}")
    print(f"[{datetime.datetime.now():%H:%M:%S}]   Download fails : {fail}")
    print(f"[{datetime.datetime.now():%H:%M:%S}]   Total zones    : {len(all_rows)}")
    print(f"[{datetime.datetime.now():%H:%M:%S}] ========================================")

    # Save dated CSV
    csv_path = os.path.join(REPORTS_DIR, f"zone_report_{date_str}.csv")
    df_out = pd.DataFrame(all_rows)
    if len(df_out) > 0:
        # Sort by status then score descending
        status_order = {"IN ZONE": 0, "NEAR": 1, "SWEPT": 2}
        df_out['_prio'] = df_out['status'].map(status_order).fillna(9)
        df_out = df_out.sort_values(['_prio', 'score'], ascending=[True, False]).drop(columns=['_prio'])
    df_out.to_csv(csv_path, index=False)
    print(f"[{datetime.datetime.now():%H:%M:%S}] Saved → {csv_path}")

    # Also save as latest (for easy access)
    latest_path = os.path.join(REPORTS_DIR, "zone_report_latest.csv")
    df_out.to_csv(latest_path, index=False)
    print(f"[{datetime.datetime.now():%H:%M:%S}] Saved → {latest_path}")

    # Summary stats
    if len(df_out) > 0:
        in_demand = len(df_out[(df_out['type']=='DEMAND')&(df_out['status']=='IN ZONE')])
        in_supply = len(df_out[(df_out['type']=='SUPPLY')&(df_out['status']=='IN ZONE')])
        near = len(df_out[df_out['status']=='NEAR'])
        swept = len(df_out[df_out['status']=='SWEPT'])
        a_grade = len(df_out[df_out['score']>=7])
        ap_grade = len(df_out[df_out['score']>=9])
        print(f"\n[{datetime.datetime.now():%H:%M:%S}] ---- SUMMARY ----")
        print(f"  Demand IN ZONE : {in_demand}")
        print(f"  Supply IN ZONE : {in_supply}")
        print(f"  Near zone      : {near}")
        print(f"  Swept/Invalid  : {swept}")
        print(f"  A grade (7+)   : {a_grade}")
        print(f"  A+ grade (9+)  : {ap_grade}")


if __name__ == "__main__":
    main()
