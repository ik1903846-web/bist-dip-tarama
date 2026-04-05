import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title=“BIST Tarayici”, page_icon=“📈”, layout=“wide”)
st.markdown(”# 📈 BIST Buyume Hissesi Tarayici”)
st.markdown(”**AYES Metodolojisi - TradingView verisi - Otomatik guncelleme**”)

@st.cache_data(ttl=3600, show_spinner=“Veriler yukleniyor…”)
def fetch_all():
url = “https://scanner.tradingview.com/turkey/scan”
payload = {
“columns”: [
“name”, “description”, “sector”,
“close”, “change”, “market_cap_basic”,
“price_earnings_ttm”, “price_book_ratio”,
“gross_margin”, “net_margin”, “return_on_equity”,
“revenue_change_ttm”, “earnings_change_ttm”,
“current_ratio”, “debt_to_equity”,
“performance_1y”, “performance_3y”, “performance_5y”,
“total_revenue”, “gross_profit”, “net_income”,
“free_cash_flow”, “ebitda”,
“52_week_high”,
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
        try:
            return d[i]
        except:
            return None

    price = g(3)
    high52 = g(23)
    ath_dus = round(((price - high52) / high52) * 100, 1) if price and high52 and high52 > 0 else None

    puan = 0
    sd = g(11) or 0
    nkd = g(12) or 0
    fk = g(6)
    pddd = g(7)
    roe = g(10) or 0
    nkm = g(9) or 0
    nb = g(14) or 0
    co = g(13) or 0
    sna = g(21) or 0
    g1 = g(15) or 0
    g5 = g(17)

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

    stocks.append({
        "Hisse": g(0),
        "Sirket": g(1),
        "Sektor": g(2) or "Diger",
        "Puan": puan,
        "Fiyat": price,
        "Gun%": round(g(4) or 0, 2),
        "FK": round(fk, 1) if fk and fk > 0 else None,
        "PDDD": round(pddd, 2) if pddd and pddd > 0 else None,
        "Brut Marj%": round(g(8) or 0, 1),
        "Net Marj%": round(nkm, 1),
        "ROE%": round(roe, 1),
        "Satis Buy%": round(sd, 1),
        "Kar Buy%": round(nkd, 1),
        "1Y Getiri%": round(g1, 1),
        "3Y Getiri%": round(g(16) or 0, 1),
        "5Y Getiri%": round(g5, 1) if g5 else None,
        "ATH Dusus%": ath_dus,
        "Piyasa Deg(BL)": round(g(5) / 1e9, 2) if g(5) else None,
        "Net Kar(ML)": round(g(20) / 1e6, 0) if g(20) else None,
        "FAVOK(ML)": round(g(22) / 1e6, 0) if g(22) else None,
    })

return pd.DataFrame(stocks), datetime.now().strftime("%d.%m.%Y %H:%M")
```

try:
df, guncelleme = fetch_all()
st.success(f”✅ {len(df)} hisse yuklendi - Son guncelleme: {guncelleme}”)

```
with st.expander("Filtreler", expanded=True):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        min_puan = st.slider("Min AYES Puani", 0, 90, 0, 5)
    with col2:
        sektorler = ["Tumu"] + sorted(df["Sektor"].dropna().unique().tolist())
        secili_sektor = st.selectbox("Sektor", sektorler)
    with col3:
        min_roe = st.number_input("Min ROE%", value=0.0, step=5.0)
    with col4:
        min_satis = st.number_input("Min Satis Buy%", value=0.0, step=10.0)

filtered = df[df["Puan"] >= min_puan].copy()
if secili_sektor != "Tumu":
    filtered = filtered[filtered["Sektor"] == secili_sektor]
if min_roe > 0:
    filtered = filtered[filtered["ROE%"] >= min_roe]
if min_satis > 0:
    filtered = filtered[filtered["Satis Buy%"] >= min_satis]

filtered = filtered.sort_values("Puan", ascending=False)
st.markdown(f"**{len(filtered)} hisse bulundu**")

goster = ["Hisse", "Sirket", "Sektor", "Puan", "Fiyat", "FK", "PDDD",
          "Brut Marj%", "Net Marj%", "ROE%", "Satis Buy%", "Kar Buy%",
          "1Y Getiri%", "ATH Dusus%"]

st.dataframe(
    filtered[goster].reset_index(drop=True),
    use_container_width=True,
    height=600,
    column_config={
        "Puan": st.column_config.ProgressColumn("Puan", min_value=0, max_value=100),
        "Fiyat": st.column_config.NumberColumn("Fiyat TL", format="%.2f"),
    }
)

secili = st.selectbox("Hisse detayi:", ["Sec..."] + filtered["Hisse"].tolist())
if secili != "Sec...":
    row = filtered[filtered["Hisse"] == secili].iloc[0]
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("AYES Puani", f"{row['Puan']}/100")
        st.metric("FK", row["FK"])
        st.metric("PDDD", row["PDDD"])
        st.metric("ROE%", f"{row['ROE%']}%")
    with c2:
        st.metric("Satis Buy%", f"{row['Satis Buy%']}%")
        st.metric("Kar Buy%", f"{row['Kar Buy%']}%")
        st.metric("Brut Marj%", f"{row['Brut Marj%']}%")
        st.metric("Net Marj%", f"{row['Net Marj%']}%")
    with c3:
        st.metric("1Y Getiri%", f"{row['1Y Getiri%']}%")
        st.metric("ATH Dusus%", f"{row['ATH Dusus%']}%")
        st.metric("Net Kar(ML)", row["Net Kar(ML)"])
        st.metric("FAVOK(ML)", row["FAVOK(ML)"])

buf = BytesIO()
filtered.to_excel(buf, index=False)
st.download_button("Excel Indir", buf.getvalue(),
                   f"bist_{datetime.now().strftime('%Y%m%d')}.xlsx")
```

except Exception as e:
st.error(f”Hata: {e}”)
st.info(“Sayfayi yenileyin.”)