import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from streamlit_lottie import st_lottie
import requests
import time
from datetime import datetime
import pytz

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="ASDP Treasury Command Center", layout="wide", page_icon="🚢")

# --- FUNGSI ANIMASI LOTTIE (DIPERBAIKI) ---
def load_lottieurl(url):
    try:
        r = requests.get(url, timeout=5) # Tambah timeout biar gak nunggu kelamaan
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None

# Gunakan link yang lebih stabil atau backup
lottie_url = "https://assets5.lottiefiles.com/packages/lf20_7wwmup6o.json"
lottie_ship = load_lottieurl(lottie_url)

# --- SPLASH SCREEN INTERAKTIF (DIPERBAIKI) ---
if 'initialized' not in st.session_state:
    st.session_state.initialized = False

if not st.session_state.initialized:
    with st.container():
        st.markdown("<br><br>", unsafe_allow_html=True)
        # HANYA TAMPILKAN LOTTIE JIKA BERHASIL DI-LOAD
        if lottie_ship:
            st_lottie(lottie_ship, height=300, key="loader")
        else:
            st.info("🚢 Menyiapkan data ASDP... (Animasi dilewati karena koneksi)")
            
        st.markdown("<h2 style='text-align: center; color: #004d99;'>Menyiapkan ASDP Treasury Command Center...</h2>", unsafe_allow_html=True)
        bar = st.progress(0)
        for i in range(100):
            time.sleep(0.01)
            bar.progress(i + 1)
        st.session_state.initialized = True
        st.rerun()

# --- FUNGSI MARKET DATA BENCHMARK (LIVE) ---
def get_live_market_data():
    try:
        data = yf.Ticker("ID10Y=F").history(period="1d")
        return round(float(data['Close'].iloc[-1]), 2)
    except: return 6.65

# --- KONEKSI GOOGLE SHEETS (SEMI-OTOMATIS) ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=300)
def load_all_data():
    # Mengambil data dari 3 tab utama
    df_f = conn.read(worksheet="Funding")
    df_l = conn.read(worksheet="Lending")
    try:
        df_m = conn.read(worksheet="Market_Watch")
    except:
        df_m = pd.DataFrame(columns=['Kategori', 'Seri', 'Yield (%)', 'Status', 'Rating'])
    
    # Pembersihan Nama Kolom
    df_f.columns = [c.strip() for c in df_f.columns]
    df_l.columns = [c.strip() for c in df_l.columns]
    return df_f, df_l, df_m

# Load Data Awal
df_f_raw, df_l_raw, df_m_raw = load_all_data()

# --- SIDEBAR: FILTER & INTELLIGENCE ---
st.sidebar.image("https://www.indonesiaferry.co.id/img/logo.png", width=150)
st.sidebar.header("🗓️ Filter Laporan")

available_months = sorted(df_f_raw['Periode'].unique(), reverse=True)
selected_month = st.sidebar.selectbox("Pilih Periode Analisis:", available_months)

# Filter Data Berdasarkan Bulan
df_f = df_f_raw[df_f_raw['Periode'] == selected_month].copy()
df_l = df_l_raw[df_l_raw['Periode'] == selected_month].copy()

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Market Intelligence")
sbn_val = get_live_market_data()
current_sbn = st.sidebar.number_input("Benchmark SBN 10Y (%)", value=sbn_val, step=0.01)

st.sidebar.markdown("---")
st.sidebar.header("🛡️ Credit Simulation")
rating = st.sidebar.selectbox("Simulasi Rating Obligasi:", ["AAA", "AA+", "AA", "A"])
risk_spread = {"AAA": 80, "AA+": 100, "AA": 120, "A": 260}
est_yield_bond = current_sbn + (risk_spread[rating]/100)

# --- DASHBOARD UTAMA ---
st.toast(f"Data {selected_month} Berhasil Dimuat!", icon="✅")
tab1, tab2, tab3 = st.tabs(["💰 WS 1: Funding Monitor", "📈 WS 2: Lending Schedule", "📊 WS 3: ALM & Market"])

# ==========================================
# WS 1: FUNDING MONITOR
# ==========================================
with tab1:
    st.subheader(f"Portfolio Funding ASDP - {selected_month}")
    df_f['Net_Yield'] = df_f['Rate (%)'] * 0.8
    net_sbn = current_sbn * 0.9
    df_f['Gap_vs_SBN'] = net_sbn - df_f['Net_Yield']
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
    m2.metric("SBN 10Y Net Benchmark", f"{net_sbn:.2f}%")
    
    df_pindah = df_f[df_f['Gap_vs_SBN'] > 0.5]
    pot_sbn = (df_pindah['Nominal'] * (df_pindah['Gap_vs_SBN']/100)).sum()
    m3.metric("Potensi Gain Optimasasi", f"Rp {pot_sbn:,.0f}", delta=f"{len(df_pindah)} Bilyet Alert", delta_color="inverse")

    st.divider()
    v1, v2 = st.columns([2, 1])
    with v1:
        fig_f = px.bar(df_f, x='Nomor_Bilyet', y='Net_Yield', color='Gap_vs_SBN', 
                       color_continuous_scale='RdYlGn_r', title="Yield Deposito vs Benchmark SBN")
        fig_f.add_hline(y=net_sbn, line_dash="dash", line_color="blue", annotation_text="Benchmark SBN Net")
        st.plotly_chart(fig_f, use_container_width=True)
    with v2:
        st.info(f"**Strategi:** Penempatan ke Obligasi {rating} berpotensi menghasilkan Net Yield {est_yield_bond*0.9:.2f}%")
        fig_pie = px.pie(df_f, values='Nominal', names='Bank', hole=0.3, title="Konsentrasi Bank")
        st.plotly_chart(fig_pie, use_container_width=True)

# ==========================================
# WS 2: LENDING SCHEDULE (POKOK & BUNGA)
# ==========================================
with tab2:
    st.subheader(f"Jadwal Penerimaan Piutang Anak Usaha - {selected_month}")
    
    # Hitung Inflow per Tipe dari Tabel Angsuran
    inf_bunga = df_l[df_l['Tipe'] == 'Bunga']['Nominal'].sum()
    inf_pokok = df_l[df_l['Tipe'] == 'Pokok']['Nominal'].sum()
    total_in = inf_bunga + inf_pokok
    
    l1, l2, l3 = st.columns(3)
    l1.metric("Total Inflow Bulan Ini", f"Rp {total_in:,.0f}")
    l2.metric("Penerimaan Bunga", f"Rp {inf_bunga:,.0f}")
    l3.metric("Penerimaan Pokok", f"Rp {inf_pokok:,.0f}")

    fig_l = px.bar(df_l, x='Debitur', y='Nominal', color='Tipe', 
                   title="Komposisi Inflow: Pokok vs Bunga", barmode='group',
                   color_discrete_map={'Bunga': '#2ecc71', 'Pokok': '#3498db'})
    st.plotly_chart(fig_l, use_container_width=True)
    
    st.markdown("**Detail Jadwal Angsuran (PK Mandiri & BRI):**")
    st.dataframe(df_l[['Debitur', 'Bank', 'Tipe', 'Nominal', 'Keterangan']], use_container_width=True)

# ==========================================
# WS 3: ALM RESUME & MARKET INTEL
# ==========================================
with tab3:
    st.subheader(f"Analisis Kecukupan Kas & Market Watch - {selected_month}")
    
    # Simulasi Outflow (Est. Bunga ke Bank)
    avg_cof = df_l['CoF (%)'].mean() if not df_l.empty else 0
    total_out = (total_in * 0.9) # Asumsi kewajiban ke bank 90% dari tagihan
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Cash Inflow (Debitur)", f"Rp {total_in:,.0f}")
    c2.metric("Cash Outflow (Kewajiban Bank)", f"Rp {total_out:,.0f}")
    
    cov = total_in / total_out if total_out > 0 else 0
    c3.metric("Coverage Ratio", f"{cov:.2f}x", delta=f"Rp {total_in - total_out:,.0f} Surplus")

    st.divider()
    
    # MARKET BENCHMARKS SECTION
    st.write("🎯 **Riset Pasar & Benchmark Eksternal**")
    col_b1, col_b2, col_b3 = st.columns(3)
    
    with col_b1:
        st.link_button("📈 Reksa Dana Bond (Bareksa)", 
                       "https://www.bareksa.com/id/data/mutualfund/5052/sucorinvest-phei-aaa-corporate-bond-fund")
        st.caption("Benchmark return obligasi korporasi AAA.")

    with col_b2:
        st.link_button("📊 Tren Yield Tenor (CEIC)", 
                       "https://www.ceicdata.com/en/indonesia/pt-penilai-harga-efek-indonesia-corporate-bond-yield-by-tenor")
        st.caption("Pantau tren yield berdasarkan tenor (1Y-10Y).")

    with col_b3:
        st.link_button("🔍 Cek Fair Value (PHEI)", 
                       "https://www.phei.co.id/Data-Pasar/Ringkasan-Pasar")
        st.caption("Data resmi harga wajar pasar SBN & Korporasi.")

    # Chart ALM
    fig_alm = go.Figure(data=[
        go.Bar(name='Total Inflow', x=['Cashflow'], y=[total_in], marker_color='#27ae60'),
        go.Bar(name='Total Outflow', x=['Cashflow'], y=[total_out], marker_color='#c0392b')
    ])
    fig_alm.update_layout(title="Proyeksi Kecukupan Arus Kas Bulanan", height=400)
    st.plotly_chart(fig_alm, use_container_width=True)
