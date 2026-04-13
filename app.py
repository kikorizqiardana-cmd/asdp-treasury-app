import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta

# --- 1. CONFIG HALAMAN ---
st.set_page_config(page_title="Corporate Treasury Command Center", layout="wide", page_icon="🚢")

# --- 2. DATA ENGINE ---
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
        # Load Tab Funding & Lending
        df_f = pd.read_csv(base_url + "Funding")
        df_l = pd.read_csv(base_url + "Lending")
        
        # Bersihkan nama kolom
        df_f.columns = [c.strip() for c in df_f.columns]
        df_l.columns = [c.strip() for c in df_l.columns]
        
        # Penyelarasan Nama Kolom
        if 'Rate (%)' in df_f.columns: df_f.rename(columns={'Rate (%)': 'Rate'}, inplace=True)
        if 'Debitur' in df_l.columns: df_l.rename(columns={'Debitur': 'Kreditur'}, inplace=True)
        
        # Cleaning Angka & Tanggal
        for df in [df_f, df_l]:
            for col in ['Nominal', 'Rate', 'Lending_Rate (%)', 'Cost_of_Fund (%)']:
                if col in df.columns: df[col] = clean_numeric_robust(df[col])
            if 'Jatuh_Tempo' in df.columns:
                df['Jatuh_Tempo'] = pd.to_datetime(df['Jatuh_Tempo'], dayfirst=True, errors='coerce')
            if 'Periode' in df.columns:
                df['Periode'] = df['Periode'].astype(str).str.strip()
                
        return df_f, df_l, None
    except Exception as e: return pd.DataFrame(), pd.DataFrame(), str(e)

def get_live_sbn():
    try:
        data = yf.Ticker("ID10Y=F").history(period="1d")
        if not data.empty: return round(float(data['Close'].iloc[-1]), 2), "Yahoo Finance (Live)"
    except: pass
    return 6.65, "Default (Manual)"

# --- 3. SIDEBAR ---
logo_path = "ferry.png"
if os.path.exists(logo_path): st.sidebar.image(logo_path, use_container_width=True)
st.sidebar.markdown("---")

df_f_raw, df_l_raw, err = load_gsheets_data()
if err: 
    st.sidebar.error(f"API Error: {err}")
    st.stop()
else:
    all_months = sorted(list(set(df_f_raw['Periode'].unique()) | set(df_l_raw['Periode'].unique())), reverse=True)
    sel_month = st.sidebar.selectbox("Pilih Periode Analisis:", all_months)
    df_f = df_f_raw[df_f_raw['Periode'] == sel_month].copy()
    df_l = df_l_raw[df_l_raw['Periode'] == sel_month].copy()

st.sidebar.header("⚙️ Market Intelligence")
sbn_val, sbn_source = get_live_sbn()
current_sbn = st.sidebar.number_input(f"Benchmark SBN 10Y ({sbn_source})", value=sbn_val, step=0.01)

# --- 4. DASHBOARD UI ---
st.title(f"🚢 Treasury & Debt Strategic Dashboard")
tab1, tab2, tab3 = st.tabs(["💰 Modul 1: Funding", "📈 Modul 2: Lending & Cash Out", "📊 Modul 3: ALM Resume"])

# ==========================================
# TAB 1: FUNDING (MODUL 1)
# ==========================================
with tab1:
    if not df_f.empty:
        df_f['Pendapatan_Riil'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        df_f['Net_Yield'] = df_f['Rate'] * 0.8
        net_sbn = current_sbn * 0.9
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric(f"Total Revenue ({sel_month})", f"Rp {df_f['Pendapatan_Riil'].sum():,.0f}")
        m3.metric("SBN Net Benchmark", f"{net_sbn:.2f}%")
        
        v1, v2 = st.columns([1, 1])
        with v1:
            df_bank_rev = df_f.groupby('Bank')['Pendapatan_Riil'].sum().reset_index()
            fig_rev = px.bar(df_bank_rev, x='Bank', y='Pendapatan_Riil', title="Revenue per Bank (IDR)", text_auto=',.0f')
            st.plotly_chart(fig_rev, use_container_width=True)
        with v2:
            fig_yield_pie = px.pie(df_f, values='Net_Yield', names='Bank', title="Komposisi Net Yield per Bank", hole=0.4)
            st.plotly_chart(fig_yield_pie, use_container_width=True)
    else: st.info("Data Funding tidak tersedia untuk periode ini.")

# ==========================================
# TAB 2: LENDING & CASH OUT (MODUL 2)
# ==========================================
with tab2:
    if not df_l.empty:
        # Perhitungan Cash Out
        # Jika kolom bunga tidak eksplisit, asumsikan nominal adalah kewajiban pembayaran di periode tsb
        total_cash_out = df_l['Nominal'].sum()
        
        l1, l2, l3 = st.columns(3)
        l1.metric("Total Cash Out (Pembayaran)", f"Rp {total_cash_out:,.0f}")
        l2.metric("Jumlah Kreditur", len(df_l['Kreditur'].unique()))
        l3.metric("Periode Pembayaran", sel_month)

        st.divider()

        # MODUL 2 ALERT: Jatuh Tempo Pembayaran (14 Hari)
        st.subheader("🚨 Payment Maturity Alert (H-14)")
        with st.container(height=250):
            today = datetime.now()
            limit_14 = today + timedelta(days=14)
            
            # Filter data yang jatuh tempo dalam 14 hari ke depan
            df_alert = df_l[(df_l['Jatuh_Tempo'] >= today) & (df_l['Jatuh_Tempo'] <= limit_14)].sort_values('Jatuh_Tempo')
            
            if not df_alert.empty:
                for _, row in df_alert.iterrows():
                    sisa_hari = (row['Jatuh_Tempo'] - today).days
                    tgl_str = row['Jatuh_Tempo'].strftime('%d-%m-%Y')
                    st.error(f"**{row['Kreditur']}** | Kewajiban: `Rp {row['Nominal']:,.0f}` | Jatuh Tempo: **{tgl_str}** ({sisa_hari} hari lagi)")
            else:
                st.success("✅ Tidak ada jadwal pembayaran dalam 14 hari ke depan.")

        st.divider()

        # Visualisasi Lending
        c1, c2 = st.columns(2)
        with c1:
            fig_debt = px.bar(df_l, x='Kreditur', y='Nominal', color='Kreditur', 
                              title="Kewajiban Pembayaran per Bank", text_auto=',.0f')
            st.plotly_chart(fig_debt, use_container_width=True)
        with c2:
            # Jika ada kolom Tipe (Bunga/Pokok), tampilkan distribusinya
            if 'Tipe' in df_l.columns:
                fig_type = px.pie(df_l, values='Nominal', names='Tipe', title="Proporsi Pokok vs Bunga")
                st.plotly_chart(fig_type, use_container_width=True)

        with st.expander("📑 Detail Tabel Kewajiban Pembayaran"):
            df_l_disp = df_l.copy()
            df_l_disp['Jatuh_Tempo'] = df_l_disp['Jatuh_Tempo'].apply(lambda x: x.strftime('%d-%m-%Y') if pd.notnull(x) else '-')
            st.dataframe(df_l_disp, use_container_width=True)
    else: st.info("Data Lending tidak tersedia untuk periode ini.")

# ==========================================
# TAB 3: ALM RESUME
# ==========================================
with tab3:
    if not df_f.empty and not df_l.empty:
        rev_in = df_f['Pendapatan_Riil'].sum()
        cash_out = df_l['Nominal'].sum()
        net_pos = rev_in - cash_out
        
        r1, r2, r3 = st.columns(3)
        r1.metric("Total Revenue (Inflow)", f"Rp {rev_in:,.0f}")
        r2.metric("Total Debt Payment (Outflow)", f"Rp {cash_out:,.0f}")
        r3.metric("Net Cash Position", f"Rp {net_pos:,.0f}", delta=f"{'Surplus' if net_pos > 0 else 'Defisit'}")
