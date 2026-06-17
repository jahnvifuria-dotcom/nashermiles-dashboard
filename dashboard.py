import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="NM Offline Stores", layout="wide", page_icon="NM")

# ── Load ──────────────────────────────────────────────────────────────────────
@st.cache_data
def load():
    from data_prep import load_all, generate_insights, STORE_ORDER, STORE_COLORS, STORE_SHORT, _month_sort_key
    monthly, sku, daily = load_all()
    insights = generate_insights(monthly, sku)
    return monthly, sku, daily, insights, STORE_ORDER, STORE_COLORS, STORE_SHORT, _month_sort_key

try:
    monthly, sku, daily, insights, STORE_ORDER, STORE_COLORS, STORE_SHORT, _msk = load()
except Exception as e:
    st.error(f"Failed to load data: {e}")
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### NM Offline Dashboard")
    if st.button("Refresh Data", use_container_width=True):
        load.clear(); st.rerun()
    st.divider()

    all_stores = [s for s in STORE_ORDER if s in monthly['Store'].unique()]
    sel_stores = st.multiselect("Stores", all_stores, default=all_stores)

    # Month range — two dropdowns, start padded to Apr 2025
    all_periods = sorted(monthly['Month_dt'].unique())
    start_period = pd.Period('2025-04', freq='M')
    display_periods = sorted(set([start_period] + list(all_periods)))
    month_labels = [p.strftime('%b %Y') for p in display_periods]
    col_lo, col_hi = st.columns(2)
    with col_lo:
        sel_lo = st.selectbox("From", month_labels, index=0, key='month_lo')
    with col_hi:
        sel_hi = st.selectbox("To", month_labels, index=len(month_labels)-1, key='month_hi')
    lo = _msk(sel_lo)
    hi = _msk(sel_hi)
    st.divider()
    st.caption("Source: DSR cache + Store Dashboard")

# ── Filter ────────────────────────────────────────────────────────────────────
mf = monthly[monthly['Store'].isin(sel_stores) &
             (monthly['Month_dt'] >= lo) & (monthly['Month_dt'] <= hi)].copy()
sf = sku[sku['Store'].isin(sel_stores) &
         (sku['Month_dt'] >= lo) & (sku['Month_dt'] <= hi)].copy()
df_daily = daily[daily['Store'].isin(sel_stores) &
                 daily['Month_dt'].apply(lambda p: lo <= p <= hi)].copy()

if mf.empty:
    st.warning("No data for selected filters.")
    st.stop()

mf = mf.sort_values('Month_dt')
mf['Month_label'] = mf['Month_dt'].apply(lambda p: p.strftime('%b %Y'))

# ── Header KPIs ───────────────────────────────────────────────────────────────
st.markdown("## Nasher Miles — Offline Store Performance")
tot_sales = mf['Net_Sales'].sum()
tot_units = mf['Units'].sum()
tot_spend = mf['Total Spend'].sum()
avg_asp   = tot_sales / tot_units if tot_units > 0 else 0
roas      = tot_sales / tot_spend if tot_spend > 0 else 0

k1,k2,k3,k4,k5 = st.columns(5)
k1.metric("Net Sales",      f"Rs.{tot_sales/1e5:.1f}L")
k2.metric("Units Sold",     f"{int(tot_units):,}")
k3.metric("Avg ASP",        f"Rs.{avg_asp:,.0f}")
k4.metric("Ad Spend",       f"Rs.{tot_spend/1e5:.1f}L")
k5.metric("Sales / Spend",  f"{roas:.1f}x" if tot_spend > 0 else "N/A")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_names = ["Overview", "Store Compare", "SKU Analysis", "Daily View", "Insights"] + \
            [STORE_SHORT.get(s, s) for s in all_stores]
tabs = st.tabs(tab_names)

# helper
def fmt_inr(x): return f"Rs.{x:,.0f}" if pd.notna(x) and x else "—"


# ══════════════════════════════════════════════════════════════════════════════
# TAB 0 — OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
with tabs[0]:
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Net Sales by Store")
        fig = px.line(mf, x='Month_label', y='Net_Sales', color='Store',
                      markers=True, color_discrete_map=STORE_COLORS,
                      labels={'Net_Sales': 'Net Sales (Rs.)', 'Month_label': ''},
                      category_orders={'Store': STORE_ORDER})
        fig.update_layout(height=340, margin=dict(t=10,b=10),
                          legend=dict(orientation='h', y=-0.28, font=dict(size=10)))
        fig.update_yaxes(tickformat=',.0f')
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Units Sold")
        fig2 = px.bar(mf, x='Month_label', y='Units', color='Store',
                      barmode='group', color_discrete_map=STORE_COLORS,
                      labels={'Units': 'Units', 'Month_label': ''},
                      category_orders={'Store': STORE_ORDER})
        fig2.update_layout(height=340, margin=dict(t=10,b=10),
                           legend=dict(orientation='h', y=-0.28, font=dict(size=10)))
        st.plotly_chart(fig2, use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("Walk-ins & Conversion Rate")
        wi_df = mf[mf['Walkins'].notna() & mf['Conv Rate'].notna()].copy()
        if wi_df.empty:
            st.info("No walk-in data for selected range/stores.")
        else:
            fig3 = make_subplots(specs=[[{"secondary_y": True}]])
            for store in sel_stores:
                s_df = wi_df[wi_df['Store'] == store].sort_values('Month_dt')
                if s_df.empty: continue
                fig3.add_trace(go.Bar(x=s_df['Month_label'], y=s_df['Walkins'],
                    name=f'{STORE_SHORT.get(store,store)} Walk-ins',
                    marker_color=STORE_COLORS.get(store,'#888'), opacity=0.55,
                ), secondary_y=False)
                fig3.add_trace(go.Scatter(x=s_df['Month_label'],
                    y=(s_df['Conv Rate']*100).round(1),
                    name=f'{STORE_SHORT.get(store,store)} Conv%',
                    mode='lines+markers',
                    line=dict(color=STORE_COLORS.get(store,'#888'), dash='dot', width=2),
                ), secondary_y=True)
            fig3.update_yaxes(title_text="Walk-ins", secondary_y=False)
            fig3.update_yaxes(title_text="Conv Rate %", secondary_y=True, ticksuffix='%')
            fig3.update_layout(height=340, margin=dict(t=10,b=10), barmode='group',
                               legend=dict(orientation='h', y=-0.28, font=dict(size=9)))
            st.plotly_chart(fig3, use_container_width=True)

    with c4:
        st.subheader("Sales / Spend Efficiency")
        sp_df = mf[mf['Sales/Spend'].notna()].copy()
        if sp_df.empty:
            st.info("No spend data for selected range.")
        else:
            fig4 = px.line(sp_df, x='Month_label', y='Sales/Spend', color='Store',
                           markers=True, color_discrete_map=STORE_COLORS,
                           labels={'Sales/Spend': 'Rs. Sales per Rs.1 Spend', 'Month_label': ''})
            fig4.add_hline(y=1, line_dash='dash', line_color='red',
                           annotation_text='Break-even (1x)')
            fig4.update_layout(height=340, margin=dict(t=10,b=10),
                               legend=dict(orientation='h', y=-0.28, font=dict(size=10)))
            st.plotly_chart(fig4, use_container_width=True)

    # ASP
    st.subheader("ASP Trend")
    asp_df = mf[mf['ASP'].notna() & (mf['ASP'] > 0)]
    fig5 = px.line(asp_df, x='Month_label', y='ASP', color='Store',
                   markers=True, color_discrete_map=STORE_COLORS,
                   labels={'ASP': 'ASP (Rs.)', 'Month_label': ''},
                   category_orders={'Store': STORE_ORDER})
    fig5.update_layout(height=300, margin=dict(t=10,b=10),
                       legend=dict(orientation='h', y=-0.3, font=dict(size=10)))
    fig5.update_yaxes(tickformat=',.0f')
    st.plotly_chart(fig5, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — STORE COMPARE
# ══════════════════════════════════════════════════════════════════════════════
with tabs[1]:
    st.subheader("Period Totals")
    summary = (mf.groupby('Store').agg(
        Net_Sales=('Net_Sales','sum'), Units=('Units','sum'),
        Meta_Spend=('Meta Spend','sum'), Google_Spend=('Google Spend','sum'),
        Total_Spend=('Total Spend','sum'), Months=('Month_label','count'),
        Total_Walkins=('Walkins','sum'), Total_Conversions=('Conversions','sum'),
        Avg_Conv=('Conv Rate','mean'),
    ).reset_index())
    summary['ASP']         = (summary['Net_Sales']/summary['Units'].replace(0,np.nan)).round(0)
    summary['Sales/Spend'] = (summary['Net_Sales']/summary['Total_Spend'].replace(0,np.nan)).round(2)
    # Recalculate conversion rate from totals (more accurate than avg of monthly rates)
    summary['Conv_Rate_calc'] = (summary['Total_Conversions'] / summary['Total_Walkins'].replace(0,np.nan))
    summary['Store_order'] = summary['Store'].map({s:i for i,s in enumerate(STORE_ORDER)}).fillna(99)
    summary = summary.sort_values('Store_order').drop(columns='Store_order')

    disp = summary[['Store','Net_Sales','Units','ASP','Total_Spend','Sales/Spend',
                    'Total_Walkins','Total_Conversions','Conv_Rate_calc','Months']].copy()
    disp.columns = ['Store','Net Sales','Units','ASP','Total Spend','Sales/Spend',
                    'Walk-ins','Conversions','Conv Rate','Months']
    for c in ['Net Sales','Total Spend']:
        disp[c] = disp[c].apply(lambda x: fmt_inr(x) if pd.notna(x) else '—')
    disp['ASP']         = disp['ASP'].apply(lambda x: fmt_inr(x) if pd.notna(x) else '—')
    disp['Sales/Spend'] = disp['Sales/Spend'].apply(lambda x: f"{x:.1f}x" if pd.notna(x) else '—')
    disp['Walk-ins']    = disp['Walk-ins'].apply(lambda x: f"{int(x):,}" if pd.notna(x) and x > 0 else '—')
    disp['Conversions'] = disp['Conversions'].apply(lambda x: f"{int(x):,}" if pd.notna(x) and x > 0 else '—')
    disp['Conv Rate']   = disp['Conv Rate'].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else '—')
    st.dataframe(disp, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Revenue Share")
    fig_pie = px.pie(summary, values='Net_Sales', names='Store', hole=0.45,
                     color='Store', color_discrete_map=STORE_COLORS)
    fig_pie.update_traces(textinfo='percent', textposition='inside', textfont_size=11)
    fig_pie.update_layout(height=360, margin=dict(t=10,b=10),
                          showlegend=True,
                          legend=dict(orientation='v', x=1.02, y=0.5, font=dict(size=11)))
    st.plotly_chart(fig_pie, use_container_width=True)

    # helper: heatmap that shows blank for NaN, not 0
    def _fmt_lakh(v):
        if np.isnan(v): return ''
        if v >= 1e5:  return f"{v/1e5:.1f}L"
        if v >= 1e3:  return f"{v/1e3:.0f}K"
        return f"{v:.0f}"

    def _heatmap(piv, colorscale, fmt, title, height_per_row=52):
        piv.columns.name = None
        vals = piv.values.astype(float)
        if fmt == 'lakh':
            text = [[_fmt_lakh(v) for v in row] for row in vals]
        elif fmt == '.0f':
            text = [[f"{v:.0f}" if not np.isnan(v) else '' for v in row] for row in vals]
        elif fmt == '.1f':
            text = [[f"{v:.1f}" if not np.isnan(v) else '' for v in row] for row in vals]
        else:
            text = [[f"{v:.3g}" if not np.isnan(v) else '' for v in row] for row in vals]
        fig = go.Figure(go.Heatmap(
            z=vals, x=list(piv.columns), y=list(piv.index),
            text=text, texttemplate='%{text}',
            colorscale=colorscale, showscale=False,
            xgap=2, ygap=2,
        ))
        fig.update_layout(height=max(220, len(piv)*height_per_row+80),
                          margin=dict(t=10,b=10))
        fig.update_xaxes(tickangle=-30)
        return fig

    sorted_months = sorted(mf['Month_label'].unique(), key=_msk)
    store_idx = [s for s in STORE_ORDER if s in mf['Store'].unique()]

    st.subheader("Net Sales Heatmap (Store x Month)")
    pivot = (mf.pivot_table(index='Store', columns='Month_label', values='Net_Sales', aggfunc='sum')
               .reindex(index=store_idx).reindex(columns=sorted_months))
    st.plotly_chart(_heatmap(pivot, 'YlOrRd', 'lakh', 'Net Sales'), use_container_width=True)

    wi_piv = (mf.pivot_table(index='Store', columns='Month_label', values='Walkins', aggfunc='sum')
                .reindex(index=store_idx).reindex(columns=sorted_months))
    if wi_piv.notna().any().any():
        st.subheader("Walk-ins Heatmap")
        st.plotly_chart(_heatmap(wi_piv, 'Blues', '.0f', 'Walk-ins'), use_container_width=True)

    conv_piv = (mf.pivot_table(index='Store', columns='Month_label', values='Conv Rate', aggfunc='mean')
                  .reindex(index=store_idx).reindex(columns=sorted_months))
    if conv_piv.notna().any().any():
        st.subheader("Conversion Rate Heatmap")
        st.plotly_chart(_heatmap(conv_piv * 100, 'Greens', '.1f', 'Conv %'), use_container_width=True)


# SKU category mapping (sourced from Shopify productType via API)
import json as _json
_SHOPIFY_MAP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'shopify_range_map.json')
try:
    with open(_SHOPIFY_MAP_PATH) as _f:
        _SHOPIFY_RANGE_MAP = _json.load(_f)
except Exception:
    _SHOPIFY_RANGE_MAP = {}

_RANGE_LOOKUP = {}
for _cat, _ranges in _SHOPIFY_RANGE_MAP.items():
    for _r in _ranges:
        _RANGE_LOOKUP[_r.lower().replace(" ", "")] = _cat

def _sku_to_range(sku_str):
    if not isinstance(sku_str, str): return "Other"
    sl = sku_str.lower()
    if "backpack" in sl or "sling" in sl: return "Backpack"
    if "toiletry" in sl or "toilet" in sl: return "Travel Accessories"
    if "neck" in sl or "pillow" in sl: return "Travel Accessories"
    if "cover" in sl and "luggage" in sl: return "Travel Accessories"
    if "house" in sl and "pride" in sl: return "Backpack"
    import re as _re
    cleaned = _re.sub(r'(?i)^(luggage_|lugcover_|lug_|nm_)+', '', sku_str)
    parts = _re.split(r'[_\s/]+', cleaned)
    candidates = parts + ([parts[0]+parts[1]] if len(parts) > 1 else [])
    for p in candidates:
        key = p.lower().replace(" ", "")
        if key in _RANGE_LOOKUP:
            return _RANGE_LOOKUP[key]
        for rk, cat in _RANGE_LOOKUP.items():
            if len(key) >= 6 and rk.startswith(key):
                return cat
    return "Other"


_CODE_TO_RANGE = {
    'S2090': 'Silicon Valley', '1304': 'Paris', 'PP05': 'Boston',
    'DL901': 'Oslo', 'DHP106': 'Goa', 'A849': 'Bruges',
    'H167': 'Venice', '1308': 'Antwerp', 'BS0522': 'Berlin',
    'PP13': 'Krabi', 'PP08': 'Singapore', 'PP06': 'Istanbul',
    'PP07': 'Vienna', 'PP09': 'Vegas', 'PP10': 'Chicago',
    'PP021': 'Montreal', 'A6608': 'Springfield',
    'Spring': 'Springfield Plus',
    'PP001': 'Coorg', 'PP01': 'The Line', 'PP8002': 'Seattle', 'Quiddle': 'Quidditch', 'H116': 'Denver', 'H166': 'Denver', 'Line': 'The Line',
    'TTT': 'Tic Tac Toe', 'Zoo': 'Tic Tac Toe',
    'Teck': 'Tech Kit', 'Tech': 'Tech Kit', 'HP': 'House Pride', 'Hawai': 'Hawaii',
    'Haffepuff': 'Haffepuff', 'DL964': 'Oslo', 'PackingCube': 'Packing Cubes', 'PackingCubes': 'Packing Cubes',
    'Toiletry': 'Toiletry Kit', 'ToiletryKit': 'Toiletry Kit', 'ToiletryKit2': 'Toiletry Kit',
}
_CODE_TO_RANGE_UPPER = {k.upper(): v for k, v in _CODE_TO_RANGE.items()}
_SKU_SKIP = {'NM', 'LUG', 'LG', 'SET', 'OF', 'PLUS', ''}

def _sku_to_range_name(sku_str):
    if not isinstance(sku_str, str): return 'Other'
    import re as _re
    # strip NMB80753CEA-NM_ style barcoded prefixes, then lug_/nm_ prefixes
    cleaned = _re.sub(r'(?i)^[A-Z0-9]+-NM_', '', sku_str)
    cleaned = _re.sub(r'(?i)^(lug_|nm_)+', '', cleaned)
    parts = _re.split(r'[_\s/\-]+', cleaned)
    # check product codes first (case-insensitive)
    for p in parts:
        if p.upper() in _CODE_TO_RANGE_UPPER:
            return _CODE_TO_RANGE_UPPER[p.upper()]
    # check bigrams against range lookup (handles "Silicon Valley", "The Line", etc.)
    for i in range(len(parts) - 1):
        key = (parts[i] + parts[i+1]).lower()
        if key in _RANGE_LOOKUP:
            return parts[i] + ' ' + parts[i+1]
    for p in parts:
        pu = p.upper()
        if p and pu not in _SKU_SKIP and not p.isdigit() and len(p) > 2:
            if _re.match(r'^[SML]\d?$', p) or _re.match(r'^\d{2}$', p):
                continue
            if _re.match(r'^[A-Z0-9]{5,}$', pu) and any(c.isdigit() for c in pu):
                continue
            return p
    return parts[0] if parts else 'Other'


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — SKU ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
with tabs[2]:
    # ── Filters row ──────────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4 = st.columns([2,2,2,2])
    with fc1:
        sku_store = st.selectbox("Store", ['All Stores'] + sel_stores, key='sku_store')
    with fc2:
        av_m = ['All Months'] + sorted(sf['Month'].unique(), key=_msk)
        sku_month = st.selectbox("Month", av_m, key='sku_month')
    with fc3:
        coll_opts = ['All Categories'] + sorted(sf['SKU'].apply(_sku_to_range).unique())
        sku_coll  = st.selectbox("Category", coll_opts, key='sku_coll')
    with fc4:
        sort_by = st.selectbox("Sort by", ['Net Sales','Units','ASP'], key='sku_sort')

    sf2 = sf.copy()
    sf2['Category'] = sf2['SKU'].apply(_sku_to_range)
    sf2['Range']    = sf2['SKU'].apply(_sku_to_range_name)
    if sku_store != 'All Stores': sf2 = sf2[sf2['Store']==sku_store]
    if sku_month != 'All Months': sf2 = sf2[sf2['Month']==sku_month]
    if sku_coll  != 'All Categories': sf2 = sf2[sf2['Category']==sku_coll]

    sort_col_map = {'Net Sales': 'Net_Sales', 'Units': 'Units', 'ASP': 'ASP_num'}
    top_agg = (sf2.groupby(['SKU','Category','Range'])
                  .agg(Units=('Units','sum'), Net_Sales=('Net Sales','sum'))
                  .reset_index())
    top_agg['ASP_num'] = (top_agg['Net_Sales'] / top_agg['Units'].replace(0, np.nan)).round(0)
    top_agg = top_agg.sort_values(sort_col_map[sort_by], ascending=False)

    top20 = top_agg.head(20)

    if top20.empty:
        st.info("No SKU data.")
    else:
        st.subheader(f"Top 20 SKUs — {sku_store} | {sku_month} | {sku_coll}")
        ca, cb = st.columns([3,2])
        with ca:
            fig_sku = px.bar(top20.sort_values('Net_Sales'), x='Net_Sales', y='SKU',
                             orientation='h', color='Category',
                             labels={'Net_Sales':'Net Sales (Rs.)','SKU':''},
                             color_discrete_sequence=px.colors.qualitative.Safe)
            fig_sku.update_layout(height=max(420, len(top20)*26+80), margin=dict(t=10,b=10,l=10),
                                  legend=dict(orientation='h', y=-0.15, font=dict(size=10)))
            fig_sku.update_xaxes(tickformat=',.0f')
            st.plotly_chart(fig_sku, use_container_width=True)
        with cb:
            d2 = top20.copy()
            d2['Net Sales'] = d2['Net_Sales'].apply(fmt_inr)
            d2['ASP']       = d2['ASP_num'].apply(lambda x: fmt_inr(x) if pd.notna(x) else '—')
            st.dataframe(d2[['SKU','Category','Units','Net Sales','ASP']],
                         use_container_width=True, hide_index=True,
                         height=max(420, len(top20)*28+40))

    # ── Category & Range summary + Pie chart ─────────────────────────────────
    st.divider()
    st.subheader("Sales by Category & Range")

    cat_agg = (sf2.groupby('Category')
                  .agg(Units=('Units','sum'), Net_Sales=('Net Sales','sum'))
                  .reset_index()
                  .sort_values('Net_Sales', ascending=False))
    cat_agg['Net Sales'] = cat_agg['Net_Sales'].apply(fmt_inr)
    cat_agg['Share %']   = (cat_agg['Net_Sales'] / cat_agg['Net_Sales'].sum() * 100).round(1).astype(str) + '%'

    rng_agg = (sf2.groupby(['Category','Range'])
                  .agg(Units=('Units','sum'), Net_Sales=('Net Sales','sum'))
                  .reset_index()
                  .sort_values('Net_Sales', ascending=False))
    rng_agg['Net Sales'] = rng_agg['Net_Sales'].apply(fmt_inr)

    pie_data = sf2.groupby('Category')['Net Sales'].sum().reset_index()
    fig_pie = px.pie(pie_data, values='Net Sales', names='Category',
                     color_discrete_sequence=px.colors.qualitative.Safe,
                     hole=0.4)
    fig_pie.update_traces(textposition='inside', textinfo='percent',
                          textfont_size=12)
    fig_pie.update_layout(height=420, margin=dict(t=20, b=20, l=10, r=160),
                          showlegend=True,
                          legend=dict(orientation='v', x=1.02, y=0.5, font=dict(size=12)))
    st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("**By Category**")
    st.dataframe(cat_agg[['Category','Units','Net Sales','Share %']],
                 use_container_width=True, hide_index=True)

    st.markdown("**By Range**")
    st.dataframe(rng_agg[['Category','Range','Units','Net Sales']],
                 use_container_width=True, hide_index=True)

    # ── Full SKU Table ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("All SKU Data")
    tbl = top_agg.copy()
    tbl['Net Sales'] = tbl['Net_Sales'].apply(fmt_inr)
    tbl['ASP']       = tbl['ASP_num'].apply(lambda x: fmt_inr(x) if pd.notna(x) else '—')
    st.caption(f"{len(tbl):,} SKU rows — sorted by {sort_by}. Use filters above to narrow down.")
    st.dataframe(
        tbl[['SKU','Category','Range','Units','Net Sales','ASP']],
        use_container_width=True, hide_index=True,
        column_config={
            'SKU':      st.column_config.TextColumn('SKU', width='large'),
            'Category': st.column_config.TextColumn('Category'),
            'Range':    st.column_config.TextColumn('Range'),
            'Units':    st.column_config.NumberColumn('Units', format='%d'),
            'Net Sales':st.column_config.TextColumn('Net Sales'),
            'ASP':      st.column_config.TextColumn('ASP'),
        },
        height=500,
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — DAILY VIEW
# ══════════════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.subheader("Daily Net Sales (DSR Cache)")
    if df_daily.empty:
        st.info("No daily data for filters.")
    else:
        dag = (df_daily.groupby(['Store','Date'])
               .agg(Net_Sales=('Net','sum'), Units=('Qty','sum'))
               .reset_index().sort_values('Date'))
        fig_d = px.bar(dag, x='Date', y='Net_Sales', color='Store',
                       barmode='stack', color_discrete_map=STORE_COLORS,
                       labels={'Net_Sales':'Net Sales (Rs.)'},
                       category_orders={'Store': STORE_ORDER})
        fig_d.update_layout(height=380, margin=dict(t=10,b=10),
                            legend=dict(orientation='h', y=-0.2))
        fig_d.update_yaxes(tickformat=',.0f')
        st.plotly_chart(fig_d, use_container_width=True)

        st.subheader("Daily Drill-down")
        d_store = st.selectbox("Store", sel_stores, key='ds')
        d_df = (df_daily[df_daily['Store']==d_store]
                .groupby('Date').agg(Net_Sales=('Net','sum'), Units=('Qty','sum'), SKUs=('SKU','nunique'))
                .reset_index().sort_values('Date', ascending=False))
        d_df['Net Sales'] = d_df['Net_Sales'].apply(fmt_inr)
        d_df['Date_str']  = d_df['Date'].dt.strftime('%d %b %Y')
        st.dataframe(d_df[['Date_str','Net Sales','Units','SKUs']].rename(columns={'Date_str':'Date'}),
                     use_container_width=True, hide_index=True)

        d_dates = sorted(df_daily[df_daily['Store']==d_store]['Date'].dt.date.unique(), reverse=True)
        if d_dates:
            sel_date = st.selectbox("Date for SKU breakdown", d_dates, key='dd')
            drill = (df_daily[(df_daily['Store']==d_store) & (df_daily['Date'].dt.date==sel_date)]
                     .groupby('SKU').agg(Units=('Qty','sum'), Net_Sales=('Net','sum'))
                     .sort_values('Net_Sales', ascending=False).reset_index())
            drill['ASP']       = (drill['Net_Sales']/drill['Units'].replace(0,np.nan)).round(0).apply(fmt_inr)
            drill['Net Sales'] = drill['Net_Sales'].apply(fmt_inr)
            st.dataframe(drill[['SKU','Units','Net Sales','ASP']], use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════
with tabs[4]:
    st.subheader("Auto-Generated Insights")

    TYPE_COLOR = {
        'top':        '#1F77B4',
        'efficiency': '#2CA02C',
        'trend':      '#FF7F0E',
        'product':    '#9467BD',
        'conversion': '#17BECF',
        'warning':    '#D62728',
    }
    for ins in insights:
        color = TYPE_COLOR.get(ins['type'], '#888')
        st.markdown(f"""
<div style="border-left:4px solid {color}; padding:10px 16px; margin-bottom:12px;
            background:#f9f9f9; border-radius:4px;">
  <strong>{ins['title']}</strong><br>
  <span style="color:#444; font-size:0.9em;">{ins['body']}</span>
</div>
""", unsafe_allow_html=True)

    st.divider()
    # MoM table
    st.subheader("Month-on-Month Summary (All Stores)")
    months = sorted(monthly['Month_dt'].unique())
    if len(months) >= 2:
        mom_rows = []
        for i in range(1, len(months)):
            cur_p, prev_p = months[i], months[i-1]
            for store in STORE_ORDER:
                cur_v  = monthly[(monthly['Store']==store) & (monthly['Month_dt']==cur_p)]['Net_Sales'].sum()
                prev_v = monthly[(monthly['Store']==store) & (monthly['Month_dt']==prev_p)]['Net_Sales'].sum()
                if cur_v == 0 and prev_v == 0: continue
                mom = (cur_v - prev_v) / prev_v * 100 if prev_v > 0 else np.nan
                mom_rows.append({
                    'Store': STORE_SHORT.get(store, store),
                    'Month': cur_p.strftime('%b %Y'),
                    'Net Sales': fmt_inr(cur_v),
                    'Prev Month': fmt_inr(prev_v),
                    'MoM %': f"{mom:+.1f}%" if pd.notna(mom) else 'New',
                })
        if mom_rows:
            mom_df = pd.DataFrame(mom_rows)
            # Latest month first
            mom_df['_m'] = mom_df['Month'].apply(_msk)
            mom_df = mom_df.sort_values(['_m','Store'], ascending=[False, True]).drop(columns='_m')
            st.dataframe(mom_df, use_container_width=True, hide_index=True)

    # Top SKUs network wide
    st.subheader("Top 15 SKUs — Network Wide")
    net_top = (sf.groupby('SKU').agg(Units=('Units','sum'), Net_Sales=('Net Sales','sum'))
                 .sort_values('Net_Sales', ascending=False).head(15).reset_index())
    net_top['ASP']       = (net_top['Net_Sales']/net_top['Units'].replace(0,np.nan)).round(0).apply(fmt_inr)
    net_top['Net Sales'] = net_top['Net_Sales'].apply(fmt_inr)
    st.dataframe(net_top[['SKU','Units','Net Sales','ASP']], use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# STORE-SPECIFIC TABS (one per store)
# ══════════════════════════════════════════════════════════════════════════════
for tab_i, store in enumerate(all_stores):
    with tabs[5 + tab_i]:
        sdf  = mf[mf['Store'] == store].sort_values('Month_dt')
        s_sk = sf[sf['Store'] == store]
        s_da = df_daily[df_daily['Store'] == store]
        color = STORE_COLORS.get(store, '#1F77B4')

        if sdf.empty:
            st.info(f"No data for {store} in selected range.")
            continue

        # Store header KPIs
        t_sales = sdf['Net_Sales'].sum()
        t_units = sdf['Units'].sum()
        t_spend = sdf['Total Spend'].sum()
        t_asp   = t_sales / t_units if t_units > 0 else 0
        t_roas  = t_sales / t_spend if t_spend > 0 else 0
        avg_wi  = sdf['Walkins'].mean()
        avg_cv  = sdf['Conv Rate'].mean()

        st.markdown(f"### {store}")
        st.caption(f"{sdf['City'].iloc[0]}  |  {len(sdf)} months of data")

        m1,m2,m3,m4,m5,m6 = st.columns(6)
        def _fmt_L(v):
            if v >= 1e5: return f"Rs.{v/1e5:.1f}L"
            if v >= 1e3: return f"Rs.{v/1e3:.0f}K"
            return f"Rs.{v:,.0f}"
        m1.metric("Net Sales",    _fmt_L(t_sales))
        m2.metric("Units",        f"{int(t_units):,}")
        m3.metric("ASP",          fmt_inr(t_asp))
        m4.metric("Ad Spend",     _fmt_L(t_spend) if t_spend > 0 else "N/A")
        m5.metric("Sales/Spend",  f"{t_roas:.1f}x" if t_spend > 0 else "N/A")
        m6.metric("Avg Conv Rate", f"{avg_cv*100:.1f}%" if pd.notna(avg_cv) else "N/A")

        st.divider()

        # Sales + units dual chart
        fig_s = make_subplots(specs=[[{"secondary_y": True}]])
        fig_s.add_trace(go.Bar(x=sdf['Month_label'], y=sdf['Net_Sales'],
            name='Net Sales', marker_color=color, opacity=0.75), secondary_y=False)
        fig_s.add_trace(go.Scatter(x=sdf['Month_label'], y=sdf['Units'],
            name='Units', mode='lines+markers',
            line=dict(color='#333', width=2)), secondary_y=True)
        fig_s.update_yaxes(title_text="Net Sales (Rs.)", secondary_y=False, tickformat=',.0f')
        fig_s.update_yaxes(title_text="Units", secondary_y=True)
        fig_s.update_layout(height=350, margin=dict(t=30,b=10),
                            title_text="Sales & Units",
                            legend=dict(orientation='h', y=-0.2, font=dict(size=11)))
        fig_s.update_xaxes(tickangle=-30)
        st.plotly_chart(fig_s, use_container_width=True)

        wi_s = sdf[sdf['Walkins'].notna() & sdf['Conv Rate'].notna()]
        if not wi_s.empty:
            fig_w = make_subplots(specs=[[{"secondary_y": True}]])
            fig_w.add_trace(go.Bar(x=wi_s['Month_label'], y=wi_s['Walkins'],
                name='Walk-ins', marker_color='#AED6F1', opacity=0.8), secondary_y=False)
            fig_w.add_trace(go.Bar(x=wi_s['Month_label'], y=wi_s['Conversions'],
                name='Conversions', marker_color=color, opacity=0.9), secondary_y=False)
            fig_w.add_trace(go.Scatter(x=wi_s['Month_label'],
                y=(wi_s['Conv Rate']*100).round(1),
                name='Conv%', mode='lines+markers',
                line=dict(color='#E74C3C', width=2, dash='dot')), secondary_y=True)
            fig_w.update_yaxes(title_text="Count", secondary_y=False)
            fig_w.update_yaxes(title_text="Conv Rate %", secondary_y=True, ticksuffix='%')
            fig_w.update_layout(height=350, margin=dict(t=30,b=10),
                                title_text="Walk-ins, Conversions & Conv Rate",
                                barmode='group',
                                legend=dict(orientation='h', y=-0.2, font=dict(size=11)))
            fig_w.update_xaxes(tickangle=-30)
            st.plotly_chart(fig_w, use_container_width=True)

        # ASP
        asp_s = sdf[sdf['ASP'].notna() & (sdf['ASP'] > 0)]
        if not asp_s.empty:
            fig_a = px.bar(asp_s, x='Month_label', y='ASP',
                           labels={'ASP':'ASP (Rs.)','Month_label':''},
                           color_discrete_sequence=[color])
            fig_a.update_layout(height=320, margin=dict(t=30,b=10), title_text="ASP")
            fig_a.update_yaxes(tickformat=',.0f')
            fig_a.update_xaxes(tickangle=-30)
            st.plotly_chart(fig_a, use_container_width=True)

        # Sales/Spend
        sp_s = sdf[sdf['Sales/Spend'].notna() & (sdf['Total Spend'] > 0)].copy()
        if not sp_s.empty:
            sp_s['roas_label'] = sp_s['Sales/Spend'].apply(lambda x: f"{x:.1f}x")
            fig_sp = make_subplots(specs=[[{"secondary_y": True}]])
            fig_sp.add_trace(go.Bar(x=sp_s['Month_label'], y=sp_s['Net_Sales'],
                name='Net Sales', marker_color=color, opacity=0.75), secondary_y=False)
            fig_sp.add_trace(go.Bar(x=sp_s['Month_label'], y=sp_s['Total Spend'],
                name='Ad Spend', marker_color='#E74C3C', opacity=0.75), secondary_y=False)
            fig_sp.add_trace(go.Scatter(x=sp_s['Month_label'], y=sp_s['Sales/Spend'],
                name='ROAS', mode='lines+markers+text',
                text=sp_s['roas_label'], textposition='top center', textfont_size=10,
                line=dict(color='#2C3E50', width=2.5), marker_size=7), secondary_y=True)
            fig_sp.update_yaxes(title_text='Rs.', secondary_y=False, tickformat=',.0f')
            fig_sp.update_yaxes(title_text='ROAS', secondary_y=True, rangemode='tozero')
            fig_sp.add_hline(y=1, line_dash='dash', line_color='red', secondary_y=True,
                             annotation_text='Break-even', annotation_position='bottom right')
            fig_sp.update_layout(height=380, margin=dict(t=30,b=10), title_text="Sales / Spend (ROAS)",
                                 barmode='group',
                                 legend=dict(orientation='h', y=-0.2, font=dict(size=10)))
            fig_sp.update_xaxes(tickangle=-30)
            st.plotly_chart(fig_sp, use_container_width=True)
        else:
            st.info("No spend data for this store.")

        # Top SKUs for this store
        st.subheader("Top SKUs")
        sk_top = (s_sk.groupby('SKU').agg(Units=('Units','sum'), Net_Sales=('Net Sales','sum'))
                      .sort_values('Net_Sales', ascending=False).head(15).reset_index())
        if sk_top.empty:
            st.info("No SKU data.")
        else:
            ck1, ck2 = st.columns([3,2])
            with ck1:
                fig_sk = px.bar(sk_top.sort_values('Net_Sales'), x='Net_Sales', y='SKU',
                                orientation='h', color_discrete_sequence=[color],
                                labels={'Net_Sales':'Net Sales (Rs.)','SKU':''})
                fig_sk.update_layout(height=max(320, len(sk_top)*26+80), margin=dict(t=10,b=10))
                fig_sk.update_xaxes(tickformat=',.0f')
                st.plotly_chart(fig_sk, use_container_width=True)
            with ck2:
                sk_top['ASP_fmt']  = (sk_top['Net_Sales'] / sk_top['Units'].replace(0, np.nan)).apply(
                    lambda x: fmt_inr(x) if pd.notna(x) else '—')
                sk_top['Net Sales'] = sk_top['Net_Sales'].apply(fmt_inr)
                st.dataframe(sk_top[['SKU','Units','Net Sales','ASP_fmt']].rename(columns={'ASP_fmt':'ASP'}),
                             use_container_width=True,
                             hide_index=True, height=max(320, len(sk_top)*28+40))

        # Top Ranges & Categories
        st.divider()
        st.subheader("Sales by Range & Category")
        s_sk2 = s_sk.copy()
        s_sk2['Category'] = s_sk2['SKU'].apply(_sku_to_range)
        s_sk2['Range']    = s_sk2['SKU'].apply(_sku_to_range_name)

        rc1, rc2 = st.columns(2)
        with rc1:
            rng_agg = (s_sk2.groupby('Range')
                            .agg(Units=('Units','sum'), Net_Sales=('Net Sales','sum'))
                            .reset_index().sort_values('Net_Sales', ascending=False).head(15))
            fig_rng = px.bar(rng_agg.sort_values('Net_Sales'), x='Net_Sales', y='Range',
                             orientation='h', color_discrete_sequence=[color],
                             labels={'Net_Sales':'Net Sales (Rs.)','Range':''})
            fig_rng.update_layout(height=max(320, len(rng_agg)*26+80),
                                  margin=dict(t=30,b=10), title_text="Top Ranges")
            fig_rng.update_xaxes(tickformat=',.0f')
            st.plotly_chart(fig_rng, use_container_width=True)

        with rc2:
            cat_agg = (s_sk2.groupby('Category')
                            .agg(Units=('Units','sum'), Net_Sales=('Net Sales','sum'))
                            .reset_index().sort_values('Net_Sales', ascending=False))
            cat_agg['Share %'] = (cat_agg['Net_Sales'] / cat_agg['Net_Sales'].sum() * 100).round(1).astype(str) + '%'
            cat_agg['Net Sales'] = cat_agg['Net_Sales'].apply(fmt_inr)
            st.markdown("**By Category**")
            st.dataframe(cat_agg[['Category','Units','Net Sales','Share %']],
                         use_container_width=True, hide_index=True)

        # Daily trend for store
        if not s_da.empty:
            st.subheader("Daily Sales")
            s_dag = (s_da.groupby('Date').agg(Net_Sales=('Net','sum'), Units=('Qty','sum'))
                        .reset_index().sort_values('Date'))
            fig_dd = px.bar(s_dag, x='Date', y='Net_Sales', color_discrete_sequence=[color],
                            labels={'Net_Sales':'Net Sales (Rs.)','Date':''})
            fig_dd.update_layout(height=260, margin=dict(t=10,b=10))
            fig_dd.update_yaxes(tickformat=',.0f')
            st.plotly_chart(fig_dd, use_container_width=True)
