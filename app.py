import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import pytz

# Konfigurasi Halaman
st.set_page_config(page_title="ASDP Treasury Command Center", layout="wide")
st.title("🚢 ASDP Integrated Treasury & ALM Command Center")

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

# --- SIDEBAR: GLOBAL SETTINGS ---
st.sidebar.header("⚙️ Market Intelligence")
sbn_live, source_status = get_live_market_data()
current_sbn = st.sidebar.number_input("Benchmark SBN 10Y (%)", value=sbn_live, step=0.01)
threshold = st.sidebar.slider("Threshold Pindah Dana (%)", 0.0, 10.0, 0.5)

st.sidebar.markdown("---")
st.sidebar.header("🏢 Risk Simulation (Rating)")
rating_pilihan = st.sidebar.selectbox("Simulasi Pindah ke Rating:", ["AAA", "AA+", "AA", "A"])
risk_notes = {
    "AAA": {"spread": 80, "desc": "🛡️ Stabil & Aman. Kapasitas sangat kuat."},
    "AA+": {"spread": 100, "desc": "✅ Sangat Kuat. Tahan guncangan ekonomi."},
    "AA": {"spread": 120, "desc": "✅ Kualitas Tinggi. Kapasitas kuat."},
    "A": {"spread": 260, "desc": "🚨 Investasi Layak, tapi Sensitif. Risiko downgrade lebih tinggi."}
}
est_yield_bond = current_sbn + (risk_notes[rating_pilihan]['spread']/100)

st.sidebar.markdown("---")
file_funding = st.sidebar.file_uploader("1. Upload Data Funding (Deposito)", type=["xlsx"])
file_lending = st.sidebar.file_uploader("2. Upload Data Lending (Anak Usaha)", type=["xlsx"])

# --- TAB SYSTEM ---
tab1, tab2 = st.tabs(["💰 Funding Monitoring (Full Version)", "📈 Lending & Gap Analysis"])

# ==========================================
# TAB 1: FUNDING (VERSI LENGKAP GAMBAR 3)
# ==========================================
with tab1:
    if file_funding:
        try:
            df_f = pd.read_excel(file_funding)
            df_f['Jatuh_Tempo'] = pd.to_datetime(df_f['Jatuh_Tempo'], errors='coerce')
            df_f['Net_Yield'] = df_f['Rate'] * 0.8
            net_sbn = current_sbn * 0.9
            net_bond = est_yield_bond * 0.9
            
            # Hitung Gap & Status
            df_f['Gap_vs_SBN'] = net_sbn - df_f['Net_Yield']
            df_f['Status'] = df_f['Gap_vs_SBN'].apply(lambda x: 'PINDAHKAN' if x >= threshold else 'TAHAN')
            df_f['Color'] = df_f['Status'].apply(lambda x: 'red' if x == 'PINDAHKAN' else 'green')

            # Metrics Atas (Gaya Gambar 3)
            m1, m2, m3 = st.columns(3)
            total_f = df_f['Nominal'].sum()
            m1.metric("Total Portfolio", f"Rp {total_f:,.0f}")
            m2.metric("SBN Yield (Net)", f"{net_sbn:.2f}%")
            
            df_pindah = df_f[df_f['Status'] == 'PINDAHKAN']
            cuan_hilang = (df_pindah['Nominal'] * (df_pindah['Gap_vs_SBN']/100)).sum()
            m3.metric("Potensi Tambahan Cuan", f"Rp {cuan_hilang:,.0f} / thn", delta_color="inverse")

            # Warning Jatuh Tempo
            df_f['Sisa_Hari'] = (df_f['Jatuh_Tempo'] - datetime.now()).dt.days
            near_mat = df_f[df_f['Sisa_Hari'] <= 30].dropna(subset=['Sisa_Hari'])
            if not near_mat.empty:
                st.warning(f"⚠️ Ada {len(near_mat)} bilyet jatuh tempo dalam 30 hari!")

            # Grafik Utama
            v1, v2 = st.columns([2, 1])
            with v1:
                fig_f = px.bar(df_f, x='Nomor_Bilyet', y='Net_Yield', color='Status',
                               color_discrete_map={'PINDAHKAN':'#ef553b', 'TAHAN':'#00cc96'},
                               title="Yield Net per Bilyet vs SBN Line")
                fig_f.add_hline(y=net_sbn, line_dash="dash", line_color="blue", annotation_text="SBN Net")
                st.plotly_chart(fig_f, use_container_width=True)
            with v2:
                fig_pie = px.pie(df_f, values='Nominal', names='Bank', title="Distribusi Dana")
                st.plotly_chart(fig_pie, use_container_width=True)

            st.subheader("📑 Detail Tabel Funding")
            st.dataframe(df_f.style.background_gradient(subset=['Gap_vs_SBN'], cmap='Reds'), use_container_width=True)

        except Exception as e:
            st.error(f"Error Funding: {e}")
    else:
        st.info("Silakan upload data Deposito.")

# ==========================================
# TAB 2: LENDING & GAP (FIX ERROR)
# ==========================================
with tab2:
    if file_lending:
        try:
            df_l = pd.read_excel(file_lending)
            # FIX: Bersihkan nama kolom dari spasi atau karakter aneh
            df_l.columns = [c.strip() for c in df_l.columns]
            
            # Mapping Kolom agar fleksibel
            col_map = {
                'Lending_Rate (%)': 'Lending_Rate (%)',
                'Cost_of_Fund (%)': 'Cost_of_Fund (%)',
                'Nominal_Lending': 'Nominal_Lending'
            }
            # Cari kolom yang mirip kalau gak ketemu yang pas
            for k in col_map.keys():
                if k not in df_l.columns:
                    for real_col in df_l.columns:
                        if k.split(' ')[0] in real_col:
                            df_l.rename(columns={real_col: k}, inplace=True)

            # Hitung Margin/Spread
            df_l['Spread'] = df_l['Lending_Rate (%)'] - df_l['Cost_of_Fund (%)']
            
            # Metrics
            l1, l2, l3 = st.columns(3)
            total_l = df_l['Nominal_Lending'].sum()
            avg_l_rate = (df_l['Nominal_Lending'] * df_l['Lending_Rate (%)']).sum() / total_l
            avg_cof = (df_l['Nominal_Lending'] * df_l['Cost_of_Fund (%)']).sum() / total_l
            l1.metric("Total Penyaluran", f"Rp {total_l:,.0f}")
            l2.metric("Avg. Lending Rate", f"{avg_l_rate:.2f}%")
            l3.metric("Net Interest Margin (NIM)", f"{(avg_l_rate - avg_cof):.2f}%")

            # Visualisasi Gap
            fig_l = go.Figure()
            fig_l.add_trace(go.Bar(x=df_l['Debitur'], y=df_l['Lending_Rate (%)'], name='Lending Rate', marker_color='#00cc96'))
            fig_l.add_trace(go.Bar(x=df_l['Debitur'], y=df_l['Cost_of_Fund (%)'], name='Cost of Fund', marker_color='#ef553b'))
            fig_l.update_layout(barmode='group', title="Spread per Debitur (Lending vs CoF)")
            st.plotly_chart(fig_l, use_container_width=True)

            st.subheader("📑 Detail Tabel Lending")
            st.dataframe(df_l.style.background_gradient(subset=['Spread'], cmap='RdYlGn'), use_container_width=True)

        except Exception as e:
            st.error(f"Error Lending: {e}. Pastikan nama kolom di Excel sesuai (Debitur, Nominal_Lending, Lending_Rate (%), Cost_of_Fund (%))")
    else:
        st.info("Silakan upload data Lending.")
