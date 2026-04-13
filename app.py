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
        st.markdown("<h2 style='text-align: center;'>Menyinkronkan Data Treasury ASDP...</h2>", unsafe_allow_html=True)
        bar = st.progress(0)
        for i in range(100):
            time.sleep(0.01)
            bar.progress(i + 1)
        st.session_state.initialized = True
        st.rerun()

# --- DATA ENGINE ---
def clean_numeric(series):
    return pd.to_numeric(series.astype(str).str.replace('%', '').str.replace(',', '').str.replace('Rp', '').str.strip(), errors='coerce').fillna(0)

@st.cache_data(ttl=60)
def load_data_robust():
    sheet_id = "182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY"
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet="
    try:
        df_f = pd.read_csv(base_url + "Funding")
        df_l = pd.read_csv(base_url + "Lending")
        
        # Bersihkan Nama Kolom
        df_f.columns = [c.strip() for c in df_f.columns]
        df_l.columns = [c.strip() for c in df_l.columns]
        
        # Bersihkan Angka
        for df in [df_f, df_l]:
            if 'Nominal' in df.columns: df['Nominal'] = clean_numeric(df['Nominal'])
            if 'Rate (%)' in df.columns: df['Rate (%)'] = clean_numeric(df['Rate (%)'])
            if 'CoF (%)' in df.columns: df['CoF (%)'] = clean_numeric(df['CoF (%)'])
            if 'Periode' in df.columns: df['Periode'] = df['Periode'].astype(str).str.strip()
        
        return df_f, df_l, None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), str(e)

# EXECUTION
df_f_raw, df_l_raw, error_msg = load_data_robust()

# SIDEBAR
st.sidebar.image("https://www.indonesiaferry.co.id/img/logo.png", width=150)
if error_msg:
    st.error(f"⚠️ Masalah GSheets: {error_msg}")
    st.stop()

# Gabungkan semua periode unik dari kedua tab
all_periods = sorted(list(set(df_f_raw['Periode'].unique()) | set(df_l_raw['Periode'].unique())), reverse=True)
selected_month = st.sidebar.selectbox("Pilih Periode Analisis:", all_periods)

# Filter Data Berdasarkan Bulan Pilihan
df_f = df_f_raw[df_f_raw['Periode'] == selected_month].copy()
df_l = df_l_raw[df_l_raw['Periode'] == selected_month].copy()

# Live SBN
try: sbn_val = round(float(yf.Ticker("ID10Y=F").history(period="1d")['Close'].iloc[-1]), 2)
except: sbn_val = 6.65
current_sbn = st.sidebar.number_input("Benchmark SBN 10Y (%)", value=sbn_val, step=0.01)

# --- DASHBOARD UI ---
st.title(f"🚢 ASDP Treasury Dashboard")
st.caption(f"Status Data: Terkoneksi | Periode: {selected_month}")

tab1, tab2, tab3 = st.tabs(["💰 Funding Monitor", "📈 Lending Schedule", "📊 ALM Resume"])

with tab1:
    st.subheader("Monitoring Penempatan Dana (Funding)")
    if not df_f.empty:
        df_f['Net_Yield'] = df_f['Rate (%)'] * 0.8
        net_sbn = current_sbn * 0.9
        
        c1, c2 = st.columns(2)
        c1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        c2.metric("SBN 10Y Net", f"{net_sbn:.2f}%")
        
        fig_f = px.bar(df_f, x='Nomor_Bilyet', y='Net_Yield', color='Bank', title="Yield vs SBN Benchmark", text_auto='.2f')
        fig_f.add_hline(y=net_sbn, line_dash="dash", line_color="red", annotation_text="Benchmark SBN")
        st.plotly_chart(fig_f, use_container_width=True)
        st.dataframe(df_f, use_container_width=True)
    else:
        st.info(f"Belum ada data Funding untuk periode {selected_month}")

with tab2:
    st.subheader("Jadwal Angsuran Pokok & Bunga (Lending)")
    if not df_l.empty:
        # Pembersihan Tipe (Bunga vs Pokok)
        df_l['Tipe'] = df_l['Tipe'].astype(str).str.strip().str.capitalize()
        inf_b = df_l[df_l['Tipe'] == 'Bunga']['Nominal'].sum()
        inf_p = df_l[df_l['Tipe'] == 'Pokok']['Nominal'].sum()
        
        l1, l2 = st.columns(2)
        l1.metric("Penerimaan Bunga", f"Rp {inf_b:,.0f}")
        l2.metric("Penerimaan Pokok", f"Rp {inf_p:,.0f}")
        
        fig_l = px.bar(df_l, x='Debitur', y='Nominal', color='Tipe', barmode='group', title="Komposisi Inflow Bulanan")
        st.plotly_chart(fig_l, use_container_width=True)
        st.dataframe(df_l, use_container_width=True)
    else:
        st.info(f"Belum ada data Lending untuk periode {selected_month}. Cek tanggal di GSheets kamu!")

with tab3:
    st.subheader("ALM & Market Intelligence")
    # Hitung total inflow dari tab Lending
    total_in = df_l['Nominal'].sum() if not df_l.empty else 0
    total_out = total_in * 0.9 # Simulasi kewajiban bank
    
    r1, r2, r3 = st.columns(3)
    r1.metric("Cash Inflow (Piutang)", f"Rp {total_in:,.0f}")
    r2.metric("Cash Outflow (Kewajiban)", f"Rp {total_out:,.0f}")
    
    coverage = total_in / total_out if total_out > 0 else 0
    r3.metric("Coverage Ratio", f"{coverage:.2f}x", delta=f"Rp {total_in - total_out:,.0f} Surplus")
    
    st.divider()
    st.write("🔗 **Market Intelligence Peek:**")
    m1, m2, m3 = st.columns(3)
    m1.link_button("📈 Bareksa Bond Fund", "https://www.bareksa.com/id/data/mutualfund/5052/sucorinvest-phei-aaa-corporate-bond-fund")
    m2.link_button("📊 CEIC Yield Tenor", "https://www.ceicdata.com/en/indonesia/pt-penilai-harga-efek-indonesia-corporate-bond-yield-by-tenor")
    m3.link_button("🔍 PHEI Fair Value", "https://www.phei.co.id/Data-Pasar/Ringkasan-Pasar")
