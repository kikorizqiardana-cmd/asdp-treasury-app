import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import pytz

# Konfigurasi Halaman
st.set_page_config(page_title="ASDP ALM Command Center", layout="wide")
st.title("🚢 ASDP Integrated Treasury & ALM Strategic Dashboard")

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

# --- SIDEBAR ---
st.sidebar.header("⚙️ Market Intelligence")
sbn_live, source_status = get_live_market_data()
current_sbn = st.sidebar.number_input("Benchmark SBN 10Y (%)", value=sbn_live, step=0.01)
threshold = st.sidebar.slider("Threshold Pindah Dana (%)", 0.0, 10.0, 0.5)

st.sidebar.markdown("---")
st.sidebar.header("🛡️ Credit Risk Simulation")
rating_pilihan = st.sidebar.selectbox("Pilih Rating Simulasi:", ["AAA", "AA+", "AA", "A"])
risk_notes = {
    "AAA": {"spread": 80, "desc": "🛡️ Stabil & Aman. Kapasitas sangat kuat."},
    "AA+": {"spread": 100, "desc": "✅ Sangat Kuat. Tahan guncangan."},
    "AA": {"spread": 120, "desc": "✅ Kualitas Tinggi. Kapasitas kuat."},
    "A": {"spread": 260, "desc": "🚨 Sensitif. Risiko downgrade lebih tinggi."}
}
selected_spread = st.sidebar.slider(f"Spread {rating_pilihan} (bps)", 30, 450, risk_notes[rating_pilihan]["spread"])
est_yield_bond = current_sbn + (selected_spread/100)

st.sidebar.markdown("---")
file_funding = st.sidebar.file_uploader("1. Upload Data Funding (Deposito)", type=["xlsx"])
file_lending = st.sidebar.file_uploader("2. Upload Data Lending (Anak Usaha)", type=["xlsx"])

# Inisialisasi Data Global
df_f = pd.DataFrame()
df_l = pd.DataFrame()

tab1, tab2, tab3 = st.tabs(["💰 Funding Monitoring (WS 1)", "📈 Lending Monitoring (WS 2)", "📊 ALM Resume (WS 3)"])

# ==========================================
# TAB 1: FUNDING (PERSIS SCREENSHOT WS 1)
# ==========================================
with tab1:
    if file_funding:
        try:
            df_f = pd.read_excel(file_funding)
            df_f['Jatuh_Tempo'] = pd.to_datetime(df_f['Jatuh_Tempo'], errors='coerce')
            df_f['Net_Yield'] = df_f['Rate'] * 0.8
            net_sbn = current_sbn * 0.9
            net_sim = est_yield_bond * 0.9
            df_f['Gap_vs_SBN'] = net_sbn - df_f['Net_Yield']
            
            # Metrics Row
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Portfolio", f"Rp {df_f['Nominal'].sum():,.0f}")
            m2.metric("SBN Net (Risk-Free)", f"{net_sbn:.2f}%")
            m3.metric(f"Simulasi Net {rating_pilihan}", f"{net_sim:.2f}%")

            # Risk Assessment Box
            st.subheader(f"⚠️ Risk Assessment: Penempatan di Rating {rating_pilihan}")
            if rating_pilihan == "A":
                st.error(f"🚨 **WARNING RISIKO RATING A:** Investasi Layak, tapi Sensitif. Kapasitas masih kuat, namun gampang melemah jika ekonomi memburuk.")
                st.markdown("""
                * **Credit Migration Risk:** Lebih mudah 'turun kasta' (downgrade) ke rating BBB jika ekonomi melambat.
                * **Liquidity Risk:** Di pasar sekunder, obligasi rating A lebih sulit dijual cepat dibanding AAA/AA.
                * **Spread Volatility:** Jika terjadi krisis, harga obligasi rating A akan jatuh lebih dalam.
                """)
            else:
                st.info(f"🛡️ **PROFIL RISIKO {rating_pilihan}:** {risk_notes[rating_pilihan]['desc']}")

            # Cuan Tambahan
            st.divider()
            c1, c2 = st.columns(2)
            df_pindah = df_f[df_f['Gap_vs_SBN'] >= threshold]
            pot_sbn = (df_pindah['Nominal'] * (net_sbn - df_pindah['Net_Yield'])/100).sum()
            pot_sim = (df_pindah['Nominal'] * (net_sim - df_pindah['Net_Yield'])/100).sum()
            c1.metric("Cuan Tambahan (Pindah ke SBN)", f"Rp {pot_sbn:,.0f}")
            c2.metric(f"Cuan Tambahan (Pindah ke {rating_pilihan})", f"Rp {pot_sim:,.0f}")

            # Charts
            v1, v2 = st.columns([2, 1])
            with v1:
                fig_f = px.bar(df_f, x='Nomor_Bilyet', y='Net_Yield', color='Gap_vs_SBN', 
                               color_continuous_scale='RdYlGn_r', title="Yield per Bilyet vs Benchmark")
                fig_f.add_hline(y=net_sbn, line_dash="dash", line_color="blue", annotation_text="SBN Net")
                st.plotly_chart(fig_f, use_container_width=True)
            with v2:
                fig_pie = px.pie(df_f, values='Nominal', names='Bank', title="Konsentrasi Dana")
                st.plotly_chart(fig_pie, use_container_width=True)

            st.subheader("📑 Detail Tabel Inventori")
            st.dataframe(df_f.style.background_gradient(subset=['Gap_vs_SBN'], cmap='Reds'), use_container_width=True)
        except Exception as e:
            st.error(f"Error Funding: {e}")
    else:
        st.info("Harap upload file Funding (Deposito).")

# ==========================================
# TAB 2: LENDING (PERSIS SCREENSHOT WS 2)
# ==========================================
with tab2:
    if file_lending:
        try:
            df_l = pd.read_excel(file_lending)
            df_l.columns = [c.strip() for c in df_l.columns]
            df_l['Spread'] = df_l['Lending_Rate (%)'] - df_l['Cost_of_Fund (%)']
            
            # Metrics
            l1, l2, l3 = st.columns(3)
            l1.metric("Total Penyaluran", f"Rp {df_l['Nominal_Lending'].sum():,.0f}")
            l2.metric("Avg. Lending Rate", f"{df_l['Lending_Rate (%)'].mean():.2f}%")
            l3.metric("Avg. Margin (Spread)", f"{df_l['Spread'].mean():.2f}%")

            # Chart Lending vs CoF
            fig_l = go.Figure()
            fig_l.add_trace(go.Bar(x=df_l['Debitur'], y=df_l['Lending_Rate (%)'], name='Lending Rate', marker_color='green'))
            fig_l.add_trace(go.Bar(x=df_l['Debitur'], y=df_l['Cost_of_Fund (%)'], name='Cost of Fund', marker_color='red'))
            fig_l.update_layout(barmode='group', title="Lending Rate vs Cost of Fund")
            st.plotly_chart(fig_l, use_container_width=True)

            st.subheader("📑 Detail Tabel Lending")
            st.dataframe(df_l.style.background_gradient(subset=['Spread'], cmap='RdYlGn'), use_container_width=True)
        except Exception as e:
            st.error(f"Error Lending: {e}")
    else:
        st.info("Harap upload file Lending (Anak Usaha).")

# ==========================================
# TAB 3: ALM RESUME (COVER POKOK + BUNGA)
# ==========================================
with tab3:
    if not df_f.empty and not df_l.empty:
        st.subheader("📋 Resume ALM: Kemampuan Bayar Pokok & Bunga")
        
        # Simulasi Bulanan (Asumsi Tenor Rata-rata 12 Bulan)
        inflow_bunga = (df_l['Nominal_Lending'] * (df_l['Lending_Rate (%)']/100) / 12).sum()
        inflow_pokok = (df_l['Nominal_Lending'] / 12).sum()
        total_inflow = inflow_bunga + inflow_pokok
        
        outflow_bunga = (df_l['Nominal_Lending'] * (df_l['Cost_of_Fund (%)']/100) / 12).sum()
        outflow_pokok = (df_l['Nominal_Lending'] / 12).sum() 
        total_outflow = outflow_bunga + outflow_pokok
        
        r1, r2, r3 = st.columns(3)
        r1.metric("Total Inflow (Debitur)", f"Rp {total_inflow:,.0f}")
        r2.metric("Total Outflow (Bank)", f"Rp {total_outflow:,.0f}")
        
        coverage = total_inflow / total_outflow if total_outflow > 0 else 0
        r3.metric("Cashflow Coverage Ratio", f"{coverage:.2f}x", 
                  delta=f"Rp {total_inflow - total_outflow:,.0f} Surplus/Bulan")

        # Visualisasi Strategi
        st.markdown("---")
        st.subheader("💡 Strategic Insight")
        
        col_res1, col_res2 = st.columns([1, 1])
        with col_res1:
            if coverage >= 1.1:
                st.success(f"✅ **CASHFLOW SEHAT**: Setoran dari Debitur sanggup menutup Pokok + Bunga ke Bank.")
            else:
                st.error(f"🚨 **DEFISIT CASHFLOW**: Pendapatan dari Debitur mepet/kurang untuk bayar kewajiban!")
            
            liquidity_surplus = df_f['Nominal'].sum() - df_l['Nominal_Lending'].sum()
            st.info(f"Sisa dana menganggur di Funding: **Rp {liquidity_surplus:,.0f}**. Rekomendasi: Masukkan ke SBN Net ({net_sbn:.2f}%) untuk optimasi yield.")

        with col_res2:
            fig_res = go.Figure(data=[
                go.Bar(name='Cash Inflow (Anak Usaha)', x=['Bulanan'], y=[total_inflow], marker_color='green'),
                go.Bar(name='Cash Outflow (Kewajiban)', x=['Bulanan'], y=[total_outflow], marker_color='red')
            ])
            fig_res.update_layout(title="Kecukupan Arus Kas: Pokok + Bunga", barmode='group')
            st.plotly_chart(fig_res, use_container_width=True)
    else:
        st.warning("Silakan upload kedua data (Funding & Lending) untuk melihat WS 3.")
