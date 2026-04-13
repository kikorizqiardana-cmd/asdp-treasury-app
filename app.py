import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta

# --- 1. CONFIG HALAMAN ---
st.set_page_config(page_title="ASDP Strategic Treasury", layout="wide", page_icon="🚢")

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
        df_f = pd.read_csv(base_url + "Funding")
        df_l = pd.read_csv(base_url + "Lending")
        df_f.columns = [c.strip() for c in df_f.columns]
        df_l.columns = [c.strip() for c in df_l.columns]
        if 'Debitur' in df_l.columns: df_l.rename(columns={'Debitur': 'Kreditur'}, inplace=True)
        if 'Rate (%)' in df_f.columns: df_f.rename(columns={'Rate (%)': 'Rate'}, inplace=True)
        for c in ['Nominal', 'Rate']:
            if c in df_f.columns: df_f[c] = clean_numeric_robust(df_f[c])
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

# --- 3. SIDEBAR ---
logo_path = "ferry.png"
if os.path.exists(logo_path): st.sidebar.image(logo_path, use_container_width=True)
st.sidebar.markdown("---")

df_f_raw, df_l_raw, err = load_gsheets_data()
if err: 
    st.sidebar.error(f"API Error: {err}")
    st.stop()
else:
    all_months = sorted(df_f_raw['Periode'].unique().tolist(), reverse=True)
    sel_month = st.sidebar.selectbox("Pilih Periode Analisis:", all_months)
    df_f = df_f_raw[df_f_raw['Periode'] == sel_month].copy()

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

with tab1:
    if not df_f.empty:
        # Kalkulasi Dasar
        df_f['Net_Yield'] = df_f['Rate'] * 0.8
        df_f['Pendapatan_Riil'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        
        # Benchmark Net (Pajak SBN/Obligasi 10%)
        net_sbn = current_sbn * 0.9
        net_bond = target_bond_gross * 0.9
        
        # Kalkulasi Potensi Revenue Tambahan
        total_rev_current = df_f['Pendapatan_Riil'].sum()
        total_rev_sbn = (df_f['Nominal'] * (net_sbn / 100) / 12).sum()
        total_rev_bond = (df_f['Nominal'] * (net_bond / 100) / 12).sum()
        
        diff_sbn = total_rev_sbn - total_rev_current
        diff_bond = total_rev_bond - total_rev_current
        
        # 1. METRICS BARIS 1 (KONDISI SAAT INI)
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric(f"Total Revenue ({sel_month})", f"Rp {total_rev_current:,.0f}")
        m3.metric("SBN Net Benchmark", f"{net_sbn:.2f}%")

        # 2. METRICS BARIS 2 (PROYEKSI TAMBAHAN / OPPORTUNITY GAIN)
        p1, p2, p3 = st.columns(3)
        p1.metric("Potensi Tambahan Revenue (SBN)", f"Rp {diff_sbn:,.0f}", 
                  delta=f"{((total_rev_sbn/total_rev_current)-1)*100:.1f}% Increase", delta_color="normal")
        p2.metric(f"Potensi Tambahan Revenue ({rating})", f"Rp {diff_bond:,.0f}", 
                  delta=f"{((total_rev_bond/total_rev_current)-1)*100:.1f}% Increase", delta_color="normal")
        p3.metric(f"Target Yield {rating} (Net)", f"{net_bond:.2f}%")

        st.divider()

        # 3. ALERTS (SCROLLABLE)
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            st.subheader("🚩 Spread Alert (vs SBN)")
            with st.container(height=160):
                df_loss = df_f[df_f['Net_Yield'] < net_sbn]
                if not df_loss.empty:
                    for _, row in df_loss.iterrows():
                        st.error(f"**{row['Bank']}** | Yield: `{row['Net_Yield']:.2f}%` | Rev: `Rp {row['Pendapatan_Riil']:,.0f}`")
                else: st.success("Seluruh penempatan optimal.")

        with col_a2:
            st.subheader("⏳ Maturity Watch (H-14)")
            with st.container(height=160):
                today = datetime.now()
                df_soon = df_f[(df_f['Jatuh_Tempo'] >= today) & (df_f['Jatuh_Tempo'] <= today + timedelta(days=14))]
                if not df_soon.empty:
                    for _, row in df_soon.iterrows():
                        st.warning(f"**{row['Bank']}** | `{row['Jatuh_Tempo'].strftime('%d-%m-%Y')}` | Rp {row['Nominal']:,.0f}")
                else: st.info("Tidak ada jatuh tempo dalam 14 hari.")

        st.divider()

        # 4. PERFORMANCE CHARTS
        st.subheader("📊 Strategic Revenue & Yield Analytics")
        v1, v2 = st.columns([1, 1])
        
        df_bank_perf = df_f.groupby('Bank').agg({
            'Pendapatan_Riil': 'sum',
            'Net_Yield': 'mean'
        }).reset_index().sort_values('Pendapatan_Riil', ascending=False)

        with v1:
            # BAR CHART REVENUE (RUPIAH)
            fig_rev = px.bar(
                df_bank_perf, 
                x='Bank', 
                y='Pendapatan_Riil',
                title=f"Total Revenue per Bank (IDR)",
                text_auto=',.0f',
                color='Bank',
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            fig_rev.update_traces(textposition='outside')
            st.plotly_chart(fig_rev, use_container_width=True)
            
        with v2:
            # PIE CHART YIELD (%)
            fig_yield_pie = px.pie(
                df_bank_perf, 
                values='Net_Yield', 
                names='Bank',
                title="Komposisi Net Yield per Bank",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Safe
            )
            fig_yield_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_yield_pie, use_container_width=True)

        # 5. TABEL DETAIL
        with st.expander("📑 Detail Inventori & Full Data Analysis"):
            df_disp = df_f.copy()
            df_disp['Jatuh_Tempo'] = df_disp['Jatuh_Tempo'].apply(lambda x: x.strftime('%d-%m-%Y') if pd.notnull(x) else '-')
            st.dataframe(df_disp.style.format({
                'Nominal': '{:,.0f}',
                'Pendapatan_Riil': '{:,.0f}',
                'Rate': '{:.2f}%',
                'Net_Yield': '{:.2f}%'
            }), use_container_width=True)

with tab2:
    if not df_l_raw.empty:
        st.subheader("Monitoring Penyaluran Dana (Anak Usaha)")
        st.dataframe(df_l_raw, use_container_width=True)
