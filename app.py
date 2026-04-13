import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="ASDP Strategic Dashboard", layout="wide", page_icon="🚢")

# --- 2. ENGINE PEMBERSIH DATA ---
def clean_numeric_robust(series):
    def process_val(val):
        val = str(val).strip().replace('Rp', '').replace('%', '').replace(' ', '').replace(',', '')
        if not val or val == 'nan' or val == 'None': return "0"
        return val
    # Menghapus titik ribuan sebelum konversi jika ada format 1.000.000
    # Namun pd.to_numeric biasanya butuh penanganan manual untuk format IDR
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
        if 'Debitur' in df_l.columns: df_l.rename(columns={'Debitur': 'Debitur'}, inplace=True) # Tetap
        if 'Bank' in df_l.columns: df_l.rename(columns={'Bank': 'Kreditur'}, inplace=True)
        
        # Cleaning Dasar
        for c in ['Nominal', 'Rate']:
            if c in df_f.columns: df_f[c] = clean_numeric_robust(df_f[c])
        for c in ['Nominal', 'Cost_of_Fund (%)']:
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

# --- 3. SIDEBAR (PERSIS SCREENSHOT) ---
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
st.title(f"🚢 ASDP Treasury Strategic Dashboard")
tab1, tab2 = st.tabs(["💰 Performance & Projections", "📈 Lending Monitor"])

# ==========================================
# TAB 1: FUNDING (REKONSTRUKSI TOTAL)
# ==========================================
with tab1:
    if not df_f.empty:
        # Perhitungan
        df_f['Net_Yield'] = df_f['Rate'] * 0.8
        df_f['Pendapatan_Riil'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        net_sbn = current_sbn * 0.9
        net_bond = target_bond_gross * 0.9
        
        # Opportunity Gain
        total_rev_curr = df_f['Pendapatan_Riil'].sum()
        total_rev_sbn = (df_f['Nominal'] * (net_sbn/100) / 12).sum()
        total_rev_bond = (df_f['Nominal'] * (net_bond/100) / 12).sum()
        diff_sbn = total_rev_sbn - total_rev_curr
        diff_bond = total_rev_bond - total_rev_curr

        # BARIS 1: METRICS UTAMA
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric(f"Total Revenue ({sel_month})", f"Rp {total_rev_curr:,.0f}")
        m3.metric("SBN Net Benchmark", f"{net_sbn:.2f}%")

        # BARIS 2: OPPORTUNITY GAIN
        p1, p2, p3 = st.columns(3)
        p1.metric("Potensi Tambahan Revenue (SBN)", f"Rp {diff_sbn:,.0f}", 
                  delta=f"{((total_rev_sbn/total_rev_curr)-1)*100:.1f}% Increase")
        p2.metric(f"Potensi Tambahan Revenue ({rating})", f"Rp {diff_bond:,.0f}", 
                  delta=f"{((total_rev_bond/total_rev_curr)-1)*100:.1f}% Increase")
        p3.metric(f"Target Yield {rating} (Net)", f"{net_bond:.2f}%")

        st.divider()

        # BARIS 3: ALERTS (SIDE BY SIDE)
        col_alert1, col_alert2 = st.columns(2)
        with col_alert1:
            st.subheader("🚩 Spread Alert (vs SBN)")
            with st.container(height=200):
                df_loss = df_f[df_f['Net_Yield'] < net_sbn]
                if not df_loss.empty:
                    for _, row in df_loss.iterrows():
                        st.error(f"**{row['Bank']}** | Yield: `{row['Net_Yield']:.2f}%` | Rev: `Rp {row['Pendapatan_Riil']:,.0f}`")
                else: st.success("Seluruh penempatan optimal.")

        with col_alert2:
            st.subheader("⏳ Maturity Watch (H-14)")
            with st.container(height=200):
                today = datetime.now()
                df_soon = df_f[(df_f['Jatuh_Tempo'] >= today) & (df_f['Jatuh_Tempo'] <= today + timedelta(days=14))]
                if not df_soon.empty:
                    for _, row in df_soon.iterrows():
                        st.warning(f"**{row['Bank']}** | `{row['Jatuh_Tempo'].strftime('%d-%m-%Y')}`")
                else: st.info("Tidak ada jatuh tempo dalam 14 hari.")

        st.divider()

        # BARIS 4: ANALYTICS (SIDE BY SIDE)
        st.subheader("📊 Strategic Revenue & Yield Analytics")
        v1, v2 = st.columns([1.2, 1])
        df_bank_perf = df_f.groupby('Bank').agg({'Pendapatan_Riil': 'sum', 'Net_Yield': 'mean'}).reset_index().sort_values('Pendapatan_Riil', ascending=False)

        with v1:
            fig_rev = px.bar(df_bank_perf, x='Bank', y='Pendapatan_Riil', title="Total Revenue per Bank (IDR)", text_auto=',.0f', color='Bank')
            fig_rev.update_layout(showlegend=False)
            st.plotly_chart(fig_rev, use_container_width=True)
            
        with v2:
            fig_yield = px.pie(df_bank_perf, values='Net_Yield', names='Bank', hole=0.5, title="Komposisi Net Yield per Bank")
            st.plotly_chart(fig_yield, use_container_width=True)

        with st.expander("📑 Detail Inventori & Full Data Analysis"):
            st.dataframe(df_f, use_container_width=True)

# ==========================================
# TAB 2: LENDING (BANK SEBAGAI KREDITUR)
# ==========================================
with tab2:
    if not df_l.empty:
        # Perhitungan
        total_debt = df_l['Nominal'].sum()
        
        l1, l2, l3 = st.columns(3)
        l1.metric("Total Outstanding Debt", f"Rp {total_debt:,.0f}")
        l2.metric("Avg. Cost of Fund", f"{df_l['Cost_of_Fund (%)'].mean():.2f}%")
        l3.metric("Kreditur Terbesar", df_l.groupby('Kreditur')['Nominal'].sum().idxmax())

        st.divider()
        
        # Alert Pembayaran
        st.subheader("🚨 Payment Maturity Alert (H-14)")
        with st.container(height=150):
            today = datetime.now()
            df_pay = df_l[(df_l['Jatuh_Tempo'] >= today) & (df_l['Jatuh_Tempo'] <= today + timedelta(days=14))]
            if not df_pay.empty:
                for _, row in df_pay.iterrows():
                    st.error(f"**{row['Kreditur']}** | Rp {row['Nominal']:,.0f} | `{row['Jatuh_Tempo'].strftime('%d-%m-%Y')}`")
            else: st.success("Tidak ada kewajiban jatuh tempo dalam 14 hari.")

        # Grafik Kreditur (Bank)
        st.subheader("📊 Analisis Kreditur (Pemberi Pinjaman)")
        df_kred = df_l.groupby('Kreditur')['Nominal'].sum().reset_index().sort_values('Nominal', ascending=False)
        fig_kred = px.bar(df_kred, x='Kreditur', y='Nominal', title="Eksposisi Pinjaman per Bank (Kreditur)", text_auto=',.0f', color='Kreditur')
        st.plotly_chart(fig_kred, use_container_width=True)
