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

# --- 2. ENGINE DATA (ROBUST) ---
def clean_numeric_robust(series):
    def process_val(val):
        val = str(val).strip().replace('Rp', '').replace('%', '').replace(' ', '').replace(',', '')
        if not val or val == 'nan' or val == 'None': return "0"
        return val
    # Proteksi ribuan format titik
    return pd.to_numeric(series.apply(lambda x: str(x).replace('.', '') if '.' in str(x) and len(str(x).split('.')[-1]) == 3 else x).apply(process_val), errors='coerce').fillna(0)

# Map Bulan Standar
MONTH_MAP_ID = {
    1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April', 5: 'Mei', 6: 'Juni',
    7: 'Juli', 8: 'Agustus', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
}
MONTH_MAP_REV = {
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'Mei': 5, 'Jun': 6, 'Jul': 7, 'Agu': 8, 'Sep': 9, 'Okt': 10, 'Nov': 11, 'Des': 12,
    'Januari': 1, 'Februari': 2, 'Maret': 3, 'April': 4, 'Mei': 5, 'Juni': 6, 'Juli': 7, 'Agustus': 8, 'September': 9, 'Oktober': 10, 'November': 11, 'Desember': 12
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
        if 'Bank' in df_f.columns: df_f.rename(columns={'Bank': 'Kreditur'}, inplace=True)
        
        for c in ['Nominal', 'Rate']:
            if c in df_f.columns: df_f[c] = clean_numeric_robust(df_f[c])
        for c in ['Nominal', 'Cost_of_Fund (%)', 'Lending_Rate (%)']:
            if c in df_l.columns: df_l[c] = clean_numeric_robust(df_l[c])
            
        # Helper Kalkulasi: Memecah Periode (Jan-2026 atau Januari 2026)
        def parse_date_parts(p):
            p = str(p).replace('-', ' ').strip()
            parts = p.split(' ')
            m_idx = MONTH_MAP_REV.get(parts[0], 0)
            y_val = parts[1] if len(parts) > 1 else "2026"
            return pd.Series([m_idx, y_val])

        df_f[['m_idx', 'year_val']] = df_f['Periode'].apply(parse_date_parts)
        
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

# --- 3. PROSES INPUT & SELEKSI ---
df_f_raw, df_l_raw, err = load_gsheets_data()
if err: st.error(f"GSheets Connection Error: {err}"); st.stop()

# FITUR KALENDER
st.sidebar.header("📅 Periode Analisis")
sel_date = st.sidebar.date_input("Pilih Bulan & Tahun:", value=datetime(2026, 3, 1))
s_m_idx = sel_date.month
s_y_val = str(sel_date.year)
s_m_name = MONTH_MAP_ID[s_m_idx]

# Market Data
hist_market = get_market_history()
sbn_val = st.sidebar.number_input("SBN 10Y Benchmark (Live)", value=round(float(hist_market['SBN_10Y'].iloc[-1]), 2), step=0.01)
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
    # Filter Data Bulanan (MtD)
    df_f = df_f_raw[(df_f_raw['m_idx'] == s_m_idx) & (df_f_raw['year_val'] == s_y_val)].copy()
    
    if not df_f.empty:
        df_f['Net_Yield'] = df_f['Rate'] * 0.8
        df_f['Rev_MtD'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        total_mtd = df_f['Rev_MtD'].sum()
        
        # HITUNG YTD: Filter HANYA tahun yang sama DAN bulan <= pilihan
        ytd_mask = (df_f_raw['year_val'] == s_y_val) & (df_f_raw['m_idx'] <= s_m_idx)
        df_ytd = df_f_raw[ytd_mask].copy()
        df_ytd['Rev_YtD'] = (df_ytd['Nominal'] * (df_ytd['Rate'] / 100)) / 12
        total_ytd = df_ytd['Rev_YtD'].sum()

        net_sbn = sbn_val * 0.9

        # Metrics Baris 1 (WhatsApp Style)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric(f"MtD Revenue ({s_m_name})", f"Rp {total_mtd:,.0f}")
        m3.metric(f"YtD Revenue (Jan-{s_m_name[:3]})", f"Rp {total_ytd:,.0f}")
        m4.metric("SBN Net Benchmark", f"{net_sbn:.2f}%")

        # Opportunity Baris 2
        p1, p2, p3 = st.columns(3)
        p1.metric("Potensi Tambahan (SBN)", f"Rp {(df_f['Nominal'] * (net_sbn/100) / 12).sum() - total_mtd:,.0f}")
        p2.metric(f"Potensi Tambahan ({rating})", f"Rp {(df_f['Nominal'] * (target_bond_net/100) / 12).sum() - total_mtd:,.0f}")
        p3.metric(f"Target Yield {rating} (Net)", f"{target_bond_net:.2f}%")

        st.divider()
        c_al1, c_al2 = st.columns(2)
        with c_al1:
            st.subheader("🚩 Spread Alert (vs SBN)")
            with st.container(height=180):
                df_loss = df_f[df_f['Net_Yield'] < net_sbn]
                if not df_loss.empty:
                    for _, row in df_loss.iterrows(): st.error(f"**{row['Kreditur']}** | Yield: `{row['Net_Yield']:.2f}%`")
                else: st.success("Strategi Penempatan Optimal.")
        with c_al2:
            st.subheader("⏳ Maturity Watch (H-14)")
            with st.container(height=180):
                today = datetime.now()
                df_soon = df_f[(df_f['Jatuh_Tempo'] >= today) & (df_f['Jatuh_Tempo'] <= today + timedelta(days=14))]
                if not df_soon.empty:
                    for _, row in df_soon.iterrows(): st.warning(f"**{row['Kreditur']}** | `{row['Jatuh_Tempo'].strftime('%d-%m-%Y')}`")
                else: st.info("Tidak ada jatuh tempo dekat.")

        st.divider()
        v1, v2 = st.columns([1.2, 1])
        with v1: st.plotly_chart(px.bar(df_f.groupby('Kreditur')['Rev_MtD'].sum().reset_index(), x='Kreditur', y='Rev_MtD', title="Revenue per Bank (MtD)", text_auto=',.0f', color='Kreditur'), use_container_width=True)
        with v2: st.plotly_chart(px.pie(df_f, values='Net_Yield', names='Kreditur', hole=0.5, title="Net Yield Mix"), use_container_width=True)
    else:
        st.warning(f"Data untuk {s_m_name} {s_y_val} belum tersedia di Google Sheets.")

# ==========================================
# TAB 2 & 3 (LOCKED & FIXED)
# ==========================================
with tab2:
    # Cari string periode asli untuk filter Lending
    actual_p = df_f['Periode'].iloc[0] if not df_f.empty else ""
    df_l = df_l_raw[df_l_raw['Periode'] == actual_p].copy()
    if not df_l.empty:
        l1, l2, l3 = st.columns(3)
        l1.metric("Total Cash Out Debt", f"Rp {df_l['Nominal'].sum():,.0f}")
        l2.metric("Avg. Yield Lending", f"{df_l['Lending_Rate (%)'].mean():.2f}%")
        l3.metric("Bank Kreditur Utama", df_l.groupby('Kreditur')['Nominal'].sum().idxmax())
        st.divider()
        st.plotly_chart(px.bar(df_l.groupby('Kreditur')['Nominal'].sum().reset_index().sort_values('Nominal', ascending=False), x='Kreditur', y='Nominal', text_auto=',.0f', color='Kreditur', title="Cash Out per Bank"), use_container_width=True)

with tab3:
    st.header(f"📊 ALM Strategic Intelligence - {s_m_name}")
    if not df_f.empty:
        outflow_v = df_l['Nominal'].sum() if not df_l.empty else 0
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Interest Revenue", f"Rp {total_mtd:,.0f}")
        c2.metric("Total Cash Out Debt", f"Rp {outflow_v:,.0f}")
        c3.metric("Net Flow Gap", f"Rp {total_mtd - outflow_v:,.0f}")
        c4.metric("ICR Strength", f"{(total_mtd/outflow_v if outflow_v > 0 else 0):.2f}x")
        st.divider()
        # RECO
        r1, r2 = st.columns(2)
        with r1:
            st.markdown("### 🇮🇩 Top 3 SBN Benchmark")
            st.table(pd.DataFrame({"Seri": ["FR0101", "FR0100", "FR0098"], "Yield": [f"{sbn_val:.2f}%", f"{(sbn_val-0.15):.2f}%", f"{(sbn_val+0.3):.2f}%"]}))
        with r2:
            st.markdown(f"### 🏢 Top 3 Corp Bond ({rating})")
            issuer_map = {"AAA": ["Bank Mandiri", "Telkom", "BRI"], "AA+": ["Astra", "BCA", "Indosat"], "AA": ["Adaro", "UT", "Semen Indo"], "A": ["Japfa", "Alam Sutera", "Gajah Tunggal"], "BBB": ["Lippo", "APLN", "Modernland"]}
            st.table(pd.DataFrame({"Issuer": issuer_map.get(rating, ["N/A"]*3), "Yield": [f"{(target_bond_net):.2f}%", f"{(target_bond_net-0.1):.2f}%", f"{(target_bond_net+0.1):.2f}%"]}))
        
        st.divider()
        # FIX SYNTAX & NAME ERROR
        plot_df = hist_market.copy()
        plot_df['Bareksa'] = plot_df['SBN_10Y'] * (bareksa_val / (sbn_val if sbn_val != 0 else 1))
        plot_df['PHEI'] = plot_df['SBN_10Y'] * (criec_val / (sbn_val if sbn_val != 0 else 1))
        
        fig_alm = go.Figure()
        fig_alm.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SBN_10Y'], name='SBN 10Y'))
        fig_alm.add_trace(go.Scatter(x=plot_df.index, y=plot_df['Bareksa'], name='Bareksa MM', line=dict(dash='dot')))
        fig_alm.add_trace(go.Scatter(x=plot_df.index, y=plot_df['PHEI'], name='PHEI Bond Index', line=dict(width=3)))
        st.plotly_chart(fig_alm, use_container_width=True)
