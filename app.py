import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import os
import numpy as np
from datetime import datetime, timedelta

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="ASDP ALM Strategic Command", layout="wide", page_icon="🚢")

# --- 2. ENGINE DATA ---
def clean_numeric_robust(series):
    def process_val(val):
        val = str(val).strip().replace('Rp', '').replace('%', '').replace(' ', '').replace(',', '')
        if not val or val == 'nan' or val == 'None': return "0"
        return val
    return pd.to_numeric(series.apply(lambda x: str(x).replace('.', '') if '.' in str(x) and len(str(x).split('.')[-1]) == 3 else x).apply(process_val), errors='coerce').fillna(0)

# Helper untuk urutan bulan YtD
month_map = {
    'Januari': 1, 'Februari': 2, 'Maret': 3, 'April': 4, 'Mei': 5, 'Juni': 6,
    'Juli': 7, 'Agustus': 8, 'September': 9, 'Oktober': 10, 'November': 11, 'Desember': 12
}

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
        
        # Cleaning angka di dataframe mentah
        for c in ['Nominal', 'Rate']:
            if c in df_f.columns: df_f[c] = clean_numeric_robust(df_f[c])
        for c in ['Nominal', 'Cost_of_Fund (%)', 'Lending_Rate (%)']:
            if c in df_l.columns: df_l[c] = clean_numeric_robust(df_l[c])
            
        for df in [df_f, df_l]:
            if 'Jatuh_Tempo' in df.columns: 
                df['Jatuh_Tempo'] = pd.to_datetime(df['Jatuh_Tempo'], dayfirst=True, errors='coerce')
        return df_f, df_l, None
    except Exception as e: return pd.DataFrame(), pd.DataFrame(), str(e)

@st.cache_data(ttl=3600)
def get_market_history():
    try:
        data = yf.Ticker("ID10Y=F").history(period="6mo")
        if not data.empty: return data[['Close']].rename(columns={'Close': 'SBN_10Y'}).copy()
    except: pass
    dates = pd.date_range(end=datetime.now(), periods=180)
    return pd.DataFrame({'SBN_10Y': np.linspace(6.5, 6.8, 180)}, index=dates).copy()

# --- 3. SIDEBAR ---
logo_path = "ferry.png"
if os.path.exists(logo_path): st.sidebar.image(logo_path, use_container_width=True)
st.sidebar.markdown("---")

df_f_raw, df_l_raw, err = load_gsheets_data()
if err: st.stop()

all_months = sorted(list(set(df_f_raw['Periode'].unique()) | set(df_l_raw['Periode'].unique())), reverse=True)
sel_month = st.sidebar.selectbox("Pilih Periode Analisis:", all_months)

# LOGIKA YTD: Ambil bulan dan tahun dari periode terpilih
try:
    sel_month_name = sel_month.split(' ')[0]
    sel_year = sel_month.split(' ')[1]
    sel_month_num = month_map.get(sel_month_name, 0)
except:
    sel_month_num, sel_year = 0, "2026"

# Filter data bulanan (MtD)
df_f = df_f_raw[df_f_raw['Periode'] == sel_month].copy()
df_l = df_l_raw[df_l_raw['Periode'] == sel_month].copy()

# Market Intelligence
hist_data = get_market_history()
sbn_val = st.sidebar.number_input("SBN 10Y Benchmark (Live)", value=round(float(hist_data['SBN_10Y'].iloc[-1]), 2), step=0.01)
bareksa_val = st.sidebar.number_input("Bareksa (Money Market %)", value=4.75, step=0.01)
criec_val = st.sidebar.number_input("PHEI CRIEC Index (%)", value=7.20, step=0.01)

rating = st.sidebar.selectbox("Pilih Rating Reinvestasi:", ["AAA", "AA+", "AA", "A", "BBB"])
spread_map = {"AAA": 80, "AA+": 110, "AA": 140, "A": 260, "BBB": 480}
target_bond_net = (sbn_val + (spread_map[rating]/100)) * 0.9

# --- 4. DASHBOARD UI ---
st.title(f"🚢 ASDP Treasury & ALM Master Command Center")
tab1, tab2, tab3 = st.tabs(["💰 Modul 1: Funding", "📈 Modul 2: Lending", "📊 Modul 3: ALM Resume"])

# ==========================================
# TAB 1: FUNDING (LAYOUT WHATSAPP + YTD)
# ==========================================
with tab1:
    if not df_f.empty:
        # Perhitungan MtD
        df_f['Net_Yield'] = df_f['Rate'] * 0.8
        df_f['Pendapatan_Riil'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        mtd_rev = df_f['Pendapatan_Riil'].sum()
        
        # PERHITUNGAN YTD (AKUMULASI)
        df_f_ytd = df_f_raw[df_f_raw['Periode'].str.contains(sel_year)].copy()
        df_f_ytd['month_num'] = df_f_ytd['Periode'].apply(lambda x: month_map.get(x.split(' ')[0], 0))
        df_f_ytd = df_f_ytd[df_f_ytd['month_num'] <= sel_month_num]
        df_f_ytd['Pendapatan_YtD'] = (df_f_ytd['Nominal'] * (df_f_ytd['Rate'] / 100)) / 12
        ytd_rev_total = df_f_ytd['Pendapatan_YtD'].sum()

        net_sbn = sbn_val * 0.9

        # BARIS 1: METRICS UTAMA (MtD & YtD)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric(f"MtD Revenue ({sel_month_name})", f"Rp {mtd_rev:,.0f}")
        m3.metric(f"YtD Revenue (Jan - {sel_month_name})", f"Rp {ytd_rev_total:,.0f}")
        m4.metric("SBN Net Benchmark", f"{net_sbn:.2f}%")

        # BARIS 2: OPPORTUNITY GAIN
        p1, p2, p3 = st.columns(3)
        p1.metric("Potensi Tambahan (SBN)", f"Rp {(df_f['Nominal'] * (net_sbn/100) / 12).sum() - mtd_rev:,.0f}")
        p2.metric(f"Potensi Tambahan ({rating})", f"Rp {(df_f['Nominal'] * (target_bond_net/100) / 12).sum() - mtd_rev:,.0f}")
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
        with v1: 
            fig_rev = px.bar(df_f.groupby('Bank')['Pendapatan_Riil'].sum().reset_index(), 
                             x='Bank', y='Pendapatan_Riil', title="MtD Revenue per Bank", text_auto=',.0f', color='Bank')
            st.plotly_chart(fig_rev, use_container_width=True)
        with v2: st.plotly_chart(px.pie(df_f, values='Net_Yield', names='Bank', hole=0.5, title="Net Yield Mix"), use_container_width=True)

# ==========================================
# TAB 2: LENDING (LOCKED)
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
# TAB 3: ALM RESUME (LOCKED)
# ==========================================
with tab3:
    st.header(f"📊 ALM Strategic Intelligence - {sel_month}")
    if not df_f.empty and not df_l.empty:
        inflow_b = df_f['Pendapatan_Riil'].sum()
        outflow_val = df_l['Nominal'].sum()
        icr = inflow_b / outflow_val if outflow_val > 0 else 0
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Interest Revenue", f"Rp {inflow_b:,.0f}")
        c2.metric("Total Cash Out Debt", f"Rp {outflow_val:,.0f}")
        c3.metric("Net Interest Margin", f"Rp {inflow_b - outflow_val:,.0f}")
        c4.metric("ICR Strength", f"{icr:.2f}x")
        st.divider()
        # RECOMENDATIONS SECTION
        rec1, rec2 = st.columns(2)
        with rec1:
            st.markdown("### 🇮🇩 Top 3 SBN Benchmark")
            sbn_data = {"Seri": ["FR0101 (10Y)", "FR0100 (9Y)", "FR0098 (20Y)"], "Indikasi Yield": [f"{sbn_val:.2f}%", f"{(sbn_val-0.15):.2f}%", f"{(sbn_val+0.35):.2f}%"]}
            st.table(pd.DataFrame(sbn_data))
        with rec2:
            st.markdown(f"### 🏢 Top 3 Corp Bond/Sukuk ({rating})")
            issuer_map = {
                "AAA": {"Issuer": ["Bank Mandiri", "Telkom Indonesia", "Bank BRI"], "Inst": ["Obligasi", "Sukuk", "Obligasi"]},
                "AA+": {"Issuer": ["Astra Intl", "BCA", "Indosat"], "Inst": ["Obligasi", "Obligasi", "Sukuk"]},
                "AA": {"Issuer": ["Adaro Energy", "United Tractors", "Semen Indo"], "Inst": ["Obligasi", "Obligasi", "Sukuk"]},
                "A": {"Issuer": ["Japfa Comfeed", "Gajah Tunggal", "Alam Sutera"], "Inst": ["Obligasi", "Obligasi", "MTN"]},
                "BBB": {"Issuer": ["Lippo Karawaci", "Agung Podomoro", "Modernland"], "Inst": ["High Yield", "Obligasi", "MTN"]}
            }
            picks = issuer_map.get(rating, issuer_map["AAA"])
            corp_data = {"Issuer": picks["Issuer"], "Instrumen": picks["Inst"], "Yield": [f"{(sbn_val + spread_map[rating]/100):.2f}%", f"{(sbn_val + spread_map[rating]/100 - 0.1):.2f}%", f"{(sbn_val + spread_map[rating]/100 + 0.15):.2f}%"]}
            st.table(pd.DataFrame(corp_data))
        st.divider()
        plot_market = raw_market_data.copy()
        plot_market['Bareksa'] = plot_market['SBN_10Y'] * (bareksa_val / (sbn_val if sbn_val != 0 else 1))
        plot_market['PHEI_Bond'] = plot_market['SBN_10Y'] * (criec_val / (sbn_val if sbn_val != 0 else 1))
        fig_h = go.Figure()
        fig_h.add_trace(go.Scatter(x=plot_market.index, y=plot_market['SBN_10Y'], name='SBN 10Y'))
        fig_h.add_trace(go.Scatter(x=plot_market.index, y=plot_market['Bareksa'], name='Bareksa MM', line=dict(dash='dot')))
        fig_h.add_trace(go.Scatter(x=plot_market.index, y=plot_market['PHEI_Bond'], name='PHEI Bond Index', line=dict(width=3)))
        st.plotly_chart(fig_h, use_container_width=True)
