import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from streamlit_lottie import st_lottie
import requests
import time

# --- CONFIG ---
st.set_page_config(page_title="ASDP Treasury Command Center", layout="wide", page_icon="🚢")

# --- LOTTIE HANDLER (SAFE MODE) ---
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
        st.markdown("<h2 style='text-align: center; color: #004d99;'>Menyiapkan ASDP Treasury Command Center...</h2>", unsafe_allow_html=True)
        bar = st.progress(0)
        for i in range(100):
            time.sleep(0.01)
            bar.progress(i + 1)
        st.session_state.initialized = True
        st.rerun()

# --- DATA ENGINE ---
def get_live_sbn():
    try:
        return round(float(yf.Ticker("ID10Y=F").history(period="1d")['Close'].iloc[-1]), 2)
    except: return 6.65

conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=300)
def load_all_data():
    try:
        # Load tab Funding & Lending
        df_f = conn.read(worksheet="Funding")
        df_l = conn.read(worksheet="Lending")
        # Bersihkan nama kolom
        df_f.columns = [c.strip() for c in df_f.columns]
        df_l.columns = [c.strip() for c in df_l.columns]
        return df_f, df_l, None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), str(e)

# --- EXECUTION ---
df_f_raw, df_l_raw, error_msg = load_all_data()

# SIDEBAR
st.sidebar.image("https://www.indonesiaferry.co.id/img/logo.png", width=150)
if error_msg:
    st.sidebar.error(f"Koneksi GSheets Gagal: {error_msg}")
    st.stop() # Berhenti di sini kalau data gagal load

available_months = sorted(df_f_raw['Periode'].unique(), reverse=True)
selected_month = st.sidebar.selectbox("Pilih Periode Analisis:", available_months)

df_f = df_f_raw[df_f_raw['Periode'] == selected_month].copy()
df_l = df_l_raw[df_l_raw['Periode'] == selected_month].copy()

sbn_val = get_live_sbn()
current_sbn = st.sidebar.number_input("Benchmark SBN 10Y (%)", value=sbn_val, step=0.01)

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["💰 WS 1: Funding", "📈 WS 2: Lending Schedule", "📊 WS 3: ALM Resume"])

with tab1:
    st.subheader(f"Portfolio Funding - {selected_month}")
    if not df_f.empty:
        df_f['Net_Yield'] = df_f['Rate (%)'] * 0.8
        net_sbn = current_sbn * 0.9
        
        m1, m2 = st.columns(2)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric("SBN 10Y Net", f"{net_sbn:.2f}%")
        
        fig_f = px.bar(df_f, x='Nomor_Bilyet', y='Net_Yield', title="Yield vs SBN Benchmark")
        fig_f.add_hline(y=net_sbn, line_dash="dash", line_color="blue")
        st.plotly_chart(fig_f, use_container_width=True)

with tab2:
    st.subheader(f"Jadwal Penerimaan - {selected_month}")
    if not df_l.empty:
        # Menghitung Inflow Bunga & Pokok (Case Sensitive!)
        inf_b = df_l[df_l['Tipe'] == 'Bunga']['Nominal'].sum()
        inf_p = df_l[df_l['Tipe'] == 'Pokok']['Nominal'].sum()
        
        l1, l2 = st.columns(2)
        l1.metric("Penerimaan Bunga", f"Rp {inf_b:,.0f}")
        l2.metric("Penerimaan Pokok", f"Rp {inf_p:,.0f}")
        
        st.dataframe(df_l, use_container_width=True)

with tab3:
    st.subheader("Analisis Kecukupan Kas")
    if not df_l.empty:
        total_in = df_l['Nominal'].sum()
        total_out = total_in * 0.9 # Simulasi kewajiban bank
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Cash Inflow", f"Rp {total_in:,.0f}")
        c2.metric("Cash Outflow", f"Rp {total_out:,.0f}")
        
        coverage = total_in / total_out if total_out > 0 else 0
        c3.metric("Coverage Ratio", f"{coverage:.2f}x")
        
        st.link_button("🔍 Peek Market Data (PHEI)", "https://www.phei.co.id/Data-Pasar/Ringkasan-Pasar")
