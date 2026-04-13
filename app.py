import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from streamlit_lottie import st_lottie
import requests
import time

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="ASDP Treasury Command Center", layout="wide", page_icon="🚢")

# --- FUNGSI ANIMASI LOTTIE ---
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
        if lottie_ship: st_lottie(lottie_ship, height=300, key="loader")
        st.markdown("<h2 style='text-align: center; color: #004d99;'>Menyiapkan ASDP Treasury Command Center...</h2>", unsafe_allow_html=True)
        bar = st.progress(0)
        for i in range(100):
            time.sleep(0.01)
            bar.progress(i + 1)
        st.session_state.initialized = True
        st.rerun()

# --- DATA ENGINE (DIRECT CSV) ---
@st.cache_data(ttl=300)
def load_data_direct():
    sheet_id = "182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY"
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet="
    try:
        df_f = pd.read_csv(base_url + "Funding")
        df_l = pd.read_csv(base_url + "Lending")
        # Bersihkan spasi di nama kolom
        df_f.columns = [c.strip() for c in df_f.columns]
        df_l.columns = [c.strip() for c in df_l.columns]
        return df_f, df_l, None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), str(e)

def get_live_sbn():
    try: return round(float(yf.Ticker("ID10Y=F").history(period="1d")['Close'].iloc[-1]), 2)
    except: return 6.65

# --- EXECUTION ---
df_f_raw, df_l_raw, error_msg = load_data_direct()

# SIDEBAR
st.sidebar.image("https://www.indonesiaferry.co.id/img/logo.png", width=150)
if error_msg:
    st.error(f"Koneksi GSheets Gagal: {error_msg}")
    st.stop()

available_months = sorted(df_f_raw['Periode'].unique(), reverse=True)
selected_month = st.sidebar.selectbox("Pilih Periode Analisis:", available_months)
current_sbn = st.sidebar.number_input("Benchmark SBN 10Y (%)", value=get_live_sbn(), step=0.01)

# Filter Data
df_f = df_f_raw[df_f_raw['Periode'] == selected_month].copy()
df_l = df_l_raw[df_l_raw['Periode'] == selected_month].copy()

# --- DASHBOARD ---
st.title(f"🚢 ASDP Treasury Dashboard - {selected_month}")
tab1, tab2, tab3 = st.tabs(["💰 Funding", "📈 Lending Schedule", "📊 ALM Resume"])

# --- WS 1: FUNDING ---
with tab1:
    st.subheader("Monitoring Yield Penempatan Dana")
    if 'Rate (%)' in df_f.columns:
        df_f['Net_Yield'] = df_f['Rate (%)'] * 0.8
        net_sbn = current_sbn * 0.9
        
        m1, m2 = st.columns(2)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric("SBN 10Y Net", f"{net_sbn:.2f}%")
        
        fig_f = px.bar(df_f, x='Nomor_Bilyet', y='Net_Yield', color='Bank', title="Yield Deposito vs SBN")
        fig_f.add_hline(y=net_sbn, line_dash="dash", line_color="red")
        st.plotly_chart(fig_f, use_container_width=True)
    else:
        st.warning("⚠️ Kolom 'Rate (%)' tidak ditemukan di tab Funding Google Sheets kamu.")
    st.dataframe(df_f, use_container_width=True)

# --- WS 2: LENDING ---
with tab2:
    st.subheader("Jadwal Angsuran Pokok & Bunga")
    if 'Tipe' in df_l.columns and 'Nominal' in df_l.columns:
        inf_b = df_l[df_l['Tipe'] == 'Bunga']['Nominal'].sum()
        inf_p = df_l[df_l['Tipe'] == 'Pokok']['Nominal'].sum()
        
        l1, l2 = st.columns(2)
        l1.metric("Penerimaan Bunga", f"Rp {inf_b:,.0f}")
        l2.metric("Penerimaan Pokok", f"Rp {inf_p:,.0f}")
        
        fig_l = px.bar(df_l, x='Debitur', y='Nominal', color='Tipe', barmode='group')
        st.plotly_chart(fig_l, use_container_width=True)
    else:
        st.warning("⚠️ Kolom 'Tipe' atau 'Nominal' tidak ditemukan di tab Lending Google Sheets kamu.")
    st.dataframe(df_l, use_container_width=True)

# --- WS 3: ALM ---
with tab3:
    st.subheader("ALM Resume & Market Benchmark")
    total_in = df_l['Nominal'].sum() if 'Nominal' in df_l.columns else 0
    total_out = total_in * 0.9
    
    r1, r2 = st.columns(2)
    r1.metric("Cash Inflow", f"Rp {total_in:,.0f}")
    r2.metric("Cash Outflow (Est)", f"Rp {total_out:,.0f}")
    
    st.divider()
    st.write("🔗 **External Market Peek:**")
    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.link_button("📈 Reksa Dana (Bareksa)", "https://www.bareksa.com/id/data/mutualfund/5052/sucorinvest-phei-aaa-corporate-bond-fund")
    m_col2.link_button("📊 Yield Tenor (CEIC)", "https://www.ceicdata.com/en/indonesia/pt-penilai-harga-efek-indonesia-corporate-bond-yield-by-tenor")
    m_col3.link_button("🔍 Fair Value (PHEI)", "https://www.phei.co.id/Data-Pasar/Ringkasan-Pasar")
