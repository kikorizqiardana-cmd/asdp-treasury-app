import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from streamlit_lottie import st_lottie
import requests
import time
from datetime import datetime, timedelta
import base64
import os

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="ASDP Treasury Command Center", layout="wide", page_icon="🚢")

# --- FUNGSI AMBIL GAMBAR LOKAL (DENGAN PENGAMAN) ---
def get_base64_image(image_path):
    try:
        if os.path.exists(image_path):
            with open(image_path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode()
    except Exception:
        return None
    return None

# Cek apakah file ferry.png ada di folder
logo_filename = 'ferry.png'
logo_path = os.path.join(os.path.dirname(__file__), logo_filename)
encoded_logo = get_base64_image(logo_path)

# --- FUNGSI ANIMASI LOTTIE ---
def load_lottieurl(url):
    try:
        r = requests.get(url, timeout=10)
        return r.json() if r.status_code == 200 else None
    except: return None

lottie_ship = load_lottieurl("https://assets5.lottiefiles.com/packages/lf20_7wwmup6o.json")

# --- 2. SPLASH SCREEN ---
if 'initialized' not in st.session_state:
    st.session_state.initialized = False

if not st.session_state.initialized:
    with st.container():
        st.markdown("<br><br>", unsafe_allow_html=True)
        if lottie_ship: st_lottie(lottie_ship, height=300, key="asdp_v5_1")
        st.markdown("<h2 style='text-align: center; color: #004d99;'>Menyiapkan Dashboard Executive ASDP...</h2>", unsafe_allow_html=True)
        bar = st.progress(0)
        for i in range(100):
            time.sleep(0.01)
            bar.progress(i + 1)
        st.session_state.initialized = True
        st.rerun()

# --- 3. DATA ENGINE ---
def clean_numeric_robust(series):
    def process_val(val):
        val = str(val).strip().replace('Rp', '').replace('%', '').replace(' ', '')
        if not val or val == 'nan': return "0"
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

@st.cache_data(ttl=60)
def load_data():
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
            if 'Periode' in df.columns: df['Periode'] = df['Periode'].astype(str).str.strip()
            if 'Jatuh_Tempo' in df.columns:
                df['Jatuh_Tempo'] = pd.to_datetime(df['Jatuh_Tempo'], dayfirst=True, errors='coerce')
        return df_f, df_l, None
    except Exception as e: return pd.DataFrame(), pd.DataFrame(), str(e)

df_f_raw, df_l_raw, error_msg = load_data()

# --- 4. SIDEBAR ---
if encoded_logo:
    st.sidebar.markdown(f'<div style="text-align: center;"><img src="data:image/png;base64,{encoded_logo}" width="200"></div>', unsafe_allow_html=True)
else:
    # Backup kalau ferry.png nggak ada di GitHub
    st.sidebar.image("https://www.indonesiaferry.co.id/img/logo.png", width=180)

st.sidebar.markdown("---")
all_periods = sorted(list(set(df_f_raw['Periode'].unique()) | set(df_l_raw['Periode'].unique())), reverse=True)
selected_month = st.sidebar.selectbox("Pilih Periode Analisis:", all_periods)

try:
    sbn_val = round(float(yf.Ticker("ID10Y=F").history(period="1d")['Close'].iloc[-1]), 2)
except: sbn_val = 6.65
current_sbn = st.sidebar.number_input("Benchmark SBN 10Y (%)", value=sbn_val, step=0.01)

df_f = df_f_raw[df_f_raw['Periode'] == selected_month].copy()
df_l = df_l_raw[df_l_raw['Periode'] == selected_month].copy()

# --- 5. DASHBOARD UI ---
tab1, tab2, tab3 = st.tabs(["💰 Funding Monitor", "📈 Lending Schedule", "📊 ALM & Market Intel"])

with tab1:
    st.header(f"Intelligence Funding - {selected_month}")
    if not df_f.empty:
        df_f['Net_Yield_Rate'] = df_f['Rate (%)'] * 0.8
        net_sbn = current_sbn * 0.9
        df_f['Monthly_Yield'] = (df_f['Nominal'] * (df_f['Rate (%)'] / 100)) / 12

        # --- NOTIFIKASI PINTAR ---
        st.subheader("🔔 Treasury Alerts")
        c_a1, c_a2 = st.columns(2)
        with c_a1:
            st.markdown("**🚨 Underperform vs SBN Net**")
            with st.container(height=180):
                under = df_f[df_f['Net_Yield_Rate'] < net_sbn]
                if not under.empty:
                    for _, row in under.iterrows():
                        st.error(f"**{row['Bank']}** | Gap: {net_sbn - row['Net_Yield_Rate']:.2f}%")
                else: st.success("✅ Rate aman.")
        with c_a2:
            st.markdown("**⏳ Jatuh Tempo (H-7)**")
            with st.container(height=180):
                if 'Jatuh_Tempo' in df_f.columns:
                    today = datetime.now()
                    soon = df_f[(df_f['Jatuh_Tempo'] >= today) & (df_f['Jatuh_Tempo'] <= today + timedelta(days=7))]
                    if not soon.empty:
                        for _, row in soon.iterrows():
                            st.warning(f"**{row['Bank']}** | {row['Jatuh_Tempo'].strftime('%d-%m-%Y')}")
                    else: st.info("📅 Tidak ada jatuh tempo dekat.")

        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric("Total Yield Bulanan", f"Rp {df_f['Monthly_Yield'].sum():,.0f}")
        m3.metric("SBN 10Y Net", f"{net_sbn:.2f}%")

        st.markdown("### 📊 Rekonsiliasi Penerimaan Bunga per Bank")
        df_bank = df_f.groupby('Bank')['Monthly_Yield'].sum().reset_index()
        df_bank['Yield_B'] = df_bank['Monthly_Yield'] / 1e9
        
        fig = px.bar(df_bank, x='Bank', y='Yield_B', color='Bank', text_auto='.2f', 
                     title="Penerimaan Bunga (Rp Miliar/Billion)")
        fig.update_traces(texttemplate='%{y:.2f} B', textposition='outside')
        fig.update_layout(yaxis_tickformat=',.2f', showlegend=False, yaxis_title="Rp Billion")
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("Jadwal Angsuran & Inflow")
    if not df_l.empty:
        st.dataframe(df_l, use_container_width=True)

with tab3:
    st.header("Strategic Risk & Re-Investment")
    if not df_f.empty:
        st.subheader("🎯 Simulator Re-Investasi")
        rating_opt = ["AAA", "AA", "A", "BBB", "BB"]
        choice = st.selectbox("Pilih Target Rating:", rating_opt)
        spreads = {"AAA": 0.8, "AA": 1.3, "A": 2.5, "BBB": 4.0, "BB": 6.5}
        
        target_gross = current_sbn + spreads[choice]
        target_net = target_gross * 0.9
        current_avg_net = df_f['Net_Yield_Rate'].mean()
        potensi_duit = (df_f['Nominal'].sum() * ((target_net - current_avg_net)/100)) / 12
        
        st.success(f"**Potensi Tambahan Cuan (Net):** Rp {potensi_duit:,.0f} per bulan jika pindah ke {choice}")
        
        st.write("🔗 **Market Peek:**")
        c_m1, c_m2 = st.columns(2)
        c_m1.link_button("📈 Bareksa Bond Fund", "https://www.bareksa.com/id/data/mutualfund/5052/sucorinvest-phei-aaa-corporate-bond-fund")
        c_m2.link_button("🔍 PHEI Fair Value", "https://www.phei.co.id/Data-Pasar/Ringkasan-Pasar")
