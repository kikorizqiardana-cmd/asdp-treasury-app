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
        
        # Cleaning Angka (Cek keberadaan kolom dulu biar gak Error)
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

# --- 3. SIDEBAR (MODUL 1 & 2 PRESERVED) ---
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

st.sidebar.markdown("---")
st.sidebar.header("🏢 Bond/Sukuk Simulator")
rating = st.sidebar.selectbox("Pilih Rating Target:", ["AAA", "AA+", "AA", "A", "BBB"])
spread_map = {"AAA": 80, "AA+": 110, "AA": 140, "A": 260, "BBB": 480}
sel_spread = st.sidebar.slider(f"Spread {rating} (bps)", 0, 600, spread_map[rating])
target_bond_gross = current_sbn + (sel_spread / 100)

# --- 4. DASHBOARD UI ---
st.title(f"🚢 ASDP Treasury & ALM Command Center")
tab1, tab2, tab3 = st.tabs(["💰 Modul 1: Funding", "📈 Modul 2: Lending", "📊 Modul 3: ALM Resume"])

# ==========================================
# TAB 1: FUNDING (MODUL 1 - TIDAK BERUBAH)
# ==========================================
with tab1:
    if not df_f.empty:
        df_f['Net_Yield'] = df_f['Rate'] * 0.8
        df_f['Pendapatan_Riil'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        net_sbn = current_sbn * 0.9
        net_bond = target_bond_gross * 0.9
        
        # Opportunity Gain
        total_rev_curr = df_f['Pendapatan_Riil'].sum()
        total_rev_sbn = (df_f['Nominal'] * (net_sbn/100) / 12).sum()
        total_rev_bond = (df_f['Nominal'] * (net_bond/100) / 12).sum()

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric(f"Total Revenue ({sel_month})", f"Rp {total_rev_curr:,.0f}")
        m3.metric("SBN Net Benchmark", f"{net_sbn:.2f}%")

        p1, p2, p3 = st.columns(3)
        p1.metric("Potensi Tambahan (SBN)", f"Rp {total_rev_sbn - total_rev_curr:,.0f}")
        p2.metric(f"Potensi Tambahan ({rating})", f"Rp {total_rev_bond - total_rev_curr:,.0f}")
        p3.metric(f"Target Yield {rating} (Net)", f"{net_bond:.2f}%")

        st.divider()
        c_al1, c_al2 = st.columns(2)
        with c_al1:
            st.subheader("🚩 Spread Alert (vs SBN)")
            with st.container(height=180):
                df_loss = df_f[df_f['Net_Yield'] < net_sbn]
                if not df_loss.empty:
                    for _, row in df_loss.iterrows(): st.error(f"**{row['Bank']}** | Yield: `{row['Net_Yield']:.2f}%`")
                else: st.success("Optimal.")
        with c_al2:
            st.subheader("⏳ Maturity Watch (H-14)")
            with st.container(height=180):
                today = datetime.now()
                df_soon = df_f[(df_f['Jatuh_Tempo'] >= today) & (df_f['Jatuh_Tempo'] <= today + timedelta(days=14))]
                if not df_soon.empty:
                    for _, row in df_soon.iterrows(): st.warning(f"**{row['Bank']}** | `{row['Jatuh_Tempo'].strftime('%d-%m-%Y')}`")
                else: st.info("Aman.")

        st.divider()
        v1, v2 = st.columns([1.2, 1])
        with v1:
            df_bp = df_f.groupby('Bank')['Pendapatan_Riil'].sum().reset_index()
            st.plotly_chart(px.bar(df_bp, x='Bank', y='Pendapatan_Riil', title="Revenue per Bank", text_auto=',.0f'), use_container_width=True)
        with v2:
            st.plotly_chart(px.pie(df_f, values='Net_Yield', names='Bank', hole=0.5, title="Net Yield Mix"), use_container_width=True)

# ==========================================
# TAB 2: LENDING (MODUL 2 - TIDAK BERUBAH + FIX ERROR)
# ==========================================
with tab2:
    if not df_l.empty:
        total_debt = df_l['Nominal'].sum()
        
        l1, l2, l3 = st.columns(3)
        l1.metric("Total Outstanding Debt", f"Rp {total_debt:,.0f}")
        
        # FIX ERROR: Cek apakah kolom CoF ada
        if 'Cost_of_Fund (%)' in df_l.columns:
            avg_cof = df_l['Cost_of_Fund (%)'].mean()
            l2.metric("Avg. Cost of Fund", f"{avg_cof:.2f}%")
        else:
            l2.metric("Avg. Cost of Fund", "N/A (No Column)")
            
        l3.metric("Kreditur Terbesar", df_l.groupby('Kreditur')['Nominal'].sum().idxmax() if 'Kreditur' in df_l.columns else "N/A")

        st.divider()
        st.subheader("🚨 Payment Maturity Alert (H-14)")
        with st.container(height=150):
            today = datetime.now()
            if 'Jatuh_Tempo' in df_l.columns:
                df_pay = df_l[(df_l['Jatuh_Tempo'] >= today) & (df_l['Jatuh_Tempo'] <= today + timedelta(days=14))]
                if not df_pay.empty:
                    for _, row in df_pay.iterrows(): st.error(f"**{row['Kreditur']}** | Rp {row['Nominal']:,.0f} | `{row['Jatuh_Tempo'].strftime('%d-%m-%Y')}`")
                else: st.success("Tidak ada cicilan dekat.")

        if 'Kreditur' in df_l.columns:
            st.subheader("📊 Eksposisi Pinjaman per Bank (Kreditur)")
            df_kred = df_l.groupby('Kreditur')['Nominal'].sum().reset_index().sort_values('Nominal', ascending=False)
            st.plotly_chart(px.bar(df_kred, x='Kreditur', y='Nominal', text_auto=',.0f', color='Kreditur'), use_container_width=True)

# ==========================================
# TAB 3: MODUL 3 - ALM RESUME (NEW!)
# ==========================================
with tab3:
    st.header("📊 Asset Liability Management (ALM) Resume")
    
    if not df_f.empty and not df_l.empty:
        # 1. Net Liquidity Position
        total_asset = df_f['Nominal'].sum()
        total_liability = df_l['Nominal'].sum()
        net_gap = total_asset - total_liability
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Liquid Asset (Funding)", f"Rp {total_asset:,.0f}")
        c2.metric("Total Debt (Lending)", f"Rp {total_liability:,.0f}")
        c3.metric("Net Liquidity Gap", f"Rp {net_gap:,.0f}", delta=f"{'SURPLUS' if net_gap > 0 else 'DEFISIT'}")
        
        st.divider()
        
        # 2. Interest Rate Matching (Inflow vs Outflow)
        # Inflow Bunga per Bulan (Funding)
        inflow_bunga = df_f['Pendapatan_Riil'].sum()
        
        # Outflow Bunga per Bulan (Lending)
        if 'Cost_of_Fund (%)' in df_l.columns:
            outflow_bunga = (df_l['Nominal'] * (df_l['Cost_of_Fund (%)'] / 100) / 12).sum()
        else:
            outflow_bunga = 0
            
        a1, a2 = st.columns(2)
        with a1:
            st.subheader("💹 Interest Flow Analysis (Bulanan)")
            fig_alm = go.Figure(data=[
                go.Bar(name='Inflow (Bunga Deposito)', x=['Cashflow'], y=[inflow_bunga], marker_color='green'),
                go.Bar(name='Outflow (Beban Bunga)', x=['Cashflow'], y=[outflow_bunga], marker_color='red')
            ])
            fig_alm.update_layout(barmode='group', title="Inflow vs Outflow Bunga Bulanan")
            st.plotly_chart(fig_alm, use_container_width=True)
            
        with a2:
            st.subheader("💡 ALM Strategic Note")
            net_interest = inflow_bunga - outflow_bunga
            st.write(f"**Net Interest Income (NII):** Rp {net_interest:,.0f}")
            if net_interest > 0:
                st.success("✅ Treasury ASDP dalam posisi **Net Inflow**. Pendapatan bunga deposito mampu menutup beban bunga bank.")
            else:
                st.warning("🚨 Treasury ASDP dalam posisi **Net Outflow**. Beban bunga bank lebih tinggi dari pendapatan deposito.")
                
        # 3. Maturity Profile Gap (Visualisasi Jadwal Jatuh Tempo)
        st.subheader("📅 Maturity Profile Comparison")
        df_f_mat = df_f[['Jatuh_Tempo', 'Nominal']].copy()
        df_f_mat['Tipe'] = 'Asset (Funding)'
        df_l_mat = df_l[['Jatuh_Tempo', 'Nominal']].copy()
        df_l_mat['Tipe'] = 'Liability (Lending)'
        
        df_merged_mat = pd.concat([df_f_mat, df_l_mat])
        df_merged_mat = df_merged_mat[df_merged_mat['Jatuh_Tempo'].notnull()]
        
        fig_mat = px.area(df_merged_mat.sort_values('Jatuh_Tempo'), x='Jatuh_Tempo', y='Nominal', color='Tipe',
                          title="Asset vs Liability Maturity Profile", labels={'Nominal': 'Volume Dana'})
        st.plotly_chart(fig_mat, use_container_width=True)
    else:
        st.info("Upload/Konek data Funding & Lending untuk melihat Resume ALM.")
