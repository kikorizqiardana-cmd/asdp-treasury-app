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

# --- 3. ENGINE DATA (RADAR PENCARI KATA KUNCI + JATUH TEMPO) ---
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

        # RADAR KOLOM LENDING: Cari kata kunci di nama kolom
        def map_lending_cols(c):
            norm = " ".join(str(c).strip().lower().split())
            if 'bank' in norm or 'kreditur' in norm: return 'Kreditur'
            if 'rate' in norm or 'suku' in norm: return 'Lending_Rate'
            if 'sisa' in norm or 'outstanding' in norm: return 'Outstanding'
            if 'pokok' in norm or 'nominal' in norm: return 'Bayar_Pokok' # Menangkap kolom "Nominal" sbg Pokok
            if 'bunga' in norm and 'suku' not in norm and 'rate' not in norm: return 'Bayar_Bunga'
            if 'jatuh' in norm and 'tempo' in norm: return 'Jatuh_Tempo'
            return str(c).strip()

        df_l.columns = [map_lending_cols(c) for c in df_l.columns]
        
        # Funding Clean
        def map_funding_cols(c):
            norm = " ".join(str(c).strip().lower().split())
            if 'rate' in norm: return 'Rate'
            if 'bank' in norm or 'kreditur' in norm: return 'Kreditur'
            if 'jatuh' in norm and 'tempo' in norm: return 'Jatuh_Tempo'
            return str(c).strip()
        
        df_f.columns = [map_funding_cols(c) for c in df_f.columns]

        # PAGAR ANTI-KEYERROR
        for req in ['Kreditur', 'Lending_Rate', 'Outstanding', 'Bayar_Pokok', 'Bayar_Bunga', 'Jatuh_Tempo']:
            if req not in df_l.columns:
                if req == 'Kreditur': df_l[req] = "Unknown"
                elif req == 'Jatuh_Tempo': df_l[req] = pd.NaT
                else: df_l[req] = 0.0

        # Pembersihan Angka
        for col in ['Nominal', 'Rate']:
            if col in df_f.columns: df_f[col] = df_f[col].apply(clean_numeric_robust)
        for col in ['Lending_Rate', 'Outstanding', 'Bayar_Pokok', 'Bayar_Bunga']:
            if col in df_l.columns: df_l[col] = df_l[col].apply(clean_numeric_robust)

        # Parse Tanggal Jatuh Tempo
        if 'Jatuh_Tempo' in df_f.columns:
            df_f['Jatuh_Tempo'] = pd.to_datetime(df_f['Jatuh_Tempo'], dayfirst=True, errors='coerce')
        if 'Jatuh_Tempo' in df_l.columns:
            df_l['Jatuh_Tempo'] = pd.to_datetime(df_l['Jatuh_Tempo'], dayfirst=True, errors='coerce')

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
        c_al1, c_al2 = st.columns(2)
        with c_al1:
            st.subheader("🚩 Spread Alert (vs SBN)")
            with st.container(height=180):
                net_sbn = sbn_val * 0.9
                df_loss = df_f[(df_f['Rate'] * 0.8) < net_sbn]
                if not df_loss.empty:
                    for _, row in df_loss.iterrows(): st.error(f"**{row['Kreditur']}** | Yield Net: `{(row['Rate']*0.8):.2f}%`")
                else: st.success("Strategi Penempatan Optimal.")
        with c_al2:
            st.subheader("⏳ Maturity Watch (H-14) - Funding")
            with st.container(height=180):
                today = datetime.now()
                df_soon = df_f[(df_f['Jatuh_Tempo'] >= today) & (df_f['Jatuh_Tempo'] <= today + timedelta(days=14))]
                if not df_soon.empty:
                    for _, row in df_soon.iterrows(): st.warning(f"**{row['Kreditur']}** | JT: `{row['Jatuh_Tempo'].strftime('%d-%m-%Y')}`")
                else: st.info("Tidak ada penempatan jatuh tempo dekat.")

        st.divider()
        v1, v2 = st.columns([1.2, 1])
        with v1: st.plotly_chart(px.bar(df_f.groupby('Kreditur')['Rev_MtD'].sum().reset_index(), x='Kreditur', y='Rev_MtD', title="Revenue per Bank (MtD)", text_auto=',.0f', color='Kreditur'), use_container_width=True)
        with v2: st.plotly_chart(px.pie(df_f, values='Nominal', names='Kreditur', hole=0.5, title="Nominal Mix"), use_container_width=True)
    else:
        st.warning(f"Data Funding untuk {s_m_name} {s_y_val} tidak ditemukan.")

# ==========================================
# TAB 2: LENDING (NOMINAL FIXED & ALERT JATUH TEMPO)
# ==========================================
with tab2:
    df_l = df_l_raw[(df_l_raw['m_idx'] == s_m_idx) & (df_l_raw['year_val'] == s_y_val)].copy()

    if not df_l.empty:
        # Metrik Agregat
        l1, l2, l3 = st.columns(3)
        l1.metric("Total Sisa Outstanding", f"Rp {df_l['Outstanding'].sum():,.0f}")
        avg_rt = np.nan_to_num(df_l['Lending_Rate'].mean())
        l2.metric("Avg Yield Lending (Rate)", f"{avg_rt:.2f}%")
        tot_pay = df_l['Bayar_Pokok'].sum() + df_l['Bayar_Bunga'].sum()
        l3.metric("Total Pembayaran (Pokok + Bunga)", f"Rp {tot_pay:,.0f}")

        st.divider()

        # 🚨 ALERT JATUH TEMPO PEMBAYARAN (H-14)
        today = datetime.now()
        df_soon_l = df_l[(df_l['Jatuh_Tempo'] >= today) & (df_l['Jatuh_Tempo'] <= today + timedelta(days=14))]
        if not df_soon_l.empty:
            st.error("⏳ **WARNING: Jatuh Tempo Kewajiban (H-14)**")
            for _, row in df_soon_l.iterrows():
                jt_date = row['Jatuh_Tempo'].strftime('%d-%m-%Y')
                st.warning(f"🏦 **{row['Kreditur']}** | Jatuh Tempo: `{jt_date}` | Tagihan Pokok: **Rp {row['Bayar_Pokok']:,.0f}**")
            st.divider()

        # Breakdown per Bank
        st.subheader("🏦 Rincian Kewajiban per Kreditur")
        k_list = [k for k in df_l['Kreditur'].unique() if str(k) != '0.0' and str(k) != 'Unknown']
        
        if not k_list:
            st.info("Nama bank tidak ditemukan untuk periode ini.")
        else:
            bank_cols = st.columns(len(k_list))
            for i, b_name in enumerate(k_list):
                with bank_cols[i]:
                    st.image(get_bank_logo(b_name), width=90)
                    b_sub = df_l[df_l['Kreditur'] == b_name]
                    
                    v_rate = np.nan_to_num(b_sub['Lending_Rate'].mean())
                    v_out = b_sub['Outstanding'].sum()
                    v_pokok = b_sub['Bayar_Pokok'].sum()
                    v_bunga = b_sub['Bayar_Bunga'].sum()
                    
                    st.markdown(f"### **{b_name}**")
                    st.caption(f"Rate: {v_rate:.2f}%")
                    st.markdown(f"""
                    * **Sisa Outstanding:** Rp {v_out:,.0f}
                    * **Bayar Pokok:** Rp {v_pokok:,.0f}
                    * **Bayar Bunga:** Rp {v_bunga:,.0f}
                    ---
                    **Total Tagihan: Rp {(v_pokok + v_bunga):,.0f}**
                    """)

            st.divider()
            st.subheader(f"📊 Eksposisi Pembayaran per Bank - {s_m_name}")
            
            df_plot = df_l[df_l['Kreditur'].isin(k_list)].groupby('Kreditur').agg({'Bayar_Pokok': 'sum', 'Bayar_Bunga': 'sum'}).reset_index()
            fig_l_bar = px.bar(
                df_plot,
                x='Kreditur', y=['Bayar_Pokok', 'Bayar_Bunga'],
                title="Breakdown Pembayaran Pokok vs Bunga",
                text_auto=',.0f', barmode='group',
                color_discrete_sequence=['#1f77b4', '#ff7f0e']
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
        out_total = (df_l['Bayar_Pokok'].sum() + df_l['Bayar_Bunga'].sum()) if not df_l.empty else 0
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
