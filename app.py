import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta

# --- 1. CONFIG HALAMAN ---
st.set_page_config(page_title="ASDP ALM Strategy", layout="wide", page_icon="🚢")

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

# DATA LOADING
df_f_raw, df_l_raw, err = load_gsheets_data()
if err: 
    st.sidebar.error(f"API Error: {err}")
    st.stop()
else:
    all_months = sorted(df_f_raw['Periode'].unique().tolist(), reverse=True)
    sel_month = st.sidebar.selectbox("Pilih Periode Analisis:", all_months)
    df_f = df_f_raw[df_f_raw['Periode'] == sel_month].copy()

# MARKET INTEL
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
st.title(f"🚢 ASDP Treasury Strategic Dashboard")
tab1, tab2 = st.tabs(["💰 Funding & Reinvestment Analysis", "📈 Lending Monitor"])

with tab1:
    if not df_f.empty:
        # Perhitungan Pajak & Revenue
        df_f['Net_Yield'] = df_f['Rate'] * 0.8  # Depo 20% Tax
        net_sbn = current_sbn * 0.9           # SBN 10% Tax
        net_bond = target_bond_gross * 0.9    # Bond 10% Tax
        df_f['Pendapatan_Riil'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        
        # 1. METRICS ATAS
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric(f"Net Yield SBN", f"{net_sbn:.2f}%")
        m3.metric(f"Net Yield Bond {rating}", f"{net_bond:.2f}%", delta=f"{(net_bond - net_sbn):.2f}% vs SBN")

        st.divider()

        # 2. ALERTS (SCROLLABLE)
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            st.subheader("🚩 Underperform Alerts")
            with st.container(height=180):
                df_loss = df_f[df_f['Net_Yield'] < net_sbn]
                if not df_loss.empty:
                    for _, row in df_loss.iterrows():
                        st.error(f"**{row['Bank']}** | Yield Net: {row['Net_Yield']:.2f}% (Bawah SBN)")
                else: st.success("Seluruh penempatan optimal vs SBN.")

        with col_a2:
            st.subheader("⏳ Maturity Watch (H-7)")
            with st.container(height=180):
                today = datetime.now()
                df_soon = df_f[(df_f['Jatuh_Tempo'] >= today) & (df_f['Jatuh_Tempo'] <= today + timedelta(days=7))]
                if not df_soon.empty:
                    for _, row in df_soon.iterrows():
                        st.warning(f"**{row['Bank']}** | `{row['Jatuh_Tempo'].strftime('%d-%m-%Y')}` | Rp {row['Nominal']:,.0f}")
                else: st.info("Tidak ada jatuh tempo dalam 7 hari.")

        st.divider()

        # 3. STRATEGIC CHARTS (AGREGAT PER BANK)
        st.subheader("📊 Strategic Yield & Revenue Aggregation")
        v1, v2 = st.columns([2, 1])
        
        with v1:
            # Grafik Net Yield Agregat per Bank + Benchmark Lines
            # Kita hitung rata-rata yield tertimbang (weighted average) atau simpel per bank
            df_bank_yield = df_f.groupby('Bank')['Net_Yield'].mean().reset_index().sort_values('Net_Yield')
            
            fig_yield = go.Figure()
            fig_yield.add_trace(go.Bar(
                x=df_bank_yield['Bank'], 
                y=df_bank_yield['Net_Yield'],
                name='Avg Net Yield per Bank',
                marker_color='#004d99',
                text=[f"{val:.2f}%" for val in df_bank_yield['Net_Yield']],
                textposition='auto'
            ))
            
            # Tambahkan Garis Benchmark
            fig_yield.add_hline(y=net_sbn, line_dash="dash", line_color="orange", 
                                annotation_text=f"SBN Net ({net_sbn:.2f}%)", annotation_position="top left")
            fig_yield.add_hline(y=net_bond, line_dash="dot", line_color="green", 
                                annotation_text=f"{rating} Bond Net ({net_bond:.2f}%)", annotation_position="top right")
            
            fig_yield.update_layout(title="Rata-rata Net Yield per Bank vs Market Benchmark", yaxis_title="Net Yield (%)")
            st.plotly_chart(fig_yield, use_container_width=True)
            
        with v2:
            # Grafik Total Revenue per Bank
            df_bank_rev = df_f.groupby('Bank')['Pendapatan_Riil'].sum().reset_index()
            fig_rev = px.pie(df_bank_rev, values='Pendapatan_Riil', names='Bank', hole=0.4,
                             title="Kontribusi Revenue per Bank (%)")
            st.plotly_chart(fig_rev, use_container_width=True)

        # 4. TABEL DETAIL
        with st.expander("📑 Detail Tabel Inventori & Spread Analysis"):
            df_disp = df_f.copy()
            df_disp['Jatuh_Tempo'] = df_disp['Jatuh_Tempo'].apply(lambda x: x.strftime('%d-%m-%Y') if pd.notnull(x) else '-')
            st.dataframe(df_disp, use_container_width=True)

with tab2:
    if not df_l_raw.empty:
        st.subheader("Lending & ALM Summary")
        st.dataframe(df_l_raw, use_container_width=True)
