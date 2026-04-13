import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_lottie import st_lottie
import requests
import time
from datetime import datetime, timedelta

# --- 1. CONFIG HALAMAN ---
st.set_page_config(page_title="ASDP ALM Revenue Center", layout="wide", page_icon="🚢")

# --- 2. DATA ENGINE (ANTI-CRASH) ---
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
        # Load Tabs
        df_f = pd.read_csv(base_url + "Funding")
        df_l = pd.read_csv(base_url + "Lending")
        
        # Strip column names
        df_f.columns = [c.strip() for c in df_f.columns]
        df_l.columns = [c.strip() for c in df_l.columns]
        
        # Penyelarasan Nama Kolom (Google Sheets ke App)
        if 'Debitur' in df_l.columns: df_l.rename(columns={'Debitur': 'Kreditur'}, inplace=True)
        if 'Rate (%)' in df_f.columns: df_f.rename(columns={'Rate (%)': 'Rate'}, inplace=True)
        if 'Nominal' in df_l.columns: df_l.rename(columns={'Nominal': 'Nominal_Lending'}, inplace=True)
        
        # Cleaning Angka
        for c in ['Nominal', 'Rate']:
            if c in df_f.columns: df_f[c] = clean_numeric_robust(df_f[c])
        for c in ['Nominal_Lending', 'Lending_Rate (%)', 'Cost_of_Fund (%)']:
            if c in df_l.columns: df_l[c] = clean_numeric_robust(df_l[c])
        
        # Pastikan kolom Periode ada dan bersih
        if 'Periode' in df_f.columns: df_f['Periode'] = df_f['Periode'].astype(str).str.strip()
        if 'Periode' in df_l.columns: df_l['Periode'] = df_l['Periode'].astype(str).str.strip()
            
        # Format Tanggal
        if 'Jatuh_Tempo' in df_f.columns:
            df_f['Jatuh_Tempo'] = pd.to_datetime(df_f['Jatuh_Tempo'], dayfirst=True, errors='coerce')
            
        return df_f, df_l, None
    except Exception as e: return pd.DataFrame(), pd.DataFrame(), str(e)

# --- 3. SIDEBAR (LOGO & FILTER) ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/id/thumb/4/41/Logo_ASDP_Indonesia_Ferry.svg/1280px-Logo_ASDP_Indonesia_Ferry.svg.png", use_container_width=True)
st.sidebar.markdown("---")

df_f_raw, df_l_raw, error_msg = load_gsheets_data()

if error_msg:
    st.sidebar.error(f"⚠️ Gagal Konek GSheets: {error_msg}")
    st.stop()

# --- FILTER BULAN (Dinamis dari GSheets) ---
st.sidebar.header("📅 Periode Analisis")
all_months = sorted(list(set(df_f_raw['Periode'].unique()) | set(df_l_raw['Periode'].unique())), reverse=True)
selected_month = st.sidebar.selectbox("Pilih Bulan:", all_months)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Market Benchmark")
current_sbn = st.sidebar.number_input("Benchmark SBN 10Y (%)", value=6.65, step=0.01)

# Filtering Data Berdasarkan Bulan
df_f = df_f_raw[df_f_raw['Periode'] == selected_month].copy()
df_l = df_l_raw[df_l_raw['Periode'] == selected_month].copy()

# --- 4. DASHBOARD UI ---
st.title(f"🚢 PT ASDP Indonesia Ferry - Dashboard {selected_month}")
tab1, tab2, tab3 = st.tabs(["💰 Funding Monitoring", "📈 Lending Monitoring", "📊 ALM Summary"])

# ==========================================
# TAB 1: FUNDING (Penerimaan Riil)
# ==========================================
with tab1:
    if not df_f.empty:
        # HITUNG PENDAPATAN RIIL PER BILYET
        # Rumus: (Nominal * (Rate/100)) / 12
        df_f['Pendapatan_Riil'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        df_f['Net_Yield'] = df_f['Rate'] * 0.8
        net_sbn = current_sbn * 0.9
        df_f['Gap_vs_SBN'] = df_f['Net_Yield'] - net_sbn
        
        # 1. METRICS TOTAL REVENUE
        total_rev = df_f['Pendapatan_Riil'].sum()
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric(f"Total Pendapatan Bunga ({selected_month})", f"Rp {total_rev:,.0f}")
        m3.metric("SBN Net Benchmark", f"{net_sbn:.2f}%")

        st.divider()

        # 2. GRAFIK REVENUE PER BANK
        st.subheader("📊 Rekonsiliasi Pendapatan Bunga per Bank")
        # Grouping untuk chart
        df_bank_rev = df_f.groupby('Bank')['Pendapatan_Riil'].sum().reset_index()
        fig_rev = px.bar(df_bank_rev, x='Bank', y='Pendapatan_Riil', color='Bank',
                         text_auto=',.0f', title=f"Pendapatan Riil Bulan {selected_month} (IDR)")
        fig_rev.update_layout(showlegend=False, yaxis_title="Pendapatan (Rp)")
        st.plotly_chart(fig_rev, use_container_width=True)

        # 3. TABEL DETAIL DENGAN PENDAPATAN PER BILYET
        with st.expander("📑 Detail Tabel Inventori Funding & Revenue", expanded=True):
            df_disp = df_f.copy()
            # Format Tanggal
            df_disp['Jatuh_Tempo'] = df_disp['Jatuh_Tempo'].apply(lambda x: x.strftime('%d-%m-%Y') if pd.notnull(x) and hasattr(x, 'strftime') else '-')
            
            # Reorder kolom agar Pendapatan Riil terlihat jelas
            cols = ['Bank', 'Nomor_Bilyet', 'Nominal', 'Rate', 'Pendapatan_Riil', 'Jatuh_Tempo', 'Periode']
            # Cek jika kolom ada
            existing_cols = [c for c in cols if c in df_disp.columns]
            
            st.dataframe(df_disp[existing_cols].style.format({
                'Nominal': '{:,.0f}',
                'Pendapatan_Riil': '{:,.0f}',
                'Rate': '{:.2f}%'
            }).background_gradient(subset=['Pendapatan_Riil'], cmap='Greens'), use_container_width=True)
    else:
        st.info(f"Tidak ada data Funding untuk periode {selected_month}")

# ==========================================
# TAB 2: LENDING MONITORING
# ==========================================
with tab2:
    if not df_l.empty:
        df_l['Spread'] = df_l['Lending_Rate (%)'] - df_l['Cost_of_Fund (%)']
        df_l['Bunga_Keluar_Bank'] = (df_l['Nominal_Lending'] * (df_l['Cost_of_Fund (%)']/100)) / 12
        
        l1, l2, l3 = st.columns(3)
        l1.metric("Total Penyaluran", f"Rp {df_l['Nominal_Lending'].sum():,.0f}")
        l2.metric("Total Beban Bunga ke Bank", f"Rp {df_l['Bunga_Keluar_Bank'].sum():,.0f}")
        l3.metric("Avg. Margin (Spread)", f"{df_l['Spread'].mean():.2f}%")
        
        fig_l = px.bar(df_l, x='Kreditur', y='Nominal_Lending', color='Kreditur', title="Outstanding Pinjaman per Bank")
        st.plotly_chart(fig_l, use_container_width=True)
        st.dataframe(df_l, use_container_width=True)

# ==========================================
# TAB 3: ALM SUMMARY (CASHFLOW REVENUE)
# ==========================================
with tab3:
    if not df_f.empty and not df_l.empty:
        st.subheader(f"📋 Resume Arus Kas Bunga - {selected_month}")
        
        rev_in = df_f['Pendapatan_Riil'].sum()
        cost_out = df_l['Bunga_Keluar_Bank'].sum()
        net_spread_idr = rev_in - cost_out
        
        r1, r2, r3 = st.columns(3)
        r1.metric("Total Bunga Masuk (Funding)", f"Rp {rev_in:,.0f}")
        r2.metric("Total Bunga Keluar (Lending)", f"Rp {cost_out:,.0f}")
        
        color = "normal" if net_spread_idr >= 0 else "inverse"
        r3.metric("Net Interest Position (NIP)", f"Rp {net_spread_idr:,.0f}", 
                  delta=f"{'SURPLUS' if net_spread_idr >= 0 else 'DEFISIT'}", delta_color=color)

        # Gauge Chart untuk NIP
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = net_spread_idr,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Net Position Bunga (IDR)"},
            gauge = {
                'axis': {'range': [None, max(rev_in, cost_out)]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, rev_in], 'color': "lightgray"}]
            }
        ))
        st.plotly_chart(fig_gauge, use_container_width=True)
