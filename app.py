import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime

# --- 1. CONFIG HALAMAN ---
st.set_page_config(page_title="ASDP Treasury Analytics", layout="wide", page_icon="🚢")

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

# Sidebar: Market & Filter
sbn_val, sbn_source = get_live_sbn()
st.sidebar.header("⚙️ Market Intelligence")
current_sbn = st.sidebar.number_input(f"Benchmark SBN 10Y ({sbn_source})", value=sbn_val, step=0.01)
threshold = st.sidebar.slider("Threshold Alert (%)", 0.0, 5.0, 0.5)

all_periods = sorted(list(set(df_f_raw['Periode'].unique())), reverse=True)
selected_month = st.sidebar.selectbox("Pilih Periode Analisis:", all_periods)

# Filter Data
df_f = df_f_raw[df_f_raw['Periode'] == selected_month].copy()
df_l = df_l_raw[df_l_raw['Periode'] == selected_month].copy()

# --- 4. DASHBOARD UI ---
st.title(f"🚢 ASDP Revenue Analytics - {selected_month}")
tab1, tab2, tab3 = st.tabs(["💰 Funding Performance", "📊 Revenue per Bank", "📉 Lending & ALM"])

# ==========================================
# TAB 1: FUNDING PERFORMANCE
# ==========================================
with tab1:
    if not df_f.empty:
        df_f['Nominal'] = clean_numeric(df_f['Nominal'])
        df_f['Rate'] = clean_numeric(df_f['Rate'])
        df_f['Pendapatan_Riil'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        df_f['Net_Yield'] = df_f['Rate'] * 0.8
        net_sbn = current_sbn * 0.9
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric(f"Total Revenue {selected_month}", f"Rp {df_f['Pendapatan_Riil'].sum():,.0f}")
        m3.metric("Live SBN Net Benchmark", f"{net_sbn:.2f}%")

        st.divider()
        st.subheader("🌐 Agregat Portofolio Seluruh Bank")
        c1, c2 = st.columns([2, 1])
        with c1:
            df_agg = df_f.groupby('Bank')['Pendapatan_Riil'].sum().reset_index().sort_values('Pendapatan_Riil', ascending=False)
            fig_agg = px.bar(df_agg, x='Bank', y='Pendapatan_Riil', text_auto=',.0f', 
                             title="Total Revenue per Bank (IDR)", color='Bank')
            st.plotly_chart(fig_agg, use_container_width=True)
        with c2:
            fig_pie_agg = px.pie(df_f, values='Nominal', names='Bank', hole=0.4, title="Konsentrasi Nominal per Bank (%)")
            st.plotly_chart(fig_pie_agg, use_container_width=True)

        with st.expander("📑 Lihat Detail Tabel Data"):
            st.dataframe(df_f, use_container_width=True)
    else:
        st.info("Pilih periode untuk memuat data.")

# ==========================================
# TAB 2: REVENUE PER BANK (DETAILED)
# ==========================================
with tab2:
    if not df_f.empty:
        st.subheader(f"🔍 Deep Dive Revenue per Bank - {selected_month}")
        
        # Ambil daftar bank unik di bulan tersebut
        list_bank = df_f['Bank'].unique()
        
        for bank in list_bank:
            df_bank_detail = df_f[df_f['Bank'] == bank].copy()
            total_rev_bank = df_bank_detail['Pendapatan_Riil'].sum()
            
            with st.container(border=True):
                st.markdown(f"### 🏦 Bank: {bank}")
                col_b1, col_b2, col_b3 = st.columns([2, 1, 1])
                
                with col_b1:
                    # Bar chart per bilyet
                    # Memastikan kolom Nomor_Bilyet ada, jika tidak pakai index
                    label_bilyet = 'Nomor_Bilyet' if 'Nomor_Bilyet' in df_bank_detail.columns else df_bank_detail.index
                    fig_b_bar = px.bar(df_bank_detail, x=label_bilyet, y='Pendapatan_Riil', 
                                       title=f"Revenue per Bilyet - {bank}",
                                       text_auto=',.0f', color_discrete_sequence=['#004d99'])
                    st.plotly_chart(fig_b_bar, use_container_width=True)
                
                with col_b2:
                    # Pie chart kontribusi bilyet terhadap total revenue bank tersebut
                    fig_b_pie = px.pie(df_bank_detail, values='Pendapatan_Riil', names=label_bilyet,
                                       title=f"Kontribusi Bilyet (%)",
                                       hole=0.3)
                    fig_b_pie.update_traces(textinfo='percent+label')
                    st.plotly_chart(fig_b_pie, use_container_width=True)
                
                with col_b3:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    st.metric("Total Bank Revenue", f"Rp {total_rev_bank:,.0f}")
                    st.metric("Jumlah Bilyet", f"{len(df_bank_detail)}")
                    st.caption(f"Rata-rata Yield: {df_bank_detail['Rate'].mean():.2f}%")
    else:
        st.info("Data tidak tersedia.")

# ==========================================
# TAB 3: LENDING & ALM
# ==========================================
with tab3:
    if not df_l.empty:
        st.subheader("Monitoring Lending (Outstanding)")
        st.dataframe(df_l, use_container_width=True)
        # Tambahkan resume ALM sederhana
        if not df_f.empty:
            surplus = df_f['Nominal'].sum() - clean_numeric(df_l_raw['Nominal']).sum()
            st.metric("Total Asset-Liability Gap (Nominal)", f"Rp {surplus:,.0f}")
