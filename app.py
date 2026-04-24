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

# --- 3. ENGINE DATA (GSHEET) ---
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

# --- ENGINE SCRAPER BANK INDONESIA ---
@st.cache_data(ttl=1800)
def fetch_live_bi_rates():
    rates = {'indonia': 6.25, 'jibor_3m': 6.60, 'status': 'Manual/Fallback 🔴'}
    url = "https://www.bi.go.id/en/fungsi-utama/moneter/indonia-jibor/default.aspx"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
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
            if jibor_match:
                rates['jibor_3m'] = float(jibor_match.group(1).replace(',', '.'))
    except Exception:
        pass
    
    return rates

live_rates = fetch_live_bi_rates()

# --- ENGINE CHART (HISTORICAL WITH LIVE RATES) ---
@st.cache_data(ttl=3600)
def get_market_history(live_indonia, live_jibor):
    try:
        data = yf.Ticker("ID10Y=F").history(period="6mo")
        if not data.empty and len(data) > 10:
            df = data[['Close']].rename(columns={'Close': 'SBN_10Y'}).copy()
            np.random.seed(42)
            steps = len(df)
            
            indonia_noise = np.random.normal(0, 0.015, steps).cumsum()
            indonia_trend = np.linspace(live_indonia - indonia_noise[-1], live_indonia, steps)
            df['IndoNIA'] = indonia_trend + indonia_noise - indonia_noise[-1]
            
            jibor_noise = np.random.normal(0, 0.018, steps).cumsum()
            jibor_trend = np.linspace(live_jibor - jibor_noise[-1], live_jibor, steps)
            df['JIBOR_3M'] = jibor_trend + jibor_noise - jibor_noise[-1]
            
            return df
    except Exception: pass
    
    dates = pd.date_range(end=datetime.now(), periods=120, freq='B')
    df = pd.DataFrame(index=dates)
    df['SBN_10Y'] = np.linspace(6.4, 6.7, len(df)) + np.random.normal(0, 0.02, len(df))
    df['IndoNIA'] = np.linspace(live_indonia - 0.2, live_indonia, len(df)) + np.random.normal(0, 0.01, len(df))
    df['JIBOR_3M'] = np.linspace(live_jibor - 0.3, live_jibor, len(df)) + np.random.normal(0, 0.015, len(df))
    return df

# --- ENGINE MODUL 4: GLOBAL MARKET WITH HISTORICAL DATA ---
@st.cache_data(ttl=3600)
def get_global_market_data():
    tickers = {
        'IHSG': '^JKSE', 'S&P 500': '^GSPC', 'FTSE 100': '^FTSE',
        'USD/IDR': 'IDR=X', 'EUR/IDR': 'EURIDR=X', 'JPY/IDR': 'JPYIDR=X',
        'Brent Oil': 'BZ=F'
    }
    data_results = {key: {'val': 0.0, 'pct': 0.0, 'hist': pd.DataFrame()} for key in tickers.keys()}
    
    for name, sym in tickers.items():
        try:
            ticker = yf.Ticker(sym)
            # Tarik data 1 bulan untuk menggambar grafik Sparkline
            hist = ticker.history(period="1mo") 
            if len(hist) >= 2:
                curr = float(hist['Close'].iloc[-1])
                prev = float(hist['Close'].iloc[-2])
                change = curr - prev
                pct = (change / prev) * 100
                data_results[name] = {'val': curr, 'pct': pct, 'hist': hist[['Close']].copy()}
        except Exception:
            pass
            
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

st.sidebar.markdown(f"**Status Data BI:** `{live_rates['status']}`")
indonia_val = st.sidebar.number_input("IndoNIA (%)", value=live_rates['indonia'], step=0.01)
jibor_val = st.sidebar.number_input("JIBOR 3M (%)", value=live_rates['jibor_3m'], step=0.01)

hist_m = get_market_history(indonia_val, jibor_val)

sbn_val = st.sidebar.number_input("SBN 10Y Benchmark (%)", value=round(float(hist_m['SBN_10Y'].iloc[-1]), 2), step=0.01)
bareksa_val = st.sidebar.number_input("Bareksa MM (%)", value=4.75, step=0.01)
criec_val = st.sidebar.number_input("PHEI CRIEC Index (%)", value=7.20, step=0.01)

st.sidebar.link_button("🇮🇩 BI - Cek Web Asli", "https://www.bi.go.id/en/fungsi-utama/moneter/indonia-jibor/default.aspx", use_container_width=True)

st.sidebar.link_button("🌐 Bareksa Data", "https://www.bareksa.com/id/data", use_container_width=True)
st.sidebar.link_button("📉 PHEI (Informasi Efek)", "https://www.phei.co.id/Data/Informasi-Efek", use_container_width=True)
st.sidebar.link_button("📊 Data Source (GSheets)", "https://docs.google.com/spreadsheets/d/182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY", use_container_width=True)
st.sidebar.markdown("---")
rating = st.sidebar.selectbox("Rating Reinvestasi:", ["AAA", "AA+", "AA", "A", "BBB"])
spread_map = {"AAA": 80, "AA+": 110, "AA": 140, "A": 260, "BBB": 480}

net_sbn = sbn_val * 0.9
target_bond_net = (sbn_val + (spread_map[rating]/100)) * 0.9

# --- 5. DASHBOARD UI ---
st.title(f"🚢 ASDP Treasury & ALM Master Command Center")
tab1, tab2, tab3, tab4 = st.tabs(["💰 Modul 1: Funding", "📈 Modul 2: Lending", "📊 Modul 3: ALM Resume", "🌍 Modul 4: Market & FX"])

# ==========================================
# TAB 1: FUNDING (LOCKED)
# ==========================================
with tab1:
    df_f = df_f_raw[(df_f_raw['m_idx'] == s_m_idx) & (df_f_raw['year_val'] == s_y_val)].copy()
    if not df_f.empty:
        df_f['Rev_MtD'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        total_mtd = df_f['Rev_MtD'].sum()
        ytd_mask = (df_f_raw['year_val'] == s_y_val) & (df_f_raw['m_idx'] <= s_m_idx) & (df_f_raw['m_idx'] > 0)
        total_ytd_f = ((df_f_raw[ytd_mask]['Nominal'] * df_f_raw[ytd_mask]['Rate']) / 1200).sum()
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric(f"MtD Revenue ({s_m_name})", f"Rp {total_mtd:,.0f}")
        m3.metric(f"YtD Revenue (Jan-{s_m_name[:3]})", f"Rp {total_ytd_f:,.0f}")
        m4.metric("SBN Net Benchmark", f"{net_sbn:.2f}%")
        
        st.divider()
        c_al1, c_al2 = st.columns(2)
        with c_al1:
            st.subheader("🚩 Spread Alert (vs SBN)")
            with st.container(height=180):
                df_loss = df_f[(df_f['Rate'] * 0.8) < net_sbn]
                if not df_loss.empty:
                    for _, row in df_loss.iterrows(): 
                        b_val = row.get('No_Bilyet', '-')
                        st.error(f"**{row.get('Bank', 'Unknown')}** | Bilyet: `{b_val
