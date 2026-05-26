import os, sys, socket, subprocess, json, re
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from loader import (
    load_campaigns, load_search_terms_brand, load_search_terms_pmax,
    load_audiences, load_landing_pages, load_placements,
    load_shopping, load_demographics, load_geography,
    filter_dates, filter_goals, _USE_PARQUET, PARQUET_FOLDER,
)

# ---------------------------------------------------------------------------
# Helpers — network URL and last-sync info
# ---------------------------------------------------------------------------
def _get_network_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"

def _last_sync_info() -> dict:
    """Read pulled_at and metrics from google_latest.json if it exists."""
    sync_path = os.path.join(os.path.dirname(__file__), 'processed', 'google_latest.json')
    if not os.path.exists(sync_path):
        return {}
    try:
        with open(sync_path, encoding='utf-8') as f:
            d = json.load(f)
        pulled = d.get('metrics', {}).get('pulled_at', '')
        date_range = d.get('metrics', {}).get('data_range', {})
        return {'pulled_at': pulled, 'data_range': date_range}
    except Exception:
        return {}

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Nasher Miles — Google Ads Dashboard",
    page_icon="🧳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Brand colours
# ---------------------------------------------------------------------------
BRAND_BLUE   = "#1A1A2E"
BRAND_ORANGE = "#FF6B35"
BRAND_TEAL   = "#00C9A7"
BRAND_RED    = "#E63946"
BRAND_GREY   = "#F0F2F6"
GROUP_COLORS = {
    "Branded Search":        "#FF6B35",
    "Generic Search":        "#00C9A7",
    "Competitor Search":     "#E63946",
    "Performance Max":       "#4361EE",
    "Demand Gen / Retargeting": "#7B2FBE",
    "Video / Awareness":     "#F4A261",
    "Offline":               "#6C757D",
    "Other":                 "#ADB5BD",
}
# Maps sidebar goal filter → campaign groups to include
GOAL_TO_GROUPS = {
    "Sales":       ["Branded Search", "Generic Search", "Competitor Search",
                    "Performance Max", "Other"],
    "Cart":        ["Demand Gen / Retargeting"],
    "Video Views": ["Video / Awareness"],
    "Offline":     ["Offline"],
}
# Reverse: campaign group → conversion goal label (for Overview chart)
GROUP_TO_GOAL = {
    "Branded Search":           "Sales",
    "Generic Search":           "Sales",
    "Competitor Search":        "Sales",
    "Performance Max":          "Sales",
    "Other":                    "Sales",
    "Demand Gen / Retargeting": "Cart",
    "Video / Awareness":        "Video Views",
    "Offline":                  "Offline",
}

st.markdown("""
<style>
  .metric-card{background:#fff;border-radius:12px;padding:14px 10px;
    box-shadow:0 2px 8px rgba(0,0,0,.07);text-align:center;}
  .metric-label{font-size:12px;color:#6c757d;font-weight:600;letter-spacing:.5px;
    text-transform:uppercase;margin-bottom:4px;}
  .metric-value{font-size:16px;font-weight:800;color:#1A1A2E;word-break:break-word;}
  .metric-delta{font-size:12px;margin-top:4px;}
  .ok-badge{background:#d4edda;color:#155724;padding:2px 10px;border-radius:20px;
    font-size:12px;font-weight:700;}
  .critical-badge{background:#f8d7da;color:#721c24;padding:2px 10px;border-radius:20px;
    font-size:12px;font-weight:700;}
  div[data-testid="stSidebar"]{background:#1A1A2E;}
  div[data-testid="stSidebar"] *{color:#fff !important;}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar — global filters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🧳 Nasher Miles")
    st.markdown("### Google Ads Intelligence")
    st.markdown("---")

    DATA_MIN = pd.Timestamp("2025-10-01")
    DATA_MAX = pd.Timestamp("2026-05-19")

    date_range = st.date_input(
        "Date range",
        value=(pd.Timestamp("2026-04-01").date(), DATA_MAX.date()),
        min_value=DATA_MIN.date(),
        max_value=DATA_MAX.date(),
    )
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = DATA_MIN.date(), DATA_MAX.date()

    goal_options = ["Sales", "Cart", "Offline", "Video Views"]
    selected_goals = st.multiselect(
        "Conversion goal",
        goal_options,
        default=goal_options,
    )

    roas_target = st.number_input("ROAS target", value=3.0, step=0.1, min_value=0.5)

    comp_mode = st.selectbox(
        "Comparison period",
        ["None", "Previous Period", "Previous Month", "Previous Quarter", "Same Period Last Year"],
        key='comp_mode', index=1,
    )

    st.markdown("---")
    active_tab = st.radio(
        "Navigate",
        ["📊 Overview", "📋 Campaigns", "🔍 Search Terms",
         "🛒 Products & Collections", "📄 Landing Pages",
         "👥 Audiences & Demographics", "🗺️ Geography", "📺 Placements"],
        label_visibility="collapsed",
    )
    st.markdown("---")

    # ── Refresh Data ─────────────────────────────────────────────────────────
    st.markdown("#### 🔄 Data")
    if _USE_PARQUET:
        # Cloud deployment — data comes from parquet files pushed via daily sync
        try:
            import glob as _glob
            _pq_files = list(PARQUET_FOLDER.glob("*.parquet"))
            if _pq_files:
                _latest_mtime = max(f.stat().st_mtime for f in _pq_files)
                _latest_dt = datetime.fromtimestamp(_latest_mtime)
                st.caption(f"Data updated: {_latest_dt.strftime('%d %b %Y')}")
        except Exception:
            pass
        st.caption("Refreshed daily via automated sync.")
    else:
        # Local deployment — can run sync script directly
        sync_info = _last_sync_info()
        if sync_info.get('pulled_at'):
            try:
                pulled_dt = datetime.fromisoformat(sync_info['pulled_at'])
                st.caption(f"Last synced: {pulled_dt.strftime('%d %b %Y, %H:%M')}")
            except Exception:
                st.caption(f"Last synced: {sync_info['pulled_at'][:16]}")
            dr = sync_info.get('data_range', {})
            if dr:
                st.caption(f"Data window: {dr.get('start','')} → {dr.get('end','')}")
        else:
            st.caption("google_latest.json not found — click Refresh to generate.")

        if st.button("🔄 Refresh Google Data", use_container_width=True):
            with st.spinner("Running google_sync.py (30-day window)…"):
                sync_script = os.path.join(os.path.dirname(__file__), 'google_sync.py')
                result = subprocess.run(
                    [sys.executable, sync_script, '30'],
                    capture_output=True, text=True, timeout=120
                )
            if result.returncode == 0:
                st.cache_data.clear()
                st.success("Data refreshed! Reloading…")
                st.rerun()
            else:
                st.error("Sync failed. See details below.")
                st.code(result.stderr or result.stdout, language='text')

    st.markdown("---")

    # ── Launch / Share ────────────────────────────────────────────────────────
    st.markdown("#### 🚀 Launch & Share")
    _port = 8502          # update if you start on a different port
    _ip   = _get_network_ip()
    _local_url   = f"http://localhost:{_port}"
    _network_url = f"http://{_ip}:{_port}"

    st.markdown(
        f"**Local:** [{_local_url}]({_local_url})",
        unsafe_allow_html=False,
    )
    st.markdown(
        f"**Network:** [{_network_url}]({_network_url})",
        unsafe_allow_html=False,
    )
    st.code(_network_url, language=None)
    st.caption("Share the Network URL with your team on the same Wi-Fi.")

    st.markdown("---")
    st.caption("Data: Oct 2025 – May 2026")

# ---------------------------------------------------------------------------
# Load & filter campaigns (small — always loaded)
# ---------------------------------------------------------------------------
with st.spinner("Loading campaign data…"):
    df_camp = load_campaigns()

df_camp_dated = filter_dates(df_camp, start_date, end_date)
if selected_goals:
    _allowed_groups: set = set()
    for _g in selected_goals:
        _allowed_groups.update(GOAL_TO_GROUPS.get(_g, []))
    df_camp_f = df_camp_dated[df_camp_dated['Group'].isin(_allowed_groups)]
else:
    df_camp_f = df_camp_dated

# ---------------------------------------------------------------------------
# Comparison period computation
# ---------------------------------------------------------------------------
def _comp_range(start, end, mode):
    delta_days = (pd.Timestamp(end) - pd.Timestamp(start)).days + 1
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    if mode == 'Previous Period':
        ce = s - timedelta(days=1)
        cs = ce - timedelta(days=delta_days - 1)
        return cs.date(), ce.date()
    if mode == 'Previous Month':
        return (s - relativedelta(months=1)).date(), (e - relativedelta(months=1)).date()
    if mode == 'Previous Quarter':
        return (s - relativedelta(months=3)).date(), (e - relativedelta(months=3)).date()
    if mode == 'Same Period Last Year':
        return (s - relativedelta(years=1)).date(), (e - relativedelta(years=1)).date()
    return None, None

comp_start, comp_end = _comp_range(start_date, end_date, comp_mode) if comp_mode != 'None' else (None, None)
has_comp = comp_start is not None
_comp_label = {
    'Previous Period': 'prev period',
    'Previous Month': 'prev month',
    'Previous Quarter': 'prev quarter',
    'Same Period Last Year': 'same period last year',
}.get(comp_mode, '')

# Comparison campaign dataframe (same goal filter, different dates)
if has_comp:
    _df_camp_comp_dated = filter_dates(df_camp, comp_start, comp_end)
    if selected_goals:
        df_camp_comp = _df_camp_comp_dated[_df_camp_comp_dated['Group'].isin(_allowed_groups)]
    else:
        df_camp_comp = _df_camp_comp_dated
else:
    df_camp_comp = pd.DataFrame(columns=df_camp_f.columns)

def _dpct(curr, prev):
    """% change from prev to curr. Returns None if prev is 0 or has_comp is False."""
    if not has_comp or prev is None or prev == 0:
        return None
    return round((curr - prev) / abs(prev) * 100, 1)

def _delta_badge(pct, good='up'):
    """Return HTML badge string for a delta percentage."""
    if pct is None:
        return ''
    arrow = '▲' if pct >= 0 else '▼'
    color = '#00C9A7' if ((pct >= 0 and good == 'up') or (pct < 0 and good == 'down')) else '#E63946'
    return f'<span style="color:{color};font-size:11px;font-weight:700">{arrow}{abs(pct):.1f}%</span>'

# ---------------------------------------------------------------------------
# KPI helper
# ---------------------------------------------------------------------------
def _ascii_label(name: str, maxlen: int = 40) -> str:
    """Return a chart-safe label: ASCII portion of name; if too short, transliterate hint."""
    ascii_part = re.sub(r'[^\x20-\x7E]', '', str(name)).strip()
    if len(ascii_part) >= 4:
        return ascii_part[:maxlen]
    # Entirely non-Latin — keep but truncate so chart Y-axis doesn't garble
    return str(name)[:maxlen]

def _fmt_inr(v):
    """Format large INR values in abbreviated Indian format."""
    if v >= 1_00_00_000:
        return f"Rs.{v/1_00_00_000:.1f}Cr"
    if v >= 1_00_000:
        return f"Rs.{v/1_00_000:.2f}L"
    if v >= 1_000:
        return f"Rs.{v/1_000:.1f}K"
    return f"Rs.{v:.0f}"

def kpi_card(col, label, value, fmt="{:,.0f}", prefix="", suffix="",
             delta=None, delta_good="up", inr=False):
    with col:
        delta_html = ""
        if delta is not None:
            arrow = "▲" if delta >= 0 else "▼"
            colour = BRAND_TEAL if (
                (delta >= 0 and delta_good == "up") or
                (delta < 0 and delta_good == "down")
            ) else BRAND_RED
            delta_html = f'<div class="metric-delta" style="color:{colour}">{arrow} {abs(delta):.1f}%</div>'
        display = _fmt_inr(value) if inr else f"{prefix}{fmt.format(value)}{suffix}"
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-label">{label}</div>
          <div class="metric-value">{display}</div>
          {delta_html}
        </div>""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Smart period aggregation — adapts to the selected date range
# ---------------------------------------------------------------------------
def _smart_agg(df_in, start, end):
    """Return (df_aggregated, period_label) with period column named 'Period'."""
    days_span = (pd.Timestamp(end) - pd.Timestamp(start)).days + 1
    df = df_in.copy()
    if days_span <= 7:
        df['Period'] = df['Day']
        label = "Daily"
    elif days_span <= 90:
        df['Period'] = df['Day'].dt.to_period('W').apply(lambda p: p.start_time)
        label = "Weekly"
    else:
        df['Period'] = df['Day'].dt.to_period('M').apply(lambda p: p.start_time)
        label = "Monthly"
    return df, label, days_span

# ---------------------------------------------------------------------------
# Page routing — only the active tab renders
# ---------------------------------------------------------------------------

# ============================================================
# TAB 1 — Overview
# ============================================================
if active_tab == "📊 Overview":
    st.markdown(f"### Overview — {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}")

    total_spend       = df_camp_f['Cost'].sum()
    total_conv        = df_camp_f['Conversions'].sum()
    total_revenue     = df_camp_f['Conv_Value'].sum()
    total_clicks      = df_camp_f['Clicks'].sum()
    total_impressions = df_camp_f['Impressions'].sum()
    blended_roas      = round(total_revenue / total_spend, 2) if total_spend > 0 else 0
    blended_ctr       = round(total_clicks / total_impressions * 100, 2) if total_impressions > 0 else 0
    blended_cpc       = round(total_spend / total_clicks, 2) if total_clicks > 0 else 0

    _pr_spend = df_camp_comp['Cost'].sum()
    _pr_rev   = df_camp_comp['Conv_Value'].sum()
    _pr_conv  = df_camp_comp['Conversions'].sum()
    _pr_clicks= df_camp_comp['Clicks'].sum()
    _pr_impr  = df_camp_comp['Impressions'].sum() if 'Impressions' in df_camp_comp.columns else 0
    _pr_roas  = round(_pr_rev / _pr_spend, 2) if _pr_spend > 0 else 0
    _pr_ctr   = round(_pr_clicks / _pr_impr * 100, 2) if _pr_impr > 0 else 0
    _pr_cpc   = round(_pr_spend / _pr_clicks, 2) if _pr_clicks > 0 else 0

    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    kpi_card(c1, "Total Spend", total_spend, inr=True, delta=_dpct(total_spend, _pr_spend), delta_good='down')
    kpi_card(c2, "ROAS", blended_roas, fmt="{:.2f}", suffix="x", delta=_dpct(blended_roas, _pr_roas), delta_good='up')
    kpi_card(c3, "Revenue", total_revenue, inr=True, delta=_dpct(total_revenue, _pr_rev), delta_good='up')
    kpi_card(c4, "Conversions", total_conv, fmt="{:,.0f}", delta=_dpct(total_conv, _pr_conv), delta_good='up')
    kpi_card(c5, "Clicks", total_clicks, fmt="{:,.0f}", delta=_dpct(total_clicks, _pr_clicks), delta_good='up')
    kpi_card(c6, "CTR", blended_ctr, fmt="{:.2f}", suffix="%", delta=_dpct(blended_ctr, _pr_ctr), delta_good='up')
    kpi_card(c7, "Avg CPC", blended_cpc, inr=True, delta=_dpct(blended_cpc, _pr_cpc), delta_good='down')

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row: ROAS gauge | Spend by Campaign Type | Spend by Conversion Goal ──
    col_gauge, col_type, col_goal = st.columns([1, 1.5, 1.5])

    with col_gauge:
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=blended_roas,
            delta={'reference': roas_target, 'increasing': {'color': BRAND_TEAL},
                   'decreasing': {'color': BRAND_RED}},
            title={'text': f"Blended ROAS vs {roas_target}x target", 'font': {'size': 14}},
            gauge={
                'axis': {'range': [0, max(roas_target * 2, blended_roas * 1.2)]},
                'bar': {'color': BRAND_ORANGE},
                'steps': [
                    {'range': [0, roas_target * 0.7], 'color': '#f8d7da'},
                    {'range': [roas_target * 0.7, roas_target], 'color': '#fff3cd'},
                    {'range': [roas_target, roas_target * 2], 'color': '#d4edda'},
                ],
                'threshold': {
                    'line': {'color': BRAND_BLUE, 'width': 3},
                    'thickness': 0.75,
                    'value': roas_target,
                },
            },
            number={'suffix': 'x', 'font': {'size': 22, 'color': BRAND_BLUE},
                    'valueformat': '.2f'},
        ))
        fig_gauge.update_layout(height=360, margin=dict(t=60, b=20, l=20, r=20))
        st.plotly_chart(fig_gauge, use_container_width=True)

    with col_type:
        grp_type = (df_camp_f.groupby('Campaign_Type')
                    .agg(Spend=('Cost','sum'), Revenue=('Conv_Value','sum'))
                    .reset_index())
        grp_type = grp_type[grp_type['Spend']>0].sort_values('Spend', ascending=False)
        grp_type['ROAS'] = (grp_type['Revenue']/grp_type['Spend']).round(2)
        grp_type['Period'] = 'Current'

        if has_comp:
            grp_type_c = (df_camp_comp.groupby('Campaign_Type')
                          .agg(Spend=('Cost','sum'), Revenue=('Conv_Value','sum'))
                          .reset_index())
            grp_type_c = grp_type_c[grp_type_c['Spend']>0]
            grp_type_c['ROAS'] = (grp_type_c['Revenue']/grp_type_c['Spend']).round(2)
            grp_type_c['Period'] = _comp_label.title()
            grp_combined = pd.concat([grp_type, grp_type_c], ignore_index=True)
            fig_type = px.bar(
                grp_combined, x='Campaign_Type', y='Spend',
                color='Period', barmode='group',
                color_discrete_sequence=[BRAND_ORANGE, '#ADB5BD'],
                title="Spend by Campaign Type",
                labels={'Spend':'Spend (Rs.)','Campaign_Type':''},
                custom_data=['ROAS','Revenue'],
            )
            fig_type.update_traces(
                hovertemplate="<b>%{x}</b> · %{data.name}<br>Spend: Rs.%{y:,.0f}<br>ROAS: %{customdata[0]:.2f}x<br>Revenue: Rs.%{customdata[1]:,.0f}<extra></extra>"
            )
        else:
            fig_type = px.bar(
                grp_type, x='Campaign_Type', y='Spend', color='Campaign_Type',
                text=grp_type['ROAS'].apply(lambda r: f"{r:.1f}x"),
                title="Spend by Campaign Type",
                labels={'Spend':'Spend (Rs.)','Campaign_Type':''},
            )
            fig_type.update_traces(textposition='outside')
            fig_type.update_traces(
                hovertemplate="<b>%{x}</b><br>Spend: Rs.%{y:,.0f}<br>ROAS: %{text}<extra></extra>"
            )
        fig_type.update_layout(showlegend=has_comp, height=300,
                                margin=dict(t=40,b=0,l=0,r=0),
                                plot_bgcolor='white', paper_bgcolor='white')
        st.plotly_chart(fig_type, use_container_width=True)

    with col_goal:
        _df_goal = df_camp_f.copy()
        _df_goal['Conv_Goal'] = _df_goal['Group'].map(GROUP_TO_GOAL).fillna('Sales')
        grp_goal = (_df_goal.groupby('Conv_Goal')
                    .agg(Spend=('Cost','sum'), Revenue=('Conv_Value','sum'),
                         Conversions=('Conversions','sum'))
                    .reset_index())
        grp_goal = grp_goal[grp_goal['Spend']>0].sort_values('Spend', ascending=False)
        grp_goal['ROAS'] = (grp_goal['Revenue']/grp_goal['Spend']).round(2)
        grp_goal['Period'] = 'Current'

        if has_comp:
            _df_goal_c = df_camp_comp.copy()
            _df_goal_c['Conv_Goal'] = _df_goal_c['Group'].map(GROUP_TO_GOAL).fillna('Sales')
            grp_goal_c = (_df_goal_c.groupby('Conv_Goal')
                          .agg(Spend=('Cost','sum'), Revenue=('Conv_Value','sum'),
                               Conversions=('Conversions','sum'))
                          .reset_index())
            grp_goal_c = grp_goal_c[grp_goal_c['Spend']>0]
            grp_goal_c['ROAS'] = (grp_goal_c['Revenue']/grp_goal_c['Spend']).round(2)
            grp_goal_c['Period'] = _comp_label.title()
            grp_goal['Period'] = 'Current'
            goal_combined = pd.concat([grp_goal[['Conv_Goal','ROAS','Period']], grp_goal_c[['Conv_Goal','ROAS','Period']]], ignore_index=True)
            fig_goal = px.bar(
                goal_combined, x='Conv_Goal', y='ROAS',
                color='Period', barmode='group',
                color_discrete_sequence=[BRAND_ORANGE, '#ADB5BD'],
                title="ROAS by Conversion Goal",
                labels={'ROAS':'ROAS','Conv_Goal':''},
            )
            fig_goal.add_hline(y=roas_target, line_dash="dash", line_color=BRAND_RED,
                                annotation_text=f"Target {roas_target}x", annotation_position="top right")
            fig_goal.update_traces(
                hovertemplate="<b>%{x}</b> · %{data.name}<br>ROAS: %{y:.2f}x<extra></extra>"
            )
        else:
            _goal_colors = {'Sales':BRAND_ORANGE,'Cart':BRAND_TEAL,'Video Views':'#F4A261','Offline':'#6C757D'}
            fig_goal = px.bar(
                grp_goal, x='Conv_Goal', y='ROAS',
                color='Conv_Goal', color_discrete_map=_goal_colors,
                text=grp_goal['ROAS'].apply(lambda r: f"{r:.2f}x" if r>0 else "TOF"),
                title="ROAS by Conversion Goal",
                labels={'ROAS':'ROAS','Conv_Goal':''},
                custom_data=[grp_goal['Spend'], grp_goal['Revenue']],
            )
            fig_goal.update_traces(textposition='outside')
            fig_goal.add_hline(y=roas_target, line_dash="dash", line_color=BRAND_RED,
                                annotation_text=f"Target {roas_target}x", annotation_position="top right")
            fig_goal.update_traces(
                hovertemplate=(
                    "<b>%{x}</b><br>ROAS: %{y:.2f}x<br>"
                    "Spend: Rs.%{customdata[0]:,.0f}<br>"
                    "Revenue: Rs.%{customdata[1]:,.0f}<extra></extra>"
                )
            )
        fig_goal.update_layout(showlegend=has_comp, height=300,
                                margin=dict(t=40,b=0,l=0,r=0),
                                plot_bgcolor='white', paper_bgcolor='white')
        st.plotly_chart(fig_goal, use_container_width=True)

    # Period toggle — user can override the smart default
    _days_span = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days + 1
    _default_p = 0 if _days_span <= 7 else (1 if _days_span <= 90 else 2)
    _period_choice = st.radio(
        "Trend view", ["Daily", "Weekly", "Monthly"],
        index=_default_p, horizontal=True, key='trend_period',
    )
    _df_t = df_camp_f.copy()
    if _period_choice == "Daily":
        _df_t['Period'] = _df_t['Day']
        _period_label = "Daily"
    elif _period_choice == "Weekly":
        _df_t['Period'] = _df_t['Day'].dt.to_period('W').apply(lambda p: p.start_time)
        _period_label = "Weekly"
    else:
        _df_t['Period'] = _df_t['Day'].dt.to_period('M').apply(lambda p: p.start_time)
        _period_label = "Monthly"
    st.markdown(f"#### {_period_label} Spend & ROAS Trend")
    trend = (_df_t.groupby('Period')
             .agg(Spend=('Cost', 'sum'), Revenue=('Conv_Value', 'sum'), Clicks=('Clicks', 'sum'))
             .reset_index())
    trend['ROAS'] = (trend['Revenue'] / trend['Spend']).round(2).where(trend['Spend'] > 0, 0)

    if has_comp:
        _df_tc = df_camp_comp.copy()
        if _period_choice == "Daily":
            _df_tc['Period'] = _df_tc['Day']
        elif _period_choice == "Weekly":
            _df_tc['Period'] = _df_tc['Day'].dt.to_period('W').apply(lambda p: p.start_time)
        else:
            _df_tc['Period'] = _df_tc['Day'].dt.to_period('M').apply(lambda p: p.start_time)
        trend_comp = (_df_tc.groupby('Period')
                      .agg(Spend=('Cost', 'sum'), Revenue=('Conv_Value', 'sum'))
                      .reset_index())
        trend_comp['ROAS'] = (trend_comp['Revenue'] / trend_comp['Spend']).round(2).where(trend_comp['Spend'] > 0, 0)
    else:
        trend_comp = None

    fig_trend = make_subplots(specs=[[{"secondary_y": True}]])
    fig_trend.add_trace(go.Bar(
        x=trend['Period'], y=trend['Spend'], name='Spend (Rs.)',
        marker_color=BRAND_ORANGE, opacity=0.85), secondary_y=False)
    fig_trend.add_trace(go.Scatter(
        x=trend['Period'], y=trend['ROAS'], name='ROAS',
        mode='lines+markers', line=dict(color=BRAND_TEAL, width=3),
        marker=dict(size=7)), secondary_y=True)
    if trend_comp is not None and len(trend_comp) > 0:
        fig_trend.add_trace(go.Bar(
            x=trend_comp['Period'], y=trend_comp['Spend'], name=f'Spend ({_comp_label})',
            marker_color=BRAND_ORANGE, opacity=0.35), secondary_y=False)
        fig_trend.add_trace(go.Scatter(
            x=trend_comp['Period'], y=trend_comp['ROAS'], name=f'ROAS ({_comp_label})',
            mode='lines+markers', line=dict(color=BRAND_TEAL, width=2, dash='dash'),
            marker=dict(size=5)), secondary_y=True)
    fig_trend.add_hline(y=roas_target, line_dash="dash", line_color=BRAND_RED,
                        annotation_text=f"Target {roas_target}x",
                        secondary_y=True)
    fig_trend.update_yaxes(title_text="Spend (Rs.)", secondary_y=False)
    fig_trend.update_yaxes(title_text="ROAS", secondary_y=True)
    fig_trend.update_layout(height=320, plot_bgcolor='white', paper_bgcolor='white',
                             legend=dict(orientation='h', y=1.12),
                             margin=dict(t=10, b=0))
    st.plotly_chart(fig_trend, use_container_width=True)


# ============================================================
# TAB 2 — Campaigns
# ============================================================
elif active_tab == "📋 Campaigns":
    st.markdown(f"### Campaign Performance — {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}")

    # ── Group filter (compact, full-width multiselect) ──────────────────────
    all_groups = sorted(df_camp_f['Group'].unique().tolist())
    sel_groups = st.multiselect(
        "Filter by campaign group", all_groups, default=all_groups,
        key='camp_group_filter',
    )
    df_c2 = df_camp_f[df_camp_f['Group'].isin(sel_groups)] if sel_groups else df_camp_f

    # ── Aggregate by campaign ────────────────────────────────────────────────
    camp_tbl = (df_c2.groupby(['Campaign', 'Campaign_Type', 'Group'])
                .agg(Spend=('Cost', 'sum'), Clicks=('Clicks', 'sum'),
                     Impressions=('Impressions', 'sum'),
                     Conversions=('Conversions', 'sum'),
                     Revenue=('Conv_Value', 'sum'))
                .reset_index())
    camp_tbl['ROAS'] = (camp_tbl['Revenue'] / camp_tbl['Spend']).round(2).where(
        camp_tbl['Spend'] > 0, 0)
    camp_tbl['CPC']  = (camp_tbl['Spend'] / camp_tbl['Clicks']).round(2).where(
        camp_tbl['Clicks'] > 0, 0)
    camp_tbl['Status'] = camp_tbl['ROAS'].apply(
        lambda r: '✅ OK' if r >= roas_target else ('🔴 LOW' if r > 0 else '⚪ No Conv.'))
    camp_tbl = camp_tbl.sort_values('Spend', ascending=False)
    _total_sp = camp_tbl['Spend'].sum()

    # ── Section 1 — Account KPIs strip ──────────────────────────────────────
    _c_rev   = df_c2['Conv_Value'].sum()
    _c_conv  = df_c2['Conversions'].sum()
    _c_click = df_c2['Clicks'].sum()
    _c_roas  = round(_c_rev / _total_sp, 2) if _total_sp > 0 else 0

    if has_comp:
        _df_c2_comp = df_camp_comp[df_camp_comp['Group'].isin(sel_groups)] if sel_groups else df_camp_comp
        _pr_c_sp   = _df_c2_comp['Cost'].sum()
        _pr_c_rev  = _df_c2_comp['Conv_Value'].sum()
        _pr_c_conv = _df_c2_comp['Conversions'].sum()
        _pr_c_click= _df_c2_comp['Clicks'].sum()
        _pr_c_roas = round(_pr_c_rev / _pr_c_sp, 2) if _pr_c_sp > 0 else 0
    else:
        _pr_c_sp = _pr_c_rev = _pr_c_conv = _pr_c_click = _pr_c_roas = 0

    kc1, kc2, kc3, kc4, kc5 = st.columns(5)
    kpi_card(kc1, "Total Spend",  _total_sp, inr=True, delta=_dpct(_total_sp, _pr_c_sp), delta_good='down')
    kpi_card(kc2, "ROAS",         _c_roas,   fmt="{:.2f}", suffix="x", delta=_dpct(_c_roas, _pr_c_roas), delta_good='up')
    kpi_card(kc3, "Revenue",      _c_rev,    inr=True, delta=_dpct(_c_rev, _pr_c_rev), delta_good='up')
    kpi_card(kc4, "Conversions",  _c_conv,   fmt="{:,.0f}", delta=_dpct(_c_conv, _pr_c_conv), delta_good='up')
    kpi_card(kc5, "Clicks",       _c_click,  fmt="{:,.0f}", delta=_dpct(_c_click, _pr_c_click), delta_good='up')

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 2 — Campaign Type breakdown ─────────────────────────────────
    st.markdown("#### Campaign Type Breakdown")
    col_pie, col_type_tbl = st.columns([4, 5])

    type_tbl = (df_c2.groupby('Campaign_Type')
                .agg(Spend=('Cost', 'sum'), Revenue=('Conv_Value', 'sum'),
                     Conversions=('Conversions', 'sum'),
                     Campaigns=('Campaign', 'nunique'))
                .reset_index())
    type_tbl['ROAS']    = (type_tbl['Revenue'] / type_tbl['Spend']).round(2).where(type_tbl['Spend'] > 0, 0)
    _sp_total = type_tbl['Spend'].sum()
    type_tbl['Spend %'] = (type_tbl['Spend'] / _sp_total * 100).round(1) if _sp_total > 0 else 0.0
    type_tbl = type_tbl[type_tbl['Spend'] > 0].sort_values('Spend', ascending=False).reset_index(drop=True)

    if has_comp:
        _type_comp = (df_camp_comp[df_camp_comp['Group'].isin(sel_groups)] if sel_groups else df_camp_comp).groupby('Campaign_Type').agg(
            Spend_prev=('Cost','sum'), Revenue_prev=('Conv_Value','sum')).reset_index()
        type_tbl = type_tbl.merge(_type_comp, on='Campaign_Type', how='left').fillna(0)
        type_tbl['Spend Δ%'] = type_tbl.apply(lambda r: _dpct(r['Spend'], r['Spend_prev']), axis=1)
        type_tbl['ROAS_prev'] = (type_tbl['Revenue_prev']/type_tbl['Spend_prev']).round(2).where(type_tbl['Spend_prev']>0, 0)
        type_tbl['ROAS Δ%'] = type_tbl.apply(lambda r: _dpct(r['ROAS'], r['ROAS_prev']), axis=1)

    with col_pie:
        if has_comp and 'Spend_prev' in type_tbl.columns:
            _pt_curr = type_tbl[['Campaign_Type','Spend','ROAS']].copy()
            _pt_curr['Period'] = 'Current'
            _pt_curr['roas_label'] = _pt_curr['ROAS'].apply(lambda r: f"{r:.1f}x")
            _pt_prev = type_tbl[['Campaign_Type','Spend_prev','ROAS_prev']].copy().rename(
                columns={'Spend_prev':'Spend','ROAS_prev':'ROAS'})
            _pt_prev['Period'] = _comp_label.title()
            _pt_prev['roas_label'] = _pt_prev['ROAS'].apply(lambda r: f"{r:.1f}x")
            _pt_combined = pd.concat([_pt_curr, _pt_prev])
            fig_pie = px.bar(_pt_combined, x='Campaign_Type', y='Spend',
                             color='Period', text='roas_label', barmode='group',
                             color_discrete_sequence=[BRAND_ORANGE,'#ADB5BD'],
                             title="Spend by Campaign Type (ROAS on bars)",
                             labels={'Spend':'Spend (Rs.)','Campaign_Type':''})
            fig_pie.update_traces(
                textposition='outside',
                hovertemplate="<b>%{x}</b> · %{data.name}<br>Spend: Rs.%{y:,.0f}<br>ROAS: %{text}<extra></extra>"
            )
            fig_pie.update_layout(height=360, plot_bgcolor='white', paper_bgcolor='white',
                                   margin=dict(t=55,b=30,l=10,r=10), showlegend=True)
        else:
            grp_pie = type_tbl.copy()
            fig_pie = px.pie(grp_pie, values='Spend', names='Campaign_Type', hole=0.45,
                             custom_data=['ROAS','Revenue'])
            fig_pie.update_traces(
                hovertemplate=("<b>%{label}</b><br>Spend: Rs.%{value:,.0f}<br>Share: %{percent}<br>"
                               "ROAS: %{customdata[0]:.2f}x<br>Revenue: Rs.%{customdata[1]:,.0f}<extra></extra>"),
                textinfo='percent', textfont_size=13)
            fig_pie.update_layout(height=340, showlegend=True,
                                   legend=dict(orientation='v',x=1.0,y=0.5,font=dict(size=12),bgcolor='rgba(0,0,0,0)'),
                                   margin=dict(t=10,b=10,l=10,r=10), paper_bgcolor='white')
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_type_tbl:
        _type_display_cols = ['Campaign_Type','Campaigns','Spend','Revenue','ROAS','Conversions','Spend %']
        if has_comp:
            _type_display_cols += ['Spend Δ%', 'ROAS Δ%']
        _type_fmt = {'Spend':'Rs.{:,.0f}','Revenue':'Rs.{:,.0f}','ROAS':'{:.2f}x','Conversions':'{:,.1f}','Spend %':'{:.1f}%'}
        if has_comp:
            _type_fmt['Spend Δ%'] = '{:+.1f}%'
            _type_fmt['ROAS Δ%'] = '{:+.1f}%'
        st.dataframe(
            type_tbl[_type_display_cols]
            .rename(columns={'Campaign_Type':'Type'})
            .style.format(_type_fmt, na_rep='—'),
            use_container_width=True, height=340, hide_index=True)

    st.markdown("---")

    # ── Section 3 — Top 10 campaigns table (no bar chart — names too long) ──
    st.markdown("#### Top 10 Campaigns by Spend")

    def _row_roas_style(row):
        roas_val = row.get('ROAS', 0)
        if isinstance(roas_val, str):
            return [''] * len(row)
        if roas_val >= roas_target:
            bg = '#d4edda'
        elif roas_val > 0:
            bg = '#fff3cd'
        else:
            bg = '#f8f9fa'
        return [f'background-color:{bg}'] * len(row)

    top10 = camp_tbl.head(10).reset_index(drop=True)
    top10.index = top10.index + 1

    if has_comp:
        _df_c2_comp = df_camp_comp[df_camp_comp['Group'].isin(sel_groups)] if sel_groups else df_camp_comp
        _c10_comp = (_df_c2_comp.groupby('Campaign')
                     .agg(Spend_prev=('Cost','sum'), Revenue_prev=('Conv_Value','sum'))
                     .reset_index())
        top10 = top10.merge(_c10_comp[['Campaign','Spend_prev','Revenue_prev']], on='Campaign', how='left').fillna(0)
        top10['Spend Δ%'] = top10.apply(lambda r: _dpct(r['Spend'], r['Spend_prev']), axis=1)
        top10['Rev Δ%'] = top10.apply(lambda r: _dpct(r['Revenue'], r['Revenue_prev']), axis=1)
        top10['ROAS_prev'] = (top10['Revenue_prev'] / top10['Spend_prev']).round(2).where(top10['Spend_prev'] > 0, 0)
        top10['ROAS Δ%'] = top10.apply(lambda r: _dpct(r['ROAS'], r['ROAS_prev']), axis=1)

    _top10_cols = ['Campaign','Group','Campaign_Type','Spend','Revenue','ROAS','Conversions','CPC','Status']
    _top10_fmt = {'Spend':'Rs.{:,.0f}','Revenue':'Rs.{:,.0f}','ROAS':'{:.2f}x','CPC':'Rs.{:.0f}','Conversions':'{:,.1f}'}
    if has_comp:
        _top10_cols += ['Spend Δ%','Rev Δ%','ROAS Δ%']
        _top10_fmt['Spend Δ%'] = '{:+.1f}%'
        _top10_fmt['Rev Δ%'] = '{:+.1f}%'
        _top10_fmt['ROAS Δ%'] = '{:+.1f}%'
    st.dataframe(
        top10[_top10_cols].rename(columns={'Campaign_Type':'Type'})
        .style.apply(_row_roas_style, axis=1).format(_top10_fmt, na_rep='—'),
        use_container_width=True, height=400)

    st.markdown("---")

    # ── Section 4 — All campaigns table ─────────────────────────────────────
    st.markdown("#### All Campaigns")
    st.caption(f"Sorted by Spend · {len(camp_tbl)} campaigns · ROAS target: {roas_target}x")

    def _style_status(val):
        if '✅' in str(val):
            return 'background-color:#d4edda;color:#155724;font-weight:700'
        if '🔴' in str(val):
            return 'background-color:#f8d7da;color:#721c24;font-weight:700'
        return 'color:#6c757d'

    if has_comp:
        _df_c2_comp_all = df_camp_comp[df_camp_comp['Group'].isin(sel_groups)] if sel_groups else df_camp_comp
        _all_comp = (_df_c2_comp_all.groupby('Campaign')
                     .agg(Spend_prev=('Cost','sum'), Revenue_prev=('Conv_Value','sum'))
                     .reset_index())
        camp_tbl = camp_tbl.merge(_all_comp, on='Campaign', how='left').fillna(0)
        camp_tbl['Spend Δ%'] = camp_tbl.apply(lambda r: _dpct(r['Spend'], r['Spend_prev']), axis=1)
        camp_tbl['Rev Δ%'] = camp_tbl.apply(lambda r: _dpct(r['Revenue'], r['Revenue_prev']), axis=1)
        camp_tbl['ROAS_prev'] = (camp_tbl['Revenue_prev'] / camp_tbl['Spend_prev']).round(2).where(camp_tbl['Spend_prev'] > 0, 0)
        camp_tbl['ROAS Δ%'] = camp_tbl.apply(lambda r: _dpct(r['ROAS'], r['ROAS_prev']), axis=1)

    display_cols = ['Campaign', 'Group', 'Campaign_Type', 'Spend', 'Clicks',
                    'Conversions', 'Revenue', 'ROAS', 'CPC', 'Status']
    _disp_fmt = {'Spend':'Rs.{:,.0f}','Revenue':'Rs.{:,.0f}','ROAS':'{:.2f}x','CPC':'Rs.{:.0f}','Clicks':'{:,.0f}','Conversions':'{:,.1f}'}
    if has_comp:
        display_cols += ['Spend Δ%','Rev Δ%','ROAS Δ%']
        _disp_fmt['Spend Δ%'] = '{:+.1f}%'
        _disp_fmt['Rev Δ%'] = '{:+.1f}%'
        _disp_fmt['ROAS Δ%'] = '{:+.1f}%'
    styled = (camp_tbl[display_cols]
              .rename(columns={'Campaign_Type': 'Type'})
              .reset_index(drop=True)
              .style
              .map(_style_status, subset=['Status'])
              .format(_disp_fmt, na_rep='—'))
    st.dataframe(styled, use_container_width=True, height=480, hide_index=True)

    # ── Section 5 — Insights ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 💡 Campaign Insights")

    if has_comp:
        st.info(f"📊 Comparison mode: showing changes vs **{_comp_label}** ({comp_start.strftime('%d %b')} – {comp_end.strftime('%d %b %Y')})")

    _min_sp = max(5000.0, _total_sp * 0.02)
    _sig = camp_tbl[camp_tbl['Spend'] >= _min_sp] if _total_sp > 0 else camp_tbl

    ins1, ins2, ins3, ins4 = st.columns(4)

    _grp_roas = (df_c2.groupby('Group')
                 .apply(lambda g: g['Conv_Value'].sum() / g['Cost'].sum()
                        if g['Cost'].sum() > 0 else 0)
                 .reset_index(name='ROAS'))
    _best_grp = _grp_roas.loc[_grp_roas['ROAS'].idxmax()] if len(_grp_roas) else None

    with ins1:
        if _best_grp is not None:
            if has_comp and len(df_camp_comp) > 0:
                _grp_roas_comp = (df_camp_comp.groupby('Group')
                                  .apply(lambda g: g['Conv_Value'].sum() / g['Cost'].sum()
                                         if g['Cost'].sum() > 0 else 0)
                                  .reset_index(name='ROAS'))
                _best_grp_prev_row = _grp_roas_comp[_grp_roas_comp['Group'] == _best_grp['Group']]
                _best_grp_prev = _best_grp_prev_row['ROAS'].values[0] if len(_best_grp_prev_row) > 0 else 0
                _best_grp_sp = df_c2[df_c2['Group'] == _best_grp['Group']]['Cost'].sum()
                _best_grp_sp_prev = df_camp_comp[df_camp_comp['Group'] == _best_grp['Group']]['Cost'].sum() if len(df_camp_comp) > 0 else 0
                _sp_delta_str = f" · spend {'+' if _best_grp_sp >= _best_grp_sp_prev else ''}{_dpct(_best_grp_sp, _best_grp_sp_prev) or 0:.1f}% vs {_comp_label}" if _best_grp_sp_prev > 0 else ""
                st.markdown(f"""
                <div class="metric-card">
                  <div class="metric-label">🏆 Best Group (ROAS)</div>
                  <div class="metric-value" style="font-size:14px">{_best_grp['Group']}</div>
                  <div class="metric-delta" style="color:{BRAND_TEAL}">{_best_grp['ROAS']:.1f}x ROAS{_sp_delta_str}</div>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="metric-card">
                  <div class="metric-label">🏆 Best Group (ROAS)</div>
                  <div class="metric-value" style="font-size:14px">{_best_grp['Group']}</div>
                  <div class="metric-delta" style="color:{BRAND_TEAL}">{_best_grp['ROAS']:.1f}x ROAS</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="metric-card"><div class="metric-label">🏆 Best Group</div>'
                        '<div class="metric-value">—</div></div>', unsafe_allow_html=True)

    _top_camp = camp_tbl.iloc[0] if len(camp_tbl) else None
    with ins2:
        if _top_camp is not None:
            st.markdown(f"""
            <div class="metric-card">
              <div class="metric-label">💰 Top Spender</div>
              <div class="metric-value" style="font-size:13px">{_top_camp['Campaign']}</div>
              <div class="metric-delta" style="color:{BRAND_ORANGE}">
                Rs.{_top_camp['Spend']:,.0f} &nbsp;·&nbsp; ROAS {_top_camp['ROAS']:.1f}x
              </div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="metric-card"><div class="metric-label">💰 Top Spender</div>'
                        '<div class="metric-value">—</div></div>', unsafe_allow_html=True)

    _beat      = camp_tbl[camp_tbl['ROAS'] >= roas_target]
    _beat_sp   = _beat['Spend'].sum()
    _pct_beat  = _beat_sp / _total_sp * 100 if _total_sp > 0 else 0
    with ins3:
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-label">✅ Above ROAS Target</div>
          <div class="metric-value">{len(_beat)} / {len(camp_tbl)} campaigns</div>
          <div class="metric-delta" style="color:{BRAND_TEAL}">{_pct_beat:.0f}% of total spend</div>
        </div>""", unsafe_allow_html=True)

    _tot_clicks = df_c2['Clicks'].sum()
    _avg_cpc    = df_c2['Cost'].sum() / _tot_clicks if _tot_clicks > 0 else 0
    if has_comp:
        _spend_delta = _dpct(_total_sp, _pr_c_sp)
        _roas_delta  = _dpct(_c_roas, _pr_c_roas)
        _color = BRAND_TEAL if (_roas_delta or 0) >= 0 else BRAND_RED
        _arrow = "▲" if (_roas_delta or 0) >= 0 else "▼"
        with ins4:
            st.markdown(f"""
            <div class="metric-card">
              <div class="metric-label">📊 Period vs {_comp_label.title()}</div>
              <div class="metric-value" style="font-size:13px">Spend {'+' if (_spend_delta or 0)>=0 else ''}{(_spend_delta or 0):.1f}%</div>
              <div class="metric-delta" style="color:{_color}">{_arrow} ROAS {abs(_roas_delta or 0):.1f}%</div>
            </div>""", unsafe_allow_html=True)
    else:
        with ins4:
            st.markdown(f"""
            <div class="metric-card">
              <div class="metric-label">🖱️ Avg CPC</div>
              <div class="metric-value">Rs.{_avg_cpc:.0f}</div>
              <div class="metric-delta" style="color:#6c757d">{int(_tot_clicks):,} total clicks</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    _under = _sig[(_sig['ROAS'] < 1) & (_sig['ROAS'] > 0)].sort_values('Spend', ascending=False)
    if len(_under) > 0:
        _under_label = f"**⚠️ Under-performers (ROAS < 1x, spend > 1% of total):**" + (f" vs {_comp_label}" if has_comp else "")
        st.markdown(_under_label)
        st.dataframe(
            _under[['Campaign', 'Group', 'Spend', 'Revenue', 'ROAS']]
            .reset_index(drop=True)
            .style.format({'Spend': 'Rs.{:,.0f}', 'Revenue': 'Rs.{:,.0f}', 'ROAS': '{:.2f}x'}),
            use_container_width=True, hide_index=True)

    _scale = _sig[_sig['ROAS'] >= roas_target * 1.5].sort_values('ROAS', ascending=False).head(3)
    if len(_scale) > 0:
        _scale_label = f"**🚀 Scale candidates (ROAS ≥ 1.5× target):**" + (f" vs {_comp_label}" if has_comp else "")
        st.markdown(_scale_label)
        st.dataframe(
            _scale[['Campaign', 'Group', 'Spend', 'ROAS', 'Conversions']]
            .reset_index(drop=True)
            .style.format({'Spend': 'Rs.{:,.0f}', 'ROAS': '{:.2f}x', 'Conversions': '{:,.1f}'}),
            use_container_width=True, hide_index=True)


# ============================================================
# TAB 3 — Search Terms
# ============================================================
elif active_tab == "🔍 Search Terms":
    st.markdown("### Search Terms")

    with st.spinner("Loading search term data…"):
        df_brand_kw = load_search_terms_brand()
        df_pmax_kw  = load_search_terms_pmax()

    df_brand_kw_f = filter_dates(df_brand_kw, start_date, end_date)
    df_pmax_kw_f  = filter_dates(df_pmax_kw,  start_date, end_date)

    # Combine all search terms
    df_all_kw = pd.concat([df_brand_kw_f, df_pmax_kw_f], ignore_index=True)

    if has_comp:
        df_brand_kw_comp = filter_dates(load_search_terms_brand(), comp_start, comp_end)
        df_pmax_kw_comp  = filter_dates(load_search_terms_pmax(),  comp_start, comp_end)
        df_all_kw_comp   = pd.concat([df_brand_kw_comp, df_pmax_kw_comp], ignore_index=True)
    else:
        df_all_kw_comp   = pd.DataFrame(columns=df_all_kw.columns)

    # ── Overview strip ───────────────────────────────────────────────────────
    st.markdown("#### Overview by Term Type")
    _kw_grp_sum = (df_all_kw.groupby('Keyword_Group')
                   .agg(Spend=('Cost','sum'), Revenue=('Conv_Value','sum'),
                        Clicks=('Clicks','sum'), Conversions=('Conversions','sum'),
                        Terms=('Keyword','nunique'))
                   .reset_index())
    _kw_grp_sum['ROAS'] = (_kw_grp_sum['Revenue']/_kw_grp_sum['Spend']).round(2).where(
        _kw_grp_sum['Spend']>0, 0)

    if has_comp and len(df_all_kw_comp) > 0:
        _kw_grp_sum_c = (df_all_kw_comp.groupby('Keyword_Group')
                         .agg(Spend=('Cost','sum'), Revenue=('Conv_Value','sum'),
                              Clicks=('Clicks','sum'), Conversions=('Conversions','sum'),
                              Terms=('Keyword','nunique'))
                         .reset_index())
        _kw_grp_sum_c['ROAS'] = (_kw_grp_sum_c['Revenue']/_kw_grp_sum_c['Spend']).round(2).where(_kw_grp_sum_c['Spend']>0,0)
        _kw_comp_map = _kw_grp_sum_c.set_index('Keyword_Group').to_dict('index')
    else:
        _kw_comp_map = {}

    _kw_cols = st.columns(len(_kw_grp_sum))
    for _ci, (_col, _row) in enumerate(zip(_kw_cols, _kw_grp_sum.itertuples())):
        with _col:
            _prev_row = _kw_comp_map.get(_row.Keyword_Group, {})
            _sp_delta = _dpct(_row.Spend, _prev_row.get('Spend', 0))
            _roas_delta = _dpct(_row.ROAS, _prev_row.get('ROAS', 0))
            _delta_html = ''
            if _sp_delta is not None:
                _delta_html = f'<br>{_delta_badge(_sp_delta, "up")} spend &nbsp; {_delta_badge(_roas_delta, "up")} ROAS'
            st.markdown(f"""
            <div class="metric-card">
              <div class="metric-label">{_row.Keyword_Group}</div>
              <div class="metric-value" style="font-size:14px">
                Rs.{_row.Spend:,.0f} spend<br>
                ROAS {_row.ROAS:.1f}x<br>
                {int(_row.Terms):,} terms
              </div>
              <div class="metric-delta">{_delta_html}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    _kw_col_l, _kw_col_r = st.columns(2)
    with _kw_col_l:
        if has_comp and len(_kw_comp_map) > 0:
            _kw_curr_sp = _kw_grp_sum[['Keyword_Group','Spend']].copy(); _kw_curr_sp['Period']='Current'
            _kw_prev_sp = pd.DataFrame([{'Keyword_Group':k,'Spend':v.get('Spend',0),'Period':_comp_label.title()} for k,v in _kw_comp_map.items()])
            _kw_sp_comb = pd.concat([_kw_curr_sp, _kw_prev_sp])
            fig_kw_overview = px.bar(_kw_sp_comb, x='Keyword_Group', y='Spend',
                                      color='Period', barmode='group',
                                      color_discrete_sequence=[BRAND_ORANGE,'#ADB5BD'],
                                      title="Spend by Term Type", labels={'Spend':'Spend (Rs.)','Keyword_Group':''})
            fig_kw_overview.update_traces(hovertemplate="<b>%{x}</b> · %{data.name}<br>Spend: Rs.%{y:,.0f}<extra></extra>")
            fig_kw_overview.update_layout(showlegend=True, height=280, plot_bgcolor='white', paper_bgcolor='white')
        else:
            fig_kw_overview = px.bar(
                _kw_grp_sum.sort_values('Spend', ascending=False),
                x='Keyword_Group', y='Spend',
                color='Keyword_Group',
                color_discrete_map={'Branded': BRAND_ORANGE, 'Generic': BRAND_TEAL, 'Competitor': BRAND_RED},
                text=_kw_grp_sum.sort_values('Spend', ascending=False)['ROAS'].apply(lambda r: f"{r:.1f}x"),
                title="Spend by Term Type", labels={'Spend': 'Spend (Rs.)', 'Keyword_Group': ''},
            )
            fig_kw_overview.update_traces(textposition='outside')
            fig_kw_overview.update_traces(
                hovertemplate="<b>%{x}</b><br>Spend: Rs.%{y:,.0f}<br>ROAS: %{text}<extra></extra>"
            )
            fig_kw_overview.update_layout(showlegend=False, height=280, plot_bgcolor='white', paper_bgcolor='white')
        st.plotly_chart(fig_kw_overview, use_container_width=True)
    with _kw_col_r:
        if has_comp and len(_kw_comp_map) > 0:
            _kw_curr_roas = _kw_grp_sum[['Keyword_Group','ROAS']].copy(); _kw_curr_roas['Period']='Current'
            _kw_prev_roas = pd.DataFrame([{'Keyword_Group':k,'ROAS':v.get('ROAS',0),'Period':_comp_label.title()} for k,v in _kw_comp_map.items()])
            _kw_roas_comb = pd.concat([_kw_curr_roas, _kw_prev_roas])
            fig_kw_rev = px.bar(_kw_roas_comb, x='Keyword_Group', y='ROAS',
                                 color='Period', barmode='group',
                                 color_discrete_sequence=[BRAND_ORANGE,'#ADB5BD'],
                                 title="ROAS by Term Type", labels={'ROAS':'ROAS','Keyword_Group':''})
            fig_kw_rev.add_hline(y=roas_target, line_dash="dash", line_color=BRAND_RED,
                                  annotation_text=f"Target {roas_target}x", annotation_position="top right")
            fig_kw_rev.update_traces(hovertemplate="<b>%{x}</b> · %{data.name}<br>ROAS: %{y:.2f}x<extra></extra>")
            fig_kw_rev.update_layout(showlegend=True, height=280, plot_bgcolor='white', paper_bgcolor='white')
        else:
            fig_kw_rev = px.bar(
                _kw_grp_sum.sort_values('ROAS', ascending=False),
                x='Keyword_Group', y='ROAS',
                color='Keyword_Group',
                color_discrete_map={'Branded': BRAND_ORANGE, 'Generic': BRAND_TEAL, 'Competitor': BRAND_RED},
                text=_kw_grp_sum.sort_values('ROAS', ascending=False)['ROAS'].apply(lambda r: f"{r:.2f}x"),
                title="ROAS by Term Type", labels={'ROAS': 'ROAS', 'Keyword_Group': ''},
            )
            fig_kw_rev.update_traces(textposition='outside')
            fig_kw_rev.add_hline(y=roas_target, line_dash="dash", line_color=BRAND_RED,
                                  annotation_text=f"Target {roas_target}x", annotation_position="top right")
            fig_kw_rev.update_traces(
                hovertemplate="<b>%{x}</b><br>ROAS: %{y:.2f}x<br>Revenue: Rs.%{customdata[0]:,.0f}<br>Spend: Rs.%{customdata[1]:,.0f}<extra></extra>",
                customdata=_kw_grp_sum.sort_values('ROAS', ascending=False)[['Revenue','Spend']].values
            )
            fig_kw_rev.update_layout(showlegend=False, height=280, plot_bgcolor='white', paper_bgcolor='white')
        st.plotly_chart(fig_kw_rev, use_container_width=True)

    st.markdown("---")
    sub_branded, sub_generic, sub_competitor = st.tabs(
        ["🏷️ Branded", "🔎 Generic", "⚔️ Competitor"])

    def _kw_table_chart(df_kw, group_name, n=100, chart_n=15, df_kw_comp=None):
        sub = (df_kw[df_kw['Keyword_Group'] == group_name]
               .groupby('Keyword')
               .agg(Cost=('Cost', 'sum'), Clicks=('Clicks', 'sum'),
                    Conv_Value=('Conv_Value', 'sum'), Conversions=('Conversions', 'sum'))
               .reset_index())
        sub['ROAS'] = (sub['Conv_Value'] / sub['Cost']).round(2).where(sub['Cost'] > 0, 0)
        sub['CPA'] = (sub['Cost'] / sub['Conversions']).round(2).where(sub['Conversions'] > 0, 0)
        sub['Conv_Rate'] = (sub['Conversions'] / sub['Clicks'] * 100).round(2).where(sub['Clicks'] > 0, 0)
        sub = sub.sort_values('Conv_Value', ascending=False).head(n)

        if df_kw_comp is not None and len(df_kw_comp) > 0:
            sub_comp = (df_kw_comp[df_kw_comp['Keyword_Group'] == group_name]
                        .groupby('Keyword')
                        .agg(Cost_prev=('Cost','sum'), Conv_Value_prev=('Conv_Value','sum'),
                             Conversions_prev=('Conversions','sum'))
                        .reset_index())
            sub_comp['ROAS_prev'] = (sub_comp['Conv_Value_prev']/sub_comp['Cost_prev']).round(2).where(sub_comp['Cost_prev']>0, 0)
            sub = sub.merge(sub_comp[['Keyword','Cost_prev','Conv_Value_prev','ROAS_prev']], on='Keyword', how='left').fillna(0)
            sub['Spend Δ%'] = sub.apply(lambda r: _dpct(r['Cost'], r['Cost_prev']), axis=1)
            sub['ROAS Δ%'] = sub.apply(lambda r: _dpct(r['ROAS'], r['ROAS_prev']), axis=1)

        _kw_disp_cols = ['Keyword', 'Cost', 'Clicks', 'Conv_Value', 'Conversions', 'ROAS', 'CPA', 'Conv_Rate']
        _kw_fmt = {'Spend (Rs.)': 'Rs.{:,.0f}', 'Revenue (Rs.)': 'Rs.{:,.0f}',
                   'ROAS': '{:.2f}x', 'CPA': 'Rs.{:.0f}',
                   'Clicks': '{:,.0f}', 'Conversions': '{:,.1f}',
                   'Conv_Rate': '{:.2f}%'}
        if df_kw_comp is not None and 'Spend Δ%' in sub.columns:
            _kw_disp_cols += ['Spend Δ%', 'ROAS Δ%']
            _kw_fmt['Spend Δ%'] = '{:+.1f}%'
            _kw_fmt['ROAS Δ%'] = '{:+.1f}%'

        st.markdown(f"**Top {min(n, len(sub))} {group_name} keywords by Revenue**")
        st.dataframe(
            sub[_kw_disp_cols]
            .rename(columns={'Conv_Value': 'Revenue (Rs.)', 'Cost': 'Spend (Rs.)'})
            .style.format(_kw_fmt, na_rep='—'),
            use_container_width=True, height=400, hide_index=True)

        # top_chart sorted descending by current Revenue; highest at TOP of horizontal bar chart
        top_chart = sub.head(chart_n).copy()
        top_chart = top_chart.sort_values('Conv_Value', ascending=False).reset_index(drop=True)
        # Descending list → category_orders puts highest first → appears at TOP of chart
        _kw_order_desc = top_chart['Keyword'].tolist()  # already descending
        if df_kw_comp is not None and 'Conv_Value_prev' in sub.columns:
            _tc_curr = top_chart[['Keyword','Conv_Value','ROAS','Cost']].copy(); _tc_curr['Period']='Current'
            _tc_prev = top_chart[['Keyword','Conv_Value_prev','ROAS_prev','Cost_prev']].copy().rename(
                columns={'Conv_Value_prev':'Conv_Value','ROAS_prev':'ROAS','Cost_prev':'Cost'}); _tc_prev['Period']=_comp_label.title()
            _tc_comb = pd.concat([_tc_curr, _tc_prev])
            fig = px.bar(
                _tc_comb, x='Conv_Value', y='Keyword', orientation='h',
                color='Period', barmode='group',
                color_discrete_sequence=[GROUP_COLORS.get(f'{group_name} Search', BRAND_ORANGE), '#ADB5BD'],
                title=f"Top {chart_n} {group_name} keywords — Revenue (Rs.)",
                labels={'Conv_Value': 'Revenue (Rs.)', 'Keyword': ''},
                category_orders={'Keyword': _kw_order_desc},
                custom_data=['ROAS','Cost'],
            )
            fig.update_traces(
                hovertemplate="<b>%{y}</b> · %{data.name}<br>Revenue: Rs.%{x:,.0f}<br>ROAS: %{customdata[0]:.2f}x<br>Spend: Rs.%{customdata[1]:,.0f}<extra></extra>"
            )
            fig.update_layout(height=max(380, chart_n * 28), showlegend=True,
                               plot_bgcolor='white', paper_bgcolor='white',
                               margin=dict(t=40, b=0, r=80))
        else:
            fig = px.bar(
                top_chart[::-1], x='Conv_Value', y='Keyword', orientation='h',
                title=f"Top {chart_n} {group_name} keywords — Revenue (Rs.)",
                labels={'Conv_Value': 'Revenue (Rs.)', 'Keyword': ''},
                color_discrete_sequence=[GROUP_COLORS.get(f'{group_name} Search', BRAND_ORANGE)],
                text=top_chart[::-1]['ROAS'].apply(lambda r: f"{r:.1f}x"),
            )
            fig.update_traces(textposition='outside')
            fig.update_traces(
                hovertemplate="<b>%{y}</b><br>Revenue: Rs.%{x:,.0f}<br>ROAS: %{text}<extra></extra>"
            )
            fig.update_layout(height=max(380, chart_n * 28), showlegend=False,
                               plot_bgcolor='white', paper_bgcolor='white',
                               margin=dict(t=40, b=0, r=80))
        st.plotly_chart(fig, use_container_width=True)

        if len(sub) > 0:
            st.markdown("---")
            st.markdown("#### 💡 Insights")
            if has_comp:
                st.info(f"📊 Comparison mode: showing changes vs **{_comp_label}** ({comp_start.strftime('%d %b')} – {comp_end.strftime('%d %b %Y')})")
            _kw_total_spend = sub['Cost'].sum()
            _kw_min_sp = max(5000.0, _kw_total_spend * 0.02)
            _kw_elig = sub[sub['Cost'] >= _kw_min_sp]
            _has_elig = len(_kw_elig) > 0

            _best     = sub.iloc[0]  # highest revenue (no min-spend filter)
            _best_roas_pool = _kw_elig if _has_elig else sub
            _best_roas = _best_roas_pool.loc[_best_roas_pool['ROAS'].idxmax()] if _best_roas_pool['ROAS'].max() > 0 else None
            _worst_cands = _kw_elig[_kw_elig['ROAS'] > 0] if _has_elig else pd.DataFrame()
            _worst = _worst_cands.sort_values('ROAS').iloc[0] if len(_worst_cands) > 0 else None
            # Best conversion rate term (min-spend gated)
            _cvr_pool = _kw_elig[_kw_elig['Conv_Rate'] > 0] if _has_elig else sub[sub['Conv_Rate'] > 0]
            _best_cvr = _cvr_pool.loc[_cvr_pool['Conv_Rate'].idxmax()] if len(_cvr_pool) > 0 else None

            ic1, ic2, ic3, ic4 = st.columns(4)
            with ic1:
                _rev_delta_str = ''
                if df_kw_comp is not None and 'Spend Δ%' in sub.columns:
                    _rev_delta = _dpct(_best['Conv_Value'], _best.get('Conv_Value_prev', 0))
                    if _rev_delta is not None:
                        _rev_delta_str = f' · {_delta_badge(_rev_delta, "up")}'
                st.markdown(f"""<div class="metric-card">
  <div class="metric-label">💰 Top Revenue Term</div>
  <div class="metric-value" style="font-size:13px">{_best['Keyword'][:40]}</div>
  <div class="metric-delta" style="color:#00C9A7">Rs.{_best['Conv_Value']:,.0f} revenue · {_best['Conv_Rate']:.1f}% CVR{_rev_delta_str}</div>
</div>""", unsafe_allow_html=True)
            with ic2:
                if _best_roas is not None:
                    _roas_delta_str = ''
                    if df_kw_comp is not None and 'ROAS Δ%' in sub.columns:
                        _rd = _dpct(_best_roas['ROAS'], _best_roas.get('ROAS_prev', 0))
                        if _rd is not None:
                            _roas_delta_str = f' · {_delta_badge(_rd, "up")}'
                    st.markdown(f"""<div class="metric-card">
  <div class="metric-label">🏆 Best ROAS Term</div>
  <div class="metric-value" style="font-size:13px">{_best_roas['Keyword'][:40]}</div>
  <div class="metric-delta" style="color:#00C9A7">{_best_roas['ROAS']:.1f}x ROAS · Rs.{_best_roas['Cost']:,.0f} spend{_roas_delta_str}</div>
</div>""", unsafe_allow_html=True)
                else:
                    st.markdown('<div class="metric-card"><div class="metric-label">🏆 Best ROAS Term</div>'
                                '<div class="metric-value" style="font-size:13px">No conversions yet</div></div>',
                                unsafe_allow_html=True)
            with ic3:
                if _best_cvr is not None:
                    st.markdown(f"""<div class="metric-card">
  <div class="metric-label">🎯 Best Conv Rate Term</div>
  <div class="metric-value" style="font-size:13px">{_best_cvr['Keyword'][:40]}</div>
  <div class="metric-delta" style="color:#4361EE">{_best_cvr['Conv_Rate']:.2f}% CVR · Rs.{_best_cvr['Cost']:,.0f} spend</div>
</div>""", unsafe_allow_html=True)
                else:
                    st.markdown('<div class="metric-card"><div class="metric-label">🎯 Best Conv Rate</div>'
                                '<div class="metric-value" style="font-size:13px">No clicks yet</div></div>',
                                unsafe_allow_html=True)
            with ic4:
                if _worst is not None:
                    _worst_delta_str = ''
                    if df_kw_comp is not None and 'ROAS Δ%' in sub.columns:
                        _wd = _dpct(_worst['ROAS'], _worst.get('ROAS_prev', 0))
                        if _wd is not None:
                            _worst_delta_str = f' · {_delta_badge(_wd, "up")}'
                    st.markdown(f"""<div class="metric-card">
  <div class="metric-label">⚠️ Lowest ROAS Term</div>
  <div class="metric-value" style="font-size:13px">{_worst['Keyword'][:40]}</div>
  <div class="metric-delta" style="color:#E63946">{_worst['ROAS']:.1f}x ROAS · Rs.{_worst['Cost']:,.0f} spent{_worst_delta_str}</div>
</div>""", unsafe_allow_html=True)
                else:
                    st.markdown('<div class="metric-card"><div class="metric-label">⚠️ Lowest ROAS Term</div>'
                                '<div class="metric-value" style="font-size:13px">All terms above min spend threshold</div></div>',
                                unsafe_allow_html=True)

    with sub_branded:
        _kw_table_chart(df_all_kw, 'Branded', n=100, chart_n=15,
                        df_kw_comp=df_all_kw_comp if has_comp else None)

    with sub_generic:
        _kw_table_chart(df_all_kw, 'Generic', n=100, chart_n=15,
                        df_kw_comp=df_all_kw_comp if has_comp else None)

    with sub_competitor:
        _kw_table_chart(df_all_kw, 'Competitor', n=50, chart_n=15,
                        df_kw_comp=df_all_kw_comp if has_comp else None)

    # ── Impression-only terms ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 👁️ Impression-Only Terms (not spending)")
    st.caption("These terms are triggering your ads but getting zero clicks. Consider: add as exact-match keywords with dedicated bids, or add as negatives if irrelevant.")

    if 'Impressions' in df_brand_kw_f.columns:
        _imp_only_brand = (df_brand_kw_f[df_brand_kw_f['Cost'] == 0]
                           .groupby('Keyword')
                           .agg(Impressions=('Impressions', 'sum'), Clicks=('Clicks', 'sum'))
                           .reset_index())
        _imp_only_brand = _imp_only_brand[_imp_only_brand['Impressions'] > 100].sort_values('Impressions', ascending=False).head(20)
        if len(_imp_only_brand) > 0:
            st.dataframe(_imp_only_brand, use_container_width=True, hide_index=True)
        else:
            st.info("No impression-only terms found in the selected period.")
    else:
        st.info("Impressions column not available in brand keyword data.")


# ============================================================
# TAB 4 — Products & Collections
# ============================================================
elif active_tab == "🛒 Products & Collections":
    st.markdown("### Products & Collections")

    with st.spinner("Loading shopping data…"):
        df_shop = load_shopping()

    df_shop_f = filter_dates(df_shop, start_date, end_date, col='Day')

    if has_comp:
        df_shop_comp = filter_dates(load_shopping(), comp_start, comp_end, col='Day')
    else:
        df_shop_comp = pd.DataFrame(columns=df_shop_f.columns)

    # ── Category overview ────────────────────────────────────────────────────
    st.markdown("#### Category Overview")
    cat_overview = (df_shop_f.groupby('Category')
                    .agg(Spend=('Cost','sum'), Revenue=('Conv_Value','sum'),
                         Conversions=('Conversions','sum'))
                    .reset_index())
    cat_overview['ROAS'] = (cat_overview['Revenue']/cat_overview['Spend']).round(2).where(
        cat_overview['Spend']>0, 0)
    cat_overview = cat_overview[cat_overview['Spend']>0].sort_values('Revenue', ascending=False)

    if has_comp and len(df_shop_comp) > 0:
        _cat_comp = (df_shop_comp.groupby('Category')
                     .agg(Revenue_prev=('Conv_Value','sum'), Spend_prev=('Cost','sum'))
                     .reset_index())
        cat_overview = cat_overview.merge(_cat_comp, on='Category', how='left').fillna(0)

    _cat_cols = st.columns(len(cat_overview))
    for _col, _row in zip(_cat_cols, cat_overview.itertuples()):
        with _col:
            st.markdown(f"""
            <div class="metric-card">
              <div class="metric-label">{_row.Category}</div>
              <div class="metric-value" style="font-size:14px">
                {_fmt_inr(_row.Revenue)} rev<br>
                ROAS {_row.ROAS:.1f}x<br>
                {_fmt_inr(_row.Spend)} spend
              </div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_cat_bar, col_cat_roas = st.columns(2)
    with col_cat_bar:
        if has_comp and 'Spend_prev' in cat_overview.columns and cat_overview['Spend_prev'].sum() > 0:
            _co_curr = cat_overview[['Category','Spend']].copy(); _co_curr['Period'] = 'Current'
            _co_prev = cat_overview[['Category','Spend_prev']].copy().rename(columns={'Spend_prev':'Spend'}); _co_prev['Period'] = _comp_label.title()
            _co_comb = pd.concat([_co_curr, _co_prev])
            fig_cat = px.bar(_co_comb, x='Category', y='Spend', color='Period', barmode='group',
                             color_discrete_sequence=[BRAND_ORANGE,'#ADB5BD'],
                             title="Spend by Category", labels={'Spend':'Spend (Rs.)','Category':''})
            fig_cat.update_traces(hovertemplate="<b>%{x}</b> · %{data.name}<br>Spend: Rs.%{y:,.0f}<extra></extra>")
            fig_cat.update_layout(showlegend=True, height=260, plot_bgcolor='white', paper_bgcolor='white')
        else:
            fig_cat = px.bar(cat_overview, x='Category', y='Spend',
                             color='Category', text=cat_overview['ROAS'].apply(lambda r: f"{r:.1f}x"),
                             title="Spend by Category",
                             labels={'Spend':'Spend (Rs.)','Category':''})
            fig_cat.update_traces(textposition='outside')
            fig_cat.update_traces(
                hovertemplate="<b>%{x}</b><br>Spend: Rs.%{y:,.0f}<br>ROAS: %{text}<br>Revenue: Rs.%{customdata[0]:,.0f}<extra></extra>",
                customdata=cat_overview[['Revenue']].values
            )
            fig_cat.update_layout(showlegend=False, height=260,
                                   plot_bgcolor='white', paper_bgcolor='white')
        st.plotly_chart(fig_cat, use_container_width=True)
    with col_cat_roas:
        fig_cat_roas = px.bar(cat_overview, x='Category', y='ROAS',
                              color='Category', text=cat_overview['ROAS'].apply(lambda r: f"{r:.1f}x"),
                              title="ROAS by Category",
                              labels={'ROAS':'ROAS','Category':''})
        fig_cat_roas.update_traces(textposition='outside')
        fig_cat_roas.update_traces(
            hovertemplate="<b>%{x}</b><br>ROAS: %{y:.2f}x<extra></extra>"
        )
        fig_cat_roas.add_hline(y=roas_target, line_dash="dash", line_color=BRAND_RED,
                               annotation_text=f"Target {roas_target}x")
        fig_cat_roas.update_layout(showlegend=False, height=260,
                                    plot_bgcolor='white', paper_bgcolor='white')
        st.plotly_chart(fig_cat_roas, use_container_width=True)

    st.markdown("---")

    # Category filter
    cats = ['All'] + sorted(df_shop_f['Category'].unique().tolist())
    sel_cat = st.selectbox("Filter by category", cats, key='shop_cat')
    df_s = df_shop_f if sel_cat == 'All' else df_shop_f[df_shop_f['Category'] == sel_cat]

    if has_comp:
        df_s_comp = df_shop_comp if sel_cat == 'All' else df_shop_comp[df_shop_comp['Category'] == sel_cat] if len(df_shop_comp) > 0 else pd.DataFrame(columns=df_s.columns)
    else:
        df_s_comp = pd.DataFrame(columns=df_s.columns)

    # ── Full-width Collections ───────────────────────────────────────────────
    st.markdown("#### Top 15 Collections by Revenue")
    coll_tbl = (df_s.groupby(['Collection', 'Category'])
                .agg(Spend=('Cost', 'sum'), Revenue=('Conv_Value', 'sum'),
                     Conversions=('Conversions', 'sum'))
                .reset_index())
    coll_tbl['ROAS'] = (coll_tbl['Revenue'] / coll_tbl['Spend']).round(2).where(
        coll_tbl['Spend'] > 0, 0)
    coll_tbl = coll_tbl[coll_tbl['Spend'] > 0].sort_values('Revenue', ascending=False).head(15)

    if has_comp and len(df_s_comp) > 0:
        coll_tbl_comp = (df_s_comp.groupby(['Collection', 'Category'])
                         .agg(Revenue_prev=('Conv_Value','sum'), Spend_prev=('Cost','sum'),
                              Conversions_prev=('Conversions','sum'))
                         .reset_index())
        coll_tbl = coll_tbl.merge(
            coll_tbl_comp[['Collection','Category','Revenue_prev','Spend_prev','Conversions_prev']],
            on=['Collection','Category'], how='left').fillna(0)
        coll_tbl['ROAS_prev'] = (coll_tbl['Revenue_prev'] / coll_tbl['Spend_prev']).round(2).where(coll_tbl['Spend_prev'] > 0, 0)
        coll_tbl['Rev Δ%']   = coll_tbl.apply(lambda r: _dpct(r['Revenue'],     r['Revenue_prev']),     axis=1)
        coll_tbl['Spend Δ%'] = coll_tbl.apply(lambda r: _dpct(r['Spend'],       r['Spend_prev']),       axis=1)
        coll_tbl['ROAS Δ%']  = coll_tbl.apply(lambda r: _dpct(r['ROAS'],        r['ROAS_prev']),        axis=1)
        coll_tbl['Conv Δ%']  = coll_tbl.apply(lambda r: _dpct(r['Conversions'], r['Conversions_prev']), axis=1)

    # Descending order: category_orders first item → TOP of horizontal bar chart
    _coll_order_desc = coll_tbl.sort_values('Revenue', ascending=False)['Collection'].tolist()

    if has_comp and 'Revenue_prev' in coll_tbl.columns:
        # Per-collection grouped: 2 bars per collection (Current + Previous), colored by Category
        # Sort ascending so Plotly default reversal puts highest at TOP
        _coll_sorted_asc = coll_tbl.sort_values('Revenue', ascending=True)
        _cc_curr = _coll_sorted_asc[['Collection','Revenue','Category','ROAS','Spend']].copy()
        _cc_curr['Period'] = 'Current'
        _cc_prev = _coll_sorted_asc[['Collection','Revenue_prev','Category','ROAS_prev','Spend_prev']].copy().rename(
            columns={'Revenue_prev':'Revenue','ROAS_prev':'ROAS','Spend_prev':'Spend'})
        _cc_prev['Period'] = _comp_label.title()
        _cc_comb = pd.concat([_cc_curr, _cc_prev], ignore_index=True)

        fig_coll = px.bar(
            _cc_comb, x='Revenue', y='Collection', orientation='h',
            color='Category',
            facet_col='Period',
            facet_col_spacing=0.15,
            barmode='stack',
            title="Top 15 Collections — Current vs Previous Period (by Category)",
            labels={'Revenue': 'Revenue (Rs.)', 'Collection': ''},
            custom_data=['ROAS','Spend','Category'],
        )
        fig_coll.update_traces(
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Category: %{customdata[2]}<br>"
                "Revenue: Rs.%{x:,.0f}<br>"
                "ROAS: %{customdata[0]:.2f}x<br>"
                "Spend: Rs.%{customdata[1]:,.0f}"
                "<extra></extra>"
            )
        )
        # Clean facet titles ("Period=Current" → "Current")
        fig_coll.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1],
                                                          font=dict(size=13, color='#333')))
        # Show y-axis labels only on left panel; hide on right to avoid overlap
        fig_coll.update_yaxes(showticklabels=True, col=1)
        fig_coll.update_yaxes(showticklabels=False, col=2)
        fig_coll.update_layout(height=580, plot_bgcolor='white', paper_bgcolor='white',
                                margin=dict(t=60, b=20, l=180, r=20), showlegend=True)
    else:
        fig_coll = px.bar(
            coll_tbl[::-1], x='Revenue', y='Collection', orientation='h',
            color='Category', title="Top 15 Collections by Revenue",
            labels={'Revenue': 'Revenue (Rs.)', 'Collection': ''},
            text=coll_tbl[::-1]['ROAS'].apply(lambda r: f"{r:.1f}x"),
            category_orders={'Collection': _coll_order_desc},
            custom_data=[coll_tbl[::-1]['Spend'], coll_tbl[::-1]['Conversions']],
        )
        fig_coll.update_traces(textposition='outside')
        fig_coll.update_traces(
            hovertemplate=(
                "<b>%{y}</b> · <b>%{fullData.name}</b><br>"
                "Revenue: Rs.%{x:,.0f}<br>"
                "ROAS: %{text}<br>"
                "Spend: Rs.%{customdata[0]:,.0f}<br>"
                "Conversions: %{customdata[1]:.1f}"
                "<extra></extra>"
            )
        )
        fig_coll.update_layout(height=500, plot_bgcolor='white', paper_bgcolor='white',
                                margin=dict(t=40, b=0, l=160, r=80))
    st.plotly_chart(fig_coll, use_container_width=True)

    _coll_disp_cols = ['Collection', 'Category', 'Spend', 'Revenue', 'ROAS', 'Conversions']
    _coll_fmt = {'Spend': 'Rs.{:,.0f}', 'Revenue': 'Rs.{:,.0f}', 'ROAS': '{:.2f}x', 'Conversions': '{:,.1f}'}
    if has_comp and 'Rev Δ%' in coll_tbl.columns:
        _coll_disp_cols += ['Spend Δ%', 'Rev Δ%', 'ROAS Δ%', 'Conv Δ%']
        _coll_fmt['Spend Δ%'] = '{:+.1f}%'
        _coll_fmt['Rev Δ%']   = '{:+.1f}%'
        _coll_fmt['ROAS Δ%']  = '{:+.1f}%'
        _coll_fmt['Conv Δ%']  = '{:+.1f}%'
    st.dataframe(
        coll_tbl[_coll_disp_cols]
        .style.format(_coll_fmt, na_rep='—'),
        use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── Full-width Products ──────────────────────────────────────────────────
    st.markdown("#### Top 15 Products by Revenue")
    prod_tbl = (df_s.groupby(['Product_Title', 'Collection', 'Category'])
                .agg(Spend=('Cost', 'sum'), Revenue=('Conv_Value', 'sum'),
                     Conversions=('Conversions', 'sum'))
                .reset_index())
    prod_tbl['ROAS'] = (prod_tbl['Revenue'] / prod_tbl['Spend']).round(2).where(
        prod_tbl['Spend'] > 0, 0)
    prod_tbl = prod_tbl[prod_tbl['Spend'] > 0].sort_values('Revenue', ascending=False).head(15)
    prod_tbl['Short_Title'] = prod_tbl['Product_Title'].str[:50] + '…'

    if has_comp and len(df_s_comp) > 0:
        prod_tbl_comp = (df_s_comp.groupby(['Product_Title', 'Collection', 'Category'])
                         .agg(Revenue_prev=('Conv_Value','sum'), Spend_prev=('Cost','sum'))
                         .reset_index())
        prod_tbl_comp['ROAS_prev'] = (prod_tbl_comp['Revenue_prev']/prod_tbl_comp['Spend_prev']).round(2).where(prod_tbl_comp['Spend_prev']>0, 0)
        prod_tbl = prod_tbl.merge(prod_tbl_comp[['Product_Title','Revenue_prev','ROAS_prev']], on='Product_Title', how='left').fillna(0)
        prod_tbl['Rev Δ%'] = prod_tbl.apply(lambda r: _dpct(r['Revenue'], r['Revenue_prev']), axis=1)
        prod_tbl['ROAS Δ%'] = prod_tbl.apply(lambda r: _dpct(r['ROAS'], r['ROAS_prev']), axis=1)

    if has_comp and 'Revenue_prev' in prod_tbl.columns:
        _pc_curr = prod_tbl[['Short_Title','Revenue']].copy(); _pc_curr['Period']='Current'
        _pc_prev = prod_tbl[['Short_Title','Revenue_prev']].copy().rename(columns={'Revenue_prev':'Revenue'}); _pc_prev['Period']=_comp_label.title()
        # prev first → bottom bar; curr second → top bar (read first)
        _pc_comb = pd.concat([_pc_prev, _pc_curr])
        fig_prod = px.bar(
            _pc_comb, x='Revenue', y='Short_Title', orientation='h',
            color='Period', barmode='group',
            color_discrete_map={'Current': BRAND_ORANGE, _comp_label.title(): '#ADB5BD'},
            title="Top 15 Products by Revenue",
            labels={'Revenue': 'Revenue (Rs.)', 'Short_Title': ''},
        )
        fig_prod.update_traces(hovertemplate="<b>%{y}</b> · %{data.name}<br>Revenue: Rs.%{x:,.0f}<extra></extra>")
        fig_prod.update_layout(height=640, plot_bgcolor='white', paper_bgcolor='white',
                                margin=dict(t=40, b=0, l=260, r=80),
                                yaxis=dict(tickfont=dict(size=10), automargin=True), showlegend=True)
    else:
        fig_prod = px.bar(
            prod_tbl[::-1], x='Revenue', y='Short_Title', orientation='h',
            color='Category', title="Top 15 Products by Revenue",
            labels={'Revenue': 'Revenue (Rs.)', 'Short_Title': ''},
            text=prod_tbl[::-1]['ROAS'].apply(lambda r: f"{r:.1f}x"),
            custom_data=[prod_tbl[::-1]['Product_Title'], prod_tbl[::-1]['Conversions']],
        )
        fig_prod.update_traces(textposition='auto')
        fig_prod.update_traces(
            hovertemplate="<b>%{customdata[0]}</b><br>Revenue: Rs.%{x:,.0f}<br>ROAS: %{text}<br>Conversions: %{customdata[1]:,.1f}<extra></extra>"
        )
        fig_prod.update_layout(height=640, plot_bgcolor='white', paper_bgcolor='white',
                                margin=dict(t=40, b=0, l=260, r=80),
                                yaxis=dict(tickfont=dict(size=10), automargin=True))
    st.plotly_chart(fig_prod, use_container_width=True)

    _prod_disp_cols = ['Short_Title', 'Collection', 'Category', 'Spend', 'Revenue', 'ROAS', 'Conversions']
    _prod_fmt = {'Spend': 'Rs.{:,.0f}', 'Revenue': 'Rs.{:,.0f}', 'ROAS': '{:.2f}x', 'Conversions': '{:,.1f}'}
    if has_comp and 'Rev Δ%' in prod_tbl.columns:
        _prod_disp_cols += ['Rev Δ%', 'ROAS Δ%']
        _prod_fmt['Rev Δ%'] = '{:+.1f}%'
        _prod_fmt['ROAS Δ%'] = '{:+.1f}%'
    st.dataframe(
        prod_tbl[_prod_disp_cols]
        .rename(columns={'Short_Title': 'Product'})
        .style.format(_prod_fmt, na_rep='—'),
        use_container_width=True, height=480, hide_index=True)

    st.markdown("---")

    # ── Product Insights ─────────────────────────────────────────────────────
    st.markdown("#### 💡 Product Insights")
    if has_comp:
        st.info(f"📊 Comparison mode: showing changes vs **{_comp_label}** ({comp_start.strftime('%d %b')} – {comp_end.strftime('%d %b %Y')})")
    if len(prod_tbl) > 0:
        _prod_total_spend = prod_tbl['Spend'].sum()
        _min_sp = max(5000.0, _prod_total_spend * 0.02)
        _prod_elig = prod_tbl[prod_tbl['Spend'] >= _min_sp]
        _best_roas_prod = _prod_elig.loc[_prod_elig['ROAS'].idxmax()] if len(_prod_elig) > 0 else prod_tbl.loc[prod_tbl['ROAS'].idxmax()]
        _best_rev_prod  = prod_tbl.iloc[0]  # already sorted by Revenue desc
        _worst_cands = _prod_elig[_prod_elig['ROAS'] > 0]
        _worst_roas_prod = _worst_cands.loc[_worst_cands['ROAS'].idxmin()] if len(_worst_cands) > 0 else None

        # Best category ROAS from the full filtered shopping data
        _cat_roas_tbl = (df_s.groupby('Category')
                         .apply(lambda g: g['Conv_Value'].sum() / g['Cost'].sum()
                                if g['Cost'].sum() > 0 else 0)
                         .reset_index(name='ROAS'))
        _best_cat = _cat_roas_tbl.loc[_cat_roas_tbl['ROAS'].idxmax()] if len(_cat_roas_tbl) > 0 else None

        pi1, pi2, pi3, pi4 = st.columns(4)
        with pi1:
            st.markdown(f"""
<div class="metric-card">
  <div class="metric-label">🏆 Best ROAS Product</div>
  <div class="metric-value" style="font-size:13px">{_best_roas_prod['Short_Title']}</div>
  <div class="metric-delta" style="color:#00C9A7">{_best_roas_prod['ROAS']:.1f}x ROAS</div>
</div>""", unsafe_allow_html=True)
        with pi2:
            st.markdown(f"""
<div class="metric-card">
  <div class="metric-label">💰 Highest Revenue Product</div>
  <div class="metric-value" style="font-size:13px">{_best_rev_prod['Short_Title']}</div>
  <div class="metric-delta" style="color:#00C9A7">{_fmt_inr(_best_rev_prod['Revenue'])} revenue</div>
</div>""", unsafe_allow_html=True)
        with pi3:
            if _worst_roas_prod is not None:
                st.markdown(f"""
<div class="metric-card">
  <div class="metric-label">⚠️ Worst ROAS Product (&gt;5% spend)</div>
  <div class="metric-value" style="font-size:13px">{_worst_roas_prod['Short_Title']}</div>
  <div class="metric-delta" style="color:#E63946">{_worst_roas_prod['ROAS']:.1f}x ROAS</div>
</div>""", unsafe_allow_html=True)
            else:
                st.markdown('<div class="metric-card"><div class="metric-label">⚠️ Worst ROAS Product</div>'
                            '<div class="metric-value">—</div></div>', unsafe_allow_html=True)
        with pi4:
            if _best_cat is not None:
                st.markdown(f"""
<div class="metric-card">
  <div class="metric-label">🏅 Best Category by ROAS</div>
  <div class="metric-value" style="font-size:13px">{_best_cat['Category']}</div>
  <div class="metric-delta" style="color:#00C9A7">{_best_cat['ROAS']:.1f}x ROAS</div>
</div>""", unsafe_allow_html=True)
            else:
                st.markdown('<div class="metric-card"><div class="metric-label">🏅 Best Category</div>'
                            '<div class="metric-value">—</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        _scale_prods = prod_tbl[prod_tbl['ROAS'] > 5].sort_values('ROAS', ascending=False)
        if len(_scale_prods) > 0:
            st.markdown("**🚀 Scale candidates — ROAS > 5x:**")
            st.dataframe(
                _scale_prods[['Short_Title', 'Collection', 'Category', 'Spend', 'Revenue', 'ROAS', 'Conversions']]
                .rename(columns={'Short_Title': 'Product'})
                .style.format({'Spend': 'Rs.{:,.0f}', 'Revenue': 'Rs.{:,.0f}',
                               'ROAS': '{:.2f}x', 'Conversions': '{:,.1f}'}),
                use_container_width=True, hide_index=True)

        _under_prods = prod_tbl[(prod_tbl['ROAS'] < 1) & (prod_tbl['Spend'] > 5000)].sort_values('Spend', ascending=False)
        if len(_under_prods) > 0:
            st.markdown("**⚠️ Under-performers — ROAS < 1x and spend > Rs.5,000:**")
            st.dataframe(
                _under_prods[['Short_Title', 'Collection', 'Category', 'Spend', 'Revenue', 'ROAS', 'Conversions']]
                .rename(columns={'Short_Title': 'Product'})
                .style.format({'Spend': 'Rs.{:,.0f}', 'Revenue': 'Rs.{:,.0f}',
                               'ROAS': '{:.2f}x', 'Conversions': '{:,.1f}'}),
                use_container_width=True, hide_index=True)


# ============================================================
# TAB 5 — Landing Pages
# ============================================================
elif active_tab == "📄 Landing Pages":
    st.markdown(f"### Landing Pages — {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}")

    with st.spinner("Loading landing page data…"):
        df_lp = load_landing_pages()

    df_lp_f = filter_dates(df_lp, start_date, end_date)

    # ── Overview KPIs ────────────────────────────────────────────────────────
    _lp_all = (df_lp_f.groupby('Display_URL')
               .agg(Spend=('Cost', 'sum'), Revenue=('Conv_Value', 'sum'),
                    Clicks=('Clicks', 'sum'), Conversions=('Conversions', 'sum'))
               .reset_index())
    _lp_tot_spend  = _lp_all['Spend'].sum()
    _lp_tot_rev    = _lp_all['Revenue'].sum()
    _lp_tot_clicks = _lp_all['Clicks'].sum()
    _lp_tot_conv   = _lp_all['Conversions'].sum()
    _lp_roas   = round(_lp_tot_rev / _lp_tot_spend, 2) if _lp_tot_spend > 0 else 0
    _lp_cvr    = round(_lp_tot_conv / _lp_tot_clicks * 100, 2) if _lp_tot_clicks > 0 else 0
    _lp_cpa    = round(_lp_tot_spend / _lp_tot_conv, 0) if _lp_tot_conv > 0 else 0

    if has_comp:
        df_lp_comp = filter_dates(load_landing_pages(), comp_start, comp_end)
        _pr_lp_sp  = df_lp_comp['Cost'].sum()
        _pr_lp_rev = df_lp_comp['Conv_Value'].sum()
        _pr_lp_clicks = df_lp_comp['Clicks'].sum()
        _pr_lp_conv = df_lp_comp['Conversions'].sum()
        _pr_lp_roas = round(_pr_lp_rev / _pr_lp_sp, 2) if _pr_lp_sp > 0 else 0
        _pr_lp_cvr = round(_pr_lp_conv / _pr_lp_clicks * 100, 2) if _pr_lp_clicks > 0 else 0
        _pr_lp_cpa = round(_pr_lp_sp / _pr_lp_conv, 0) if _pr_lp_conv > 0 else 0
    else:
        _pr_lp_sp = _pr_lp_rev = _pr_lp_roas = _pr_lp_cvr = _pr_lp_cpa = 0

    lk1, lk2, lk3, lk4, lk5, lk6 = st.columns(6)
    kpi_card(lk1, "Total Spend",   _lp_tot_spend,  inr=True, delta=_dpct(_lp_tot_spend, _pr_lp_sp), delta_good='down')
    kpi_card(lk2, "ROAS",          _lp_roas,        fmt="{:.2f}", suffix="x", delta=_dpct(_lp_roas, _pr_lp_roas), delta_good='up')
    kpi_card(lk3, "Revenue",       _lp_tot_rev,    inr=True, delta=_dpct(_lp_tot_rev, _pr_lp_rev), delta_good='up')
    kpi_card(lk4, "Conversions",   _lp_tot_conv,   fmt="{:,.0f}", delta=_dpct(_lp_tot_conv, _pr_lp_conv if has_comp else 0), delta_good='up')
    kpi_card(lk5, "Conv Rate",     _lp_cvr,         fmt="{:.2f}", suffix="%", delta=_dpct(_lp_cvr, _pr_lp_cvr), delta_good='up')
    kpi_card(lk6, "CPA",           _lp_cpa,        inr=True, delta=_dpct(_lp_cpa, _pr_lp_cpa), delta_good='down')

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Page type overview (mini breakdown) ──────────────────────────────────
    st.markdown("#### Breakdown by Page Type")
    _lp_type_ov = (df_lp_f.groupby('Page_Type')
                   .agg(Spend=('Cost', 'sum'), Revenue=('Conv_Value', 'sum'),
                        Clicks=('Clicks', 'sum'), Conversions=('Conversions', 'sum'))
                   .reset_index())
    _lp_type_ov['ROAS']     = (_lp_type_ov['Revenue'] / _lp_type_ov['Spend']).round(2).where(
        _lp_type_ov['Spend'] > 0, 0)
    _lp_type_ov['CVR_pct']  = (_lp_type_ov['Conversions'] / _lp_type_ov['Clicks'] * 100).round(2).where(
        _lp_type_ov['Clicks'] > 0, 0)
    _lp_type_ov['CPA']      = (_lp_type_ov['Spend'] / _lp_type_ov['Conversions']).round(0).where(
        _lp_type_ov['Conversions'] > 0, 0)
    _lp_type_ov['Spend_pct'] = (_lp_type_ov['Spend'] / _lp_type_ov['Spend'].sum() * 100).round(1)
    _lp_type_ov = _lp_type_ov[_lp_type_ov['Spend'] > 0].sort_values('Revenue', ascending=False).reset_index(drop=True)

    if has_comp and len(df_lp_comp) > 0:
        _lp_type_comp = (df_lp_comp.groupby('Page_Type')
                         .agg(Revenue_prev=('Conv_Value','sum'),
                              Conversions_prev=('Conversions','sum'),
                              Clicks_prev=('Clicks','sum'))
                         .reset_index())
        _lp_type_comp['CVR_prev'] = (_lp_type_comp['Conversions_prev'] / _lp_type_comp['Clicks_prev'] * 100).round(2).where(_lp_type_comp['Clicks_prev'] > 0, 0)
        _lp_type_ov = _lp_type_ov.merge(_lp_type_comp[['Page_Type','Revenue_prev','CVR_prev']], on='Page_Type', how='left').fillna(0)
    else:
        _lp_type_ov['Revenue_prev'] = 0
        _lp_type_ov['CVR_prev'] = 0

    _pt_cols = st.columns(min(len(_lp_type_ov), 5))
    for _col, _row in zip(_pt_cols, _lp_type_ov.to_dict('records')):
        with _col:
            _pt_roas_color = BRAND_TEAL if _row['ROAS'] >= roas_target else (BRAND_RED if _row['ROAS'] > 0 else '#6c757d')
            st.markdown(f"""
<div class="metric-card">
  <div class="metric-label">{_row['Page_Type']}</div>
  <div class="metric-value" style="font-size:13px">{_fmt_inr(_row['Revenue'])}</div>
  <div class="metric-delta" style="color:{_pt_roas_color}">ROAS {_row['ROAS']:.1f}x &nbsp;·&nbsp; CVR {_row['CVR_pct']:.2f}%</div>
  <div class="metric-delta" style="color:#6c757d">{_fmt_inr(_row['Spend'])} spend · {_row['Spend_pct']:.0f}%</div>
</div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Always build _lp_type_ov2 (with Spend_prev/ROAS_prev) for use in both columns
    if has_comp and len(df_lp_comp) > 0:
        _lp_sp_comp = (df_lp_comp.groupby('Page_Type')['Cost'].sum()
                       .reset_index().rename(columns={'Cost':'Spend_prev'}))
        _lp_type_ov2 = _lp_type_ov.merge(_lp_sp_comp, on='Page_Type', how='left').fillna(0)
    else:
        _lp_type_ov2 = _lp_type_ov.copy()
        _lp_type_ov2['Spend_prev'] = 0
    _lp_type_ov2['ROAS_prev'] = (_lp_type_ov2['Revenue_prev'] / _lp_type_ov2['Spend_prev']).round(2).where(
        _lp_type_ov2['Spend_prev'] > 0, 0)

    col_lp_bar, col_lp_roas = st.columns(2)
    with col_lp_bar:
        # Spend as bar height, ROAS as text label on top, both in hover
        if has_comp and _lp_type_ov2['Revenue_prev'].sum() > 0:
            _lpt_curr = _lp_type_ov2[['Page_Type','Spend','ROAS']].copy()
            _lpt_curr['Period'] = 'Current'
            _lpt_curr['roas_label'] = _lpt_curr['ROAS'].apply(lambda r: f"{r:.1f}x")
            _lpt_prev = _lp_type_ov2[['Page_Type','Spend_prev','ROAS_prev']].copy().rename(
                columns={'Spend_prev':'Spend','ROAS_prev':'ROAS'})
            _lpt_prev['Period'] = _comp_label.title()
            _lpt_prev['roas_label'] = _lpt_prev['ROAS'].apply(lambda r: f"{r:.1f}x")
            _lpt_comb = pd.concat([_lpt_curr, _lpt_prev])
            fig_lp_type = px.bar(_lpt_comb, x='Page_Type', y='Spend', color='Period',
                                  text='roas_label', barmode='group',
                                  color_discrete_sequence=[BRAND_ORANGE,'#ADB5BD'],
                                  title="Spend by Page Type (ROAS on bars)",
                                  labels={'Spend':'Spend (Rs.)','Page_Type':''})
            fig_lp_type.update_traces(
                textposition='outside',
                hovertemplate="<b>%{x}</b> · %{data.name}<br>Spend: Rs.%{y:,.0f}<br>ROAS: %{text}<extra></extra>"
            )
            fig_lp_type.update_layout(showlegend=True, height=300, plot_bgcolor='white', paper_bgcolor='white',
                                       margin=dict(t=55,b=10,l=10,r=10))
        else:
            fig_lp_type = px.bar(
                _lp_type_ov, x='Page_Type', y='Spend',
                color='Page_Type',
                text=_lp_type_ov['ROAS'].apply(lambda r: f"{r:.1f}x"),
                title="Spend by Page Type (ROAS on bars)",
                labels={'Spend': 'Spend (Rs.)', 'Page_Type': ''},
            )
            fig_lp_type.update_traces(
                textposition='outside',
                hovertemplate=(
                    "<b>%{x}</b><br>Spend: Rs.%{y:,.0f}<br>ROAS: %{text}<br>"
                    "Revenue: Rs.%{customdata[0]:,.0f}<extra></extra>"
                ),
                customdata=_lp_type_ov[['Revenue']].values
            )
            fig_lp_type.update_layout(showlegend=False, height=300, plot_bgcolor='white', paper_bgcolor='white',
                                       margin=dict(t=55,b=10,l=10,r=10))
        st.plotly_chart(fig_lp_type, use_container_width=True)
    with col_lp_roas:
        # Spend as bar height, CVR as text label on top, both in hover
        if has_comp and _lp_type_ov2['CVR_prev'].sum() > 0:
            _lpc_curr = _lp_type_ov2[['Page_Type','Spend','CVR_pct']].copy().rename(columns={'CVR_pct':'CVR'})
            _lpc_curr['Period'] = 'Current'
            _lpc_curr['cvr_label'] = _lpc_curr['CVR'].apply(lambda r: f"{r:.2f}%")
            _lpc_prev = _lp_type_ov2[['Page_Type','Spend_prev','CVR_prev']].copy().rename(
                columns={'Spend_prev':'Spend','CVR_prev':'CVR'})
            _lpc_prev['Period'] = _comp_label.title()
            _lpc_prev['cvr_label'] = _lpc_prev['CVR'].apply(lambda r: f"{r:.2f}%")
            _lpc_comb = pd.concat([_lpc_curr, _lpc_prev])
            fig_lp_cvr = px.bar(_lpc_comb, x='Page_Type', y='Spend', color='Period',
                                 text='cvr_label', barmode='group',
                                 color_discrete_sequence=[BRAND_ORANGE,'#ADB5BD'],
                                 title="Spend by Page Type (CVR on bars)",
                                 labels={'Spend':'Spend (Rs.)','Page_Type':''})
            fig_lp_cvr.update_traces(
                textposition='outside',
                hovertemplate="<b>%{x}</b> · %{data.name}<br>Spend: Rs.%{y:,.0f}<br>CVR: %{text}<extra></extra>"
            )
            fig_lp_cvr.update_layout(showlegend=True, height=300, plot_bgcolor='white', paper_bgcolor='white',
                                      margin=dict(t=55,b=10,l=10,r=10))
        else:
            fig_lp_cvr = px.bar(
                _lp_type_ov, x='Page_Type', y='Spend',
                color='Page_Type',
                text=_lp_type_ov['CVR_pct'].apply(lambda r: f"{r:.2f}%"),
                title="Spend by Page Type (CVR on bars)",
                labels={'Spend': 'Spend (Rs.)', 'Page_Type': ''},
            )
            fig_lp_cvr.update_traces(
                textposition='outside',
                hovertemplate="<b>%{x}</b><br>Spend: Rs.%{y:,.0f}<br>CVR: %{text}<extra></extra>"
            )
            fig_lp_cvr.update_layout(showlegend=False, height=300, plot_bgcolor='white', paper_bgcolor='white',
                                      margin=dict(t=55,b=10,l=10,r=10))
        st.plotly_chart(fig_lp_cvr, use_container_width=True)

    st.dataframe(
        _lp_type_ov[['Page_Type', 'Spend', 'Revenue', 'ROAS', 'Conversions', 'CVR_pct', 'CPA', 'Spend_pct']]
        .rename(columns={'Page_Type': 'Type', 'CVR_pct': 'CVR%', 'Spend_pct': 'Spend %'})
        .style.format({'Spend': 'Rs.{:,.0f}', 'Revenue': 'Rs.{:,.0f}', 'ROAS': '{:.2f}x',
                       'Conversions': '{:,.1f}', 'CVR%': '{:.2f}%', 'CPA': 'Rs.{:,.0f}',
                       'Spend %': '{:.1f}%'}),
        use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── Page type filter ─────────────────────────────────────────────────────
    page_types = ['All'] + sorted(df_lp_f['Page_Type'].dropna().unique().tolist())
    sel_pt = st.selectbox("Filter individual pages by type", page_types, key='lp_type')
    df_lp2 = df_lp_f if sel_pt == 'All' else df_lp_f[df_lp_f['Page_Type'] == sel_pt]

    lp_tbl = (df_lp2.groupby(['Display_URL', 'Page_Type'])
              .agg(Spend=('Cost', 'sum'), Revenue=('Conv_Value', 'sum'),
                   Clicks=('Clicks', 'sum'), Conversions=('Conversions', 'sum'))
              .reset_index())
    lp_tbl['ROAS'] = (lp_tbl['Revenue'] / lp_tbl['Spend']).round(2).where(
        lp_tbl['Spend'] > 0, 0)
    lp_tbl['Conv_Rate'] = (lp_tbl['Conversions'] / lp_tbl['Clicks'] * 100).round(2).where(
        lp_tbl['Clicks'] > 0, 0)
    lp_tbl['CPA'] = (lp_tbl['Spend'] / lp_tbl['Conversions']).round(0).where(
        lp_tbl['Conversions'] > 0, 0)
    lp_tbl = lp_tbl[lp_tbl['Spend'] > 0].sort_values('Revenue', ascending=False).head(15)

    if has_comp:
        lp_tbl_comp = (df_lp_comp.groupby(['Display_URL', 'Page_Type'])
                       .agg(Revenue_prev=('Conv_Value','sum'), Spend_prev=('Cost','sum'))
                       .reset_index())
        lp_tbl_comp['ROAS_prev'] = (lp_tbl_comp['Revenue_prev']/lp_tbl_comp['Spend_prev']).round(2).where(lp_tbl_comp['Spend_prev']>0, 0)
        lp_tbl = lp_tbl.merge(lp_tbl_comp[['Display_URL','Revenue_prev','Spend_prev','ROAS_prev']], on='Display_URL', how='left').fillna(0)
        lp_tbl['Spend Δ%'] = lp_tbl.apply(lambda r: _dpct(r['Spend'], r['Spend_prev']), axis=1)
        lp_tbl['Rev Δ%'] = lp_tbl.apply(lambda r: _dpct(r['Revenue'], r['Revenue_prev']), axis=1)
        lp_tbl['ROAS Δ%'] = lp_tbl.apply(lambda r: _dpct(r['ROAS'], r['ROAS_prev']), axis=1)

    st.markdown("#### Top 15 Landing Pages by Revenue")
    if has_comp and 'Revenue_prev' in lp_tbl.columns:
        # Sort ascending → Plotly default reversal puts highest Revenue at TOP
        _lp_asc = lp_tbl.sort_values('Revenue', ascending=True)
        _lp_curr = _lp_asc[['Display_URL','Revenue','Spend','ROAS']].copy(); _lp_curr['Period']='Current'
        _lp_prev = _lp_asc[['Display_URL','Revenue_prev','Spend_prev','ROAS_prev']].copy().rename(
            columns={'Revenue_prev':'Revenue','Spend_prev':'Spend','ROAS_prev':'ROAS'})
        _lp_prev['Period'] = _comp_label.title()
        # prev first → bottom bar; curr second → top bar (read first)
        _lp_comb = pd.concat([_lp_prev, _lp_curr], ignore_index=True)
        fig_lp = px.bar(
            _lp_comb, x='Revenue', y='Display_URL', orientation='h',
            color='Period', barmode='group',
            color_discrete_map={'Current': BRAND_ORANGE, _comp_label.title(): '#ADB5BD'},
            title="Top 15 Landing Pages by Revenue",
            labels={'Revenue': 'Revenue (Rs.)', 'Display_URL': ''},
            custom_data=['Spend','ROAS'],
        )
        fig_lp.update_traces(
            hovertemplate="<b>%{y}</b> · %{data.name}<br>Revenue: Rs.%{x:,.0f}<br>Spend: Rs.%{customdata[0]:,.0f}<br>ROAS: %{customdata[1]:.2f}x<extra></extra>"
        )
        fig_lp.update_layout(height=560, plot_bgcolor='white', paper_bgcolor='white',
                              margin=dict(t=50, b=0, l=20, r=80), showlegend=True)
    else:
        fig_lp = px.bar(
            lp_tbl[::-1], x='Revenue', y='Display_URL', orientation='h',
            color='Page_Type', title="Top 15 Landing Pages by Revenue",
            labels={'Revenue': 'Revenue (Rs.)', 'Display_URL': ''},
            text=lp_tbl[::-1]['ROAS'].apply(lambda r: f"{r:.1f}x"),
        )
        fig_lp.update_traces(textposition='outside')
        fig_lp.update_traces(
            hovertemplate="<b>%{y}</b><br>Revenue: Rs.%{x:,.0f}<br>ROAS: %{text}<extra></extra>"
        )
        fig_lp.update_layout(height=520, plot_bgcolor='white', paper_bgcolor='white',
                              margin=dict(t=40, b=0, l=20, r=80))
    st.plotly_chart(fig_lp, use_container_width=True)

    _lp_disp_cols = ['Display_URL', 'Page_Type', 'Spend', 'Clicks', 'Revenue',
                     'Conversions', 'Conv_Rate', 'ROAS', 'CPA']
    _lp_tbl_fmt = {'Spend': 'Rs.{:,.0f}', 'Revenue': 'Rs.{:,.0f}',
                   'ROAS': '{:.2f}x', 'CVR%': '{:.2f}%', 'CPA': 'Rs.{:,.0f}',
                   'Clicks': '{:,.0f}', 'Conversions': '{:,.1f}'}
    if has_comp and 'Rev Δ%' in lp_tbl.columns:
        _lp_disp_cols += ['Spend Δ%', 'Rev Δ%', 'ROAS Δ%']
        _lp_tbl_fmt['Spend Δ%'] = '{:+.1f}%'
        _lp_tbl_fmt['Rev Δ%'] = '{:+.1f}%'
        _lp_tbl_fmt['ROAS Δ%'] = '{:+.1f}%'
    st.dataframe(
        lp_tbl[_lp_disp_cols]
        .rename(columns={'Display_URL': 'URL', 'Page_Type': 'Type', 'Conv_Rate': 'CVR%'})
        .style.format(_lp_tbl_fmt, na_rep='—'),
        use_container_width=True, hide_index=True)

    # ── Insights ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 💡 Landing Page Insights")
    if has_comp:
        st.info(f"📊 Comparison mode: showing changes vs **{_comp_label}** ({comp_start.strftime('%d %b')} – {comp_end.strftime('%d %b %Y')})")
    if len(lp_tbl) > 0:
        _lp_min_sp = max(5000.0, lp_tbl['Spend'].sum() * 0.02)
        _lp_elig = lp_tbl[lp_tbl['Spend'] >= _lp_min_sp]

        li1, li2, li3, li4 = st.columns(4)
        _lp_best_roas = _lp_elig.loc[_lp_elig['ROAS'].idxmax()] if len(_lp_elig) > 0 else lp_tbl.iloc[0]
        _lp_best_cvr  = _lp_elig.loc[_lp_elig['Conv_Rate'].idxmax()] if len(_lp_elig) > 0 else lp_tbl.iloc[0]
        _lp_worst = _lp_elig[_lp_elig['ROAS'] > 0].sort_values('ROAS').iloc[0] if len(_lp_elig[_lp_elig['ROAS'] > 0]) > 0 else None
        _lp_top_rev = lp_tbl.iloc[0]

        _lp_roas_delta_str = ''
        _lp_rev_delta_str = ''
        _lp_worst_delta_str = ''
        if has_comp and 'Rev Δ%' in lp_tbl.columns:
            _lrd = _dpct(_lp_best_roas['ROAS'], _lp_best_roas.get('ROAS_prev', 0))
            if _lrd is not None:
                _lp_roas_delta_str = f' · {_delta_badge(_lrd, "up")}'
            _lrvd = _dpct(_lp_top_rev['Revenue'], _lp_top_rev.get('Revenue_prev', 0))
            if _lrvd is not None:
                _lp_rev_delta_str = f' · {_delta_badge(_lrvd, "up")}'
            if _lp_worst is not None:
                _lwd = _dpct(_lp_worst['ROAS'], _lp_worst.get('ROAS_prev', 0))
                if _lwd is not None:
                    _lp_worst_delta_str = f' · {_delta_badge(_lwd, "up")}'

        with li1:
            st.markdown(f"""<div class="metric-card">
  <div class="metric-label">🏆 Best ROAS Page</div>
  <div class="metric-value" style="font-size:12px">{_lp_best_roas['Display_URL'][-40:]}</div>
  <div class="metric-delta" style="color:#00C9A7">{_lp_best_roas['ROAS']:.1f}x ROAS{_lp_roas_delta_str}</div>
</div>""", unsafe_allow_html=True)
        with li2:
            st.markdown(f"""<div class="metric-card">
  <div class="metric-label">🎯 Best Conv Rate Page</div>
  <div class="metric-value" style="font-size:12px">{_lp_best_cvr['Display_URL'][-40:]}</div>
  <div class="metric-delta" style="color:#00C9A7">{_lp_best_cvr['Conv_Rate']:.2f}% CVR</div>
</div>""", unsafe_allow_html=True)
        with li3:
            st.markdown(f"""<div class="metric-card">
  <div class="metric-label">💰 Highest Revenue Page</div>
  <div class="metric-value" style="font-size:12px">{_lp_top_rev['Display_URL'][-40:]}</div>
  <div class="metric-delta" style="color:#FF6B35">{_fmt_inr(_lp_top_rev['Revenue'])} revenue{_lp_rev_delta_str}</div>
</div>""", unsafe_allow_html=True)
        with li4:
            if _lp_worst is not None:
                st.markdown(f"""<div class="metric-card">
  <div class="metric-label">⚠️ Lowest ROAS Page</div>
  <div class="metric-value" style="font-size:12px">{_lp_worst['Display_URL'][-40:]}</div>
  <div class="metric-delta" style="color:#E63946">{_lp_worst['ROAS']:.1f}x ROAS · {_fmt_inr(_lp_worst['Spend'])} spent{_lp_worst_delta_str}</div>
</div>""", unsafe_allow_html=True)

        if has_comp and 'Rev Δ%' in lp_tbl.columns:
            _lp_with_delta = lp_tbl.dropna(subset=['Rev Δ%'])
            if len(_lp_with_delta) > 0:
                _lp_best_imp = _lp_with_delta.loc[_lp_with_delta['Rev Δ%'].idxmax()]
                _lp_worst_dec = _lp_with_delta.loc[_lp_with_delta['Rev Δ%'].idxmin()]
                st.markdown(f"**Most improved page:** {_lp_best_imp['Display_URL'][-50:]} — revenue {_lp_best_imp['Rev Δ%']:+.1f}%")
                st.markdown(f"**Most declined page:** {_lp_worst_dec['Display_URL'][-50:]} — revenue {_lp_worst_dec['Rev Δ%']:+.1f}%")


# ============================================================
# TAB 6 — Audiences & Demographics
# ============================================================
elif active_tab == "👥 Audiences & Demographics":
    import numpy as np
    st.markdown(f"### Audiences & Demographics — {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}")

    with st.spinner("Loading audience & demographic data…"):
        df_aud  = load_audiences()
        df_demo = load_demographics()

    df_aud_f  = filter_dates(df_aud,  start_date, end_date)
    df_demo_f = filter_dates(df_demo, start_date, end_date)

    # ── Comparison data ──────────────────────────────────────────────────────
    if has_comp:
        df_aud_comp  = filter_dates(load_audiences(), comp_start, comp_end)
        df_demo_comp = filter_dates(load_demographics(), comp_start, comp_end)
        _pr_aud_sp   = df_aud_comp['Cost'].sum()
        _pr_aud_rev  = df_aud_comp['Conv_Value'].sum()
        _pr_aud_conv = df_aud_comp['Conversions'].sum()
        _pr_aud_roas = round(_pr_aud_rev / _pr_aud_sp, 2) if _pr_aud_sp > 0 else 0
    else:
        df_aud_comp = pd.DataFrame(columns=df_aud_f.columns)
        df_demo_comp = pd.DataFrame(columns=df_demo_f.columns)
        _pr_aud_sp = _pr_aud_rev = _pr_aud_conv = _pr_aud_roas = 0

    # ── Overview KPIs ────────────────────────────────────────────────────────
    _aud_spend = df_aud_f['Cost'].sum()
    _aud_rev   = df_aud_f['Conv_Value'].sum()
    _aud_conv  = df_aud_f['Conversions'].sum()
    _aud_roas  = round(_aud_rev / _aud_spend, 2) if _aud_spend > 0 else 0
    _aud_segs  = df_aud_f['Audience'].nunique()

    ak1, ak2, ak3, ak4, ak5 = st.columns(5)
    kpi_card(ak1, "Total Spend",  _aud_spend, inr=True, delta=_dpct(_aud_spend, _pr_aud_sp), delta_good='down')
    kpi_card(ak2, "ROAS",         _aud_roas,  fmt="{:.2f}", suffix="x", delta=_dpct(_aud_roas, _pr_aud_roas), delta_good='up')
    kpi_card(ak3, "Revenue",      _aud_rev,   inr=True, delta=_dpct(_aud_rev, _pr_aud_rev), delta_good='up')
    kpi_card(ak4, "Conversions",  _aud_conv,  fmt="{:,.0f}", delta=_dpct(_aud_conv, _pr_aud_conv), delta_good='up')
    kpi_card(ak5, "Segments",     _aud_segs,  fmt="{:.0f}")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── SECTION A: Funnel + Segments ─────────────────────────────────────────
    st.markdown("#### Audience Segments")
    col_funnel, col_seg = st.columns([1, 2])

    with col_funnel:
        st.markdown("**Funnel Split (TOF / MOF / BOF)**")
        funnel = (df_aud_f.groupby('Funnel')
                  .agg(Spend=('Cost', 'sum'), Revenue=('Conv_Value', 'sum'),
                       Conversions=('Conversions', 'sum'))
                  .reset_index())
        funnel['ROAS'] = (funnel['Revenue'] / funnel['Spend']).round(2).where(funnel['Spend'] > 0, 0)
        funnel = funnel[funnel['Spend'] > 0]
        funnel_order = ['TOF', 'MOF', 'BOF']
        funnel['Funnel'] = pd.Categorical(funnel['Funnel'], categories=funnel_order, ordered=True)
        funnel = funnel.sort_values('Funnel')

        if has_comp and len(df_aud_comp) > 0:
            funnel_comp = (df_aud_comp.groupby('Funnel').agg(Spend=('Cost','sum')).reset_index())
            funnel['Period'] = 'Current'
            funnel_comp['Period'] = _comp_label.title()
            funnel_comb = pd.concat([funnel[['Funnel','Spend','Period']], funnel_comp[['Funnel','Spend','Period']]])
            fig_funnel = px.bar(funnel_comb, x='Funnel', y='Spend', color='Period', barmode='group',
                                 color_discrete_sequence=[BRAND_ORANGE,'#ADB5BD'],
                                 labels={'Spend': 'Spend (Rs.)'}, title="Spend by Funnel Stage")
            fig_funnel.update_traces(hovertemplate="<b>%{x}</b> · %{data.name}<br>Spend: Rs.%{y:,.0f}<extra></extra>")
            fig_funnel.update_layout(showlegend=True, height=320, plot_bgcolor='white', paper_bgcolor='white')
        else:
            fig_funnel = px.bar(funnel, x='Funnel', y='Spend', color='Funnel',
                                 text=funnel['ROAS'].apply(lambda r: f"{r:.1f}x"),
                                 color_discrete_sequence=['#F4A261', '#2A9D8F', '#264653'],
                                 labels={'Spend': 'Spend (Rs.)'}, title="Spend by Funnel Stage")
            fig_funnel.update_traces(textposition='outside')
            fig_funnel.update_traces(hovertemplate="<b>%{x}</b><br>Spend: Rs.%{y:,.0f}<br>ROAS: %{text}<extra></extra>")
            fig_funnel.update_layout(showlegend=False, height=320, plot_bgcolor='white', paper_bgcolor='white')
        st.plotly_chart(fig_funnel, use_container_width=True)

    with col_seg:
        st.markdown("**All Audience Segments — by ROAS (min. Rs.500 spend)**")
        seg = (df_aud_f.groupby('Audience')
               .agg(Spend=('Cost', 'sum'), Revenue=('Conv_Value', 'sum'),
                    Clicks=('Clicks', 'sum'), Conversions=('Conversions', 'sum'))
               .reset_index())
        seg['ROAS']      = (seg['Revenue'] / seg['Spend']).round(2).where(seg['Spend'] > 0, 0)
        seg['CPA']       = (seg['Spend'] / seg['Conversions']).round(0).where(seg['Conversions'] > 0, 0)
        seg['Conv_Rate'] = (seg['Conversions'] / seg['Clicks'] * 100).round(2).where(seg['Clicks'] > 0, 0)
        seg = seg[seg['Spend'] >= 500].sort_values('ROAS', ascending=False).reset_index(drop=True)

        if has_comp and len(df_aud_comp) > 0:
            seg_comp = (df_aud_comp.groupby('Audience')
                        .agg(Revenue_prev=('Conv_Value','sum'), Spend_prev=('Cost','sum'))
                        .reset_index())
            seg_comp['ROAS_prev'] = (seg_comp['Revenue_prev']/seg_comp['Spend_prev']).round(2).where(seg_comp['Spend_prev']>0, 0)
            seg = seg.merge(seg_comp[['Audience','Revenue_prev','Spend_prev','ROAS_prev']], on='Audience', how='left').fillna(0)
            seg['Spend Δ%'] = seg.apply(lambda r: _dpct(r['Spend'], r['Spend_prev']), axis=1)
            seg['Rev Δ%']  = seg.apply(lambda r: _dpct(r['Revenue'], r['Revenue_prev']), axis=1)
            seg['ROAS Δ%'] = seg.apply(lambda r: _dpct(r['ROAS'], r['ROAS_prev']), axis=1)

        _seg_cols = ['Audience', 'Spend', 'Revenue', 'Conversions', 'Conv_Rate', 'ROAS', 'CPA']
        # Note: format keys use POST-rename column names ('CVR%' not 'Conv_Rate')
        _seg_fmt  = {'Spend': 'Rs.{:,.0f}', 'Revenue': 'Rs.{:,.0f}',
                     'ROAS': '{:.2f}x', 'Conversions': '{:,.1f}',
                     'CVR%': '{:.2f}%', 'CPA': 'Rs.{:,.0f}'}
        if has_comp and 'Rev Δ%' in seg.columns:
            _seg_cols += ['Spend Δ%', 'Rev Δ%', 'ROAS Δ%']
            _seg_fmt['Spend Δ%'] = '{:+.1f}%'
            _seg_fmt['Rev Δ%']  = '{:+.1f}%'
            _seg_fmt['ROAS Δ%'] = '{:+.1f}%'
        st.dataframe(
            seg[_seg_cols].rename(columns={'Conv_Rate': 'CVR%'})
            .style.format(_seg_fmt, na_rep='—'),
            use_container_width=True, height=320, hide_index=True)

    # ── SECTION B: Audience Insights ─────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 💡 Audience Insights")
    if has_comp:
        st.info(f"📊 vs **{_comp_label}** ({comp_start.strftime('%d %b')} – {comp_end.strftime('%d %b %Y')})")
    if len(seg) > 0:
        _aud_min_sp = max(5000.0, seg['Spend'].sum() * 0.02)
        _aud_elig   = seg[seg['Spend'] >= _aud_min_sp]
        ai1, ai2, ai3 = st.columns(3)
        _aud_best     = _aud_elig.loc[_aud_elig['ROAS'].idxmax()] if len(_aud_elig) > 0 else seg.iloc[0]
        _aud_top_rev  = seg.iloc[0]
        _aud_worst_c  = _aud_elig[_aud_elig['ROAS'] > 0].sort_values('ROAS')
        _aud_worst    = _aud_worst_c.iloc[0] if len(_aud_worst_c) > 0 else None

        _ard = _dpct(_aud_best['ROAS'], _aud_best.get('ROAS_prev', 0)) if has_comp and 'ROAS Δ%' in seg.columns else None
        _arvd = _dpct(_aud_top_rev['Revenue'], _aud_top_rev.get('Revenue_prev', 0)) if has_comp and 'Rev Δ%' in seg.columns else None
        with ai1:
            st.markdown(f"""<div class="metric-card">
  <div class="metric-label">🏆 Best ROAS Audience</div>
  <div class="metric-value" style="font-size:13px">{str(_aud_best['Audience'])[:45]}</div>
  <div class="metric-delta" style="color:#00C9A7">{_aud_best['ROAS']:.1f}x ROAS{' · ' + _delta_badge(_ard,'up') if _ard is not None else ''}</div>
</div>""", unsafe_allow_html=True)
        with ai2:
            st.markdown(f"""<div class="metric-card">
  <div class="metric-label">💰 Highest Revenue Audience</div>
  <div class="metric-value" style="font-size:13px">{str(_aud_top_rev['Audience'])[:45]}</div>
  <div class="metric-delta" style="color:#FF6B35">{_fmt_inr(_aud_top_rev['Revenue'])} revenue{' · ' + _delta_badge(_arvd,'up') if _arvd is not None else ''}</div>
</div>""", unsafe_allow_html=True)
        with ai3:
            if _aud_worst is not None:
                _awd = _dpct(_aud_worst['ROAS'], _aud_worst.get('ROAS_prev', 0)) if has_comp and 'ROAS Δ%' in seg.columns else None
                st.markdown(f"""<div class="metric-card">
  <div class="metric-label">⚠️ Lowest ROAS Audience</div>
  <div class="metric-value" style="font-size:13px">{str(_aud_worst['Audience'])[:45]}</div>
  <div class="metric-delta" style="color:#E63946">{_aud_worst['ROAS']:.1f}x · {_fmt_inr(_aud_worst['Spend'])} spent{' · ' + _delta_badge(_awd,'up') if _awd is not None else ''}</div>
</div>""", unsafe_allow_html=True)

        if has_comp and 'ROAS Δ%' in seg.columns:
            _aud_with_delta = seg.dropna(subset=['ROAS Δ%'])
            if len(_aud_with_delta) > 0:
                _aud_best_imp  = _aud_with_delta.loc[_aud_with_delta['ROAS Δ%'].idxmax()]
                _aud_worst_dec = _aud_with_delta.loc[_aud_with_delta['ROAS Δ%'].idxmin()]
                st.markdown(f"**Most improved:** {str(_aud_best_imp['Audience'])[:60]} — ROAS {_aud_best_imp['ROAS Δ%']:+.1f}%")
                st.markdown(f"**Most declined:** {str(_aud_worst_dec['Audience'])[:60]} — ROAS {_aud_worst_dec['ROAS Δ%']:+.1f}%")

    # ── SECTION C: Demographics ───────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Demographics")

    # Age × Gender aggregation
    age_gender = (df_demo_f.groupby(['Age', 'Gender'])
                  .agg(Revenue=('Conv_Value', 'sum'), Spend=('Cost', 'sum'),
                       Conversions=('Conversions', 'sum'), Clicks=('Clicks','sum'))
                  .reset_index())
    age_gender['ROAS']     = (age_gender['Revenue'] / age_gender['Spend']).round(2).where(age_gender['Spend'] > 0, 0)
    age_gender['Conv_Rate'] = (age_gender['Conversions'] / age_gender['Clicks'] * 100).round(2).where(age_gender['Clicks'] > 0, 0)
    age_order = ['18 - 24', '25 - 34', '35 - 44', '45 - 54', '55 - 64', '65 or more', 'Undetermined']
    age_gender['Age'] = pd.Categorical(age_gender['Age'], categories=age_order, ordered=True)

    pivot_ag   = age_gender.pivot_table(index='Age', columns='Gender', values='Revenue',     aggfunc='sum').fillna(0)
    pivot_sp   = age_gender.pivot_table(index='Age', columns='Gender', values='Spend',       aggfunc='sum').fillna(0)
    pivot_conv = age_gender.pivot_table(index='Age', columns='Gender', values='Conversions', aggfunc='sum').fillna(0)
    pivot_roas = age_gender.pivot_table(index='Age', columns='Gender', values='ROAS',        aggfunc='mean').fillna(0)
    pivot_cvr  = age_gender.pivot_table(index='Age', columns='Gender', values='Conv_Rate',   aggfunc='mean').fillna(0)

    # Align all pivots to same shape
    _idx = pivot_ag.index; _cols = pivot_ag.columns
    pivot_sp   = pivot_sp.reindex(index=_idx, columns=_cols, fill_value=0)
    pivot_conv = pivot_conv.reindex(index=_idx, columns=_cols, fill_value=0)
    pivot_roas = pivot_roas.reindex(index=_idx, columns=_cols, fill_value=0)
    pivot_cvr  = pivot_cvr.reindex(index=_idx, columns=_cols, fill_value=0)

    _cdata = np.dstack([pivot_sp.values, pivot_conv.values, pivot_roas.values, pivot_cvr.values])

    def _make_rev_heatmap(z_pivot, cdata, title, colorbar_title="Revenue (Rs.)"):
        fig = go.Figure(go.Heatmap(
            z=z_pivot.values,
            x=list(z_pivot.columns),
            y=list(z_pivot.index),
            text=[[f"Rs.{v:,.0f}" for v in row] for row in z_pivot.values],
            texttemplate="%{text}",
            colorscale='RdYlGn',
            customdata=cdata,
            hovertemplate=(
                "<b>Age:</b> %{y} &nbsp;|&nbsp; <b>Gender:</b> %{x}<br>"
                "<b>Revenue:</b> Rs.%{z:,.0f}<br>"
                "<b>Spend:</b> Rs.%{customdata[0]:,.0f}<br>"
                "<b>Conversions:</b> %{customdata[1]:.1f}<br>"
                "<b>ROAS:</b> %{customdata[2]:.2f}x<br>"
                "<b>Conv Rate:</b> %{customdata[3]:.2f}%"
                "<extra></extra>"
            ),
            colorbar=dict(title=colorbar_title),
        ))
        fig.update_layout(title=title, height=300, margin=dict(t=50, b=0),
                          xaxis_title="Gender", yaxis_title="Age",
                          plot_bgcolor='white', paper_bgcolor='white')
        return fig

    def _make_roas_heatmap(z_pivot, title):
        fig = go.Figure(go.Heatmap(
            z=z_pivot.values,
            x=list(z_pivot.columns),
            y=list(z_pivot.index),
            text=[[f"{v:.2f}x" for v in row] for row in z_pivot.values],
            texttemplate="%{text}",
            colorscale='RdYlGn',
            hovertemplate=(
                "<b>Age:</b> %{y} &nbsp;|&nbsp; <b>Gender:</b> %{x}<br>"
                "<b>ROAS:</b> %{z:.2f}x"
                "<extra></extra>"
            ),
            colorbar=dict(title="ROAS"),
        ))
        fig.update_layout(title=title, height=300, margin=dict(t=50, b=0),
                          xaxis_title="Gender", yaxis_title="Age",
                          plot_bgcolor='white', paper_bgcolor='white')
        return fig

    # Row: Current Spend heatmap | ROAS heatmap
    st.markdown("#### Age × Gender — Spend & ROAS")
    _hm_col1, _hm_col2 = st.columns(2)
    with _hm_col1:
        # Build customdata for Spend heatmap: Revenue, Conversions, ROAS, CVR
        _cdata_sp = np.dstack([pivot_ag.values, pivot_conv.values, pivot_roas.values, pivot_cvr.values])
        _fig_sp = go.Figure(go.Heatmap(
            z=pivot_sp.values,
            x=list(pivot_sp.columns),
            y=list(pivot_sp.index),
            text=[[f"Rs.{v:,.0f}" for v in row] for row in pivot_sp.values],
            texttemplate="%{text}",
            colorscale='RdYlGn',
            customdata=_cdata_sp,
            hovertemplate=(
                "<b>Age:</b> %{y} &nbsp;|&nbsp; <b>Gender:</b> %{x}<br>"
                "<b>Spend:</b> Rs.%{z:,.0f}<br>"
                "<b>Revenue:</b> Rs.%{customdata[0]:,.0f}<br>"
                "<b>Conversions:</b> %{customdata[1]:.1f}<br>"
                "<b>ROAS:</b> %{customdata[2]:.2f}x<br>"
                "<b>Conv Rate:</b> %{customdata[3]:.2f}%"
                "<extra></extra>"
            ),
            colorbar=dict(title="Spend (Rs.)"),
        ))
        _fig_sp.update_layout(title="Spend by Age & Gender (current period)", height=300,
                               margin=dict(t=50, b=0), xaxis_title="Gender", yaxis_title="Age",
                               plot_bgcolor='white', paper_bgcolor='white')
        st.plotly_chart(_fig_sp, use_container_width=True)
    with _hm_col2:
        st.plotly_chart(_make_roas_heatmap(pivot_roas, "ROAS by Age & Gender (green = best)"),
                        use_container_width=True)

    # Comparison rows (only when has_comp)
    if has_comp and len(df_demo_comp) > 0:
        age_gender_prev = (df_demo_comp.groupby(['Age', 'Gender'])
                           .agg(Revenue=('Conv_Value', 'sum'), Spend=('Cost', 'sum'),
                                Conversions=('Conversions', 'sum'), Clicks=('Clicks','sum'))
                           .reset_index())
        age_gender_prev['ROAS']      = (age_gender_prev['Revenue'] / age_gender_prev['Spend']).round(2).where(age_gender_prev['Spend'] > 0, 0)
        age_gender_prev['Conv_Rate'] = (age_gender_prev['Conversions'] / age_gender_prev['Clicks'] * 100).round(2).where(age_gender_prev['Clicks'] > 0, 0)
        age_gender_prev['Age'] = pd.Categorical(age_gender_prev['Age'], categories=age_order, ordered=True)

        pivot_ag_prev   = age_gender_prev.pivot_table(index='Age', columns='Gender', values='Revenue',     aggfunc='sum').fillna(0)
        pivot_sp_prev   = age_gender_prev.pivot_table(index='Age', columns='Gender', values='Spend',       aggfunc='sum').fillna(0)
        pivot_conv_prev = age_gender_prev.pivot_table(index='Age', columns='Gender', values='Conversions', aggfunc='sum').fillna(0)
        pivot_roas_prev = age_gender_prev.pivot_table(index='Age', columns='Gender', values='ROAS',        aggfunc='mean').fillna(0)
        pivot_cvr_prev  = age_gender_prev.pivot_table(index='Age', columns='Gender', values='Conv_Rate',   aggfunc='mean').fillna(0)

        # Align to current period shape
        pivot_ag_prev   = pivot_ag_prev.reindex(index=_idx, columns=_cols, fill_value=0)
        pivot_sp_prev   = pivot_sp_prev.reindex(index=_idx, columns=_cols, fill_value=0)
        pivot_conv_prev = pivot_conv_prev.reindex(index=_idx, columns=_cols, fill_value=0)
        pivot_roas_prev = pivot_roas_prev.reindex(index=_idx, columns=_cols, fill_value=0)
        pivot_cvr_prev  = pivot_cvr_prev.reindex(index=_idx, columns=_cols, fill_value=0)

        _cdata_prev = np.dstack([pivot_sp_prev.values, pivot_conv_prev.values, pivot_roas_prev.values, pivot_cvr_prev.values])
        pivot_delta = ((pivot_ag - pivot_ag_prev) / pivot_ag_prev.replace(0, float('nan')) * 100).round(1)

        _hm_col3, _hm_col4 = st.columns(2)
        with _hm_col3:
            _cdata_sp_prev = np.dstack([pivot_ag_prev.values, pivot_conv_prev.values, pivot_roas_prev.values, pivot_cvr_prev.values])
            _fig_sp_prev = go.Figure(go.Heatmap(
                z=pivot_sp_prev.values,
                x=list(pivot_sp_prev.columns),
                y=list(pivot_sp_prev.index),
                text=[[f"Rs.{v:,.0f}" for v in row] for row in pivot_sp_prev.values],
                texttemplate="%{text}",
                colorscale='RdYlGn',
                customdata=_cdata_sp_prev,
                hovertemplate=(
                    "<b>Age:</b> %{y} &nbsp;|&nbsp; <b>Gender:</b> %{x}<br>"
                    "<b>Spend:</b> Rs.%{z:,.0f}<br>"
                    "<b>Revenue:</b> Rs.%{customdata[0]:,.0f}<br>"
                    "<b>Conversions:</b> %{customdata[1]:.1f}<br>"
                    "<b>ROAS:</b> %{customdata[2]:.2f}x"
                    "<extra></extra>"
                ),
                colorbar=dict(title="Spend (Rs.)"),
            ))
            _fig_sp_prev.update_layout(
                title=f"Spend by Age & Gender ({_comp_label.title()})",
                height=300, margin=dict(t=50, b=0),
                xaxis_title="Gender", yaxis_title="Age",
                plot_bgcolor='white', paper_bgcolor='white')
            st.plotly_chart(_fig_sp_prev, use_container_width=True)
        with _hm_col4:
            st.plotly_chart(
                _make_roas_heatmap(pivot_roas_prev, f"ROAS by Age & Gender ({_comp_label.title()})"),
                use_container_width=True)

        # ── Row 3: Delta heatmaps (Spend Δ% and ROAS Δ%) ────────────────────
        st.markdown(f"**Period vs {_comp_label.title()} — Change Heatmaps** (🟢 green = improved, 🔴 red = declined)")
        _hm_col5, _hm_col6 = st.columns(2)

        # Compute delta pivots (% change vs previous period)
        _pivot_sp_delta   = ((pivot_sp - pivot_sp_prev) / pivot_sp_prev.replace(0, float('nan')) * 100).round(1)
        _pivot_roas_delta = ((pivot_roas - pivot_roas_prev) / pivot_roas_prev.replace(0, float('nan')) * 100).round(1)

        def _delta_label(v):
            if pd.isna(v): return "N/A"
            return f"{v:+.0f}%"

        with _hm_col5:
            _sp_delta_text = [[_delta_label(v) for v in row] for row in _pivot_sp_delta.values]
            _fig_sp_delta = go.Figure(go.Heatmap(
                z=_pivot_sp_delta.values,
                x=list(_pivot_sp_delta.columns),
                y=list(_pivot_sp_delta.index),
                text=_sp_delta_text,
                texttemplate="%{text}",
                colorscale='RdYlGn',
                zmid=0,
                hovertemplate=(
                    "<b>Age:</b> %{y} &nbsp;|&nbsp; <b>Gender:</b> %{x}<br>"
                    "<b>Spend Δ:</b> %{z:+.1f}%"
                    "<extra></extra>"
                ),
                colorbar=dict(title="Spend Δ%"),
            ))
            _fig_sp_delta.update_layout(
                title=f"Spend Δ% vs {_comp_label.title()} (green = spend grew)",
                height=300, margin=dict(t=50, b=0),
                xaxis_title="Gender", yaxis_title="Age",
                plot_bgcolor='white', paper_bgcolor='white')
            st.plotly_chart(_fig_sp_delta, use_container_width=True)

        with _hm_col6:
            _roas_delta_text = [[_delta_label(v) for v in row] for row in _pivot_roas_delta.values]
            _fig_roas_delta = go.Figure(go.Heatmap(
                z=_pivot_roas_delta.values,
                x=list(_pivot_roas_delta.columns),
                y=list(_pivot_roas_delta.index),
                text=_roas_delta_text,
                texttemplate="%{text}",
                colorscale='RdYlGn',
                zmid=0,
                hovertemplate=(
                    "<b>Age:</b> %{y} &nbsp;|&nbsp; <b>Gender:</b> %{x}<br>"
                    "<b>ROAS Δ:</b> %{z:+.1f}%"
                    "<extra></extra>"
                ),
                colorbar=dict(title="ROAS Δ%"),
            ))
            _fig_roas_delta.update_layout(
                title=f"ROAS Δ% vs {_comp_label.title()} (green = efficiency improved)",
                height=300, margin=dict(t=50, b=0),
                xaxis_title="Gender", yaxis_title="Age",
                plot_bgcolor='white', paper_bgcolor='white')
            st.plotly_chart(_fig_roas_delta, use_container_width=True)

    # ── SECTION D: Demographics Detail Table ──────────────────────────────────
    st.markdown("---")
    st.markdown("#### Demographics Detail")
    dem_tbl = (df_demo_f.groupby(['Age', 'Gender', 'Parental_Status'])
               .agg(Spend=('Cost', 'sum'), Revenue=('Conv_Value', 'sum'),
                    Clicks=('Clicks', 'sum'), Conversions=('Conversions', 'sum'))
               .reset_index())
    dem_tbl['ROAS']      = (dem_tbl['Revenue'] / dem_tbl['Spend']).round(2).where(dem_tbl['Spend'] > 0, 0)
    dem_tbl['Conv_Rate'] = (dem_tbl['Conversions'] / dem_tbl['Clicks'] * 100).round(2).where(dem_tbl['Clicks'] > 0, 0)
    dem_tbl = dem_tbl[dem_tbl['Spend'] > 100].sort_values('Revenue', ascending=False).reset_index(drop=True)
    st.dataframe(
        dem_tbl[['Age', 'Gender', 'Parental_Status', 'Spend', 'Revenue', 'Conversions', 'Conv_Rate', 'ROAS']]
        .rename(columns={'Parental_Status': 'Parent Status', 'Conv_Rate': 'CVR%'})
        .style.format({'Spend': 'Rs.{:,.0f}', 'Revenue': 'Rs.{:,.0f}',
                       'ROAS': '{:.2f}x', 'Conversions': '{:,.1f}', 'CVR%': '{:.2f}%'}),
        use_container_width=True, height=400, hide_index=True)

    # ── SECTION E: Parental Status ─────────────────────────────────────────────
    st.markdown("#### Parental Status — Spend & ROAS")
    parent = (df_demo_f.groupby('Parental_Status')
              .agg(Spend=('Cost', 'sum'), Revenue=('Conv_Value', 'sum'),
                   Conversions=('Conversions', 'sum'))
              .reset_index())
    parent['ROAS'] = (parent['Revenue'] / parent['Spend']).round(2).where(parent['Spend'] > 0, 0)

    if has_comp and len(df_demo_comp) > 0:
        parent_comp = (df_demo_comp.groupby('Parental_Status')
                       .agg(Spend_prev=('Cost','sum'), Revenue_prev=('Conv_Value','sum'))
                       .reset_index())
        parent_comp['ROAS_prev'] = (parent_comp['Revenue_prev'] / parent_comp['Spend_prev']).round(2).where(parent_comp['Spend_prev'] > 0, 0)
        parent = parent.merge(parent_comp, on='Parental_Status', how='left').fillna(0)

    _par_col1, _par_col2 = st.columns(2)
    with _par_col1:
        if has_comp and 'Spend_prev' in parent.columns and parent['Spend_prev'].sum() > 0:
            _psp_curr = parent[['Parental_Status','Spend']].copy(); _psp_curr['Period'] = 'Current'
            _psp_prev = parent[['Parental_Status','Spend_prev']].copy().rename(columns={'Spend_prev':'Spend'}); _psp_prev['Period'] = _comp_label.title()
            _psp_comb = pd.concat([_psp_curr, _psp_prev])
            fig_par_sp = px.bar(_psp_comb, x='Parental_Status', y='Spend', color='Period', barmode='group',
                                 color_discrete_sequence=[BRAND_ORANGE,'#ADB5BD'],
                                 labels={'Spend':'Spend (Rs.)','Parental_Status':''},
                                 title="Spend by Parental Status")
            fig_par_sp.update_traces(hovertemplate="<b>%{x}</b> · %{data.name}<br>Spend: Rs.%{y:,.0f}<extra></extra>")
            fig_par_sp.update_layout(showlegend=True, height=320, plot_bgcolor='white', paper_bgcolor='white')
        else:
            fig_par_sp = px.bar(parent, x='Parental_Status', y='Spend',
                                 color='Parental_Status',
                                 text=parent['Spend'].apply(lambda v: _fmt_inr(v)),
                                 labels={'Spend':'Spend (Rs.)','Parental_Status':''},
                                 title="Spend by Parental Status",
                                 color_discrete_sequence=['#F4A261','#2A9D8F','#264653','#E9C46A'])
            fig_par_sp.update_traces(textposition='outside')
            fig_par_sp.update_traces(
                hovertemplate="<b>%{x}</b><br>Spend: Rs.%{y:,.0f}<br>Revenue: Rs.%{customdata[0]:,.0f}<extra></extra>",
                customdata=parent[['Revenue']].values
            )
            fig_par_sp.update_layout(showlegend=False, height=320, plot_bgcolor='white', paper_bgcolor='white')
        st.plotly_chart(fig_par_sp, use_container_width=True)

    with _par_col2:
        if has_comp and 'ROAS_prev' in parent.columns and parent['ROAS_prev'].sum() > 0:
            _prs_curr = parent[['Parental_Status','ROAS']].copy(); _prs_curr['Period'] = 'Current'
            _prs_prev = parent[['Parental_Status','ROAS_prev']].copy().rename(columns={'ROAS_prev':'ROAS'}); _prs_prev['Period'] = _comp_label.title()
            _prs_comb = pd.concat([_prs_curr, _prs_prev])
            fig_par = px.bar(_prs_comb, x='Parental_Status', y='ROAS', color='Period', barmode='group',
                              color_discrete_sequence=[BRAND_ORANGE,'#ADB5BD'],
                              labels={'ROAS':'ROAS','Parental_Status':''},
                              title="ROAS by Parental Status")
            fig_par.add_hline(y=roas_target, line_dash="dash", line_color=BRAND_RED,
                               annotation_text=f"Target {roas_target}x", annotation_position="top right")
            fig_par.update_traces(hovertemplate="<b>%{x}</b> · %{data.name}<br>ROAS: %{y:.2f}x<extra></extra>")
            fig_par.update_layout(showlegend=True, height=320, plot_bgcolor='white', paper_bgcolor='white')
        else:
            fig_par = px.bar(parent, x='Parental_Status', y='ROAS',
                              color='Parental_Status',
                              text=parent['ROAS'].apply(lambda r: f"{r:.2f}x"),
                              labels={'ROAS':'ROAS','Parental_Status':''},
                              title="ROAS by Parental Status",
                              color_discrete_sequence=['#F4A261','#2A9D8F','#264653','#E9C46A'])
            fig_par.update_traces(textposition='outside')
            fig_par.add_hline(y=roas_target, line_dash="dash", line_color=BRAND_RED,
                               annotation_text=f"Target {roas_target}x", annotation_position="top right")
            fig_par.update_traces(
                hovertemplate="<b>%{x}</b><br>ROAS: %{y:.2f}x<br>Spend: Rs.%{customdata[0]:,.0f}<extra></extra>",
                customdata=parent[['Spend']].values
            )
            fig_par.update_layout(showlegend=False, height=320, plot_bgcolor='white', paper_bgcolor='white')
        st.plotly_chart(fig_par, use_container_width=True)

    # ── SECTION F: Demographics Insights ──────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 💡 Demographics Insights")
    if len(dem_tbl) > 0:
        _age_agg = (dem_tbl.groupby('Age')
                    .agg(Revenue=('Revenue','sum'), Spend=('Spend','sum'), Conversions=('Conversions','sum'))
                    .reset_index())
        _age_agg['ROAS'] = (_age_agg['Revenue'] / _age_agg['Spend']).round(2).where(_age_agg['Spend'] > 0, 0)
        _best_age = _age_agg.loc[_age_agg['Revenue'].idxmax()] if len(_age_agg) > 0 else None

        _gen_agg = (dem_tbl.groupby('Gender')
                    .agg(Revenue=('Revenue','sum'), Spend=('Spend','sum'), Conversions=('Conversions','sum'))
                    .reset_index())
        _gen_agg['ROAS'] = (_gen_agg['Revenue'] / _gen_agg['Spend']).round(2).where(_gen_agg['Spend'] > 0, 0)
        _best_gen = _gen_agg.loc[_gen_agg['Revenue'].idxmax()] if len(_gen_agg) > 0 else None

        _dem_min_sp  = max(500.0, dem_tbl['Spend'].sum() * 0.01)
        _dem_elig    = dem_tbl[dem_tbl['Spend'] >= _dem_min_sp]
        _best_seg    = _dem_elig.loc[_dem_elig['ROAS'].idxmax()] if len(_dem_elig) > 0 else dem_tbl.iloc[0]
        _best_cvr_   = _dem_elig[_dem_elig['Conv_Rate'] > 0]
        _best_cvr_seg = _best_cvr_.loc[_best_cvr_['Conv_Rate'].idxmax()] if len(_best_cvr_) > 0 else None

        # Build comparison aggregates for delta badges
        _dem_age_delta = {}; _dem_gen_delta = {}; _dem_seg_roas_delta = None
        if has_comp and len(df_demo_comp) > 0:
            _dem_tbl_comp = (df_demo_comp.groupby(['Age','Gender','Parental_Status'])
                             .agg(Spend=('Cost','sum'), Revenue=('Conv_Value','sum'))
                             .reset_index())
            _dem_tbl_comp['ROAS'] = (_dem_tbl_comp['Revenue']/_dem_tbl_comp['Spend']).round(2).where(_dem_tbl_comp['Spend']>0, 0)
            _age_agg_comp = _dem_tbl_comp.groupby('Age').agg(Revenue=('Revenue','sum'), Spend=('Spend','sum')).reset_index()
            _age_agg_comp['ROAS'] = (_age_agg_comp['Revenue']/_age_agg_comp['Spend']).round(2).where(_age_agg_comp['Spend']>0, 0)
            _gen_agg_comp = _dem_tbl_comp.groupby('Gender').agg(Revenue=('Revenue','sum'), Spend=('Spend','sum')).reset_index()
            _gen_agg_comp['ROAS'] = (_gen_agg_comp['Revenue']/_gen_agg_comp['Spend']).round(2).where(_gen_agg_comp['Spend']>0, 0)
            if _best_age is not None:
                _prev_age_rev = _age_agg_comp[_age_agg_comp['Age']==_best_age['Age']]['Revenue'].sum()
                _dem_age_delta = _dpct(_best_age['Revenue'], _prev_age_rev)
            if _best_gen is not None:
                _prev_gen_rev = _gen_agg_comp[_gen_agg_comp['Gender']==_best_gen['Gender']]['Revenue'].sum()
                _dem_gen_delta = _dpct(_best_gen['Revenue'], _prev_gen_rev)
            _best_seg_comp = _dem_tbl_comp[(_dem_tbl_comp['Age']==_best_seg['Age']) & (_dem_tbl_comp['Gender']==_best_seg['Gender'])]['ROAS'].mean()
            _dem_seg_roas_delta = _dpct(_best_seg['ROAS'], _best_seg_comp) if _best_seg_comp > 0 else None

        # Extra aggregates for insights
        _total_dem_rev = dem_tbl['Revenue'].sum()
        _total_dem_sp  = dem_tbl['Spend'].sum()
        _age_split_rev = _age_agg.set_index('Age')['Revenue'].sort_values(ascending=False)
        _gen_split_rev = _gen_agg.set_index('Gender')['Revenue']
        _male_pct    = (_gen_split_rev.get('Male', 0)    / _total_dem_rev * 100) if _total_dem_rev > 0 else 0
        _female_pct  = (_gen_split_rev.get('Female', 0)  / _total_dem_rev * 100) if _total_dem_rev > 0 else 0
        _top2_ages   = _age_split_rev.head(2)
        _top2_age_pct = (_top2_ages.sum() / _total_dem_rev * 100) if _total_dem_rev > 0 else 0
        _highest_sp_seg = _dem_elig.loc[_dem_elig['Spend'].idxmax()] if len(_dem_elig) > 0 else dem_tbl.iloc[0]

        di1, di2, di3, di4 = st.columns(4)
        with di1:
            if _best_age is not None:
                _age_rev_pct = _best_age['Revenue'] / _total_dem_rev * 100 if _total_dem_rev > 0 else 0
                _age_delta_str = f' · {_delta_badge(_dem_age_delta, "up")}' if _dem_age_delta is not None and _dem_age_delta != {} else ''
                _age2_str = f' + {_top2_ages.index[1]} = {_top2_age_pct:.0f}% combined' if len(_top2_ages) > 1 else ''
                st.markdown(f"""<div class="metric-card">
  <div class="metric-label">📊 Top Age Group</div>
  <div class="metric-value">{_best_age['Age']}</div>
  <div class="metric-delta" style="color:#00C9A7">{_fmt_inr(_best_age['Revenue'])} · {_age_rev_pct:.0f}% of revenue{_age_delta_str}</div>
  <div class="metric-delta" style="color:#6c757d;font-size:11px">{_age2_str}</div>
</div>""", unsafe_allow_html=True)
        with di2:
            if _best_gen is not None:
                _gen_rev_pct = _best_gen['Revenue'] / _total_dem_rev * 100 if _total_dem_rev > 0 else 0
                _gen_delta_str = f' · {_delta_badge(_dem_gen_delta, "up")}' if _dem_gen_delta is not None and _dem_gen_delta != {} else ''
                _split_str = f"M {_male_pct:.0f}% · F {_female_pct:.0f}%"
                st.markdown(f"""<div class="metric-card">
  <div class="metric-label">👤 Top Gender</div>
  <div class="metric-value">{_best_gen['Gender']}</div>
  <div class="metric-delta" style="color:#00C9A7">{_fmt_inr(_best_gen['Revenue'])} · {_gen_rev_pct:.0f}% · ROAS {_best_gen['ROAS']:.2f}x{_gen_delta_str}</div>
  <div class="metric-delta" style="color:#6c757d;font-size:11px">Split: {_split_str}</div>
</div>""", unsafe_allow_html=True)
        with di3:
            _seg_delta_str = f' · {_delta_badge(_dem_seg_roas_delta, "up")}' if _dem_seg_roas_delta is not None else ''
            _seg_sp_pct = (_best_seg['Spend'] / _total_dem_sp * 100) if _total_dem_sp > 0 else 0
            st.markdown(f"""<div class="metric-card">
  <div class="metric-label">🏆 Best ROAS Segment</div>
  <div class="metric-value" style="font-size:13px">{_best_seg['Age']} · {_best_seg['Gender']}</div>
  <div class="metric-delta" style="color:#00C9A7">{_best_seg['ROAS']:.2f}x ROAS{_seg_delta_str}</div>
  <div class="metric-delta" style="color:#6c757d;font-size:11px">{_fmt_inr(_best_seg['Revenue'])} rev · {_seg_sp_pct:.0f}% of spend</div>
</div>""", unsafe_allow_html=True)
        with di4:
            if _best_cvr_seg is not None:
                _cvr_sp_pct = (_best_cvr_seg['Spend'] / _total_dem_sp * 100) if _total_dem_sp > 0 else 0
                st.markdown(f"""<div class="metric-card">
  <div class="metric-label">🎯 Best CVR Segment</div>
  <div class="metric-value" style="font-size:13px">{_best_cvr_seg['Age']} · {_best_cvr_seg['Gender']}</div>
  <div class="metric-delta" style="color:#4361EE">{_best_cvr_seg['Conv_Rate']:.2f}% CVR</div>
  <div class="metric-delta" style="color:#6c757d;font-size:11px">{_fmt_inr(_best_cvr_seg['Spend'])} spend · {_cvr_sp_pct:.0f}% of total</div>
</div>""", unsafe_allow_html=True)

        # Row 2: Highest spend segment + comparison change insight
        di5, di6, di7, di8 = st.columns(4)
        with di5:
            _hs_roas = _highest_sp_seg.get('ROAS', 0)
            _hs_color = BRAND_TEAL if _hs_roas >= roas_target else BRAND_RED
            st.markdown(f"""<div class="metric-card">
  <div class="metric-label">💰 Highest Spend Segment</div>
  <div class="metric-value" style="font-size:13px">{_highest_sp_seg['Age']} · {_highest_sp_seg['Gender']}</div>
  <div class="metric-delta" style="color:{_hs_color}">{_fmt_inr(_highest_sp_seg['Spend'])} · ROAS {_hs_roas:.2f}x</div>
</div>""", unsafe_allow_html=True)
        with di6:
            # Parental status with highest ROAS
            _par_agg2b = (dem_tbl.groupby('Parental_Status')
                          .agg(Revenue=('Revenue','sum'), Spend=('Spend','sum'))
                          .reset_index())
            _par_agg2b['ROAS'] = (_par_agg2b['Revenue']/_par_agg2b['Spend']).round(2).where(_par_agg2b['Spend']>0, 0)
            if len(_par_agg2b) > 0:
                _best_par = _par_agg2b.loc[_par_agg2b['ROAS'].idxmax()]
                _par_roas_color = BRAND_TEAL if _best_par['ROAS'] >= roas_target else BRAND_RED
                st.markdown(f"""<div class="metric-card">
  <div class="metric-label">👶 Best Parental Status</div>
  <div class="metric-value" style="font-size:13px">{_best_par['Parental_Status']}</div>
  <div class="metric-delta" style="color:{_par_roas_color}">{_best_par['ROAS']:.2f}x ROAS · {_fmt_inr(_best_par['Revenue'])}</div>
</div>""", unsafe_allow_html=True)
        with di7:
            # Worst performing segment (most spend, lowest ROAS)
            _worst_elig = _dem_elig[_dem_elig['ROAS'] > 0].sort_values('ROAS').head(1)
            if len(_worst_elig) > 0:
                _ws = _worst_elig.iloc[0]
                st.markdown(f"""<div class="metric-card">
  <div class="metric-label">⚠️ Lowest ROAS Segment</div>
  <div class="metric-value" style="font-size:13px">{_ws['Age']} · {_ws['Gender']}</div>
  <div class="metric-delta" style="color:{BRAND_RED}">{_ws['ROAS']:.2f}x ROAS · {_fmt_inr(_ws['Spend'])} spend</div>
</div>""", unsafe_allow_html=True)
        with di8:
            # Revenue concentration: top segment share
            _top_seg_rev_pct = (_best_seg['Revenue'] / _total_dem_rev * 100) if _total_dem_rev > 0 else 0
            _efficiency = (_best_seg['Revenue'] / _best_seg['Spend']) if _best_seg['Spend'] > 0 else 0
            st.markdown(f"""<div class="metric-card">
  <div class="metric-label">📈 Best Combo Efficiency</div>
  <div class="metric-value" style="font-size:13px">{_best_seg['Age']} × {_best_seg['Gender']}</div>
  <div class="metric-delta" style="color:{BRAND_TEAL}">{_fmt_inr(_best_seg['Revenue'])} rev · {_top_seg_rev_pct:.0f}% of total</div>
  <div class="metric-delta" style="color:#6c757d;font-size:11px">Rs.{_efficiency:.0f} rev per rupee spent</div>
</div>""", unsafe_allow_html=True)

        # Narrative summary
        _top_age_name = _top2_ages.index[0] if len(_top2_ages) > 0 else '—'
        _top_age2_name = _top2_ages.index[1] if len(_top2_ages) > 1 else '—'
        _narrative_comp = ''
        if has_comp and _dem_age_delta is not None and _dem_age_delta != {}:
            _dir = 'grew' if (_dem_age_delta or 0) >= 0 else 'declined'
            _narrative_comp = f" Top age group revenue **{_dir} {abs(_dem_age_delta or 0):.1f}%** vs {_comp_label}."
        st.markdown(f"""
> **Key findings:** **{_best_gen['Gender'] if _best_gen is not None else '—'}** drives **{_male_pct if (_best_gen is not None and _best_gen['Gender']=='Male') else _female_pct:.0f}%** of revenue.
> Age groups **{_top_age_name}** + **{_top_age2_name}** together = **{_top2_age_pct:.0f}%** of revenue.
> Best ROAS combo: **{_best_seg['Age']} × {_best_seg['Gender']}** at **{_best_seg['ROAS']:.2f}x**.{_narrative_comp}
""", unsafe_allow_html=False)


# ============================================================
# TAB 7 — Geography
# ============================================================
elif active_tab == "🗺️ Geography":
    st.markdown(f"### Geography — {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}")

    with st.spinner("Loading geography data…"):
        df_geo = load_geography()

    df_geo_f = filter_dates(df_geo, start_date, end_date)

    # ── Estimate AOV from campaign data (same date window) ───────────────────
    # Google Ads doesn't export Conv. Value at city/state level, so we
    # estimate revenue = Conversions × blended_AOV from the campaign report.
    _geo_total_rev  = df_camp_f['Conv_Value'].sum()
    _geo_total_conv = df_camp_f['Conversions'].sum()
    _est_aov = round(_geo_total_rev / _geo_total_conv, 2) if _geo_total_conv > 0 else 0

    # ── Overview KPIs ────────────────────────────────────────────────────────
    _geo_spend = df_geo_f['Cost'].sum()
    _geo_conv  = df_geo_f['Conversions'].sum()
    _geo_clicks= df_geo_f['Clicks'].sum()
    _geo_cpa   = round(_geo_spend / _geo_conv, 0) if _geo_conv > 0 else 0
    _geo_est_rev  = _geo_conv * _est_aov
    _geo_est_roas = round(_geo_est_rev / _geo_spend, 2) if _geo_spend > 0 else 0
    _geo_cities= df_geo_f['City'].nunique()
    _geo_states= df_geo_f['State'].nunique()

    if has_comp:
        df_geo_comp = filter_dates(load_geography(), comp_start, comp_end)
        _pr_geo_sp   = df_geo_comp['Cost'].sum()
        _pr_geo_conv = df_geo_comp['Conversions'].sum()
        _pr_geo_cpa  = round(_pr_geo_sp / _pr_geo_conv, 0) if _pr_geo_conv > 0 else 0
        _pr_geo_est_rev  = _pr_geo_conv * _est_aov
        _pr_geo_est_roas = round(_pr_geo_est_rev / _pr_geo_sp, 2) if _pr_geo_sp > 0 else 0
    else:
        _pr_geo_sp = _pr_geo_conv = _pr_geo_cpa = _pr_geo_est_roas = 0

    gk1, gk2, gk3, gk4, gk5, gk6 = st.columns(6)
    kpi_card(gk1, "Total Spend",    _geo_spend,     inr=True, delta=_dpct(_geo_spend, _pr_geo_sp), delta_good='down')
    kpi_card(gk2, "Conversions",    _geo_conv,      fmt="{:,.0f}", delta=_dpct(_geo_conv, _pr_geo_conv), delta_good='up')
    kpi_card(gk3, "Blended CPA",    _geo_cpa,       inr=True, delta=_dpct(_geo_cpa, _pr_geo_cpa), delta_good='down')
    kpi_card(gk4, "Est. ROAS",      _geo_est_roas,  fmt="{:.2f}", suffix="x", delta=_dpct(_geo_est_roas, _pr_geo_est_roas), delta_good='up')
    kpi_card(gk5, "Cities",         _geo_cities,    fmt="{:.0f}")
    kpi_card(gk6, "States",         _geo_states,    fmt="{:.0f}")
    st.caption(f"⚠️ Est. ROAS is calculated using blended AOV of Rs.{_est_aov:,.0f} (total campaign revenue ÷ conversions). Google Ads doesn't export conversion value at city/state level.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── States — full width (shown first) ───────────────────────────────────
    st.markdown("#### Top 15 States by Spend")
    state_tbl = (df_geo_f.groupby('State')
                 .agg(Spend=('Cost', 'sum'), Clicks=('Clicks', 'sum'),
                      Conversions=('Conversions', 'sum'))
                 .reset_index())
    state_tbl['CPA']       = (state_tbl['Spend'] / state_tbl['Conversions']).round(0).where(
        state_tbl['Conversions'] > 0, 0)
    state_tbl['Conv_Rate'] = (state_tbl['Conversions'] / state_tbl['Clicks'] * 100).round(2).where(
        state_tbl['Clicks'] > 0, 0)
    state_tbl['Est_Revenue'] = (state_tbl['Conversions'] * _est_aov).round(0)
    state_tbl['Est_ROAS']  = (state_tbl['Est_Revenue'] / state_tbl['Spend']).round(2).where(
        state_tbl['Spend'] > 0, 0)
    state_tbl = state_tbl[state_tbl['Spend'] > 0].sort_values('Spend', ascending=False).head(15)
    _state_order_desc = state_tbl['State'].tolist()  # descending: highest first → appears at TOP

    if has_comp and len(df_geo_comp) > 0:
        state_tbl_comp = (df_geo_comp.groupby('State')
                          .agg(Spend_prev=('Cost','sum'), Conversions_prev=('Conversions','sum'))
                          .reset_index())
        state_tbl = state_tbl.merge(state_tbl_comp, on='State', how='left').fillna(0)
        state_tbl['Spend Δ%'] = state_tbl.apply(lambda r: _dpct(r['Spend'], r['Spend_prev']), axis=1)
        state_tbl['Conv Δ%'] = state_tbl.apply(lambda r: _dpct(r['Conversions'], r['Conversions_prev']), axis=1)

    if has_comp and 'Spend_prev' in state_tbl.columns:
        # Sort ascending so Plotly reverses to highest-at-top (same proven pattern as single-period charts)
        _st_sorted_asc = state_tbl.sort_values('Spend', ascending=True)
        _st_curr = _st_sorted_asc[['State','Spend','Conversions','Est_ROAS','CPA','Conv_Rate']].copy()
        _st_curr['Period'] = 'Current'
        _st_curr.rename(columns={'Conversions':'Conv_val','Est_ROAS':'ROAS_val','CPA':'CPA_val','Conv_Rate':'CVR_val'}, inplace=True)
        _st_prev_df = _st_sorted_asc[['State','Spend_prev','Conversions_prev']].copy()
        _st_prev_df.columns = ['State','Spend','Conv_val']
        _st_prev_df['ROAS_val'] = (_st_prev_df['Conv_val'] * _est_aov / _st_prev_df['Spend']).round(2).where(_st_prev_df['Spend']>0, 0)
        _st_prev_df['CPA_val']  = (_st_prev_df['Spend'] / _st_prev_df['Conv_val']).round(0).where(_st_prev_df['Conv_val']>0, 0)
        _st_prev_df['CVR_val']  = 0
        _st_prev_df['Period'] = _comp_label.title()
        # prev first → bottom bar; curr second → top bar (read first)
        _st_comb = pd.concat([_st_prev_df, _st_curr], ignore_index=True)
        fig_state = px.bar(
            _st_comb, x='Spend', y='State', orientation='h',
            color='Period', barmode='group',
            color_discrete_map={'Current': BRAND_TEAL, _comp_label.title(): '#ADB5BD'},
            title="Top 15 States — Spend (Current vs Comparison)",
            labels={'Spend': 'Spend (Rs.)', 'State': ''},
            custom_data=['Conv_val','ROAS_val','CPA_val','CVR_val'],
        )
        fig_state.update_traces(
            hovertemplate=(
                "<b>%{y}</b> · %{data.name}<br>"
                "Spend: Rs.%{x:,.0f}<br>"
                "Conversions: %{customdata[0]:.1f}<br>"
                "Est. ROAS*: %{customdata[1]:.2f}x<br>"
                "CPA: Rs.%{customdata[2]:,.0f}"
                "<extra></extra>"
            )
        )
        fig_state.update_layout(height=480, plot_bgcolor='white', paper_bgcolor='white',
                                 margin=dict(t=40, b=0, r=130), showlegend=True)
    else:
        fig_state = px.bar(
            state_tbl[::-1], x='Spend', y='State', orientation='h',
            title="Top 15 States by Spend",
            color_discrete_sequence=[BRAND_TEAL],
            labels={'Spend': 'Spend (Rs.)', 'State': ''},
            category_orders={'State': _state_order_desc},
            text=state_tbl[::-1]['Est_ROAS'].apply(lambda r: f"{r:.1f}x ROAS*"),
            custom_data=[state_tbl[::-1]['Conversions'], state_tbl[::-1]['Clicks'],
                         state_tbl[::-1]['CPA'], state_tbl[::-1]['Conv_Rate'],
                         state_tbl[::-1]['Est_ROAS']],
        )
        fig_state.update_traces(textposition='outside')
        fig_state.update_traces(
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Spend: Rs.%{x:,.0f}<br>"
                "Est. ROAS*: %{customdata[4]:.2f}x<br>"
                "Conversions: %{customdata[0]:,.1f}<br>"
                "CPA: Rs.%{customdata[2]:,.0f}<br>"
                "Conv Rate: %{customdata[3]:.2f}%<br>"
                "Clicks: %{customdata[1]:,.0f}"
                "<extra></extra>"
            )
        )
        fig_state.update_layout(height=480, plot_bgcolor='white', paper_bgcolor='white',
                                 margin=dict(t=40, b=0, r=130))
    st.plotly_chart(fig_state, use_container_width=True)

    _state_cols = ['State', 'Spend', 'Conversions', 'Est_ROAS', 'Conv_Rate', 'CPA', 'Clicks']
    _state_fmt = {'Spend': 'Rs.{:,.0f}', 'CPA': 'Rs.{:,.0f}',
                  'Clicks': '{:,.0f}', 'Conversions': '{:,.1f}',
                  'CVR%': '{:.2f}%', 'ROAS*': '{:.2f}x'}
    if has_comp and 'Spend Δ%' in state_tbl.columns:
        _state_cols += ['Spend Δ%', 'Conv Δ%']
        _state_fmt['Spend Δ%'] = '{:+.1f}%'
        _state_fmt['Conv Δ%'] = '{:+.1f}%'
    st.dataframe(
        state_tbl[_state_cols]
        .rename(columns={'Conv_Rate': 'CVR%', 'Est_ROAS': 'ROAS*'})
        .style.format(_state_fmt, na_rep='—'),
        use_container_width=True, hide_index=True)
    st.caption("*ROAS estimated using blended AOV — directional only.")

    st.markdown("---")

    # ── Cities — full width (shown second) ──────────────────────────────────
    st.markdown("#### Top 20 Cities by Spend")
    city_tbl = (df_geo_f.groupby(['City', 'State'])
                .agg(Spend=('Cost', 'sum'), Clicks=('Clicks', 'sum'),
                     Conversions=('Conversions', 'sum'))
                .reset_index())
    city_tbl['CPA']       = (city_tbl['Spend'] / city_tbl['Conversions']).round(0).where(
        city_tbl['Conversions'] > 0, 0)
    city_tbl['Conv_Rate'] = (city_tbl['Conversions'] / city_tbl['Clicks'] * 100).round(2).where(
        city_tbl['Clicks'] > 0, 0)
    city_tbl['Est_Revenue'] = (city_tbl['Conversions'] * _est_aov).round(0)
    city_tbl['Est_ROAS']  = (city_tbl['Est_Revenue'] / city_tbl['Spend']).round(2).where(
        city_tbl['Spend'] > 0, 0)
    city_tbl = city_tbl[city_tbl['Spend'] > 0].sort_values('Spend', ascending=False).head(20)
    _city_order_desc = city_tbl['City'].tolist()  # descending: highest first → appears at TOP

    if has_comp and len(df_geo_comp) > 0:
        city_tbl_comp = (df_geo_comp.groupby(['City', 'State'])
                         .agg(Spend_prev=('Cost','sum'), Conversions_prev=('Conversions','sum'))
                         .reset_index())
        city_tbl = city_tbl.merge(city_tbl_comp[['City','Spend_prev','Conversions_prev']], on='City', how='left').fillna(0)
        city_tbl['Spend Δ%'] = city_tbl.apply(lambda r: _dpct(r['Spend'], r['Spend_prev']), axis=1)
        city_tbl['Conv Δ%'] = city_tbl.apply(lambda r: _dpct(r['Conversions'], r['Conversions_prev']), axis=1)

    if has_comp and 'Spend_prev' in city_tbl.columns:
        # Sort ascending so Plotly reverses to highest-at-top (same proven pattern as single-period charts)
        _ct_sorted_asc = city_tbl.sort_values('Spend', ascending=True)
        _ct_curr = _ct_sorted_asc[['City','Spend','Conversions','Est_ROAS','CPA','Conv_Rate']].copy()
        _ct_curr['Period'] = 'Current'
        _ct_curr.rename(columns={'Conversions':'Conv_val','Est_ROAS':'ROAS_val','CPA':'CPA_val','Conv_Rate':'CVR_val'}, inplace=True)
        _ct_prev_df = _ct_sorted_asc[['City','Spend_prev','Conversions_prev']].copy()
        _ct_prev_df.columns = ['City','Spend','Conv_val']
        _ct_prev_df['ROAS_val'] = (_ct_prev_df['Conv_val'] * _est_aov / _ct_prev_df['Spend']).round(2).where(_ct_prev_df['Spend']>0, 0)
        _ct_prev_df['CPA_val']  = (_ct_prev_df['Spend'] / _ct_prev_df['Conv_val']).round(0).where(_ct_prev_df['Conv_val']>0, 0)
        _ct_prev_df['CVR_val']  = 0
        _ct_prev_df['Period'] = _comp_label.title()
        # prev first → bottom bar; curr second → top bar (read first)
        _ct_comb = pd.concat([_ct_prev_df, _ct_curr], ignore_index=True)
        fig_city = px.bar(
            _ct_comb, x='Spend', y='City', orientation='h',
            color='Period', barmode='group',
            color_discrete_map={'Current': BRAND_TEAL, _comp_label.title(): '#ADB5BD'},
            title="Top 20 Cities — Spend (Current vs Comparison)",
            labels={'Spend': 'Spend (Rs.)', 'City': ''},
            custom_data=['Conv_val','ROAS_val','CPA_val','CVR_val'],
        )
        fig_city.update_traces(
            hovertemplate=(
                "<b>%{y}</b> · %{data.name}<br>"
                "Spend: Rs.%{x:,.0f}<br>"
                "Conversions: %{customdata[0]:.1f}<br>"
                "Est. ROAS*: %{customdata[1]:.2f}x<br>"
                "CPA: Rs.%{customdata[2]:,.0f}"
                "<extra></extra>"
            )
        )
        fig_city.update_layout(height=560, plot_bgcolor='white', paper_bgcolor='white',
                                margin=dict(t=40, b=0, r=120), showlegend=True)
    else:
        fig_city = px.bar(
            city_tbl[::-1], x='Spend', y='City', orientation='h',
            color='State', title="Top 20 Cities by Spend",
            labels={'Spend': 'Spend (Rs.)', 'City': ''},
            category_orders={'City': _city_order_desc},
            text=city_tbl[::-1]['Est_ROAS'].apply(lambda r: f"{r:.1f}x ROAS*"),
            custom_data=[city_tbl[::-1]['Conversions'], city_tbl[::-1]['Clicks'],
                         city_tbl[::-1]['CPA'], city_tbl[::-1]['Conv_Rate'],
                         city_tbl[::-1]['Est_ROAS']],
        )
        fig_city.update_traces(textposition='outside')
        fig_city.update_traces(
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Spend: Rs.%{x:,.0f}<br>"
                "Est. ROAS*: %{customdata[4]:.2f}x<br>"
                "Conversions: %{customdata[0]:,.1f}<br>"
                "CPA: Rs.%{customdata[2]:,.0f}<br>"
                "Conv Rate: %{customdata[3]:.2f}%<br>"
                "Clicks: %{customdata[1]:,.0f}"
                "<extra></extra>"
            )
        )
        fig_city.update_layout(height=560, plot_bgcolor='white', paper_bgcolor='white',
                                margin=dict(t=40, b=0, r=120))
    st.plotly_chart(fig_city, use_container_width=True)

    _city_cols = ['City', 'State', 'Spend', 'Conversions', 'Est_ROAS', 'Conv_Rate', 'CPA', 'Clicks']
    _city_fmt = {'Spend': 'Rs.{:,.0f}', 'CPA': 'Rs.{:,.0f}',
                 'Clicks': '{:,.0f}', 'Conversions': '{:,.1f}',
                 'CVR%': '{:.2f}%', 'ROAS*': '{:.2f}x'}
    if has_comp and 'Spend Δ%' in city_tbl.columns:
        _city_cols += ['Spend Δ%', 'Conv Δ%']
        _city_fmt['Spend Δ%'] = '{:+.1f}%'
        _city_fmt['Conv Δ%'] = '{:+.1f}%'
    st.dataframe(
        city_tbl[_city_cols]
        .rename(columns={'Conv_Rate': 'CVR%', 'Est_ROAS': 'ROAS*'})
        .style.format(_city_fmt, na_rep='—'),
        use_container_width=True, hide_index=True)
    st.caption("*ROAS estimated using blended AOV — directional only.")

    # ── Insights ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 💡 Geography Insights & Bid Adjustments")
    if has_comp:
        st.info(f"📊 Comparison mode: showing changes vs **{_comp_label}** ({comp_start.strftime('%d %b')} – {comp_end.strftime('%d %b %Y')})")

    if len(city_tbl) > 0 and _geo_cpa > 0:
        _geo_min_sp = max(5000.0, city_tbl['Spend'].sum() * 0.02)
        _city_elig  = city_tbl[city_tbl['Spend'] >= _geo_min_sp]

        gi1, gi2, gi3, gi4 = st.columns(4)
        _top_city  = city_tbl.iloc[0]
        _best_cpa_city  = _city_elig[_city_elig['CPA'] > 0].sort_values('CPA').iloc[0] if len(_city_elig[_city_elig['CPA']>0]) > 0 else None
        _worst_cpa_city = _city_elig[_city_elig['CPA'] > 0].sort_values('CPA', ascending=False).iloc[0] if len(_city_elig[_city_elig['CPA']>0]) > 0 else None
        _top_state = state_tbl.iloc[0]

        with gi1:
            st.markdown(f"""<div class="metric-card">
  <div class="metric-label">🏆 Top Volume City</div>
  <div class="metric-value">{_top_city['City']}</div>
  <div class="metric-delta" style="color:#00C9A7">{_top_city['Conversions']:,.0f} conversions</div>
</div>""", unsafe_allow_html=True)
        with gi2:
            if _best_cpa_city is not None:
                st.markdown(f"""<div class="metric-card">
  <div class="metric-label">✅ Best CPA City</div>
  <div class="metric-value">{_best_cpa_city['City']}</div>
  <div class="metric-delta" style="color:#00C9A7">Rs.{_best_cpa_city['CPA']:,.0f} CPA → BID UP</div>
</div>""", unsafe_allow_html=True)
        with gi3:
            if _worst_cpa_city is not None:
                st.markdown(f"""<div class="metric-card">
  <div class="metric-label">⚠️ Worst CPA City</div>
  <div class="metric-value">{_worst_cpa_city['City']}</div>
  <div class="metric-delta" style="color:#E63946">Rs.{_worst_cpa_city['CPA']:,.0f} CPA → BID DOWN</div>
</div>""", unsafe_allow_html=True)
        with gi4:
            st.markdown(f"""<div class="metric-card">
  <div class="metric-label">💰 Top State by Spend</div>
  <div class="metric-value">{_top_state['State']}</div>
  <div class="metric-delta" style="color:#FF6B35">{_fmt_inr(_top_state['Spend'])} · Rs.{_top_state['CPA']:,.0f} CPA</div>
</div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Bid-up candidates: CPA < 70% of blended CPA, meaningful spend
        _bid_up   = _city_elig[(_city_elig['CPA'] > 0) & (_city_elig['CPA'] < _geo_cpa * 0.7)].sort_values('CPA')
        _bid_down = _city_elig[(_city_elig['CPA'] > _geo_cpa * 1.3)].sort_values('CPA', ascending=False)

        if len(_bid_up) > 0:
            st.markdown(f"**🔼 Bid-up candidates** — CPA well below blended Rs.{_geo_cpa:,.0f} (Est. ROAS* above account avg):")
            _bu_disp = ['City', 'State', 'Spend', 'Conversions', 'Est_ROAS', 'Conv_Rate', 'CPA']
            _bu_fmt = {'Spend': 'Rs.{:,.0f}', 'CPA': 'Rs.{:,.0f}', 'Conversions': '{:,.1f}', 'ROAS*': '{:.2f}x', 'CVR%': '{:.2f}%'}
            if has_comp and 'Spend Δ%' in _bid_up.columns:
                _bu_disp += ['Spend Δ%', 'Conv Δ%']
                _bu_fmt['Spend Δ%'] = '{:+.1f}%'; _bu_fmt['Conv Δ%'] = '{:+.1f}%'
            st.dataframe(_bid_up[_bu_disp]
                         .rename(columns={'Est_ROAS': 'ROAS*', 'Conv_Rate': 'CVR%'})
                         .style.format(_bu_fmt, na_rep='—'),
                         use_container_width=True, hide_index=True)
        if len(_bid_down) > 0:
            st.markdown(f"**🔽 Bid-down candidates** — CPA well above blended Rs.{_geo_cpa:,.0f} (Est. ROAS* below account avg):")
            _bd_disp = ['City', 'State', 'Spend', 'Conversions', 'Est_ROAS', 'Conv_Rate', 'CPA']
            _bd_fmt = {'Spend': 'Rs.{:,.0f}', 'CPA': 'Rs.{:,.0f}', 'Conversions': '{:,.1f}', 'ROAS*': '{:.2f}x', 'CVR%': '{:.2f}%'}
            if has_comp and 'Spend Δ%' in _bid_down.columns:
                _bd_disp += ['Spend Δ%', 'Conv Δ%']
                _bd_fmt['Spend Δ%'] = '{:+.1f}%'; _bd_fmt['Conv Δ%'] = '{:+.1f}%'
            st.dataframe(_bid_down[_bd_disp]
                         .rename(columns={'Est_ROAS': 'ROAS*', 'Conv_Rate': 'CVR%'})
                         .style.format(_bd_fmt, na_rep='—'),
                         use_container_width=True, hide_index=True)
        if has_comp and 'Spend Δ%' in city_tbl.columns:
            _city_with_both = city_tbl.dropna(subset=['Spend Δ%', 'Conv Δ%'])
            _city_with_both = _city_with_both[_city_with_both['Spend Δ%'] != 0]
            if len(_city_with_both) > 0:
                _city_efficiency = _city_with_both.copy()
                _city_efficiency['Eff_Delta'] = _city_efficiency['Conv Δ%'] - _city_efficiency['Spend Δ%']
                _eff_improved = _city_efficiency[_city_efficiency['Eff_Delta'] > 5].sort_values('Eff_Delta', ascending=False).head(3)
                _eff_declined = _city_efficiency[_city_efficiency['Eff_Delta'] < -5].sort_values('Eff_Delta').head(3)
                if len(_eff_improved) > 0:
                    st.markdown("**📈 Cities where efficiency improved** (conversions grew faster than spend):")
                    for _, _r in _eff_improved.iterrows():
                        st.markdown(f"- {_r['City']}: spend {_r['Spend Δ%']:+.1f}% but conversions {_r['Conv Δ%']:+.1f}%")
                if len(_eff_declined) > 0:
                    st.markdown("**📉 Cities where efficiency declined** (spend grew faster than conversions):")
                    for _, _r in _eff_declined.iterrows():
                        st.markdown(f"- {_r['City']}: spend {_r['Spend Δ%']:+.1f}% but conversions {_r['Conv Δ%']:+.1f}%")


# ============================================================
# TAB 8 — Placements
# ============================================================
elif active_tab == "📺 Placements":
    st.markdown(f"### Placements — {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}")

    with st.spinner("Loading placement data…"):
        df_pl = load_placements()

    df_pl_f = filter_dates(df_pl, start_date, end_date)

    # ── Account-level overview ───────────────────────────────────────────────
    _pl_spend  = df_pl_f['Cost'].sum()
    _pl_rev    = df_pl_f['Conv_Value'].sum()
    _pl_views  = df_pl_f['Views'].sum()
    _pl_clicks = df_pl_f['Clicks'].sum()
    _pl_conv   = df_pl_f['Conversions'].sum()
    _pl_roas   = round(_pl_rev / _pl_spend, 2) if _pl_spend > 0 else 0

    if has_comp:
        df_pl_comp = filter_dates(load_placements(), comp_start, comp_end)
        _pr_pl_sp    = df_pl_comp['Cost'].sum()
        _pr_pl_rev   = df_pl_comp['Conv_Value'].sum()
        _pr_pl_views = df_pl_comp['Views'].sum()
        _pr_pl_clicks= df_pl_comp['Clicks'].sum()
        _pr_pl_roas  = round(_pr_pl_rev / _pr_pl_sp, 2) if _pr_pl_sp > 0 else 0
    else:
        _pr_pl_sp = _pr_pl_rev = _pr_pl_views = _pr_pl_clicks = _pr_pl_roas = 0

    pk1, pk2, pk3, pk4, pk5 = st.columns(5)
    kpi_card(pk1, "Total Spend",  _pl_spend,  inr=True, delta=_dpct(_pl_spend, _pr_pl_sp), delta_good='down')
    kpi_card(pk2, "ROAS",         _pl_roas,   fmt="{:.2f}", suffix="x", delta=_dpct(_pl_roas, _pr_pl_roas), delta_good='up')
    kpi_card(pk3, "Revenue",      _pl_rev,    inr=True, delta=_dpct(_pl_rev, _pr_pl_rev), delta_good='up')
    kpi_card(pk4, "Video Views",  _pl_views,  fmt="{:,.0f}", delta=_dpct(_pl_views, _pr_pl_views), delta_good='up')
    kpi_card(pk5, "Clicks",       _pl_clicks, fmt="{:,.0f}", delta=_dpct(_pl_clicks, _pr_pl_clicks), delta_good='up')

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Placement type summary ───────────────────────────────────────────────
    st.markdown("#### Spend by Placement Type")
    pt_tbl = (df_pl_f.groupby('Placement_Type')
              .agg(Spend=('Cost', 'sum'), Revenue=('Conv_Value', 'sum'),
                   Views=('Views', 'sum'), Clicks=('Clicks', 'sum'),
                   Conversions=('Conversions', 'sum'))
              .reset_index())
    pt_tbl['ROAS']   = (pt_tbl['Revenue'] / pt_tbl['Spend']).round(2).where(pt_tbl['Spend'] > 0, 0)
    pt_tbl['CPV']    = (pt_tbl['Spend'] / pt_tbl['Views']).round(2).where(pt_tbl['Views'] > 0, 0)
    pt_tbl['CPC']    = (pt_tbl['Spend'] / pt_tbl['Clicks']).round(2).where(pt_tbl['Clicks'] > 0, 0)
    pt_tbl = pt_tbl[pt_tbl['Spend'] > 0].sort_values('Spend', ascending=False)

    fig_pt = px.bar(
        pt_tbl, x='Placement_Type', y='Spend',
        color='Placement_Type',
        text=pt_tbl['ROAS'].apply(lambda r: f"{r:.1f}x" if r > 0 else "views only"),
        title="Spend by Placement Type (ROAS label; 'views only' = awareness)",
        labels={'Spend': 'Spend (Rs.)', 'Placement_Type': ''},
    )
    fig_pt.update_traces(textposition='outside')
    fig_pt.update_traces(
        hovertemplate="<b>%{x}</b><br>Spend: Rs.%{y:,.0f}<br>ROAS: %{text}<extra></extra>"
    )
    fig_pt.update_layout(showlegend=False, height=300,
                          plot_bgcolor='white', paper_bgcolor='white')
    st.plotly_chart(fig_pt, use_container_width=True)

    st.dataframe(
        pt_tbl[['Placement_Type', 'Spend', 'Views', 'Clicks', 'Conversions', 'Revenue', 'ROAS', 'CPV', 'CPC']]
        .rename(columns={'Placement_Type': 'Type'})
        .style.format({'Spend': 'Rs.{:,.0f}', 'Revenue': 'Rs.{:,.0f}', 'ROAS': '{:.2f}x',
                       'CPV': 'Rs.{:.2f}', 'CPC': 'Rs.{:.2f}',
                       'Views': '{:,.0f}', 'Clicks': '{:,.0f}', 'Conversions': '{:,.1f}'}),
        use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── Split: YouTube (views-based) vs Performance (conversions-based) ──────
    df_yt   = df_pl_f[df_pl_f['Views'] > 0]
    df_perf = df_pl_f[df_pl_f['Views'] == 0]

    # ── YouTube (full width) ─────────────────────────────────────────────────
    st.markdown("#### 📹 Top YouTube Placements (by Views)")
    yt_tbl = (df_yt.groupby(['Placement', 'Placement_Type'])
              .agg(Spend=('Cost', 'sum'), Views=('Views', 'sum'), Clicks=('Clicks', 'sum'))
              .reset_index())
    yt_tbl['CPV'] = (yt_tbl['Spend'] / yt_tbl['Views']).round(3).where(yt_tbl['Views'] > 0, 0)
    yt_tbl = yt_tbl[yt_tbl['Spend'] > 0].sort_values('Views', ascending=False).head(15)
    # Chart label: ASCII-safe truncated name (Indic scripts can't render in Plotly SVG)
    yt_tbl['Label'] = yt_tbl['Placement'].apply(lambda n: _ascii_label(n, 40))

    if has_comp and len(df_pl_comp) > 0:
        df_yt_comp = df_pl_comp[df_pl_comp['Views'] > 0]
        yt_tbl_comp = (df_yt_comp.groupby('Placement')
                       .agg(Views_prev=('Views','sum'), Spend_prev=('Cost','sum'))
                       .reset_index())
        yt_tbl_comp['CPV_prev'] = (yt_tbl_comp['Spend_prev']/yt_tbl_comp['Views_prev']).round(3).where(yt_tbl_comp['Views_prev']>0, 0)
        yt_tbl = yt_tbl.merge(yt_tbl_comp[['Placement','Views_prev','CPV_prev']], on='Placement', how='left').fillna(0)
        yt_tbl['Views Δ%'] = yt_tbl.apply(lambda r: _dpct(r['Views'], r['Views_prev']), axis=1)
        yt_tbl['CPV Δ%'] = yt_tbl.apply(lambda r: _dpct(r['CPV'], r['CPV_prev']), axis=1)
        _yt_curr = yt_tbl[['Label','Views']].copy(); _yt_curr['Period']='Current'
        _yt_prev = yt_tbl[['Label','Views_prev']].copy().rename(columns={'Views_prev':'Views'}); _yt_prev['Period']=_comp_label.title()
        _yt_comb = pd.concat([_yt_curr, _yt_prev])
        fig_yt = px.bar(
            _yt_comb, x='Views', y='Label', orientation='h',
            color='Period', barmode='group',
            color_discrete_sequence=[BRAND_RED, '#ADB5BD'],
            title="Top YouTube Channels/Videos by Views",
            labels={'Views': 'Views', 'Label': ''},
        )
        fig_yt.update_traces(hovertemplate="<b>%{y}</b> · %{data.name}<br>Views: %{x:,.0f}<extra></extra>")
        fig_yt.update_layout(height=420, plot_bgcolor='white', paper_bgcolor='white',
                              margin=dict(t=40, b=0, r=30),
                              yaxis=dict(tickfont=dict(size=10), automargin=True), showlegend=True)
    else:
        fig_yt = px.bar(
            yt_tbl[::-1], x='Views', y='Label', orientation='h',
            title="Top YouTube Channels/Videos by Views",
            color_discrete_sequence=[BRAND_RED],
            labels={'Views': 'Views', 'Label': ''},
            custom_data=[yt_tbl[::-1]['Spend'], yt_tbl[::-1]['Placement'],
                         yt_tbl[::-1]['CPV'], yt_tbl[::-1]['Clicks']],
        )
        fig_yt.update_traces(
            hovertemplate=(
                "<b>%{customdata[1]}</b><br>"
                "Views: %{x:,.0f}<br>"
                "Spend: Rs.%{customdata[0]:,.0f}<br>"
                "CPV: Rs.%{customdata[2]:.3f}<br>"
                "Clicks: %{customdata[3]:,.0f}"
                "<extra></extra>"
            )
        )
        fig_yt.update_layout(height=420, plot_bgcolor='white', paper_bgcolor='white',
                              margin=dict(t=40, b=0, r=30),
                              yaxis=dict(tickfont=dict(size=10), automargin=True))
    st.plotly_chart(fig_yt, use_container_width=True)

    st.caption("Full channel/video names (including regional scripts) shown in table below.")
    _yt_disp_cols = ['Placement', 'Placement_Type', 'Spend', 'Views', 'Clicks', 'CPV']
    _yt_fmt = {'Spend': 'Rs.{:,.0f}', 'Views': '{:,.0f}', 'Clicks': '{:,.0f}', 'CPV': 'Rs.{:.3f}'}
    if has_comp and 'Views Δ%' in yt_tbl.columns:
        _yt_disp_cols += ['Views Δ%', 'CPV Δ%']
        _yt_fmt['Views Δ%'] = '{:+.1f}%'
        _yt_fmt['CPV Δ%'] = '{:+.1f}%'
    st.dataframe(
        yt_tbl[_yt_disp_cols]
        .rename(columns={'Placement_Type': 'Type'})
        .style.format(_yt_fmt, na_rep='—'),
        use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── Performance (full width) ──────────────────────────────────────────────
    st.markdown("#### 🖥️ Top Performance Placements (by Revenue)")
    perf_tbl = (df_perf.groupby(['Placement', 'Placement_Type'])
                .agg(Spend=('Cost', 'sum'), Revenue=('Conv_Value', 'sum'),
                     Clicks=('Clicks', 'sum'), Conversions=('Conversions', 'sum'))
                .reset_index())
    perf_tbl['ROAS'] = (perf_tbl['Revenue'] / perf_tbl['Spend']).round(2).where(perf_tbl['Spend'] > 0, 0)
    perf_tbl = perf_tbl[perf_tbl['Spend'] > 0].sort_values('Revenue', ascending=False).head(15)
    perf_tbl['Short'] = perf_tbl['Placement'].str[:45]

    if has_comp and len(df_pl_comp) > 0:
        df_perf_comp = df_pl_comp[df_pl_comp['Views'] == 0]
        perf_tbl_comp = (df_perf_comp.groupby('Placement')
                         .agg(Revenue_prev=('Conv_Value','sum'), Spend_prev=('Cost','sum'))
                         .reset_index())
        perf_tbl_comp['ROAS_prev'] = (perf_tbl_comp['Revenue_prev']/perf_tbl_comp['Spend_prev']).round(2).where(perf_tbl_comp['Spend_prev']>0, 0)
        perf_tbl = perf_tbl.merge(perf_tbl_comp[['Placement','Revenue_prev','ROAS_prev']], on='Placement', how='left').fillna(0)
        perf_tbl['Rev Δ%'] = perf_tbl.apply(lambda r: _dpct(r['Revenue'], r['Revenue_prev']), axis=1)
        perf_tbl['ROAS Δ%'] = perf_tbl.apply(lambda r: _dpct(r['ROAS'], r['ROAS_prev']), axis=1)
        _pp_curr = perf_tbl[['Short','Revenue']].copy(); _pp_curr['Period']='Current'
        _pp_prev = perf_tbl[['Short','Revenue_prev']].copy().rename(columns={'Revenue_prev':'Revenue'}); _pp_prev['Period']=_comp_label.title()
        _pp_comb = pd.concat([_pp_curr, _pp_prev])
        fig_perf = px.bar(
            _pp_comb, x='Revenue', y='Short', orientation='h',
            color='Period', barmode='group',
            color_discrete_sequence=[BRAND_ORANGE, '#ADB5BD'],
            title="Top Performance Placements by Revenue",
            labels={'Revenue': 'Revenue (Rs.)', 'Short': ''},
        )
        fig_perf.update_traces(hovertemplate="<b>%{y}</b> · %{data.name}<br>Revenue: Rs.%{x:,.0f}<extra></extra>")
        fig_perf.update_layout(height=400, plot_bgcolor='white', paper_bgcolor='white',
                                margin=dict(t=40, b=0, r=80),
                                yaxis=dict(tickfont=dict(size=10)), showlegend=True)
    else:
        fig_perf = px.bar(
            perf_tbl[::-1], x='Revenue', y='Short', orientation='h',
            color='Placement_Type', title="Top Performance Placements by Revenue",
            labels={'Revenue': 'Revenue (Rs.)', 'Short': ''},
            text=perf_tbl[::-1]['ROAS'].apply(lambda r: f"{r:.1f}x"),
            custom_data=[perf_tbl[::-1]['Spend'], perf_tbl[::-1]['Placement']],
        )
        fig_perf.update_traces(textposition='outside')
        fig_perf.update_traces(
            hovertemplate="<b>%{customdata[1]}</b><br>Revenue: Rs.%{x:,.0f}<br>Spend: Rs.%{customdata[0]:,.0f}<br>ROAS: %{text}<extra></extra>"
        )
        fig_perf.update_layout(height=400, plot_bgcolor='white', paper_bgcolor='white',
                                margin=dict(t=40, b=0, r=80),
                                yaxis=dict(tickfont=dict(size=10)))
    st.plotly_chart(fig_perf, use_container_width=True)

    _perf_disp_cols = ['Short', 'Placement_Type', 'Spend', 'Clicks', 'Revenue', 'ROAS', 'Conversions']
    _perf_fmt = {'Spend': 'Rs.{:,.0f}', 'Revenue': 'Rs.{:,.0f}', 'ROAS': '{:.2f}x',
                 'Clicks': '{:,.0f}', 'Conversions': '{:,.1f}'}
    if has_comp and 'Rev Δ%' in perf_tbl.columns:
        _perf_disp_cols += ['Rev Δ%', 'ROAS Δ%']
        _perf_fmt['Rev Δ%'] = '{:+.1f}%'
        _perf_fmt['ROAS Δ%'] = '{:+.1f}%'
    st.dataframe(
        perf_tbl[_perf_disp_cols]
        .rename(columns={'Short': 'Placement', 'Placement_Type': 'Type'})
        .style.format(_perf_fmt, na_rep='—'),
        use_container_width=True, hide_index=True)

    # ── Placement insights ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 💡 Placement Insights")
    if has_comp:
        st.info(f"📊 Comparison mode: showing changes vs **{_comp_label}** ({comp_start.strftime('%d %b')} – {comp_end.strftime('%d %b %Y')})")
    if len(perf_tbl) > 0:
        _pl_min_sp = max(5000.0, perf_tbl['Spend'].sum() * 0.02)
        _pl_elig   = perf_tbl[perf_tbl['Spend'] >= _pl_min_sp]
        pli1, pli2, pli3 = st.columns(3)
        _pl_best  = _pl_elig.loc[_pl_elig['ROAS'].idxmax()] if len(_pl_elig) > 0 else perf_tbl.iloc[0]
        _pl_worst_cands = _pl_elig[_pl_elig['ROAS'] > 0]
        _pl_worst = _pl_worst_cands.sort_values('ROAS').iloc[0] if len(_pl_worst_cands) > 0 else None

        _pl_roas_delta_str = ''
        _pl_worst_delta_str = ''
        if has_comp and 'ROAS Δ%' in perf_tbl.columns:
            _pld = _dpct(_pl_best['ROAS'], _pl_best.get('ROAS_prev', 0))
            if _pld is not None:
                _pl_roas_delta_str = f' · {_delta_badge(_pld, "up")}'
            if _pl_worst is not None:
                _pwd = _dpct(_pl_worst['ROAS'], _pl_worst.get('ROAS_prev', 0))
                if _pwd is not None:
                    _pl_worst_delta_str = f' · {_delta_badge(_pwd, "up")}'

        with pli1:
            st.markdown(f"""<div class="metric-card">
  <div class="metric-label">🏆 Best ROAS Placement</div>
  <div class="metric-value" style="font-size:12px">{str(_pl_best['Short'])[:45]}</div>
  <div class="metric-delta" style="color:#00C9A7">{_pl_best['ROAS']:.1f}x ROAS{_pl_roas_delta_str}</div>
</div>""", unsafe_allow_html=True)
        with pli2:
            if len(yt_tbl) > 0:
                _yt_top = yt_tbl.iloc[0]
                _yt_views_delta_str = ''
                if has_comp and 'Views Δ%' in yt_tbl.columns:
                    _ytd = _dpct(_yt_top['Views'], _yt_top.get('Views_prev', 0))
                    if _ytd is not None:
                        _yt_views_delta_str = f' · {_delta_badge(_ytd, "up")}'
                st.markdown(f"""<div class="metric-card">
  <div class="metric-label">📹 Top YouTube Channel</div>
  <div class="metric-value" style="font-size:12px">{_ascii_label(str(_yt_top['Placement']), 45)}</div>
  <div class="metric-delta" style="color:#FF6B35">{_yt_top['Views']:,.0f} views · Rs.{_yt_top['CPV']:.2f} CPV{_yt_views_delta_str}</div>
</div>""", unsafe_allow_html=True)
        with pli3:
            if _pl_worst is not None:
                st.markdown(f"""<div class="metric-card">
  <div class="metric-label">⚠️ Lowest ROAS Placement</div>
  <div class="metric-value" style="font-size:12px">{str(_pl_worst['Short'])[:45]}</div>
  <div class="metric-delta" style="color:#E63946">{_pl_worst['ROAS']:.1f}x ROAS → consider excluding{_pl_worst_delta_str}</div>
</div>""", unsafe_allow_html=True)

        if has_comp and 'Rev Δ%' in perf_tbl.columns:
            _perf_with_delta = perf_tbl.dropna(subset=['Rev Δ%'])
            if len(_perf_with_delta) > 0:
                _perf_best_imp = _perf_with_delta.loc[_perf_with_delta['Rev Δ%'].idxmax()]
                _perf_worst_dec = _perf_with_delta.loc[_perf_with_delta['Rev Δ%'].idxmin()]
                st.markdown(f"**Most improved placement:** {str(_perf_best_imp['Short'])[:60]} — revenue {_perf_best_imp['Rev Δ%']:+.1f}%")
                st.markdown(f"**Most declined placement:** {str(_perf_worst_dec['Short'])[:60]} — revenue {_perf_worst_dec['Rev Δ%']:+.1f}%")
