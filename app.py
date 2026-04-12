import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import pytz

# Konfigurasi Halaman
st.set_page_config(page_title="ASDP Treasury Command Center", layout="wide")
st.title("🚢 ASDP Integrated Treasury & ALM Dashboard")

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

# --- SIDEBAR: KONFIGURASI PERSIS SEPERTI GAMBAR ---
st.sidebar.header("⚙️ Market Intelligence")
sbn_live, source_status = get_live_market_data()
current_sbn = st.sidebar.number_input("Benchmark SBN 10Y (%)", value=sbn_live, step=0.01)
threshold = st.sidebar.slider("Threshold Pindah Dana (%)", 0.0, 10.0, 0.5)

st.sidebar.markdown("---")
st.sidebar.header("🛡️ Credit Risk Simulation")
rating_pilihan = st.sidebar.selectbox("Pilih Rating Simulasi:", ["AAA", "AA+", "AA", "A"])

# Logika Spread & Risk Note
risk_notes = {
    "AAA": {"spread": 80, "desc": "Stabil & Aman. Kapasitas sangat kuat. Risiko gagal bayar hampir nol."},
    "AA+": {"spread": 100, "desc": "Sangat Kuat. Sedikit di bawah AAA, tahan terhadap perubahan ekonomi."},
    "AA": {"spread": 120, "desc": "Kualitas Tinggi. Kapasitas kuat, namun sedikit rentan terhadap efek ekonomi jangka panjang."},
    "A": {"spread": 260, "desc": "Investasi Layak, tapi Sensitif. Kapasitas masih kuat, namun gampang melemah jika ekonomi memburuk."}
}

selected_spread = st.sidebar.slider(f"Spread {rating_pilihan} (bps)", 30, 450, risk_notes[rating_pilihan]["spread"])
est_yield_bond = current_sbn + (selected_spread/100)

st.sidebar.markdown("---")
file_funding = st.sidebar.file_uploader("Upload Data Funding (Deposito)", type=["xlsx"])
file_lending = st.sidebar.file_uploader("Upload Data Lending (Anak Usaha)", type=["xlsx"])

# --- TAB SYSTEM ---
tab1, tab2 = st.tabs(["💰 Funding Monitoring (Full Version)", "📈 Lending & Gap Analysis"])

# ==========================================
# TAB 1: FUNDING (KEMBALI KE VERSI MEWAH)
# ==========================================
with tab1:
    if file_funding:
        try:
            df_f = pd.read_excel(file_funding)
            df_f['Jatuh_Tempo'] = pd.to_datetime(df_f['Jatuh_Tempo'], errors='coerce')
            df_f['Net_Yield'] = df_f['Rate'] * 0.8
            net_sbn = current_sbn * 0.9
            net_simulasi = est_yield_bond * 0.9
            df_f['Gap_vs_SBN'] = net_sbn - df_f['Net_Yield']
            df_f['Sisa_Hari'] = (df_f['Jatuh_Tempo'] - datetime.now()).dt.days
            
            # 1. Metrics Atas
            tz_jkt = pytz.timezone('Asia/Jakarta')
            st.caption(f"Update: {datetime.now(tz_jkt).strftime('%d/%m/%Y %H:%M')} WIB")
            
            m1, m2, m3 = st.columns(3)
            total_f = df_f['Nominal'].sum()
            m1.metric("Total Portfolio", f"Rp {total_f:,.0f}")
            m2.metric("SBN Net (Risk-Free)", f"{net_sbn:.2f}%")
            m3.metric(f"Simulasi Net {rating_pilihan}", f"{net_simulasi:.2f}%")

            # 2. Risk Assessment Box (Persis Gambar)
            st.subheader(f"⚠️ Risk Assessment: Penempatan di Rating {rating_pilihan}")
            if rating_pilihan == "A":
                st.error(f"🚨 **WARNING RISIKO RATING A:** {risk_notes['A']['desc']}")
                st.markdown("""
                * **Credit Migration Risk:** Lebih mudah 'turun kasta' (downgrade) ke rating BBB jika ekonomi melambat.
                * **Liquidity Risk:** Di pasar sekunder, obligasi rating A lebih sulit dijual cepat dibanding AAA/AA.
                * **Spread Volatility:** Jika terjadi krisis, harga obligasi rating A akan jatuh lebih dalam.
                """)
            else:
                st.info(f"🛡️ **PROFIL RISIKO {rating_pilihan}:** {risk_notes[rating_pilihan]['desc']}")

            # 3. Potensi Cuan (Dua Kolom)
            st.divider()
            c1, c2 = st.columns(2)
            df_pindah = df_f[df_f['Gap_vs_SBN'] >= threshold]
            pot_sbn = (df_pindah['Nominal'] * (net_sbn - df_pindah['Net_Yield'])/100).sum()
            pot_sim = (df_pindah['Nominal'] * (net_simulasi - df_pindah['Net_Yield'])/100).sum()

            c1.metric("Cuan Tambahan (Pindah ke SBN)", f"Rp {pot_sbn:,.0f}")
            c2.metric(f"Cuan Tambahan (Pindah ke {rating_pilihan})", f"Rp {pot_sim:,.0f}")

            # 4. Visualisasi
            v1, v2 = st.columns([2, 1])
            with v1:
                fig_f = px.bar(df_f, x='Nomor_Bilyet', y='Net_Yield', color='Gap_vs_SBN', 
                                 title="Yield per Bilyet vs Benchmark", color_continuous_scale='RdYlGn_r')
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
        st.info("Silakan upload data Deposito.")

# ==========================================
# TAB 2: LENDING (FIX ERROR KOLOM)
# ==========================================
with tab2:
    if file_lending:
        try:
            df_l = pd.read_excel(file_lending)
            # Membersihkan spasi pada nama kolom agar tidak KeyError
            df_l.columns = [c.strip() for c in df_l.columns]
            
            # Hitung Margin
            df_l['Spread'] = df_l['Lending_Rate (%)'] - df_l['Cost_of_Fund (%)']
            total_l = df_l['Nominal_Lending'].sum()
            
            # Metrics
            l1, l2, l3 = st.columns(3)
            l1.metric("Total Penyaluran", f"Rp {total_l:,.0f}")
            l2.metric("Avg. Lending Rate", f"{df_l['Lending_Rate (%)'].mean():.2f}%")
            l3.metric("Avg. Margin (Spread)", f"{df_l['Spread'].mean():.2f}%")

            # Chart
            fig_l = go.Figure()
            fig_l.add_trace(go.Bar(x=df_l['Debitur'], y=df_l['Lending_Rate (%)'], name='Lending Rate', marker_color='green'))
            fig_l.add_trace(go.Bar(x=df_l['Debitur'], y=df_l['Cost_of_Fund (%)'], name='Cost of Fund', marker_color='red'))
            fig_l.update_layout(barmode='group', title="Lending Rate vs CoF")
            st.plotly_chart(fig_l, use_container_width=True)

            st.dataframe(df_l.style.background_gradient(subset=['Spread'], cmap='RdYlGn'), use_container_width=True)
        except Exception as e:
            st.error(f"Error Lending: {e}. Periksa nama kolom (Lending_Rate (%), Cost_of_Fund (%))")
    else:
        st.info("Silakan upload data Lending.")
