import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import pytz

# Konfigurasi Halaman
st.set_page_config(page_title="ASDP ALM Dashboard", layout="wide")
st.title("🚢 ASDP Integrated ALM Command Center")

# --- FUNGSI MARKET DATA ---
def get_live_market_data():
    try:
        ticker = "ID10Y=F"
        data = yf.Ticker(ticker).history(period="1d")
        val = round(float(data['Close'].iloc[-1]), 2)
        source = "Yahoo Finance (SBN 10Y)"
    except:
        val = 6.65 
        source = "Default/Manual"
    return val, source

# --- SIDEBAR: KONFIGURASI GLOBAL ---
st.sidebar.header("⚙️ Market Intelligence")
sbn_live, source_status = get_live_market_data()
current_sbn = st.sidebar.number_input("Benchmark SBN 10Y (%)", value=sbn_live, step=0.01)

st.sidebar.markdown("---")
st.sidebar.header("📂 Data Management")
file_funding = st.sidebar.file_uploader("1. Upload Data Funding (Deposito)", type=["xlsx"])
file_lending = st.sidebar.file_uploader("2. Upload Data Lending (Penyaluran)", type=["xlsx"])

# --- TAB SYSTEM ---
tab1, tab2 = st.tabs(["💰 Funding Monitoring", "📈 Lending & Gap Analysis"])

# ==========================================
# TAB 1: FUNDING MONITORING (LOGIKA LAMA)
# ==========================================
with tab1:
    if file_funding:
        try:
            df_f = pd.read_excel(file_funding)
            df_f['Jatuh_Tempo'] = pd.to_datetime(df_f['Jatuh_Tempo'], errors='coerce')
            df_f['Net_Yield'] = df_f['Rate'] * 0.8
            net_sbn = current_sbn * 0.9
            
            # Metrics
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Funding", f"Rp {df_f['Nominal'].sum():,.0f}")
            c2.metric("SBN Net Benchmark", f"{net_sbn:.2f}%")
            c3.metric("Avg. Funding Rate", f"{df_f['Rate'].mean():.2f}%")

            # Visualization
            fig_f = px.bar(df_f, x='Nomor_Bilyet', y='Net_Yield', color='Bank', title="Yield Deposito per Bilyet")
            fig_f.add_hline(y=net_sbn, line_dash="dash", line_color="red")
            st.plotly_chart(fig_f, use_container_width=True)
            
            st.subheader("📑 Detail Data Funding")
            st.dataframe(df_f, use_container_width=True)
        except Exception as e:
            st.error(f"Error Funding: {e}")
    else:
        st.info("Silakan upload file Data Deposito di sidebar.")

# ==========================================
# TAB 2: LENDING & GAP ANALYSIS (LOGIKA BARU)
# ==========================================
with tab2:
    if file_lending:
        try:
            df_l = pd.read_excel(file_lending)
            df_l['Tgl_Jatuh_Tempo'] = pd.to_datetime(df_l['Tgl_Jatuh_Tempo'], errors='coerce')
            
            # Hitung Spread (Margin)
            # Spread = Lending Rate - Cost of Fund
            df_l['Spread'] = df_l['Lending_Rate (%)'] - df_l['Cost_of_Fund (%)']
            
            # Weighted Averages
            total_lending = df_l['Nominal_Lending'].sum()
            avg_lending_rate = (df_l['Nominal_Lending'] * df_l['Lending_Rate (%)']).sum() / total_lending
            avg_cof = (df_l['Nominal_Lending'] * df_l['Cost_of_Fund (%)']).sum() / total_lending
            total_margin = avg_lending_rate - avg_cof

            # Metrics
            st.subheader("🎯 Ringkasan Portofolio Lending")
            l1, l2, l3 = st.columns(3)
            l1.metric("Total Penyaluran (Lending)", f"Rp {total_lending:,.0f}")
            l2.metric("Avg. Lending Rate", f"{avg_lending_rate:.2f}%")
            l3.metric("Net Interest Margin (NIM)", f"{total_margin:.2f}%", delta=f"{total_margin:.2f}%", delta_color="normal")

            # Visualization: Spread per Debitur
            st.markdown("---")
            st.subheader("📊 Analisis Margin per Debitur")
            
            # Grafik Waterfall atau Grouped Bar untuk Spread
            fig_spread = go.Figure()
            fig_spread.add_trace(go.Bar(x=df_l['Debitur'], y=df_l['Lending_Rate (%)'], name='Lending Rate', marker_color='green'))
            fig_spread.add_trace(go.Bar(x=df_l['Debitur'], y=df_l['Cost_of_Fund (%)'], name='Cost of Fund', marker_color='red'))
            fig_spread.update_layout(barmode='group', title="Lending Rate vs Cost of Fund per Anak Usaha")
            st.plotly_chart(fig_spread, use_container_width=True)

            # Analisis Gap & Risiko
            st.markdown("---")
            st.subheader("⚠️ Early Warning & Gap Analysis")
            
            col_a, col_b = st.columns(2)
            with col_a:
                # Cek pinjaman yang marginnya tipis (< 1%)
                low_margin = df_l[df_l['Spread'] < 1.0]
                if not low_margin.empty:
                    st.error(f"Ada {len(low_margin)} Debitur dengan margin sangat tipis (< 1%)!")
                    st.dataframe(low_margin[['Debitur', 'Spread', 'Bank_Sumber_Dana']])
                else:
                    st.success("Semua margin penyaluran dana masih di atas 1%. Aman!")
            
            with col_b:
                # Konsentrasi Debitur
                fig_pie_l = px.pie(df_l, values='Nominal_Lending', names='Debitur', title="Distribusi Eksposur Debitur")
                st.plotly_chart(fig_pie_l, use_container_width=True)

            st.subheader("📑 Detail Inventori Lending")
            st.dataframe(df_l.style.background_gradient(subset=['Spread'], cmap='RdYlGn'), use_container_width=True)

        except Exception as e:
            st.error(f"Error Lending: {e}")
    else:
        st.info("Silakan upload file Data Lending di sidebar.")
