import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from streamlit_lottie import st_lottie
import requests
import time

# --- CONFIG ---
st.set_page_config(page_title="ASDP Treasury Command Center", layout="wide", page_icon="🚢")

def load_lottieurl(url):
    try:
        r = requests.get(url, timeout=5)
        return r.json() if r.status_code == 200 else None
    except: return None

lottie_ship = load_lottieurl("https://assets5.lottiefiles.com/packages/lf20_7wwmup6o.json")

# --- SPLASH SCREEN ---
if 'initialized' not in st.session_state:
    st.session_state.initialized = False

if not st.session_state.initialized:
    with st.container():
        st.markdown("<br><br>", unsafe_allow_html=True)
        if lottie_ship: st_lottie(lottie_ship, height=300)
        st.markdown("<h2 style='text-align: center;'>Menyelaraskan Format Angka ASDP...</h2>", unsafe_allow_html=True)
        bar = st.progress(0)
        for i in range(100):
            time.sleep(0.01)
            bar.progress(i + 1)
        st.session_state.initialized = True
        st.rerun()

# --- DATA ENGINE (ULTIMATE CLEANER) ---
def clean_numeric_robust(series):
    """Fungsi sakti untuk membersihkan campuran format desimal koma & titik"""
    def process_val(val):
        val = str(val).strip().replace('Rp', '').replace('%', '').replace(' ', '')
        if not val or val == 'nan': return "0"
        
        commas = val.count(',')
        dots = val.count('.')
        
        # Kasus 1: Ada koma dan titik (e.g., 1.000,50 atau 1,000.50)
        if commas > 0 and dots > 0:
            if val.rfind(',') > val.rfind('.'): # Format Indo: 1.000,50
                return val.replace('.', '').replace(',', '.')
            else: # Format US: 1,000.50
                return val.replace(',', '')
        
        # Kasus 2: Hanya ada koma (e.g., 25,000,000 atau 5,75)
        if commas > 0:
            # Jika koma lebih dari satu atau ada 3 angka di belakang (ribuan)
            if commas > 1 or len(val.split(',')[-1]) == 3:
                return val.replace(',', '')
            else: # Desimal (5,75)
                return val.replace(',', '.')
        
        # Kasus 3: Hanya ada titik (e.g., 25.000.000 atau 5.75)
        if dots > 0:
            if dots > 1 or len(val.split('.')[-1]) == 3:
                return val.replace('.', '')
            else: # Sudah format US desimal (5.75)
                return val
        
        return val

    s = series.apply(process_val)
    return pd.to_numeric(s, errors='coerce').fillna(0)

@st.cache_data(ttl=60)
def load_data_robust():
    sheet_id = "182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY"
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet="
    try:
        df_f = pd.read_csv(base_url + "Funding")
        df_l = pd.read_csv(base_url + "Lending")
        df_f.columns = [c.strip() for c in df_f.columns]
        df_l.columns = [c.strip() for c in df_l.columns]
        
        for df in [df_f, df_l]:
            if 'Nominal' in df.columns: df['Nominal'] = clean_numeric_robust(df['Nominal'])
            if 'Rate (%)' in df.columns: df['Rate (%)'] = clean_numeric_robust(df['Rate (%)'])
            if 'CoF (%)' in df.columns: df['CoF (%)'] = clean_numeric_robust(df['CoF (%)'])
            if 'Periode' in df.columns: df['Periode'] = df['Periode'].astype(str).str.strip()
            
        return df
