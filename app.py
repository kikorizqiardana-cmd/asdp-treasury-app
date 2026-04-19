import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import os
import numpy as np
from datetime import datetime, timedelta
import streamlit.components.v1 as components

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="ASDP ALM Strategic Command", layout="wide", page_icon="🚢")

# --- 2. DATA MAPPING (ULTRA ROBUST) ---
MONTH_MAP_ID = {
    1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April', 5: 'Mei', 6: 'Juni',
    7: 'Juli', 8: 'Agustus', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
}
MONTH_LOOKUP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mei': 5, 'may': 5, 'jun': 6, 
    'jul': 7, 'agu': 8, 'aug': 8, 'sep': 9, 'okt': 10, 'oct': 10, 'nov': 11, 'des': 12, 'dec': 12
}

# --- 3. ENGINE DATA (PRECISION NUMERIC & DATE RADAR) ---
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
    except: return 0.0

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
            if 'bilyet' in norm or 'rekening' in norm: return 'No_Bilyet' # <-- RADAR BILYET
            return str(c).strip()
        
        df_f.columns = [map_funding_cols(c) for c in df_f.columns]

        # PENGAMAN KOLOM BILYET
        if 'No_Bilyet' not in df_f.columns:
            df_f['No_Bilyet'] = "-"
        df_f['No_Bilyet'] = df_f['No_Bilyet'].astype(str).replace('nan', '-')

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
            except: return 2026

        df_f['m_idx'] = df_f['Periode'].apply(robust_parse_month)
        df_f['year_val'] = df_f['Periode'].apply(robust_parse_year)
        df_l['m_idx'] = df_l['Periode'].apply(robust_parse_month)
        df_l['year_val'] = df_l['Periode'].apply(robust_parse_year)
        
        return df_f, df_l, None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), f"Error Parse: {str(e)}"

@st.cache_data(ttl=3600)
def get_market_history():
    try:
        data = yf.Ticker("ID10Y=F").history(period="6mo")
        if not data.empty: return data[['Close']].rename(columns={'Close': 'SBN_10Y'}).copy()
    except: pass
    return pd.DataFrame({'SBN_10Y': [6.6]}, index=[datetime.now()])

# --- 4. SIDEBAR (REALTIME CLOCK ADDED & LOCKED) ---
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
hist_m = get_market_history()
sbn_val = st.sidebar.number_input("SBN 10Y Benchmark (Live)", value=round(float(hist_m['SBN_10Y'].iloc[-1]), 2), step=0.01)
bareksa_val = st.sidebar.number_input("Bareksa (Money Market %)", value=4.75, step=0.01)
criec_val = st.sidebar.number_input("PHEI CRIEC Index (%)", value=7.20, step=0.01)

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
tab1, tab2, tab3 = st.tabs(["💰 Modul 1: Funding", "📈 Modul 2: Lending", "📊 Modul 3: ALM Resume"])

# ==========================================
# TAB 1: FUNDING (BILYET TRACKER ADDED)
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
                    # Menambahkan Nomor Bilyet ke tampilan Alert
                    for _, row in df_loss.iterrows(): st.error(f"**{row['Bank']}** | Bilyet: `{row['No_Bilyet']}` | Yield Net: `{(row['Rate']*0.8):.2f}%`")
                else: st.success("Strategi Penempatan Optimal.")
        with c_al2:
            st.subheader("⏳ Maturity Watch (H-14)")
            with st.container(height=180):
                today = datetime.now()
                df_soon = df_f[(df_f['Jatuh_Tempo'] >= today) & (df_f['Jatuh_Tempo'] <= today + timedelta(days=14))]
                if not df_soon.empty:
                    # Menambahkan Nomor Bilyet ke tampilan Maturity
                    for _, row in df_soon.iterrows(): st.warning(f"**{row['Bank']}** | Bilyet: `{row['No_Bilyet']}` | JT: `{row['Jatuh_Tempo'].strftime('%d-%m-%Y')}`")
                else: st.info("Tidak ada penempatan jatuh tempo dekat.")

        st.divider()
        st.subheader("📊 Resume Proyeksi Tambahan (Per Bulan)")
        df_proj = df_f.copy()
        df_proj['Yield_Net'] = df_proj['Rate'] * 0.8
        
        df_proj['Gap_SBN'] = net_sbn - df_proj['Yield_Net']
        df_proj['Potensi_SBN'] = (df_proj['Gap_SBN'] / 100) * df_proj['Nominal'] / 12
        tot_potensi_sbn = df_proj['Potensi_SBN'].sum()
        
        df_proj['Gap_Obligasi'] = target_bond_net - df_proj['Yield_Net']
        df_proj['Potensi_Obligasi'] = (df_proj['Gap_Obligasi'] / 100) * df_proj['Nominal'] / 12
        tot_potensi_obligasi = df_proj['Potensi_Obligasi'].sum()

        c_res1, c_res2 = st.columns(2)
        c_res1.metric("Proyeksi Tamb
