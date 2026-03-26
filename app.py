import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import requests
import time, json, os
from datetime import datetime

st.set_page_config(page_title="BIST Dip Tarama", page_icon="📊", layout="wide")

BIST_INDICES = [
    "XUTUM", "XTUMY", "XU030", "XU100", "XYLDZ", "XBANA", "XKOBI",
    "XUSIN", "XGIDA", "XKMYA", "XMADN", "XMANA", "XMESY", "XKAGT",
    "XTAST", "XTEKS", "XUHIZ", "XELKT", "XILTM", "XINSA", "XSPOR",
    "XULAS", "XUMAL", "XBANK", "XSGRT", "XFINK", "XHOLD", "XGMYO",
    "XAKUR", "XYORT", "XUTEK", "XBLSM",
]

SECTOR_TO_INDEX = {
    "Financial Services": "XBANK", "Finance": "XBANK",
    "Technology": "XUTEK", "Technology Services": "XUTEK",
    "Electronic Technology": "XUTEK",
    "Industrials": "XUSIN", "Industrial Services": "XUSIN",
    "Producer Manufacturing": "XUSIN", "Consumer Durables": "XUSIN",
    "Consumer Cyclical": "XUHIZ", "Consumer Services": "XUHIZ",
    "Consumer Defensive": "XGIDA", "Consumer Non-Durables": "XGIDA",
    "Consumer Non-Durable": "XGIDA",
    "Basic Materials": "XMANA", "Non-Energy Minerals": "XMADN",
    "Process Industries": "XKMYA",
    "Communication Services": "XILTM", "Communications": "XILTM",
    "Energy": "XELKT", "Energy Minerals": "XELKT", "Utilities": "XELKT",
    "Real Estate": "XGMYO",
    "Healthcare": "XUSIN", "Health Technology": "XUSIN", "Health Services": "XUSIN",
    "Transportation": "XULAS",
    "Distribution Services": "XUHIZ", "Retail Trade": "XUHIZ",
    "Commercial Services": "XUHIZ", "Miscellaneous": "XUTUM",
}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stocks():
    url = "https://scanner.tradingview.com/turkey/scan"
    payload = {
        "columns": ["name", "sector", "indexes"],
        "sort": {"sortBy": "name", "sortOrder": "asc"},
        "range": [0, 700], "markets": ["turkey"],
        "symbols": {"query": {"types": []}, "tickers": []},
        "options": {"lang": "en"},
    }
    resp = requests.post(url, json=payload,
                         headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}, timeout=20)
    resp.raise_for_status()
    stocks = {}
    bist_set = set(BIST_INDICES)
    for item in resp.json()["data"]:
        sym = item["s"].replace("BIST:", "")
        vals = item["d"]
        sector = vals[1] if len(vals) > 1 and vals[1] else "Unknown"
        idx_list = []
        raw_indexes = vals[2] if len(vals) > 2 and vals[2] else []
        if isinstance(raw_indexes, list):
            for idx_info in raw_indexes:
                if isinstance(idx_info, dict) and "proname" in idx_info:
                    proname = idx_info["proname"]
                    if proname.startswith("BIST:"):
                        idx_name = proname.replace("BIST:", "")
                        if idx_name in bist_set and idx_name not in idx_list:
                            idx_list.append(idx_name)
        if not idx_list:
            sec_idx = SECTOR_TO_INDEX.get(sector)
            if sec_idx: idx_list.append(sec_idx)
            idx_list.append("XUTUM")
        stocks[sym] = {"sector": sector, "indices": idx_list}
    return stocks


def tv_get_close(tv, symbol, exchange, interval, n_bars=5000):
    try:
        data = tv.get_hist(symbol, exchange, interval=interval, n_bars=n_bars)
        if data is not None and len(data) > 0:
            return data["close"]
    except Exception:
        pass
    return None


def gorsel_hafiza(close_arr):
    n = len(close_arr)
    if n < 20: return 0
    atl, ath = close_arr.min(), close_arr.max()
    rng = ath - atl
    if rng <= 0: return 0
    pos = (close_arr - atl) / rng * 100.0
    bounces, in_dip = 0, False
    for p in pos:
        if p <= 20: in_dip = True
        elif p >= 80 and in_dip: bounces += 1; in_dip = False
    return bounces


def calc_dim(series):
    if series is None: return None
    clean = series.dropna()
    if len(clean) < 5: return None
    atl, ath, cur = float(clean.min()), float(clean.max()), float(clean.iloc[-1])
    if atl <= 0 or ath <= 0: return None
    return {"cur": cur, "atl": atl, "ath": ath,
            "atl_pct": (cur - atl) / atl * 100.0, "ath_pot": (ath - cur) / cur * 100.0}


def align_and_divide(numerator, denominator):
    n, d = numerator.copy(), denominator.copy()
    n.index = n.index.normalize()
    d.index = d.index.normalize()
    n = n[~n.index.duplicated(keep='last')]
    d = d[~d.index.duplicated(keep='last')]
    merged = pd.DataFrame({"num": n, "den": d}).ffill().dropna()
    if len(merged) < 5: return None
    return merged["num"] / merged["den"]


def run_scan(stock_data, stocks_info, usdtry, indices, threshold):
    results = []
    for sym, close in stock_data.items():
        try:
            info = stocks_info.get(sym, {})
            sector, stock_indices = info.get("sector", ""), info.get("indices", ["XUTUM"])
            tl = calc_dim(close)
            if tl is None: continue
            usd = calc_dim(align_and_divide(close, usdtry))
            idx_results = []
            for idx_name in stock_indices:
                if idx_name in indices:
                    ratio = align_and_divide(close, indices[idx_name])
                    dim = calc_dim(ratio)
                    if dim: idx_results.append({"name": idx_name, **dim})
            best_idx = min(idx_results, key=lambda x: abs(x["atl_pct"])) if idx_results else None
            candidates = []
            if tl: candidates.append(("TL", abs(tl["atl_pct"]), tl["atl_pct"], tl["ath_pot"]))
            if usd: candidates.append(("USD", abs(usd["atl_pct"]), usd["atl_pct"], usd["ath_pot"]))
            if best_idx: candidates.append((best_idx["name"], abs(best_idx["atl_pct"]), best_idx["atl_pct"], best_idx["ath_pot"]))
            if not candidates: continue
            best = min(candidates, key=lambda x: x[1])
            if not any(c[1] <= threshold for c in candidates): continue
            gh = gorsel_hafiza(close.values)
            idx_parts = [f"{ir['name']}:%{ir['atl_pct']:.1f}|+%{ir['ath_pot']:.0f}" for ir in sorted(idx_results, key=lambda x: abs(x["atl_pct"]))]
            results.append({
                "Hisse": sym, "Sektor": sector, "Dahil Endeksler": ", ".join(stock_indices),
                "En Yakin Grafik": best[0], "atl_fark": round(abs(best[2]), 2),
                "ath_pot": round(best[3], 1), "gh": gh,
                "TL Fiyat": round(tl["cur"], 2), "TL ATL": round(tl["atl"], 2),
                "TL ATH": round(tl["ath"], 2), "tl_atl_fark": round(tl["atl_pct"], 2),
                "tl_ath_pot": round(tl["ath_pot"], 1),
                "USD Fiyat": round(usd["cur"], 4) if usd else None,
                "USD ATL": round(usd["atl"], 4) if usd else None,
                "usd_atl_fark": round(usd["atl_pct"], 2) if usd else None,
                "usd_ath_pot": round(usd["ath_pot"], 1) if usd else None,
                "Endeks Detay": " | ".join(idx_parts) if idx_parts else "-",
            })
        except Exception: continue
    return results


def generate_html(records, indices_list, meta):
    tpl = os.path.join(os.path.dirname(__file__), "template.html")
    if not os.path.exists(tpl): return None
    with open(tpl, "r", encoding="utf-8") as f: html = f.read()
    clean = []
    for r in records:
        row = {}
        for k, v in r.items():
            row[k] = None if isinstance(v, float) and (np.isnan(v) or np.isinf(v)) else v
        clean.append(row)
    html = html.replace("__DATA__", json.dumps(clean, ensure_ascii=False))
    html = html.replace("__INDICES__", json.dumps(indices_list, ensure_ascii=False))
    html = html.replace("__META__", json.dumps(meta, ensure_ascii=False))
    return html


def main():
    st.markdown("# BIST Dip Tarama")
    st.markdown("**Tum veriler TradingView'den - 32 endeks, haftalik periyot**")

    with st.sidebar:
        st.header("Ayarlar")
        threshold = st.slider("ATL Esik (%)", 5, 50, 15, 1)
        period = st.selectbox("Mum Periyodu", ["Haftalik", "Aylik", "6 Aylik", "Yillik (12 Ay)"])

    if st.button("Taramayi Baslat", type="primary", use_container_width=True):
        from tvDatafeed import TvDatafeed, Interval
        period_map = {
            "Haftalik": (Interval.in_weekly, 5000, None),
            "Aylik": (Interval.in_monthly, 5000, None),
            "6 Aylik": (Interval.in_monthly, 5000, "6ME"),
            "Yillik (12 Ay)": (Interval.in_monthly, 5000, "YE"),
        }
        interval, n_bars, resample_rule = period_map[period]

        with st.status("Tarama baslatiliyor...", expanded=True) as status:
            st.write("Hisse listesi aliniyor...")
            stocks = fetch_stocks()
            st.write(f"{len(stocks)} hisse bulundu")

            st.write("TradingView'e baglaniliyor...")
            tv = TvDatafeed()

            st.write("USDTRY indiriliyor...")
            usdtry = tv_get_close(tv, "USDTRY", "FX_IDC", interval, n_bars)
            if usdtry is None:
                st.error("USDTRY alinamadi!")
                return
            st.write(f"USDTRY: {float(usdtry.iloc[-1]):.2f}")

            st.write(f"{len(BIST_INDICES)} endeks indiriliyor...")
            indices = {}
            for name in BIST_INDICES:
                s = tv_get_close(tv, name, "BIST", interval, n_bars)
                if s is not None: indices[name] = s
            st.write(f"{len(indices)} endeks alindi")

            st.write(f"{len(stocks)} hisse indiriliyor (bu kisim ~10dk surer)...")
            stock_data = {}
            progress = st.progress(0)
            syms = list(stocks.keys())
            fails = 0
            for i, s in enumerate(syms):
                c = tv_get_close(tv, s, "BIST", interval, n_bars)
                if c is not None:
                    stock_data[s] = c
                    fails = 0
                else:
                    fails += 1
                    if fails >= 3:
                        try: tv = TvDatafeed(); fails = 0; time.sleep(1)
                        except: pass
                progress.progress((i + 1) / len(syms))
                if (i + 1) % 100 == 0: time.sleep(1)
            progress.empty()
            st.write(f"{len(stock_data)} hisse verisi alindi")

            if resample_rule:
                st.write(f"Resample ediliyor ({resample_rule})...")
                usdtry = usdtry.resample(resample_rule).last().dropna()
                for k in list(indices.keys()):
                    indices[k] = indices[k].resample(resample_rule).last().dropna()
                for k in list(stock_data.keys()):
                    r = stock_data[k].resample(resample_rule).last().dropna()
                    if len(r) >= 5: stock_data[k] = r
                    else: del stock_data[k]

            st.write("Hesaplaniyor...")
            records = run_scan(stock_data, stocks, usdtry, indices, threshold)
            st.write(f"{len(records)} hisse bulundu")
            status.update(label=f"Tarama tamamlandi! {len(records)} hisse", state="complete")

        meta = {"usdtry": float(usdtry.iloc[-1]), "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "total_scanned": len(stock_data), "threshold": threshold, "period": period}
        html = generate_html(records, list(indices.keys()), meta)
        if html:
            st.session_state["html"] = html
            st.session_state["records"] = records

    if "html" in st.session_state:
        components.html(st.session_state["html"], height=900, scrolling=True)
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("HTML Indir", data=st.session_state["html"],
                               file_name=f"bist_dip_{datetime.now().strftime('%Y%m%d')}.html", mime="text/html")
        with col2:
            if st.session_state.get("records"):
                from io import BytesIO
                buf = BytesIO()
                pd.DataFrame(st.session_state["records"]).to_excel(buf, index=False)
                st.download_button("Excel Indir", data=buf.getvalue(),
                                   file_name=f"bist_dip_{datetime.now().strftime('%Y%m%d')}.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


if __name__ == "__main__":
    main()
