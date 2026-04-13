import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import requests
import time
from datetime import datetime, timedelta

# --- A. SETUP DASAR ---
st.set_page_config(page_title="ASDP Treasury Center", layout="wide", page_icon="🚢")

# Link Logo Online (Anti-Error)
LOGO_URL = "https://upload.wikimedia.org/wikipedia/id/thumb/4/41/Logo_ASDP_Indonesia_Ferry.svg/1280px-Logo_ASDP_Indonesia_Ferry.svg.png"

# --- B. FUNGSI LIVE MARKET (YFINANCE) ---
def get_live_sbn():
    try:
        ticker = yf.Ticker("ID10Y=F")
        data = ticker.history(period="1d")
        if not data.empty:
            return round(float(data['Close'].iloc[-1]), 2), "Yahoo Finance (Live)"
    except:
        pass
    return 6.65, "Default (Manual)"

# --- C. FUNGSI LOAD DATA (GOOGLE SHEETS) ---
@st.cache_data(ttl=60)
def load_gsheets():
    sheet_id = "182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY"
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet="
    try:
        df_f = pd.read_csv(base_url + "Funding")
        df_l = pd.read_csv(base_url + "Lending")
        
        # Bersihkan nama kolom dari spasi liar
        df_f.columns = [c.strip() for c in df_f.columns]
        df_l.columns = [c.strip() for c in df_l.columns]
        
        # Penyelarasan Nama Kolom (Sesuai GSheets Kiko)
        if 'Rate (%)' in df_f.columns: df_f.rename(columns={'Rate (%)': 'Rate'}, inplace=True)
        if 'Debitur' in df_l.columns: df_l.rename(columns={'Debitur': 'Kreditur'}, inplace=True)
        
        return df_f, df_l, None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), str(e)

# --- D. SIDEBAR & FILTER ---
st.sidebar.image(LOGO_URL, use_container_width=True)
st.sidebar.markdown("<h3 style='text-align: center;'>Treasury Command Center</h3>", unsafe_allow_html=True)
st.sidebar.markdown("---")

# Tarik Data
df_f_raw, df_l_raw, error_api = load_gsheets()

if error_api:
    st.error(f"⚠️ Gagal tarik data: {error_api}")
    st.stop()

# Filter Periode
all_months = sorted(list(set(df_f_raw['Periode'].unique()) | set(df_l_raw['Periode'].unique())), reverse=True)
sel_month = st.sidebar.selectbox("Pilih Periode Analisis:", all_months)

# SBN Live
sbn_val, sbn_source = get_live_sbn()
st.sidebar.markdown("---")
st.sidebar.header("⚙️ Market Intelligence")
current_sbn = st.sidebar.number_input(f"SBN 10Y ({sbn_source})", value=sbn_val, step=0.01)

# Filter Data Berdasarkan Bulan
df_f = df_f_raw[df_f_raw['Periode'] == sel_month].copy()
df_l = df_l_raw[df_l_raw['Periode'] == sel_month].copy()

# --- E. TAMPILAN DASHBOARD ---
st.title(f"🚢 ASDP Executive Dashboard - {sel_month}")

tab1, tab2 = st.tabs(["💰 Funding Overview", "📈 Lending Overview"])

with tab1:
    if not df_f.empty:
        st.subheader("Data Placement Deposito")
        st.dataframe(df_f, use_container_width=True)
    else:
        st.info("Data tidak ditemukan.")

with tab2:
    if not df_l.empty:
        st.subheader("Data Penyaluran Dana")
        st.dataframe(df_l, use_container_width=True)
