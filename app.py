import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import os
import numpy as np
from datetime import datetime, timedelta
import streamlit.components.v1 as components
import requests
import re

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="ASDP ALM Strategic Command", layout="wide", page_icon="🚢")

# --- 2. DATA MAPPING ---
MONTH_MAP_ID = {
    1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April', 5: 'Mei', 6: 'Juni',
    7: 'Juli', 8: 'Agustus', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
}
MONTH_LOOKUP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mei': 5, 'may': 5, 'jun': 6, 
    'jul': 7, 'agu': 8, 'aug': 8, 'sep': 9, 'okt': 10, 'oct': 10, 'nov': 11, 'des': 12, 'dec': 12
}

# --- 3. ENGINE DATA ---
def clean_numeric_robust(val):
    if pd.isna(val): return 0.0
    val_str = str(val).strip().replace('Rp', '').replace('%', '').replace(' ', '')
    if not val_str or val_str.lower() == 'nan': return 0.0
    if ',' in val_str and '.' in val_str: val_str = val_str.replace('.', '').replace(',', '.')
    elif ',' in val_str: val_str = val_str.replace(',', '.')
    elif '.' in val_str: 
        parts = val_str.split('.')
        if len(parts[-1]) == 3: val_str = val_str.replace('.', '')
    try: return float(val_str)
    except Exception: return 0.0

@st.cache_data(ttl=1)
def load_gsheets_data():
    sheet_id = "182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY"
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet="
    try:
        df_f_raw = pd.read_csv(base_url + "Funding")
        df_l_raw = pd.read_csv(base_url + "Lending")
        df_f = df_f_raw.dropna(subset=['Periode']).copy()
        df_l = df_l_raw.dropna(subset=['Periode']).copy()
        def map_lending_cols(c):
            norm = " ".join(str(c).strip().lower().split())
            if 'bank' in norm or 'kreditur' in norm: return 'Kreditur'
            if 'rate' in norm or 'suku' in norm: return 'Lending_Rate'
            if 'sisa' in norm or 'outstanding' in norm: return 'Outstanding'
            if 'tipe' in norm or 'jenis' in norm: return 'Tipe'
            if 'nominal' in norm or 'jumlah' in norm: return 'Nominal_Lending'
            if 'jatuh' in norm and 'tempo' in norm: return 'Jatuh_Tempo'
            return str(c).strip()
        df_l.columns = [map_lending_cols(c) for c in df_l.columns]
        def map_funding_cols(c):
            norm = " ".join(str(c).strip().lower().split())
            if 'rate' in norm: return 'Rate'
            if 'bank' in norm or 'kreditur' in norm: return 'Bank'
            if 'nominal' in norm: return 'Nominal'
            if 'jatuh' in norm and 'tempo' in norm: return 'Jatuh_Tempo'
            if 'bilyet' in norm or 'rekening' in norm: return 'No_Bilyet'
            return str(c).strip()
        df_f.columns = [map_funding_cols(c) for c in df_f.columns]
        if 'No_Bilyet' not in df_f.columns: df_f['No_Bilyet'] = "-"
        df_f['No_Bilyet'] = df_f['No_Bilyet'].fillna("-").astype(str).replace('nan', '-')
        for col in ['Nominal', 'Rate']:
            if col in df_f.columns: df_f[col] = df_f[col].apply(clean_numeric_robust)
        for col in ['Lending_Rate', 'Outstanding', 'Nominal_Lending']:
            if col in df_l.columns: df_l[col] = df_l[col].apply(clean_numeric_robust)
        if 'Jatuh_Tempo' in df_f.columns: df_f['Jatuh_Tempo'] = pd.to_datetime(df_f['Jatuh_Tempo'], dayfirst=True, errors='coerce')
        if 'Jatuh_Tempo' in df_l.columns: df_l['Jatuh_Tempo'] = pd.to_datetime(df_l['Jatuh_Tempo'], dayfirst=True, errors='coerce')
        def robust_parse_month(p):
            p_clean = str(p).lower().replace('-', ' ').strip()
            for key, val in MONTH_LOOKUP.items():
                if key in p_clean: return val
            return 0
        def robust_parse_year(p):
            try:
                pts = str(p).replace('-', ' ').strip().split()
                return int(pts[1]) if len(pts) > 1 else 2026
            except Exception: return 2026
        df_f['m_idx'] = df_f['Periode'].apply(robust_parse_month)
        df_f['year_val'] = df_f['Periode'].apply(robust_parse_year)
        df_l['m_idx'] = df_l['Periode'].apply(robust_parse_month)
        df_l['year_val'] = df_l['Periode'].apply(robust_parse_year)
        return df_f, df_l, None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), f"Error Parse: {str(e)}"

# --- SCRAPER BI ---
@st.cache_data(ttl=1800)
def fetch_live_bi_rates():
    rates = {'indonia': 6.25, 'jibor_3m': 6.60, 'status': 'Manual/Fallback 🔴'}
    url = "https://www.bi.go.id/en/fungsi-utama/moneter/indonia-jibor/default.aspx"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/114.0.0.0 Safari/537.36'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            clean_text = re.sub(r'<[^>]+>', ' ', res.text)
            clean_text = re.sub(r'\s+', ' ', clean_text)
            indonia_match = re.search(r'INDONIA\s*\(\%\)\s*([\d\.\,]+)', clean_text, re.IGNORECASE)
            if indonia_match:
                rates['indonia'] = float(indonia_match.group(1).replace(',', '.'))
                rates['status'] = 'Live Auto-Scraped 🟢'
            jibor_match = re.search(r'3\s*Month\s*([\d\.\,]+)', clean_text, re.IGNORECASE)
            if jibor_match: rates['jibor_3m'] = float(jibor_match.group(1).replace(',', '.'))
    except Exception: pass
    return rates

# --- GLOBAL MARKET ENGINE ---
@st.cache_data(ttl=3600)
def get_global_market_data():
    tickers = {
        'IHSG': '^JKSE', 'S&P 500': '^GSPC', 'FTSE 100': '^FTSE',
        'USD/IDR': 'IDR=X', 'EUR/IDR': 'EURIDR=X', 'JPY/IDR': 'JPYIDR=X',
        'Brent Oil': 'BZ=F'
    }
    data_results = {}
    for name, sym in tickers.items():
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="2d")
            if len(hist) >= 2:
                curr = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                change = curr - prev
                pct = (change / prev) * 100
                data_results[name] = {'val': curr, 'pct': pct}
        except: data_results[name] = {'val': 0, 'pct': 0}
    return data_results

# --- 4. SIDEBAR ---
logo_path = "ferry.png"
if os.path.exists(logo_path): st.sidebar.image(logo_path, use_container_width=True)

with st.sidebar:
    clock_html = """
    <div style="text-align: center; background-color: #f0f2f6; padding: 10px; border-radius: 8px; border: 1px solid #ddd; margin-bottom: 10px;">
        <p id="clock" style="font-family: 'Courier New', Courier, monospace; font-size: 18px; font-weight: bold; color: #1f77b4; margin: 0;"></p>
    </div>
    <script>
        function updateTime() {
            var now = new Date();
            var options = { weekday: 'long', year: 'numeric', month: 'short', day: 'numeric' };
            var dateStr = now.toLocaleDateString('id-ID', options);
            var timeStr = now.toLocaleTimeString('id-ID', { hour12: false });
            document.getElementById('clock').innerHTML = dateStr + '<br>' + timeStr + ' WIB';
        }
        setInterval(updateTime, 1000);
        updateTime();
    </script>
    """
    components.html(clock_html, height=75)

st.sidebar.markdown("---")
st.sidebar.header("📅 Periode Analisis")
sel_date = st.sidebar.date_input("Pilih Bulan & Tahun:", value=datetime(2026, 3, 1))
s_m_idx, s_y_val = int(sel_date.month), int(sel_date.year)
s_m_name = MONTH_MAP_ID[s_m_idx]

df_f_raw, df_l_raw, err = load_gsheets_data()
if err: st.error(err); st.stop()

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Market Intelligence")
live_rates = fetch_live_bi_rates()
indonia_val = st.sidebar.number_input("IndoNIA (%)", value=live_rates['indonia'], step=0.01)
jibor_val = st.sidebar.number_input("JIBOR 3M (%)", value=live_rates['jibor_3m'], step=0.01)
sbn_val = st.sidebar.number_input("SBN 10Y Benchmark (%)", value=6.65, step=0.01)
rating = st.sidebar.selectbox("Rating Reinvestasi:", ["AAA", "AA+", "AA", "A", "BBB"])
spread_map = {"AAA": 80, "AA+": 110, "AA": 140, "A": 260, "BBB": 480}
net_sbn = sbn_val * 0.9
target_bond_net = (sbn_val + (spread_map[rating]/100)) * 0.9

# --- 5. DASHBOARD UI ---
st.title(f"🚢 ASDP Treasury & ALM Master Command Center")
tab1, tab2, tab3, tab4 = st.tabs(["💰 Modul 1", "📈 Modul 2", "📊 Modul 3", "🌍 Modul 4: Market & FX"])

# MODUL 1, 2, 3 (LOCKED - TIDAK ADA PERUBAHAN LOGIKA)
with tab1:
    df_f = df_f_raw[(df_f_raw['m_idx'] == s_m_idx) & (df_f_raw['year_val'] == s_y_val)].copy()
    if not df_f.empty:
        df_f['Rev_MtD'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric(f"MtD Revenue ({s_m_name})", f"Rp {df_f['Rev_MtD'].sum():,.0f}")
        m4.metric("SBN Net Benchmark", f"{net_sbn:.2f}%")
        st.divider()
        c_res1, c_res2 = st.columns(2)
        df_proj = df_f.copy()
        df_proj['Yield_Net'] = df_proj['Rate'] * 0.8
        df_proj['Potensi_SBN'] = ((net_sbn - df_proj['Yield_Net']) / 100) * df_proj['Nominal'] / 12
        df_proj['Potensi_Obligasi'] = ((target_bond_net - df_proj['Yield_Net']) / 100) * df_proj['Nominal'] / 12
        c_res1.metric("Proyeksi Tambahan ke SBN", f"Rp {df_proj['Potensi_SBN'].sum():,.0f}")
        c_res2.metric("Proyeksi Tambahan ke Obligasi", f"Rp {df_proj['Potensi_Obligasi'].sum():,.0f}")
        st.divider()
        st.plotly_chart(px.bar(df_f.groupby('Bank')['Rev_MtD'].sum().reset_index(), x='Bank', y='Rev_MtD', title="Revenue per Bank (MtD)", text_auto=',.0f'), use_container_width=True)
    else: st.warning("Data Funding tidak ditemukan.")

with tab2:
    df_l = df_l_raw[(df_l_raw['m_idx'] == s_m_idx) & (df_l_raw['year_val'] == s_y_val)].copy()
    if not df_l.empty:
        is_bunga_mtd = df_l['Tipe'].astype(str).str.contains('bunga|margin|fee', case=False, na=False)
        l1, l2, l3, l4 = st.columns(4)
        l1.metric("Total Outstanding", f"Rp {df_l.groupby('Kreditur')['Outstanding'].max().sum():,.0f}")
        l2.metric(f"MtD Bayar ({s_m_name})", f"Rp {df_l['Nominal_Lending'].sum():,.0f}")
        l4.metric("Avg Yield Lending", f"{df_l['Lending_Rate'].mean():.2f}%")
        st.divider()
        st.plotly_chart(px.bar(df_l, x='Kreditur', y='Nominal_Lending', color='Tipe', title="Breakdown Pembayaran Bulanan"), use_container_width=True)
    else: st.warning("Data Lending tidak ditemukan.")

with tab3:
    st.subheader(f"📊 ALM Strategic Intelligence - {s_m_name}")
    ytd_mask_f = (df_f_raw['year_val'] == s_y_val) & (df_f_raw['m_idx'] <= s_m_idx) & (df_f_raw['m_idx'] > 0)
    ytd_rev = ((df_f_raw[ytd_mask_f]['Nominal'] * df_f_raw[ytd_mask_f]['Rate']) / 1200).sum()
    ytd_mask_l = (df_l_raw['year_val'] == s_y_val) & (df_l_raw['m_idx'] <= s_m_idx) & (df_l_raw['m_idx'] > 0)
    is_bunga_ytd = df_l_raw[ytd_mask_l]['Tipe'].astype(str).str.contains('bunga|margin|fee', case=False, na=False)
    ytd_bunga_out = df_l_raw[ytd_mask_l].loc[is_bunga_ytd, 'Nominal_Lending'].sum()
    icr_val = (ytd_rev / ytd_bunga_out) if ytd_bunga_out > 0 else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("YtD Interest Revenue", f"Rp {ytd_rev:,.0f}")
    c2.metric("YtD Interest Outflow", f"Rp {ytd_bunga_out:,.0f}")
    c4.metric("ICR Strength (YtD)", f"{icr_val:.2f}x")
    st.divider()
    st.subheader("📈 6-Month Market Trend")
    plot_df = yf.Ticker("ID10Y=F").history(period="6mo")[['Close']].rename(columns={'Close': 'SBN'})
    plot_df['IndoNIA'] = indonia_val
    plot_df['JIBOR_3M'] = jibor_val
    f_alm = go.Figure()
    f_alm.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SBN'], name='SBN 10Y', line=dict(color='blue', width=3)))
    f_alm.add_trace(go.Scatter(x=plot_df.index, y=plot_df['IndoNIA'], name='IndoNIA (Live)', line=dict(dash='dash', color='purple')))
    f_alm.add_trace(go.Scatter(x=plot_df.index, y=plot_df['JIBOR_3M'], name='JIBOR 3M (Live)', line=dict(dash='dot', color='green')))
    st.plotly_chart(f_alm, use_container_width=True)

# ==========================================
# NEW TAB 4: GLOBAL MARKET & FX MONITOR
# ==========================================
with tab4:
    st.header("🌍 Global Market & FX Real-Time Monitor")
    g_data = get_global_market_data()
    
    # 1. ROW: GLOBAL INDICES
    st.subheader("📈 Stock Indices")
    idx1, idx2, idx3 = st.columns(3)
    with idx1:
        st.metric("🇮🇩 IHSG (Jakarta)", f"{g_data['IHSG']['val']:,.2f}", f"{g_data['IHSG']['pct']:.2f}%")
    with idx2:
        st.metric("🇺🇸 S&P 500 (Wall St)", f"{g_data['S&P 500']['val']:,.2f}", f"{g_data['S&P 500']['pct']:.2f}%")
    with idx3:
        st.metric("🇬🇧 FTSE 100 (London)", f"{g_data['FTSE 100']['val']:,.2f}", f"{g_data['FTSE 100']['pct']:.2f}%")
    
    st.divider()
    
    # 2. ROW: FOREX & COMMODITY
    st.subheader("💵 Forex & Commodities")
    fx1, fx2, fx3, oil = st.columns(4)
    with fx1:
        st.metric("🇺🇸 USD / IDR", f"Rp {g_data['USD/IDR']['val']:,.2f}", f"{g_data['USD/IDR']['pct']:.2f}%", delta_color="inverse")
    with fx2:
        st.metric("🇪🇺 EUR / IDR", f"Rp {g_data['EUR/IDR']['val']:,.2f}", f"{g_data['EUR/IDR']['pct']:.2f}%", delta_color="inverse")
    with fx3:
        st.metric("🇯🇵 JPY / IDR", f"Rp {g_data['JPY/IDR']['val']:,.2f}", f"{g_data['JPY/IDR']['pct']:.2f}%", delta_color="inverse")
    with oil:
        # Brent Oil sangat vital untuk operasional kapal ASDP
        st.metric("🛢️ Brent Crude Oil", f"USD {g_data['Brent Oil']['val']:,.2f}", f"{g_data['Brent Oil']['pct']:.2f}%", delta_color="inverse")

    st.divider()
    st.info("💡 **Tips Strategic:** Perhatikan pergerakan **Brent Oil** dan **USD/IDR**. Kenaikan pada kedua instrumen ini biasanya berdampak langsung pada kenaikan biaya operasional (BBM & Spareparts) kapal.")
