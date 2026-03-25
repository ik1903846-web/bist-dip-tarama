import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import requests
import yfinance as yf
import time, json, os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

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
# DATA
# ══════════════════════════════════════════════════════════════
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stocks():
    """TradingView'den hisse listesi, basarisizsa isyatirim'den"""
    bist_set = set(BIST_INDICES)

    # Once TradingView dene
    try:
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
                if sec_idx:
                    idx_list.append(sec_idx)
                idx_list.append("XUTUM")
            stocks[sym] = {"sector": sector, "indices": idx_list}
        if len(stocks) > 50:
            return stocks
    except Exception:
        pass

    # Fallback: isyatirim'den hisse listesi
    from isyatirimhisse import fetch_stock_data
    st.warning("TradingView erisilemedi, isyatirim'den hisse listesi aliniyor...")
    try:
        # Tum endekslerden hisse listesi topla
        from isyatirimhisse import fetch_index_data
        stocks = {}
        for idx_name in BIST_INDICES:
            try:
                df = fetch_index_data(indices=idx_name,
                                      start_date=datetime.now().strftime("%d-%m-%Y"),
                                      end_date=datetime.now().strftime("%d-%m-%Y"))
                if df is not None and "CODE" in df.columns:
                    for sym in df["CODE"].unique():
                        sym = str(sym).strip()
                        if sym and sym not in stocks:
                            stocks[sym] = {"sector": "Unknown", "indices": [idx_name]}
                        elif sym in stocks and idx_name not in stocks[sym]["indices"]:
                            stocks[sym]["indices"].append(idx_name)
            except Exception:
                pass
        if len(stocks) > 50:
            return stocks
    except Exception:
        pass

    # Son fallback: yfinance ile BIST hisselerini bul
    import yfinance as yf
    st.warning("isyatirim hisse listesi de basarisiz, Yahoo Finance deneniyor...")
    tickers_raw = yf.download("XU100.IS", period="5d", progress=False)
    # Manuel liste
    stocks = {}
    for sym in ["AKBNK","ARCLK","ASELS","BIMAS","BJKAS","DOHOL","EKGYO","ENJSA",
                "EREGL","FROTO","GARAN","GUBRF","HEKTS","ISCTR","KCHOL","KOZAL",
                "MGROS","PETKM","PGSUS","SAHOL","SASA","SISE","SOKM","TAVHL",
                "TCELL","THYAO","TKFEN","TOASO","TTKOM","TUPRS","VESTL","YKBNK",
                "AKSEN","AEFES","CIMSA","ENKAI","HALKB","VAKBN","OTKAR","TTRAK",
                "PEKGY","GOZDE","DENGE","FORMT","ADEL","HOROZ","MARTI","ONRYT",
                "FENER","GSRAY","TSPOR","DGNMO","OSMEN"]:
        stocks[sym] = {"sector": "Unknown", "indices": ["XUTUM"]}
    return stocks


def dl_indices(interval="1wk"):
    from isyatirimhisse import fetch_index_data
    idx_data = {}
    end_date = datetime.now().strftime("%d-%m-%Y")
    for name in BIST_INDICES:
        try:
            df = fetch_index_data(indices=name, start_date="01-01-2010", end_date=end_date)
            if df is not None and len(df) > 50:
                s = df.set_index("DATE")["VALUE"].astype(float)
                s.index = pd.to_datetime(s.index)
                if interval == "1wk":
                    s = s.resample("W-FRI").last().dropna()
                elif interval == "1mo":
                    s = s.resample("ME").last().dropna()
                idx_data[name] = s
        except Exception:
            pass
    return idx_data


def dl_stocks(symbols, interval="1wk", batch_size=10, progress_bar=None):
    from isyatirimhisse import fetch_stock_data
    result_tl = {}
    result_usd = {}
    batches = [symbols[i:i+batch_size] for i in range(0, len(symbols), batch_size)]
    end_date = datetime.now().strftime("%d-%m-%Y")
    done = 0

    def fetch_batch(batch):
        try:
            df = fetch_stock_data(symbols=batch, start_date="01-01-2005", end_date=end_date)
            if df is None or len(df) == 0:
                return {}
            out = {}
            for sym, grp in df.groupby("HGDG_HS_KODU"):
                grp = grp.sort_values("HGDG_TARIH")
                grp["HGDG_TARIH"] = pd.to_datetime(grp["HGDG_TARIH"])
                tl = grp.set_index("HGDG_TARIH")["HGDG_KAPANIS"].astype(float)
                usd = grp.set_index("HGDG_TARIH")["DOLAR_BAZLI_FIYAT"].astype(float)
                if interval == "1wk":
                    tl = tl.resample("W-FRI").last().dropna()
                    usd = usd.resample("W-FRI").last().dropna()
                elif interval == "1mo":
                    tl = tl.resample("ME").last().dropna()
                    usd = usd.resample("ME").last().dropna()
                if len(tl) > 10:
                    out[sym] = {"tl": tl, "usd": usd}
            return out
        except Exception:
            return {}

    for batch in batches:
        batch_result = fetch_batch(batch)
        for sym, data in batch_result.items():
            result_tl[sym] = data["tl"]
            result_usd[sym] = data["usd"]
        done += len(batch)
        if progress_bar:
            progress_bar.progress(min(done / len(symbols), 1.0),
                                  text=f"{done}/{len(symbols)} hisse (isyatirim)")

    # Kaybolan hisseleri tek tek dene
    missing = [s for s in symbols if s not in result_tl]
    if missing:
        for sym in missing:
            r = fetch_batch([sym])
            if sym in r:
                result_tl[sym] = r[sym]["tl"]
                result_usd[sym] = r[sym]["usd"]

    return result_tl, result_usd


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


def run_scan(stock_tl, stock_usd, stocks_info, indices, threshold):
    results = []
    for sym, close in stock_tl.items():
        try:
            info = stocks_info.get(sym, {})
            sector = info.get("sector", "")
            stock_indices = info.get("indices", ["XUTUM"])

            close = close[close > 0]
            if len(close) < 10:
                continue

            tl = calc_dim(close)
            usd_close = stock_usd.get(sym)
            if usd_close is not None:
                usd_close = usd_close[usd_close > 0]
            usd = calc_dim(usd_close)

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
            idx_parts = [f"{ir['name']}:%{ir['atl_pct']:.1f}"
                         for ir in sorted(idx_results, key=lambda x: abs(x["atl_pct"]))]

            results.append({
                "Hisse": sym,
                "Sektor": sector,
                "Dahil Endeksler": ", ".join(stock_indices),
                "En Yakin Grafik": best[0],
                "atl_fark": round(abs(best[2]), 2),
                "ath_pot": round(best[3], 1),
                "gh": gh,
                "TL Fiyat": round(tl["cur"], 2) if tl else None,
                "TL ATL": round(tl["atl"], 2) if tl else None,
                "TL ATH": round(tl["ath"], 2) if tl else None,
                "tl_atl_fark": round(tl["atl_pct"], 2) if tl else None,
                "tl_ath_pot": round(tl["ath_pot"], 1) if tl else None,
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
# HTML
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
# UI
# ══════════════════════════════════════════════════════════════
def main():
    st.markdown("# 📊 BIST Dip Tarama")
    st.markdown("**isyatirim.com.tr verileri | 32 endeks | Haftalik periyot**")

    with st.sidebar:
        st.header("Ayarlar")
        threshold = st.slider("ATL Esik (%)", 5, 30, 15, 1)
        interval = st.selectbox("Periyot", ["1wk", "1d", "1mo"],
                                format_func=lambda x: {"1wk": "Haftalik", "1d": "Gunluk", "1mo": "Aylik"}[x])

    if st.button("🚀 Taramayi Baslat", type="primary", use_container_width=True):
        with st.status("Tarama baslatiliyor...", expanded=True) as status:
            st.write("📋 Hisse listesi aliniyor (TradingView)...")
            stocks = fetch_stocks()
            st.write(f"✅ {len(stocks)} hisse bulundu")

            st.write(f"📈 {len(BIST_INDICES)} endeks indiriliyor (isyatirim)...")
            indices = dl_indices(interval)
            st.write(f"✅ {len(indices)}/{len(BIST_INDICES)} endeks alindi")

            st.write("📊 Hisse verileri indiriliyor (isyatirim)...")
            progress = st.progress(0, text="Basliyor...")
            stock_tl, stock_usd = dl_stocks(list(stocks.keys()), interval, 30, progress)
            progress.empty()
            st.write(f"✅ {len(stock_tl)} hisse verisi alindi")

            st.write("🔢 Hesaplaniyor...")
            records = run_scan(stock_tl, stock_usd, stocks, indices, threshold)
            st.write(f"✅ {len(records)} hisse bulundu")

            status.update(label=f"Tamamlandi! {len(records)} hisse", state="complete")

        usdtry_s = yf.download("USDTRY=X", period="5d", progress=False, auto_adjust=True)
        usdtry_rate = float(usdtry_s["Close"].dropna().iloc[-1]) if not usdtry_s.empty else 0

        meta = {
            "usdtry": usdtry_rate,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total_scanned": len(stock_tl),
            "threshold": threshold,
        }

        html = generate_html(records, list(indices.keys()), meta)
        if html:
            st.session_state["html"] = html
            st.session_state["records"] = records

    if "html" in st.session_state:
        components.html(st.session_state["html"], height=900, scrolling=True)

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "📥 HTML Dashboard Indir",
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
