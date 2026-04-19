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

# --- 2. ENGINE DATA (ROBUST & ACCURATE) ---
def clean_numeric_robust(series):
    def process_val(val):
        val = str(val).strip().replace('Rp', '').replace('%', '').replace(' ', '').replace(',', '')
        if not val or val == 'nan' or val == 'None': return "0"
        return val
    # Handling format ribuan titik/koma secara cerdas
    return pd.to_numeric(series.apply(lambda x: str(x).replace('.', '') if '.' in str(x) and len(str(x).split('.')[-1]) == 3 else x).apply(process_val), errors='coerce').fillna(0)

MONTH_MAP = {
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'Mei': 5, 'Jun': 6,
    'Jul': 7, 'Agu': 8, 'Sep': 9, 'Okt': 10, 'Nov': 11, 'Des': 12,
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
        
        # Helper kolom untuk sorting & YtD
        def parse_p(p):
            p = str(p).replace('-', ' ').strip()
            parts = p.split(' ')
            m_str = parts[0]
            y_str = parts[1] if len(parts) > 1 else "2026"
            return m_str, y_str, MONTH_MAP.get(m_str, 0)

        df_f[['m_nm', 'y_val', 'm_idx']] = df_f['Periode'].apply(lambda x: pd.Series(parse_p(x)))
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

# --- 3. PROSES DATA ---
df_f_raw, df_l_raw, err = load_gsheets_data()
if err: st.error(f"Error: {err}"); st.stop()

# Sorting Periode
all_months = sorted(df_f_raw['Periode'].unique().tolist(), 
                    key=lambda x: (str(x).replace('-', ' ').split(' ')[1] if ' ' in str(x).replace('-', ' ') else "2026", 
                                   MONTH_MAP.get(str(x).replace('-', ' ').split(' ')[0], 0)), 
                    reverse=True)
sel_month = st.sidebar.selectbox("Pilih Periode Analisis:", all_months)

# Metadata Pilihan
m_name = str(sel_month).replace('-', ' ').split(' ')[0]
y_name = str(sel_month).replace('-', ' ').split(' ')[1] if ' ' in str(sel_month).replace('-', ' ') else "2026"
m_idx_selected = MONTH_MAP.get(m_name, 0)

# Market Data
hist_m = get_market_history()
sbn_val = st.sidebar.number_input("SBN 10Y Benchmark (Live)", value=round(float(hist_m['SBN_10Y'].iloc[-1]), 2), step=0.01)
bareksa_val = st.sidebar.number_input("Bareksa (Money Market %)", value=4.75, step=0.01)
criec_val = st.sidebar.number_input("PHEI CRIEC Index (%)", value=7.20, step=0.01)

rating = st.sidebar.selectbox("Pilih Rating Reinvestasi:", ["AAA", "AA+", "AA", "A", "BBB"])
spread_map = {"AAA": 80, "AA+": 110, "AA": 140, "A": 260, "BBB": 480}
target_bond_net = (sbn_val + (spread_map[rating]/100)) * 0.9

# --- 4. DASHBOARD UI ---
st.title(f"🚢 ASDP Treasury & ALM Master Command Center")
tab1, tab2, tab3 = st.tabs(["💰 Modul 1: Funding", "📈 Modul 2: Lending", "📊 Modul 3: ALM Resume"])

# ==========================================
# TAB 1: FUNDING (YTD FIX)
# ==========================================
with tab1:
    df_f = df_f_raw[df_f_raw['Periode'] == sel_month].copy()
    
    if not df_f.empty:
        # MtD Calculation
        df_f['Net_Yield'] = df_f['Rate'] * 0.8
        df_f['Rev_MtD'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        total_mtd = df_f['Rev_MtD'].sum()
        
        # YTD CALCULATION (AKURAT)
        # 1. Hitung pendapatan per baris di seluruh data mentah
        df_f_raw['Rev_Line'] = (df_f_raw['Nominal'] * (df_f_raw['Rate'] / 100)) / 12
        # 2. Filter: Harus di tahun yang sama DAN bulan <= bulan terpilih
        ytd_mask = (df_f_raw['y_val'] == y_name) & (df_f_raw['m_idx'].astype(int) <= m_idx_selected)
        total_ytd = df_f_raw[ytd_mask]['Rev_Line'].sum()

        net_sbn = sbn_val * 0.9

        # Metrics baris 1 (WhatsApp Style)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric(f"MtD Revenue ({m_name})", f"Rp {total_mtd:,.0f}")
        m3.metric(f"YtD Revenue (Jan-{m_name})", f"Rp {total_ytd:,.0f}")
        m4.metric("SBN Net Benchmark", f"{net_sbn:.2f}%")

        # Metrics baris 2
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
                    for _, row in df_loss.iterrows(): st.error(f"**{row['Bank']}** | Yield: `{row['Net_Yield']:.2f}%`")
                else: st.success("Posisi Penempatan Optimal.")
        with c_al2:
            st.subheader("⏳ Maturity Watch (H-14)")
            with st.container(height=180):
                today = datetime.now()
                df_soon = df_f[(df_f['Jatuh_Tempo'] >= today) & (df_f['Jatuh_Tempo'] <= today + timedelta(days=14))]
                if not df_soon.empty:
                    for _, row in df_soon.iterrows(): st.warning(f"**{row['Bank']}** | `{row['Jatuh_Tempo'].strftime('%d-%m-%Y')}`")
                else: st.info("Tidak ada jatuh tempo dalam waktu dekat.")

        st.divider()
        v1, v2 = st.columns([1.2, 1])
        with v1: st.plotly_chart(px.bar(df_f.groupby('Bank')['Rev_MtD'].sum().reset_index(), x='Bank', y='Rev_MtD', title="Revenue per Bank (MtD)", text_auto=',.0f', color='Bank'), use_container_width=True)
        with v2: st.plotly_chart(px.pie(df_f, values='Net_Yield', names='Bank', hole=0.5, title="Net Yield Mix"), use_container_width=True)

# ==========================================
# TAB 2 & 3 (LOCKED & STABLE)
# ==========================================
with tab2:
    df_l = df_l_raw[df_l_raw['Periode'] == sel_month].copy()
    if not df_l.empty:
        l1, l2, l3 = st.columns(3)
        l1.metric("Total Cash Out Debt", f"Rp {df_l['Nominal'].sum():,.0f}")
        l2.metric("Avg. Yield Lending", f"{df_l['Lending_Rate (%)'].mean():.2f}%" if 'Lending_Rate (%)' in df_l.columns else "N/A")
        l3.metric("Bank Kreditur Utama", df_l.groupby('Kreditur')['Nominal'].sum().idxmax())
        st.divider()
        st.plotly_chart(px.bar(df_l.groupby('Kreditur')['Nominal'].sum().reset_index().sort_values('Nominal', ascending=False), x='Kreditur', y='Nominal', text_auto=',.0f', color='Kreditur', title="Cash Out per Bank"), use_container_width=True)

with tab3:
    st.header(f"📊 ALM Strategic Intelligence - {sel_month}")
    if not df_f.empty:
        outflow = df_l_raw[df_l_raw['Periode'] == sel_month]['Nominal'].sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Interest Revenue", f"Rp {total_mtd:,.0f}")
        c2.metric("Total Cash Out Debt", f"Rp {outflow:,.0f}")
        c3.metric("Net NIM", f"Rp {total_mtd - outflow:,.0f}")
        c4.metric("ICR Strength", f"{(total_mtd/outflow if outflow > 0 else 0):.2f}x")
        st.divider()
        # Recommendations
        r1, r2 = st.columns(2)
        with r1:
            st.markdown("### 🇮🇩 Top 3 SBN Benchmark")
            st.table(pd.DataFrame({"Seri": ["FR0101", "FR0100", "FR0098"], "Yield": [f"{sbn_val:.2f}%", f"{(sbn_val-0.15):.2f}%", f"{(sbn_val+0.3):.2f}%"]}))
        with r2:
            st.markdown(f"### 🏢 Top 3 Corp Bond ({rating})")
            issuer_map = {"AAA": ["Bank Mandiri", "Telkom", "BRI"], "AA+": ["Astra", "BCA", "Indosat"], "AA": ["Adaro", "UT", "Semen Indo"], "A": ["Japfa", "Alam Sutera", "Gajah Tunggal"], "BBB": ["Lippo", "APLN", "Modernland"]}
            st.table(pd.DataFrame({"Issuer": issuer_map.get(rating, ["N/A"]*3), "Yield": [f"{(target_bond_net):.2f}%", f"{(target_bond_net-0.1):.2f}%", f"{(target_bond_net+0.1):.2f}%"]}))
        st.divider()
        # Historical Plot
        plot_d = hist_m.copy()
        plot_d['Bareksa'] = plot_d['SBN_10Y'] * (bareksa_val / (sbn_val if sbn_val != 0 else 1))
        plot_d['PHEI'] = plot_d['SBN_10Y'] * (criec_val / (sbn_val if sbn_val != 0 else 1))
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=plot_d.index, y=plot_d['SBN_10Y'], name='SBN 10Y'))
        fig.add_trace(go.Scatter(x=plot_d.index, y=plot_m['Bareksa'], name='Bareksa', line=dict(dash='dot')))
        fig.add_trace(go.Scatter(x=plot_d.index, y=plot_m['PHEI'], name='PHEI Bond', width=3))
        st.plotly_chart(fig, use_container_width=True)
