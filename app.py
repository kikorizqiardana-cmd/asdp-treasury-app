import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from streamlit_lottie import st_lottie
import requests
import time
from datetime import datetime, timedelta
import base64
import os

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="ASDP Treasury Command Center", layout="wide", page_icon="🚢")

# --- FUNGSI AMBIL GAMBAR LOKAL UNTUK SIDEBAR ---
def get_base64_image(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return None

# Path ke gambar ferry di repo
logo_path = os.path.join(os.path.dirname(__file__), 'ferry.png')
encoded_logo = get_base64_image(logo_path)

# --- FUNGSI ANIMASI LOTTIE SPLASH ---
def load_lottieurl(url):
    try:
        r = requests.get(url, timeout=10)
        return r.json() if r.status_code == 200 else None
    except: return None

lottie_ship = load_lottieurl("https://assets5.lottiefiles.com/packages/lf20_7wwmup6o.json")

# --- 2. SPLASH SCREEN (SESSION STATE) ---
if 'initialized' not in st.session_state:
    st.session_state.initialized = False

if not st.session_state.initialized:
    with st.container():
        st.markdown("<br><br>", unsafe_allow_html=True)
        if lottie_ship: st_lottie(lottie_ship, height=300, key="asdp_vision_edition")
        st.markdown("<h2 style='text-align: center; color: #004d99;'>Menyiapkan ASDP Treasury Intelligence...</h2>", unsafe_allow_html=True)
        bar = st.progress(0)
        for i in range(100):
            time.sleep(0.01)
            bar.progress(i + 1)
        st.session_state.initialized = True
        st.rerun()

# --- 3. DATA ENGINE (SUPER ROBUST - INDO STANDARD) ---
def clean_numeric_robust(series):
    def process_val(val):
        val = str(val).strip().replace('Rp', '').replace('%', '').replace(' ', '')
        if not val or val == 'nan' or val == 'None': return "0"
        commas, dots = val.count(','), val.count('.')
        # Logika Koma/Titik Desimal vs Ribuan
        if commas > 0 and dots > 0:
            if val.rfind(',') > val.rfind('.'): return val.replace('.', '').replace(',', '.') # Format Indo
            else: return val.replace(',', '') # Format US
        if commas > 0:
            if commas > 1 or len(val.split(',')[-1]) == 3: return val.replace(',', '') # Ribuan
            else: return val.replace(',', '.') # Desimal
        if dots > 0:
            if dots > 1 or len(val.split('.')[-1]) == 3: return val.replace('.', '')
        return val
    return pd.to_numeric(series.apply(process_val), errors='coerce').fillna(0)

@st.cache_data(ttl=60) # Cache data selama 60 detik
def load_data_from_gsheets():
    sheet_id = "182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY"
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet="
    try:
        # Load Tabs
        df_f = pd.read_csv(base_url + "Funding")
        df_l = pd.read_csv(base_url + "Lending")
        
        # Bersihkan Nama Kolom
        df_f.columns = [c.strip() for c in df_f.columns]
        df_l.columns = [c.strip() for c in df_l.columns]
        
        # Bersihkan Data Angka & Periode
        for df in [df_f, df_l]:
            if 'Nominal' in df.columns: df['Nominal'] = clean_numeric_robust(df['Nominal'])
            if 'Rate (%)' in df.columns: df['Rate (%)'] = clean_numeric_robust(df['Rate (%)'])
            if 'CoF (%)' in df.columns: df['CoF (%)'] = clean_numeric_robust(df['CoF (%)'])
            if 'Periode' in df.columns: df['Periode'] = df['Periode'].astype(str).str.strip()
            
            # Handle Tanggal Jatuh Tempo (Format DD-MM-YYYY dari GSheets)
            if 'Jatuh_Tempo' in df.columns:
                df['Jatuh_Tempo'] = pd.to_datetime(df['Jatuh_Tempo'], dayfirst=True, errors='coerce')
        
        return df_f, df_l, None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), str(e)

# EXECUTION DATA LOAD
df_f_raw, df_l_raw, error_msg = load_data_from_gsheets()

# --- 4. SIDEBAR CONTRTOLS ---
st.sidebar.markdown("<br>", unsafe_allow_html=True)

# TAMBAHKAN GAMBAR FERRY/LOGO ASDP (Jika file ferry.png ada)
if encoded_logo:
    st.sidebar.markdown(f'<div style="text-align: center;"><img src="data:image/png;base64,{encoded_logo}" width="200"></div>', unsafe_allow_html=True)
else:
    # Backup jika gambar tidak ditemukan
    st.sidebar.image("https://www.indonesiaferry.co.id/img/logo.png", width=180)
    st.sidebar.warning("⚠️ Simpan file ferry.png di repo untuk logo kapal.")

st.sidebar.markdown("<h2 style='text-align: center; color: #004d99;'>Treasury Sidebar</h2>", unsafe_allow_html=True)

if error_msg:
    st.sidebar.error(f"Gagal memuat data: {error_msg}")
    st.stop()

# Dropdown Periode
all_periods = sorted(list(set(df_f_raw['Periode'].unique()) | set(df_l_raw['Periode'].unique())), reverse=True)
selected_month = st.sidebar.selectbox("Pilih Periode Analisis:", all_periods, index=0)

# Ambil Live SBN (Risk Free)
try:
    ticker = yf.Ticker("ID10Y=F")
    hist = ticker.history(period="1d")
    sbn_val = round(float(hist['Close'].iloc[-1]), 2) if not hist.empty else 6.65
except: sbn_val = 6.65 # Backup rate

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Market Benchmark")
# Input SBN (Bisa dioverride Group Head)
current_sbn = st.sidebar.number_input("Benchmark SBN 10Y (%)", value=sbn_val, step=0.01, format="%.2f")
st.sidebar.caption(f"SBN Net (Pajak 10%): **{current_sbn * 0.9:.2f}%**")

# Filter Data Berdasarkan Bulan Pilihan
df_f = df_f_raw[df_f_raw['Periode'] == selected_month].copy()
df_l = df_l_raw[df_l_raw['Periode'] == selected_month].copy()

# --- 5. DASHBOARD UI TABS ---
tab1, tab2, tab3 = st.tabs(["💰 Funding Monitor", "📈 Lending Schedule", "📊 ALM & Market Intel"])

# ==========================================
# TAB 1: FUNDING MONITOR
# ==========================================
with tab1:
    st.header(f"Intelligence Funding - {selected_month}")
    
    if not df_f.empty:
        # Kalkulasi Yield & Bunga Bulanan
        df_f['Net_Yield_Rate'] = df_f['Rate (%)'] * 0.8 # Pajak Deposito 20%
        net_sbn_benchmark = current_sbn * 0.9 # Pajak SBN 10%
        # Rumus Bunga Bulanan: (Nominal * Rate/100) / 12
        df_f['Monthly_Yield_IDR'] = (df_f['Nominal'] * (df_f['Rate (%)'] / 100)) / 12

        # --- SMART NOTIFICATIONS (ALERTS) ---
        st.subheader("🔔 Treasury Alerts (Real-Time)")
        col_a1, col_a2 = st.columns(2)
        
        with col_a1:
            st.markdown("**🚨 Underperform vs SBN Net**")
            under = df_f[df_f['Net_Yield_Rate'] < net_sbn_benchmark]
            if not under.empty:
                # Scrollable container
                with st.container(height=180):
                    for _, row in under.iterrows():
                        gap = net_sbn_benchmark - row['Net_Yield_Rate']
                        st.error(f"**{row['Bank']}** ({row['Nomor_Bilyet']}) | Gap: {gap:.2f}% vs SBN Net")
            else:
                st.success("✅ Semua rate penempatan Deposito di atas SBN Net.")

        with col_a2:
            st.markdown("**⏳ Jatuh Tempo (H-7)**")
            if 'Jatuh_Tempo' in df_f.columns:
                today = datetime.now()
                seven_days_later = today + timedelta(days=7)
                soon = df_f[(df_f['Jatuh_Tempo'] >= today) & (df_f['Jatuh_Tempo'] <= seven_days_later)]
                
                if not soon.empty:
                    with st.container(height=180):
                        for _, row in soon.iterrows():
                            # FORMAT TANGGAL DD-MM-YYYY
                            dt_str = row['Jatuh_Tempo'].strftime('%d-%m-%Y')
                            st.warning(f"**{row['Bank']}** | Jatuh Tempo: {dt_str}")
                else:
                    st.info("📅 Tidak ada bilyet yang jatuh tempo dalam 7 hari ke depan.")
            else:
                st.info("Kolom 'Jatuh_Tempo' tidak ditemukan di GSheets.")

        st.divider()
        
        # --- KEY METRICS ---
        total_monthly_yield = df_f['Monthly_Yield_IDR'].sum()
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric("Total Yield Bulan Ini (Gross)", f"Rp {total_monthly_yield:,.0f}")
        m3.metric("Benchmark SBN Net", f"{net_sbn_benchmark:.2f}%")

        # --- GRAFIK & VISUALISASI ---
        st.markdown("### 📊 Rekonsiliasi Penerimaan Bunga per Bank")
        
        col_c1, col_c2 = st.columns([2, 1])
        
        with col_c1:
            # Grouping data untuk chart total per Bank
            df_bank_yield = df_f.groupby('Bank')['Monthly_Yield_IDR'].sum().reset_index()
            # GANTI "G" MENJADI "B" (Billion/Miliar)
            # Kita bagi nilai y dengan 1,000,000,000 dan ubah label sumbu Y
            df_bank_yield['Yield_B'] = df_bank_yield['Monthly_Yield_IDR'] / 1e9
            
            fig_bar = px.bar(df_bank_yield, 
                             x='Bank', 
                             y='Yield_B', 
                             color='Bank',
                             # Tampilkan 2 desimal di atas batang
                             text_auto='.2f', 
                             title=f"Total Penerimaan Bunga Bulan Ini: Rp {total_monthly_yield:,.0f}",
                             labels={'Yield_B': 'Penerimaan Bunga (Rp B)'})
            
            # Tambahkan akhiran "B" (Billion) pada teks di atas batang
            fig_bar.update_traces(texttemplate='%{y:.2f} B', textposition='outside')
            
            # Format sumbu Y agar menampilkan angka utuh tanpa "G", tapi dengan pemisah ribuan
            # Kita matikan legend karena warnanya sudah ada di sumbu X
            fig_bar.update_layout(yaxis_tickformat=',.2f', showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with col_c2:
            st.plotly_chart(px.pie(df_f, values='Nominal', names='Bank', hole=0.4, title="Komposisi Dana Bilyet"), use_container_width=True)

        with st.expander("Lihat Detail Tabel Data Funding"):
            # Format Tanggal untuk Tampilan Tabel (DD-MM-YYYY)
            df_display = df_f.copy()
            if 'Jatuh_Tempo' in df_display.columns:
                df_display['Jatuh_Tempo'] = df_display['Jatuh_Tempo'].dt.strftime('%d-%m-%Y')
            st.dataframe(df_display, use_container_width=True)
    else:
        st.info("Data Funding tidak tersedia untuk periode ini.")

# ==========================================
# TAB 2: LENDING SCHEDULE (TETAP SAMA)
# ==========================================
with tab2:
    st.header("Jadwal Angsuran & Spread")
    if not df_l.empty:
        # Bersihkan Tipe
        df_l['Tipe'] = df_l['Tipe'].astype(str).str.strip().str.capitalize()
        inf_b = df_l[df_l['Tipe'] == 'Bunga']['Nominal'].sum()
        inf_p = df_l[df_l['Tipe'] == 'Pokok']['Nominal'].sum()
        
        l1, l2, l3 = st.columns(3)
        l1.metric("Total Inflow (Lending)", f"Rp {(inf_b+inf_p):,.0f}")
        l2.metric("Penerimaan Bunga", f"Rp {inf_b:,.0f}")
        l3.metric("Penerimaan Pokok", f"Rp {inf_p:,.0f}")
        
        st.dataframe(df_l, use_container_width=True)
    else:
        st.info("Pilih periode yang memiliki data Lending.")

# ==========================================
# TAB 3: ALM & MARKET INTELLIGENCE (INTELLIGENT DROP DOWN)
# ==========================================
with tab3:
    st.header("Strategic ALM & Risk Analytics")
    
    # 1. Baris Proyeksi Inflow (Revisi dari Penerimaan Real)
    y_fund = df_f['Monthly_Yield_IDR'].sum() if not df_f.empty else 0
    y_lend = df_l[df_l['Tipe'].astype(str).str.capitalize() == 'Bunga']['Nominal'].sum() if not df_l.empty else 0
    total_monthly_interest = y_fund + y_lend
    
    st.subheader("🗓️ Proyeksi Inflow Kas Bulan Ini (Gaji Kas)")
    p1, p2, p3 = st.columns(3)
    p1.metric("Bunga Deposito (Kas/Penerimaan Real)", f"Rp {y_fund:,.0f}")
    p2.metric("Bunga Pinjaman (Inflow)", f"Rp {y_lend:,.0f}")
    p3.metric("Total Pendapatan Bunga (Inflow)", f"Rp {total_monthly_interest:,.0f}")

    st.divider()
    
    # --- 🛡️ RISK-YIELD SIMULATION (DROP DOWN INTELLIGENCE) ---
    st.subheader("🎯 Simulator Strategi Re-Investasi Dana Funding")
    st.write("Gunakan simulator ini untuk memproyeksikan tambahan pendapatan net jika seluruh dana Funding dialihkan.")
    
    # Data Spread (Estimasi Market over SBN untuk obligasi tenor senada)
    spread_map = {
        "SBN (Government)": 0.0,
        "Corporate AAA (Bonds/Sukuk)": 0.8,
        "Corporate AA (Bonds/Sukuk)": 1.3,
        "Corporate A (Bonds/Sukuk)": 2.5,
        "Corporate BBB (Bonds/Sukuk)": 4.0,
        "Corporate BB (High Risk)": 6.5
    }
    
    # Dropdown Pilihan Rating
    rating_choice = st.selectbox("Simulasi Pemindahan Dana ke Rating/Instrumen Lain:", list(spread_map.keys()))
    
    # Kalkulasi Simulasi
    if not df_f.empty:
        total_nominal_funding = df_f['Nominal'].sum()
        current_monthly_net_yield = (df_f['Nominal'] * (df_f['Net_Yield_Rate']/100) / 12).sum()
        current_avg_net_rate = df_f['Net_Yield_Rate'].mean()
        
        spread_chosen = spread_map[rating_choice]
        sim_gross_rate = current_sbn + spread_chosen
        # Pajak SBN/Obligasi/Sukuk 10% vs Deposito 20%
        sim_net_rate = sim_gross_rate * 0.9 
        
        sim_monthly_net_yield = (total_nominal_funding * (sim_net_rate / 100)) / 12
        delta_net_yield = sim_monthly_net_yield - current_monthly_net_yield
        
        # Tampilkan Box Hasil Simulasi
        st.success(f"""
        ### Hasil Simulasi Strategi (Penempatan di {rating_choice}):
        - **Estimasi Yield (Gross):** {sim_gross_rate:.2f}%
        - **Estimasi Yield (Net 10%):** {sim_net_rate:.2f}%
        - **Perbandingan Net Rate:** {sim_net_rate:.2f}% (Simulasi) vs {current_avg_net_rate:.2f}% (Eksisting Avg.)
        - **Potensi Tambahan Yield (Net/Bulan):** **Rp {delta_net_yield:,.0f}**
        """)
        
        # Visualisasi Metrik Perbandingan
        r1, r2, r3 = st.columns(3)
        r1.metric("Kondisi Net Saat Ini (Rata-rata)", f"{current_avg_net_rate:.2f}%")
        r2.metric(f"Simulasi Net {rating_choice}", f"{sim_net_rate:.2f}%")
        # delta_color="normal" agar kenaikan hijau, penurunan merah
        r3.metric("Kenaikan Net (Rp/Bulan)", f"Rp {delta_net_yield:,.0f}", delta=f"{delta_net_yield:,.0f} IDR", delta_color="normal")
    else:
        st.info("Pilih periode yang memiliki data Funding untuk simulasi.")
        
    st.divider()
    st.write("🔗 **Real-time Market Peek (Verifikasi Spread):**")
    m1, m2, m3 = st.columns(3)
    m1.link_button("📈 Bareksa Bond Fund", "https://www.bareksa.com/id/data/mutualfund/5052/sucorinvest-phei-aaa-corporate-bond-fund")
    m2.link_button("📊 CEIC Yield Tenor", "https://www.ceicdata.com/en/indonesia/pt-penilai-harga-efek-indonesia-corporate-bond-yield-by-tenor")
    m3.link_button("🔍 PHEI Fair Value", "https://www.phei.co.id/Data-Pasar/Ringkasan-Pasar")
