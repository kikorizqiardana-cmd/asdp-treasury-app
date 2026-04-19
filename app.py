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

# --- 3. ENGINE DATA (PRECISION NUMERIC & STRICT INTEGER TYPE) ---
def clean_numeric_robust(val):
    if pd.isna(val): return 0.0
    val_str = str(val).strip().replace('Rp', '').replace('%', '').replace(' ', '')
    if not val_str or val_str.lower() == 'nan': return 0.0
    
    if ',' in val_str and '.' in val_str:
        val_str = val_str.replace('.', '').replace(',', '.')
    elif ',' in val_str: 
        val_str = val_str.replace(',', '.')
    elif '.' in val_str: 
        parts = val_str.split('.')
        if len(parts[-1]) == 3:
            val_str = val_str.replace('.', '')
            
    try:
        return float(val_str)
    except:
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

        def map_lending_cols(c):
            norm = " ".join(str(c).strip().lower().split())
            if 'bank' in norm or 'kreditur' in norm: return 'Kreditur'
            if 'rate' in norm or 'suku' in norm: return 'Lending_Rate'
            if 'sisa' in norm or 'outstanding' in norm: return 'Outstanding'
            if 'tipe' in norm or 'jenis' in norm: return 'Tipe'
            if 'nominal' in norm: return 'Nominal_Lending'
            if 'jatuh' in norm and 'tempo' in norm: return 'Jatuh_Tempo'
            return str(c).strip()

        df_l.columns = [map_lending_cols(c) for c in df_l.columns]
        
        def map_funding_cols(c):
            norm = " ".join(str(c).strip().lower().split())
            if 'rate' in norm: return 'Rate'
            if 'bank' in norm or 'kreditur' in norm: return 'Kreditur'
            if 'jatuh' in norm and 'tempo' in norm: return 'Jatuh_Tempo'
            return str(c).strip()
        
        df_f.columns = [map_funding_cols(c) for c in df_f.columns]

        for col in ['Nominal', 'Rate']:
            if col in df_f.columns: df_f[col] = df_f[col].apply(clean_numeric_robust)
        for col in ['Lending_Rate', 'Outstanding', 'Nominal_Lending']:
            if col in df_l.columns: df_l[col] = df_l[col].apply(clean_numeric_robust)

        if 'Jatuh_Tempo' in df_f.columns: df_f['Jatuh_Tempo'] = pd.to_datetime(df_f['Jatuh_Tempo'], dayfirst=True, errors='coerce')
        if 'Jatuh_Tempo' in df_l.columns: df_l['Jatuh_Tempo'] = pd.to_datetime(df_l['Jatuh_Tempo'], dayfirst=True, errors='coerce')

        def safe_parse_date(p):
            try:
                p_str = str(p).replace('-', ' ').strip()
                pts = p_str.split()
                return pd.Series([int(MONTH_MAP_REV.get(pts[0], 0)), str(pts[1])])
            except: return pd.Series([0, "2026"])

        df_f[['m_idx', 'year_val']] = df_f['Periode'].apply(safe_parse_date)
        df_l[['m_idx', 'year_val']] = df_l['Periode'].apply(safe_parse_date)
        
        # SANGAT PENTING: Paksa kolom index bulan jadi format matematika murni (Integer)
        df_f['m_idx'] = pd.to_numeric(df_f['m_idx'], errors='coerce').fillna(0).astype(int)
        df_l['m_idx'] = pd.to_numeric(df_l['m_idx'], errors='coerce').fillna(0).astype(int)
        
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
s_m_idx, s_y_val = int(sel_date.month), str(sel_date.year)
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
# TAB 1: FUNDING (RESTORED PROJECTION)
# ==========================================
with tab1:
    df_f = df_f_raw[(df_f_raw['m_idx'] == s_m_idx) & (df_f_raw['year_val'] == s_y_val)].copy()
    if not df_f.empty:
        df_f['Rev_MtD'] = (df_f['Nominal'] * (df_f['Rate'] / 100)) / 12
        total_mtd = df_f['Rev_MtD'].sum()
        ytd_mask = (df_f_raw['year_val'] == s_y_val) & (df_f_raw['m_idx'] <= s_m_idx) & (df_f_raw['m_idx'] > 0)
        total_ytd_f = ((df_f_raw[ytd_mask]['Nominal'] * df_f_raw[ytd_mask]['Rate']) / 1200).sum()
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric(f"MtD Revenue ({s_m_name})", f"Rp {total_mtd:,.0f}")
        m3.metric(f"YtD Revenue (Jan-{s_m_name[:3]})", f"Rp {total_ytd_f:,.0f}")
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
            st.subheader("⏳ Maturity Watch (H-14)")
            with st.container(height=180):
                today = datetime.now()
                df_soon = df_f[(df_f['Jatuh_Tempo'] >= today) & (df_f['Jatuh_Tempo'] <= today + timedelta(days=14))]
                if not df_soon.empty:
                    for _, row in df_soon.iterrows(): st.warning(f"**{row['Kreditur']}** | JT: `{row['Jatuh_Tempo'].strftime('%d-%m-%Y')}`")
                else: st.info("Tidak ada penempatan jatuh tempo dekat.")

        st.divider()
        st.subheader("📊 Strategic Projection: SBN vs Corporate Bonds")
        df_proj = df_f.copy()
        df_proj['Yield_Net'] = df_proj['Rate'] * 0.8
        df_proj['Gap_vs_Target'] = target_bond_net - df_proj['Yield_Net']
        df_proj['Potensi_Ops_Gain'] = (df_proj['Gap_vs_Target'] / 100) * df_proj['Nominal'] / 12
        
        st.dataframe(
            df_proj[['Kreditur', 'Nominal', 'Rate', 'Yield_Net', 'Gap_vs_Target', 'Potensi_Ops_Gain']].style.format({
                'Nominal': '{:,.0f}', 'Rate': '{:.2f}%', 'Yield_Net': '{:.2f}%', 
                'Gap_vs_Target': '{:.2f}%', 'Potensi_Ops_Gain': '{:,.0f}'
            }), use_container_width=True
        )

        st.divider()
        v1, v2 = st.columns([1.2, 1])
        with v1: st.plotly_chart(px.bar(df_f.groupby('Kreditur')['Rev_MtD'].sum().reset_index(), x='Kreditur', y='Rev_MtD', title="Revenue per Bank (MtD)", text_auto=',.0f', color='Kreditur'), use_container_width=True)
        with v2: st.plotly_chart(px.pie(df_f, values='Nominal', names='Kreditur', hole=0.5, title="Nominal Mix"), use_container_width=True)
    else:
        st.warning(f"Data Funding untuk {s_m_name} {s_y_val} tidak ditemukan.")

# ==========================================
# TAB 2: LENDING (YTD FIX & MATEMATIKA MURNI)
# ==========================================
with tab2:
    df_l = df_l_raw[(df_l_raw['m_idx'] == s_m_idx) & (df_l_raw['year_val'] == s_y_val)].copy()
    
    # YTD MASK SEKARANG 100% AMAN (Int vs Int)
    ytd_mask_l = (df_l_raw['year_val'] == s_y_val) & (df_l_raw['m_idx'] <= s_m_idx) & (df_l_raw['m_idx'] > 0)
    df_l_ytd = df_l_raw[ytd_mask_l].copy()

    if not df_l.empty:
        # Kalkulasi MtD
        mtd_pokok = df_l.loc[df_l['Tipe'].astype(str).str.contains('pokok', case=False, na=False), 'Nominal_Lending'].sum()
        mtd_bunga = df_l.loc[df_l['Tipe'].astype(str).str.contains('bunga', case=False, na=False), 'Nominal_Lending'].sum()
        mtd_total = mtd_pokok + mtd_bunga

        # Kalkulasi YtD (FIXED)
        ytd_pokok = df_l_ytd.loc[df_l_ytd['Tipe'].astype(str).str.contains('pokok', case=False, na=False), 'Nominal_Lending'].sum()
        ytd_bunga = df_l_ytd.loc[df_l_ytd['Tipe'].astype(str).str.contains('bunga', case=False, na=False), 'Nominal_Lending'].sum()
        ytd_total = ytd_pokok + ytd_bunga

        total_out = df_l.groupby('Kreditur')['Outstanding'].max().sum()
        avg_rt = np.nan_to_num(df_l['Lending_Rate'].mean())

        l1, l2, l3, l4 = st.columns(4)
        l1.metric("Total Sisa Outstanding", f"Rp {total_out:,.0f}")
        l2.metric(f"MtD Bayar ({s_m_name})", f"Rp {mtd_total:,.0f}")
        l3.metric(f"YtD Bayar (Jan-{s_m_name[:3]})", f"Rp {ytd_total:,.0f}")
        l4.metric("Avg Yield Lending", f"{avg_rt:.2f}%")

        st.divider()
        # ALERT JATUH TEMPO LENDING (H-14)
        today = datetime.now()
        df_soon_l = df_l_raw[(df_l_raw['Jatuh_Tempo'] >= today) & (df_l_raw['Jatuh_Tempo'] <= today + timedelta(days=14))]
        if not df_soon_l.empty:
            st.error("⏳ **WARNING: Jatuh Tempo Tagihan Lending (H-14)**")
            df_soon_agg = df_soon_l.groupby(['Kreditur', 'Jatuh_Tempo'])['Nominal_Lending'].sum().reset_index()
            for _, row in df_soon_agg.iterrows():
                st.warning(f"🏦 **{row['Kreditur']}** | JT: `{row['Jatuh_Tempo'].strftime('%d-%m-%Y')}` | Tagihan: **Rp {row['Nominal_Lending']:,.0f}**")
            st.divider()

        # Rincian per Bank (NO LOGOS)
        st.subheader("🏦 Rincian Kewajiban per Kreditur")
        k_list = [k for k in df_l['Kreditur'].unique() if str(k) != '0.0' and str(k) != 'Unknown']
        if k_list:
            bank_cols = st.columns(len(k_list))
            plot_data = []
            for i, b_name in enumerate(k_list):
                with bank_cols[i]:
                    b_sub = df_l[df_l['Kreditur'] == b_name]
                    v_rate = np.nan_to_num(b_sub['Lending_Rate'].mean())
                    v_out = b_sub['Outstanding'].max()
                    v_pokok = b_sub.loc[b_sub['Tipe'].astype(str).str.contains('pokok', case=False, na=False), 'Nominal_Lending'].sum()
                    v_bunga = b_sub.loc[b_sub['Tipe'].astype(str).str.contains('bunga', case=False, na=False), 'Nominal_Lending'].sum()
                    plot_data.append({'Kreditur': b_name, 'Pokok': v_pokok, 'Bunga': v_bunga})

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
            df_plot = pd.DataFrame(plot_data)
            st.plotly_chart(px.bar(df_plot, x='Kreditur', y=['Pokok', 'Bunga'], title="Breakdown Pembayaran Pokok vs Bunga", barmode='group', color_discrete_sequence=['#1f77b4', '#ff7f0e']), use_container_width=True)
    else:
        st.warning(f"Data Lending untuk {s_m_name} {s_y_val} tidak ditemukan.")

# ==========================================
# TAB 3: ALM RESUME
# ==========================================
with tab3:
    st.header(f"📊 ALM Strategic Intelligence - {s_m_name}")
    if not df_f.empty:
        out_total = df_l['Nominal_Lending'].sum() if not df_l.empty else 0
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
