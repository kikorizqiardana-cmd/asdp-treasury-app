import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import os
import numpy as np
from datetime import datetime, timedelta
import streamlit.components.v1 as components
import requests
import re

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="ASDP ALM Strategic Command", layout="wide", page_icon="🚢")

# --- 2. DATA MAPPING ---
MONTH_MAP_ID = {
    1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April', 5: 'Mei', 6: 'Juni',
    7: 'Juli', 8: 'Agustus', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
}
MONTH_LOOKUP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mei': 5, 'may': 5, 'jun': 6, 
    'jul': 7, 'agu': 8, 'aug': 8, 'sep': 9, 'okt': 10, 'oct': 10, 'nov': 11, 'des': 12, 'dec': 12
}

# --- 3. ENGINE DATA (GSHEET & SCRAPER BI) ---
def clean_numeric_robust(val):
    if pd.isna(val): return 0.0
    val_str = str(val).strip().replace('Rp', '').replace('%', '').replace(' ', '')
    if not val_str or val_str.lower() == 'nan': return 0.0
    if ',' in val_str and '.' in val_str: val_str = val_str.replace('.', '').replace(',', '.')
    elif ',' in val_str: val_str = val_str.replace(',', '.')
    elif '.' in val_str: 
        parts = val_str.split('.')
        if len(parts[-1]) == 3: val_str = val_str.replace('.', '')
    try: return float(val_str)
    except Exception: return 0.0

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
            if 'nominal' in norm or 'jumlah' in norm: return 'Nominal_Lending'
            if 'jatuh' in norm and 'tempo' in norm: return 'Jatuh_Tempo'
            return str(c).strip()

        df_l.columns = [map_lending_cols(c) for c in df_l.columns]
        
        def map_funding_cols(c):
            norm = " ".join(str(c).strip().lower().split())
            if 'rate' in norm: return 'Rate'
            if 'bank' in norm or 'kreditur' in norm: return 'Bank'
            if 'nominal' in norm: return 'Nominal'
            if 'jatuh' in norm and 'tempo' in norm: return 'Jatuh_Tempo'
            if 'bilyet' in norm or 'rekening' in norm: return 'No_Bilyet'
            return str(c).strip()
        
        df_f.columns = [map_funding_cols(c) for c in df_f.columns]

        if 'No_Bilyet' not in df_f.columns: df_f['No_Bilyet'] = "-"
        df_f['No_Bilyet'] = df_f['No_Bilyet'].fillna("-").astype(str).replace('nan', '-')

        for col in ['Nominal', 'Rate']:
            if col in df_f.columns: df_f[col] = df_f[col].apply(clean_numeric_robust)
        for col in ['Lending_Rate', 'Outstanding', 'Nominal_Lending']:
            if col in df_l.columns: df_l[col] = df_l[col].apply(clean_numeric_robust)

        if 'Jatuh_Tempo' in df_f.columns: df_f['Jatuh_Tempo'] = pd.to_datetime(df_f['Jatuh_Tempo'], dayfirst=True, errors='coerce')
        if 'Jatuh_Tempo' in df_l.columns: df_l['Jatuh_Tempo'] = pd.to_datetime(df_l['Jatuh_Tempo'], dayfirst=True, errors='coerce')

        def robust_parse_month(p):
            p_clean = str(p).lower().replace('-', ' ').strip()
            for key, val in MONTH_LOOKUP.items():
                if key in p_clean: return val
            return 0
            
        def robust_parse_year(p):
            try:
                pts = str(p).replace('-', ' ').strip().split()
                return int(pts[1]) if len(pts) > 1 else 2026
            except Exception: return 2026

        df_f['m_idx'] = df_f['Periode'].apply(robust_parse_month)
        df_f['year_val'] = df_f['Periode'].apply(robust_parse_year)
        df_l['m_idx'] = df_l['Periode'].apply(robust_parse_month)
        df_l['year_val'] = df_l['Periode'].apply(robust_parse_year)
        
        return df_f, df_l, None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), f"Error Parse: {str(e)}"

@st.cache_data(ttl=3600)
def get_market_history():
    try:
        data = yf.Ticker("ID10Y=F").history(period="6mo")
        if not data.empty and len(data) > 10:
            df = data[['Close']].rename(columns={'Close': 'SBN_10Y'}).copy()
            return df
    except Exception: pass
    
    dates = pd.date_range(end=datetime.now(), periods=120, freq='B')
    df = pd.DataFrame(index=dates)
    df['SBN_10Y'] = np.linspace(6.4, 6.7, len(df)) + np.random.normal(0, 0.02, len(df))
    return df

# --- ENGINE SCRAPER BANK INDONESIA ---
@st.cache_data(ttl=3600)
def fetch_live_bi_rates():
    rates = {'indonia': 6.25, 'jibor_3m': 6.60, 'status': 'Manual/Fallback'}
    url = "https://www.bi.go.id/en/fungsi-utama/moneter/indonia-jibor/default.aspx"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            text = res.text.replace('&nbsp;', ' ')
            # Scrape INDONIA
            indonia_match = re.search(r'INDONIA\s*\(\%\)\s*([\d\.\,]+)', text, re.IGNORECASE)
            if indonia_match:
                rates['indonia'] = float(indonia_match.group(1).replace(',', '.'))
                rates['status'] = 'Live Auto-Scraped 🟢'
            # Scrape JIBOR 3M
            jibor_match = re.search(r'3\s*(?:Month|Bulan).*?([\d\.\,]+)', text, re.IGNORECASE)
            if jibor_match:
                rates['jibor_3m'] = float(jibor_match.group(1).replace(',', '.'))
    except Exception:
        pass
    return rates

# Panggil Scraper
live_rates = fetch_live_bi_rates()

# --- 4. SIDEBAR ---
logo_path = "ferry.png"
if os.path.exists(logo_path): st.sidebar.image(logo_path, use_container_width=True)

with st.sidebar:
    clock_html = """
    <div style="text-align: center; background-color: #f0f2f6; padding: 10px; border-radius: 8px; border: 1px solid #ddd; margin-bottom: 10px;">
        <p id="clock" style="font-family: 'Courier New', Courier, monospace; font-size: 18px; font-weight: bold; color: #1f77b4; margin: 0;"></p>
    </div>
    <script>
        function updateTime() {
            var now = new Date();
            var options = { weekday: 'long', year: 'numeric', month: 'short', day: 'numeric' };
            var dateStr = now.toLocaleDateString('id-ID', options);
            var timeStr = now.toLocaleTimeString('id-ID', { hour12: false });
            document.getElementById('clock').innerHTML = dateStr + '<br>' + timeStr + ' WIB';
        }
        setInterval(updateTime, 1000);
        updateTime();
    </script>
    """
    components.html(clock_html, height=75)

st.sidebar.markdown("---")
st.sidebar.header("📅 Periode Analisis")
sel_date = st.sidebar.date_input("Pilih Bulan & Tahun:", value=datetime(2026, 3, 1))
s_m_idx, s_y_val = int(sel_date.month), int(sel_date.year)
s_m_name = MONTH_MAP_ID[s_m_idx]

df_f_raw, df_l_raw, err = load_gsheets_data()
if err: st.error(err); st.stop()

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Market Intelligence")
hist_m = get_market_history()
sbn_val = st.sidebar.number_input("SBN 10Y Benchmark (%)", value=round(float(hist_m['SBN_10Y'].iloc[-1]), 2), step=0.01)
bareksa_val = st.sidebar.number_input("Bareksa MM (%)", value=4.75, step=0.01)
criec_val = st.sidebar.number_input("PHEI CRIEC Index (%)", value=7.20, step=0.01)

# INPUT YANG SUDAH TERISI OTOMATIS DARI SCRAPER
st.sidebar.markdown(f"**Status Data BI:** `{live_rates['status']}`")
indonia_val = st.sidebar.number_input("IndoNIA (%)", value=live_rates['indonia'], step=0.01)
jibor_val = st.sidebar.number_input("JIBOR 3M (%)", value=live_rates['jibor_3m'], step=0.01)

st.sidebar.link_button("🇮🇩 BI - Cek Web Asli", "https://www.bi.go.id/en/fungsi-utama/moneter/indonia-jibor/default.aspx", use_container_width=True)

st.sidebar.link_button("🌐 Bareksa Data", "https://www.bareksa.com/id/data", use_container_width=True)
st.sidebar.link_button("📉 PHEI (Informasi Efek)", "https://www.phei.co.id/Data/Informasi-Efek", use_container_width=True)
st.sidebar.link_button("📊 Data Source (GSheets)", "https://docs.google.com/spreadsheets/d/182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY", use_container_width=True)
st.sidebar.markdown("---")
rating = st.sidebar.selectbox("Rating Reinvestasi:", ["AAA", "AA+", "AA", "A", "BBB"])
spread_map = {"AAA": 80, "AA+": 110, "AA": 140, "A": 260, "BBB": 480}

net_sbn = sbn_val * 0.9
target_bond_net = (sbn_val + (spread_map[rating]/100)) * 0.9

# --- 5. DASHBOARD UI ---
st.title(f"🚢 ASDP Treasury & ALM Master Command Center")
tab1, tab2, tab3 = st.tabs(["💰 Modul 1: Funding", "📈 Modul 2: Lending", "📊 Modul 3: ALM Resume"])

# ==========================================
# TAB 1: FUNDING
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
        m4.metric("SBN Net Benchmark", f"{net_sbn:.2f}%")
        
        st.divider()
        c_al1, c_al2 = st.columns(2)
        with c_al1:
            st.subheader("🚩 Spread Alert (vs SBN)")
            with st.container(height=180):
                df_loss = df_f[(df_f['Rate'] * 0.8) < net_sbn]
                if not df_loss.empty:
                    for _, row in df_loss.iterrows(): 
                        b_val = row.get('No_Bilyet', '-')
                        st.error(f"**{row.get('Bank', 'Unknown')}** | Bilyet: `{b_val}` | Yield Net: `{(row.get('Rate', 0)*0.8):.2f}%`")
                else: st.success("Strategi Penempatan Optimal.")
        with c_al2:
            st.subheader("⏳ Maturity Watch (H-14)")
            with st.container(height=180):
                today = datetime.now()
                df_soon = df_f[(df_f['Jatuh_Tempo'] >= today) & (df_f['Jatuh_Tempo'] <= today + timedelta(days=14))]
                if not df_soon.empty:
                    for _, row in df_soon.iterrows(): 
                        b_val = row.get('No_Bilyet', '-')
                        st.warning(f"**{row.get('Bank', 'Unknown')}** | Bilyet: `{b_val}` | JT: `{row['Jatuh_Tempo'].strftime('%d-%m-%Y')}`")
                else: st.info("Tidak ada penempatan jatuh tempo dekat.")

        st.divider()
        st.subheader("📊 Resume Proyeksi Tambahan (Per Bulan)")
        df_proj = df_f.copy()
        df_proj['Yield_Net'] = df_proj['Rate'] * 0.8
        df_proj['Gap_SBN'] = net_sbn - df_proj['Yield_Net']
        df_proj['Potensi_SBN'] = (df_proj['Gap_SBN'] / 100) * df_proj['Nominal'] / 12
        tot_potensi_sbn = df_proj['Potensi_SBN'].sum()
        
        df_proj['Gap_Obligasi'] = target_bond_net - df_proj['Yield_Net']
        df_proj['Potensi_Obligasi'] = (df_proj['Gap_Obligasi'] / 100) * df_proj['Nominal'] / 12
        tot_potensi_obligasi = df_proj['Potensi_Obligasi'].sum()

        c_res1, c_res2 = st.columns(2)
        c_res1.metric("Proyeksi Tambahan jika ke SBN", f"Rp {tot_potensi_sbn:,.0f}")
        c_res2.metric("Proyeksi Tambahan jika ke Obligasi/Sukuk", f"Rp {tot_potensi_obligasi:,.0f}")

        st.divider()
        v1, v2 = st.columns([1.2, 1])
        with v1: st.plotly_chart(px.bar(df_f.groupby('Bank')['Rev_MtD'].sum().reset_index(), x='Bank', y='Rev_MtD', title="Revenue per Bank (MtD)", text_auto=',.0f', color='Bank'), use_container_width=True)
        with v2: st.plotly_chart(px.pie(df_f, values='Nominal', names='Bank', hole=0.5, title="Nominal Mix Placement"), use_container_width=True)
    else:
        st.warning(f"Data Funding untuk {s_m_name} {s_y_val} tidak ditemukan.")

# ==========================================
# TAB 2: LENDING
# ==========================================
with tab2:
    df_l = df_l_raw[(df_l_raw['m_idx'] == s_m_idx) & (df_l_raw['year_val'] == s_y_val)].copy()
    ytd_mask_l = (df_l_raw['year_val'] == s_y_val) & (df_l_raw['m_idx'] <= s_m_idx) & (df_l_raw['m_idx'] > 0)
    df_l_ytd = df_l_raw[ytd_mask_l].copy()

    if not df_l.empty:
        is_bunga_mtd = df_l['Tipe'].astype(str).str.contains('bunga|margin|fee', case=False, na=False)
        mtd_bunga = df_l.loc[is_bunga_mtd, 'Nominal_Lending'].sum()
        mtd_total = df_l['Nominal_Lending'].sum()
        mtd_pokok = mtd_total - mtd_bunga

        is_bunga_ytd = df_l_ytd['Tipe'].astype(str).str.contains('bunga|margin|fee', case=False, na=False)
        ytd_bunga = df_l_ytd.loc[is_bunga_ytd, 'Nominal_Lending'].sum()
        ytd_total = df_l_ytd['Nominal_Lending'].sum()
        ytd_pokok = ytd_total - ytd_bunga

        total_out = df_l.groupby('Kreditur')['Outstanding'].max().sum()
        avg_rt = np.nan_to_num(df_l['Lending_Rate'].mean())

        l1, l2, l3, l4 = st.columns(4)
        l1.metric("Total Sisa Outstanding", f"Rp {total_out:,.0f}")
        l2.metric(f"MtD Bayar ({s_m_name})", f"Rp {mtd_total:,.0f}")
        l3.metric(f"YtD Bayar (Jan-{s_m_name[:3]})", f"Rp {ytd_total:,.0f}")
        l4.metric("Avg Yield Lending", f"{avg_rt:.2f}%")

        st.divider()
        today = datetime.now()
        df_soon_l = df_l_raw[(df_l_raw['Jatuh_Tempo'] >= today) & (df_l_raw['Jatuh_Tempo'] <= today + timedelta(days=14))]
        if not df_soon_l.empty:
            st.error("⏳ **WARNING: Jatuh Tempo Tagihan Lending (H-14)**")
            df_soon_agg = df_soon_l.groupby(['Kreditur', 'Jatuh_Tempo'])['Nominal_Lending'].sum().reset_index()
            for _, row in df_soon_agg.iterrows(): st.warning(f"🏦 **{row['Kreditur']}** | JT: `{row['Jatuh_Tempo'].strftime('%d-%m-%Y')}` | Tagihan: **Rp {row['Nominal_Lending']:,.0f}**")
            st.divider()

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
                    v_bunga = b_sub.loc[b_sub['Tipe'].astype(str).str.contains('bunga|margin|fee', case=False, na=False), 'Nominal_Lending'].sum()
                    v_pokok = b_sub['Nominal_Lending'].sum() - v_bunga
                    plot_data.append({'Kreditur': b_name, 'Pokok': v_pokok, 'Bunga': v_bunga})
                    st.markdown(f"### 🏢 **{b_name}**")
                    st.caption(f"Rate: {v_rate:.2f}%")
                    st.markdown(f"* Sisa: Rp {v_out:,.0f}\n* Pokok: Rp {v_pokok:,.0f}\n* Bunga: Rp {v_bunga:,.0f}\n---\n**Total: Rp {(v_pokok + v_bunga):,.0f}**")
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
    
    ytd_mask_f = (df_f_raw['year_val'] == s_y_val) & (df_f_raw['m_idx'] <= s_m_idx) & (df_f_raw['m_idx'] > 0)
    ytd_rev = ((df_f_raw[ytd_mask_f]['Nominal'] * df_f_raw[ytd_mask_f]['Rate']) / 1200).sum()

    mtd_mask_l = (df_l_raw['year_val'] == s_y_val) & (df_l_raw['m_idx'] == s_m_idx)
    df_l_mtd = df_l_raw[mtd_mask_l].copy()
    
    ytd_mask_l = (df_l_raw['year_val'] == s_y_val) & (df_l_raw['m_idx'] <= s_m_idx) & (df_l_raw['m_idx'] > 0)
    df_l_ytd = df_l_raw[ytd_mask_l].copy()

    if not df_f.empty and not df_l_ytd.empty:
        is_bunga_ytd = df_l_ytd['Tipe'].astype(str).str.contains('bunga|margin|fee', case=False, na=False)
        ytd_bunga_out = df_l_ytd.loc[is_bunga_ytd, 'Nominal_Lending'].sum()
        
        is_bunga_mtd = df_l_mtd['Tipe'].astype(str).str.contains('bunga|margin|fee', case=False, na=False)
        mtd_pokok_out = df_l_mtd.loc[~is_bunga_mtd, 'Nominal_Lending'].sum()

        icr_val = (ytd_rev / ytd_bunga_out) if ytd_bunga_out > 0 else 0
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("YtD Interest Revenue", f"Rp {ytd_rev:,.0f}")
        c2.metric("YtD Interest Outflow", f"Rp {ytd_bunga_out:,.0f}")
        c3.metric("Net Flow Gap (Interest)", f"Rp {ytd_rev - ytd_bunga_out:,.0f}")
        c4.metric("ICR Strength (YtD)", f"{icr_val:.2f}x")
        
        st.divider()

        if mtd_pokok_out > 0:
            st.warning(f"🏦 **CASH FLOW ALERT:** Siapkan likuiditas operasional sebesar **Rp {mtd_pokok_out:,.0f}** untuk pembayaran **Pokok Pinjaman** di bulan {s_m_name} {s_y_val}.")
        else:
            st.info(f"✅ **Aman:** Tidak ada kewajiban pembayaran Pokok Pinjaman di bulan {s_m_name} {s_y_val}.")
            
        st.divider()
        
        st.subheader("⚠️ Risk Assessment")
        cr1, cr2 = st.columns(2)
        with cr1:
            st.markdown("**1. ICR Operations Check (YtD)**")
            if icr_val < 1.0:
                st.error(f"🚨 **CRITICAL RISK (ICR: {icr_val:.2f}x):** Bunga placement YtD tidak menutupi kewajiban bunga pinjaman. Potensi defisit kas operasi berlanjut!")
            elif icr_val < 1.5:
                st.warning(f"⚠️ **WARNING (ICR: {icr_val:.2f}x):** ICR cukup tipis. Pertimbangkan realokasi penempatan ke instrumen dengan yield lebih tinggi.")
            else:
                st.success(f"✅ **SAFE (ICR: {icr_val:.2f}x):** ICR sangat sehat. Pendapatan bunga menutupi kewajiban dengan buffer yang memadai.")

        with cr2:
            st.markdown("**2. Corporate Bond Reinvestment Risk**")
            if rating == "AAA":
                st.info("🛡️ **Rating AAA:** Risiko gagal bayar sangat rendah. Aman untuk penempatan dana besar, namun potensi yield sedikit tertahan.")
            elif rating in ["AA+", "AA"]:
                st.success(f"⚖️ **Rating {rating}:** Titik ekuilibrium terbaik antara keamanan (Investment Grade) dan optimalisasi spread.")
            elif rating == "A":
                st.warning("⚠️ **Rating A:** Waspada terhadap volatilitas pasar. Pastikan counterparty memiliki buffer likuiditas yang kuat.")
            elif rating == "BBB":
                st.error("🚨 **Rating BBB:** Batas bawah Investment Grade. Risiko downgrade ke *Junk Bond* terbuka lebar. Hanya untuk alokasi taktis!")

        st.divider()
        
        st.subheader("📈 6-Month Market Trend vs Live Rates")
        plot_df = hist_m.copy()
        plot_df['Bareksa'] = plot_df['SBN_10Y'] * (bareksa_val / (sbn_val if sbn_val != 0 else 1))
        plot_df['PHEI'] = plot_df['SBN_10Y'] * (criec_val / (sbn_val if sbn_val != 0 else 1))
        
        f_alm = go.Figure()
        f_alm.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SBN_10Y'], name='SBN 10Y (Hist)', line=dict(color='blue', width=3)))
        f_alm.add_trace(go.Scatter(x=plot_df.index, y=plot_df['Bareksa'], name='Bareksa MM (Hist)', line=dict(color='orange', width=2)))
        f_alm.add_trace(go.Scatter(x=plot_df.index, y=plot_df['PHEI'], name='PHEI Bond Index (Hist)', line=dict(color='red', width=3)))
        
        f_alm.add_trace(go.Scatter(x=plot_df.index, y=[indonia_val]*len(plot_df), name=f'IndoNIA Live ({indonia_val}%)', line=dict(color='purple', dash='dash', width=2)))
        f_alm.add_trace(go.Scatter(x=plot_df.index, y=[jibor_val]*len(plot_df), name=f'JIBOR 3M Live ({jibor_val}%)', line=dict(color='green', dash='dot', width=2)))
        
        f_alm.update_layout(
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis_title="Rate (%)"
        )
        st.plotly_chart(f_alm, use_container_width=True)
    else:
        st.info("Menunggu data sinkronisasi untuk menampilkan Resume ALM.")
