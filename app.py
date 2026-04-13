import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime

# --- 1. SETUP DASAR & BRANDING ---
st.set_page_config(page_title="ASDP Treasury Center", layout="wide", page_icon="🚢")

# LOGO FIX: Kita pakai link yang lebih ringan dan stabil
LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/Logo_ASDP_Indonesia_Ferry.svg/512px-Logo_ASDP_Indonesia_Ferry.svg.png"

# SIDEBAR BRANDING
with st.sidebar:
    try:
        # Kita coba panggil gambarnya
        st.image(LOGO_URL, width=200)
    except:
        # Kalau gagal, munculkan teks keren ini sebagai backup
        st.markdown("### 🚢 **PT ASDP Indonesia Ferry**")
    
    st.markdown("<h3 style='text-align: center; color: #004d99;'>Treasury Command Center</h3>", unsafe_allow_html=True)
    st.markdown("---")

# --- 2. FUNGSI LOAD DATA (GOOOGLE SHEETS) ---
@st.cache_data(ttl=60)
def load_gsheets():
    # ID Sheet Kiko yang sakti
    sheet_id = "182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY"
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet="
    try:
        # Load tab Funding & Lending
        df_f = pd.read_csv(base_url + "Funding")
        df_l = pd.read_csv(base_url + "Lending")
        
        # Bersihkan spasi di nama kolom
        df_f.columns = [c.strip() for c in df_f.columns]
        df_l.columns = [c.strip() for c in df_l.columns]
        
        return df_f, df_l, None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), str(e)

# --- 3. EKSEKUSI DATA ---
df_f_raw, df_l_raw, error_api = load_gsheets()

if error_api:
    st.sidebar.error(f"⚠️ Gagal tarik data: {error_api}")
    st.stop()

# Filter Periode Dinamis
all_months = sorted(list(set(df_f_raw['Periode'].unique()) | set(df_l_raw['Periode'].unique())), reverse=True)
sel_month = st.sidebar.selectbox("Pilih Periode Analisis:", all_months)

# --- 4. TAMPILAN DASHBOARD ---
st.title(f"🚢 ASDP Executive Dashboard")
st.markdown(f"**Periode Aktif:** `{sel_month}`")

# Filter data berdasarkan bulan pilihan
df_f = df_f_raw[df_f_raw['Periode'] == sel_month].copy()
df_l = df_l_raw[df_l_raw['Periode'] == sel_month].copy()

# Tabs untuk memisahkan pandangan
tab1, tab2 = st.tabs(["💰 Funding Overview", "📈 Lending Overview"])

with tab1:
    if not df_f.empty:
        st.subheader(f"Inventori Funding - {sel_month}")
        st.dataframe(df_f, use_container_width=True)
    else:
        st.warning("Data Funding bulan ini kosong di Google Sheets.")

with tab2:
    if not df_l.empty:
        st.subheader(f"Inventori Lending - {sel_month}")
        st.dataframe(df_l, use_container_width=True)
    else:
        st.warning("Data Lending bulan ini kosong di Google Sheets.")

# Footer Identitas
st.sidebar.markdown("---")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%d-%m-%Y %H:%M')}")
