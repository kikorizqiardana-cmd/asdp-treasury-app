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
        val = 6.65 
        source = "Default/Manual"
    return val, source

# --- SIDEBAR: KONFIGURASI ---
st.sidebar.header("⚙️ Market Intelligence")
sbn_live, source_status = get_live_market_data()
current_sbn = st.sidebar.number_input("Benchmark SBN 10Y (%)", value=sbn_live, step=0.01)
threshold = st.sidebar.slider("Threshold Pindah Dana (%)", 0.0, 10.0, 0.5)

st.sidebar.markdown("---")
st.sidebar.header("🏢 Credit Risk Simulation")
rating_pilihan = st.sidebar.selectbox("Pilih Rating Simulasi:", ["AAA", "AA+", "AA", "A"])

# Logika Spread & Risk Note berdasarkan Rating
risk_notes = {
    "AAA": {"spread": 80, "color": "blue", "desc": "Stabil & Aman. Kapasitas pembayaran bunga dan pokok sangat kuat. Risiko gagal bayar hampir nol."},
    "AA+": {"spread": 100, "color": "green", "desc": "Sangat Kuat. Sedikit di bawah AAA, namun sangat tahan terhadap perubahan kondisi ekonomi."},
    "AA": {"spread": 120, "color": "green", "desc": "Kualitas Tinggi. Kapasitas kuat, namun sedikit lebih rentan terhadap efek jangka panjang ekonomi dibanding AAA."},
    "A": {"spread": 260, "color": "orange", "desc": "Investasi Layak, tapi Sensitif. Kapasitas pembayaran masih kuat, namun perubahan kondisi ekonomi/bisnis dapat melemahkan kapasitas tersebut secara signifikan."}
}

selected_spread = st.sidebar.slider(f"Spread {rating_pilihan} (bps)", 30, 450, risk_notes[rating_pilihan]["spread"])
estimated_yield = current_sbn + (selected_spread/100)

uploaded_file = st.sidebar.file_uploader("Upload Data Deposito (Excel)", type=["xlsx"])

if uploaded_file:
    try:
        df_raw = pd.read_excel(uploaded_file)
        df_raw['Jatuh_Tempo'] = pd.to_datetime(df_raw['Jatuh_Tempo'], errors='coerce')
        
        list_bank = sorted(df_raw['Bank'].unique())
        selected_banks = st.sidebar.multiselect("Filter Bank:", options=list_bank, default=list_bank)
        df = df_raw[df_raw['Bank'].isin(selected_banks)].copy()

        # --- KALKULASI YIELD ---
        df['Net_Yield'] = df['Rate'] * 0.8
        net_sbn = current_sbn * 0.9
        net_simulasi = estimated_yield * 0.9
        df['Gap_vs_SBN'] = net_sbn - df['Net_Yield']
        df['Sisa_Hari'] = (df['Jatuh_Tempo'] - datetime.now()).dt.days
        
        # --- TOP METRICS ---
        tz_jkt = pytz.timezone('Asia/Jakarta')
        st.caption(f"Update: {datetime.now(tz_jkt).strftime('%d/%m/%Y %H:%M')} WIB")
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Portfolio", f"Rp {df['Nominal'].sum():,.0f}")
        m2.metric("SBN Net (Risk-Free)", f"{net_sbn:.2f}%")
        m3.metric(f"Simulasi Net {rating_pilihan}", f"{net_simulasi:.2f}%")

        # --- RISK WARNING SECTION (NOTIFIKASI OTOMATIS) ---
        st.subheader(f"⚠️ Risk Assessment: Penempatan di Rating {rating_pilihan}")
        if rating_pilihan == "A":
            st.error(f"🚨 **WARNING RISIKO RATING A:** {risk_notes['A']['desc']}")
            st.markdown("""
            * **Credit Migration Risk:** Lebih mudah 'turun kasta' (downgrade) ke rating BBB jika ekonomi melambat.
            * **Liquidity Risk:** Di pasar sekunder, obligasi rating A lebih sulit dijual cepat dibanding AAA/AA.
            * **Spread Volatility:** Jika terjadi krisis, harga obligasi rating A akan jatuh lebih dalam dibanding rating yang lebih tinggi.
            """)
        elif rating_pilihan in ["AA", "AA+"]:
            st.success(f"✅ **PROFIL RISIKO {rating_pilihan}:** {risk_notes[rating_pilihan]['desc']}")
        else:
            st.info(f"🛡️ **PROFIL RISIKO {rating_pilihan}:** {risk_notes[rating_pilihan]['desc']}")

        # --- OPTIMALISASI ---
        st.divider()
        c1, c2 = st.columns(2)
        df_pindah = df[df['Gap_vs_SBN'] >= threshold]
        pot_sbn = (df_pindah['Nominal'] * (net_sbn - df_pindah['Net_Yield'])/100).sum()
        pot_sim = (df_pindah['Nominal'] * (net_simulasi - df_pindah['Net_Yield'])/100).sum()

        with c1:
            st.metric(f"Cuan Tambahan (Pindah ke SBN)", f"Rp {pot_sbn:,.0f}")
        with c2:
            st.metric(f"Cuan Tambahan (Pindah ke {rating_pilihan})", f"Rp {pot_sim:,.0f}", delta=f"Gap {rating_pilihan} vs SBN")

        # --- VISUALISASI ---
        v1, v2 = st.columns([2, 1])
        with v1:
            fig_bar = px.bar(df, x='Nomor_Bilyet', y='Net_Yield', color='Gap_vs_SBN', 
                             title="Yield per Bilyet vs Benchmark", color_continuous_scale='RdYlGn_r')
            fig_bar.add_hline(y=net_simulasi, line_dash="dash", line_color="orange", annotation_text=f"Rating {rating_pilihan}")
            st.plotly_chart(fig_bar, use_container_width=True)
        with v2:
            fig_pie = px.pie(df, values='Nominal', names='Bank', title="Konsentrasi Dana")
            st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("📑 Detail Tabel Inventori")
        st.dataframe(df.style.background_gradient(subset=['Gap_vs_SBN'], cmap='Reds'), use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
