import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="ASDP ALM Command Center", layout="wide", page_icon="🚢")

# --- 2. ENGINE PEMBERSIH DATA (ANTI-ERROR) ---
def clean_numeric_robust(series):
    def process_val(val):
        val = str(val).strip().replace('Rp', '').replace('%', '').replace(' ', '').replace(',', '')
        if not val or val == 'nan' or val == 'None': return "0"
        return val
    return pd.to_numeric(series.apply(lambda x: str(x).replace('.', '') if '.' in str(x) and len(str(x).split('.')[-1]) == 3 else x).apply(process_val), errors='coerce').fillna(0)

@st.cache_data(ttl=1)
def load_gsheets_data():
    sheet_id = "182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY"
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet="
    try:
        df_f = pd.read_csv(base_url + "Funding")
        df_l = pd.read_csv(base_url + "Lending")
        df_f.columns = [c.strip() for c in df_f.columns]
        df_l.columns = [c.strip() for c in df_l.columns]
        
        # Penyelarasan Nama Kolom
        if 'Rate (%)' in df_f.columns: df_f.rename(columns={'Rate (%)': 'Rate'}, inplace=True)
        if 'Bank' in df_l.columns: df_l.rename(columns={'Bank': 'Kreditur'}, inplace=True)
        
        # Cleaning Angka
        for c in ['Nominal', 'Rate']:
            if c in df_f.columns: df_f[c] = clean_numeric_robust(df_f[c])
        
        cols_lending = ['Nominal', 'Cost_of_Fund (%)', 'Lending_Rate (%)']
        for c in cols_lending:
            if c in df_l.columns: df_l[c] = clean_numeric_robust(df_l[c])
            
        if 'Jatuh_Tempo' in df_f.columns:
            df_f['Jatuh_Tempo'] = pd.to_datetime(df_f['Jatuh_Tempo'], dayfirst=True, errors='coerce')
        if 'Jatuh_Tempo' in df_l.columns:
            df_l['Jatuh_Tempo'] = pd.to_datetime(df_l['Jatuh_Tempo'], dayfirst=True, errors='coerce')
            
        return df_f, df_l, None
    except Exception as e: return pd.DataFrame(), pd.DataFrame(), str(e)

def get_live_sbn():
    try:
        data = yf.Ticker("ID10Y=F").history(period="1d")
        if not data.empty: return round(float(data['Close'].iloc[-1]), 2), "Yahoo Finance (Live)"
    except: pass
    return 6.65, "Default (Manual)"

# --- 3. SIDEBAR (LOGO & MARKET) ---
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
st.title(f"🚢 ASDP Treasury & ALM Command Center")
tab1, tab2, tab3 = st.tabs(["💰 Modul 1: Funding", "📈 Modul 2: Lending", "📊 Modul 3: ALM Resume"])

# ==========================================
# TAB 1 & 2 (PERSTABLISHED BY KIKO)
# ==========================================
# [Kode Tab 1 & Tab 2 tetap dipertahankan sesuai desain sebelumnya agar tidak berubah]
with tab1:
    if not df_f.empty:
        df_f['Net_Yield'] = df_f['Rate'] * 0.8
        df_f['Pendapatan_Riil'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        net_sbn = current_sbn * 0.9
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric(f"Total Revenue ({sel_month})", f"Rp {df_f['Pendapatan_Riil'].sum():,.0f}")
        m3.metric("SBN Net Benchmark", f"{net_sbn:.2f}%")
        st.divider()
        v1, v2 = st.columns([1.2, 1])
        with v1: st.plotly_chart(px.bar(df_f.groupby('Bank')['Pendapatan_Riil'].sum().reset_index(), x='Bank', y='Pendapatan_Riil', title="Revenue per Bank", text_auto=',.0f'), use_container_width=True)
        with v2: st.plotly_chart(px.pie(df_f, values='Net_Yield', names='Bank', hole=0.5, title="Net Yield Mix"), use_container_width=True)

with tab2:
    if not df_l.empty:
        total_debt = df_l['Nominal'].sum()
        l1, l2, l3 = st.columns(3)
        l1.metric("Total Outstanding Debt", f"Rp {total_debt:,.0f}")
        l2.metric("Avg. CoF", f"{df_l['Cost_of_Fund (%)'].mean():.2f}%" if 'Cost_of_Fund (%)' in df_l.columns else "N/A")
        l3.metric("Kreditur Terbesar", df_l.groupby('Kreditur')['Nominal'].sum().idxmax() if 'Kreditur' in df_l.columns else "N/A")
        st.divider()
        if 'Kreditur' in df_l.columns: st.plotly_chart(px.bar(df_l.groupby('Kreditur')['Nominal'].sum().reset_index().sort_values('Nominal', ascending=False), x='Kreditur', y='Nominal', text_auto=',.0f', color='Kreditur', title="Debt per Bank"), use_container_width=True)

# ==========================================
# TAB 3: MODUL 3 - ALM RESUME (REVENUE & ICR)
# ==========================================
with tab3:
    st.header(f"📊 Financial Health & ALM Metrics - {sel_month}")
    
    if not df_f.empty and not df_l.empty:
        # --- PERHITUNGAN REVENUE & BEBAN ---
        # 1. Inflow: Pendapatan Bunga Deposito (Funding)
        inflow_bunga = df_f['Pendapatan_Riil'].sum()
        
        # 2. Outflow: Beban Bunga Bank (Lending - menggunakan Cost of Fund)
        if 'Cost_of_Fund (%)' in df_l.columns:
            outflow_bunga = (df_l['Nominal'] * (df_l['Cost_of_Fund (%)'] / 100) / 12).sum()
        else:
            outflow_bunga = 0
            
        # 3. Interest Coverage Ratio (ICR)
        # ICR = Interest Income / Interest Expense
        icr_ratio = inflow_bunga / outflow_bunga if outflow_bunga > 0 else 0
        
        # --- DISPLAY METRICS ---
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Interest Revenue", f"Rp {inflow_bunga:,.0f}")
        c2.metric("Total Interest Expense", f"Rp {outflow_bunga:,.0f}")
        
        # Net Interest Margin (Simple)
        net_interest = inflow_bunga - outflow_bunga
        c3.metric("Net Interest Position", f"Rp {net_interest:,.0f}", delta=f"{'Surplus' if net_interest > 0 else 'Defisit'}")
        
        # ICR Metric with Color Coding
        icr_color = "normal" if icr_ratio >= 1.5 else "inverse"
        c4.metric("Interest Coverage Ratio (ICR)", f"{icr_ratio:.2f}x", delta="Target: > 1.5x", delta_color=icr_color)
        
        st.divider()
        
        # --- VISUALISASI MODUL 3 ---
        col_v1, col_v2 = st.columns([1, 1])
        
        with col_v1:
            st.subheader("💹 Inflow vs Outflow Cash")
            fig_compare = go.Figure(data=[
                go.Bar(name='Interest Income (Asset)', x=['Monthly bunga'], y=[inflow_bunga], marker_color='#2ecc71'),
                go.Bar(name='Interest Expense (Liability)', x=['Monthly bunga'], y=[outflow_bunga], marker_color='#e74c3c')
            ])
            fig_compare.update_layout(barmode='group', height=400)
            st.plotly_chart(fig_compare, use_container_width=True)
            
        with col_v2:
            st.subheader("🛡️ ICR Stability Gauge")
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = icr_ratio,
                title = {'text': "Coverage Strength"},
                gauge = {
                    'axis': {'range': [0, 5]},
                    'bar': {'color': "darkblue"},
                    'steps' : [
                        {'range': [0, 1], 'color': "#ff4d4d"},
                        {'range': [1, 1.5], 'color': "#ffa64d"},
                        {'range': [1.5, 5], 'color': "#33cc33"}],
                    'threshold' : {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': 1.5}
                }
            ))
            fig_gauge.update_layout(height=400)
            st.plotly_chart(fig_gauge, use_container_width=True)

        # Formula Note
        st.info(f"**Analisis ICR:** Saat ini ICR ASDP berada di angka **{icr_ratio:.2f}x**. Artinya, setiap Rp 1 beban bunga bank di-cover oleh Rp {icr_ratio:.2f} pendapatan dari deposito.")

    else:
        st.warning("Data tidak lengkap untuk menghitung modul ALM.")
