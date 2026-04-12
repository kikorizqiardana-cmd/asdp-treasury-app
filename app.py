import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime
import pytz

# Konfigurasi Halaman
st.set_page_config(page_title="ASDP Treasury Dashboard", layout="wide")
st.title("🚢 ASDP Smart Treasury Dashboard")

# --- FUNGSI MARKET DATA ---
def get_live_market_data():
    try:
        ticker = "ID10Y=F"
        data = yf.Ticker(ticker).history(period="1d")
        val = round(float(data['Close'].iloc[-1]), 2)
        source = "Yahoo Finance (SBN 10Y)"
    except:
        val = 6.50
        source = "Default/Manual"
    return val, source

# --- SIDEBAR ---
st.sidebar.header("⚙️ Konfigurasi & Filter")
auto_rate, data_source = get_live_market_data()
current_sbn = st.sidebar.number_input("Benchmark SBN (%)", value=auto_rate, step=0.01)
threshold = st.sidebar.slider("Threshold Pindah Dana (%)", 0.0, 10.0, 0.5)

uploaded_file = st.sidebar.file_uploader("Upload Data Deposito (Excel)", type=["xlsx"])

if uploaded_file:
    try:
        df_raw = pd.read_excel(uploaded_file)
        
        # Validasi Kolom Dasar
        required_cols = ['Bank', 'Nomor_Bilyet', 'Nominal', 'Rate', 'Jatuh_Tempo']
        if not all(c in df_raw.columns for c in required_cols):
            st.error(f"❌ Kolom Excel tidak sesuai! Butuh: {required_cols}")
            st.stop()

        # --- FITUR FILTER BANK ---
        list_bank = sorted(df_raw['Bank'].unique())
        selected_banks = st.sidebar.multiselect("Filter Berdasarkan Bank:", options=list_bank, default=list_bank)

        # Filter Dataframe Berdasarkan Pilihan
        df = df_raw[df_raw['Bank'].isin(selected_banks)].copy()

        if df.empty:
            st.warning("⚠️ Tidak ada data untuk bank yang dipilih.")
            st.stop()

        # --- PROSES DATA ---
        df['Jatuh_Tempo'] = pd.to_datetime(df['Jatuh_Tempo'], errors='coerce')
        df['Sisa_Hari'] = (df['Jatuh_Tempo'] - datetime.now()).dt.days
        df['Net_Yield'] = df['Rate'] * 0.8
        net_sbn = current_sbn * 0.9
        df['Gap'] = net_sbn - df['Net_Yield']
        
        # --- DASHBOARD METRICS ---
        tz_jkt = pytz.timezone('Asia/Jakarta')
        st.caption(f"Update: {datetime.now(tz_jkt).strftime('%d/%m/%Y %H:%M')} WIB | Sumber: {data_source}")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Portfolio (Filtered)", f"Rp {df['Nominal'].sum():,.0f}")
        c2.metric("SBN Benchmark (Net)", f"{net_sbn:.2f}%")
        
        loss_potential = (df[df['Gap'] >= threshold]['Nominal'] * (df['Gap']/100)).sum()
        c3.metric("Potensi Cuan Tambahan", f"Rp {loss_potential:,.0f}")

        # --- ALERTS ---
        st.subheader("⚠️ Action Items")
        exp_col1, exp_col2 = st.columns(2)
        
        with exp_col1:
            near_mat = df[df['Sisa_Hari'] <= 30].sort_values('Sisa_Hari')
            if not near_mat.empty:
                st.warning(f"🔔 {len(near_mat)} Bilyet Segera Jatuh Tempo")
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
                             title="Yield Net per Bilyet vs Benchmark",
                             color_continuous_scale='RdYlGn_r',
                             hover_data=['Bank', 'Nominal'])
            fig_bar.add_hline(y=net_sbn, line_dash="dash", line_color="blue")
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with v2:
            bank_dist = df.groupby('Bank')['Nominal'].sum().reset_index()
            fig_pie = px.pie(bank_dist, values='Nominal', names='Bank', title="Proporsi Penempatan")
            st.plotly_chart(fig_pie, use_container_width=True)

        # --- TABEL DETAIL ---
        st.subheader("📑 Data Inventory")
        st.dataframe(df.style.background_gradient(subset=['Gap'], cmap='Reds'), use_container_width=True)

    except Exception as e:
        st.error(f"Terjadi kesalahan: {e}")
else:
    st.info("👋 Halo Kiko! Silakan upload file data_deposito.xlsx untuk memulai analisis.")
