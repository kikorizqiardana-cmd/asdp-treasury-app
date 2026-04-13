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
st.set_page_config(page_title="ASDP Treasury Command Center", layout="wide", page_icon="🚢")

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
        if 'Jatuh_Tempo' in df_f.columns:
            df_f['Jatuh_Tempo'] = pd.to_datetime(df_f['Jatuh_Tempo'], dayfirst=True, errors='coerce')
        return df_f, df_l, None
    except Exception as e: return pd.DataFrame(), pd.DataFrame(), str(e)

def get_live_sbn():
    try:
        data = yf.Ticker("ID10Y=F").history(period="1d")
        if not data.empty: return round(float(data['Close'].iloc[-1]), 2), "Yahoo Finance (Live)"
    except: pass
    return 6.65, "Default (Manual)"

# --- 3. SIDEBAR ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/id/thumb/4/41/Logo_ASDP_Indonesia_Ferry.svg/1280px-Logo_ASDP_Indonesia_Ferry.svg.png", use_container_width=True)
st.sidebar.markdown("---")

# MODE DATA
st.sidebar.header("📡 Sumber Data")
mode_data = st.sidebar.radio("Metode Pengambilan Data:", ["Google Sheets API (Live)", "Upload File Manual"])

df_f_raw, df_l_raw = pd.DataFrame(), pd.DataFrame()
if mode_data == "Google Sheets API (Live)":
    df_f_raw, df_l_raw, err = load_gsheets_data()
    if err: st.sidebar.error(f"API Error: {err}")
    else:
        all_months = sorted(df_f_raw['Periode'].unique().tolist(), reverse=True)
        sel_month = st.sidebar.selectbox("Pilih Periode:", all_months)
        df_f = df_f_raw[df_f_raw['Periode'] == sel_month].copy()
        df_l = df_l_raw[df_l_raw['Periode'] == sel_month].copy()
else:
    f_up = st.sidebar.file_uploader("Upload Funding (Excel)", type=["xlsx"])
    if f_up: df_f = pd.read_excel(f_up)
    sel_month = "Manual Data"

# MARKET INTEL
sbn_live, sbn_source = get_live_sbn()
st.sidebar.markdown("---")
st.sidebar.header("⚙️ Market Intelligence")
current_sbn = st.sidebar.number_input(f"SBN 10Y ({sbn_source})", value=sbn_live, step=0.01)
threshold = st.sidebar.slider("Threshold Alert Spread (%)", 0.0, 5.0, 1.0)

# --- 4. DASHBOARD UI ---
st.title(f"🚢 ASDP Treasury Dashboard")
tab1, tab2, tab3 = st.tabs(["💰 Funding Intelligence", "📈 Lending Monitor", "📊 ALM Resume"])

with tab1:
    if not df_f.empty:
        # Kalkulasi
        df_f['Pendapatan_Riil'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        df_f['Net_Yield'] = df_f['Rate'] * 0.8
        net_sbn = current_sbn * 0.9
        df_f['Gap_vs_SBN'] = df_f['Net_Yield'] - net_sbn
        
        # 1. METRICS
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric(f"Total Revenue ({sel_month})", f"Rp {df_f['Pendapatan_Riil'].sum():,.0f}")
        m3.metric("Benchmark SBN Net", f"{net_sbn:.2f}%")

        st.divider()

        # 2. SCROLLABLE ALERTS
        col_alert1, col_alert2 = st.columns(2)
        
        with col_alert1:
            st.subheader("🚩 Spread Alert (Scrollable)")
            with st.container(height=200):
                df_kritis = df_f[df_f['Gap_vs_SBN'] < -threshold]
                if not df_kritis.empty:
                    for _, row in df_kritis.iterrows():
                        st.error(f"**{row['Bank']}** | Gap: `{row['Gap_vs_SBN']:.2f}%` | Rate: {row['Rate']:.2f}%")
                else:
                    st.success("✅ Seluruh yield bilyet masih dalam batas aman.")

        with col_alert2:
            st.subheader("⏳ Maturity Alert (Scrollable)")
            with st.container(height=200):
                today = datetime.now()
                # Alert jika jatuh tempo dalam 7 hari ke depan
                h7 = today + timedelta(days=7)
                df_jatuh_tempo = df_f[(df_f['Jatuh_Tempo'] >= today) & (df_f['Jatuh_Tempo'] <= h7)]
                
                if not df_jatuh_tempo.empty:
                    for _, row in df_jatuh_tempo.iterrows():
                        tgl_str = row['Jatuh_Tempo'].strftime('%d-%m-%Y')
                        st.warning(f"**{row['Bank']}** | Jatuh Tempo: `{tgl_str}` | Rp {row['Nominal']:,.0f}")
                else:
                    st.info("📅 Tidak ada bilyet yang jatuh tempo dalam 7 hari ke depan.")

        st.divider()

        # 3. CHARTS (BAR & PIE)
        st.subheader("📊 Portfolio Visual Analytics")
        c1, c2 = st.columns([2, 1])
        with c1:
            df_bank_rev = df_f.groupby('Bank')['Pendapatan_Riil'].sum().reset_index()
            fig_bar = px.bar(df_bank_rev, x='Bank', y='Pendapatan_Riil', color='Bank',
                             title="Total Revenue per Bank (IDR)", text_auto=',.0f')
            st.plotly_chart(fig_bar, use_container_width=True)
        with c2:
            fig_pie = px.pie(df_f, values='Nominal', names='Bank', hole=0.4, 
                             title="Konsentrasi Dana (%)")
            st.plotly_chart(fig_pie, use_container_width=True)

        # 4. TABEL DETAIL
        with st.expander("📑 Detail Tabel Inventori Funding"):
            df_disp = df_f.copy()
            df_disp['Jatuh_Tempo'] = df_disp['Jatuh_Tempo'].apply(lambda x: x.strftime('%d-%m-%Y') if pd.notnull(x) else '-')
            st.dataframe(df_disp, use_container_width=True)

with tab2:
    if not df_l.empty:
        st.subheader("Lending & Cost of Fund Analytics")
        st.dataframe(df_l, use_container_width=True)

with tab3:
    if not df_f.empty:
        st.subheader("ALM Resume & Net Interest Position")
        rev_in = df_f['Pendapatan_Riil'].sum()
        st.metric("Total Monthly Revenue (Inflow)", f"Rp {rev_in:,.0f}")
