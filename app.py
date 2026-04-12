import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
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

# --- SIDEBAR: KONFIGURASI & SIMULASI ---
st.sidebar.header("⚙️ Market & Dashboard")
auto_rate, data_source = get_live_market_data()
current_sbn = st.sidebar.number_input("Benchmark SBN (%)", value=auto_rate, step=0.01)
threshold = st.sidebar.slider("Threshold Pindah Dana (%)", 0.0, 10.0, 0.5)

st.sidebar.markdown("---")
st.sidebar.header("🏢 Simulasi Korporasi (Rating AA)")
# Kupon obligasi korporasi AA biasanya di atas SBN
rate_bond_aa = st.sidebar.number_input("Estimasi Kupon Korporasi AA (%)", value=7.50, step=0.1)

uploaded_file = st.sidebar.file_uploader("Upload Data Deposito (Excel)", type=["xlsx"])

if uploaded_file:
    try:
        df_raw = pd.read_excel(uploaded_file)
        
        # Validasi Kolom
        required_cols = ['Bank', 'Nomor_Bilyet', 'Nominal', 'Rate', 'Jatuh_Tempo']
        if not all(c in df_raw.columns for c in required_cols):
            st.error(f"❌ Kolom Excel kurang! Butuh: {required_cols}")
            st.stop()

        # Filter Bank
        list_bank = sorted(df_raw['Bank'].unique())
        selected_banks = st.sidebar.multiselect("Filter Bank:", options=list_bank, default=list_bank)
        df = df_raw[df_raw['Bank'].isin(selected_banks)].copy()

        # --- PROSES DATA & YIELD ---
        df['Jatuh_Tempo'] = pd.to_datetime(df['Jatuh_Tempo'], errors='coerce')
        df['Sisa_Hari'] = (df['Jatuh_Tempo'] - datetime.now()).dt.days
        
        # Kalkulasi Net (Pajak Depo 20%, SBN/Bond 10%)
        df['Net_Yield'] = df['Rate'] * 0.8
        net_sbn = current_sbn * 0.9
        net_bond = rate_bond_aa * 0.9
        
        df['Gap_vs_SBN'] = net_sbn - df['Net_Yield']
        df['Gap_vs_Bond'] = net_bond - df['Net_Yield']
        
        # --- METRICS DASHBOARD ---
        tz_jkt = pytz.timezone('Asia/Jakarta')
        st.caption(f"Update: {datetime.now(tz_jkt).strftime('%d/%m/%Y %H:%M')} WIB | Market: {data_source}")
        
        m1, m2, m3 = st.columns(3)
        total_dana = df['Nominal'].sum()
        m1.metric("Total Portfolio", f"Rp {total_dana:,.0f}")
        m2.metric("SBN Net", f"{net_sbn:.2f}%")
        m3.metric("Korporasi AA Net", f"{net_bond:.2f}%")

        # --- POTENSI OPTIMALISASI ---
        st.subheader("🎯 Potensi Optimalisasi Yield")
        c1, c2 = st.columns(2)
        
        # Filter bilyet yang di atas threshold untuk dipindahkan
        df_pindah = df[df['Gap_vs_SBN'] >= threshold]
        potensi_sbn = (df_pindah['Nominal'] * (df_pindah['Gap_vs_SBN']/100)).sum()
        potensi_bond = (df_pindah['Nominal'] * (df_pindah['Gap_vs_Bond']/100)).sum()

        with c1:
            st.info(f"Jika dipindah ke **SBN** (Selisih >{threshold}%)")
            st.metric("Tambahan Cuan/Tahun", f"Rp {potensi_sbn:,.0f}")
        
        with c2:
            st.success(f"Jika dipindah ke **Obligasi AA** (Kupon {rate_bond_aa}%)")
            st.metric("Tambahan Cuan/Tahun", f"Rp {potensi_bond:,.0f}")

        # --- VISUALISASI ---
        st.subheader("📊 Analisis Perbandingan")
        v1, v2 = st.columns([2, 1])
        
        with v1:
            # Grafik Perbandingan 3 Instrumen (Net)
            labels = ['Deposito (Avg)', 'SBN (Bench)', 'Korporasi AA']
            values = [df['Net_Yield'].mean(), net_sbn, net_bond]
            fig_comp = go.Figure(data=[go.Bar(x=labels, y=values, marker_color=['gray', 'blue', 'green'])])
            fig_comp.update_layout(title="Perbandingan Yield Netto Rata-rata (%)", height=400)
            st.plotly_chart(fig_comp, use_container_width=True)
            
        with v2:
            fig_pie = px.pie(df, values='Nominal', names='Bank', title="Konsentrasi Dana")
            st.plotly_chart(fig_pie, use_container_width=True)

        # --- ALERTS ---
        st.subheader("⚠️ Action Items")
        a1, a2 = st.columns(2)
        with a1:
            near_mat = df[df['Sisa_Hari'] <= 30].sort_values('Sisa_Hari')
            if not near_mat.empty:
                st.warning(f"🔔 {len(near_mat)} Bilyet Jatuh Tempo < 30 Hari")
                st.dataframe(near_mat[['Bank', 'Nomor_Bilyet', 'Sisa_Hari']], use_container_width=True)
        with a2:
            if not df_pindah.empty:
                st.error(f"🚨 {len(df_pindah)} Bilyet Harus Dievaluasi (Gap > {threshold}%)")
                st.dataframe(df_pindah[['Bank', 'Nomor_Bilyet', 'Gap_vs_SBN']], use_container_width=True)

        # --- DETAIL TABLE ---
        st.subheader("📑 Inventory Detail")
        st.dataframe(df.style.background_gradient(subset=['Gap_vs_SBN'], cmap='Reds'), use_container_width=True)

    except Exception as e:
        st.error(f"Terjadi kesalahan: {e}")
else:
    st.info("👋 Halo Kiko! Silakan upload file data_deposito.xlsx untuk memulai.")
