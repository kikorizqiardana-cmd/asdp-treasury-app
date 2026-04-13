import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import requests
import os
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
        
        for c in ['Nominal', 'Rate']:
            if c in df_f.columns: df_f[c] = clean_numeric_robust(df_f[c])
        
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
logo_path = "ferry.png"
if os.path.exists(logo_path): st.sidebar.image(logo_path, use_container_width=True)
st.sidebar.markdown("---")

# DATA LOADING
df_f_raw, df_l_raw, err = load_gsheets_data()
if err: st.sidebar.error(f"API Error: {err}")
else:
    all_months = sorted(df_f_raw['Periode'].unique().tolist(), reverse=True)
    sel_month = st.sidebar.selectbox("Pilih Periode Analisis:", all_months)
    df_f = df_f_raw[df_f_raw['Periode'] == sel_month].copy()

# MARKET INTEL & BOND SIMULATOR
st.sidebar.header("⚙️ Market Intelligence")
sbn_val, sbn_source = get_live_sbn()
current_sbn = st.sidebar.number_input(f"SBN 10Y Benchmark ({sbn_source})", value=sbn_live_val if 'sbn_live_val' in locals() else sbn_val, step=0.01)

st.sidebar.markdown("---")
st.sidebar.header("🏢 Corporate Bond Simulator")
rating = st.sidebar.selectbox("Pilih Rating Target:", ["AAA", "AA+", "AA", "A", "BBB"])

# Spread Mapper (Bps over SBN) - Estimasi Market 2026
spread_map = {"AAA": 75, "AA+": 100, "AA": 130, "A": 250, "BBB": 450}
selected_spread = st.sidebar.slider(f"Spread {rating} (bps)", 0, 600, spread_map[rating])

# Kalkulasi Target Yield (Bond Yield = SBN + Spread)
target_yield_bond = current_sbn + (selected_spread / 100)
st.sidebar.info(f"Proyeksi Yield {rating}: **{target_yield_bond:.2f}%**")

# --- 4. DASHBOARD UI ---
st.title(f"🚢 ASDP Treasury & Investment Dashboard")
tab1, tab2 = st.tabs(["💰 Funding & Bond Projection", "📈 Lending Monitor"])

with tab1:
    if not df_f.empty:
        # Kalkulasi Dasar
        df_f['Net_Yield'] = df_f['Rate'] * 0.8  # Pajak Deposito 20%
        net_sbn = current_sbn * 0.9           # Pajak SBN 10%
        net_bond = target_yield_bond * 0.9    # Pajak Obligasi/Sukuk 10%
        df_f['Pendapatan_Riil'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        
        # 1. METRICS PROYEKSI
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric(f"Net Yield SBN", f"{net_sbn:.2f}%")
        m3.metric(f"Net Yield {rating} Bond", f"{net_bond:.2f}%", delta=f"{(net_bond - net_sbn):.2f}% vs SBN")

        st.divider()

        # 2. ALERTS (SCROLLABLE)
        c_a1, c_a2 = st.columns(2)
        with c_a1:
            st.subheader("🚩 Opportunity Loss Alert")
            with st.container(height=200):
                # Filter deposito yang yield-nya lebih kecil dari target Bond
                df_loss = df_f[df_f['Net_Yield'] < net_bond]
                if not df_loss.empty:
                    for _, row in df_loss.iterrows():
                        gap = net_bond - row['Net_Yield']
                        st.error(f"**{row['Bank']}** | Gap: `{gap:.2f}%` vs {rating}")
                else: st.success("Yield deposito sudah optimal.")

        with c_a2:
            st.subheader("⏳ Maturity Watch")
            with st.container(height=200):
                today = datetime.now()
                df_soon = df_f[(df_f['Jatuh_Tempo'] >= today) & (df_f['Jatuh_Tempo'] <= today + timedelta(days=14))]
                if not df_soon.empty:
                    for _, row in df_soon.iterrows():
                        st.warning(f"**{row['Bank']}** | `{row['Jatuh_Tempo'].strftime('%d-%m-%Y')}`")
                else: st.info("Tidak ada jatuh tempo dekat (14 hari).")

        st.divider()

        # 3. PROJECTION CHARTS
        st.subheader(f"📊 Proyeksi Yield: Reinvestment ke {rating} Corporate Bond")
        v1, v2 = st.columns([2, 1])
        with v1:
            # Chart Perbandingan Yield
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_f.index, y=df_f['Net_Yield'], name='Existing Depo Net', marker_color='gray'))
            fig.add_hline(y=net_sbn, line_dash="dash", line_color="blue", annotation_text="SBN Net")
            fig.add_hline(y=net_bond, line_dash="dot", line_color="green", annotation_text=f"Bond {rating} Net")
            fig.update_layout(title="Existing Yield vs Reinvestment Target", yaxis_title="Yield (%)")
            st.plotly_chart(fig, use_container_width=True)
            
        with v2:
            # Pie Chart Revenue Contribution
            fig_pie = px.pie(df_f, values='Pendapatan_Riil', names='Bank', hole=0.4, title="Revenue Contribution per Bank")
            st.plotly_chart(fig_pie, use_container_width=True)

        # 4. TABEL DETAIL
        with st.expander("📑 Lihat Detail Inventori & Spread"):
            df_disp = df_f.copy()
            df_disp['Spread_vs_Bond'] = df_disp['Net_Yield'] - net_bond
            df_disp['Jatuh_Tempo'] = df_disp['Jatuh_Tempo'].apply(lambda x: x.strftime('%d-%m-%Y') if pd.notnull(x) else '-')
            st.dataframe(df_disp.style.format({'Net_Yield': '{:.2f}%', 'Spread_vs_Bond': '{:.2f}%'}), use_container_width=True)

with tab2:
    if not df_l_raw.empty:
        st.subheader("Lending & ALM Summary")
        st.dataframe(df_l_raw, use_container_width=True)
