import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import requests
import yfinance as yf
import time, json, os
from datetime import datetime

st.set_page_config(page_title="BIST Dip Tarama", page_icon="📊", layout="wide")

BIST_INDICES = [
    "XU030", "XU050", "XU100",
    "XBANK", "XGMYO", "XUSIN", "XGIDA", "XMANA", "XHOLD",
    "XTEKS", "XKMYA", "XILTM", "XELKT", "XTCRT",
    "XINSA", "XSPOR", "XTEKY", "XULAS", "XTRZM",
]

SECTOR_TO_INDEX = {
    "Financial Services": "XBANK", "Finance": "XBANK",
    "Technology": "XTEKY", "Technology Services": "XTEKY",
    "Electronic Technology": "XTEKY",
    "Industrials": "XUSIN", "Industrial Services": "XUSIN",
    "Producer Manufacturing": "XUSIN", "Consumer Durables": "XUSIN",
    "Consumer Cyclical": "XTCRT", "Consumer Services": "XTCRT",
    "Consumer Defensive": "XGIDA", "Consumer Non-Durables": "XGIDA",
    "Consumer Non-Durable": "XGIDA",
    "Basic Materials": "XMANA", "Non-Energy Minerals": "XMANA",
    "Process Industries": "XKMYA",
    "Communication Services": "XILTM", "Communications": "XILTM",
    "Energy": "XELKT", "Energy Minerals": "XELKT", "Utilities": "XELKT",
    "Real Estate": "XGMYO",
    "Healthcare": "XUSIN", "Health Technology": "XUSIN", "Health Services": "XUSIN",
    "Transportation": "XULAS",
    "Distribution Services": "XTCRT", "Retail Trade": "XTCRT",
    "Commercial Services": "XTCRT", "Miscellaneous": "XU100",
}


# ══════════════════════════════════════════════════════════════
# DATA FUNCTIONS
# ══════════════════════════════════════════════════════════════
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stocks():
    url = "https://scanner.tradingview.com/turkey/scan"
    payload = {
        "columns": ["name", "sector", "indexes"],
        "sort": {"sortBy": "name", "sortOrder": "asc"},
        "range": [0, 700],
        "markets": ["turkey"],
        "symbols": {"query": {"types": []}, "tickers": []},
        "options": {"lang": "en"},
    }
    resp = requests.post(url, json=payload,
                         headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
                         timeout=20)
    resp.raise_for_status()
    stocks = {}
    for item in resp.json()["data"]:
        sym = item["s"].replace("BIST:", "")
        vals = item["d"]
        sector = vals[1] if len(vals) > 1 and vals[1] else "Unknown"
        idx_list = ["XUTUM"]
        raw_indexes = vals[2] if len(vals) > 2 and vals[2] else []
        if isinstance(raw_indexes, list):
            for idx_info in raw_indexes:
                if isinstance(idx_info, dict) and "proname" in idx_info:
                    proname = idx_info["proname"]
                    if proname.startswith("BIST:"):
                        idx_name = proname.replace("BIST:", "")
                        if idx_name not in idx_list:
                            idx_list.append(idx_name)
        if len(idx_list) <= 1:
            sec_idx = SECTOR_TO_INDEX.get(sector)
            if sec_idx and sec_idx not in idx_list:
                idx_list.append(sec_idx)
            if "XU100" not in idx_list:
                idx_list.append("XU100")
        stocks[sym] = {"sector": sector, "indices": idx_list}
    return stocks


def dl_single(ticker, interval="1wk"):
    try:
        d = yf.download(ticker, period="max", interval=interval, progress=False, auto_adjust=True)
        if d.empty:
            return None
        s = d["Close"].dropna()
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
        return s if len(s) > 0 else None
    except Exception:
        return None


def dl_batch(symbols, interval="1wk", batch_size=50, progress_bar=None):
    result = {}
    batches = [symbols[i:i+batch_size] for i in range(0, len(symbols), batch_size)]
    done = 0
    for batch in batches:
        tickers = [f"{s}.IS" for s in batch]
        try:
            data = yf.download(" ".join(tickers), period="max", interval=interval,
                               group_by="ticker", threads=True, progress=False, auto_adjust=True)
            if data is not None:
                for s in batch:
                    t = f"{s}.IS"
                    try:
                        if len(batch) == 1:
                            c = data["Close"].dropna()
                        else:
                            if t not in data.columns.get_level_values(0):
                                continue
                            c = data[t]["Close"].dropna()
                        if isinstance(c, pd.DataFrame):
                            c = c.iloc[:, 0]
                        if len(c) > 0:
                            result[s] = c
                    except Exception:
                        pass
        except Exception:
            pass
        done += len(batch)
        if progress_bar:
            progress_bar.progress(min(done / len(symbols), 1.0), text=f"{done}/{len(symbols)} hisse")
        time.sleep(0.3)
    return result


def gorsel_hafiza(close_arr):
    n = len(close_arr)
    if n < 20:
        return 0
    atl = close_arr.min()
    ath = close_arr.max()
    rng = ath - atl
    if rng <= 0:
        return 0
    pos = (close_arr - atl) / rng * 100.0
    bounces = 0
    in_dip = False
    for p in pos:
        if p <= 20:
            in_dip = True
        elif p >= 80 and in_dip:
            bounces += 1
            in_dip = False
    return bounces


def calc_dim(series):
    if series is None:
        return None
    clean = series.dropna()
    if len(clean) < 5:
        return None
    atl = float(clean.min())
    ath = float(clean.max())
    cur = float(clean.iloc[-1])
    if atl <= 0 or ath <= 0:
        return None
    return {"cur": cur, "atl": atl, "ath": ath,
            "atl_pct": (cur - atl) / atl * 100.0,
            "ath_pot": (ath - cur) / cur * 100.0}


def run_scan(stock_data, stocks_info, usdtry, indices, threshold):
    results = []
    for sym, close in stock_data.items():
        try:
            info = stocks_info.get(sym, {})
            sector = info.get("sector", "")
            stock_indices = info.get("indices", ["XUTUM"])

            tl = calc_dim(close)
            if tl is None:
                continue

            ua = usdtry.reindex(close.index, method="ffill")
            usd = calc_dim(close / ua)

            idx_results = []
            for idx_name in stock_indices:
                if idx_name in indices:
                    ia = indices[idx_name].reindex(close.index, method="ffill")
                    dim = calc_dim(close / ia)
                    if dim:
                        idx_results.append({"name": idx_name, **dim})

            best_idx = min(idx_results, key=lambda x: abs(x["atl_pct"])) if idx_results else None

            candidates = []
            if tl:
                candidates.append(("TL", abs(tl["atl_pct"]), tl["atl_pct"], tl["ath_pot"]))
            if usd:
                candidates.append(("USD", abs(usd["atl_pct"]), usd["atl_pct"], usd["ath_pot"]))
            if best_idx:
                candidates.append((best_idx["name"], abs(best_idx["atl_pct"]),
                                   best_idx["atl_pct"], best_idx["ath_pot"]))
            if not candidates:
                continue
            best = min(candidates, key=lambda x: x[1])
            if not any(c[1] <= threshold for c in candidates):
                continue

            gh = gorsel_hafiza(close.values)
            idx_parts = [f"{ir['name']}:%{ir['atl_pct']:.1f}" for ir in sorted(idx_results, key=lambda x: abs(x["atl_pct"]))]

            results.append({
                "Hisse": sym,
                "Sektor": sector,
                "Dahil Endeksler": ", ".join(stock_indices),
                "En Yakin Grafik": best[0],
                "atl_fark": round(abs(best[2]), 2),
                "ath_pot": round(best[3], 1),
                "gh": gh,
                "TL Fiyat": round(tl["cur"], 2),
                "TL ATL": round(tl["atl"], 2),
                "TL ATH": round(tl["ath"], 2),
                "tl_atl_fark": round(tl["atl_pct"], 2),
                "tl_ath_pot": round(tl["ath_pot"], 1),
                "USD Fiyat": round(usd["cur"], 4) if usd else None,
                "USD ATL": round(usd["atl"], 4) if usd else None,
                "usd_atl_fark": round(usd["atl_pct"], 2) if usd else None,
                "usd_ath_pot": round(usd["ath_pot"], 1) if usd else None,
                "Endeks Detay": " | ".join(idx_parts) if idx_parts else "-",
            })
        except Exception:
            continue
    return results


# ══════════════════════════════════════════════════════════════
# GENERATE HTML
# ══════════════════════════════════════════════════════════════
def generate_html(records, indices_list, meta):
    template_path = os.path.join(os.path.dirname(__file__), "template.html")
    if not os.path.exists(template_path):
        return None
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    clean = []
    for r in records:
        row = {}
        for k, v in r.items():
            if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
                row[k] = None
            else:
                row[k] = v
        clean.append(row)

    html = html.replace("__DATA__", json.dumps(clean, ensure_ascii=False))
    html = html.replace("__INDICES__", json.dumps(indices_list, ensure_ascii=False))
    html = html.replace("__META__", json.dumps(meta, ensure_ascii=False))
    return html


# ══════════════════════════════════════════════════════════════
# STREAMLIT UI
# ══════════════════════════════════════════════════════════════
def main():
    st.markdown("# 📊 BIST Dip Tarama")
    st.markdown("**Haftalik periyotta TL, USD ve Endeks bazli ATL taramasi**")

    with st.sidebar:
        st.header("Ayarlar")
        threshold = st.slider("ATL Esik (%)", 5, 30, 15, 1)
        interval = st.selectbox("Periyot", ["1wk", "1d", "1mo"],
                                format_func=lambda x: {"1wk": "Haftalik", "1d": "Gunluk", "1mo": "Aylik"}[x])

    if st.button("🚀 Taramayi Baslat", type="primary", use_container_width=True):
        with st.status("Tarama baslatiliyor...", expanded=True) as status:
            st.write("📋 Hisse listesi aliniyor...")
            stocks = fetch_stocks()
            st.write(f"✅ {len(stocks)} hisse bulundu")

            st.write("💱 USDTRY indiriliyor...")
            usdtry = dl_single("USDTRY=X", interval)
            if usdtry is None:
                st.error("USDTRY alinamadi!")
                return
            usdtry_rate = float(usdtry.iloc[-1])
            st.write(f"✅ USDTRY: {usdtry_rate:.2f}")

            st.write("📈 Endeks verileri indiriliyor...")
            indices = {}
            for name in BIST_INDICES:
                s = dl_single(f"{name}.IS", interval)
                if s is not None:
                    indices[name] = s
            if "XU100" in indices:
                indices["XUTUM"] = indices["XU100"]
            st.write(f"✅ {len(indices)} endeks alindi")

            st.write("📊 Hisse verileri indiriliyor...")
            progress = st.progress(0, text="Basliyor...")
            stock_data = dl_batch(list(stocks.keys()), interval, 50, progress)
            progress.empty()
            st.write(f"✅ {len(stock_data)} hisse verisi alindi")

            st.write("🔢 Hesaplaniyor...")
            records = run_scan(stock_data, stocks, usdtry, indices, threshold)
            st.write(f"✅ {len(records)} hisse bulundu")

            status.update(label=f"Tarama tamamlandi! {len(records)} hisse", state="complete")

        meta = {
            "usdtry": usdtry_rate,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total_scanned": len(stock_data),
            "threshold": threshold,
        }

        html = generate_html(records, list(indices.keys()), meta)
        if html:
            st.session_state["html"] = html
            st.session_state["records"] = records
        else:
            st.error("template.html bulunamadi!")

    if "html" in st.session_state:
        components.html(st.session_state["html"], height=900, scrolling=True)

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "📥 HTML Indir (tek dosya dashboard)",
                data=st.session_state["html"],
                file_name=f"bist_dip_tarama_{datetime.now().strftime('%Y%m%d')}.html",
                mime="text/html",
            )
        with col2:
            if st.session_state.get("records"):
                df = pd.DataFrame(st.session_state["records"])
                from io import BytesIO
                buf = BytesIO()
                df.to_excel(buf, index=False, sheet_name="Dip Tarama")
                st.download_button(
                    "📥 Excel Indir",
                    data=buf.getvalue(),
                    file_name=f"bist_dip_tarama_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )


if __name__ == "__main__":
    main()
