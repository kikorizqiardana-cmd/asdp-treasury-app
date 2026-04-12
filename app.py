import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="ASDP Treasury Dashboard", layout="wide")
st.title("🚢 ASDP Smart Treasury Dashboard")

# --- SIDEBAR ---
st.sidebar.header("Konfigurasi & Input")
uploaded_file = st.sidebar.file_uploader("Upload Data Deposito (Excel)", type=["xlsx"])

def get_market_rate():
    try:
        data = yf.Ticker("ID10Y=F").history(period="1d")
        return round(float(data['Close'].iloc[-1]), 2)
    except:
        return 6.50

current_sbn = st.sidebar.number_input("Benchmark SBN (%)", value=get_market_rate())
threshold = st.sidebar.slider("Threshold Pindah Dana (%)", 0.0, 2.0, 0.5)

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        
        # --- VALIDASI KOLOM ---
        required_cols = ['Bank', 'Nomor_Bilyet', 'Nominal', 'Rate', 'Jatuh_Tempo']
        missing_cols = [c for c in required_cols if c not in df.columns]
        
        if missing_cols:
            st.error(f"❌ File Excel kamu kurang kolom: {', '.join(missing_cols)}")
            st.stop()

        # --- PROSES DATA (DENGAN PENGAMAN) ---
        # errors='coerce' artinya kalau ada tanggal aneh, dijadikan 'NaT' (kosong) bukan bikin error
        df['Jatuh_Tempo'] = pd.to_datetime(df['Jatuh_Tempo'], errors='coerce')
        
        # Buat kolom Sisa_Hari
        df['Sisa_Hari'] = (df['Jatuh_Tempo'] - datetime.now()).dt.days
        
        df['Net_Yield'] = df['Rate'] * 0.8
        net_sbn = current_sbn * 0.9
        df['Gap'] = net_sbn - df['Net_Yield']
        
        # --- DASHBOARD UTAMA ---
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Portfolio", f"Rp {df['Nominal'].sum():,.0f}")
        col2.metric("SBN Yield (Net)", f"{net_sbn:.2f}%")
        
        loss_yield = (df[df['Gap'] > threshold]['Nominal'] * (df['Gap']/100)).sum()
        col3.metric("Potensi Cuan Hilang", f"Rp {loss_yield:,.0f}")

        # Alert Jatuh Tempo
        near_maturity = df[df['Sisa_Hari'] <= 30].dropna(subset=['Sisa_Hari'])
        if not near_maturity.empty:
            st.warning(f"⚠️ Ada {len(near_maturity)} bilyet jatuh tempo dalam 30 hari!")
            st.dataframe(near_maturity[['Bank', 'Nomor_Bilyet', 'Jatuh_Tempo', 'Sisa_Hari']])

        # Visualisasi
        c1, c2 = st.columns(2)
        with c1:
            fig_bar = px.bar(df, x='Nomor_Bilyet', y='Net_Yield', color='Gap',
                             title="Yield Net per Bilyet vs SBN",
                             color_continuous_scale='RdYlGn_r')
            fig_bar.add_hline(y=net_sbn, line_dash="dash", line_color="blue")
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with c2:
            bank_dist = df.groupby('Bank')['Nominal'].sum().reset_index()
            fig_pie = px.pie(bank_dist, values='Nominal', names='Bank', title="Distribusi Dana")
            st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("📑 Detail Tabel")
        st.dataframe(df.style.background_gradient(subset=['Gap'], cmap='Reds'))

    except Exception as e:
        st.error(f"Terjadi kesalahan saat membaca file: {e}")
else:
    st.info("Silakan upload file Excel. Pastikan ada kolom: Bank, Nomor_Bilyet, Nominal, Rate, dan Jatuh_Tempo.")
