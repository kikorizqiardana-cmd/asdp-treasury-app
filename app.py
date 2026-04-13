import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

# --- 1. SETTING DASAR & BRANDING ---
st.set_page_config(page_title="ASDP Treasury Center", layout="wide", page_icon="🚢")

# Kita pakai Logo Online agar tidak FileNotFoundError lagi
ASDP_LOGO = "https://upload.wikimedia.org/wikipedia/id/thumb/4/41/Logo_ASDP_Indonesia_Ferry.svg/1280px-Logo_ASDP_Indonesia_Ferry.svg.png"

st.sidebar.image(ASDP_LOGO, use_container_width=True)
st.sidebar.markdown("<h3 style='text-align: center;'>Treasury Command Center</h3>", unsafe_allow_html=True)
st.sidebar.markdown("---")

# --- 2. FUNGSI MEMBERSIHKAN ANGKA (THE CLEANER) ---
# Ini penting supaya GSheets yang isinya "Rp 1.000" tidak bikin error
def clean_number(series):
    return pd.to_numeric(
        series.astype(str).str.replace(r'[Rp% ,]', '', regex=True), 
        errors='coerce'
    ).fillna(0)

# --- 3. KONEKSI GOOGLE SHEETS ---
@st.cache_data(ttl=60)
def load_data():
    sheet_id = "182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY"
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet="
    try:
        df_f = pd.read_csv(base_url + "Funding")
        df_l = pd.read_csv(base_url + "Lending")
        
        # Bersihkan nama kolom
        df_f.columns = [c.strip() for c in df_f.columns]
        df_l.columns = [c.strip() for c in df_l.columns]
        
        # Penyelarasan nama kolom
        if 'Rate (%)' in df_f.columns: df_f.rename(columns={'Rate (%)': 'Rate'}, inplace=True)
        if 'Debitur' in df_l.columns: df_l.rename(columns={'Debitur': 'Kreditur'}, inplace=True)
        
        return df_f, df_l, None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), str(e)

# --- 4. EKSEKUSI AWAL ---
df_f_raw, df_l_raw, error = load_data()

if error:
    st.error(f"Waduh, koneksi GSheets bermasalah: {error}")
else:
    st.success("✅ Koneksi Data Aman! Dashboard siap dirakit lebih lanjut.")
    
    # Tampilkan Filter Bulan di Sidebar
    all_months = sorted(df_f_raw['Periode'].unique().tolist(), reverse=True)
    selected_month = st.sidebar.selectbox("Pilih Periode:", all_months)
    
    # Filter Data
    df_f = df_f_raw[df_f_raw['Periode'] == selected_month].copy()
    
    # Cek Data Sederhana
    st.write(f"Data Funding Bulan {selected_month}:", df_f.head())
