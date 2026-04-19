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

# --- 2. ENGINE DATA (DIPERKUAT) ---
def clean_numeric_robust(series):
    def process_val(val):
        val = str(val).strip().replace('Rp', '').replace('%', '').replace(' ', '').replace(',', '')
        if not val or val == 'nan' or val == 'None': return "0"
        return val
    return pd.to_numeric(series.apply(lambda x: str(x).replace('.', '') if '.' in str(x) and len(str(x).split('.')[-1]) == 3 else x).apply(process_val), errors='coerce').fillna(0)

# Map bulan standar untuk kalkulasi YtD
MONTH_MAP = {
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
        
        for c in ['Nominal', 'Rate']:
            if c in df_f.columns: df_f[c] = clean_numeric_robust(df_f[c])
        for c in ['Nominal', 'Cost_of_Fund (%)', 'Lending_Rate (%)']:
            if c in df_l.columns: df_l[c] = clean_numeric_robust(df_l[c])
            
        for df in [df_f, df_l]:
            if 'Jatuh_Tempo' in df.columns: 
                df['Jatuh_Tempo'] = pd.to_datetime(df['Jatuh_Tempo'], dayfirst=True, errors='coerce')
        
        # Tambahkan kolom helper urutan bulan & tahun dengan proteksi error
        def get_month_num(p):
            p = str(p).strip()
            return MONTH_MAP.get(p.split(' ')[0], 0) if ' ' in p else 0

        def get_year_val(p):
            p = str(p).strip()
            return p.split(' ')[1] if ' ' in p else "2026"

        df_f['month_idx'] = df_f['Periode'].apply(get_month_num)
        df_f['year_idx'] = df_f['Periode'].apply(get_year_val)
        
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

# --- 3. PROSES DATA AWAL ---
df_f_raw, df_l_raw, err = load_gsheets_data()
if err: st.error(f"Gagal memuat data: {err}"); st.stop()

# Definisi data pasar di awal untuk menghindari NameError
raw_market_data = get_market_history()

# Sorting bulan yang lebih aman (Bulletproof Sort)
def safe_sort_key(p):
    p = str(p).strip()
    if ' ' not in p: return (0, 0)
    parts = p.split(' ')
    return (int(parts[1]) if parts[1].isdigit() else 0, MONTH_MAP.get(parts[0], 0))

all_months = sorted(df_f_raw['Periode'].unique().tolist(), key=safe_sort_key, reverse=True)
sel_month = st.sidebar.selectbox("Pilih Periode Analisis:", all_months)

# Metadata pilihan user
sel_month_name = str(sel_month).split(' ')[0]
sel_year = str(sel_month).split(' ')[1] if ' ' in str(sel_month) else "2026"
sel_idx = MONTH_MAP.get(sel_month_name, 0)

# Sidebar Market Inputs
st.sidebar.header("⚙️ Market Intelligence")
sbn_val = st.sidebar.number_input("SBN 10Y Benchmark (Live)", value=round(float(raw_market_data['SBN_10Y'].iloc[-1]), 2), step=0.01)
bareksa_val = st.sidebar.number_input("Bareksa (Money Market %)", value=4.75, step=0.01)
criec_val = st.sidebar.number_input("PHEI CRIEC Index (%)", value=7.20, step=0.01)

rating = st.sidebar.selectbox("Pilih Rating Reinvestasi:", ["AAA", "AA+", "AA", "A", "BBB"])
spread_map = {"AAA": 80, "AA+": 110, "AA": 140, "A": 260, "BBB": 480}
target_bond_net = (sbn_val + (spread_map[rating]/100)) * 0.9

# --- 4. DASHBOARD UI ---
st.title(f"🚢 ASDP Treasury & ALM Master Command Center")
tab1, tab2, tab3 = st.tabs(["💰 Modul 1: Funding", "📈 Modul 2: Lending", "📊 Modul 3: ALM Resume"])

# ==========================================
# TAB 1: FUNDING (YTD ACCURATE)
# ==========================================
with tab1:
    df_f = df_f_raw[df_f_raw['Periode'] == sel_month].copy()
    
    if not df_f.empty:
        df_f['Net_Yield'] = df_f['Rate'] * 0.8
        df_f['Pendapatan_Riil'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        mtd_rev = df_f['Pendapatan_Riil'].sum()
        
        # PERHITUNGAN YTD YANG AKURAT
        # Hanya ambil data di tahun yang sama dan bulan yang lebih kecil/sama dengan pilihan
        ytd_mask = (df_f_raw['year_idx'] == sel_year) & (df_f_raw['month_idx'] <= sel_idx)
        df_ytd_data = df_f_raw[ytd_mask].copy()
        df_ytd_data['Rev_YtD'] = (df_ytd_data['Nominal'] * (df_ytd_data['Rate'] / 100)) / 12
        ytd_rev = df_ytd_data['Rev_YtD'].sum()

        net_sbn = sbn_val * 0.9

        # Metrics baris 1
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric(f"MtD Revenue ({sel_month_name})", f"Rp {mtd_rev:,.0f}")
        m3.metric(f"YtD Revenue (Jan-{sel_month_name})", f"Rp {ytd_rev:,.0f}")
        m4.metric("SBN Net Benchmark", f"{net_sbn:.2f}%")

        # Opportunity metrics
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
                else: st.success("Strategi Penempatan Optimal.")
        with c_al2:
            st.subheader("⏳ Maturity Watch (H-14)")
            with st.container(height=180):
                today = datetime.now()
                df_soon = df_f[(df_f['Jatuh_Tempo'] >= today) & (df_f['Jatuh_Tempo'] <= today + timedelta(days=14))]
                if not df_soon.empty:
                    for _, row in df_soon.iterrows(): st.warning(f"**{row['Bank']}** | `{row['Jatuh_Tempo'].strftime('%d-%m-%Y')}`")
                else: st.info("Tidak ada jatuh tempo dekat.")

        st.divider()
        v1, v2 = st.columns([1.2, 1])
        with v1: 
            fig_rev = px.bar(df_f.groupby('Bank')['Pendapatan_Riil'].sum().reset_index(), 
                             x='Bank', y='Pendapatan_Riil', title="Revenue per Bank (MtD)", text_auto=',.0f', color='Bank')
            st.plotly_chart(fig_rev, use_container_width=True)
        with v2: st.plotly_chart(px.pie(df_f, values='Net_Yield', names='Bank', hole=0.5, title="Net Yield Mix"), use_container_width=True)

# ==========================================
# TAB 2: LENDING (LOCKED)
# ==========================================
with tab2:
    df_l = df_l_raw[df_l_raw['Periode'] == sel_month].copy()
    if not df_l.empty:
        l1, l2, l3 = st.columns(3)
        l1.metric("Total Cash Out Debt", f"Rp {df_l['Nominal'].sum():,.0f}")
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
# TAB 3: ALM RESUME (STABLE PLOTTING)
# ==========================================
with tab3:
    st.header(f"📊 ALM Strategic Intelligence - {sel_month}")
    if not df_f.empty and not df_l.empty:
        inflow_b = df_f['Pendapatan_Riil'].sum()
        outflow_val = df_l_raw[df_l_raw['Periode'] == sel_month]['Nominal'].sum()
        icr = inflow_b / outflow_val if outflow_val > 0 else 0
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Interest Revenue", f"Rp {inflow_b:,.0f}")
        c2.metric("Total Cash Out Debt", f"Rp {outflow_val:,.0f}")
        c3.metric("Net Interest Margin", f"Rp {inflow_b - outflow_val:,.0f}")
        c4.metric("ICR Strength", f"{icr:.2f}x")
        st.divider()
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
        
        # Plotting stabil menggunakan raw_market_data yang sudah didefinisikan di awal
        plot_m = raw_market_data.copy()
        plot_m['Bareksa'] = plot_m['SBN_10Y'] * (bareksa_val / (sbn_val if sbn_val != 0 else 1))
        plot_m['PHEI_Bond'] = plot_m['SBN_10Y'] * (criec_val / (sbn_val if sbn_val != 0 else 1))
        fig_h = go.Figure()
        fig_h.add_trace(go.Scatter(x=plot_m.index, y=plot_m['SBN_10Y'], name='SBN 10Y'))
        fig_h.add_trace(go.Scatter(x=plot_m.index, y=plot_m['Bareksa'], name='Bareksa MM', line=dict(dash='dot')))
        fig_h.add_trace(go.Scatter(x=plot_m.index, y=plot_m['PHEI_Bond'], name='PHEI Bond Index', line=dict(width=3)))
        st.plotly_chart(fig_h, use_container_width=True)
