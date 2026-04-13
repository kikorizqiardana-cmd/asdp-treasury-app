import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime

# --- 1. CONFIG HALAMAN ---
st.set_page_config(page_title="ASDP Treasury Watcher", layout="wide", page_icon="🚢")

# Handle Logo Lokal
logo_path = "ferry.png"
with st.sidebar:
    if os.path.exists(logo_path):
        st.image(logo_path, use_container_width=True)
    else:
        st.markdown("### 🚢 PT ASDP Indonesia Ferry")
    st.markdown("---")

# --- 2. DATA ENGINE ---
def clean_numeric(series):
    return pd.to_numeric(
        series.astype(str).str.replace(r'[Rp% ,]', '', regex=True), 
        errors='coerce'
    ).fillna(0)

@st.cache_data(ttl=60)
def load_gsheets():
    sheet_id = "182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY"
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet="
    try:
        df_f = pd.read_csv(base_url + "Funding")
        df_l = pd.read_csv(base_url + "Lending")
        df_f.columns = [c.strip() for c in df_f.columns]
        df_l.columns = [c.strip() for c in df_l.columns]
        
        if 'Rate (%)' in df_f.columns: df_f.rename(columns={'Rate (%)': 'Rate'}, inplace=True)
        if 'Debitur' in df_l.columns: df_l.rename(columns={'Debitur': 'Kreditur'}, inplace=True)
        
        # Konversi Tanggal Sejak Awal
        if 'Jatuh_Tempo' in df_f.columns:
            df_f['Jatuh_Tempo'] = pd.to_datetime(df_f['Jatuh_Tempo'], dayfirst=True, errors='coerce')
            
        return df_f, df_l, None
    except Exception as e: return pd.DataFrame(), pd.DataFrame(), str(e)

def get_live_sbn():
    try:
        data = yf.Ticker("ID10Y=F").history(period="1d")
        if not data.empty: return round(float(data['Close'].iloc[-1]), 2), "Yahoo Finance (Live)"
    except: pass
    return 6.65, "Default (Manual)"

# --- 3. PENGAMBILAN DATA ---
df_f_raw, df_l_raw, err = load_gsheets()
if err:
    st.sidebar.error(f"GSheets Error: {err}")
    st.stop()

# --- SIDEBAR: MARKET & SPREAD SLIDER ---
sbn_val, sbn_source = get_live_sbn()
st.sidebar.header("⚙️ Market Intelligence")
current_sbn = st.sidebar.number_input(f"Benchmark SBN 10Y ({sbn_source})", value=sbn_val, step=0.01)

# FITUR BARU: SPREAD ALERT SLIDER
st.sidebar.markdown("---")
st.sidebar.header("🚨 Spread Alert Settings")
st.sidebar.info("Tentukan jarak spread (Yield vs SBN) yang dianggap kritis.")
spread_threshold = st.sidebar.slider("Threshold Alert Spread (%)", 1.0, 5.0, 1.0, step=0.1)

all_periods = sorted(list(set(df_f_raw['Periode'].unique())), reverse=True)
selected_month = st.sidebar.selectbox("Pilih Periode Analisis:", all_periods)

# Filter Data
df_f = df_f_raw[df_f_raw['Periode'] == selected_month].copy()
df_l = df_l_raw[df_l_raw['Periode'] == selected_month].copy()

# --- 4. DASHBOARD UI ---
st.title(f"🚢 ASDP Treasury Watcher - {selected_month}")
tab1, tab2, tab3 = st.tabs(["💰 Funding & Spread Alert", "📊 Revenue per Bank", "📈 ALM Monitor"])

# ==========================================
# TAB 1: FUNDING & SPREAD ALERT
# ==========================================
with tab1:
    if not df_f.empty:
        df_f['Nominal'] = clean_numeric(df_f['Nominal'])
        df_f['Rate'] = clean_numeric(df_f['Rate'])
        df_f['Pendapatan_Riil'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        df_f['Net_Yield'] = df_f['Rate'] * 0.8
        net_sbn = current_sbn * 0.9
        
        # Gap vs SBN Net
        df_f['Gap_vs_SBN'] = df_f['Net_Yield'] - net_sbn
        
        # 1. METRICS
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric(f"Total Revenue {selected_month}", f"Rp {df_f['Pendapatan_Riil'].sum():,.0f}")
        m3.metric("Live SBN Net Benchmark", f"{net_sbn:.2f}%")

        st.divider()

        # 2. SPREAD ALERT SECTION (RED BOXES)
        # Filter bilyet yang gap-nya lebih buruk (negatif) dari -spread_threshold
        # Contoh: Jika slider 1%, maka yang gap-nya -1.1%, -2% dst akan muncul.
        df_kritis = df_f[df_f['Gap_vs_SBN'] < -spread_threshold]
        
        st.subheader(f"🚩 Critical Spread Alert (Threshold: {spread_threshold}%)")
        if not df_kritis.empty:
            st.error(f"Terdeteksi **{len(df_kritis)} bilyet** dengan spread yield jauh di bawah SBN Net!")
            cols_k = st.columns(len(df_kritis) if len(df_kritis) <= 4 else 4)
            for i, (_, row) in enumerate(df_kritis.iterrows()):
                with cols_k[i % 4]:
                    with st.container(border=True):
                        st.markdown(f"**{row['Bank']}**")
                        st.markdown(f"Gap: `:red[{row['Gap_vs_SBN']:.2f}%]`")
                        # MATURITY DATE VISIBILITY
                        tgl_jatuh_tempo = row['Jatuh_Tempo'].strftime('%d-%m-%Y') if pd.notnull(row['Jatuh_Tempo']) else "N/A"
                        st.caption(f"Maturity: {tgl_jatuh_tempo}")
        else:
            st.success(f"✅ Aman! Tidak ada bilyet dengan spread yield di bawah {spread_threshold}% dari benchmark.")

        # 3. TABEL DETAIL DENGAN MATURITY
        st.markdown("---")
        st.subheader("📑 Detail Inventori & Maturity Schedule")
        df_disp = df_f.copy()
        # Amankan format tanggal untuk tabel
        df_disp['Jatuh_Tempo'] = df_disp['Jatuh_Tempo'].apply(lambda x: x.strftime('%d-%m-%Y') if pd.notnull(x) else '-')
        
        st.dataframe(df_disp.style.format({
            'Nominal': '{:,.0f}',
            'Pendapatan_Riil': '{:,.0f}',
            'Gap_vs_SBN': '{:.2f}%',
            'Net_Yield': '{:.2f}%'
        }).background_gradient(subset=['Gap_vs_SBN'], cmap='RdYlGn'), use_container_width=True)
    else:
        st.info("Pilih periode untuk memuat data.")

# ==========================================
# TAB 2: REVENUE PER BANK (DETAILED)
# ==========================================
with tab2:
    if not df_f.empty:
        st.subheader(f"🔍 Revenue Breakdown per Bank - {selected_month}")
        list_bank = df_f['Bank'].unique()
        for bank in list_bank:
            df_bank_detail = df_f[df_f['Bank'] == bank].copy()
            with st.container(border=True):
                st.markdown(f"### 🏦 {bank}")
                col_b1, col_b2 = st.columns([2, 1])
                with col_b1:
                    fig_b_bar = px.bar(df_bank_detail, x=df_bank_detail.index, y='Pendapatan_Riil', 
                                       title=f"Revenue per Bilyet (IDR)", text_auto=',.0f')
                    st.plotly_chart(fig_b_bar, use_container_width=True)
                with col_b2:
                    st.metric("Total Bank Revenue", f"Rp {df_bank_detail['Pendapatan_Riil'].sum():,.0f}")
                    st.metric("Bilyet Kritis", f"{len(df_bank_detail[df_bank_detail['Gap_vs_SBN'] < -spread_threshold])}")
                    avg_mat = df_bank_detail['Jatuh_Tempo'].max()
                    st.caption(f"Maturity Terakhir: {avg_mat.strftime('%d-%m-%Y') if pd.notnull(avg_mat) else 'N/A'}")
    else:
        st.info("Data tidak tersedia.")

# TAB 3 (Lending) Tetap Sederhana
with tab3:
    if not df_l.empty:
        st.subheader("Monitoring Lending")
        st.dataframe(df_l, use_container_width=True)
