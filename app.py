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

# --- SIDEBAR: KONFIGURASI ---
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
file_funding = st.sidebar.file_uploader("Upload Data Funding (Deposito)", type=["xlsx"])
file_lending = st.sidebar.file_uploader("Upload Data Lending (Anak Usaha)", type=["xlsx"])

# Inisialisasi DataFrame Global untuk Tab 3
df_f = pd.DataFrame()
df_l = pd.DataFrame()

tab1, tab2, tab3 = st.tabs(["💰 Funding Monitoring", "📈 Lending Monitoring", "📊 ALM Resume & Strategy"])

# ==========================================
# TAB 1: FUNDING
# ==========================================
with tab1:
    if file_funding:
        df_f = pd.read_excel(file_funding)
        df_f['Jatuh_Tempo'] = pd.to_datetime(df_f['Jatuh_Tempo'], errors='coerce')
        df_f['Net_Yield'] = df_f['Rate'] * 0.8
        net_sbn = current_sbn * 0.9
        df_f['Gap_vs_SBN'] = net_sbn - df_f['Net_Yield']
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Funding", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric("SBN Net", f"{net_sbn:.2f}%")
        df_pindah = df_f[df_f['Gap_vs_SBN'] >= threshold]
        pot_sbn = (df_pindah['Nominal'] * (df_pindah['Gap_vs_SBN']/100)).sum()
        m3.metric("Potensi Tambahan Cuan", f"Rp {pot_sbn:,.0f}")

        v1, v2 = st.columns([2, 1])
        with v1:
            fig_f = px.bar(df_f, x='Nomor_Bilyet', y='Net_Yield', color='Gap_vs_SBN', color_continuous_scale='RdYlGn_r', title="Yield Deposito")
            fig_f.add_hline(y=net_sbn, line_dash="dash", line_color="blue")
            st.plotly_chart(fig_f, use_container_width=True)
        with v2:
            st.info(f"🛡️ **Rating {rating_pilihan}:** {risk_notes[rating_pilihan]['desc']}")
            st.dataframe(df_f[['Bank', 'Nominal', 'Rate']], use_container_width=True)

# ==========================================
# TAB 2: LENDING
# ==========================================
with tab2:
    if file_lending:
        df_l = pd.read_excel(file_lending)
        df_l.columns = [c.strip() for c in df_l.columns]
        df_l['Spread'] = df_l['Lending_Rate (%)'] - df_l['Cost_of_Fund (%)']
        
        l1, l2, l3 = st.columns(3)
        l1.metric("Total Lending", f"Rp {df_l['Nominal_Lending'].sum():,.0f}")
        l2.metric("Avg. Lending Rate", f"{df_l['Lending_Rate (%)'].mean():.2f}%")
        l3.metric("Avg. Margin (NIM)", f"{df_l['Spread'].mean():.2f}%")

        fig_l = go.Figure()
        fig_l.add_trace(go.Bar(x=df_l['Debitur'], y=df_l['Lending_Rate (%)'], name='Lending Rate', marker_color='green'))
        fig_l.add_trace(go.Bar(x=df_l['Debitur'], y=df_l['Cost_of_Fund (%)'], name='Cost of Fund', marker_color='red'))
        st.plotly_chart(fig_l, use_container_width=True)

# ==========================================
# TAB 3: ALM STRATEGIC RESUME
# ==========================================
with tab3:
    if not df_f.empty and not df_l.empty:
        st.subheader("📋 Kertas Kerja: Strategi Asset Liability Management")
        
        # --- KALKULASI CASH FLOW BULANAN ---
        # Asumsi bunga dibayar bulanan: (Nominal * Rate) / 12
        # Asumsi pokok dibayar bulanan (Simplified: Nominal / 12 - jika tenor 1 thn)
        # Kiko bisa menyesuaikan ini di excel nanti jika ada kolom Tenor
        
        monthly_interest_income = (df_l['Nominal_Lending'] * (df_l['Lending_Rate (%)']/100) / 12).sum()
        monthly_interest_expense = (df_l['Nominal_Lending'] * (df_l['Cost_of_Fund (%)']/100) / 12).sum()
        
        st.markdown("### 💸 Monthly Obligations Coverage")
        c1, c2, c3 = st.columns(3)
        
        c1.metric("Est. Monthly Inflow (Bunga)", f"Rp {monthly_interest_income:,.0f}")
        c2.metric("Est. Monthly Outflow (CoF)", f"Rp {monthly_interest_expense:,.0f}")
        
        net_monthly_surplus = monthly_interest_income - monthly_interest_expense
        c3.metric("Net Interest Spread (Cash)", f"Rp {net_monthly_surplus:,.0f}", 
                  delta=f"{(monthly_interest_income/monthly_interest_expense):.2f}x Cover")

        # --- REKOMENDASI ALOKASI ---
        st.markdown("---")
        st.subheader("💡 Strategic Recommendation")
        
        col_res1, col_res2 = st.columns([1, 1])
        
        with col_res1:
            total_funding = df_f['Nominal'].sum()
            total_lending = df_l['Nominal_Lending'].sum()
            liquidity_gap = total_funding - total_lending
            
            if liquidity_gap > 0:
                st.success(f"✅ **SURPLUS LIKUIDITAS: Rp {liquidity_gap:,.0f}**")
                st.write("Dana menganggur ini harus segera dialokasikan agar tidak terjadi *negative carry*.")
                st.markdown(f"""
                **Pilihan Alokasi Sisa Dana:**
                * **Opsi 1 (Konservatif):** SBN 10Y (Net {current_sbn*0.9:.2f}%)
                * **Opsi 2 (Moderat):** Obligasi {rating_pilihan} (Net {est_yield_bond*0.9:.2f}%)
                """)
            else:
                st.error(f"🚨 **DEFISIT LIKUIDITAS: Rp {abs(liquidity_gap):,.0f}**")
                st.write("Eksposur Lending lebih besar dari Funding. ASDP butuh tambahan likuiditas segera.")

        with col_res2:
            # Gauge Chart untuk Coverage Ratio
            coverage_ratio = (monthly_interest_income / monthly_interest_expense) if monthly_interest_expense > 0 else 0
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = coverage_ratio,
                title = {'text': "Interest Coverage Ratio (x)"},
                gauge = {
                    'axis': {'range': [0, 5]},
                    'bar': {'color': "green" if coverage_ratio > 1.2 else "red"},
                    'steps': [
                        {'range': [0, 1], 'color': "red"},
                        {'range': [1, 1.2], 'color': "yellow"},
                        {'range': [1.2, 5], 'color': "lightgreen"}]
                }
            ))
            st.plotly_chart(fig_gauge, use_container_width=True)

        st.info("**Catatan Strategis:** Analisis di atas memastikan bahwa pendapatan bunga dari anak usaha sanggup menutupi biaya bunga ke bank. Jika ratio < 1.0, ASDP 'nombok' bunga setiap bulannya.")

    else:
        st.info("Harap upload data Funding dan Lending untuk melihat resume strategis.")
