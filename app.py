import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from streamlit_lottie import st_lottie
import requests
import time
from datetime import datetime, timedelta

# --- CONFIG ---
st.set_page_config(page_title="ASDP Treasury Command Center", layout="wide", page_icon="🚢")

def load_lottieurl(url):
    try:
        r = requests.get(url, timeout=10)
        return r.json() if r.status_code == 200 else None
    except: return None

lottie_ship = load_lottieurl("https://assets5.lottiefiles.com/packages/lf20_7wwmup6o.json")

# --- SPLASH SCREEN ---
if 'initialized' not in st.session_state:
    st.session_state.initialized = False

if not st.session_state.initialized:
    with st.container():
        st.markdown("<br><br>", unsafe_allow_html=True)
        if lottie_ship: st_lottie(lottie_ship, height=300, key="asdp_final")
        st.markdown("<h2 style='text-align: center; color: #004d99;'>Menyiapkan Laporan Treasury ASDP...</h2>", unsafe_allow_html=True)
        bar = st.progress(0)
        for i in range(100):
            time.sleep(0.01)
            bar.progress(i + 1)
        st.session_state.initialized = True
        st.rerun()

# --- DATA ENGINE (ULTIMATE CLEANER) ---
def clean_numeric_robust(series):
    def process_val(val):
        val = str(val).strip().replace('Rp', '').replace('%', '').replace(' ', '')
        if not val or val == 'nan': return "0"
        commas, dots = val.count(','), val.count('.')
        if commas > 0 and dots > 0:
            if val.rfind(',') > val.rfind('.'): return val.replace('.', '').replace(',', '.')
            else: return val.replace(',', '')
        if commas > 0:
            if commas > 1 or len(val.split(',')[-1]) == 3: return val.replace(',', '')
            else: return val.replace(',', '.')
        if dots > 0:
            if dots > 1 or len(val.split('.')[-1]) == 3: return val.replace('.', '')
        return val
    return pd.to_numeric(series.apply(process_val), errors='coerce').fillna(0)

@st.cache_data(ttl=60)
def load_data_robust():
    sheet_id = "182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY"
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet="
    try:
        df_f = pd.read_csv(base_url + "Funding")
        df_l = pd.read_csv(base_url + "Lending")
        df_f.columns = [c.strip() for c in df_f.columns]
        df_l.columns = [c.strip() for c in df_l.columns]
        for df in [df_f, df_l]:
            if 'Nominal' in df.columns: df['Nominal'] = clean_numeric_robust(df['Nominal'])
            if 'Rate (%)' in df.columns: df['Rate (%)'] = clean_numeric_robust(df['Rate (%)'])
            if 'CoF (%)' in df.columns: df['CoF (%)'] = clean_numeric_robust(df['CoF (%)'])
            if 'Periode' in df.columns: df['Periode'] = df['Periode'].astype(str).str.strip()
            # Handle Tanggal Jatuh Tempo
            if 'Jatuh_Tempo' in df.columns:
                df['Jatuh_Tempo'] = pd.to_datetime(df['Jatuh_Tempo'], dayfirst=True, errors='coerce')
        return df_f, df_l, None
    except Exception as e: return pd.DataFrame(), pd.DataFrame(), str(e)

df_f_raw, df_l_raw, error_msg = load_data_robust()

# --- SIDEBAR ---
st.sidebar.image("https://www.indonesiaferry.co.id/img/logo.png", width=150)
all_periods = sorted(list(set(df_f_raw['Periode'].unique()) | set(df_l_raw['Periode'].unique())), reverse=True)
selected_month = st.sidebar.selectbox("Pilih Periode Analisis:", all_periods)

try:
    hist = yf.Ticker("ID10Y=F").history(period="1d")
    sbn_val = round(float(hist['Close'].iloc[-1]), 2) if not hist.empty else 6.65
except: sbn_val = 6.65

st.sidebar.markdown("---")
current_sbn = st.sidebar.number_input("Benchmark SBN 10Y (%)", value=sbn_val, step=0.01)

df_f = df_f_raw[df_f_raw['Periode'] == selected_month].copy()
df_l = df_l_raw[df_l_raw['Periode'] == selected_month].copy()

# --- DASHBOARD UI ---
st.title(f"🚢 ASDP Treasury Dashboard")
tab1, tab2, tab3 = st.tabs(["💰 Funding Monitor", "📈 Lending Schedule", "📊 ALM & Market Intel"])

# ==========================================
# WS 1: FUNDING
# ==========================================
with tab1:
    st.header(f"Intelligence Funding - {selected_month}")
    
    if not df_f.empty:
        df_f['Net_Yield_Rate'] = df_f['Rate (%)'] * 0.8
        net_sbn = current_sbn * 0.9
        df_f['Monthly_Yield'] = (df_f['Nominal'] * (df_f['Rate (%)'] / 100)) / 12

        # --- NOTIFIKASI PINTAR ---
        st.subheader("🔔 Treasury Alerts")
        col_a1, col_a2 = st.columns(2)
        
        with col_a1:
            under = df_f[df_f['Net_Yield_Rate'] < net_sbn]
            if not under.empty:
                st.error(f"⚠️ **{len(under)} Bilyet Underperform** vs SBN Net ({net_sbn:.2f}%)")
            else:
                st.success("✅ Semua rate penempatan di atas SBN Net.")

        with col_a2:
            if 'Jatuh_Tempo' in df_f.columns:
                today = datetime.now()
                # Jatuh tempo dalam 30 hari
                soon = df_f[df_f['Jatuh_Tempo'] <= (today + timedelta(days=30))]
                if not soon.empty:
                    # FORMAT TANGGAL DD-MM-YYYY DI NOTIFIKASI
                    st.warning(f"⏰ **{len(soon)} Bilyet Jatuh Tempo** (Kurang dari 30 hari)")
                    for _, row in soon.iterrows():
                        dt_str = row['Jatuh_Tempo'].strftime('%d-%m-%Y')
                        st.write(f"- **{row['Bank']}**: Jatuh tempo pada {dt_str}")
                else:
                    st.info("📅 Tidak ada jatuh tempo dalam 30 hari ke depan.")

        st.divider()
        
        # --- METRICS & CHARTS ---
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric("Potensi Yield Bulanan", f"Rp {df_f['Monthly_Yield'].sum():,.0f}")
        m3.metric("SBN 10Y Net", f"{net_sbn:.2f}%")

        # Tabel dengan format tanggal yang benar
        st.markdown("### Detail Data Funding")
        df_display = df_f.copy()
        if 'Jatuh_Tempo' in df_display.columns:
            df_display['Jatuh_Tempo'] = df_display['Jatuh_Tempo'].dt.strftime('%d-%m-%Y')
        
        st.dataframe(df_display, use_container_width=True)
        
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.bar(df_f, x='Bank', y='Monthly_Yield', title="Penerimaan Bunga per Bank"), use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(df_f, values='Nominal', names='Bank', hole=0.4, title="Konsentrasi Dana"), use_container_width=True)
    else:
        st.info("Pilih periode yang memiliki data di Google Sheets.")

# ==========================================
# WS 3: ALM & MARKET INTELLIGENCE
# ==========================================
with tab3:
    st.header("Strategic Risk Assessment")
    
    # Kalkulasi Inflow Bunga Gabungan
    y_fund = df_f['Monthly_Yield'].sum() if not df_f.empty else 0
    y_lend = df_l[df_l['Tipe'].astype(str).str.capitalize() == 'Bunga']['Nominal'].sum() if not df_l.empty else 0
    
    st.subheader("🗓️ Proyeksi Penerimaan Kas (Pendapatan Bunga)")
    p1, p2, p3 = st.columns(3)
    p1.metric("Bunga Deposito", f"Rp {y_fund:,.0f}")
    p2.metric("Bunga Pinjaman", f"Rp {y_lend:,.0f}")
    p3.metric("Total Pendapatan", f"Rp {y_fund + y_lend:,.0f}")

    st.divider()
    
    # SIMULASI RISK RATING (DROPDOWN)
    st.subheader("🛡️ Risk Simulation Tool")
    risk_choice = st.selectbox("Pilih Target Rating Re-Investasi:", ["AAA", "AA", "A", "BBB", "BB"])
    
    spread_map = {"AAA": 0.8, "AA": 1.3, "A": 2.5, "BBB": 4.0, "BB": 6.5}
    target_yield = current_sbn + spread_map[risk_choice]
    
    st.success(f"""
    **Hasil Simulasi Rating {risk_choice}:**
    - **Estimasi Yield (Gross):** {target_yield:.2f}%
    - **Estimasi Yield (Net 10%):** {target_yield * 0.9:.2f}%
    - **Potensi Tambahan Yield:** {((target_yield * 0.9) - (df_f['Net_Yield_Rate'].mean() if not df_f.empty else 0)):.2f}% vs rata-rata deposito.
    """)
    
    st.write("🔗 **Market Intelligence:**")
    m1, m2, m3 = st.columns(3)
    m1.link_button("📈 Bareksa Bond Fund", "https://www.bareksa.com/id/data/mutualfund/5052/sucorinvest-phei-aaa-corporate-bond-fund")
    m2.link_button("📊 CEIC Yield Tenor", "https://www.ceicdata.com/en/indonesia/pt-penilai-harga-efek-indonesia-corporate-bond-yield-by-tenor")
    m3.link_button("🔍 PHEI Fair Value", "https://www.phei.co.id/Data-Pasar/Ringkasan-Pasar")
