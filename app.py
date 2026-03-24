import streamlit as st
import pandas as pd
import numpy as np
import requests
import yfinance as yf
import time
from datetime import datetime

st.set_page_config(page_title="BIST Dip Tarama", page_icon="📊", layout="wide")

# ══════════════════════════════════════════════════════════════
# CACHE & DATA
# ══════════════════════════════════════════════════════════════
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


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stocks():
    """TradingView'den hisse listesi + endeks uyeligi"""
    url = "https://scanner.tradingview.com/turkey/scan"

    # Once indexes ile dene
    payload = {
        "columns": ["name", "sector", "indexes"],
        "sort": {"sortBy": "name", "sortOrder": "asc"},
        "range": [0, 700],
        "markets": ["turkey"],
        "symbols": {"query": {"types": []}, "tickers": []},
        "options": {"lang": "en"},
    }
    headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}

    resp = requests.post(url, json=payload, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    stocks = {}
    for item in data["data"]:
        sym = item["s"].replace("BIST:", "")
        vals = item["d"]
        name = vals[0] if len(vals) > 0 else sym
        sector = vals[1] if len(vals) > 1 and vals[1] else "Unknown"

        # Endeks uyeliklerini parse et
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

        # Eger TradingView'den endeks gelmezse sektor bazli ata
        if len(idx_list) <= 1:
            sec_idx = SECTOR_TO_INDEX.get(sector)
            if sec_idx and sec_idx not in idx_list:
                idx_list.append(sec_idx)
            if "XU100" not in idx_list:
                idx_list.append("XU100")

        stocks[sym] = {"name": name, "sector": sector, "indices": idx_list}

    return stocks


@st.cache_data(ttl=3600, show_spinner=False)
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
            progress_bar.progress(min(done / len(symbols), 1.0),
                                  text=f"{done}/{len(symbols)} hisse indirildi")
        time.sleep(0.3)
    return result


# ══════════════════════════════════════════════════════════════
# HESAPLAMA
# ══════════════════════════════════════════════════════════════
def gorsel_hafiza(close_arr):
    n = len(close_arr)
    if n < 20:
        return 0
    cum_min = np.minimum.accumulate(close_arr)
    cum_max = np.maximum.accumulate(close_arr)
    rng = cum_max - cum_min
    with np.errstate(divide="ignore", invalid="ignore"):
        pos = np.where(rng > 0, (close_arr - cum_min) / rng * 100.0, 50.0)
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
    return {
        "cur": cur, "atl": atl, "ath": ath,
        "atl_pct": (cur - atl) / atl * 100.0,
        "ath_pot": (ath - cur) / cur * 100.0,
    }


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
                "TL Fiyat": round(tl["cur"], 2),
                "TL ATL": round(tl["atl"], 2),
                "TL ATH": round(tl["ath"], 2),
                "TL Fark%": round(tl["atl_pct"], 2),
                "TL ATH Pot%": round(tl["ath_pot"], 1),
                "USD Fiyat": round(usd["cur"], 4) if usd else None,
                "USD ATL": round(usd["atl"], 4) if usd else None,
                "USD Fark%": round(usd["atl_pct"], 2) if usd else None,
                "USD ATH Pot%": round(usd["ath_pot"], 1) if usd else None,
                "En Yakin Endeks": best_idx["name"] if best_idx else "-",
                "Endeks Fark%": round(best_idx["atl_pct"], 2) if best_idx else None,
                "Endeks ATH Pot%": round(best_idx["ath_pot"], 1) if best_idx else None,
                "Endeks Detay": " | ".join(idx_parts) if idx_parts else "-",
                "En Yakin Grafik": best[0],
                "En Yakin Fark%": round(best[2], 2),
                "ATH Potansiyel%": round(best[3], 1),
                "Gorsel Hafiza": gh,
            })
        except Exception:
            continue

    return pd.DataFrame(results)


# ══════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════
def color_fark(val):
    if pd.isna(val):
        return ""
    v = abs(val)
    if v <= 3:
        return "background-color: #1b5e20; color: white"
    if v <= 7:
        return "background-color: #2e7d32; color: white"
    if v <= 10:
        return "background-color: #f9a825; color: black"
    if v <= 15:
        return "background-color: #e65100; color: white"
    return ""


def color_gh(val):
    if val >= 3:
        return "background-color: #1b5e20; color: white; font-weight: bold"
    if val >= 2:
        return "background-color: #2e7d32; color: white"
    if val >= 1:
        return "background-color: #f9a825; color: black"
    return "color: gray"


def main():
    # Header
    st.markdown("""
    # 📊 BIST Dip Tarama
    **Haftalik periyotta TL, USD ve Endeks bazli ATL taramasi**

    > GXSMODUJ mantigi: ATL = en dusuk kapanis, ATH = en yuksek kapanis
    """)

    # Sidebar
    with st.sidebar:
        st.header("Ayarlar")
        threshold = st.slider("ATL Esik (%)", 5, 30, 15, 1,
                              help="ATL'ye bu yuzde veya daha yakin olan hisseler listelenir")
        interval = st.selectbox("Periyot", ["1wk", "1d", "1mo"],
                                format_func=lambda x: {"1wk": "Haftalik", "1d": "Gunluk", "1mo": "Aylik"}[x])
        st.divider()
        st.markdown("""
        **Kolonlar:**
        - **TL/USD/Endeks %** = ATL'ye uzaklik
        - **ATH Pot%** = Zirveye yukselis potansiyeli
        - **GH** = Gorsel Hafiza (dipten zirveye kac kez)
        - **En Yakin** = Hangi grafikte ATL'ye en yakin
        """)

    # Tarama butonu
    if st.button("🚀 Taramayi Baslat", type="primary", use_container_width=True):
        run_full_scan(threshold, interval)
    elif "results" in st.session_state:
        show_results(st.session_state["results"], st.session_state["meta"])


def run_full_scan(threshold, interval):
    status = st.status("Tarama baslatiliyor...", expanded=True)

    # 1. Hisse listesi
    with status:
        st.write("📋 Hisse listesi aliniyor...")
    stocks = fetch_stocks()
    with status:
        st.write(f"✅ {len(stocks)} hisse bulundu")

    # 2. USDTRY
    with status:
        st.write("💱 USDTRY kuru indiriliyor...")
    usdtry = dl_single("USDTRY=X", interval)
    if usdtry is None:
        st.error("USDTRY verisi alinamadi!")
        return
    usdtry_rate = float(usdtry.iloc[-1])
    with status:
        st.write(f"✅ USDTRY: {usdtry_rate:.2f}")

    # 3. Endeksler
    with status:
        st.write("📈 Endeks verileri indiriliyor...")
    all_idx_names = set()
    for info in stocks.values():
        all_idx_names.update(info["indices"])
    all_idx_names.discard("XUTUM")  # XUTUM = XU100 proxy

    indices = {}
    for name in all_idx_names:
        s = dl_single(f"{name}.IS", interval)
        if s is not None:
            indices[name] = s
    if "XU100" in indices:
        indices["XUTUM"] = indices["XU100"]
    with status:
        st.write(f"✅ {len(indices)} endeks alindi")

    # 4. Hisse verileri
    with status:
        st.write("📊 Hisse verileri indiriliyor...")
    progress = st.progress(0, text="Basliyor...")
    stock_data = dl_batch(list(stocks.keys()), interval, 50, progress)
    progress.empty()
    with status:
        st.write(f"✅ {len(stock_data)}/{len(stocks)} hisse verisi alindi")

    # 5. Hesapla
    with status:
        st.write("🔢 ATL/ATH/Gorsel Hafiza hesaplaniyor...")
    df = run_scan(stock_data, stocks, usdtry, indices, threshold)
    with status:
        st.write(f"✅ {len(df)} hisse esik altinda")

    status.update(label=f"Tarama tamamlandi! {len(df)} hisse bulundu.", state="complete")

    meta = {
        "threshold": threshold,
        "usdtry": usdtry_rate,
        "total": len(stock_data),
        "found": len(df),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "interval": interval,
    }

    st.session_state["results"] = df
    st.session_state["meta"] = meta

    show_results(df, meta)


def show_results(df, meta):
    if df is None or len(df) == 0:
        st.warning("Esige uyan hisse bulunamadi.")
        return

    # Metrikler
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Bulunan", f"{meta['found']} hisse")
    col2.metric("Taranan", f"{meta['total']} hisse")
    col3.metric("USDTRY", f"{meta['usdtry']:.2f}")
    col4.metric("Esik", f"+/-%{meta['threshold']}")
    col5.metric("Tarih", meta["date"])

    st.divider()

    # Filtreler
    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        grafik_filtre = st.multiselect("En Yakin Grafik", df["En Yakin Grafik"].unique(),
                                        default=df["En Yakin Grafik"].unique())
    with fcol2:
        gh_min = st.number_input("Min Gorsel Hafiza", 0, 10, 0)
    with fcol3:
        sort_by = st.selectbox("Siralama", ["En Yakin Fark%", "ATH Potansiyel%", "Gorsel Hafiza", "TL Fark%", "USD Fark%"])

    # Filtrele
    filtered = df[df["En Yakin Grafik"].isin(grafik_filtre) & (df["Gorsel Hafiza"] >= gh_min)]
    ascending = sort_by != "Gorsel Hafiza" and sort_by != "ATH Potansiyel%"
    filtered = filtered.sort_values(sort_by, ascending=ascending, na_position="last")

    # Tablo
    display_cols = [
        "Hisse", "Sektor", "En Yakin Grafik", "En Yakin Fark%", "ATH Potansiyel%", "Gorsel Hafiza",
        "TL Fark%", "USD Fark%", "En Yakin Endeks", "Endeks Fark%",
        "TL Fiyat", "TL ATL", "TL ATH",
        "Dahil Endeksler", "Endeks Detay",
    ]
    show_df = filtered[display_cols].copy()

    # Stillendir
    def style_row(row):
        styles = [""] * len(row)
        for i, col in enumerate(show_df.columns):
            if col in ["TL Fark%", "USD Fark%", "Endeks Fark%", "En Yakin Fark%"]:
                styles[i] = color_fark(row[col])
            elif col == "Gorsel Hafiza":
                styles[i] = color_gh(row[col])
        return styles

    styled = show_df.style.apply(style_row, axis=1).format({
        "En Yakin Fark%": lambda x: f"%{x:.2f}" if pd.notna(x) else "",
        "ATH Potansiyel%": lambda x: f"+%{x:.0f}" if pd.notna(x) else "",
        "TL Fark%": lambda x: f"%{x:.2f}" if pd.notna(x) else "",
        "USD Fark%": lambda x: f"%{x:.2f}" if pd.notna(x) else "",
        "Endeks Fark%": lambda x: f"%{x:.2f}" if pd.notna(x) else "",
        "TL Fiyat": lambda x: f"{x:.2f}" if pd.notna(x) else "",
        "TL ATL": lambda x: f"{x:.2f}" if pd.notna(x) else "",
        "TL ATH": lambda x: f"{x:.2f}" if pd.notna(x) else "",
    })

    st.dataframe(styled, use_container_width=True, height=600)

    # Excel indirme
    st.divider()
    excel_df = filtered.copy()
    for col in ["En Yakin Fark%", "TL Fark%", "USD Fark%", "Endeks Fark%"]:
        if col in excel_df.columns:
            excel_df[col] = excel_df[col].apply(lambda x: f"%{x:.2f}" if pd.notna(x) else "")
    for col in ["ATH Potansiyel%", "TL ATH Pot%", "USD ATH Pot%", "Endeks ATH Pot%"]:
        if col in excel_df.columns:
            excel_df[col] = excel_df[col].apply(lambda x: f"+%{x:.0f}" if pd.notna(x) else "")

    from io import BytesIO
    buffer = BytesIO()
    excel_df.to_excel(buffer, index=False, sheet_name="Dip Tarama")
    st.download_button(
        "📥 Excel Indir",
        data=buffer.getvalue(),
        file_name=f"bist_dip_tarama_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    main()
