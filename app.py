import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_lottie import st_lottie
import requests
import time
from datetime import datetime, timedelta

# --- 1. CONFIG HALAMAN ---
st.set_page_config(page_title="ASDP ALM Command Center", layout="wide", page_icon="🚢")

def load_lottieurl(url):
    try:
        r = requests.get(url, timeout=5)
        return r.json() if r.status_code == 200 else None
    except: return None

lottie_ship = load_lottieurl("https://assets5.lottiefiles.com/packages/lf20_7wwmup6o.json")

# --- 2. SPLASH SCREEN ---
if 'initialized' not in st.session_state:
    st.session_state.initialized = False

if not st.session_state.initialized:
    with st.container():
        st.markdown("<br><br>", unsafe_allow_html=True)
        if lottie_ship: st_lottie(lottie_ship, height=300, key="asdp_final_splash")
        st.markdown("<h2 style='text-align: center; color: #004d99;'>Menyiapkan Executive Dashboard ASDP...</h2>", unsafe_allow_html=True)
        bar = st.progress(0)
        for i in range(100):
            time.sleep(0.01)
            bar.progress(i + 1)
        st.session_state.initialized = True
        st.rerun()

# --- 3. DATA ENGINE (ROBUST CLEANER) ---
def clean_numeric_robust(series):
    def process_val(val):
        val = str(val).strip().replace('Rp', '').replace('%', '').replace(' ', '')
        if not val or val == 'nan' or val == 'None': return "0"
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

@st.cache_data(ttl=1)
def load_gsheets_data():
    sheet_id = "182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY"
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet="
    try:
        df_f = pd.read_csv(base_url + "Funding")
        df_l = pd.read_csv(base_url + "Lending")
        df_f.columns = [c.strip() for c in df_f.columns]
        df_l.columns = [c.strip() for c in df_l.columns]
        
        # Penyelarasan Kolom untuk API
        if 'Debitur' in df_l.columns: df_l.rename(columns={'Debitur': 'Kreditur'}, inplace=True)
        if 'Rate (%)' in df_f.columns: df_f.rename(columns={'Rate (%)': 'Rate'}, inplace=True)
        if 'Nominal' in df_l.columns: df_l.rename(columns={'Nominal': 'Nominal_Lending'}, inplace=True)
        
        for df in [df_f, df_l]:
            if 'Nominal' in df.columns: df['Nominal'] = clean_numeric_robust(df['Nominal'])
            if 'Nominal_Lending' in df.columns: df['Nominal_Lending'] = clean_numeric_robust(df['Nominal_Lending'])
            if 'Rate' in df.columns: df['Rate'] = clean_numeric_robust(df['Rate'])
            if 'Lending_Rate (%)' in df.columns: df['Lending_Rate (%)'] = clean_numeric_robust(df['Lending_Rate (%)'])
            if 'Cost_of_Fund (%)' in df.columns: df['Cost_of_Fund (%)'] = clean_numeric_robust(df['Cost_of_Fund (%)'])
            if 'Jatuh_Tempo' in df.columns:
                df['Jatuh_Tempo'] = pd.to_datetime(df['Jatuh_Tempo'], dayfirst=True, errors='coerce')
        return df_f, df_l, None
    except Exception as e: return pd.DataFrame(), pd.DataFrame(), str(e)

# --- 4. SIDEBAR ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/id/thumb/4/41/Logo_ASDP_Indonesia_Ferry.svg/1280px-Logo_ASDP_Indonesia_Ferry.svg.png", use_container_width=True)
st.sidebar.markdown("---")

st.sidebar.header("📡 Sumber Data")
data_source = st.sidebar.radio("Metode Pengambilan Data:", ["Google Sheets API (Live)", "Upload File Manual"])

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Market Intelligence")
current_sbn = st.sidebar.number_input("Benchmark SBN 10Y (%)", value=6.65, step=0.01, format="%.2f")
threshold = st.sidebar.slider("Threshold Pindah Dana (%)", 0.0, 5.0, 0.5)

st.sidebar.markdown("---")
st.sidebar.header("🛡️ Credit Risk Simulation")
rating_pilihan = st.sidebar.selectbox("Pilih Rating Simulasi:", ["AAA", "AA+", "AA", "A"])
risk_notes = {
    "AAA": {"spread": 80, "desc": "🛡️ Stabil & Aman. Kapasitas pembayaran bunga dan pokok sangat kuat."},
    "AA+": {"spread": 100, "desc": "✅ Sangat Kuat. Memiliki kapasitas sangat tinggi untuk memenuhi komitmen finansial."},
    "AA": {"spread": 120, "desc": "✅ Kualitas Tinggi. Kapasitas bayar kuat, risiko sedikit lebih tinggi dari AAA."},
    "A": {"spread": 260, "desc": "🚨 Sensitif. Cukup aman namun rentan terhadap perubahan kondisi ekonomi."}
}
selected_spread = st.sidebar.slider(f"Spread {rating_pilihan} (bps)", 30, 450, risk_notes[rating_pilihan]["spread"])
est_yield_bond = current_sbn + (selected_spread/100)

# --- DATA LOADING LOGIC ---
df_f, df_l = pd.DataFrame(), pd.DataFrame()

if data_source == "Google Sheets API (Live)":
    df_f, df_l, error_msg = load_gsheets_data()
    if error_msg: st.sidebar.error(f"API Error: {error_msg}")
else:
    f_up = st.sidebar.file_uploader("Upload Funding (Excel)", type=["xlsx"])
    l_up = st.sidebar.file_uploader("Upload Lending (Excel)", type=["xlsx"])
    if f_up: 
        df_f = pd.read_excel(f_up)
        if 'Rate' in df_f.columns: df_f['Rate'] = clean_numeric_robust(df_f['Rate'])
        if 'Nominal' in df_f.columns: df_f['Nominal'] = clean_numeric_robust(df_f['Nominal'])
    if l_up: 
        df_l = pd.read_excel(l_up)
        for c in ['Nominal_Lending', 'Lending_Rate (%)', 'Cost_of_Fund (%)']:
            if c in df_l.columns: df_l[c] = clean_numeric_robust(df_l[c])

# --- 5. DASHBOARD UI ---
st.title("🚢 ASDP Integrated Treasury & ALM")
tab1, tab2, tab3 = st.tabs(["💰 Funding Monitoring (WS 1)", "📈 Lending Monitoring (WS 2)", "📊 ALM Resume (WS 3)"])

# ==========================================
# TAB 1: FUNDING MONITORING (SESUAI GAMBAR)
# ==========================================
with tab1:
    if not df_f.empty:
        # Perhitungan Dasar
        df_f['Net_Yield'] = df_f['Rate'] * 0.8
        net_sbn = current_sbn * 0.9
        net_sim = est_yield_bond * 0.9
        df_f['Gap_vs_SBN'] = df_f['Net_Yield'] - net_sbn
        
        # 1. METRICS ATAS
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Portfolio", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric("SBN Net (Risk-Free)", f"{net_sbn:.2f}%")
        m3.metric(f"Simulasi Net {rating_pilihan}", f"{net_sim:.2f}%")

        # 2. RISK ASSESSMENT BOX
        st.subheader(f"⚠️ Risk Assessment: Penempatan di Rating {rating_pilihan}")
        with st.container():
            if rating_pilihan == "A":
                st.error(f"**WARNING RISIKO RATING A:** Investasi Layak, tapi Sensitif terhadap perubahan ekonomi.")
                st.markdown("""
                * **Credit Migration Risk:** Rentan terhadap *downgrade* ke rating BBB jika makroekonomi memburuk.
                * **Liquidity Risk:** Likuiditas pasar sekunder lebih rendah dibanding rating AA/AAA.
                * **Spread Volatility:** Volatilitas harga lebih tinggi saat terjadi guncangan pasar.
                """)
            else:
                st.warning(f"**PROFIL RISIKO {rating_pilihan}:** {risk_notes[rating_pilihan]['desc']}")

        st.divider()

        # 3. CUAN TAMBAHAN
        c1, c2 = st.columns(2)
        # Dana yang yield-nya di bawah (SBN - threshold)
        df_pindah = df_f[df_f['Net_Yield'] < (net_sbn - threshold)]
        pot_sbn = (df_pindah['Nominal'] * (net_sbn - df_pindah['Net_Yield'])/100).sum()
        pot_sim = (df_pindah['Nominal'] * (net_sim - df_pindah['Net_Yield'])/100).sum()
        
        c1.metric("Cuan Tambahan (Pindah ke SBN)", f"Rp {pot_sbn:,.0f}", delta=f"Jika pindah {len(df_pindah)} bilyet")
        c2.metric(f"Cuan Tambahan (Pindah ke {rating_pilihan})", f"Rp {pot_sim:,.0f}", delta="Optimalisasi Yield", delta_color="normal")

        # 4. VISUALISASI
        st.markdown("---")
        v1, v2 = st.columns([2, 1])
        with v1:
            bil_col = 'Nomor_Bilyet' if 'Nomor_Bilyet' in df_f.columns else df_f.index
            fig_f = px.bar(df_f, x=bil_col, y='Net_Yield', color='Gap_vs_SBN', 
                           color_continuous_scale='RdYlGn', title="Yield per Bilyet vs SBN Net")
            fig_f.add_hline(y=net_sbn, line_dash="dash", line_color="blue", annotation_text="Benchmark SBN Net")
            st.plotly_chart(fig_f, use_container_width=True)
        with v2:
            bank_col = 'Bank' if 'Bank' in df_f.columns else df_f.columns[0]
            fig_pie = px.pie(df_f, values='Nominal', names=bank_col, hole=0.4, title="Konsentrasi Dana")
            st.plotly_chart(fig_pie, use_container_width=True)

        # 5. TABEL DETAIL
        with st.expander("📑 Detail Tabel Inventori Funding", expanded=True):
            df_disp = df_f.copy()
            if 'Jatuh_Tempo' in df_disp.columns:
                df_disp['Jatuh_Tempo'] = df_disp['Jatuh_Tempo'].apply(lambda x: x.strftime('%d-%m-%Y') if pd.notnull(x) else '-')
            st.dataframe(df_disp.style.background_gradient(subset=['Gap_vs_SBN'], cmap='RdYlGn'), use_container_width=True)
    else:
        st.info("Pilih sumber data (API/Upload) untuk memuat Tab Funding.")

# ==========================================
# TAB 2: LENDING MONITORING
# ==========================================
with tab2:
    if not df_l.empty:
        df_l['Spread'] = df_l['Lending_Rate (%)'] - df_l['Cost_of_Fund (%)']
        l1, l2, l3 = st.columns(3)
        l1.metric("Total Penyaluran", f"Rp {df_l['Nominal_Lending'].sum():,.0f}")
        l2.metric("Avg. Lending Rate", f"{df_l['Lending_Rate (%)'].mean():.2f}%")
        l3.metric("Avg. Margin (Spread)", f"{df_l['Spread'].mean():.2f}%")
        
        deb_col = 'Kreditur' if 'Kreditur' in df_l.columns else df_l.columns[0]
        fig_l = go.Figure()
        fig_l.add_trace(go.Bar(x=df_l[deb_col], y=df_l['Lending_Rate (%)'], name='Lending Rate', marker_color='#2ecc71'))
        fig_l.add_trace(go.Bar(x=df_l[deb_col], y=df_l['Cost_of_Fund (%)'], name='Cost of Fund', marker_color='#e74c3c'))
        fig_l.update_layout(barmode='group', title="Lending Rate vs Cost of Fund per Kreditur")
        st.plotly_chart(fig_l, use_container_width=True)
        st.dataframe(df_l, use_container_width=True)

# ==========================================
# TAB 3: ALM RESUME
# ==========================================
with tab3:
    if not df_f.empty and not df_l.empty:
        st.subheader("📋 Resume ALM: Kemampuan Bayar Pokok & Bunga")
        inf_b = (df_l['Nominal_Lending'] * (df_l['Lending_Rate (%)']/100) / 12).sum()
        inf_p = (df_l['Nominal_Lending'] / 12).sum()
        total_in = inf_b + inf_p
        
        out_b = (df_l['Nominal_Lending'] * (df_l['Cost_of_Fund (%)']/100) / 12).sum()
        out_p = (df_l['Nominal_Lending'] / 12).sum() 
        total_out = out_b + out_p
        
        r1, r2, r3 = st.columns(3)
        r1.metric("Inflow Bulanan (Anak Usaha)", f"Rp {total_in:,.0f}")
        r2.metric("Outflow Bulanan (Bank)", f"Rp {total_out:,.0f}")
        cov = total_in / total_out if total_out > 0 else 0
        r3.metric("Cashflow Coverage Ratio", f"{cov:.2f}x", delta=f"Rp {total_in-total_out:,.0f} Surplus")
