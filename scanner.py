#!/usr/bin/env python3
"""
GTF Demand & Supply Zone Scanner - NSE (Nifty 500 stocks)
GTF 'Trading in the Zone' rules based scanner.
Balanced parameters to reliably detect zones.
Run: python scanner.py
Output: reports/zone_report_YYYY-MM-DD.csv
"""
import os, sys, datetime, time, warnings
warnings.filterwarnings('ignore')
import yfinance as yf
import pandas as pd
import numpy as np

REPORTS_DIR = "reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

# ===== GTF PARAMETERS (balanced for auto-scan on 500 stocks) =====
ATR_PERIOD = 14
IMPULSE_MULT = 0.7
EXPLOSIVE_MULT = 1.5
BASE_MAX_BODY = 0.70
BASE_MAX_RANGE = 1.5
BASE_MAX_PCT = 65.0
MAX_BASES = 8
MIN_HT_ATR = 0.08
MAX_HT_ATR = 4.0
GAP_MIN_PCT = 0.2
FRESH_BARS = 80
MID_BARS = 160
MIN_SCORE = 4.0

# Read Nifty 500 symbols from nse_stocks.txt
def load_symbols():
    syms = set()
    if os.path.exists("nse_stocks.txt"):
        with open("nse_stocks.txt") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                for part in line.split(','):
                    p = part.strip().upper()
                    if p and len(p) > 1:
                        if not p.endswith('.NS'):
                            p = p + '.NS'
                        syms.add(p)
    return sorted(list(syms))

# Index mapping for quick lookup
NIFTY50 = {"RELIANCE","TCS","HDFCBANK","ICICIBANK","BHARTIARTL","SBIN","INFY","LICI","ITC","LT","HINDUNILVR","MARUTI","KOTAKBANK","AXISBANK","ASIANPAINT","BAJFINANCE","HCLTECH","SUNPHARMA","TATAMOTORS","TITAN","ONGC","NTPC","POWERGRID","M&M","TATASTEEL","WIPRO","ULTRACEMCO","ADANIENT","ADANIPORTS","JSWSTEEL","COALINDIA","NESTLEIND","GRASIM","BAJAJFINSV","DRREDDY","CIPLA","EICHERMOT","BRITANNIA","HDFCLIFE","DIVISLAB","TECHM","APOLLOHOSP","SBILIFE","HEROMOTOCO","BAJAJ-AUTO","HINDALCO","TATACONSUM","INDUSINDBK","BPCL","SHREECEM"}
BANKNIFTY = {"HDFCBANK","ICICIBANK","SBIN","KOTAKBANK","AXISBANK","BANDHANBNK","IDFCFIRSTB","FEDERALBNK","RBLBANK","AUBANK","BANKBARODA","PNB","CANBK","INDUSINDBK","YESBANK","IDBI","UNIONBANK"}
NIFTYIT = {"TCS","INFY","HCLTECH","WIPRO","TECHM","TATAELXSI","KPITTECH","CYIENT","MPHASIS","COFORGE","OFSS","LTTS","ZENSARTEC"}
NIFTY100 = {"UPL","VEDL","DABUR","PIDILITIND","SIEMENS","GODREJCP","DMART","ZOMATO","IRCTC","DLF","NAUKRI","PFC","RECLTD","BANDHANBNK","BIOCON","TORNTPHARM","GAIL","IOC","YESBANK","PNB","BANKBARODA","CANBK","UNIONBANK","INDIGO","TATAPOWER","ABB","LUPIN","AUROPHARMA","GLAND","LAURUSLABS","ALKEM","IPCA","NATCOPHARM","TORNTPOWER","BEL","HAL","RVNL","IRFC","CONCOR","TATACHEM","DEEPAKNTR","AARTIIND","NAVINFLUOR","SRF","GUJGASLTD","IGL","MGL","ATGL","PETRONET","CAMS","CDSL","MCX","BSE","IEX","ANGELONE","IDFCFIRSTB","FEDERALBNK","CHOLAFIN","M&MFIN","SHRIRAMFIN","LICHSGFIN","THERMAX","BHEL","JINDALSTEL","SAIL","NMDC","JUBLFOOD","DEVYANI","AMARAJABAT","EXIDEIND","BOSCHLTD","MOTHERSON","BALKRISIND","MRF","CEATLTD","APOLLOTYRE","TVSMOTOR","ASHOKLEY","BHARATFORG","MANAPPURAM","MUTHOOTFIN","ADANIGREEN","NHPC","POLYCAB","HAVELLS","VOLTAS","VBL","COLPAL","PAGEIND","KPRMILL","TRENT","ABFRL","ADANIPOWER","NYKAA","POLICYBZR","PAYTM","DELHIVERY"}

def get_index(sym):
    s = sym.replace('.NS','').upper().replace('BAJAJAUTO','BAJAJ-AUTO')
    if s in NIFTY50: return "NIFTY50"
    if s in BANKNIFTY: return "BANKNIFTY"
    if s in NIFTYIT: return "NIFTYIT"
    if s in NIFTY100: return "NIFTY100"
    return "NIFTYMID"

def body(h): return abs(h['Close'] - h['Open'])
def is_bull(h): return h['Close'] > h['Open']
def is_bear(h): return h['Close'] < h['Open']

def calc_atr(df, p=14):
    h,l,c = df['High'], df['Low'], df['Close']
    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(p).mean()

def detect_zones(df):
    zones = []
    df = df.copy()
    df['atr'] = calc_atr(df, ATR_PERIOD)
    if len(df) < 60:
        return zones

    for i in range(MAX_BASES+5, len(df)-1):
        a = df.iloc[i]
        a_atr = a['atr']
        if pd.isna(a_atr) or a_atr <= 0:
            continue

        bc = 0
        for bi in range(1, MAX_BASES+1):
            if i-bi < 0: break
            b = df.iloc[i-bi]
            bb = body(b)
            br = max(b['High']-b['Low'], 0.001)
            if bb <= a_atr*BASE_MAX_BODY and (br <= a_atr*BASE_MAX_RANGE or bb/br*100 <= BASE_MAX_PCT):
                bc += 1
            else:
                break

        if bc < 1:
            imp = abs(a['Close']-a['Open'])
            if i >= 1 and imp > 0 and body(df.iloc[i-1]) <= imp*0.6:
                bc = 1
            else:
                continue

        bslice = df.iloc[i-bc:i]
        wH = bslice['High'].max()
        wL = bslice['Low'].min()
        bH = bslice[['Open','Close']].max(axis=1).max()
        bL = bslice[['Open','Close']].min(axis=1).min()

        bull_imp = a['Close']>a['Open'] and body(a)>=a_atr*IMPULSE_MULT and a['Close']>wH
        bear_imp = a['Close']<a['Open'] and body(a)>=a_atr*IMPULSE_MULT and a['Close']<wL
        if not (bull_imp or bear_imp):
            continue

        is_demand = bull_imp
        prox = bH if is_demand else bL
        dist = wL if is_demand else wH

        if i-bc-1 >= 0:
            leg_in = df.iloc[i-bc-1]
            if is_demand and is_bear(leg_in):
                dist = min(dist, leg_in['Low'])
            if (not is_demand) and is_bull(leg_in):
                dist = max(dist, leg_in['High'])
        if is_demand:
            dist = min(dist, a['Low'])
        else:
            dist = max(dist, a['High'])

        ht = abs(prox - dist)
        if not (a_atr*MIN_HT_ATR <= ht <= a_atr*MAX_HT_ATR):
            continue

        pat = "RBR" if is_demand else "DBD"
        if i-bc-1 >= 0:
            lib = is_bull(df.iloc[i-bc-1])
            libe = is_bear(df.iloc[i-bc-1])
            pat = ("DBR" if libe else "RBR") if is_demand else ("RBD" if lib else "DBD")

        bars_ago = len(df) - 1 - i
        freshness = 3.0 if bars_ago<=FRESH_BARS else 1.5 if bars_ago<=MID_BARS else 0.0

        ec = 0
        if body(a) >= a_atr*EXPLOSIVE_MULT:
            ec = 1
            if i-1>=0 and body(df.iloc[i-1]) >= a_atr*EXPLOSIVE_MULT:
                ec = 2
        gap_up = gap_dn = big_gap = False
        if i-1 >= 0:
            prev = df.iloc[i-1]
            gap_up = (a['Open']-prev['High']) >= a['Close']*GAP_MIN_PCT/100
            gap_dn = (prev['Low']-a['Open']) >= a['Close']*GAP_MIN_PCT/100
            big_gap = abs(a['Open']-prev['Close']) >= a['Close']*GAP_MIN_PCT*2/100
        strength = 2.0 if ec>=2 else (2.0 if ec==1 and (gap_up if is_demand else gap_dn) and big_gap else 1.0 if ec==1 else 0.0)
        base_score = 2.0 if 1<=bc<=3 else 1.0 if 4<=bc<=5 else 0.0

        bonus = 0.0
        if i >= 20:
            try:
                ema20 = df['Close'].iloc[i-20:i+1].ewm(span=20).mean().iloc[-1]
                if (is_demand and dist>ema20) or ((not is_demand) and dist<ema20):
                    bonus += 0.5
            except: pass
        if (is_demand and gap_up) or ((not is_demand) and gap_dn):
            bonus += 0.5 if big_gap else 0.25
        rng = a['High']-a['Low']
        if rng > 0:
            cs = ((a['Close']-a['Low'])/rng) if is_demand else ((a['High']-a['Close'])/rng)
            bonus += min(1.0, max(0, cs))
        bonus = min(3.0, bonus)
        score = freshness + strength + base_score + bonus
        score = min(10.0, max(0.0, round(score*10)/10))
        if score < MIN_SCORE:
            continue

        last = df.iloc[-1]
        ztop = max(prox, dist)
        zbot = min(prox, dist)
        in_zone = (last['Low']<=ztop and last['Low']>=zbot) or (last['Close']<=ztop and last['Close']>=zbot)
        near_zone = abs(last['Close']-ztop)/ztop < 0.008 or abs(last['Close']-zbot)/zbot < 0.008
        swept = (is_demand and last['Close']<zbot) or ((not is_demand) and last['Close']>ztop)

        if in_zone: status="IN ZONE"; gap_pct=0.0
        elif near_zone:
            status="NEAR"
            if is_demand: gap_pct = round((last['Close']-ztop)/ztop*100, 2)
            else: gap_pct = round((zbot-last['Close'])/zbot*100, 2)
        elif swept:
            status="SWEPT"
            if is_demand: gap_pct = round(-(zbot-last['Close'])/zbot*100, 2)
            else: gap_pct = round((last['Close']-ztop)/ztop*100, 2)
        else:
            continue  # active but not touched

        age_m = max(1, round(bars_ago/20))
        formed_dt = df.index[i]

        zones.append({
            'zone_formed': f"{formed_dt.year}-{formed_dt.month:02d}",
            'age_m': age_m,
            'ltp': round(float(last['Close']),2),
            'today_low': round(float(last['Low']),2),
            'zone_top': round(float(ztop),2),
            'zone_bottom': round(float(zbot),2),
            'gap_pct': gap_pct,
            'score': score,
            'type': "DEMAND" if is_demand else "SUPPLY",
            'pattern': pat,
            'status': status,
        })
    return zones

def main():
    today = datetime.date.today()
    date_str = today.strftime("%Y-%m-%d")
    print(f"[{datetime.datetime.now():%H:%M:%S}] GTF Scanner starting for {date_str}")
    symbols = load_symbols()
    print(f"[{datetime.datetime.now():%H:%M:%S}] Loaded {len(symbols)} NSE symbols")

    end = today + datetime.timedelta(days=1)
    start = today - datetime.timedelta(days=550)

    all_rows = []
    done = 0; fail = 0
    for sym in symbols:
        try:
            tk = yf.Ticker(sym)
            df = tk.history(start=start, end=end, auto_adjust=True, progress=False)
            if len(df) < 60:
                done += 1; continue
            comp = sym.replace('.NS','')
            sector = "OTHER"
            try:
                info = tk.fast_info
                # sector from info is slow, skip for now
            except: pass
            try:
                info2 = tk.info
                comp = info2.get('longName') or info2.get('shortName') or comp
                sector = info2.get('sector') or "OTHER"
            except: pass
            zones = detect_zones(df)
            clean_sym = sym.replace('.NS','')
            for z in zones:
                z['symbol'] = clean_sym
                z['company'] = str(comp).replace(',',' ').replace('"',"'").replace('\n',' ')[:60]
                z['sector'] = str(sector).upper() if sector else "OTHER"
                z['index'] = get_index(sym)
                z['price_date'] = str(df.index[-1].date())
                all_rows.append(z)
            done += 1
            if done % 50 == 0:
                print(f"[{datetime.datetime.now():%H:%M:%S}] Progress {done}/{len(symbols)} → {len(all_rows)} zones")
            if done % 40 == 39:
                time.sleep(1)  # rate limit courtesy
        except Exception as e:
            fail += 1
            continue

    print(f"\n[{datetime.datetime.now():%H:%M:%S}] COMPLETE scanned={done} fail={fail} zones={len(all_rows)}")
    csv_path = os.path.join(REPORTS_DIR, f"zone_report_{date_str}.csv")
    df_out = pd.DataFrame(all_rows)
    if len(df_out) > 0:
        cols = ['symbol','company','index','sector','type','status','pattern','zone_formed','age_m','ltp','today_low','zone_top','zone_bottom','gap_pct','score','price_date']
        df_out = df_out[cols]
        status_order = {"IN ZONE":0,"NEAR":1,"SWEPT":2}
        df_out['_p'] = df_out['status'].map(status_order).fillna(9)
        df_out = df_out.sort_values(['_p','score'], ascending=[True,False]).drop(columns=['_p'])
    df_out.to_csv(csv_path, index=False)
    print(f"[{datetime.datetime.now():%H:%M:%S}] Saved {csv_path}")
    df_out.to_csv(os.path.join(REPORTS_DIR,"zone_report_latest.csv"), index=False)

    if len(df_out) > 0:
        print(f"\n--- SUMMARY ---")
        print(f"  Demand IN ZONE : {len(df_out[(df_out['type']=='DEMAND')&(df_out['status']=='IN ZONE')])}")
        print(f"  Supply IN ZONE : {len(df_out[(df_out['type']=='SUPPLY')&(df_out['status']=='IN ZONE')])}")
        print(f"  Near           : {len(df_out[df_out['status']=='NEAR'])}")
        print(f"  Swept          : {len(df_out[df_out['status']=='SWEPT'])}")
        print(f"  A grade (7+)   : {len(df_out[df_out['score']>=7])}")

if __name__ == "__main__":
    main()
