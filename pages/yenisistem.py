import streamlit as st
import requests
import pandas as pd
import json
from datetime import datetime

st.set_page_config(page_title=“BIST Tarayıcı”, page_icon=“📈”, layout=“wide”)

st.markdown(”# 📈 BIST Büyüme Hissesi Tarayıcı”)
st.markdown(”**AYES Metodolojisi • TradingView verisi • Otomatik güncelleme**”)

@st.cache_data(ttl=3600, show_spinner=“Veriler yükleniyor…”)
def fetch_all():
url = “https://scanner.tradingview.com/turkey/scan”
payload = {
“columns”: [
“name”, “description”, “sector”, “industry”,
“close”, “change”, “volume”, “market_cap_basic”,
“price_earnings_ttm”, “price_book_ratio”,
“gross_margin”, “net_margin”, “return_on_equity”,
“revenue_change_ttm”, “earnings_change_ttm”,
“current_ratio”, “debt_to_equity”,
“performance_1y”, “performance_3y”, “performance_5y”,
“total_revenue”, “gross_profit”, “net_income”,
“total_equity”, “total_assets”, “free_cash_flow”, “ebitda”,
“52_week_high”, “52_week_low”,
],
“sort”: {“sortBy”: “market_cap_basic”, “sortOrder”: “desc”},
“range”: [0, 700],
“markets”: [“turkey”],
“options”: {“lang”: “tr”},
}
headers = {
“Content-Type”: “application/json”,
“User-Agent”: “Mozilla/5.0”,
“Origin”: “https://tr.tradingview.com”,
“Referer”: “https://tr.tradingview.com/”,
}
resp = requests.post(url, json=payload, headers=headers, timeout=30)
resp.raise_for_status()
raw = resp.json()

```
stocks = []
for item in raw.get("data", []):
    d = item["d"]
    def g(i):
        try: return d[i]
        except: return None

    price = g(4)
    high52 = g(27)
    ath_dus = round(((price - high52) / high52) * 100, 1) if price and high52 and high52 > 0 else None

    # AYES Puanlama
    puan = 0
    sd = g(13) or 0
    nkd = g(14) or 0
    fk = g(8)
    pddd = g(9)
    roe = g(12) or 0
    nkm = g(11) or 0
    nb = g(16) or 0
    co = g(15) or 0
    sna = g(25) or 0
    g1 = g(17) or 0
    g5 = g(19)

    if sd > 50: puan += 10
    elif sd > 25: puan += 8
    elif sd > 10: puan += 6
    elif sd > 0: puan += 4

    if nkd > sd * 2 and nkd > 0: puan += 10
    elif nkd > sd and nkd > 0: puan += 7
    elif nkd > 0: puan += 4

    if nkm > 15: puan += 10
    elif nkm > 8: puan += 8
    elif nkm > 3: puan += 5
    elif nkm > 0: puan += 3

    if roe > 30: puan += 10
    elif roe > 15: puan += 7
    elif roe > 5: puan += 4

    if fk and fk > 0:
        if fk < 5: puan += 8
        elif fk < 10: puan += 6
        elif fk < 15: puan += 4
        elif fk < 25: puan += 2

    if pddd and pddd > 0:
        if pddd < 1: puan += 7
        elif pddd < 2: puan += 5
        elif pddd < 3: puan += 3

    if nb < 0: puan += 10
    elif nb < 1: puan += 8
    elif nb < 2: puan += 6
    elif nb < 4: puan += 3

    if co > 2: puan += 5
    elif co > 1.5: puan += 3
    elif co > 1: puan += 1

    if sna > 0: puan += 5

    if g5 and g5 > 500: puan += 5
    elif g5 and g5 > 200: puan += 4
    elif g1 > 100: puan += 3
    elif g1 > 50: puan += 2

    sektor = g(2) or "Diğer"

    stocks.append({
        "Hisse": g(0),
        "Şirket": g(1),
        "Sektör": sektor,
        "Puan": puan,
        "Fiyat": price,
        "Gün%": round(g(5) or 0, 2),
        "F/K": round(fk, 1) if fk and fk > 0 else None,
        "PD/DD": round(pddd, 2) if pddd and pddd > 0 else None,
        "Brüt Marj%": round(g(10) or 0, 1),
        "Net Marj%": round(nkm, 1),
        "ROE%": round(roe, 1),
        "Satış Büy%": round(sd, 1),
        "Kar Büy%": round(nkd, 1),
        "1Y Getiri%": round(g1, 1),
        "3Y Getiri%": round(g(18) or 0, 1),
        "5Y Getiri%": round(g5, 1) if g5 else None,
        "Net Borç/FAVÖK": round(nb, 2),
        "Cari Oran": round(co, 2),
        "ATH'dan Düşüş%": ath_dus,
        "Piyasa Değ(B₺)": round(g(7) / 1e9, 2) if g(7) else None,
        "Satışlar(M₺)": round(g(20) / 1e6, 0) if g(20) else None,
        "Net Kar(M₺)": round(g(22) / 1e6, 0) if g(22) else None,
        "FAVÖK(M₺)": round(g(26) / 1e6, 0) if g(26) else None,
    })

return pd.DataFrame(stocks), datetime.now().strftime("%d.%m.%Y %H:%M")
```

# Ana sayfa

try:
df, guncelleme = fetch_all()

```
st.success(f"✅ {len(df)} hisse yüklendi • Son güncelleme: {guncelleme}")

# Filtreler
with st.expander("🔍 Filtreler", expanded=True):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        min_puan = st.slider("Min AYES Puanı", 0, 90, 0, 5)
    with col2:
        sektorler = ["Tümü"] + sorted(df["Sektör"].dropna().unique().tolist())
        secili_sektor = st.selectbox("Sektör", sektorler)
    with col3:
        min_roe = st.number_input("Min ROE%", value=0.0, step=5.0)
    with col4:
        min_satis_buy = st.number_input("Min Satış Büyüme%", value=0.0, step=10.0)

    col5, col6, col7 = st.columns(3)
    with col5:
        fk_range = st.slider("F/K Aralığı", 0.0, 50.0, (0.0, 50.0), 0.5)
    with col6:
        pddd_range = st.slider("PD/DD Aralığı", 0.0, 10.0, (0.0, 10.0), 0.1)
    with col7:
        ath_max = st.slider("Max ATH'dan Düşüş%", -100, 0, 0, 5)

# Filtre uygula
filtered = df[df["Puan"] >= min_puan]
if secili_sektor != "Tümü":
    filtered = filtered[filtered["Sektör"] == secili_sektor]
if min_roe > 0:
    filtered = filtered[filtered["ROE%"] >= min_roe]
if min_satis_buy > 0:
    filtered = filtered[filtered["Satış Büy%"] >= min_satis_buy]
if fk_range != (0.0, 50.0):
    fk_mask = filtered["F/K"].isna() | ((filtered["F/K"] >= fk_range[0]) & (filtered["F/K"] <= fk_range[1]))
    filtered = filtered[fk_mask]
if pddd_range != (0.0, 10.0):
    pd_mask = filtered["PD/DD"].isna() | ((filtered["PD/DD"] >= pddd_range[0]) & (filtered["PD/DD"] <= pddd_range[1]))
    filtered = filtered[pd_mask]
if ath_max < 0:
    ath_mask = filtered["ATH'dan Düşüş%"].isna() | (filtered["ATH'dan Düşüş%"] <= ath_max)
    filtered = filtered[ath_mask]

filtered = filtered.sort_values("Puan", ascending=False)

st.markdown(f"**{len(filtered)} hisse bulundu**")

# Tablo
goster = ["Hisse", "Şirket", "Sektör", "Puan", "Fiyat", "F/K", "PD/DD",
          "Brüt Marj%", "Net Marj%", "ROE%", "Satış Büy%", "Kar Büy%",
          "1Y Getiri%", "ATH'dan Düşüş%"]

st.dataframe(
    filtered[goster].reset_index(drop=True),
    use_container_width=True,
    height=600,
    column_config={
        "Puan": st.column_config.ProgressColumn("Puan", min_value=0, max_value=100),
        "Hisse": st.column_config.TextColumn("Hisse", width="small"),
        "Fiyat": st.column_config.NumberColumn("Fiyat ₺", format="%.2f"),
    }
)

# Detay
st.markdown("---")
secili = st.selectbox("Hisse detayı:", ["Seç..."] + filtered["Hisse"].tolist())
if secili != "Seç...":
    row = filtered[filtered["Hisse"] == secili].iloc[0]
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("AYES Puanı", f"{row['Puan']}/100")
        st.metric("F/K", row["F/K"])
        st.metric("PD/DD", row["PD/DD"])
        st.metric("ROE%", f"{row['ROE%']}%")
    with col2:
        st.metric("Satış Büyüme%", f"{row['Satış Büy%']}%")
        st.metric("Kar Büyüme%", f"{row['Kar Büy%']}%")
        st.metric("Brüt Marj%", f"{row['Brüt Marj%']}%")
        st.metric("Net Marj%", f"{row['Net Marj%']}%")
    with col3:
        st.metric("1Y Getiri%", f"{row['1Y Getiri%']}%")
        st.metric("ATH'dan Düşüş%", f"{row[\"ATH'dan Düşüş%\"]}%")
        st.metric("Net Kar(M₺)", row["Net Kar(M₺)"])
        st.metric("FAVÖK(M₺)", row["FAVÖK(M₺)"])

# Excel indir
from io import BytesIO
buf = BytesIO()
filtered.to_excel(buf, index=False)
st.download_button("📥 Excel İndir", buf.getvalue(),
                   f"bist_tarama_{datetime.now().strftime('%Y%m%d')}.xlsx")
```

except Exception as e:
st.error(f”Veri yüklenemedi: {e}”)
st.info(“Sayfayı yenileyin veya birkaç dakika bekleyin.”)