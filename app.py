import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import os
import numpy as np
from datetime import datetime, timedelta

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="ASDP ALM Strategic Dashboard", layout="wide", page_icon="🚢")

# --- 2. ENGINE DATA (ANTI-ERROR) ---
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
        if 'Rate (%)' in df_f.columns: df_f.rename(columns={'Rate (%)': 'Rate'}, inplace=True)
        if 'Bank' in df_l.columns: df_l.rename(columns={'Bank': 'Kreditur'}, inplace=True)
        for c in ['Nominal', 'Rate']:
            if c in df_f.columns: df_f[c] = clean_numeric_robust(df_f[c])
        cols_l = ['Nominal', 'Cost_of_Fund (%)', 'Lending_Rate (%)']
        for c in cols_l:
            if c in df_l.columns: df_l[c] = clean_numeric_robust(df_l[c])
        for df in [df_f, df_l]:
            if 'Jatuh_Tempo' in df.columns: df['Jatuh_Tempo'] = pd.to_datetime(df['Jatuh_Tempo'], dayfirst=True, errors='coerce')
        return df_f, df_l, None
    except Exception as e: return pd.DataFrame(), pd.DataFrame(), str(e)

@st.cache_data(ttl=3600)
def get_market_history():
    try:
        data = yf.Ticker("ID10Y=F").history(period="6mo")
        if not data.empty: return data[['Close']].rename(columns={'Close': 'SBN_10Y'})
    except: pass
    dates = pd.date_range(end=datetime.now(), periods=180)
    return pd.DataFrame({'SBN_10Y': np.linspace(6.5, 6.8, 180)}, index=dates)

# --- 3. SIDEBAR ---
logo_path = "ferry.png"
if os.path.exists(logo_path): st.sidebar.image(logo_path, use_container_width=True)
st.sidebar.markdown("---")

df_f_raw, df_l_raw, err = load_gsheets_data()
if err: st.stop()
all_months = sorted(list(set(df_f_raw['Periode'].unique()) | set(df_l_raw['Periode'].unique())), reverse=True)
sel_month = st.sidebar.selectbox("Pilih Periode Analisis:", all_months)
df_f = df_f_raw[df_f_raw['Periode'] == sel_month].copy()
df_l = df_l_raw[df_l_raw['Periode'] == sel_month].copy()

st.sidebar.header("⚙️ Market Intelligence")
hist_data = get_market_history()
sbn_val = st.sidebar.number_input("SBN 10Y Benchmark (Live)", value=round(float(hist_data['SBN_10Y'].iloc[-1]), 2), step=0.01)

st.sidebar.markdown("---")
st.sidebar.header("📊 Market Benchmarks")
bareksa_val = st.sidebar.number_input("Bareksa (Money Market %)", value=4.75, step=0.01)
criec_val = st.sidebar.number_input("CRIEC (Corp Bond Index %)", value=7.20, step=0.01)

# TOMBOL LINK DI SIDEBAR
col_s1, col_s2 = st.sidebar.columns(2)
with col_s1: st.link_button("🌐 Bareksa", "https://www.bareksa.com", use_container_width=True)
with col_s2: st.link_button("📉 CRIEC", "https://www.phei.co.id", use_container_width=True)

rating = st.sidebar.selectbox("Rating Reinvestasi:", ["AAA", "AA+", "AA", "A", "BBB"])
spread_map = {"AAA": 80, "AA+": 110, "AA": 140, "A": 260, "BBB": 480}
target_bond_net = (sbn_val + (spread_map[rating]/100)) * 0.9

# --- 4. DASHBOARD UI ---
st.title(f"🚢 ASDP Treasury & ALM Command Center")
tab1, tab2, tab3 = st.tabs(["💰 Modul 1: Funding", "📈 Modul 2: Lending", "📊 Modul 3: ALM Resume"])

# ==========================================
# TAB 1: FUNDING (TETAP SESUAI WHATSAPP)
# ==========================================
with tab1:
    if not df_f.empty:
        df_f['Net_Yield'] = df_f['Rate'] * 0.8
        df_f['Pendapatan_Riil'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        net_sbn = sbn_val * 0.9
        total_rev = df_f['Pendapatan_Riil'].sum()

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric(f"Total Revenue ({sel_month})", f"Rp {total_rev:,.0f}")
        m3.metric("SBN Net Benchmark", f"{net_sbn:.2f}%")

        p1, p2, p3 = st.columns(3)
        p1.metric("Potensi Tambahan (SBN)", f"Rp {(df_f['Nominal'] * (net_sbn/100) / 12).sum() - total_rev:,.0f}")
        p2.metric(f"Potensi Tambahan ({rating})", f"Rp {(df_f['Nominal'] * (target_bond_net/100) / 12).sum() - total_rev:,.0f}")
        p3.metric(f"Target Yield {rating} (Net)", f"{target_bond_net:.2f}%")

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
        with v1: st.plotly_chart(px.bar(df_f.groupby('Bank')['Pendapatan_Riil'].sum().reset_index(), x='Bank', y='Pendapatan_Riil', title="Revenue per Bank", text_auto=',.0f', color='Bank'), use_container_width=True)
        with v2: st.plotly_chart(px.pie(df_f, values='Net_Yield', names='Bank', hole=0.5, title="Net Yield Mix"), use_container_width=True)

# ==========================================
# TAB 2: LENDING (TETAP)
# ==========================================
with tab2:
    if not df_l.empty:
        total_cash_out_val = df_l['Nominal'].sum()
        l1, l2, l3 = st.columns(3)
        l1.metric("Total Cash Out Debt", f"Rp {total_cash_out_val:,.0f}")
        l2.metric("Avg. Yield Lending", f"{df_l['Lending_Rate (%)'].mean():.2f}%" if 'Lending_Rate (%)' in df_l.columns else "N/A")
        l3.metric("Bank Kreditur Utama", df_l.groupby('Kreditur')['Nominal'].sum().idxmax())
        st.divider()
        with st.container(height=180):
            today = datetime.now()
            df_pay = df_l[(df_l['Jatuh_Tempo'] >= today) & (df_l['Jatuh_Tempo'] <= today + timedelta(days=14))]
            if not df_pay.empty:
                for _, row in df_pay.iterrows(): st.error(f"**{row['Kreditur']}** | Rp {row['Nominal']:,.0f} | `{row['Jatuh_Tempo'].strftime('%d-%m-%Y')}`")
            else: st.success("Jadwal pembayaran aman.")
        st.plotly_chart(px.bar(df_l.groupby('Kreditur')['Nominal'].sum().reset_index().sort_values('Nominal', ascending=False), x='Kreditur', y='Nominal', text_auto=',.0f', color='Kreditur', title="Cash Out per Bank"), use_container_width=True)

# ==========================================
# TAB 3: ALM RESUME (WITH ACTION BUTTONS)
# ==========================================
with tab3:
    st.header(f"📊 ALM Strategic & Market Trends - {sel_month}")
    if not df_f.empty and not df_l.empty:
        inflow_b = df_f['Pendapatan_Riil'].sum()
        outflow_val = df_l['Nominal'].sum()
        icr = inflow_b / outflow_val if outflow_val > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Interest Revenue", f"Rp {inflow_b:,.0f}")
        c2.metric("Total Cash Out Debt", f"Rp {outflow_val:,.0f}")
        c3.metric("Net Flow Position", f"Rp {inflow_b - outflow_val:,.0f}")
        c4.metric("ICR Ratio", f"{icr:.2f}x")

        st.divider()

        # CHART TREND HISTORIS
        st.subheader("📈 Market Historical Trend (Benchmark Mapping)")
        hist_data['Bareksa'] = hist_data['SBN_10Y'] * (bareksa_val / sbn_val)
        hist_data['CRIEC'] = hist_data['SBN_10Y'] * (criec_val / sbn_val)
        fig_hist = go.Figure()
        fig_hist.add_trace(go.Scatter(x=hist_data.index, y=hist_data['SBN_10Y'], name='SBN 10Y (Anchor)', line=dict(color='blue', width=2)))
        fig_hist.add_trace(go.Scatter(x=hist_data.index, y=hist_data['Bareksa'], name='Bareksa Index', line=dict(color='green', dash='dot')))
        fig_hist.add_trace(go.Scatter(x=hist_data.index, y=hist_data['CRIEC'], name='CRIEC Corp Bond', line=dict(color='orange', width=3)))
        st.plotly_chart(fig_hist, use_container_width=True)

        # BARIS ANALISIS & TOMBOL AKSI
        col_an1, col_an2 = st.columns(2)
        with col_an1:
            st.subheader("📝 ALM Analysis")
            with st.container(border=True):
                st.write(f"1. Yield Deposito {df_f['Rate'].mean():.2f}% vs Bareksa {bareksa_val}%.")
                st.write(f"2. Gap Reinvestasi CRIEC: **{abs(criec_val - df_f['Net_Yield'].mean()):.2f}%**.")
                st.markdown("---")
                # TOMBOL LINK DI DALAM ANALISIS
                st.markdown("**Cek Data Pasar Real-Time:**")
                btn1, btn2 = st.columns(2)
                btn1.link_button("🚀 Buka Bareksa", "https://www.bareksa.com")
                btn2.link_button("🏢 Buka CRIEC (PHEI)", "https://www.phei.co.id")
        
        with col_an2:
            st.subheader("🛡️ Risk Assessment")
            with st.container(border=True):
                if icr < 1.0: st.error("🚨 **CRITICAL**: Outflow > Inflow!")
                elif icr < 2.0: st.warning("⚠️ **WATCHLIST**: Monitor cashflow ketat.")
                else: st.success("🛡️ **SAFE**: Posisi likuiditas kuat.")
