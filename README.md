# GTF Monthly Zone Scan 🔍

Automatic daily GTF (Get Trading Freedom — Trading in the Zone) Demand & Supply zone scanner for NSE (National Stock Exchange of India).

## 📊 Kya karta hai?

- Har trading day ke baad **9:30 PM IST** ko automatic chalta hai (GitHub Actions)
- NSE ke ~5000 stocks ko EOD basis par analyze karta hai
- GTF course ke rules se Demand & Supply zones detect karta hai
- Har zone ko **/10 score** deta hai (Freshness 3 + Strength 2 + Time@Base 2 + Bonus 3)
- Pattern classify karta hai: DBR/RBD (Reversal) vs RBR/DBD (Continuation)
- Status classify karta hai: IN ZONE / NEAR / SWEPT
- CSV report banata hai `reports/` folder mein
- Connected dashboard automatically is CSV ko fetch karke live signals dikhata hai

## 📁 Files

- `scanner.py` — Main Python scanner (GTF D&S detection + scoring logic)
- `requirements.txt` — Python dependencies (yfinance, pandas, numpy)
- `nse_stocks.txt` — NSE symbols list (1 per line, comma-separated, # for comments)
- `.github/workflows/daily_scan.yml` — GitHub Actions auto-run config
- `reports/zone_report_YYYY-MM-DD.csv` — Daily output CSV

## 🚀 Setup (Pehli baar)

1. Repo ko Public rakho (dashboard fetch kar sake)
2. Saari files upload karo (folder structure same rakho)
3. GitHub repo ke Actions tab par jao
4. "Daily GTF Zone Scan" workflow select karo
5. **Run workflow** button se pehla manual run chalao
6. 10-30 min mein `reports/` mein CSV ban jayegi
7. Dashboard file mein repo name update karo:
   ```js
   const GH_REPO="tumhara_username/monthly-zone-scan";
   ```

## ⏰ Schedule

Cron: `0 16 * * 1-5` = 16:00 UTC = **9:30 PM IST** (Mon-Fri, NSE close ke 3 ghante baad)

Manual run: Actions tab → Run workflow

## 📑 CSV Columns

| Column | Matlab |
|---|---|
| SYMBOL | NSE stock symbol |
| COMPANY | Company name |
| SECTOR | Industry sector |
| INDEX | Index membership (NIFTY50/BANKNIFTY/NIFTYIT/NIFTY100/NIFTYMID) |
| PRICE_DATE | Scan date |
| ZONE_FORMED | Zone kis month mein bana (YYYY-MM) |
| AGE_M | Zone kitni purani hai (months mein) |
| LTP | Last traded price |
| TODAY_LOW | Aaj ka low |
| ZONE_TOP | Zone top (proximal/distal mein jo upar hai) |
| ZONE_BOTTOM | Zone bottom |
| GAP_PCT | Price zone se kitna door hai (%) |
| SCORE | GTF score /10 |
| TYPE | DEMAND ya SUPPLY |
| PATTERN | DBR/RBR/RBD/DBD |
| STATUS | IN ZONE / NEAR / SWEPT |

## ⚠️ Disclaimer

Ye educational screening tool hai — trading advice nahi. Hamesha SL/TP ke saath risk manage karo. Sirf Type-1 (7+/10) high-quality setups hi consider karo.
