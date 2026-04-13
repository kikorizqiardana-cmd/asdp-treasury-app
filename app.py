import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from streamlit_lottie import st_lottie
import requests
import time
from datetime import datetime, timedelta
import base64
import os

# --- 1. CONFIG ---
st.set_page_config(page_title="ASDP Treasury Command Center", layout="wide", page_icon="🚢")

def get_base64_image(image_path):
    try:
        if os.path.exists(image_path):
            with open(image_path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode()
    except: return None
    return None

logo_path = os.path.join(os.path.dirname(__file__), 'ferry.png')
encoded_logo = get_base64_image(logo_path)

# --- DATA ENGINE (THE ULTIMATE CLEANER) ---
def clean_numeric_robust(series):
    def process_val(val):
        val = str(val).strip().replace('Rp', '').replace('%', '').replace(' ', '')
        if not val or val == 'nan' or val == 'None': return "0"
        commas, dots = val.count(','), val.count('.')
        if commas > 0 and dots > 0:
            if val.rfind(',') > val.rfind('.'): return val.replace('.', '').replace(',', '.')
            else: return val.replace(',', '')
        if commas > 0:
            if commas > 1 or len(val.split(',')[-1]) == 3: return val.replace(',', '')
            else: return val.replace(',', '.')
        if dots > 0:
            if dots > 1 or len(val.split('.')[-1]) == 3: return val.replace('.', '')
        return val
    return pd.to_numeric(series.apply(process_val), errors='coerce').fillna(0)

@st.cache_data(ttl=60)
def load_data():
    sheet_id = "182zKZj0Kr56yqOGM_XW2W3Q6fhaOSo8z9TIbjC_JxxY"
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet="
    try:
        df_f = pd.read_csv(base_url + "Funding")
        df_l = pd.read_csv(base_url + "Lending")
        df_f.columns = [c.strip() for c in df_f.columns]
        df_l.columns = [c.strip() for c in df_l.columns]
        
        # Penyelarasan Istilah Kreditur
        if 'Debitur' in df_l.columns:
            df_l.rename(columns={'Debitur': 'Kreditur'}, inplace=True)
            
        for df in [df_f, df_l]:
            for col in ['Nominal', 'Rate (%)', 'CoF (%)']:
                if col in df.columns: df[col] = clean_numeric_robust(df[col])
            if 'Periode' in df.columns: df['Periode'] = df['Periode'].astype(str).str.strip()
            if 'Jatuh_Tempo' in df.columns:
                df['Jatuh_Tempo'] = pd.to_datetime(df['Jatuh_Tempo'], dayfirst=True, errors='coerce')
        return df_f, df_l, None
    except Exception as e: return pd.DataFrame(), pd.DataFrame(), str(e)

df_f_raw, df_l_raw, error_msg = load_data()

# --- 2. SIDEBAR ---
if encoded_logo:
    st.sidebar.markdown(f'<div style="text-align: center;"><img src="data:image/png;base64,{encoded_logo}" width="200"></div>', unsafe_allow_html=True)
else:
    st.sidebar.image("https://www.indonesiaferry.co.id/img/logo.png", width=180)

st.sidebar.markdown("---")
all_periods = sorted(list(set(df_f_raw['Periode'].unique()) | set(df_l_raw['Periode'].unique())), reverse=True)
selected_month = st.sidebar.selectbox("Pilih Periode Analisis:", all_periods)

try:
    sbn_val = round(float(yf.Ticker("ID10Y=F").history(period="1d")['Close'].iloc[-1]), 2)
except: sbn_val = 6.65
current_sbn = st.sidebar.number_input("Benchmark SBN 10Y (%)", value=sbn_val, step=0.01)

df_f = df_f_raw[df_f_raw['Periode'] == selected_month].copy()
df_l = df_l_raw[df_l_raw['Periode'] == selected_month].copy()

# --- 3. DASHBOARD UI ---
st.title(f"🚢 ASDP Treasury Command Center")
tab1, tab2, tab3 = st.tabs(["💰 Funding Monitor", "💸 Loan Payment (Debt)", "📊 ALM Net Position"])

# ==========================================
# WS 1: FUNDING (Uang Masuk)
# ==========================================
with tab1:
    st.header(f"Intelligence Funding - {selected_month}")
    if not df_f.empty:
        df_f['Net_Yield_Rate'] = df_f['Rate (%)'] * 0.8
        net_sbn = current_sbn * 0.9
        df_f['Monthly_Yield'] = (df_f['Nominal'] * (df_f['Rate (%)'] / 100)) / 12
        
        # Alerts
        c_a1, c_a2 = st.columns(2)
        with c_a1:
            st.markdown("**🚨 Underperform Alert**")
            with st.container(height=180):
                under = df_f[df_f['Net_Yield_Rate'] < net_sbn]
                if not under.empty:
                    for _, row in under.iterrows(): st.error(f"**{row['Bank']}** | Gap: {net_sbn - row['Net_Yield_Rate']:.2f}%")
                else: st.success("Rate aman.")
        with c_a2:
            st.markdown("**⏳ Jatuh Tempo (H-7)**")
            with st.container(height=180):
                today = datetime.now()
                soon = df_f[(df_f['Jatuh_Tempo'] >= today) & (df_f['Jatuh_Tempo'] <= today + timedelta(days=7))]
                if not soon.empty:
                    for _, row in soon.iterrows(): st.warning(f"**{row['Bank']}** | {row['Jatuh_Tempo'].strftime('%d-%m-%Y')}")
                else: st.info("Tidak ada jatuh tempo dekat.")

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Placement", f"Rp {df_f['Nominal'].sum():,.0f}")
        m2.metric("Total Yield (B)", f"Rp {df_f['Monthly_Yield'].sum()/1e9:.2f} B")
        m3.metric("SBN Net Benchmark", f"{net_sbn:.2f}%")
        
        # Chart
        df_bank = df_f.groupby('Bank')['Monthly_Yield'].sum().reset_index()
        fig = px.bar(df_bank, x='Bank', y=df_bank['Monthly_Yield']/1e9, color='Bank', text_auto='.2f', title="Penerimaan Bunga per Bank (Rp Billion)")
        fig.update_traces(texttemplate='%{y:.2f} B', textposition='outside')
        fig.update_layout(showlegend=False, yaxis_title="Rp Billion")
        st.plotly_chart(fig, use_container_width=True)

# ==========================================
# WS 2: LOAN PAYMENT (Uang Keluar)
# ==========================================
with tab2:
    st.header(f"Monitoring Kewajiban Pembayaran - {selected_month}")
    if not df_l.empty:
        df_l['Tipe'] = df_l['Tipe'].astype(str).str.strip().str.capitalize()
        total_out = df_l['Nominal'].sum()
        bunga_out = df_l[df_l['Tipe'] == 'Bunga']['Nominal'].sum()
        pokok_out = df_l[df_l['Tipe'] == 'Pokok']['Nominal'].sum()

        # DEBT ALERTS
        st.subheader("⚠️ Debt Service Monitoring")
        c_l1, c_l2 = st.columns(2)
        with c_l1:
            st.markdown("**🚨 Jadwal Pembayaran H-7 (Siapkan Dana!)**")
            with st.container(height=200):
                today = datetime.now()
                due = df_l[(df_l['Jatuh_Tempo'] >= today) & (df_l['Jatuh_Tempo'] <= today + timedelta(days=7))]
                if not due.empty:
                    for _, row in due.iterrows():
                        st.error(f"**{row['Kreditur']}** | Rp {row['Nominal']:,.0f} ({row['Tipe']}) | Jatuh Tempo: {row['Jatuh_Tempo'].strftime('%d-%m-%Y')}")
                else: st.success("Tidak ada jadwal bayar kritis dalam 7 hari.")
        with c_l2:
            st.markdown("**📉 Eksposur Kreditur Terbesar**")
            with st.container(height=200):
                top_k = df_l.groupby('Kreditur')['Nominal'].sum().idxmax()
                st.warning(f"Kreditur dengan kewajiban tertinggi: **{top_k}**")
                st.write("Pastikan likuiditas di rekening bank terkait sudah mencukupi sebelum jatuh tempo.")

        st.divider()
        l1, l2, l3 = st.columns(3)
        l1.metric("Total Uang Keluar", f"Rp {total_out:,.0f}")
        l2.metric("Beban Bunga (B)", f"Rp {bunga_out/1e9:.2f} B")
        l3.metric("Pelunasan Pokok (B)", f"Rp {pokok_out/1e9:.2f} B")

        # Chart
        st.markdown("### 📊 Rekonsiliasi Pembayaran per Kreditur")
        fig_l = px.bar(df_l, x='Kreditur', y=df_l['Nominal']/1e9, color='Tipe', barmode='stack', title="Kewajiban Pokok & Bunga (Rp Billion)", text_auto='.2f')
        fig_l.update_traces(texttemplate='%{y:.2f} B', textposition='outside')
        fig_l.update_layout(yaxis_title="Rp Billion")
        st.plotly_chart(fig_l, use_container_width=True)

        with st.expander("Lihat Detail Tabel Kewajiban"):
            df_l_disp = df_l.copy()
            if 'Jatuh_Tempo' in df_l_disp.columns:
                df_l_disp['Jatuh_Tempo'] = df_l_disp['Jatuh_Tempo'].dt.strftime('%d-%m-%Y')
            st.dataframe(df_l_disp, use_container_width=True)

# ==========================================
# WS 3: ALM NET POSITION
# ==========================================
with tab3:
    st.header("Asset Liability Management & Strategic Projection")
    inc_bunga = df_f['Monthly_Yield'].sum() if not df_f.empty else 0
    exp_bunga = df_l[df_l['Tipe'] == 'Bunga']['Nominal'].sum() if not df_l.empty else 0
    net_interest = inc_bunga - exp_bunga
    
    st.subheader("💰 Net Interest Position (Bulan Ini)")
    p1, p2, p3 = st.columns(3)
    p1.metric("Bunga Masuk (Asset)", f"Rp {inc_bunga:,.0f}")
    p2.metric("Bunga Keluar (Liability)", f"Rp {exp_bunga:,.0f}")
    p3.metric("Net Interest Position", f"Rp {net_interest:,.0f}", delta=f"{net_interest:,.0f}", delta_color="normal")

    st.divider()
    
    st.subheader("🛡️ Strategic Simulation Tool")
    choice = st.selectbox("Simulasi Optimalisasi Dana (Rating):", ["AAA", "AA", "A", "BBB"])
    spreads = {"AAA": 0.8, "AA": 1.3, "A": 2.5, "BBB": 4.0}
    target_net = (current_sbn + spreads[choice]) * 0.9
    if not df_f.empty:
        potensi_duit = (df_f['Nominal'].sum() * ((target_net - (df_f['Net_Yield_Rate'].mean()))/100)) / 12
        st.success(f"Jika dioptimalkan ke rating **{choice}**, potensi tambahan laba bunga adalah **Rp {potensi_duit:,.0f}** per bulan.")
