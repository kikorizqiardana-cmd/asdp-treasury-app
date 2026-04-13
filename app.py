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
        st.markdown("<h2 style='text-align: center;'>Sinkronisasi Data GSheets ASDP...</h2>", unsafe_allow_html=True)
        bar = st.progress(0)
        for i in range(100):
            time.sleep(0.01)
            bar.progress(i + 1)
        st.session_state.initialized = True
        st.rerun()

# --- DATA ENGINE (SUPER ROBUST) ---
def clean_numeric(series):
    """Fungsi untuk ubah '5.50%' atau '1,000' jadi angka murni 5.50"""
    return pd.to_numeric(series.astype(str).str.replace('%', '').str.replace(',', ''), errors='coerce').fillna(0)

@st.cache_data(ttl=60)
def load_data_robust():
    sheet_id = "182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY"
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet="
    try:
        df_f = pd.read_csv(base_url + "Funding")
        df_l = pd.read_csv(base_url + "Lending")
        
        # Bersihkan nama kolom dari spasi atau karakter aneh
        df_f.columns = [c.strip() for c in df_f.columns]
        df_l.columns = [c.strip() for c in df_l.columns]
        
        # Pastikan kolom kunci ada dan bersih
        if 'Nominal' in df_f.columns: df_f['Nominal'] = clean_numeric(df_f['Nominal'])
        if 'Rate (%)' in df_f.columns: df_f['Rate (%)'] = clean_numeric(df_f['Rate (%)'])
        if 'Nominal' in df_l.columns: df_l['Nominal'] = clean_numeric(df_l['Nominal'])
        if 'CoF (%)' in df_l.columns: df_l['CoF (%)'] = clean_numeric(df_l['CoF (%)'])
        
        return df_f, df_l, None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), str(e)

# EXECUTION
df_f_raw, df_l_raw, error_msg = load_data_robust()

# SIDEBAR
st.sidebar.image("https://www.indonesiaferry.co.id/img/logo.png", width=150)
if error_msg:
    st.error(f"⚠️ Error GSheets: {error_msg}")
    st.stop()

# Filter Periode (Pastikan string)
df_f_raw['Periode'] = df_f_raw['Periode'].astype(str)
available_months = sorted(df_f_raw['Periode'].unique(), reverse=True)
selected_month = st.sidebar.selectbox("Pilih Periode Analisis:", available_months)

# Filter Data
df_f = df_f_raw[df_f_raw['Periode'] == selected_month].copy()
df_l = df_l_raw[df_l_raw['Periode'].astype(str) == selected_month].copy()

# Live SBN
try: sbn_val = round(float(yf.Ticker("ID10Y=F").history(period="1d")['Close'].iloc[-1]), 2)
except: sbn_val = 6.65
current_sbn = st.sidebar.number_input("Benchmark SBN 10Y (%)", value=sbn_val, step=0.01)

# --- DASHBOARD UI ---
st.title(f"🚢 ASDP Treasury Dashboard")
st.caption(f"Periode Aktif: {selected_month}")

tab1, tab2, tab3 = st.tabs(["💰 Funding", "📈 Lending", "📊 ALM Resume"])

with tab1:
    st.subheader("Monitoring Yield Deposito")
    if not df_f.empty and 'Rate (%)' in df_f.columns:
        df_f['Net_Yield'] = df_f['Rate (%)'] * 0.8
        net_sbn = current_sbn * 0.9
        
        c1, c2 = st.columns(2)
        c1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        c2.metric("SBN 10Y Net", f"{net_sbn:.2f}%")
        
        fig_f = px.bar(df_f, x='Nomor_Bilyet', y='Net_Yield', color='Bank', title="Yield vs SBN Benchmark")
        fig_f.add_hline(y=net_sbn, line_dash="dash", line_color="red")
        st.plotly_chart(fig_f, use_container_width=True)
    else:
        st.warning("Data Funding tidak ditemukan untuk periode ini atau kolom 'Rate (%)' bermasalah.")
    st.dataframe(df_f)

with tab2:
    st.subheader("Jadwal Angsuran Pokok & Bunga")
    if not df_l.empty and 'Tipe' in df_l.columns:
        inf_b = df_l[df_l['Tipe'].str.strip() == 'Bunga']['Nominal'].sum()
        inf_p = df_l[df_l['Tipe'].str.strip() == 'Pokok']['Nominal'].sum()
        
        l1, l2 = st.columns(2)
        l1.metric("Penerimaan Bunga", f"Rp {inf_b:,.0f}")
        l2.metric("Penerimaan Pokok", f"Rp {inf_p:,.0f}")
        
        fig_l = px.bar(df_l, x='Debitur', y='Nominal', color='Tipe', barmode='group')
        st.plotly_chart(fig_l, use_container_width=True)
    else:
        st.warning("Data Lending tidak ditemukan atau kolom 'Tipe' bermasalah.")
    st.dataframe(df_l)

with tab3:
    st.subheader("ALM & Market Analytics")
    total_in = df_l['Nominal'].sum() if not df_l.empty else 0
    total_out = total_in * 0.9
    
    r1, r2, r3 = st.columns(3)
    r1.metric("Cash Inflow", f"Rp {total_in:,.0f}")
    r2.metric("Cash Outflow (Est)", f"Rp {total_out:,.0f}")
    r3.metric("Coverage", f"{total_in/total_out:.2f}x" if total_out > 0 else "0x")
    
    st.divider()
    st.write("🔗 **Market Peek:**")
    m1, m2, m3 = st.columns(3)
    m1.link_button("📈 Bareksa Bond Fund", "https://www.bareksa.com/id/data/mutualfund/5052/sucorinvest-phei-aaa-corporate-bond-fund")
    m2.link_button("📊 CEIC Yield Tenor", "https://www.ceicdata.com/en/indonesia/pt-penilai-harga-efek-indonesia-corporate-bond-yield-by-tenor")
    m3.link_button("🔍 PHEI Fair Value", "https://www.phei.co.id/Data-Pasar/Ringkasan-Pasar")
