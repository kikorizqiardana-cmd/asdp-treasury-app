import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import os
from datetime import datetime

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="ASDP Treasury Command Center", layout="wide", page_icon="🚢")

# Penanganan Logo Lokal (ferry.png dari GitHub)
logo_path = "ferry.png"

with st.sidebar:
    if os.path.exists(logo_path):
        st.image(logo_path, use_container_width=True)
    else:
        st.markdown("### 🚢 PT ASDP Indonesia Ferry")
        st.caption(f"Info: File '{logo_path}' tidak ditemukan di root folder. Pastikan nama file sesuai di GitHub.")
    st.markdown("---")

# --- 2. ENGINE PEMBERSIH DATA ---
def clean_numeric(series):
    return pd.to_numeric(
        series.astype(str).str.replace(r'[Rp% ,]', '', regex=True), 
        errors='coerce'
    ).fillna(0)

@st.cache_data(ttl=60)
def load_data():
    sheet_id = "182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY"
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet="
    try:
        df_f = pd.read_csv(base_url + "Funding")
        df_l = pd.read_csv(base_url + "Lending")
        # Membersihkan nama kolom dari spasi
        df_f.columns = [c.strip() for c in df_f.columns]
        df_l.columns = [c.strip() for c in df_l.columns]
        # Penyelarasan Nama Kolom
        if 'Rate (%)' in df_f.columns: df_f.rename(columns={'Rate (%)': 'Rate'}, inplace=True)
        if 'Debitur' in df_l.columns: df_l.rename(columns={'Debitur': 'Kreditur'}, inplace=True)
        return df_f, df_l, None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), str(e)

# --- 3. MARKET DATA (LIVE SBN 10Y) ---
def get_live_sbn():
    try:
        # Ticker ID10Y=F untuk Yield Surat Utang Negara 10 Tahun
        data = yf.Ticker("ID10Y=F").history(period="1d")
        if not data.empty:
            return round(float(data['Close'].iloc[-1]), 2), "Yahoo Finance (Live)"
    except:
        pass
    return 6.65, "Default (Manual)"

# --- 4. EKSEKUSI DATA ---
df_f_raw, df_l_raw, err = load_data()

if err:
    st.sidebar.error(f"Gagal memuat data GSheets: {err}")
    st.stop()

# Sidebar: Market Intel
sbn_val, sbn_source = get_live_sbn()
st.sidebar.header("⚙️ Market Intelligence")
current_sbn = st.sidebar.number_input(f"Benchmark SBN 10Y ({sbn_source})", value=sbn_val, step=0.01)
threshold = st.sidebar.slider("Threshold Pindah Dana (%)", 0.0, 5.0, 0.5)

# Filter Periode
all_periods = sorted(list(set(df_f_raw['Periode'].unique()) | set(df_l_raw['Periode'].unique())), reverse=True)
selected_month = st.sidebar.selectbox("Pilih Periode:", all_periods)

df_f = df_f_raw[df_f_raw['Periode'] == selected_month].copy()
df_l = df_l_raw[df_l_raw['Periode'] == selected_month].copy()

# --- 5. TAMPILAN DASHBOARD ---
st.title(f"🚢 ASDP Treasury Dashboard - {selected_month}")
tab1, tab2, tab3 = st.tabs(["💰 Funding Monitor", "📉 Lending Monitor", "📊 ALM Resume"])

with tab1:
    if not df_f.empty:
        # Kalkulasi Revenue & Yield Alert
        df_f['Nominal'] = clean_numeric(df_f['Nominal'])
        df_f['Rate'] = clean_numeric(df_f['Rate'])
        
        # Pendapatan Riil Bulanan: (Nominal * Rate) / 12
        df_f['Pendapatan_Riil'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        
        # Yield Alert: Net Yield (80% Rate) vs Net SBN (90% SBN)
        df_f['Net_Yield'] = df_f['Rate'] * 0.8
        net_sbn_bench = current_sbn * 0.9
        df_f['Gap_vs_SBN'] = df_f['Net_Yield'] - net_sbn_bench
        
        # Baris Metrik
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        col2.metric(f"Total Revenue ({selected_month})", f"Rp {df_f['Pendapatan_Riil'].sum():,.0f}")
        col3.metric("Live SBN Net Benchmark", f"{net_sbn_bench:.2f}%")
        
        # Alert Box
        underperform = df_f[df_f['Net_Yield'] < (net_sbn_bench - threshold)]
        if not underperform.empty:
            st.error(f"🚨 **Alert:** Terdeteksi {len(underperform)} bilyet yang yield-nya di bawah benchmark SBN Net.")
        else:
            st.success("✅ Seluruh penempatan dana optimal di atas benchmark.")

        st.divider()
        st.subheader("Detail Inventori Funding")
        st.dataframe(df_f.style.format({
            'Nominal': '{:,.0f}', 
            'Pendapatan_Riil': '{:,.0f}', 
            'Rate': '{:.2f}%',
            'Net_Yield': '{:.2f}%'
        }), use_container_width=True)
    else:
        st.info("Pilih periode untuk memuat data Funding.")

with tab2:
    if not df_l.empty:
        st.subheader("Monitoring Penyaluran (Lending)")
        st.dataframe(df_l, use_container_width=True)

with tab3:
    if not df_f.empty and not df_l.empty:
        st.subheader("ALM Resume")
        # Contoh Net Interest Position sederhana
        total_rev = df_f['Pendapatan_Riil'].sum()
        st.metric("Net Interest Position (Revenue)", f"Rp {total_rev:,.0f}")
