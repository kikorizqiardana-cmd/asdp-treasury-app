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

# --- 2. DATA MAPPING (LOCKED) ---
MONTH_MAP_ID = {
    1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April', 5: 'Mei', 6: 'Juni',
    7: 'Juli', 8: 'Agustus', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
}
MONTH_MAP_REV = {
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'Mei': 5, 'Jun': 6, 'Jul': 7, 'Agu': 8, 'Sep': 9, 'Okt': 10, 'Nov': 11, 'Des': 12,
    'Januari': 1, 'Februari': 2, 'Maret': 3, 'April': 4, 'Mei': 5, 'Juni': 6, 'Juli': 7, 'Agustus': 8, 'September': 9, 'Oktober': 10, 'November': 11, 'Desember': 12
}

def get_bank_logo(bank_name):
    bank_name = str(bank_name).lower()
    if 'mandiri' in bank_name: return "https://upload.wikimedia.org/wikipedia/commons/a/ad/Bank_Mandiri_logo_2016.svg"
    if 'bri' in bank_name: return "https://upload.wikimedia.org/wikipedia/commons/2/2e/BRI_Logo.svg"
    if 'bni' in bank_name: return "https://upload.wikimedia.org/wikipedia/id/5/55/BNI_logo.svg"
    if 'bca' in bank_name: return "https://upload.wikimedia.org/wikipedia/commons/5/5c/Bank_Central_Asia.svg"
    if 'btn' in bank_name: return "https://upload.wikimedia.org/wikipedia/commons/f/fd/Bank_BTN_logo.svg"
    return "https://cdn-icons-png.flaticon.com/512/2830/2830284.png"

# --- 3. ENGINE DATA (TRIPLE SHIELD) ---
def clean_numeric_robust(series):
    def process_val(val):
        if pd.isna(val): return "0"
        val = str(val).strip().replace('Rp', '').replace('%', '').replace(' ', '').replace(',', '')
        if not val or val.lower() == 'nan': return "0"
        if '.' in val and len(val.split('.')[-1]) == 3: val = val.replace('.', '')
        return val
    return pd.to_numeric(series.apply(process_val), errors='coerce').fillna(0)

@st.cache_data(ttl=1)
def load_gsheets_data():
    sheet_id = "182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY"
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet="
    try:
        # Load and drop basic NaNs
        df_f = pd.read_csv(base_url + "Funding").dropna(subset=['Periode'])
        df_l = pd.read_csv(base_url + "Lending").dropna(subset=['Periode'])
        
        # Shield 1: Strict Period Filter (Must start with a month name or digit)
        valid_starts = list(MONTH_MAP_REV.keys())
        df_f = df_f[df_f['Periode'].astype(str).str.split().str[0].isin(valid_starts)].copy()
        df_l = df_l[df_l['Periode'].astype(str).str.split().str[0].isin(valid_starts)].copy()

        df_f.columns = [c.strip() for c in df_f.columns]
        df_l.columns = [c.strip() for c in df_l.columns]
        
        # Smart Map Columns for Lending
        l_map = {'Bank': 'Kreditur', 'Rate': 'Lending_Rate', 'Sisa Outstanding': 'Outstanding', 'Pembayaran Pokok': 'Bayar_Pokok'}
        for o, n in l_map.items():
            if o in df_l.columns and n not in df_l.columns: df_l.rename(columns={o: n}, inplace=True)
        
        for c in ['Nominal', 'Rate']:
            if c in df_f.columns: df_f[c] = clean_numeric_robust(df_f[c])
        for c in ['Nominal', 'Lending_Rate', 'Outstanding', 'Bayar_Pokok']:
            if c in df_l.columns: df_l[c] = clean_numeric_robust(df_l[c])
            
        # Shield 2: Try-Except Date Parser
        def safe_parse_date(p):
            try:
                p_str = str(p).replace('-', ' ').strip()
                pts = p_str.split()
                m_idx = MONTH_MAP_REV.get(pts[0], 0)
                y_val = pts[1] if len(pts) > 1 else "2026"
                return pd.Series([m_idx, str(y_val)])
            except Exception:
                return pd.Series([0, "2026"])

        df_f[['m_idx', 'year_val']] = df_f['Periode'].apply(safe_parse_date)
        df_l[['m_idx', 'year_val']] = df_l['Periode'].apply(safe_parse_date)
        
        return df_f, df_l, None
    except Exception as e: return pd.DataFrame(), pd.DataFrame(), str(e)

@st.cache_data(ttl=3600)
def get_market_history():
    try:
        data = yf.Ticker("ID10Y=F").history(period="6mo")
        if not data.empty: return data[['Close']].rename(columns={'Close': 'SBN_10Y'}).copy()
    except: pass
    return pd.DataFrame({'SBN_10Y': [6.6]}, index=[datetime.now()])

# --- 4. SIDEBAR (LOCKED) ---
logo_path = "ferry.png"
if os.path.exists(logo_path): st.sidebar.image(logo_path, use_container_width=True)
st.sidebar.markdown("---")
st.sidebar.header("📅 Periode Analisis")
sel_date = st.sidebar.date_input("Pilih Bulan & Tahun:", value=datetime(2026, 3, 1))
s_m_idx, s_y_val = sel_date.month, str(sel_date.year)
s_m_name = MONTH_MAP_ID[s_m_idx]

df_f_raw, df_l_raw, err = load_gsheets_data()
if err: st.error(f"Error Database: {err}"); st.stop()

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Market Intelligence")
hist_m = get_market_history()
sbn_val = st.sidebar.number_input("SBN 10Y Benchmark (Live)", value=round(float(hist_m['SBN_10Y'].iloc[-1]), 2), step=0.01)
bareksa_val = st.sidebar.number_input("Bareksa (Money Market %)", value=4.75, step=0.01)
criec_val = st.sidebar.number_input("PHEI CRIEC Index (%)", value=7.20, step=0.01)

st.sidebar.link_button("🌐 Bareksa Data", "https://www.bareksa.com/id/data", use_container_width=True)
st.sidebar.link_button("📉 PHEI (Informasi Efek)", "https://www.phei.co.id/Data/Informasi-Efek", use_container_width=True)
st.sidebar.link_button("📊 Data Source (GSheets)", "https://docs.google.com/spreadsheets/d/182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY", use_container_width=True)
st.sidebar.markdown("---")
rating = st.sidebar.selectbox("Rating Reinvestasi:", ["AAA", "AA+", "AA", "A", "BBB"])
spread_map = {"AAA": 80, "AA+": 110, "AA": 140, "A": 260, "BBB": 480}
target_bond_net = (sbn_val + (spread_map[rating]/100)) * 0.9

# --- 5. DASHBOARD UI ---
st.title(f"🚢 ASDP Treasury & ALM Master Command Center")
tab1, tab2, tab3 = st.tabs(["💰 Modul 1: Funding", "📈 Modul 2: Lending", "📊 Modul 3: ALM Resume"])

# ==========================================
# TAB 1: FUNDING (LOCKED)
# ==========================================
with tab1:
    df_f = df_f_raw[(df_f_raw['m_idx'] == s_m_idx) & (df_f_raw['year_val'] == s_y_val)].copy()
    if not df_f.empty:
        df_f['Rev_MtD'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        total_mtd = df_f['Rev_MtD'].sum()
        ytd_mask = (df_f_raw['year_val'] == s_y_val) & (df_f_raw['m_idx'] <= s_m_idx)
        total_ytd = ((df_f_raw[ytd_mask]['Nominal'] * df_f_raw[ytd_mask]['Rate']) / 1200).sum()
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric(f"MtD Revenue ({s_m_name})", f"Rp {total_mtd:,.0f}")
        m3.metric(f"YtD Revenue (Jan-{s_m_name[:3]})", f"Rp {total_ytd:,.0f}")
        m4.metric("SBN Net Benchmark", f"{(sbn_val * 0.9):.2f}%")
        st.divider()
        v1, v2 = st.columns([1.2, 1])
        with v1: st.plotly_chart(px.bar(df_f.groupby('Kreditur')['Rev_MtD'].sum().reset_index(), x='Kreditur', y='Rev_MtD', title="Revenue per Bank (MtD)", text_auto=',.0f', color='Kreditur'), use_container_width=True)
        with v2: st.plotly_chart(px.pie(df_f, values='Nominal', names='Kreditur', hole=0.5, title="Nominal Mix"), use_container_width=True)

# ==========================================
# TAB 2: LENDING (ULTRA PRECISION)
# ==========================================
with tab2:
    df_l = df_l_raw[(df_l_raw['m_idx'] == s_m_idx) & (df_l_raw['year_val'] == s_y_val)].copy()

    if not df_l.empty:
        l1, l2, l3 = st.columns(3)
        l1.metric("Total Sisa Outstanding", f"Rp {df_l['Outstanding'].sum():,.0f}")
        l2.metric("Avg Yield Lending (Rate)", f"{df_l['Lending_Rate'].mean():.2f}%")
        l3.metric("Total Pembayaran Pokok", f"Rp {df_l['Bayar_Pokok'].sum():,.0f}")

        st.divider()
        st.subheader("🏦 Detail Kreditur & Pembayaran")
        k_list = df_l['Kreditur'].unique()
        bank_cols = st.columns(len(k_list))
        for i, b_name in enumerate(k_list):
            with bank_cols[i]:
                st.image(get_bank_logo(b_name), width=70)
                b_sub = df_l[df_l['Kreditur'] == b_name]
                st.write(f"**{b_name}**")
                v_rate = b_sub['Lending_Rate'].mean()
                v_out = b_sub['Outstanding'].sum()
                v_pay = b_sub['Bayar_Pokok'].sum()
                st.write(f"Rate: `{v_rate:.2f}%`")
                st.write(f"Sisa: \nRp {v_out:,.0f}")
                st.write(f"Bayar Pokok: \nRp {v_pay:,.0f}")

        st.divider()
        st.subheader(f"📊 Breakdown Pembayaran Pokok per Bank - {s_m_name}")
        fig_l_bar = px.bar(
            df_l.groupby('Kreditur')['Bayar_Pokok'].sum().reset_index(),
            x='Kreditur', y='Bayar_Pokok',
            title="Pembayaran Pokok per Bank",
            text_auto=',.0f', color='Kreditur',
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        st.plotly_chart(fig_l_bar, use_container_width=True)
    else:
        st.warning(f"Data Lending untuk {s_m_name} {s_y_val} tidak ditemukan.")

# ==========================================
# TAB 3: ALM RESUME
# ==========================================
with tab3:
    st.header(f"📊 ALM Strategic Intelligence - {s_m_name}")
    if not df_f.empty:
        out_p = df_l['Bayar_Pokok'].sum() if not df_l.empty else 0
        total_mtd_rev = (df_f['Nominal'] * (df_f['Rate'] / 100) / 12).sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Interest Revenue", f"Rp {total_mtd_rev:,.0f}")
        c2.metric("Cash Out (Pokok)", f"Rp {out_p:,.0f}")
        c3.metric("Net Flow Gap", f"Rp {total_mtd_rev - out_p:,.0f}")
        c4.metric("ICR Strength", f"{(total_mtd_rev/out_p if out_p > 0 else 0):.2f}x")
        st.divider()
        plot_df = hist_m.copy()
        plot_df['Bareksa'] = plot_df['SBN_10Y'] * (bareksa_val / (sbn_val if sbn_val != 0 else 1))
        plot_df['PHEI'] = plot_df['SBN_10Y'] * (criec_val / (sbn_val if sbn_val != 0 else 1))
        f_alm = go.Figure()
        f_alm.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SBN_10Y'], name='SBN 10Y'))
        f_alm.add_trace(go.Scatter(x=plot_df.index, y=plot_df['Bareksa'], name='Bareksa MM', line=dict(dash='dot')))
        f_alm.add_trace(go.Scatter(x=plot_df.index, y=plot_df['PHEI'], name='PHEI Bond Index', line=dict(width=3)))
        st.plotly_chart(f_alm, use_container_width=True)
