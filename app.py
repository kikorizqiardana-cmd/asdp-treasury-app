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
    b = str(bank_name).lower()
    if 'mandiri' in b: return "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ad/Bank_Mandiri_logo_2016.svg/512px-Bank_Mandiri_logo_2016.svg.png"
    if 'bri' in b: return "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/BRI_Logo.svg/512px-BRI_Logo.svg.png"
    if 'bni' in b: return "https://upload.wikimedia.org/wikipedia/id/thumb/5/55/BNI_logo.svg/512px-BNI_logo.svg.png"
    if 'bca' in b: return "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/Bank_Central_Asia.svg/512px-Bank_Central_Asia.svg.png"
    if 'btn' in b: return "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fd/Bank_BTN_logo.svg/512px-Bank_BTN_logo.svg.png"
    return "https://cdn-icons-png.flaticon.com/512/2830/2830284.png"

# --- 3. ENGINE DATA (PRECISION MAPPING) ---
def clean_numeric_robust(val):
    if pd.isna(val): return 0.0
    val_str = str(val).strip().replace('Rp', '').replace('%', '').replace(' ', '').replace(',', '')
    if not val_str or val_str.lower() == 'nan': return 0.0
    if '.' in val_str and len(val_str.split('.')[-1]) == 3: val_str = val_str.replace('.', '')
    try:
        return float(val_str)
    except ValueError:
        return 0.0

@st.cache_data(ttl=1)
def load_gsheets_data():
    sheet_id = "182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY"
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet="
    try:
        df_f_raw = pd.read_csv(base_url + "Funding")
        df_l_raw = pd.read_csv(base_url + "Lending")

        df_f = df_f_raw.dropna(subset=['Periode']).copy()
        df_l = df_l_raw.dropna(subset=['Periode']).copy()

        # SMART COLUMN FINDER (Case Insensitive & Multi-Format)
        l_map = {
            'bank': 'Kreditur', 'kreditur': 'Kreditur',
            'rate': 'Lending_Rate', 'lending rate': 'Lending_Rate',
            'sisa outstanding': 'Outstanding', 'sisa_outstanding': 'Outstanding',
            'pembayaran pokok': 'Bayar_Pokok', 'pembayaran_pokok': 'Bayar_Pokok',
            'pembayaran bunga': 'Bayar_Bunga', 'pembayaran_bunga': 'Bayar_Bunga', 'bunga': 'Bayar_Bunga'
        }

        df_l.columns = [l_map.get(str(c).strip().lower(), str(c).strip()) for c in df_l.columns]
        df_f.columns = [str(c).strip() for c in df_f.columns]
        
        # Funding Clean
        if 'Rate (%)' in df_f.columns: df_f.rename(columns={'Rate (%)': 'Rate'}, inplace=True)
        if 'Bank' in df_f.columns: df_f.rename(columns={'Bank': 'Kreditur'}, inplace=True)

        # Pembersihan Angka Semua Kolom Relevan
        for col in ['Nominal', 'Rate']:
            if col in df_f.columns: df_f[col] = df_f[col].apply(clean_numeric_robust)
        for col in ['Nominal', 'Lending_Rate', 'Outstanding', 'Bayar_Pokok', 'Bayar_Bunga']:
            if col in df_l.columns: df_l[col] = df_l[col].apply(clean_numeric_robust)

        def safe_parse_date(p):
            try:
                p_str = str(p).replace('-', ' ').strip()
                pts = p_str.split()
                return pd.Series([MONTH_MAP_REV.get(pts[0], 0), str(pts[1])])
            except: return pd.Series([0, "2026"])

        df_f[['m_idx', 'year_val']] = df_f['Periode'].apply(safe_parse_date)
        df_l[['m_idx', 'year_val']] = df_l['Periode'].apply(safe_parse_date)
        
        return df_f, df_l, None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), f"Error Parse: {str(e)}"

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
if err: st.error(err); st.stop()

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
# TAB 2: LENDING (PRECISION BREAKDOWN)
# ==========================================
with tab2:
    df_l = df_l_raw[(df_l_raw['m_idx'] == s_m_idx) & (df_l_raw['year_val'] == s_y_val)].copy()

    if not df_l.empty:
        # Metrik Agregat Utama
        col_out = 'Outstanding' if 'Outstanding' in df_l.columns else 'Nominal'
        col_pokok = 'Bayar_Pokok' if 'Bayar_Pokok' in df_l.columns else 'Nominal'
        col_bunga = 'Bayar_Bunga' if 'Bayar_Bunga' in df_l.columns else 'Nominal'
        col_rate = 'Lending_Rate' if 'Lending_Rate' in df_l.columns else 'Rate'

        l1, l2, l3 = st.columns(3)
        l1.metric("Total Sisa Outstanding", f"Rp {df_l[col_out].sum():,.0f}")
        avg_rt = np.nan_to_num(df_l[col_rate].mean())
        l2.metric("Avg Yield Lending (Rate)", f"{avg_rt:.2f}%")
        l3.metric("Total Pembayaran (P + I)", f"Rp {(df_l[col_pokok].sum() + df_l[col_bunga].sum()):,.0f}")

        st.divider()
        st.subheader("🏦 Rincian Kewajiban per Kreditur")
        
        if 'Kreditur' in df_l.columns:
            k_list = df_l['Kreditur'].unique()
            bank_cols = st.columns(len(k_list) if len(k_list) > 0 else 1)
            
            for i, b_name in enumerate(k_list):
                with bank_cols[i]:
                    st.image(get_bank_logo(b_name), width=90)
                    b_sub = df_l[df_l['Kreditur'] == b_name]
                    
                    v_rate = np.nan_to_num(b_sub[col_rate].mean())
                    v_out = b_sub[col_out].sum()
                    v_pokok = b_sub[col_pokok].sum()
                    v_bunga = b_sub[col_bunga].sum()
                    
                    st.markdown(f"### **{b_name}**")
                    st.caption(f"Rate: {v_rate:.2f}%")
                    st.markdown(f"""
                    * **Sisa Outstanding:** Rp {v_out:,.0f}
                    * **Pembayaran Pokok:** Rp {v_pokok:,.0f}
                    * **Pembayaran Bunga:** Rp {v_bunga:,.0f}
                    ---
                    **Tagihan Bulan Ini: Rp {(v_pokok + v_bunga):,.0f}**
                    """)

            st.divider()
            st.subheader(f"📊 Eksposisi Pembayaran per Bank - {s_m_name}")
            df_plot = df_l.groupby('Kreditur').agg({col_pokok: 'sum', col_bunga: 'sum'}).reset_index()
            df_plot['Total_Bayar'] = df_plot[col_pokok] + df_plot[col_bunga]
            
            fig_l_bar = px.bar(
                df_plot,
                x='Kreditur', y=[col_pokok, col_bunga],
                title="Breakdown Pembayaran Pokok & Bunga",
                text_auto=',.0f', barmode='group',
                color_discrete_sequence=['#1f77b4', '#aec7e8']
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
        out_total = (df_l[col_pokok].sum() + df_l[col_bunga].sum()) if not df_l.empty else 0
        total_mtd_rev = (df_f['Nominal'] * (df_f['Rate'] / 100) / 12).sum()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Interest Revenue", f"Rp {total_mtd_rev:,.0f}")
        c2.metric("Total Cash Out (P+I)", f"Rp {out_total:,.0f}")
        c3.metric("Net Flow Gap", f"Rp {total_mtd_rev - out_total:,.0f}")
        c4.metric("ICR Strength", f"{(total_mtd_rev/out_total if out_total > 0 else 0):.2f}x")
        st.divider()
        plot_df = hist_m.copy()
        plot_df['Bareksa'] = plot_df['SBN_10Y'] * (bareksa_val / (sbn_val if sbn_val != 0 else 1))
        plot_df['PHEI'] = plot_df['SBN_10Y'] * (criec_val / (sbn_val if sbn_val != 0 else 1))
        f_alm = go.Figure()
        f_alm.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SBN_10Y'], name='SBN 10Y'))
        f_alm.add_trace(go.Scatter(x=plot_df.index, y=plot_df['Bareksa'], name='Bareksa MM', line=dict(dash='dot')))
        f_alm.add_trace(go.Scatter(x=plot_df.index, y=plot_df['PHEI'], name='PHEI Bond Index', line=dict(width=3)))
        st.plotly_chart(f_alm, use_container_width=True)
