import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from streamlit_lottie import st_lottie
import requests
import time
# --- IMPORT PENTING UNTUK WAKTU ---
from datetime import datetime, timedelta

# --- 1. CONFIG HALAMAN ---
st.set_page_config(page_title="ASDP Treasury Command Center", layout="wide", page_icon="🚢")

# --- LOTTIE ANIMATION HANDLER ---
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
        if lottie_ship: st_lottie(lottie_ship, height=300, key="asdp_no_image_v59")
        st.markdown("<h2 style='text-align: center; color: #004d99;'>Menyiapkan Dashboard Executive ASDP...</h2>", unsafe_allow_html=True)
        bar = st.progress(0)
        for i in range(100):
            time.sleep(0.01)
            bar.progress(i + 1)
        st.session_state.initialized = True
        st.rerun()

# --- 3. DATA ENGINE (SUPER ROBUST) ---
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

@st.cache_data(ttl=60)
def load_data():
    sheet_id = "182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY"
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet="
    try:
        df_f = pd.read_csv(base_url + "Funding")
        df_l = pd.read_csv(base_url + "Lending")
        df_f.columns = [c.strip() for c in df_f.columns]
        df_l.columns = [c.strip() for c in df_l.columns]
        
        # Penyelarasan Istilah Kreditur (Bank)
        if 'Debitur' in df_l.columns: df_l.rename(columns={'Debitur': 'Kreditur'}, inplace=True)
        
        for df in [df_f, df_l]:
            for col in ['Nominal', 'Rate (%)', 'CoF (%)']:
                if col in df.columns: df[col] = clean_numeric_robust(df[col])
            if 'Periode' in df.columns: df['Periode'] = df['Periode'].astype(str).str.strip()
            if 'Jatuh_Tempo' in df.columns:
                df['Jatuh_Tempo'] = pd.to_datetime(df['Jatuh_Tempo'], dayfirst=True, errors='coerce')
        return df_f, df_l, None
    except Exception as e: return pd.DataFrame(), pd.DataFrame(), str(e)

# EXECUTION DATA LOAD
df_f_raw, df_l_raw, error_msg = load_data()

# --- 4. SIDEBAR (LOGO STANDAR) ---
st.sidebar.markdown("<br>", unsafe_allow_html=True)
# Centering logo standar ASDP dari internet
col1, col2, col3 = st.sidebar.columns([1, 4, 1])
with col2:
    st.image("https://www.indonesiaferry.co.id/img/logo.png", width=180)

st.sidebar.markdown("<h3 style='text-align: center;'>Treasury Sidebar</h3>", unsafe_allow_html=True)

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
except: sbn_val = 6.65

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Market Benchmark")
current_sbn = st.sidebar.number_input("Benchmark SBN 10Y (%)", value=sbn_val, step=0.01, format="%.2f")

# Filter Data Berdasarkan Bulan Pilihan
df_f = df_f_raw[df_f_raw['Periode'] == selected_month].copy()
df_l = df_l_raw[df_l_raw['Periode'] == selected_month].copy()

# --- 5. DASHBOARD UI TABS ---
tab1, tab2, tab3 = st.tabs(["💰 Funding Monitor", "💸 Loan Payment (Debt)", "📊 ALM Net Position"])

# ==========================================
# TAB 1: FUNDING MONITOR (EXEC LAYOUT)
# ==========================================
with tab1:
    st.header(f"Intelligence Funding - {selected_month}")
    
    if not df_f.empty:
        # Perhitungan
        df_f['Net_Yield_Rate'] = df_f['Rate (%)'] * 0.8 # Pajak Deposito 20%
        net_sbn_benchmark = current_sbn * 0.9 # Pajak SBN 10%
        df_f['Monthly_Yield_IDR'] = (df_f['Nominal'] * (df_f['Rate (%)'] / 100)) / 12

        # 1. METRICS (BARIS ATAS)
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric("Total Yield Bulan Ini (Gross)", f"Rp {df_f['Monthly_Yield_IDR'].sum():,.0f}")
        m3.metric("Benchmark SBN Net", f"{net_sbn_benchmark:.2f}%")

        # 2. ALERTS (DENGAN SCROLL)
        st.subheader("🔔 Treasury Alerts (Real-Time)")
        col_a1, col_a2 = st.columns(2)
        
        with col_a1:
            st.markdown("**🚨 Underperform vs SBN Net**")
            under = df_f[df_f['Net_Yield_Rate'] < net_sbn_benchmark]
            if not under.empty:
                with st.container(height=180):
                    for _, row in under.iterrows():
                        gap = net_sbn_benchmark - row['Net_Yield_Rate']
                        st.error(f"**{row['Bank']}** | Gap: {gap:.2f}% vs SBN Net")
            else:
                st.success("✅ Semua rate aman di atas SBN Net.")

        with col_a2:
            st.markdown("**⏳ Jatuh Tempo (H-7)**")
            if 'Jatuh_Tempo' in df_f.columns:
                # FIX: datetime dipanggil di sini, import wajib lengkap di atas!
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
                    st.info("📅 Tidak ada jatuh tempo dalam 7 hari ke depan.")
            else:
                st.info("Kolom 'Jatuh_Tempo' tidak ditemukan.")

        st.divider()
        
        # 3. GRAFIK (BERDAMPINGAN)
        st.markdown("### 📊 Rekonsiliasi Penerimaan & Konsentrasi")
        col_c1, col_c2 = st.columns([2, 1])
        
        with col_c1:
            # Grouping data untuk chart total per Bank
            df_bank_yield = df_f.groupby('Bank')['Monthly_Yield_IDR'].sum().reset_index()
            # Tampilkan dalam satuan "B" (Billion/Miliar)
            df_bank_yield['Yield_B'] = df_bank_yield['Monthly_Yield_IDR'] / 1e9
            
            fig_bar = px.bar(df_bank_yield, x='Bank', y='Yield_B', color='Bank',
                             text_auto='.2f', title="Total Penerimaan Bunga per Bank (Rp Billion)",
                             labels={'Yield_B': 'Penerimaan Bunga (Rp B)'})
            fig_bar.update_traces(texttemplate='%{y:.2f} B', textposition='outside')
            fig_bar.update_layout(yaxis_tickformat=',.2f', showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with col_c2:
            st.plotly_chart(px.pie(df_f, values='Nominal', names='Bank', hole=0.4, title="Konsentrasi Dana Bilyet"), use_container_width=True)

        # 4. TABEL (EXPANDABLE)
        with st.expander("Lihat Detail Tabel Data Funding", expanded=True):
            df_display = df_f.copy()
            if 'Jatuh_Tempo' in df_display.columns:
                df_display['Jatuh_Tempo'] = df_display['Jatuh_Tempo'].dt.strftime('%d-%m-%Y')
            st.dataframe(df_display, use_container_width=True)
    else:
        st.info("Data Funding tidak tersedia untuk periode ini.")

# ==========================================
# WS 2: LOAN PAYMENT (PENCEGAHAN GAGAL BAYAR)
# ==========================================
with tab2:
    st.header(f"Monitoring Kewajiban Pembayaran (Debt) - {selected_month}")
    if not df_l.empty:
        # Penyeragaman Tipe
        df_l['Tipe'] = df_l['Tipe'].astype(str).str.strip().str.capitalize()
        
        # --- DEBT ALERTS ---
        st.subheader("⚠️ Debt Service Monitoring")
        col_l1, col_l2 = st.columns(2)
        with col_l1:
            st.markdown("**🚨 Jadwal Pembayaran H-7 (Siapkan Dana!)**")
            with st.container(height=180):
                today = datetime.now()
                due_soon = df_l[(df_l['Jatuh_Tempo'] >= today) & (df_l['Jatuh_Tempo'] <= today + timedelta(days=7))]
                if not due_soon.empty:
                    for _, row in due_soon.iterrows():
                        # Di tab 2 kita pakai istilah Kreditur (Bank)
                        st.error(f"**{row['Kreditur']}** | Rp {row['Nominal']:,.0f} ({row['Tipe']}) | Jatuh Tempo: {row['Jatuh_Tempo'].strftime('%d-%m-%Y')}")
                else:
                    st.success("✅ Tidak ada jadwal bayar kritis dalam 7 hari.")
        
        with col_l2:
            st.markdown("**📉 Eksposur Kreditur Terbesar**")
            with st.container(height=180):
                top_kreditur = df_l.groupby('Kreditur')['Nominal'].sum().idxmax()
                st.warning(f"Kreditur dengan kewajiban tertinggi: **{top_kreditur}**")
                st.write("Pastikan likuiditas di bank terkait mencukupi sebelum jatuh tempo.")

        st.divider()

        # Metrics
        total_debt_outflow = df_l['Nominal'].sum()
        bunga_outflow = df_l[df_l['Tipe'] == 'Bunga']['Nominal'].sum()
        
        l1, l2, l3 = st.columns(3)
        l1.metric("Total Kewajiban Bulan Ini", f"Rp {total_debt_outflow:,.0f}")
        l2.metric("Beban Bunga (B)", f"Rp {bunga_outflow/1e9:.2f} B")
        l3.metric("Pelunasan Pokok (B)", f"Rp {(total_debt_outflow - bunga_outflow)/1e9:.2f} B")

        # Charts Stacked Bar (Kewajiban Pokok vs Bunga)
        st.markdown("### 📊 Rekonsiliasi Kewajiban per Kreditur")
        # Format ke B (Billion/Miliar)
        fig_loan = px.bar(df_l, x='Kreditur', y=df_l['Nominal']/1e9, color='Tipe', barmode='stack',
                         title="Komposisi Pokok & Bunga (Rp Billion)", text_auto='.2f')
        fig_loan.update_traces(texttemplate='%{y:.2f} B')
        fig_loan.update_layout(yaxis_title="Rp Billion")
        st.plotly_chart(fig_loan, use_container_width=True)

        with st.expander("Lihat Detail Tabel Kewajiban"):
            df_l_disp = df_l.copy()
            if 'Jatuh_Tempo' in df_l_disp.columns:
                df_l_disp['Jatuh_Tempo'] = df_l_disp['Jatuh_Tempo'].dt.strftime('%d-%m-%Y')
            st.dataframe(df_l_disp, use_container_width=True)
    else:
        st.info("Data Kewajiban tidak tersedia.")

# ==========================================
# WS 3: ALM NET POSITION
# ==========================================
with tab3:
    st.header("Strategic ALM & Net Position")
    
    # Pendapatan vs Beban Bunga
    y_fund = df_f['Monthly_Yield_IDR'].sum() if not df_f.empty else 0
    y_lend = df_l[df_l['Tipe'] == 'Bunga']['Nominal'].sum() if not df_l.empty else 0
    total_net_interest = y_fund - y_lend
    
    st.subheader("🗓️ Net Interest Position Bulan Ini")
    p1, p2, p3 = st.columns(3)
    p1.metric("Bunga Masuk (Asset/Deposito)", f"Rp {y_fund:,.0f}")
    p2.metric("Bunga Keluar (Liability/Pinjaman)", f"Rp {y_lend:,.0f}")
    p3.metric("Net Interest Income", f"Rp {total_net_interest:,.0f}", delta=f"{total_net_interest:,.0f}", delta_color="normal")

    st.divider()
    st.caption("ASDP Treasury Command Center v5.9 - Lean Edition")
