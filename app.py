import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from streamlit_lottie import st_lottie
import requests
import time
from datetime import datetime, timedelta

# --- 1. CONFIG HALAMAN ---
st.set_page_config(page_title="ASDP ALM Command Center", layout="wide", page_icon="🚢")

# --- FUNGSI AMBIL DATA SBN LIVE ---
def get_live_sbn():
    try:
        # Ticker untuk Indonesia 10 Years Bond Yield
        ticker = yf.Ticker("ID10Y=F")
        data = ticker.history(period="1d")
        if not data.empty:
            live_val = round(float(data['Close'].iloc[-1]), 2)
            return live_val, "Yahoo Finance (Live)"
    except:
        pass
    return 6.65, "Default (API Error)"

# --- 2. DATA ENGINE ---
def clean_numeric_robust(series):
    def process_val(val):
        val = str(val).strip().replace('Rp', '').replace('%', '').replace(' ', '')
        if not val or val == 'nan' or val == 'None': return "0"
        commas, dots = val.count(','), val.count('.')
        if commas > 0 and dots > 0:
            if val.rfind(',') > val.rfind('.'): return val.replace('.', '').replace(',', '.')
            else: return val.replace(',', '')
        if commas > 0:
            if commas > 1 or len(val.split(',')[-1]) == 3: return val.replace(',', '')
            else: return val.replace(',', '.')
        if dots > 0:
            if dots > 1 or len(val.split('.')[-1]) == 3: return val.replace('.', '')
        return val
    return pd.to_numeric(series.apply(process_val), errors='coerce').fillna(0)

@st.cache_data(ttl=1)
def load_gsheets_data():
    sheet_id = "182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY"
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet="
    try:
        df_f = pd.read_csv(base_url + "Funding")
        df_l = pd.read_csv(base_url + "Lending")
        df_f.columns = [c.strip() for c in df_f.columns]
        df_l.columns = [c.strip() for c in df_l.columns]
        
        if 'Debitur' in df_l.columns: df_l.rename(columns={'Debitur': 'Kreditur'}, inplace=True)
        if 'Rate (%)' in df_f.columns: df_f.rename(columns={'Rate (%)': 'Rate'}, inplace=True)
        if 'Nominal' in df_l.columns: df_l.rename(columns={'Nominal': 'Nominal_Lending'}, inplace=True)
        
        for c in ['Nominal', 'Rate']:
            if c in df_f.columns: df_f[c] = clean_numeric_robust(df_f[c])
        for c in ['Nominal_Lending', 'Lending_Rate (%)', 'Cost_of_Fund (%)']:
            if c in df_l.columns: df_l[c] = clean_numeric_robust(df_l[c])
        
        if 'Periode' in df_f.columns: df_f['Periode'] = df_f['Periode'].astype(str).str.strip()
        if 'Periode' in df_l.columns: df_l['Periode'] = df_l['Periode'].astype(str).str.strip()
            
        if 'Jatuh_Tempo' in df_f.columns:
            df_f['Jatuh_Tempo'] = pd.to_datetime(df_f['Jatuh_Tempo'], dayfirst=True, errors='coerce')
        return df_f, df_l, None
    except Exception as e: return pd.DataFrame(), pd.DataFrame(), str(e)

# --- 3. SIDEBAR ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/id/thumb/4/41/Logo_ASDP_Indonesia_Ferry.svg/1280px-Logo_ASDP_Indonesia_Ferry.svg.png", use_container_width=True)
st.sidebar.markdown("---")

# MODE DATA
st.sidebar.header("📡 Sumber Data")
mode_data = st.sidebar.radio("Metode Pengambilan Data:", ["Google Sheets API (Live)", "Upload File Manual"])

# INVENTORI DATA
df_f, df_l = pd.DataFrame(), pd.DataFrame()
current_month = "All"

if mode_data == "Google Sheets API (Live)":
    df_f_raw, df_l_raw, err = load_gsheets_data()
    if err:
        st.sidebar.error(f"API Error: {err}")
    else:
        st.sidebar.success("✅ Connected to GSheets")
        all_months = sorted(list(set(df_f_raw['Periode'].unique()) | set(df_l_raw['Periode'].unique())), reverse=True)
        current_month = st.sidebar.selectbox("Pilih Periode Analisis:", all_months)
        df_f = df_f_raw[df_f_raw['Periode'] == current_month].copy()
        df_l = df_l_raw[df_l_raw['Periode'] == current_month].copy()
else:
    f_up = st.sidebar.file_uploader("Upload Funding (Excel)", type=["xlsx"])
    l_up = st.sidebar.file_uploader("Upload Lending (Excel)", type=["xlsx"])
    if f_up: 
        df_f = pd.read_excel(f_up)
        for c in ['Nominal', 'Rate']:
            if c in df_f.columns: df_f[c] = clean_numeric_robust(df_f[c])
    if l_up: 
        df_l = pd.read_excel(l_up)
        for c in ['Nominal_Lending', 'Lending_Rate (%)', 'Cost_of_Fund (%)']:
            if c in df_l.columns: df_l[c] = clean_numeric_robust(df_l[c])
    current_month = "Manual Upload"

st.sidebar.markdown("---")
# MARKET DATA LIVE
st.sidebar.header("⚙️ Market Intelligence")
sbn_live_val, sbn_source = get_live_sbn()
current_sbn = st.sidebar.number_input(f"Benchmark SBN 10Y ({sbn_source})", value=sbn_live_val, step=0.01, format="%.2f")
threshold = st.sidebar.slider("Threshold Pindah Dana (%)", 0.0, 5.0, 0.5)

st.sidebar.markdown("---")
# RISK SIMULATION
st.sidebar.header("🛡️ Credit Risk Simulation")
rating_pilihan = st.sidebar.selectbox("Pilih Rating Simulasi:", ["AAA", "AA+", "AA", "A"])
risk_notes = {
    "AAA": {"spread": 80, "desc": "🛡️ Stabil & Aman. Kapasitas bayar sangat kuat."},
    "AA+": {"spread": 100, "desc": "✅ Sangat Kuat. Kapasitas finansial sangat tinggi."},
    "AA": {"spread": 120, "desc": "✅ Kualitas Tinggi. Risiko sedikit lebih tinggi dari AAA."},
    "A": {"spread": 260, "desc": "🚨 Sensitif. Cukup aman namun rentan kondisi ekonomi."}
}
selected_spread = st.sidebar.slider(f"Spread {rating_pilihan} (bps)", 30, 450, risk_notes[rating_pilihan]["spread"])
est_yield_bond = current_sbn + (selected_spread/100)

# --- 4. DASHBOARD UI ---
st.title(f"🚢 PT ASDP Indonesia Ferry - Treasury Dashboard")
tab1, tab2, tab3 = st.tabs(["💰 Funding Monitor", "📈 Lending Monitor", "📊 ALM Resume"])

# TAB 1: FUNDING
with tab1:
    if not df_f.empty:
        # Perhitungan Revenue & Yield
        df_f['Pendapatan_Riil'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        df_f['Net_Yield'] = df_f['Rate'] * 0.8
        net_sbn = current_sbn * 0.9
        net_sim = est_yield_bond * 0.9
        df_f['Gap_vs_SBN'] = df_f['Net_Yield'] - net_sbn
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric("Total Revenue Bunga (B)", f"Rp {df_f['Pendapatan_Riil'].sum()/1e9:.2f} B")
        m3.metric("Live SBN Net", f"{net_sbn:.2f}%")

        st.subheader(f"⚠️ Asesmen Risiko: {rating_pilihan}")
        if rating_pilihan == "A":
            st.error(f"**WARNING:** Rating A memiliki risiko degradasi lebih tinggi saat ekonomi goyang.")
        else:
            st.warning(f"**PROFIL:** {risk_notes[rating_pilihan]['desc']}")

        st.divider()

        c1, c2 = st.columns(2)
        df_pindah = df_f[df_f['Net_Yield'] < (net_sbn - threshold)]
        pot_sbn = (df_pindah['Nominal'] * (net_sbn - df_pindah['Net_Yield'])/100).sum()
        pot_sim = (df_pindah['Nominal'] * (net_sim - df_pindah['Net_Yield'])/100).sum()
        c1.metric("Potensi Tambahan (Pindah SBN)", f"Rp {pot_sbn:,.0f}")
        c2.metric(f"Potensi Tambahan (Pindah {rating_pilihan})", f"Rp {pot_sim:,.0f}")

        v1, v2 = st.columns([2, 1])
        with v1:
            fig_rev = px.bar(df_f.groupby('Bank')['Pendapatan_Riil'].sum().reset_index(), 
                             x='Bank', y='Pendapatan_Riil', color='Bank', title="Revenue per Bank (IDR)")
            st.plotly_chart(fig_rev, use_container_width=True)
        with v2:
            fig_pie = px.pie(df_f, values='Nominal', names=df_f.columns[0], hole=0.4, title="Komposisi Portofolio")
            st.plotly_chart(fig_pie, use_container_width=True)

        with st.expander("📑 Tabel Detail Funding", expanded=True):
            df_disp = df_f.copy()
            if 'Jatuh_Tempo' in df_disp.columns:
                df_disp['Jatuh_Tempo'] = df_disp['Jatuh_Tempo'].apply(lambda x: x.strftime('%d-%m-%Y') if pd.notnull(x) and hasattr(x, 'strftime') else '-')
            st.dataframe(df_disp.style.format({'Nominal': '{:,.0f}', 'Pendapatan_Riil': '{:,.0f}'}), use_container_width=True)
    else:
        st.info("Muat data melalui API atau Upload untuk melihat dashboard.")

# TAB 2 & 3 tetap sama dengan logika v7.6
with tab2:
    if not df_l.empty:
        df_l['Bunga_Keluar'] = (df_l['Nominal_Lending'] * (df_l['Cost_of_Fund (%)']/100)) / 12
        st.subheader("Monitoring Lending")
        st.dataframe(df_l, use_container_width=True)

with tab3:
    if not df_f.empty and not df_l.empty:
        st.subheader("ALM Resume")
        nip = df_f['Pendapatan_Riil'].sum() - (df_l['Nominal_Lending'] * (df_l['Cost_of_Fund (%)']/100) / 12).sum()
        st.metric("Net Interest Position (Monthly Surplus)", f"Rp {nip:,.0f}")
