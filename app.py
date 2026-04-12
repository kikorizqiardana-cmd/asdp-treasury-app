import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime
import pytz # Untuk zona waktu Jakarta

# Konfigurasi Halaman
st.set_page_config(page_title="ASDP Treasury Dashboard", layout="wide")
st.title("🚢 ASDP Smart Treasury Dashboard")

# --- FUNGSI OTOMATIS AMBIL DATA MARKET ---
def get_live_market_data():
    # Menarik Yield SBN 10Y Indonesia via Yahoo Finance (Agregator Global)
    try:
        ticker = "ID10Y=F"
        data = yf.Ticker(ticker).history(period="1d")
        val = round(float(data['Close'].iloc[-1]), 2)
        source = "Yahoo Finance (ID SBN 10Y)"
    except:
        val = 6.50 # Fallback jika koneksi internet/API limit
        source = "Default (Manual/Fallback)"
    
    return val, source

# --- SIDEBAR: KONFIGURASI ---
st.sidebar.header("⚙️ Konfigurasi & Market")

# Ambil data otomatis saat web dibuka
auto_rate, data_source = get_live_market_data()

# Tampilkan info sumber data
st.sidebar.info(f"Sumber Data: {data_source}")

# Input untuk Benchmark SBN (Sudah terisi otomatis dari web)
current_sbn = st.sidebar.number_input("Benchmark SBN (%) - Auto Updated", value=auto_rate, step=0.01)

# Threshold Pindah Dana (Range 0% - 10% sesuai request)
threshold = st.sidebar.slider("Threshold Pindah Dana (%)", 0.0, 10.0, 0.5)

uploaded_file = st.sidebar.file_uploader("Upload Data Deposito (Excel)", type=["xlsx"])

# --- LOGIKA DASHBOARD ---
if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        
        # Validasi Kolom
        required_cols = ['Bank', 'Nomor_Bilyet', 'Nominal', 'Rate', 'Jatuh_Tempo']
        if not all(c in df.columns for c in required_cols):
            st.error(f"❌ Kolom Excel tidak sesuai! Butuh: {required_cols}")
            st.stop()

        # Proses Tanggal & Yield
        df['Jatuh_Tempo'] = pd.to_datetime(df['Jatuh_Tempo'], errors='coerce')
        df['Sisa_Hari'] = (df['Jatuh_Tempo'] - datetime.now()).dt.days
        
        # Kalkulasi Net of Tax (20% Deposito, 10% SBN)
        df['Net_Yield'] = df['Rate'] * 0.8
        net_sbn = current_sbn * 0.9
        df['Gap'] = net_sbn - df['Net_Yield']
        
        # --- RINGKASAN ATAS ---
        tz_jkt = pytz.timezone('Asia/Jakarta')
        now_jkt = datetime.now(tz_jkt).strftime("%d/%m/%Y %H:%M")
        
        st.caption(f"Terakhir Diperbarui: {now_jkt} WIB")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Portfolio", f"Rp {df['Nominal'].sum():,.0f}")
        c2.metric("SBN Benchmark (Net)", f"{net_sbn:.2f}%")
        
        # Potensi cuan hilang hanya untuk yang di atas threshold
        loss_potential = (df[df['Gap'] >= threshold]['Nominal'] * (df['Gap']/100)).sum()
        c3.metric("Potensi Cuan Tambahan", f"Rp {loss_potential:,.0f}", delta=f"{threshold}% Thrsh", delta_color="normal")

        # --- ALERT SECTION ---
        st.subheader("⚠️ Action Required")
        exp_col1, exp_col2 = st.columns(2)
        
        with exp_col1:
            near_mat = df[df['Sisa_Hari'] <= 30].sort_values('Sisa_Hari')
            if not near_mat.empty:
                st.warning(f"🔔 {len(near_mat)} Bilyet Jatuh Tempo (<30 Hari)")
                st.dataframe(near_mat[['Bank', 'Nomor_Bilyet', 'Sisa_Hari']], use_container_width=True)
        
        with exp_col2:
            to_move = df[df['Gap'] >= threshold].sort_values('Gap', ascending=False)
            if not to_move.empty:
                st.error(f"🚨 {len(to_move)} Bilyet Underperform (> {threshold}%)")
                st.dataframe(to_move[['Bank', 'Nomor_Bilyet', 'Gap']], use_container_width=True)

        # --- VISUALISASI ---
        st.subheader("📊 Analisis Visual")
        v1, v2 = st.columns([2, 1])
        
        with v1:
            fig_bar = px.bar(df, x='Nomor_Bilyet', y='Net_Yield', color='Gap',
                             title="Performance per Bilyet vs SBN Net Line",
                             color_continuous_scale='RdYlGn_r',
                             hover_data=['Bank', 'Nominal'])
            fig_bar.add_hline(y=net_sbn, line_dash="dash", line_color="blue", annotation_text="Benchmark SBN")
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with v2:
            fig_pie = px.pie(df, values='Nominal', names='Bank', title="Konsentrasi Dana per Bank")
            st.plotly_chart(fig_pie, use_container_width=True)

        # --- TABEL DETAIL ---
        st.subheader("📑 Full Data Inventory")
        st.dataframe(df.style.background_gradient(subset=['Gap'], cmap='Reds'), use_container_width=True)

    except Exception as e:
        st.error(f"Error pembacaan: {e}")
else:
    st.info("👋 Halo Kiko! Silakan upload file data_deposito.xlsx untuk memulai.")
