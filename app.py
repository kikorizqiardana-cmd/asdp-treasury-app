import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta

# --- 1. CONFIG HALAMAN ---
st.set_page_config(page_title="ASDP Revenue Performance", layout="wide", page_icon="🚢")

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
current_sbn = st.sidebar.number_input(f"SBN 10Y Benchmark ({sbn_source})", value=sbn_val, step=0.01)

st.sidebar.markdown("---")
st.sidebar.header("🏢 Bond/Sukuk Simulator")
rating = st.sidebar.selectbox("Pilih Target Rating Reinvestasi:", ["AAA", "AA+", "AA", "A", "BBB"])
spread_map = {"AAA": 80, "AA+": 110, "AA": 140, "A": 260, "BBB": 480}
sel_spread = st.sidebar.slider(f"Spread {rating} (bps)", 0, 600, spread_map[rating])
target_bond_gross = current_sbn + (sel_spread / 100)

# --- 4. DASHBOARD UI ---
st.title(f"🚢 ASDP Revenue & Yield Strategic Dashboard")
tab1, tab2 = st.tabs(["💰 Performance per Bank", "📈 Lending Monitor"])

with tab1:
    if not df_f.empty:
        # Perhitungan
        df_f['Net_Yield'] = df_f['Rate'] * 0.8
        net_sbn = current_sbn * 0.9
        net_bond = target_bond_gross * 0.9
        df_f['Pendapatan_Riil'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        
        # 1. METRICS
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric(f"Total Revenue ({sel_month})", f"Rp {df_f['Pendapatan_Riil'].sum():,.0f}")
        m3.metric(f"Benchmark SBN Net", f"{net_sbn:.2f}%")

        st.divider()

        # 2. SCROLLABLE ALERTS
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            st.subheader("🚩 Underperform Alerts (vs SBN)")
            with st.container(height=150):
                df_loss = df_f[df_f['Net_Yield'] < net_sbn]
                if not df_loss.empty:
                    for _, row in df_loss.iterrows():
                        st.error(f"**{row['Bank']}** | Yield Net: `{row['Net_Yield']:.2f}%` | Revenue: `Rp {row['Pendapatan_Riil']:,.0f}`")
                else: st.success("Seluruh penempatan optimal.")

        with col_a2:
            st.subheader("⏳ Maturity Watch (H-14)")
            with st.container(height=150):
                today = datetime.now()
                df_soon = df_f[(df_f['Jatuh_Tempo'] >= today) & (df_f['Jatuh_Tempo'] <= today + timedelta(days=14))]
                if not df_soon.empty:
                    for _, row in df_soon.iterrows():
                        st.warning(f"**{row['Bank']}** | `{row['Jatuh_Tempo'].strftime('%d-%m-%Y')}` | Rp {row['Nominal']:,.0f}")
                else: st.info("Tidak ada jatuh tempo dalam 14 hari.")

        st.divider()

        # 3. PERFORMANCE CHARTS (RUPIAH + YIELD)
        st.subheader("📊 Performance per Bank: Revenue & Strategic Yield")
        v1, v2 = st.columns([1, 1])
        
        # Data Agregat per Bank
        df_bank_perf = df_f.groupby('Bank').agg({
            'Pendapatan_Riil': 'sum',
            'Net_Yield': 'mean'
        }).reset_index().sort_values('Pendapatan_Riil', ascending=False)

        with v1:
            # Grafik 1: Total Revenue per Bank (RUPIAH)
            fig_rev = px.bar(
                df_bank_perf, 
                x='Bank', 
                y='Pendapatan_Riil',
                title="Total Pendapatan Bunga per Bank (IDR)",
                text_auto=',.0f',
                color='Pendapatan_Riil',
                color_continuous_scale='Greens'
            )
            fig_rev.update_traces(textposition='outside')
            fig_rev.update_layout(showlegend=False, yaxis_title="Rupiah (Bunga)")
            st.plotly_chart(fig_rev, use_container_width=True)
            
        with v2:
            # Grafik 2: Strategic Yield per Bank + Garis Benchmark
            fig_yield = go.Figure()
            fig_yield.add_trace(go.Bar(
                x=df_bank_perf['Bank'], 
                y=df_bank_perf['Net_Yield'],
                name='Avg Net Yield',
                marker_color='#004d99',
                text=[f"{val:.2f}%" for val in df_bank_perf['Net_Yield']],
                textposition='auto'
            ))
            fig_yield.add_hline(y=net_sbn, line_dash="dash", line_color="orange", 
                                annotation_text=f"SBN Net ({net_sbn:.2f}%)")
            fig_yield.add_hline(y=net_bond, line_dash="dot", line_color="green", 
                                annotation_text=f"{rating} Bond Net ({net_bond:.2f}%)")
            fig_yield.update_layout(title="Strategic Yield Analysis vs Market", yaxis_title="Net Yield (%)")
            st.plotly_chart(fig_yield, use_container_width=True)

        # 4. TABEL DETAIL
        with st.expander("📑 Detail Inventori & Spread Analysis"):
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
        st.subheader("Lending & ALM Summary")
        st.dataframe(df_l_raw, use_container_width=True)
