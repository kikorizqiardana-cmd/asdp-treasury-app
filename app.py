import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime

# Konfigurasi Halaman
st.set_page_config(page_title="ASDP Treasury Dashboard", layout="wide")

st.title("🚢 ASDP Smart Treasury Dashboard")
st.markdown("Automated Yield Tracker & Maturity Alert")

# --- SIDEBAR: INPUT & MARKET DATA ---
st.sidebar.header("Konfigurasi & Input")
uploaded_file = st.sidebar.file_uploader("Upload Data Deposito (Excel)", type=["xlsx"])

def get_market_rate():
    try:
        data = yf.Ticker("ID10Y=F").history(period="1d")
        return round(data['Close'].iloc[-1], 2)
    except:
        return 6.50 # Default jika koneksi gagal

current_sbn = st.sidebar.number_input("Benchmark SBN (%)", value=get_market_rate())
threshold = st.sidebar.slider("Threshold Pindah Dana (%)", 0.0, 2.0, 0.5)

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    # Preprocessing Data
    df['Jatuh_Tempo'] = pd.to_datetime(df['Jatuh_Tempo'])
    df['Sisa_Hari'] = (df['Jatuh_Tempo'] - datetime.now()).dt.days
    df['Net_Yield'] = df['Rate'] * 0.8
    net_sbn = current_sbn * 0.9
    df['Gap'] = net_sbn - df['Net_Yield']
    
    # --- METRICS DASHBOARD ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Portfolio", f"Rp {df['Nominal'].sum():,.0f}")
    col2.metric("SBN Yield (Net)", f"{net_sbn:.2f}%")
    
    loss_yield = (df[df['Gap'] > threshold]['Nominal'] * (df['Gap']/100)).sum()
    col3.metric("Potensi Cuan Hilang", f"Rp {loss_yield:,.0f}", delta_color="inverse")

    # --- ALERT SECTION ---
    st.subheader("⚠️ Alerts & Reminders")
    
    # 1. Alert Jatuh Tempo (Kurang dari 30 hari)
    near_maturity = df[df['Sisa_Hari'] <= 30]
    if not near_maturity.empty:
        st.warning(f"Ada {len(near_maturity)} bilyet yang akan jatuh tempo dalam 30 hari!")
        st.dataframe(near_maturity[['Bank', 'Nomor_Bilyet', 'Jatuh_Tempo', 'Sisa_Hari']])

    # 2. Alert Yield Rendah
    underperform = df[df['Gap'] >= threshold]
    if not underperform.empty:
        st.error(f"Ada {len(underperform)} penempatan yang yield-nya jauh di bawah SBN!")

    # --- VISUALISASI ---
    st.subheader("📊 Analisis Portofolio")
    c1, c2 = st.columns(2)
    
    with c1:
        fig_bar = px.bar(df, x='Nomor_Bilyet', y='Net_Yield', color='Gap',
                         title="Yield Net per Bilyet vs Benchmark",
                         color_continuous_scale='RdYlGn_r')
        fig_bar.add_hline(y=net_sbn, line_dash="dash", line_color="blue", annotation_text="SBN Net")
        st.plotly_chart(fig_bar, use_container_width=True)
        
    with c2:
        fig_pie = px.pie(df, values='Nominal', names='Bank', title="Distribusi Dana per Bank")
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- DETAIL TABLE ---
    st.subheader("📑 Detail Seluruh Penempatan")
    st.dataframe(df.style.background_gradient(subset=['Gap'], cmap='Reds'))

else:
    st.info("Silakan upload file Excel kamu di sidebar untuk memulai analisis.")
