"""
dashboard.py  –  Nasher Miles Meta Ads Intelligence Dashboard
Run:  streamlit run dashboard.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import data_prep as dp

# ─── page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Nasher Miles | Meta Ads Intelligence",
    page_icon="🧳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700;900&display=swap');
  /* Apply Roboto everywhere EXCEPT span (Material Icons uses span + font ligatures for icons) */
  html, body, [class*="css"], .stMarkdown, .stText, p, div, label, h1,h2,h3,h4,h5,h6 {
    font-family: 'Roboto', sans-serif !important;
  }
  /* Apply Roboto to non-icon spans only */
  span:not(.material-icons):not([data-testid]) {
    font-family: 'Roboto', sans-serif !important;
  }
  /* brand palette */
  :root {
    --nm-navy:   #1A3C5E;
    --nm-blue:   #2E75B6;
    --nm-ltblue: #CBE3FF;
    --nm-pink:   #FECAFD;
    --nm-green:  #CBFFAB;
    --nm-yellow: #FEF9C2;
    --nm-cream:  #FFFDEB;
  }
  /* ── sidebar ── */
  [data-testid="stSidebar"] { background: var(--nm-navy) !important; }
  [data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3,
  [data-testid="stSidebar"] h4,[data-testid="stSidebar"] p,
  [data-testid="stSidebar"] span,[data-testid="stSidebar"] .stMarkdown { color: #DEEAF1 !important; }
  [data-testid="stSidebar"] label { color: #DEEAF1 !important; font-weight: 600; }
  [data-testid="stSidebar"] [data-baseweb="select"] div,
  [data-testid="stSidebar"] [data-baseweb="select"] input,
  [data-testid="stSidebar"] [data-baseweb="select"] span { color: var(--nm-navy) !important; background: #FFF; }
  [data-testid="stSidebar"] [data-baseweb="tag"] span { color: var(--nm-navy) !important; }
  [data-testid="stSidebar"] input[type="number"] { color: var(--nm-navy) !important; background: #FFF !important; }
  [data-testid="stSidebar"] .stCaption, [data-testid="stSidebar"] small { color: #A8C4D8 !important; }
  [data-testid="stSidebar"] hr { border-color: var(--nm-blue); }
  /* ── KPI cards ── */
  .metric-card {
    background: linear-gradient(135deg, var(--nm-navy) 0%, var(--nm-blue) 100%);
    border-radius: 12px; padding: 14px 12px; color: white;
    box-shadow: 0 4px 15px rgba(26,60,94,0.25);
    text-align: center; height: 130px;
    display: flex; flex-direction: column;
    justify-content: center; align-items: center;
  }
  .metric-card .label { font-size:10px; opacity:0.8; text-transform:uppercase; letter-spacing:0.8px; line-height:1.3; word-break:break-word; max-width:100%; }
  .metric-card .value { font-size:22px; font-weight:900; margin:5px 0 3px; line-height:1.1; white-space:nowrap; }
  .metric-card .delta { font-size:11px; opacity:0.85; }
  /* ── alert cards ── */
  .alert-card { border-left:4px solid; border-radius:8px; padding:12px 16px; margin-bottom:10px; }
  .alert-critical { background:#FFE2E2; border-color:#C00000; }
  .alert-warning  { background:var(--nm-yellow); border-color:#ED7D31; }
  .alert-info     { background:var(--nm-ltblue); border-color:var(--nm-blue); }
  .alert-good     { background:var(--nm-green); border-color:#276221; }
  .alert-title    { font-weight:700; font-size:13px; }
  .alert-body     { font-size:12px; margin-top:4px; color:#333; }
  /* ── narrative box ── */
  .narrative-box { background:linear-gradient(135deg,var(--nm-ltblue) 0%,var(--nm-pink) 100%); border-radius:12px; padding:20px 24px; border-left:5px solid var(--nm-navy); margin-bottom:20px; }
  .narrative-box h4 { margin:0 0 10px; color:var(--nm-navy); font-size:15px; font-weight:700; }
  .narrative-box .nb-section { margin:10px 0 4px; font-weight:700; color:var(--nm-navy); font-size:13px; }
  .narrative-box p  { margin:0 0 6px; color:#333; font-size:13px; line-height:1.65; }
  /* ── section title ── */
  .section-title { font-size:18px; font-weight:700; color:var(--nm-navy); border-bottom:2px solid var(--nm-blue); padding-bottom:6px; margin:24px 0 16px; }
  /* ── funnel stage cards ── */
  .funnel-card { border-radius:10px; padding:12px 16px; text-align:center; }
  /* ── sim card ── */
  .sim-card { background:var(--nm-ltblue); border-radius:10px; padding:14px 18px; text-align:center; }
  .sim-card .sc-label { font-size:11px; color:var(--nm-navy); font-weight:600; text-transform:uppercase; }
  .sim-card .sc-value { font-size:24px; font-weight:900; color:var(--nm-navy); margin:4px 0 2px; }
  .sim-card .sc-delta { font-size:12px; font-weight:500; }
  /* ── tabs ── */
  .stTabs [data-baseweb="tab"] { font-weight:600; font-size:13px; font-family:'Roboto',sans-serif !important; }
  .stTabs [aria-selected="true"] { color:var(--nm-navy) !important; }
</style>
""", unsafe_allow_html=True)

ROAS_BE    = 5.5
MIN_SPEND  = 2500
FREQ_ALERT = 3.0
COLORS     = ['#1A3C5E','#2E75B6','#70AD47','#ED7D31','#C00000','#7B2D8B','#00B0F0','#FFD700']

def _fmt_inr(v):
    """Spend/Revenue: ₹X,XXX.XX"""
    try:
        fv = float(v)
        return '-' if np.isnan(fv) else f"₹{fv:,.2f}"
    except (ValueError, TypeError):
        return '-'

def _fmt_num(v, decimals=2):
    """ROAS and generic: X.XX"""
    try:
        fv = float(v)
        return '-' if np.isnan(fv) else f"{fv:.{decimals}f}"
    except (ValueError, TypeError):
        return '-'

def _fmt_pct(v):
    """CTR, CVR: X.XX%"""
    try:
        fv = float(v)
        return '-' if np.isnan(fv) else f"{fv:.2f}%"
    except (ValueError, TypeError):
        return '-'

def _fmt_int(v):
    """Purchases: whole number"""
    try:
        fv = float(v)
        return '-' if np.isnan(fv) else f"{fv:.0f}"
    except (ValueError, TypeError):
        return '-'

# ─── data loading (cached) ────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner="Loading Meta Ads data...")
def load_data():
    df_c, df_d, df_p = dp.load_all()
    return df_c, df_d, df_p

# ─── sidebar filters ──────────────────────────────────────────────────────────
def sidebar(df_c):
    st.sidebar.markdown("## 🧳 Nasher Miles")
    st.sidebar.markdown("### Meta Ads Intelligence")
    st.sidebar.markdown("---")

    if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
        load_data.clear()
        st.rerun()

    st.sidebar.markdown("#### Date Range")

    min_d = dp.DATA_MIN_DATE or dp.MONTH_STARTS[0].date()
    max_d = dp.DATA_MAX_DATE or dp.MONTH_ENDS[-1].date()

    date_range = st.sidebar.date_input(
        "Select date range",
        value=(min_d, max_d),
        min_value=min_d,
        max_value=max_d,
        format="DD/MM/YYYY",
        help="Pick start and end date. Add a 'Date' column to your raw sheets for daily granularity."
    )
    # handle single-date click (user still selecting range)
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    else:
        start = end = pd.Timestamp(date_range[0] if isinstance(date_range, (list,tuple)) else date_range)

    # derive display labels for selected period
    sel_months = []
    for lbl, ms, me in zip(dp.MONTH_LABELS, dp.MONTH_STARTS, dp.MONTH_ENDS):
        if ms <= end and me >= start:
            sel_months.append(lbl)
    if not sel_months:
        sel_months = dp.MONTH_LABELS

    if dp.HAS_DAILY_DATA:
        st.sidebar.caption(f"Daily data: {date_range[0] if isinstance(date_range,tuple) else date_range} to {date_range[1] if isinstance(date_range,tuple) and len(date_range)==2 else ''}")
    else:
        st.sidebar.caption("Monthly data. Add a 'Date' column for daily granularity.")

    st.sidebar.markdown("#### Compare With")
    comp_options = ["None", "Previous Period", "Previous Month", "Previous Quarter", "Same Period Last Year"]
    comp_sel = st.sidebar.selectbox("Comparison period", comp_options, index=1,
                                    help="Overlay a prior period on KPIs and charts")

    st.sidebar.markdown("#### Objective")
    raw_objs = sorted(df_c['Objective'].dropna().astype(str).str.strip().unique().tolist())
    objectives = raw_objs + ['All']
    default_obj = 'OUTCOME_SALES' if 'OUTCOME_SALES' in objectives else objectives[0]
    obj = st.sidebar.selectbox("Campaign objective", objectives,
                                index=objectives.index(default_obj))

    st.sidebar.markdown("#### Benchmarks")
    roas_be   = st.sidebar.number_input("Break-even ROAS", value=5.5, step=0.1, min_value=1.0)
    min_spend = st.sidebar.number_input("Min spend for action (INR)", value=2500, step=500)

    st.sidebar.markdown("---")
    st.sidebar.caption("Source: OneDrive Excel. Click '🔄 Refresh Data' at the top after updating the Excel file.")

    sel_idx = list(range(len(sel_months)))  # kept for compatibility
    return sel_months, sel_idx, start, end, obj, roas_be, min_spend, comp_sel


def filter_df(df_c, df_d, df_p, obj, start, end):
    end_incl = end + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    def filt(df):
        d = df.copy()
        if obj != 'All':
            d = d[d['Objective'].astype(str).str.strip() == obj.strip()]
        date_col = 'Date' if ('Date' in d.columns and d['Date'].notna().any()) else 'Month_Start'
        d = d[(d[date_col] >= start) & (d[date_col] <= end_incl)]
        return d
    return filt(df_c), filt(df_d), filt(df_p)


def compute_comp_range(start, end, comp_sel):
    """Returns (comp_start, comp_end, label) or (None, None, '') when no comparison."""
    if comp_sel == "None":
        return None, None, ""

    delta = end - start   # timedelta of the selected window

    if comp_sel == "Previous Period":
        comp_end   = start - pd.Timedelta(days=1)
        comp_start = comp_end - delta
        label = f"{comp_start.strftime('%d %b %Y')} – {comp_end.strftime('%d %b %Y')}"

    elif comp_sel == "Previous Month":
        first_of_curr = start.replace(day=1)
        comp_end   = first_of_curr - pd.Timedelta(days=1)
        comp_start = comp_end.replace(day=1)
        label = comp_start.strftime('%b %Y')

    elif comp_sel == "Previous Quarter":
        # quarter of the start date
        q = (start.month - 1) // 3   # 0=Q1, 1=Q2, 2=Q3, 3=Q4
        if q == 0:
            comp_start = pd.Timestamp(start.year - 1, 10, 1)
            comp_end   = pd.Timestamp(start.year - 1, 12, 31)
            label = f"Q4 {start.year - 1}"
        else:
            comp_start = pd.Timestamp(start.year, (q - 1) * 3 + 1, 1)
            comp_end   = start.replace(day=1) - pd.Timedelta(days=1)
            label = f"Q{q} {start.year}"

    elif comp_sel == "Same Period Last Year":
        comp_start = start - pd.DateOffset(years=1)
        comp_end   = end   - pd.DateOffset(years=1)
        label = f"{comp_start.strftime('%d %b %Y')} – {comp_end.strftime('%d %b %Y')}"

    else:
        return None, None, ""

    return pd.Timestamp(comp_start), pd.Timestamp(comp_end), label


# ─── metric card helper ───────────────────────────────────────────────────────
def metric_card(col, label, value, delta=None, delta_good=True):
    delta_html = ""
    if delta is not None:
        sign  = "+" if delta >= 0 else ""
        color = "#90EE90" if (delta >= 0) == delta_good else "#FFB3B3"
        delta_html = f'<div class="delta" style="color:{color};">{sign}{delta:.1f}% vs prev period</div>'
    col.markdown(f"""
    <div class="metric-card">
      <div class="label">{label}</div>
      <div class="value">{value}</div>
      {delta_html}
    </div>""", unsafe_allow_html=True)


# ─── AI narrative ─────────────────────────────────────────────────────────────
def build_narrative(agg_acc, agg_fun_t, agg_cat, agg_fmt, agg_inf,
                    agg_demo, agg_plat, sel_months, roas_be, df_c_filt):
    """Full narrative: What Meta contributed / What worked / What didn't / What to change."""
    if agg_acc.empty:
        return None

    mo_map = dict(zip(dp.MONTH_ORDER, dp.MONTH_LABELS))

    # ── totals ────────────────────────────────────────────────────────────────
    total_spend  = agg_acc['Spend'].sum()
    total_rev    = agg_acc['Revenue'].sum()
    total_purch  = int(agg_acc['Purchases'].sum())
    total_atc    = int(df_c_filt['Adds to cart'].sum())
    total_impr   = agg_acc['Impressions'].sum()
    total_clicks = agg_acc['Clicks'].sum()
    overall_roas = total_rev / total_spend if total_spend else 0
    overall_cpa  = total_spend / total_purch if total_purch else 0
    overall_ctr  = total_clicks / total_impr * 100 if total_impr else 0
    overall_cvr  = total_purch / total_clicks * 100 if total_clicks else 0
    roas_color   = "#276221" if overall_roas >= roas_be else "#C00000"

    best_m_row   = agg_acc.loc[agg_acc['ROAS'].idxmax()]
    worst_m_row  = agg_acc.loc[agg_acc['ROAS'].idxmin()]
    best_m_lbl   = mo_map.get(best_m_row['Month'], str(best_m_row['Month']))
    worst_m_lbl  = mo_map.get(worst_m_row['Month'], str(worst_m_row['Month']))

    # ── trend ─────────────────────────────────────────────────────────────────
    trend_note = ""
    if len(agg_acc) >= 2:
        r_last = agg_acc.iloc[-1]['ROAS']; r_prev = agg_acc.iloc[-2]['ROAS']
        pct    = (r_last - r_prev) / r_prev * 100 if r_prev else 0
        arrow  = "up" if pct >= 0 else "down"
        trend_note = f"ROAS moved <b>{arrow} {abs(pct):.0f}%</b> in the most recent month."

    # ── what worked ───────────────────────────────────────────────────────────
    worked = []

    # best funnel
    if not agg_fun_t.empty:
        bof = agg_fun_t[agg_fun_t['Funnel'].astype(str).str.upper().str.contains('BOF', na=False)]
        if not bof.empty and bof.iloc[0]['ROAS'] >= roas_be:
            worked.append(f"<b>BOF (retargeting)</b> delivered {bof.iloc[0]['ROAS']:.2f}x ROAS — "
                          f"the engine driving purchases")
        tof = agg_fun_t[agg_fun_t['Funnel'].astype(str).str.upper().str.contains('TOF', na=False)]
        if not tof.empty:
            worked.append(f"<b>TOF</b> drove {int(tof.iloc[0]['Impressions']):,} impressions "
                          f"at CPM INR {tof.iloc[0]['CPM']:.0f} — filling the top of funnel")

    # best category
    if not agg_cat.empty:
        best_c = agg_cat.dropna(subset=['Category']).loc[agg_cat.dropna(subset=['Category'])['ROAS'].idxmax()]
        if best_c['ROAS'] >= roas_be:
            worked.append(f"<b>{best_c['Category']}</b> category: "
                          f"{best_c['ROAS']:.2f}x ROAS on INR {best_c['Spend']:,.0f} spend")

    # best format
    if not agg_fmt.empty:
        best_f = agg_fmt.dropna(subset=['Format']).loc[agg_fmt.dropna(subset=['Format'])['ROAS'].idxmax()]
        if best_f['ROAS'] >= roas_be:
            worked.append(f"<b>{best_f['Format']}</b> format outperformed with "
                          f"{best_f['ROAS']:.2f}x ROAS")

    # influencer check
    if not agg_inf.empty:
        inf  = agg_inf[agg_inf['Is_Influencer'] == True]
        bau  = agg_inf[agg_inf['Is_Influencer'] == False]
        if not inf.empty and not bau.empty:
            ir = inf.iloc[0]['ROAS']; br = bau.iloc[0]['ROAS']
            if ir > br:
                worked.append(f"<b>Influencer creatives</b> beat BAU ({ir:.2f}x vs {br:.2f}x ROAS)")
            elif br > ir:
                worked.append(f"<b>BAU (non-influencer) creatives</b> outperformed influencers "
                              f"({br:.2f}x vs {ir:.2f}x ROAS) — brand content is strong")

    # best platform
    if not agg_plat.empty:
        plat_g = agg_plat.groupby('Platform').agg(
            Spend=('Spend','sum'), Revenue=('Revenue','sum')).reset_index()
        plat_g['ROAS'] = plat_g['Revenue'] / plat_g['Spend'].replace(0, np.nan)
        best_p = plat_g.loc[plat_g['ROAS'].idxmax()]
        worked.append(f"<b>{best_p['Platform']}</b> was the best platform at "
                      f"{best_p['ROAS']:.2f}x ROAS")

    # ── what didn't work ──────────────────────────────────────────────────────
    didnt = []

    overall_roas_status = (f"<b style='color:{roas_color};'>{overall_roas:.2f}x ROAS</b> is "
                           + ("above" if overall_roas >= roas_be else "below")
                           + f" the {roas_be}x break-even across the selected period")
    didnt.append(overall_roas_status)

    # worst month
    if worst_m_row['ROAS'] < roas_be:
        didnt.append(f"<b>{worst_m_lbl}</b> was the weakest month at "
                     f"{worst_m_row['ROAS']:.2f}x ROAS")

    # underperforming funnel
    if not agg_fun_t.empty:
        under = agg_fun_t[(agg_fun_t['ROAS'] < roas_be) &
                          (agg_fun_t['Spend'] >= MIN_SPEND)].dropna(subset=['Funnel'])
        for _, r in under.iterrows():
            didnt.append(f"<b>{r['Funnel']}</b> spent INR {r['Spend']:,.0f} "
                         f"at only {r['ROAS']:.2f}x ROAS — below break-even")

    # underperforming category
    if not agg_cat.empty:
        uc = agg_cat[(agg_cat['ROAS'] < roas_be) &
                     (agg_cat['Spend'] >= MIN_SPEND)].dropna(subset=['Category'])
        for _, r in uc.iterrows():
            didnt.append(f"<b>{r['Category']}</b> category underperformed at "
                         f"{r['ROAS']:.2f}x ROAS")

    # frequency alert
    if 'Frequency' in df_c_filt.columns:
        max_freq = df_c_filt['Frequency'].max()
        if max_freq > FREQ_ALERT:
            didnt.append(f"Ad frequency reached <b>{max_freq:.1f}x</b> — "
                         f"audience is seeing the same ads too often (creative fatigue)")

    # low CVR
    if overall_cvr < 1.0:
        didnt.append(f"Overall click-to-purchase CVR is low at <b>{overall_cvr:.2f}%</b> — "
                     f"landing page or checkout friction may be losing buyers")

    # ── what we'll change ─────────────────────────────────────────────────────
    changes = []

    if overall_roas < roas_be:
        changes.append("Shift budget from underperforming segments to proven BOF retargeting "
                       "until account ROAS recovers above break-even")

    if not agg_fun_t.empty:
        bof2 = agg_fun_t[agg_fun_t['Funnel'].astype(str).str.upper().str.contains('BOF', na=False)]
        if not bof2.empty and bof2.iloc[0]['ROAS'] >= roas_be * 1.1:
            changes.append(f"Scale <b>BOF spend 20–30%</b> — "
                           f"it's at {bof2.iloc[0]['ROAS']:.2f}x with room to grow")

    if not agg_fmt.empty:
        worst_fmt = agg_fmt.dropna(subset=['Format'])
        if not worst_fmt.empty:
            wf = worst_fmt.loc[worst_fmt['ROAS'].idxmin()]
            if wf['ROAS'] < roas_be and wf['Spend'] >= MIN_SPEND:
                changes.append(f"Reduce <b>{wf['Format']}</b> format budget — "
                               f"lowest ROAS at {wf['ROAS']:.2f}x")

    if not agg_cat.empty:
        bc = agg_cat.dropna(subset=['Category']).loc[agg_cat.dropna(subset=['Category'])['ROAS'].idxmax()]
        if bc['ROAS'] >= roas_be * 1.1:
            changes.append(f"Push more budget into <b>{bc['Category']}</b> — "
                           f"strongest category at {bc['ROAS']:.2f}x ROAS")

    if 'Frequency' in df_c_filt.columns and df_c_filt['Frequency'].max() > FREQ_ALERT:
        changes.append("Rotate creatives immediately to reduce frequency and combat fatigue")

    if overall_cvr < 1.0:
        changes.append("A/B test landing page — CVR below 1% suggests checkout drop-off, "
                       "not an ads problem")

    return {
        'totals':    (total_spend, total_rev, total_purch, total_atc, overall_roas,
                      overall_cpa, overall_ctr, overall_cvr, roas_color, roas_be,
                      best_m_lbl, trend_note),
        'worked':    worked[:5],
        'didnt':     didnt[:5],
        'changes':   changes[:5],
    }


# ─── anomaly detection ────────────────────────────────────────────────────────
def detect_anomalies(df_c_filt, agg_account, agg_funnel, agg_cat, roas_be, min_spend):
    alerts = []

    # 1. ROAS below break-even with significant spend
    if not agg_account.empty:
        for _, row in agg_account.iterrows():
            if row['Spend'] >= min_spend and row['ROAS'] < roas_be:
                alerts.append({
                    'level': 'critical',
                    'title': f"ROAS below break-even in {row['Month']}",
                    'body':  f"Spent INR {row['Spend']:,.0f} at {row['ROAS']:.2f}x ROAS. "
                             f"Break-even is {roas_be}x. Immediate review needed."
                })

    # 2. High frequency
    if 'Frequency' in df_c_filt.columns:
        hi_freq = df_c_filt[df_c_filt['Frequency'] > FREQ_ALERT]
        if not hi_freq.empty:
            worst = hi_freq.loc[hi_freq['Frequency'].idxmax()]
            alerts.append({
                'level': 'warning',
                'title': f"Creative fatigue: frequency {worst['Frequency']:.1f}x",
                'body':  f"Campaign '{str(worst.get('Campaign name',''))[:50]}' has high frequency. "
                         f"Refresh creatives or expand audience."
            })

    # 3. MoM ROAS drop > 25%
    if len(agg_account) >= 2:
        r_last = agg_account.iloc[-1]['ROAS']
        r_prev = agg_account.iloc[-2]['ROAS']
        if r_prev and (r_prev - r_last) / r_prev > 0.25:
            alerts.append({
                'level': 'critical',
                'title': f"ROAS dropped {((r_prev-r_last)/r_prev*100):.0f}% MoM",
                'body':  f"From {r_prev:.2f}x to {r_last:.2f}x. Check creative rotation, "
                         f"audience saturation and bid competition."
            })

    # 4. BOF underperforming
    if not agg_funnel.empty and 'Funnel' in agg_funnel.columns:
        bof = agg_funnel[agg_funnel['Funnel'].astype(str).str.upper().str.contains('BOF')]
        if not bof.empty:
            bof_roas = bof['Revenue'].sum() / bof['Spend'].sum() if bof['Spend'].sum() else 0
            if bof_roas < roas_be and bof['Spend'].sum() >= min_spend:
                alerts.append({
                    'level': 'warning',
                    'title': f"BOF ROAS at {bof_roas:.2f}x (below {roas_be}x)",
                    'body':  "Bottom-of-funnel is where purchase intent is highest. "
                             "Check DPA catalogue, audience overlaps, and bid strategy."
                })

    # 5. Zero purchases with spend
    zero_p = df_c_filt[(df_c_filt['Purchases'] == 0) &
                       (df_c_filt['Amount spent (INR)'] >= min_spend)]
    if not zero_p.empty:
        total_zero_spend = zero_p['Amount spent (INR)'].sum()
        alerts.append({
            'level': 'warning',
            'title': f"INR {total_zero_spend:,.0f} spent with zero purchases",
            'body':  f"{len(zero_p)} ad(s) generated no purchases. "
                     "Review pixel events, landing page, and audience targeting."
        })

    # 6. Good news: a scaling opportunity
    if not agg_cat.empty:
        best = agg_cat.loc[agg_cat['ROAS'].idxmax()]
        if best['ROAS'] >= roas_be * 1.1 and best['Spend'] >= min_spend:
            alerts.append({
                'level': 'good',
                'title': f"Scale opportunity: {best.get('Category', best.get('Format',''))}",
                'body':  f"ROAS {best['ROAS']:.2f}x on INR {best['Spend']:,.0f} spend. "
                         f"Strong performer — consider increasing budget 20-30%."
            })

    return alerts[:6]  # top 6 max


# ─── chart helpers ────────────────────────────────────────────────────────────
def roas_color_scale():
    return [
        [0,   '#C00000'], [0.36, '#ED7D31'],
        [0.55,'#FFD700'], [0.75, '#70AD47'],
        [1,   '#276221']
    ]

def bar_line_chart(agg, x_col, bar_col, line_col, bar_name, line_name,
                   bar_color='#2E75B6', line_color='#ED7D31', roas_be=5.5):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=agg[x_col], y=agg[bar_col], name=bar_name,
        marker_color=bar_color, opacity=0.85
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=agg[x_col], y=agg[line_col], name=line_name,
        line=dict(color=line_color, width=3),
        mode='lines+markers+text',
        text=[_fmt_num(v)+'x' for v in agg[line_col]],
        textposition='top center', textfont=dict(size=10)
    ), secondary_y=True)
    fig.add_hline(y=roas_be, line_dash='dash', line_color='red',
                  annotation_text=f"Break-even {roas_be}x",
                  secondary_y=True)
    fig.update_layout(
        height=340, margin=dict(t=20,b=20,l=10,r=10),
        legend=dict(orientation='h', y=1.05),
        plot_bgcolor='#FAFAFA', paper_bgcolor='white',
        font=dict(family='Arial', size=11),
    )
    fig.update_yaxes(title_text=f"{bar_name} (INR)", secondary_y=False)
    fig.update_yaxes(title_text=line_name, secondary_y=True)
    return fig

def funnel_html(agg, agg_comp=None, comp_label=''):
    """HTML funnel — handles extreme scale (20M→383) by using log-scale bar widths.
    Pass agg_comp + comp_label to show period-over-period delta badges next to each stage."""
    import math
    impressions = int(agg['Impressions'].sum())
    clicks      = int(agg['Clicks'].sum())
    lpv         = int(agg['LPV'].sum()) if 'LPV' in agg.columns else 0
    atc         = int(agg['ATC'].sum())
    ic          = int(agg['IC'].sum())
    purchases   = int(agg['Purchases'].sum())

    # comparison totals
    has_comp = agg_comp is not None and not (hasattr(agg_comp, 'empty') and agg_comp.empty)
    if has_comp:
        p_impr = int(agg_comp['Impressions'].sum()) if 'Impressions' in agg_comp.columns else 0
        p_clks = int(agg_comp['Clicks'].sum())      if 'Clicks'      in agg_comp.columns else 0
        p_lpv  = int(agg_comp['LPV'].sum())         if 'LPV'         in agg_comp.columns else 0
        p_atc  = int(agg_comp['ATC'].sum())         if 'ATC'         in agg_comp.columns else 0
        p_ic   = int(agg_comp['IC'].sum())           if 'IC'          in agg_comp.columns else 0
        p_pur  = int(agg_comp['Purchases'].sum())   if 'Purchases'   in agg_comp.columns else 0
    else:
        p_impr = p_clks = p_lpv = p_atc = p_ic = p_pur = 0

    def pct(a, b): return b / a * 100 if a else 0
    def fmt_n(v):
        if v >= 1_000_000: return f"{v/1_000_000:.2f}M"
        if v >= 1_000:     return f"{v/1_000:.1f}K"
        return str(v)
    def delta_badge(curr, prev):
        """Return HTML badge showing % change vs comparison period."""
        if not has_comp or prev == 0: return ''
        d = (curr - prev) / prev * 100
        arrow = '▲' if d >= 0 else '▼'
        clr = '#276221' if d >= 0 else '#C00000'
        return (f'<span style="background:{clr};color:white;border-radius:3px;'
                f'padding:1px 5px;font-size:9px;font-weight:700;margin-left:6px;">'
                f'{arrow}{abs(d):.0f}%</span>')

    ctr   = pct(impressions, clicks)
    lpv_r = pct(clicks, lpv)
    atc_r = pct(clicks, atc)
    ic_r  = pct(atc, ic)
    cvr   = pct(ic, purchases)
    e2e   = pct(impressions, purchases)

    def log_w(v):
        if v <= 0: return 3
        return max(5, min(100, math.log10(max(v,1)) / math.log10(max(impressions,1)) * 100))

    stages = [
        ('Impressions',       impressions, '#1A3C5E', None,   None,  p_impr),
        ('Clicks',            clicks,      '#2E75B6', ctr,    f'{ctr:.2f}% CTR (of Impressions)', p_clks),
    ]
    if lpv > 0:
        stages.append(('Landing Page Views', lpv, '#3A85C6', lpv_r, f'{lpv_r:.1f}% of Clicks', p_lpv))
    stages += [
        ('Add to Cart',       atc,         '#4A90D9', atc_r,  f'{atc_r:.1f}% of Clicks',           p_atc),
        ('Checkout Started',  ic,          '#70AD47', ic_r,   f'{ic_r:.1f}% of Add-to-Cart',        p_ic),
        ('Purchases',         purchases,   '#276221', cvr,    f'{cvr:.1f}% of Checkout Started',    p_pur),
    ]

    rows = ""
    for i, stage_data in enumerate(stages):
        name, val, bg, rate, rate_lbl = stage_data[:5]
        prev_val = stage_data[5] if len(stage_data) > 5 else 0
        w = log_w(val)
        badge = delta_badge(val, prev_val)
        # rate arrow (shows conversion drop between stages)
        arrow_html = ""
        if rate is not None:
            c = '#276221' if rate >= 10 else ('#ED7D31' if rate >= 2 else '#C00000')
            arrow_html = f'<div style="text-align:center;font-size:10px;color:{c};font-weight:700;margin:1px 0;">&#9660; {rate_lbl}</div>'
        # Bar shows: formatted count (short) + comparison badge inside/after the bar
        # No separate right-side raw count column — avoids overflow for large numbers
        bar_inner = (
            f'<span style="color:white;font-weight:800;font-size:12px;white-space:nowrap;">{fmt_n(val)}</span>'
        )
        # badge shown in a fixed-width column that never overflows
        badge_col = (f'<div style="width:52px;flex-shrink:0;text-align:left;padding-left:4px;">{badge}</div>'
                     if badge else '<div style="width:52px;flex-shrink:0;"></div>')
        rows += (arrow_html
            + f'<div style="display:flex;align-items:center;gap:6px;margin:3px 0;">'
            + f'<div style="width:130px;font-size:11px;font-weight:600;color:#333;text-align:right;flex-shrink:0;">{name}</div>'
            + f'<div style="flex:1;background:#E8E8E8;border-radius:5px;height:28px;min-width:0;">'
            + f'<div style="background:{bg};width:{w:.0f}%;height:100%;border-radius:5px;display:flex;align-items:center;padding:0 8px;min-width:44px;">'
            + bar_inner
            + f'</div></div>'
            + badge_col
            + f'</div>')

    comp_footer = ''
    if has_comp and comp_label:
        p_e2e = pct(p_impr, p_pur)
        e2e_d = (e2e - p_e2e) / p_e2e * 100 if p_e2e else 0
        e2e_arrow = '▲' if e2e_d >= 0 else '▼'
        e2e_clr = '#276221' if e2e_d >= 0 else '#C00000'
        comp_footer = (f' <span style="color:{e2e_clr};font-size:10px;">'
                       f'({e2e_arrow}{abs(e2e_d):.0f}% vs {comp_label})</span>')

    html = (
        '<div style="background:#FAFAFA;border-radius:10px;padding:14px 12px;font-family:Roboto,sans-serif;">'
        + rows
        + '<div style="margin-top:10px;padding-top:8px;border-top:1px dashed #CCC;font-size:11px;color:#555;text-align:center;">'
        + f'End-to-end: <b>{e2e:.4f}%</b> of impressions became purchases{comp_footer}'
        + '</div></div>'
    )
    return html

def _with_comp_roas(df, comp_df, key_cols):
    """Merge comparison ROAS onto df; returns df with ROAS_prev column."""
    if comp_df.empty:
        return df.copy()
    sub = comp_df.dropna(subset=key_cols)[key_cols + ['ROAS']].rename(columns={'ROAS': 'ROAS_prev'})
    return df.merge(sub, on=key_cols, how='left')

def _bar_text_with_comp(df, comp_df, key_col):
    """Return (clean_df, labels) — labels are compact single-line 'X.Xx ▲N%' strings.
    clean_df has ROAS_prev stripped so it never leaks into plotly tooltips."""
    df2 = _with_comp_roas(df.dropna(subset=[key_col]).copy(), comp_df, [key_col])
    labels = []
    for _, r in df2.iterrows():
        curr = r['ROAS']
        prev = r.get('ROAS_prev', float('nan'))
        if pd.notna(prev) and prev > 0:
            pct = (curr - prev) / prev * 100
            arrow = '▲' if pct >= 0 else '▼'
            labels.append(f"{curr:.2f}x {arrow}{abs(pct):.0f}%")
        else:
            labels.append(f"{curr:.2f}x")
    # drop internal merge column so it never shows in plotly hover
    clean = df2.drop(columns=[c for c in ['ROAS_prev'] if c in df2.columns])
    return clean, labels

def _roas_color(roas_val, roas_be):
    """Return (solid_color, light_color) based on ROAS vs break-even."""
    try: v = float(roas_val)
    except: v = 0
    if v >= roas_be * 1.1: return '#276221', 'rgba(39,98,33,0.25)'
    if v >= roas_be:        return '#70AD47', 'rgba(112,173,71,0.25)'
    if v >= 4.0:            return '#FFC000', 'rgba(255,192,0,0.25)'
    if v >= 2.0:            return '#ED7D31', 'rgba(237,125,49,0.25)'
    return '#C00000', 'rgba(192,0,0,0.25)'

def _grouped_spend_bar(curr_df, comp_df, x_col, title, height, roas_be,
                       curr_label='Current', comp_label='Previous'):
    """Grouped bar chart: current spend (ROAS-coloured) + comparison spend (lighter shade).
    Labels above current bars show ROAS + Δ%; comparison bars show prev ROAS.
    Returns a go.Figure."""
    curr_df = curr_df.dropna(subset=[x_col]).copy()
    categories = curr_df[x_col].tolist()

    curr_colors = [_roas_color(r, roas_be)[0] for r in curr_df['ROAS']]
    comp_colors = [_roas_color(r, roas_be)[1] for r in curr_df['ROAS']]  # light shade of same color

    # current bar labels: "3.21x ▲8%"
    curr_labels = []
    comp_spends = []
    comp_roas_list = []
    comp_labels_list = []
    for _, row in curr_df.iterrows():
        cat = row[x_col]
        croas = row['ROAS']
        prev_row = pd.Series()
        if not (hasattr(comp_df, 'empty') and comp_df.empty) and comp_df is not None and len(comp_df):
            match = comp_df[comp_df[x_col] == cat]
            if not match.empty:
                prev_row = match.iloc[0]
        if not prev_row.empty and prev_row.get('ROAS', 0) > 0:
            proas = prev_row['ROAS']
            pct = (croas - proas) / proas * 100
            arrow = '▲' if pct >= 0 else '▼'
            curr_labels.append(f"{croas:.2f}x {arrow}{abs(pct):.0f}%")
            comp_spends.append(float(prev_row.get('Spend', 0)))
            comp_roas_list.append(proas)
            comp_labels_list.append(f"{proas:.2f}x")
        else:
            curr_labels.append(f"{croas:.2f}x")
            comp_spends.append(0)
            comp_roas_list.append(0)
            comp_labels_list.append('')

    fig = go.Figure()
    # current bars
    fig.add_trace(go.Bar(
        name=curr_label,
        x=categories,
        y=curr_df['Spend'].tolist(),
        marker_color=curr_colors,
        text=curr_labels,
        textposition='auto',          # 'auto' places text inside if bar is tall enough, else outside
        textfont=dict(size=10, family='Arial', color='white'),
        insidetextanchor='middle',
        hovertemplate='<b>%{x}</b><br>Spend: ₹%{y:,.0f}<br>%{text}<extra></extra>',
    ))
    # comparison bars (only if we have comparison data)
    has_any_comp = any(s > 0 for s in comp_spends)
    if has_any_comp:
        comp_bar_colors = [_roas_color(r, roas_be)[1] for r in comp_roas_list]
        fig.add_trace(go.Bar(
            name=comp_label,
            x=categories,
            y=comp_spends,
            marker_color=comp_bar_colors,
            marker_line_color=[_roas_color(r, roas_be)[0] for r in comp_roas_list],
            marker_line_width=1.5,
            text=comp_labels_list,
            textposition='auto',
            textfont=dict(size=9, family='Arial', color='#333'),
            insidetextanchor='middle',
            hovertemplate='<b>%{x}</b> (prev)<br>Spend: ₹%{y:,.0f}<br>ROAS: %{text}<extra></extra>',
        ))
    fig.update_layout(
        title=title,
        height=height,
        barmode='group',
        bargap=0.2,
        bargroupgap=0.06,
        plot_bgcolor='#FAFAFA',
        paper_bgcolor='white',
        font=dict(family='Arial', size=11),
        margin=dict(t=50, b=50, l=10, r=10),
        legend=dict(orientation='h', y=1.1, x=0),
        yaxis=dict(title='Spend (₹)', automargin=True),
        xaxis=dict(automargin=True),
        uniformtext_minsize=8,
        uniformtext_mode='hide',   # hide text if bar too small, prevents overflow
        showlegend=has_any_comp,
    )
    return fig

def _roas_delta_col(curr_agg, comp_agg, key_cols):
    """Return a Series of formatted ROAS delta strings for display in tables."""
    if comp_agg.empty:
        return None
    merged = _with_comp_roas(curr_agg, comp_agg, key_cols)
    if 'ROAS_prev' not in merged.columns:
        return None
    def fmt(r):
        if pd.isna(r['ROAS_prev']) or r['ROAS_prev'] == 0:
            return '–'
        d = (r['ROAS'] - r['ROAS_prev']) / r['ROAS_prev'] * 100
        sign = '+' if d >= 0 else ''
        return f"{sign}{d:.1f}%"
    return merged.apply(fmt, axis=1)

def roas_color_row(val, roas_be):
    try:
        v = float(val)
        if np.isnan(v): return None
        if v >= roas_be * 1.1: return '#E2EFDA'
        if v >= roas_be:       return '#D6F0D6'
        if v >= 4.0:           return '#FFF2CC'
        if v >= 2.0:           return '#FCE4D6'
        return '#FFE2E2'
    except: return None

def interactive_table(df_display, roas_col='ROAS', roas_be=5.5):
    """Render dataframe with colour-coded ROAS and correct number formatting."""
    disp = df_display.copy()
    # apply formatters by column name
    fmt_map = {
        'Spend':   _fmt_inr, 'Revenue': _fmt_inr, 'CPA': _fmt_inr,
        'ROAS':    _fmt_num, 'ATC_Rate':_fmt_num, 'IC_Rate':_fmt_num, 'Frequency':_fmt_num, 'CPM':_fmt_num,
        'CTR':     _fmt_pct, 'CVR':     _fmt_pct,
        'Purchases':_fmt_int, 'ATC':    _fmt_int, 'IC': _fmt_int, 'Impressions': _fmt_int, 'Clicks': _fmt_int,
    }
    for col, fn in fmt_map.items():
        if col in disp.columns:
            disp[col] = disp[col].apply(fn)

    def highlight_roas(row):
        styles = [''] * len(row)
        if roas_col in row.index:
            raw_val = df_display.loc[row.name, roas_col] if row.name in df_display.index else None
            bg = roas_color_row(raw_val, roas_be)
            if bg:
                idx = list(row.index).index(roas_col)
                styles[idx] = f'background-color: {bg}'
        return styles

    styled = disp.style.apply(highlight_roas, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)

def adset_insights(df, roas_be, min_spend, comp_df=None, comp_label=''):
    """Return list of insight strings for an adset-level dataframe.
    When comp_df + comp_label are provided, insights focus on period-over-period changes
    (biggest improvers, biggest decliners, spend shifts) instead of just absolute performance."""
    insights = []
    df = df.copy()
    df['Spend']  = pd.to_numeric(df['Spend'],  errors='coerce').fillna(0)
    df['ROAS']   = pd.to_numeric(df['ROAS'],   errors='coerce')
    df['Revenue']= pd.to_numeric(df['Revenue'],errors='coerce').fillna(0)

    # figure out the name column — try all possible entity identifier columns
    def _name(row):
        for col in ('Ad set name', 'Influencer', 'Category', 'Format', 'Type', 'Platform', 'Gender'):
            if col in row.index and pd.notna(row[col]):
                return str(row[col])
        return '(unknown)'

    has_comp = comp_df is not None and not (hasattr(comp_df, 'empty') and comp_df.empty) and comp_label

    if has_comp:
        # ── Comparison-mode insights ────────────────────────────────────────
        comp_df = comp_df.copy()
        comp_df['Spend']   = pd.to_numeric(comp_df.get('Spend',  pd.Series(dtype=float)), errors='coerce').fillna(0)
        comp_df['ROAS']    = pd.to_numeric(comp_df.get('ROAS',   pd.Series(dtype=float)), errors='coerce')
        comp_df['Revenue'] = pd.to_numeric(comp_df.get('Revenue',pd.Series(dtype=float)), errors='coerce').fillna(0)

        # overall period summary
        curr_roas = df['Revenue'].sum() / df['Spend'].sum() if df['Spend'].sum() else 0
        prev_roas = comp_df['Revenue'].sum() / comp_df['Spend'].sum() if comp_df['Spend'].sum() else 0
        curr_spd  = df['Spend'].sum(); prev_spd = comp_df['Spend'].sum()
        if prev_roas:
            roas_d = (curr_roas - prev_roas) / prev_roas * 100
            arrow = '▲' if roas_d >= 0 else '▼'
            tone  = 'improved' if roas_d >= 0 else 'declined'
            insights.append(f"Overall ROAS {tone} **{arrow}{abs(roas_d):.1f}%** vs {comp_label} "
                            f"({prev_roas:.2f}x → {curr_roas:.2f}x).")
        if prev_spd:
            spd_d = (curr_spd - prev_spd) / prev_spd * 100
            insights.append(f"Spend {'up' if spd_d >= 0 else 'down'} **{abs(spd_d):.1f}%** vs {comp_label} "
                            f"(₹{prev_spd:,.0f} → ₹{curr_spd:,.0f}).")

        # find a shared key column for merging
        shared_keys = [c for c in ('Ad set name','Influencer','Category','Format','Type','Gender','Platform')
                       if c in df.columns and c in comp_df.columns]
        if shared_keys:
            key = shared_keys[0]
            keep_cols = [c for c in [key, 'ROAS', 'Spend', 'Revenue'] if c in df.columns]
            comp_keep = [c for c in [key, 'ROAS', 'Spend'] if c in comp_df.columns]
            merged = df[keep_cols].merge(
                comp_df[comp_keep].rename(columns={'ROAS': 'ROAS_prev', 'Spend': 'Spend_prev'}),
                on=key, how='inner'
            )
            # in comparison mode don't filter by min_spend — even small-spend entities matter for trend
            merged = merged[merged['ROAS_prev'] > 0].copy()
            if not merged.empty:
                merged['ROAS_delta'] = (merged['ROAS'] - merged['ROAS_prev']) / merged['ROAS_prev'] * 100
                top3 = merged.nlargest(min(3, len(merged)), 'ROAS_delta')
                bot3 = merged.nsmallest(min(3, len(merged)), 'ROAS_delta')
                improvers = [f"**{r[key]}** ({r['ROAS_prev']:.1f}x→{r['ROAS']:.1f}x, ▲{r['ROAS_delta']:.0f}%)"
                             for _, r in top3.iterrows() if r['ROAS_delta'] > 5]
                decliners = [f"**{r[key]}** ({r['ROAS_prev']:.1f}x→{r['ROAS']:.1f}x, ▼{abs(r['ROAS_delta']):.0f}%)"
                             for _, r in bot3.iterrows() if r['ROAS_delta'] < -5]
                if improvers:
                    insights.append(f"📈 Most improved vs {comp_label}: {', '.join(improvers)}.")
                if decliners:
                    insights.append(f"📉 Biggest declines vs {comp_label}: {', '.join(decliners)} — investigate creative fatigue or audience overlap.")
                else:
                    insights.append(f"No significant ROAS declines vs {comp_label} — stable performance across {key.lower()}s.")
                # spend reallocation check (only for entities with meaningful spend)
                spend_shift = merged[merged['Spend'] >= min_spend].nlargest(2, 'Spend')
                for _, r in spend_shift.iterrows():
                    if r['ROAS'] < roas_be and r.get('Spend_prev', 0) > 0:
                        spd_d = (r['Spend'] - r['Spend_prev']) / r['Spend_prev'] * 100
                        if spd_d > 20:
                            insights.append(f"⚠️ **{r[key]}** received {spd_d:.0f}% more spend but ROAS is only {r['ROAS']:.2f}x — consider reversing this allocation.")
        else:
            insights.append(f"No matching entities found between current and comparison periods for detailed comparison.")
    else:
        # ── Current-period-only insights ────────────────────────────────────
        total = len(df); above = (df['ROAS'] >= roas_be).sum()
        insights.append(f"**{above} of {total}** ad sets are at or above the {roas_be}x break-even ROAS.")

        sig = df[df['Spend'] >= min_spend]
        if not sig.empty:
            best = sig.loc[sig['ROAS'].idxmax()] if not sig['ROAS'].isna().all() else None
            worst= sig.loc[sig['ROAS'].idxmin()] if not sig['ROAS'].isna().all() else None
            if best is not None:
                insights.append(f"Best performer (≥INR {min_spend:,} spend): **{_name(best)}** at **{best['ROAS']:.2f}x** ROAS.")
            if worst is not None and worst['ROAS'] < roas_be:
                insights.append(f"Highest-spend underperformer: **{_name(worst)}** at **{worst['ROAS']:.2f}x** ROAS on INR {worst['Spend']:,.0f} spend — review or pause.")

        zero_p = df[(df['ROAS'].isna() | (df['ROAS'] == 0)) & (df['Spend'] >= min_spend)]
        if not zero_p.empty:
            insights.append(f"⚠️ **{len(zero_p)} ad set(s)** spent ≥INR {min_spend:,} with zero/no attributed purchases — check pixel and attribution window.")

        waste = df[df['ROAS'] < 2.0]['Spend'].sum()
        if waste > 0:
            insights.append(f"INR **{waste:,.0f}** total spend in ad sets below 2x ROAS — these are destroying margin.")

        if 'Funnel' in df.columns:
            funnel_g = df.groupby('Funnel').agg(Spend=('Spend','sum'), Revenue=('Revenue','sum')).reset_index()
            funnel_g['ROAS'] = funnel_g['Revenue'] / funnel_g['Spend'].replace(0, np.nan)
            for _, r in funnel_g.iterrows():
                if not np.isnan(r['ROAS']) and r['ROAS'] >= roas_be * 1.1 and r['Spend'] >= min_spend:
                    insights.append(f"✅ **{r['Funnel']}** is your strongest funnel at **{r['ROAS']:.2f}x** — consider allocating more budget here.")
    return insights

def heatmap_chart(pivot_df, title, colorscale='Blues', fmt='.2f'):
    fig = px.imshow(
        pivot_df, text_auto=fmt, aspect='auto',
        color_continuous_scale=colorscale, title=title,
    )
    fig.update_layout(
        height=max(250, len(pivot_df)*45+80),
        margin=dict(t=40,b=10,l=10,r=10),
        font=dict(family='Arial', size=10),
        coloraxis_showscale=False,
    )
    return fig

def colored_table(df, roas_col='ROAS', roas_be=5.5):
    """Return a styled plotly table."""
    cols = list(df.columns)
    cell_vals = [df[c].tolist() for c in cols]

    # color ROAS column
    fill_colors = []
    for c in cols:
        if c == roas_col:
            colors = []
            for v in df[c]:
                try:
                    vf = float(v)
                    if vf >= roas_be*1.1: colors.append('#E2EFDA')
                    elif vf >= roas_be:   colors.append('#D6F0D6')
                    elif vf >= 4.0:       colors.append('#FFF2CC')
                    elif vf >= 2.0:       colors.append('#FCE4D6')
                    else:                 colors.append('#FFE2E2')
                except:
                    colors.append('#F2F2F2')
            fill_colors.append(colors)
        else:
            fill_colors.append(['white'] * len(df))

    fig = go.Figure(go.Table(
        header=dict(
            values=[f'<b>{c}</b>' for c in cols],
            fill_color='#1A3C5E', font=dict(color='white', size=10),
            align='center', height=28,
        ),
        cells=dict(
            values=cell_vals,
            fill_color=fill_colors,
            font=dict(color='#333', size=10),
            align=['left'] + ['center']*(len(cols)-1),
            height=24,
        ),
    ))
    fig.update_layout(margin=dict(t=0,b=0,l=0,r=0),
                      height=min(600, 40 + len(df)*26))
    return fig


# ─── comparison helpers ───────────────────────────────────────────────────────
def _comp_banner(df_curr, df_comp, comp_label):
    """Render a one-line period-over-period KPI strip. Call at the top of each tab."""
    if df_comp is None or df_comp.empty or not comp_label:
        return
    def _d(col):
        c = df_curr[col].sum() if col in df_curr.columns else 0
        p = df_comp[col].sum() if col in df_comp.columns else 0
        if not p: return None
        return (c - p) / p * 100

    metrics = [
        ("Spend",     _d('Amount spent (INR)'),            False),
        ("Revenue",   _d('Purchases conversion value'),    True),
        ("Purchases", _d('Purchases'),                     True),
        ("Impressions", _d('Impressions'),                 True),
    ]
    # add ROAS delta
    crev = df_curr['Purchases conversion value'].sum(); cspd = df_curr['Amount spent (INR)'].sum()
    prev = df_comp['Purchases conversion value'].sum(); pspd = df_comp['Amount spent (INR)'].sum()
    cr = crev/cspd if cspd else 0; pr = prev/pspd if pspd else 0
    if pr:
        metrics.insert(2, ("ROAS", (cr-pr)/pr*100, True))

    parts = []
    for name, val, good in metrics:
        if val is None: continue
        arrow = "▲" if val >= 0 else "▼"
        clr   = "#276221" if (val >= 0) == good else "#C00000"
        parts.append(f'<span style="color:{clr};font-weight:700;">{arrow}{abs(val):.1f}%</span> {name}')
    if parts:
        st.markdown(
            f'<div style="background:#F0F4F8;border-radius:8px;padding:8px 14px;margin-bottom:12px;'
            f'font-size:12px;color:#333;">📅 <b>vs {comp_label}</b> &nbsp;|&nbsp; '
            + ' &nbsp;|&nbsp; '.join(parts)
            + '</div>',
            unsafe_allow_html=True)


def _agg_with_comp_delta(curr_agg, comp_agg, key_cols, metric='ROAS'):
    """Merge comparison period metric onto current agg, return Δ% column."""
    if comp_agg is None or comp_agg.empty:
        return curr_agg.copy(), False
    valid_keys = [k for k in key_cols if k in curr_agg.columns and k in comp_agg.columns]
    if not valid_keys:
        return curr_agg.copy(), False
    comp_sub = comp_agg[valid_keys + [metric]].rename(columns={metric: f'{metric}_prev'})
    merged = curr_agg.merge(comp_sub, on=valid_keys, how='left')
    merged[f'{metric} Δ%'] = (
        (merged[metric] - merged[f'{metric}_prev']) /
        merged[f'{metric}_prev'].replace(0, np.nan) * 100
    ).round(1)
    return merged, True


# ─── what-if simulator ────────────────────────────────────────────────────────
def whatif_tab(df_c_filt, agg_fun_t, agg_cat, roas_be, min_spend):
    st.markdown('<div class="section-title">What-If Simulator</div>', unsafe_allow_html=True)

    if agg_fun_t.empty or agg_fun_t.dropna(subset=['Funnel']).empty:
        st.info("No funnel data available for selected filters.")
        return

    funnel_data = agg_fun_t.dropna(subset=['Funnel']).copy()
    total_current_spend = funnel_data['Spend'].sum()
    fl_bg = {'TOF':'#CBE3FF','MOF':'#CBFFAB','BOF':'#FECAFD'}

    # ── current allocation cards ──────────────────────────────────────────────
    st.markdown("#### Current Budget Allocation")
    alloc_cols = st.columns(len(funnel_data))
    for i, (_, row) in enumerate(funnel_data.iterrows()):
        share = row['Spend'] / total_current_spend * 100 if total_current_spend else 0
        bg = fl_bg.get(str(row['Funnel']),'#EEE')
        roas_v = row['ROAS'] if not (isinstance(row['ROAS'], float) and np.isnan(row['ROAS'])) else 0
        alloc_cols[i].markdown(
            f'<div style="background:{bg};border-radius:10px;padding:12px;text-align:center;margin-bottom:8px;">'
            f'<div style="font-size:11px;font-weight:700;color:#1A3C5E;text-transform:uppercase;">{row["Funnel"]}</div>'
            f'<div style="font-size:20px;font-weight:900;color:#1A3C5E;margin:4px 0;">&#8377;{row["Spend"]:,.0f}</div>'
            f'<div style="font-size:12px;color:#555;">{share:.1f}% of budget</div>'
            f'<div style="font-size:11px;color:#1A3C5E;font-weight:600;">{roas_v:.2f}x ROAS</div>'
            f'</div>', unsafe_allow_html=True)

    # ── two simulators in one section via internal tabs ───────────────────────
    sim_tabs = st.tabs(["Spend Simulator", "ROAS Target Simulator"])

    # ── TAB A: Spend Adjustment ───────────────────────────────────────────────
    with sim_tabs[0]:
        st.caption("Adjust spend per funnel level. Projected revenue is based on each funnel's historical ROAS.")
        col_sim, col_res = st.columns([1, 1])
        with col_sim:
            st.markdown("**Adjust Spend by Funnel (%)**")
            adjustments = {}
            for _, row in funnel_data.iterrows():
                f = str(row['Funnel'])
                roas_v = row['ROAS'] if not (isinstance(row['ROAS'], float) and np.isnan(row['ROAS'])) else 0
                pct = st.slider(
                    f"{f}  (ROAS {roas_v:.2f}x | Spend ₹{row['Spend']:,.0f})",
                    min_value=-50, max_value=150, value=0, step=5,
                    key=f"spd_{f}", format="%d%%"
                )
                adjustments[f] = pct

        with col_res:
            st.markdown("**Projected Impact**")
            sim1_rows = []
            c_sp_vals, p_sp_vals = [], []
            t_curr_sp = t_proj_sp = t_curr_rv = t_proj_rv = 0.0
            for _, row in funnel_data.iterrows():
                f = str(row['Funnel'])
                pct_adj = adjustments.get(f, 0)
                roas_v = row['ROAS'] if not (isinstance(row['ROAS'], float) and np.isnan(row['ROAS'])) else 0
                c_sp = float(row['Spend']); p_sp = c_sp * (1 + pct_adj / 100)
                c_rv = float(row['Revenue']); p_rv = p_sp * roas_v
                t_curr_sp += c_sp; t_proj_sp += p_sp
                t_curr_rv += c_rv; t_proj_rv += p_rv
                c_sp_vals.append(c_sp); p_sp_vals.append(p_sp)
                sim1_rows.append({
                    'Funnel': f, 'Adj': f"{pct_adj:+d}%",
                    'Curr Spend': f"₹{c_sp:,.0f}", 'New Spend': f"₹{p_sp:,.0f}",
                    'Curr Rev': f"₹{c_rv:,.0f}", 'Proj Rev': f"₹{p_rv:,.0f}",
                    'Rev Delta': f"{'+'if p_rv>=c_rv else''}₹{p_rv-c_rv:,.0f}"
                })
            st.dataframe(pd.DataFrame(sim1_rows), use_container_width=True, hide_index=True)

            new_roas1 = t_proj_rv / t_proj_sp if t_proj_sp else 0
            spend_d = t_proj_sp - t_curr_sp
            rev_d   = t_proj_rv - t_curr_rv
            rcc = '#276221' if new_roas1 >= roas_be else '#C00000'
            r1, r2, r3 = st.columns(3)
            r1.markdown(
                f'<div class="sim-card"><div class="sc-label">Total Spend</div>'
                f'<div class="sc-value">&#8377;{t_proj_sp:,.0f}</div>'
                f'<div class="sc-delta" style="color:{"#C00000" if spend_d>0 else "#276221"};">'
                f'{"+"if spend_d>=0 else""}&#8377;{spend_d:,.0f}</div></div>', unsafe_allow_html=True)
            r2.markdown(
                f'<div class="sim-card"><div class="sc-label">Projected Revenue</div>'
                f'<div class="sc-value">&#8377;{t_proj_rv:,.0f}</div>'
                f'<div class="sc-delta" style="color:{"#276221" if rev_d>=0 else "#C00000"};">'
                f'{"+"if rev_d>=0 else""}&#8377;{rev_d:,.0f}</div></div>', unsafe_allow_html=True)
            r3.markdown(
                f'<div class="sim-card"><div class="sc-label">Projected ROAS</div>'
                f'<div class="sc-value" style="color:{rcc};">{new_roas1:.2f}x</div>'
                f'<div class="sc-delta" style="color:{rcc};">Break-even: {roas_be}x</div></div>',
                unsafe_allow_html=True)

            fig1 = go.Figure()
            funnels_list = [r['Funnel'] for r in sim1_rows]
            fig1.add_trace(go.Bar(name='Current Spend', x=funnels_list, y=c_sp_vals,
                                  marker_color='#CBE3FF', marker_line_color='#2E75B6', marker_line_width=1))
            fig1.add_trace(go.Bar(name='Projected Spend', x=funnels_list, y=p_sp_vals,
                                  marker_color='#CBFFAB', marker_line_color='#70AD47', marker_line_width=1))
            fig1.update_layout(barmode='group', height=200, margin=dict(t=10,b=10,l=10,r=10),
                               legend=dict(orientation='h', y=1.1),
                               plot_bgcolor='#FAFAFA', paper_bgcolor='white',
                               font=dict(family='Roboto'), yaxis_title='Spend (₹)')
            st.plotly_chart(fig1, use_container_width=True)

    # ── TAB B: ROAS Target ────────────────────────────────────────────────────
    with sim_tabs[1]:
        st.caption("Set a target ROAS per funnel. See what revenue you need to hit it and how far you are today.")
        col_rt, col_rr = st.columns([1, 1])
        with col_rt:
            st.markdown("**Set Target ROAS by Funnel**")
            roas_targets = {}
            for _, row in funnel_data.iterrows():
                f = str(row['Funnel'])
                roas_v = row['ROAS'] if not (isinstance(row['ROAS'], float) and np.isnan(row['ROAS'])) else 0
                target = st.slider(
                    f"{f}  (current ROAS: {roas_v:.2f}x)",
                    min_value=0.5, max_value=15.0,
                    value=float(min(15.0, max(0.5, round(float(max(roas_be, roas_v)), 2)))),
                    step=0.25, key=f"roas_{f}", format="%.2fx"
                )
                roas_targets[f] = target

        with col_rr:
            st.markdown("**Revenue Needed & Gap**")
            sim2_rows = []
            c_rev_vals, needed_rev_vals = [], []
            t_curr_rev2 = t_needed_rev = 0.0
            for _, row in funnel_data.iterrows():
                f = str(row['Funnel'])
                target_roas = roas_targets.get(f, roas_be)
                c_sp = float(row['Spend'])
                c_rv = float(row['Revenue'])
                needed_rv = c_sp * target_roas
                gap = needed_rv - c_rv
                t_curr_rev2  += c_rv
                t_needed_rev += needed_rv
                c_rev_vals.append(c_rv); needed_rev_vals.append(needed_rv)
                sim2_rows.append({
                    'Funnel': f, 'Spend': f"₹{c_sp:,.0f}",
                    'Current Rev': f"₹{c_rv:,.0f}",
                    'Target ROAS': f"{target_roas:.2f}x",
                    'Revenue Needed': f"₹{needed_rv:,.0f}",
                    'Gap': f"{'+'if gap>=0 else''}₹{gap:,.0f}",
                    'Status': 'On track' if c_rv >= needed_rv else 'Needs improvement'
                })
            st.dataframe(pd.DataFrame(sim2_rows), use_container_width=True, hide_index=True)

            overall_gap = t_needed_rev - t_curr_rev2
            g1, g2, g3 = st.columns(3)
            g1.markdown(
                f'<div class="sim-card"><div class="sc-label">Current Revenue</div>'
                f'<div class="sc-value">&#8377;{t_curr_rev2:,.0f}</div>'
                f'<div class="sc-delta" style="color:#555;">across all funnels</div></div>',
                unsafe_allow_html=True)
            g2.markdown(
                f'<div class="sim-card"><div class="sc-label">Revenue Needed</div>'
                f'<div class="sc-value">&#8377;{t_needed_rev:,.0f}</div>'
                f'<div class="sc-delta" style="color:#555;">to hit target ROAS</div></div>',
                unsafe_allow_html=True)
            gc = '#C00000' if overall_gap > 0 else '#276221'
            g3.markdown(
                f'<div class="sim-card"><div class="sc-label">Revenue Gap</div>'
                f'<div class="sc-value" style="color:{gc};">{"+"if overall_gap>=0 else""}&#8377;{overall_gap:,.0f}</div>'
                f'<div class="sc-delta" style="color:{gc};">{"above" if overall_gap>=0 else "below"} target</div></div>',
                unsafe_allow_html=True)

            fig2 = go.Figure()
            funnels_list2 = [r['Funnel'] for r in sim2_rows]
            fig2.add_trace(go.Bar(name='Current Revenue', x=funnels_list2, y=c_rev_vals,
                                  marker_color='#CBE3FF', marker_line_color='#2E75B6', marker_line_width=1))
            fig2.add_trace(go.Bar(name='Revenue Needed', x=funnels_list2, y=needed_rev_vals,
                                  marker_color='#FECAFD', marker_line_color='#C070BF', marker_line_width=1))
            fig2.update_layout(barmode='group', height=200, margin=dict(t=10,b=10,l=10,r=10),
                               legend=dict(orientation='h', y=1.1),
                               plot_bgcolor='#FAFAFA', paper_bgcolor='white',
                               font=dict(family='Roboto'), yaxis_title='Revenue (₹)')
            st.plotly_chart(fig2, use_container_width=True)


# ─── main ─────────────────────────────────────────────────────────────────────
def main():
    # load
    df_c_raw, df_d_raw, df_p_raw = load_data()

    # sidebar
    sel_months, sel_idx, start, end, obj, roas_be, min_spend, comp_sel = sidebar(df_c_raw)

    # filter — selected period
    df_c, df_d, df_p = filter_df(df_c_raw, df_d_raw, df_p_raw, obj, start, end)

    # filter — comparison period
    comp_start, comp_end, comp_label = compute_comp_range(start, end, comp_sel)
    if comp_start is not None:
        df_c_comp, df_d_comp, df_p_comp = filter_df(df_c_raw, df_d_raw, df_p_raw, obj, comp_start, comp_end)
    else:
        df_c_comp = df_d_comp = df_p_comp = pd.DataFrame()

    # aggregates
    agg_acc   = dp._agg(df_c, ['Month','Month_Start']).sort_values('Month_Start')
    agg_fun   = dp._agg(df_c, ['Funnel','Month','Month_Start']).sort_values(['Funnel','Month_Start'])
    agg_fun_t = dp._agg(df_c, ['Funnel']).sort_values('Spend', ascending=False)
    agg_cat   = dp._agg(df_c, ['Category']).sort_values('Spend', ascending=False)
    agg_cat_m = dp._agg(df_c, ['Category','Month','Month_Start']).sort_values(['Category','Month_Start'])
    agg_fmt   = dp._agg(df_c, ['Format']).sort_values('Spend', ascending=False)
    agg_inf   = dp._agg(df_c, ['Is_Influencer'])
    inf_rows  = df_c[df_c['Is_Influencer'] == True]
    agg_per_inf = dp._agg(inf_rows, ['Influencer']).sort_values('Spend', ascending=False)
    agg_demo  = dp._agg(df_d, ['Gender','Age']).sort_values('Spend', ascending=False)
    agg_plat  = dp._agg(df_p, ['Platform','Placement']).sort_values('Spend', ascending=False)
    # agg_adset now built on-demand in the Funnel tab (filtered to spend>0)

    # ── comparison aggregates (same keys, comparison period) ─────────────────
    if not df_c_comp.empty:
        agg_acc_comp     = dp._agg(df_c_comp, ['Month','Month_Start']).sort_values('Month_Start')
        agg_fun_t_comp   = dp._agg(df_c_comp, ['Funnel'])
        agg_fun_comp     = dp._agg(df_c_comp, ['Funnel','Month','Month_Start']).sort_values(['Funnel','Month_Start'])
        agg_cat_comp     = dp._agg(df_c_comp, ['Category'])
        agg_fmt_comp     = dp._agg(df_c_comp, ['Format'])
        agg_inf_comp     = dp._agg(df_c_comp, ['Is_Influencer'])
        _inf_rows_comp   = df_c_comp[df_c_comp['Is_Influencer'] == True]
        agg_per_inf_comp = dp._agg(_inf_rows_comp, ['Influencer'])
        agg_demo_comp    = dp._agg(df_d_comp, ['Gender','Age']) if not df_d_comp.empty else pd.DataFrame()
        agg_plat_comp    = dp._agg(df_p_comp, ['Platform','Placement']) if not df_p_comp.empty else pd.DataFrame()
    else:
        agg_acc_comp = agg_fun_t_comp = agg_fun_comp = agg_cat_comp = agg_fmt_comp = \
        agg_inf_comp = agg_per_inf_comp = agg_demo_comp = agg_plat_comp = pd.DataFrame()

    # ── header ───────────────────────────────────────────────────────────────
    st.markdown("""
    <div style='background:linear-gradient(135deg,#1A3C5E,#2E75B6);
                border-radius:14px;padding:22px 28px;margin-bottom:20px;'>
      <h1 style='color:white;margin:0;font-size:26px;'>🧳 Nasher Miles — Meta Ads Intelligence</h1>
      <p style='color:#DEEAF1;margin:4px 0 0;font-size:13px;'>
        Dynamic performance dashboard powered by Claude AI
      </p>
    </div>
    """, unsafe_allow_html=True)

    period_str  = f"{sel_months[0]} – {sel_months[-1]}" if len(sel_months) > 1 else sel_months[0]
    st.caption(f"Period: **{period_str}** | Objective: **{obj}** | "
               f"Break-even ROAS: **{roas_be}x** | Min spend: **INR {min_spend:,}**")

    # ── tabs ─────────────────────────────────────────────────────────────────
    tabs = st.tabs([
        "📊 Overview",
        "🔽 Funnel & Ad Sets",
        "🎨 Creative",
        "👥 Demographics",
        "📱 Platform",
        "🧮 What-If Simulator",
    ])

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 1: OVERVIEW
    # ═══════════════════════════════════════════════════════════════════════════
    with tabs[0]:
        if df_c.empty:
            st.warning("No data for selected filters.")
            with st.expander("🔍 Debug info"):
                st.write(f"Raw rows loaded: {len(df_c_raw)}")
                st.write(f"Has Date col: {'Date' in df_c_raw.columns}")
                st.write(f"Has Month col: {'Month' in df_c_raw.columns}")
                if 'Month_Start' in df_c_raw.columns:
                    st.write(f"Month_Start non-null: {df_c_raw['Month_Start'].notna().sum()} / {len(df_c_raw)}")
                    st.write(f"Month_Start range: {df_c_raw['Month_Start'].min()} → {df_c_raw['Month_Start'].max()}")
                if 'Month' in df_c_raw.columns:
                    st.write(f"Sample Month values: {df_c_raw['Month'].dropna().unique()[:5].tolist()}")
                st.write(f"All columns: {df_c_raw.columns.tolist()}")
                st.write(f"Filter start: {start}, end: {end}")
                st.write(f"Objective filter: {obj}")
        else:
            total_spend  = df_c['Amount spent (INR)'].sum()
            total_rev    = df_c['Purchases conversion value'].sum()
            total_purch  = df_c['Purchases'].sum()
            total_impr   = df_c['Impressions'].sum()
            total_clicks = df_c['Link clicks'].sum()
            total_atc    = df_c['Adds to cart'].sum()
            overall_roas = total_rev / total_spend if total_spend else 0
            overall_cpa  = total_spend / total_purch if total_purch else 0
            overall_ctr  = total_clicks / total_impr * 100 if total_impr else 0
            overall_freq = df_c['Impressions'].sum() / df_c['Reach'].replace(0,np.nan).sum()

            # deltas vs comparison period
            def comp_delta(col_name):
                if df_c_comp.empty or col_name not in df_c_comp.columns:
                    return None
                c_val = df_c[col_name].sum() if col_name in df_c.columns else 0
                p_val = df_c_comp[col_name].sum()
                return (c_val - p_val) / p_val * 100 if p_val else None

            # ── AI narrative ────────────────────────────────────────────────
            narr = build_narrative(agg_acc, agg_fun_t, agg_cat, agg_fmt, agg_inf,
                                   agg_demo, agg_plat, sel_months, roas_be, df_c)
            if narr:
                (t_spend, t_rev, t_purch, t_atc, o_roas,
                 o_cpa, o_ctr, o_cvr, roas_col, roas_be_v,
                 best_m, trend_note) = narr['totals']

                worked_li  = "".join(f"<li>{w}</li>" for w in narr['worked'])
                didnt_li   = "".join(f"<li>{d}</li>" for d in narr['didnt'])
                changes_li = "".join(f"<li>{c}</li>" for c in narr['changes'])

                # ── period-over-period comparison note for narrative ─────────
                comp_note_html = ""
                if not df_c_comp.empty and comp_label:
                    comp_rev  = df_c_comp['Purchases conversion value'].sum()
                    comp_spd  = df_c_comp['Amount spent (INR)'].sum()
                    comp_pur  = df_c_comp['Purchases'].sum()
                    comp_roas_v = comp_rev / comp_spd if comp_spd else 0
                    d_spd  = (t_spend - comp_spd) / comp_spd * 100 if comp_spd else 0
                    d_rev  = (t_rev   - comp_rev)  / comp_rev  * 100 if comp_rev  else 0
                    d_pur  = (t_purch - comp_pur)  / comp_pur  * 100 if comp_pur  else 0
                    d_roas = (o_roas  - comp_roas_v) / comp_roas_v * 100 if comp_roas_v else 0

                    def _signed(v, good=True):
                        arrow = "▲" if v >= 0 else "▼"
                        clr   = "#276221" if (v >= 0) == good else "#C00000"
                        return f'<span style="color:{clr};font-weight:700;">{arrow} {abs(v):.1f}%</span>'

                    comp_note_html = (
                        f'<div class="nb-section">📅 vs {comp_label} ({comp_sel})</div>'
                        f'<p>Spend {_signed(d_spd, good=False)} &nbsp;|&nbsp; '
                        f'Revenue {_signed(d_rev, good=True)} &nbsp;|&nbsp; '
                        f'Purchases {_signed(d_pur, good=True)} &nbsp;|&nbsp; '
                        f'ROAS {_signed(d_roas, good=True)} '
                        f'(was <b>{comp_roas_v:.2f}x</b> → now <b>{o_roas:.2f}x</b>)</p>'
                    )

                st.markdown(f"""
                <div class="narrative-box">
                  <h4>🤖 AI Performance Story — {', '.join(sel_months)}</h4>

                  <div class="nb-section">📌 What Meta delivered</div>
                  <p>Spent <b>INR {t_spend:,.0f}</b> → generated <b>INR {t_rev:,.0f}</b> revenue
                  across <b>{t_purch:,} purchases</b> ({t_atc:,} add-to-carts).
                  Overall ROAS: <b style="color:{roas_col};">{o_roas:.2f}x</b>
                  ({'above' if o_roas >= roas_be_v else 'below'} {roas_be_v}x break-even).
                  Avg CPA: <b>INR {o_cpa:,.0f}</b>. CTR: <b>{o_ctr:.2f}%</b>.
                  Best month: <b>{best_m}</b>. {trend_note}</p>
                  {comp_note_html}

                  <div class="nb-section">✅ What worked</div>
                  <ul style="margin:4px 0 8px;padding-left:18px;font-size:13px;color:#333;line-height:1.7;">
                    {worked_li}
                  </ul>

                  <div class="nb-section">❌ What didn't work</div>
                  <ul style="margin:4px 0 8px;padding-left:18px;font-size:13px;color:#333;line-height:1.7;">
                    {didnt_li}
                  </ul>

                  <div class="nb-section">🔄 What we'll change</div>
                  <ul style="margin:4px 0 0;padding-left:18px;font-size:13px;color:#333;line-height:1.7;">
                    {changes_li}
                  </ul>
                </div>""", unsafe_allow_html=True)

            # ── KPI cards ───────────────────────────────────────────────────
            def _lakh(v):
                if v >= 1e7:  return f"₹{v/1e7:.1f}Cr"
                if v >= 1e5:  return f"₹{v/1e5:.1f}L"
                return f"₹{v:,.0f}"

            # ── comparison period caption ────────────────────────────────────
            if comp_label:
                st.caption(f"⟵ Arrows show change vs **{comp_label}** ({comp_sel})")

            # ── derived comparison-period deltas for derived metrics ─────────
            def _comp_roas_delta():
                if df_c_comp.empty: return None
                crev = df_c_comp['Purchases conversion value'].sum()
                cspd = df_c_comp['Amount spent (INR)'].sum()
                comp_roas = crev / cspd if cspd else 0
                return (overall_roas - comp_roas) / comp_roas * 100 if comp_roas else None

            def _comp_cpa_delta():
                if df_c_comp.empty: return None
                cpur = df_c_comp['Purchases'].sum()
                cspd = df_c_comp['Amount spent (INR)'].sum()
                comp_cpa = cspd / cpur if cpur else 0
                return (overall_cpa - comp_cpa) / comp_cpa * 100 if comp_cpa else None

            def _comp_ctr_delta():
                if df_c_comp.empty: return None
                cclk = df_c_comp['Link clicks'].sum()
                cimpr = df_c_comp['Impressions'].sum()
                comp_ctr = cclk / cimpr * 100 if cimpr else 0
                return (overall_ctr - comp_ctr) / comp_ctr * 100 if comp_ctr else None

            def _comp_freq_delta():
                if df_c_comp.empty: return None
                comp_freq = df_c_comp['Impressions'].sum() / df_c_comp['Reach'].replace(0, np.nan).sum()
                return (overall_freq - comp_freq) / comp_freq * 100 if comp_freq else None

            c1,c2,c3,c4,c5,c6,c7,c8 = st.columns(8)
            metric_card(c1, "Total Spend",   _lakh(total_spend),
                        comp_delta('Amount spent (INR)'), delta_good=False)
            metric_card(c2, "Revenue",        _lakh(total_rev),
                        comp_delta('Purchases conversion value'), delta_good=True)
            metric_card(c3, "Overall ROAS",  f"{overall_roas:.2f}x",
                        _comp_roas_delta(), delta_good=True)
            metric_card(c4, "Purchases",     f"{int(total_purch):,}",
                        comp_delta('Purchases'), delta_good=True)
            metric_card(c5, "Avg CPA",       f"₹{overall_cpa:,.0f}",
                        _comp_cpa_delta(), delta_good=False)
            metric_card(c6, "CTR",           f"{overall_ctr:.2f}%",
                        _comp_ctr_delta(), delta_good=True)
            metric_card(c7, "Frequency",     f"{overall_freq:.2f}x",
                        _comp_freq_delta(), delta_good=False)
            metric_card(c8, "Impressions",   f"{total_impr/1e6:.1f}M",
                        comp_delta('Impressions'), delta_good=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── anomaly alerts ──────────────────────────────────────────────
            alerts = detect_anomalies(df_c, agg_acc, agg_fun, agg_cat, roas_be, min_spend)
            if alerts:
                st.markdown('<div class="section-title">⚡ Smart Anomaly Callouts</div>',
                            unsafe_allow_html=True)
                a_cols = st.columns(min(len(alerts), 3))
                for i, alert in enumerate(alerts[:3]):
                    cls = f"alert-{alert['level']}"
                    icon = {'critical':'🔴','warning':'🟡','info':'🔵','good':'🟢'}.get(alert['level'],'⚪')
                    a_cols[i % 3].markdown(f"""
                    <div class="alert-card {cls}">
                      <div class="alert-title">{icon} {alert['title']}</div>
                      <div class="alert-body">{alert['body']}</div>
                    </div>""", unsafe_allow_html=True)
                if len(alerts) > 3:
                    a_cols2 = st.columns(min(len(alerts)-3, 3))
                    for i, alert in enumerate(alerts[3:]):
                        cls = f"alert-{alert['level']}"
                        icon = {'critical':'🔴','warning':'🟡','info':'🔵','good':'🟢'}.get(alert['level'],'⚪')
                        a_cols2[i % 3].markdown(f"""
                        <div class="alert-card {cls}">
                          <div class="alert-title">{icon} {alert['title']}</div>
                          <div class="alert-body">{alert['body']}</div>
                        </div>""", unsafe_allow_html=True)

            # ── charts ──────────────────────────────────────────────────────
            ch1, ch2 = st.columns([2, 1])
            with ch1:
                st.markdown("**Monthly Spend vs ROAS**"
                            + (f" *(vs {comp_label})*" if comp_label else ""))
                if not agg_acc.empty:
                    agg_acc_plot = agg_acc.copy()
                    agg_acc_plot['Month_Label'] = pd.to_datetime(agg_acc_plot['Month_Start']).dt.strftime('%b-%Y')
                    agg_acc_plot = agg_acc_plot.sort_values('Month_Start')
                    fig = bar_line_chart(agg_acc_plot, 'Month_Label',
                                        'Spend', 'ROAS', 'Spend (INR)', 'ROAS',
                                        roas_be=roas_be)

                    # overlay comparison period spend as a translucent bar
                    if not df_c_comp.empty:
                        agg_comp = dp._agg(df_c_comp, ['Month','Month_Start']).sort_values('Month_Start')
                        if not agg_comp.empty:
                            agg_comp['Month_Label'] = pd.to_datetime(agg_comp['Month_Start']).dt.strftime('%b-%Y')
                            fig.add_trace(go.Bar(
                                x=agg_comp['Month_Label'],
                                y=agg_comp['Spend'],
                                name=f'Spend ({comp_label})',
                                marker_color='#A8C4D8',
                                opacity=0.5,
                            ), secondary_y=False)
                            fig.add_trace(go.Scatter(
                                x=agg_comp['Month_Label'],
                                y=agg_comp['ROAS'],
                                name=f'ROAS ({comp_label})',
                                line=dict(color='#70AD47', width=2, dash='dot'),
                                mode='lines+markers',
                            ), secondary_y=True)
                            fig.update_layout(legend=dict(orientation='h', y=1.10))

                    st.plotly_chart(fig, use_container_width=True)

            with ch2:
                st.markdown("**Conversion Funnel**")
                if not agg_acc.empty:
                    components.html(
                        funnel_html(
                            agg_acc,
                            agg_comp=agg_acc_comp if not agg_acc_comp.empty else None,
                            comp_label=comp_label,
                        ),
                        height=340, scrolling=False)

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 2: FUNNEL & AD SETS
    # ═══════════════════════════════════════════════════════════════════════════
    with tabs[1]:
        if df_c.empty:
            st.warning("No data."); return

        _comp_banner(df_c, df_c_comp, comp_label)

        st.markdown('<div class="section-title">Funnel Performance</div>',
                    unsafe_allow_html=True)
        f1, f2 = st.columns([1, 1])

        with f1:
            # funnel grouped spend bar — current vs comparison
            if not agg_fun_t.empty:
                _comp_label_str = comp_label if comp_label else 'Previous'
                fig = _grouped_spend_bar(
                    curr_df=agg_fun_t.dropna(subset=['Funnel']),
                    comp_df=agg_fun_t_comp if not agg_fun_t_comp.empty else None,
                    x_col='Funnel',
                    title='Spend by Funnel — Current vs Comparison',
                    height=320,
                    roas_be=roas_be,
                    curr_label='Current period',
                    comp_label=_comp_label_str,
                )
                st.plotly_chart(fig, use_container_width=True)

        with f2:
            # funnel monthly ROAS — correct chronological ordering
            if not agg_fun.empty:
                agg_fun_plot = agg_fun.dropna(subset=['Funnel']).copy()
                agg_fun_plot['Month_Label'] = pd.to_datetime(agg_fun_plot['Month_Start']).dt.strftime('%b-%Y')
                agg_fun_plot = agg_fun_plot.sort_values(['Month_Start','Funnel'])
                month_order  = agg_fun_plot.sort_values('Month_Start')['Month_Label'].unique().tolist()

                fig = px.line(
                    agg_fun_plot, x='Month_Label', y='ROAS', color='Funnel',
                    markers=True, title='Monthly ROAS by Funnel'
                             + (f' (dotted = {comp_label})' if comp_label and not agg_fun_comp.empty else ''),
                    color_discrete_sequence=['#1A3C5E','#2E75B6','#70AD47'],
                    height=300,
                    category_orders={'Month_Label': month_order},
                )
                fig.add_hline(y=roas_be, line_dash='dash', line_color='red',
                              annotation_text=f"Break-even {roas_be}x",
                              annotation_position="bottom right")
                # add ROAS value labels on each point
                for funnel_val in agg_fun_plot['Funnel'].unique():
                    sub = agg_fun_plot[agg_fun_plot['Funnel'] == funnel_val]
                    fig.add_trace(go.Scatter(
                        x=sub['Month_Label'], y=sub['ROAS'],
                        mode='text',
                        text=[f"{v:.1f}x" if not (isinstance(v,float) and np.isnan(v)) else '' for v in sub['ROAS']],
                        textposition='top center',
                        textfont=dict(size=9),
                        showlegend=False,
                    ))
                # comparison period dotted lines
                if comp_label and not agg_fun_comp.empty:
                    agg_fun_c_plot = agg_fun_comp.dropna(subset=['Funnel']).copy()
                    agg_fun_c_plot['Month_Label'] = pd.to_datetime(agg_fun_c_plot['Month_Start']).dt.strftime('%b-%Y')
                    agg_fun_c_plot = agg_fun_c_plot.sort_values(['Month_Start','Funnel'])
                    comp_colors = {'TOF':'#6A8CAE','MOF':'#6AAE8C','BOF':'#AE6A8C'}
                    for i, funnel_val in enumerate(agg_fun_c_plot['Funnel'].unique()):
                        sub = agg_fun_c_plot[agg_fun_c_plot['Funnel'] == funnel_val]
                        clr = comp_colors.get(str(funnel_val), COLORS[i % len(COLORS)])
                        fig.add_trace(go.Scatter(
                            x=sub['Month_Label'], y=sub['ROAS'],
                            name=f'{funnel_val} (prev)',
                            mode='lines+markers',
                            line=dict(color=clr, width=1.5, dash='dot'),
                            marker=dict(size=6, symbol='circle-open'),
                            opacity=0.7,
                        ))
                fig.update_layout(
                    margin=dict(t=40,b=30,l=10,r=10), plot_bgcolor='#FAFAFA',
                    font=dict(family='Arial'), xaxis_title='Month',
                    legend=dict(orientation='h', y=1.12),
                )
                st.plotly_chart(fig, use_container_width=True)

        # ── TOF / MOF / BOF funnel breakdown ────────────────────────────────
        st.markdown('<div class="section-title">Conversion Funnel by Funnel Level (TOF / MOF / BOF)</div>',
                    unsafe_allow_html=True)
        st.caption("How each funnel level converts at each stage. Use this to find where you're losing customers within each funnel.")

        funnel_levels = ['TOF','MOF','BOF']
        fl_colors     = {'TOF':'#CBE3FF','MOF':'#CBFFAB','BOF':'#FECAFD'}
        fl_cols = st.columns(len(funnel_levels))

        for i, fl in enumerate(funnel_levels):
            fl_df = df_c[df_c['Funnel'].astype(str).str.upper() == fl.upper()] if 'Funnel' in df_c.columns else pd.DataFrame()
            bg = fl_colors.get(fl,'#EEE')
            with fl_cols[i]:
                st.markdown(f'<div style="background:{bg};border-radius:10px;padding:8px 12px;'
                            f'text-align:center;margin-bottom:8px;font-weight:700;color:#1A3C5E;'
                            f'font-size:15px;">{fl}</div>', unsafe_allow_html=True)
                if fl_df.empty:
                    st.caption("No data")
                    continue
                agg_cols = {
                    'Amount spent (INR)':'sum','Purchases conversion value':'sum',
                    'Purchases':'sum','Impressions':'sum','Link clicks':'sum',
                    'Adds to cart':'sum','Checkouts initiated':'sum'
                }
                if 'Website landing page views' in fl_df.columns:
                    agg_cols['Website landing page views'] = 'sum'
                fl_agg = fl_df.agg(agg_cols).rename({
                    'Amount spent (INR)':'Spend','Purchases conversion value':'Revenue',
                    'Link clicks':'Clicks','Adds to cart':'ATC','Checkouts initiated':'IC',
                    'Website landing page views':'LPV'
                })

                impr  = int(fl_agg.get('Impressions',0))
                clks  = int(fl_agg.get('Clicks',0))
                lpv_v = int(fl_agg.get('LPV',0))
                atc   = int(fl_agg.get('ATC',0))
                ic    = int(fl_agg.get('IC',0))
                purch = int(fl_agg.get('Purchases',0))
                spend = float(fl_agg.get('Spend',0))
                rev   = float(fl_agg.get('Revenue',0))
                roas_v= rev/spend if spend else 0

                # comparison aggregates for this funnel level
                fl_df_comp = pd.DataFrame()
                if not df_c_comp.empty and 'Funnel' in df_c_comp.columns:
                    fl_df_comp = df_c_comp[df_c_comp['Funnel'].astype(str).str.upper() == fl.upper()]
                p_impr = p_clks = p_lpv_v = p_atc = p_ic = p_purch = 0
                p_spend = p_rev = 0.0
                if not fl_df_comp.empty:
                    agg_cols_c = {k: v for k, v in agg_cols.items() if k in fl_df_comp.columns}
                    fl_agg_c = fl_df_comp.agg(agg_cols_c).rename({
                        'Amount spent (INR)':'Spend','Purchases conversion value':'Revenue',
                        'Link clicks':'Clicks','Adds to cart':'ATC','Checkouts initiated':'IC',
                        'Website landing page views':'LPV'
                    })
                    p_impr  = int(fl_agg_c.get('Impressions',0))
                    p_clks  = int(fl_agg_c.get('Clicks',0))
                    p_lpv_v = int(fl_agg_c.get('LPV',0))
                    p_atc   = int(fl_agg_c.get('ATC',0))
                    p_ic    = int(fl_agg_c.get('IC',0))
                    p_purch = int(fl_agg_c.get('Purchases',0))
                    p_spend = float(fl_agg_c.get('Spend',0))
                    p_rev   = float(fl_agg_c.get('Revenue',0))

                def fn(v):
                    if v>=1_000_000: return f"{v/1_000_000:.1f}M"
                    if v>=1_000: return f"{v/1_000:.1f}K"
                    return str(v)

                def rc(r): return '#276221' if r >= 10 else ('#ED7D31' if r >= 2 else '#C00000')
                def rp(a, b): return b / a * 100 if a else 0
                def comp_delta_html(curr, prev):
                    """Inline delta badge for stage values vs comparison period."""
                    if prev == 0 or not comp_label: return ''
                    d = (curr - prev) / prev * 100
                    ar = '▲' if d >= 0 else '▼'
                    clr = '#276221' if d >= 0 else '#C00000'
                    return (f' <span style="font-size:9px;font-weight:700;color:{clr};">'
                            f'{ar}{abs(d):.0f}%</span>')

                ctr_p = rp(impr, clks)
                lpv_p = rp(clks, lpv_v) if lpv_v else 0
                atc_p = rp(clks, atc)
                ic_p  = rp(atc, ic)
                cvr_p = rp(ic, purch)

                p_ctr_p = rp(p_impr, p_clks)
                p_atc_p = rp(p_clks, p_atc)
                p_ic_p  = rp(p_atc, p_ic)
                p_cvr_p = rp(p_ic, p_purch)

                def stage_block(label, val, row_bg, rate_label='', rate_pct=0,
                                prev_val=0, prev_rate=0):
                    # rate sub-text (inline, small, coloured)
                    rate_str = ''
                    if rate_label:
                        r_clr = rc(rate_pct)
                        comp_pp = ''
                        if comp_label and prev_rate > 0:
                            rd = rate_pct - prev_rate
                            r_ar = '▲' if rd >= 0 else '▼'
                            pp_clr = '#276221' if rd >= 0 else '#C00000'
                            comp_pp = (f' <span style="color:{pp_clr};font-size:8px;">'
                                      f'({r_ar}{abs(rd):.1f}pp)</span>')
                        rate_str = (f'<div style="font-size:9px;color:{r_clr};font-weight:600;'
                                   f'margin-left:4px;">↓ {rate_label}{comp_pp}</div>')
                    val_delta = comp_delta_html(val, prev_val)
                    row = (
                        f'<div style="background:{row_bg};border-radius:5px;padding:5px 8px;'
                        f'margin-bottom:3px;">'
                        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                        f'<span style="font-size:10px;font-weight:600;color:#333;">{label}</span>'
                        f'<span style="font-size:12px;font-weight:900;color:#1A3C5E;">{fn(val)}{val_delta}</span>'
                        f'</div>'
                        + (f'<div>{rate_str}</div>' if rate_str else '')
                        + f'</div>'
                    )
                    return row

                html_c = stage_block('Impressions', impr, bg, prev_val=p_impr)
                html_c += stage_block('Clicks', clks, '#DEEAF1',
                                      f'CTR {ctr_p:.2f}%', ctr_p, p_clks, p_ctr_p)
                if lpv_v > 0:
                    html_c += stage_block('Landing Page Views', lpv_v, '#E8F4FD',
                                          f'{lpv_p:.1f}% of Clicks', lpv_p, p_lpv_v)
                html_c += stage_block('Add to Cart', atc, '#D6F0D6',
                                      f'{atc_p:.2f}% of Clicks', atc_p, p_atc, p_atc_p)
                html_c += stage_block('Checkout', ic, '#FFF2CC',
                                      f'{ic_p:.1f}% of ATC', ic_p, p_ic, p_ic_p)
                html_c += stage_block('Purchases', purch, '#FCE4D6',
                                      f'{cvr_p:.1f}% of Checkout', cvr_p, p_purch, p_cvr_p)
                st.markdown(html_c, unsafe_allow_html=True)
                roas_col_color = '#276221' if roas_v >= roas_be else '#C00000'
                # comparison ROAS delta for this funnel level
                comp_roas_badge = ""
                p_roas_v = p_rev / p_spend if p_spend else 0
                if p_roas_v and comp_label:
                    delta_roas = (roas_v - p_roas_v) / p_roas_v * 100
                    d_arrow = "▲" if delta_roas >= 0 else "▼"
                    d_clr   = "#90EE90" if delta_roas >= 0 else "#FFB3B3"
                    comp_roas_badge = (f'<span style="color:{d_clr};font-size:10px;font-weight:700;">'
                                      f'{d_arrow}{abs(delta_roas):.1f}% vs {comp_label}</span>')
                roas_display_clr = '#90EE90' if roas_v >= roas_be else '#FFB3B3'
                st.markdown(
                    f'<div style="background:#1A3C5E;border-radius:5px;padding:6px 8px;'
                    f'text-align:center;margin-top:4px;">'
                    f'<span style="color:{roas_display_clr};font-size:16px;font-weight:900;">{roas_v:.2f}x ROAS</span>'
                    f'<span style="color:#AAA;font-size:9px;"> | ₹{spend:,.0f} spend</span>'
                    f'{"<br><span style=&quot;font-size:9px;&quot;>" + comp_roas_badge + "</span>" if comp_roas_badge else ""}'
                    f'</div>', unsafe_allow_html=True)

        # ── ROAS colour legend ───────────────────────────────────────────────
        st.markdown("""
        <div style='display:flex;gap:8px;align-items:center;margin:8px 0 14px;flex-wrap:wrap;font-size:12px;'>
          <b style='color:#1A3C5E;margin-right:4px;'>ROAS colour key:</b>
          <span style='background:#E2EFDA;color:#276221;padding:3px 10px;border-radius:4px;font-weight:600;'>≥6.0x SCALE</span>
          <span style='background:#D6F0D6;color:#276221;padding:3px 10px;border-radius:4px;font-weight:600;'>≥5.5x BREAK-EVEN</span>
          <span style='background:#FFF2CC;color:#7F5F00;padding:3px 10px;border-radius:4px;font-weight:600;'>≥4.0x OPTIMISE</span>
          <span style='background:#FCE4D6;color:#833C00;padding:3px 10px;border-radius:4px;font-weight:600;'>≥2.0x REVIEW</span>
          <span style='background:#FFE2E2;color:#C00000;padding:3px 10px;border-radius:4px;font-weight:600;'>&lt;2.0x UNDERPERFORMING</span>
        </div>""", unsafe_allow_html=True)

        # ── All ad sets with spend > 0 — with filters ────────────────────────
        st.markdown('<div class="section-title">All Active Ad Sets (Spend > 0 in selected period)</div>',
                    unsafe_allow_html=True)
        agg_adset_all = dp._agg(df_c, ['Ad set name','Funnel']).sort_values('Spend', ascending=False)
        agg_adset_all = agg_adset_all[agg_adset_all['Spend'] > 0].reset_index(drop=True)

        # filters
        st.markdown("**Filter & Sort Ad Sets**")
        fa, fb, fc, fd = st.columns(4)
        funnel_opts = ['All'] + sorted(agg_adset_all['Funnel'].dropna().unique().tolist())
        f_funnel = fa.selectbox("Funnel", funnel_opts, key='as_funnel')
        f_roas_min = fb.number_input("Min ROAS", value=0.0, step=0.5, key='as_roas_min')
        f_roas_max = fc.number_input("Max ROAS", value=50.0, step=0.5, key='as_roas_max')
        f_name = fd.text_input("Search ad set name", key='as_name')

        adset_view = agg_adset_all.copy()
        if f_funnel != 'All':
            adset_view = adset_view[adset_view['Funnel'] == f_funnel]
        if f_name:
            adset_view = adset_view[adset_view['Ad set name'].astype(str).str.contains(f_name, case=False, na=False)]
        adset_view = adset_view[
            (adset_view['ROAS'].fillna(0) >= f_roas_min) &
            (adset_view['ROAS'].fillna(0) <= f_roas_max)
        ]
        st.caption(f"Showing **{len(adset_view)}** of {len(agg_adset_all)} ad sets  |  Click any column header to sort")

        cols_show = ['Ad set name','Funnel','Spend','Revenue','ROAS','CTR','CVR','CPA','Purchases']
        cols_show = [c for c in cols_show if c in adset_view.columns]
        disp_as = adset_view[cols_show].copy()
        # merge comparison ROAS delta
        agg_adset_comp = dp._agg(df_c_comp, ['Ad set name','Funnel']) if not df_c_comp.empty else pd.DataFrame()
        disp_as, has_as_delta = _agg_with_comp_delta(disp_as, agg_adset_comp, ['Ad set name'])
        if has_as_delta and comp_label:
            cols_show = cols_show + ['ROAS Δ%']
        # keep numeric for sorting; format display cols
        for c in ['Spend','Revenue','CPA']:
            if c in disp_as.columns: disp_as[c] = disp_as[c].round(0)
        for c in ['ROAS','CTR','CVR']:
            if c in disp_as.columns: disp_as[c] = disp_as[c].round(2)
        interactive_table(disp_as[[c for c in cols_show if c in disp_as.columns]],
                          roas_col='ROAS', roas_be=roas_be)

        st.markdown("**AI Insights — Ad Sets**")
        _adset_comp_view = agg_adset_comp[agg_adset_comp['Spend'] > 0] if not agg_adset_comp.empty else pd.DataFrame()
        insights = adset_insights(adset_view, roas_be, min_spend,
                                  comp_df=_adset_comp_view if not _adset_comp_view.empty else None,
                                  comp_label=comp_label)
        for ins in insights:
            st.markdown(f"- {ins}")

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 3: CREATIVE
    # ═══════════════════════════════════════════════════════════════════════════
    with tabs[2]:
        if df_c.empty:
            st.warning("No data."); return

        _comp_banner(df_c, df_c_comp, comp_label)

        cr1, cr2 = st.columns(2)

        with cr1:
            st.markdown("**Format Performance**")
            if not agg_fmt.empty:
                fig = _grouped_spend_bar(
                    curr_df=agg_fmt.dropna(subset=['Format']),
                    comp_df=agg_fmt_comp if not agg_fmt_comp.empty else None,
                    x_col='Format',
                    title='Spend by Format — Current vs Comparison',
                    height=320, roas_be=roas_be,
                    curr_label='Current', comp_label=comp_label or 'Previous',
                )
                st.plotly_chart(fig, use_container_width=True)

        with cr2:
            st.markdown("**Category Performance**")
            if not agg_cat.empty:
                fig = _grouped_spend_bar(
                    curr_df=agg_cat.dropna(subset=['Category']),
                    comp_df=agg_cat_comp if not agg_cat_comp.empty else None,
                    x_col='Category',
                    title='Spend by Category — Current vs Comparison',
                    height=320, roas_be=roas_be,
                    curr_label='Current', comp_label=comp_label or 'Previous',
                )
                st.plotly_chart(fig, use_container_width=True)

        # ── Format & Category insights ───────────────────────────────────────
        ins_c1, ins_c2 = st.columns(2)
        with ins_c1:
            st.markdown("**AI Insights — Format**")
            if not agg_fmt.empty:
                fmt_ins = adset_insights(
                    agg_fmt.dropna(subset=['Format']).rename(columns={'Format': 'Ad set name'}),
                    roas_be, min_spend,
                    comp_df=agg_fmt_comp.rename(columns={'Format': 'Ad set name'}) if not agg_fmt_comp.empty else None,
                    comp_label=comp_label)
                for ins in fmt_ins:
                    st.markdown(f"- {ins}")
        with ins_c2:
            st.markdown("**AI Insights — Category**")
            if not agg_cat.empty:
                cat_ins = adset_insights(
                    agg_cat.dropna(subset=['Category']).rename(columns={'Category': 'Ad set name'}),
                    roas_be, min_spend,
                    comp_df=agg_cat_comp.rename(columns={'Category': 'Ad set name'}) if not agg_cat_comp.empty else None,
                    comp_label=comp_label)
                for ins in cat_ins:
                    st.markdown(f"- {ins}")

        cr3, cr4 = st.columns(2)
        with cr3:
            st.markdown("**Influencer vs BAU**")
            if not agg_inf.empty:
                agg_inf_plot = agg_inf.copy()
                agg_inf_plot['Type'] = agg_inf_plot['Is_Influencer'].map(
                    {True:'Influencer', False:'BAU'})
                agg_inf_comp_plot = pd.DataFrame()
                if not agg_inf_comp.empty:
                    agg_inf_comp_plot = agg_inf_comp.copy()
                    agg_inf_comp_plot['Type'] = agg_inf_comp_plot['Is_Influencer'].map(
                        {True:'Influencer', False:'BAU'})
                fig = _grouped_spend_bar(
                    curr_df=agg_inf_plot,
                    comp_df=agg_inf_comp_plot if not agg_inf_comp_plot.empty else None,
                    x_col='Type',
                    title='Influencer vs BAU — Current vs Comparison',
                    height=300, roas_be=roas_be,
                    curr_label='Current', comp_label=comp_label or 'Previous',
                )
                st.plotly_chart(fig, use_container_width=True)

        with cr4:
            # Category ROAS comparison — grouped bar if comparison active, else horizontal bars
            sig_cats = agg_cat.dropna(subset=['Category'])
            sig_cats = sig_cats[sig_cats['Spend'] >= min_spend]['Category'].tolist()
            agg_cat_sig = agg_cat[agg_cat['Category'].isin(sig_cats)].copy() if sig_cats else agg_cat.copy()

            if comp_label and not agg_cat_comp.empty:
                st.markdown(f"**ROAS by Category — Current vs {comp_label}**")
                agg_cat_comp_sig = agg_cat_comp[agg_cat_comp['Category'].isin(sig_cats)].copy() \
                    if sig_cats else agg_cat_comp.copy()
                categories = agg_cat_sig['Category'].tolist()
                curr_roas  = agg_cat_sig['ROAS'].tolist()
                prev_roas  = []
                for cat in categories:
                    match = agg_cat_comp_sig[agg_cat_comp_sig['Category'] == cat]
                    prev_roas.append(float(match.iloc[0]['ROAS']) if not match.empty else 0)
                curr_colors = [_roas_color(r, roas_be)[0] for r in curr_roas]
                prev_colors = [_roas_color(r, roas_be)[1] for r in prev_roas]
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    name='Current', x=categories, y=curr_roas,
                    marker_color=curr_colors,
                    text=[f"{v:.2f}x" for v in curr_roas],
                    textposition='outside', textfont=dict(size=10),
                    hovertemplate='<b>%{x}</b><br>ROAS: %{y:.2f}x<extra>Current</extra>',
                ))
                fig.add_trace(go.Bar(
                    name=comp_label, x=categories, y=prev_roas,
                    marker_color=prev_colors,
                    marker_line_color=curr_colors, marker_line_width=1.5,
                    text=[f"{v:.2f}x" if v else '' for v in prev_roas],
                    textposition='outside', textfont=dict(size=9, color='#666'),
                    hovertemplate='<b>%{x}</b><br>ROAS: %{y:.2f}x<extra>Previous</extra>',
                ))
                fig.add_hline(y=roas_be, line_dash='dash', line_color='red',
                              annotation_text=f"Break-even {roas_be}x",
                              annotation_position='bottom right')
                fig.update_layout(
                    height=300, barmode='group', bargap=0.25, bargroupgap=0.08,
                    plot_bgcolor='#FAFAFA', paper_bgcolor='white',
                    font=dict(family='Arial', size=11),
                    margin=dict(t=40, b=40, l=10, r=10),
                    legend=dict(orientation='h', y=1.1),
                    yaxis_title='ROAS',
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.markdown("**ROAS by Category**")
                if not agg_cat_sig.empty:
                    agg_cat_sig_sorted = agg_cat_sig.sort_values('ROAS', ascending=True)
                    colors = [_roas_color(r, roas_be)[0] for r in agg_cat_sig_sorted['ROAS']]
                    fig = go.Figure(go.Bar(
                        x=agg_cat_sig_sorted['ROAS'],
                        y=agg_cat_sig_sorted['Category'],
                        orientation='h',
                        marker_color=colors,
                        text=[f"{v:.2f}x" for v in agg_cat_sig_sorted['ROAS']],
                        textposition='outside',
                        hovertemplate='<b>%{y}</b><br>ROAS: %{x:.2f}x<extra></extra>',
                    ))
                    fig.add_vline(x=roas_be, line_dash='dash', line_color='red',
                                  annotation_text=f"B/E {roas_be}x")
                    fig.update_layout(
                        height=280, plot_bgcolor='#FAFAFA', paper_bgcolor='white',
                        font=dict(family='Arial'), margin=dict(t=20, b=10, l=10, r=60),
                        xaxis_title='ROAS',
                    )
                    st.plotly_chart(fig, use_container_width=True)

        if not agg_per_inf.empty:
            st.markdown('<div class="section-title">Per-Influencer Breakdown</div>',
                        unsafe_allow_html=True)

            st.markdown("**Filter & Sort Influencers**")
            ia, ib = st.columns(2)
            inf_roas_min = ia.number_input("Min ROAS", value=0.0, step=0.5, key='inf_roas_min')
            inf_roas_max = ib.number_input("Max ROAS", value=50.0, step=0.5, key='inf_roas_max')

            inf_view = agg_per_inf.copy()
            inf_view = inf_view[
                (inf_view['ROAS'].fillna(0) >= inf_roas_min) &
                (inf_view['ROAS'].fillna(0) <= inf_roas_max)
            ]
            st.caption(f"Showing **{len(inf_view)}** influencers  |  Click column header to sort")
            # attach Category for each influencer from raw campaign data
            if 'Category' in df_c.columns and 'Influencer' in df_c.columns:
                inf_cat = (df_c[df_c['Is_Influencer'] == True]
                           .groupby('Influencer')['Category']
                           .agg(lambda x: ', '.join(sorted(x.dropna().astype(str).unique())))
                           .reset_index())
                inf_view = inf_view.merge(inf_cat, on='Influencer', how='left')
            cols = ['Influencer','Category','Spend','Revenue','ROAS','Purchases','CPA','CTR','CVR']
            cols = [c for c in cols if c in inf_view.columns]
            disp_inf = inf_view[cols].copy()
            disp_inf, has_inf_delta = _agg_with_comp_delta(disp_inf, agg_per_inf_comp, ['Influencer'])
            if has_inf_delta and comp_label:
                cols = cols + ['ROAS Δ%']
            for c in ['Spend','Revenue','CPA']:
                if c in disp_inf: disp_inf[c] = disp_inf[c].round(0)
            for c in ['ROAS','CTR','CVR']:
                if c in disp_inf: disp_inf[c] = disp_inf[c].round(2)
            interactive_table(disp_inf[[c for c in cols if c in disp_inf.columns]],
                              roas_col='ROAS', roas_be=roas_be)

            st.markdown("**AI Insights — Influencers**")
            inf_ins = adset_insights(
                inf_view, roas_be, min_spend,
                comp_df=agg_per_inf_comp if not agg_per_inf_comp.empty else None,
                comp_label=comp_label)
            for ins in inf_ins:
                st.markdown(f"- {ins}")
            if len(inf_view) > 0:
                below = inf_view[inf_view['ROAS'] < roas_be]
                above = inf_view[inf_view['ROAS'] >= roas_be]
                st.markdown(f"- **{len(above)} of {len(inf_view)}** influencers are above break-even ROAS. "
                            f"{'None are profitable — influencer budget needs a full review.' if len(above)==0 else ''}")
                if not below.empty:
                    names = ', '.join(below['Influencer'].astype(str).tolist())
                    st.markdown(f"- Underperforming influencers: **{names}** — negotiate performance-based deals "
                                f"or redirect budget to BAU creatives that are proven.")

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 4: DEMOGRAPHICS
    # ═══════════════════════════════════════════════════════════════════════════
    with tabs[3]:
        if df_d.empty:
            st.warning("No demographics data for selected filters."); return

        _comp_banner(df_c, df_c_comp, comp_label)

        has_demo_comp = comp_label and not agg_demo_comp.empty

        def _rich_heatmap(curr_pivot, prev_pivot, colorscale, is_spend=False, period_label=''):
            """go.Heatmap: cell shows current value; hover reveals comparison value + Δ%."""
            ages    = curr_pivot.index.tolist()
            genders = curr_pivot.columns.tolist()
            z_curr  = curr_pivot.values.astype(float)
            if prev_pivot is not None:
                z_prev = prev_pivot.reindex(
                    index=curr_pivot.index, columns=curr_pivot.columns
                ).values.astype(float)
            else:
                z_prev = np.full_like(z_curr, np.nan)

            with np.errstate(divide='ignore', invalid='ignore'):
                z_delta = np.where(
                    (z_prev != 0) & ~np.isnan(z_prev) & ~np.isnan(z_curr),
                    (z_curr - z_prev) / np.abs(z_prev) * 100,
                    np.nan
                )

            if is_spend:
                cell_text = [[f"₹{v:,.0f}" if not np.isnan(v) else '' for v in row] for row in z_curr]
                if prev_pivot is not None:
                    hover = ("<b>%{y} · %{x}</b><br>"
                             "Current: ₹%{z:,.0f}<br>"
                             "Previous: ₹%{customdata[0]:,.0f}<br>"
                             "Change: %{customdata[1]:+.1f}%<extra></extra>")
                else:
                    hover = "<b>%{y} · %{x}</b><br>Spend: ₹%{z:,.0f}<extra></extra>"
            else:
                cell_text = [[f"{v:.2f}x" if not np.isnan(v) else '' for v in row] for row in z_curr]
                if prev_pivot is not None:
                    hover = ("<b>%{y} · %{x}</b><br>"
                             "Current: %{z:.2f}x<br>"
                             "Previous: %{customdata[0]:.2f}x<br>"
                             "Change: %{customdata[1]:+.1f}%<extra></extra>")
                else:
                    hover = "<b>%{y} · %{x}</b><br>ROAS: %{z:.2f}x<extra></extra>"

            customdata = np.stack([z_prev, z_delta], axis=-1)
            fig = go.Figure(go.Heatmap(
                z=z_curr, x=genders, y=ages,
                text=cell_text, texttemplate='%{text}',
                textfont=dict(size=10, family='Arial'),
                customdata=customdata, hovertemplate=hover,
                colorscale=colorscale, showscale=False,
                xgap=2, ygap=2,
            ))
            fig.update_layout(
                height=max(250, len(ages) * 45 + 80),
                margin=dict(t=10, b=10, l=10, r=10),
                font=dict(family='Arial', size=10),
                yaxis=dict(autorange='reversed'),
            )
            return fig

        # ── Row 1: Current period heatmaps (with comparison on hover) ──────────
        d_cols_r1 = st.columns(2)
        with d_cols_r1[0]:
            st.markdown("**ROAS by Gender × Age** — Current Period"
                        + (f" *(hover for vs {comp_label})*" if has_demo_comp else ""))
            if not agg_demo.empty:
                try:
                    curr_p = agg_demo.pivot_table(index='Age', columns='Gender', values='ROAS', aggfunc='mean')
                    prev_p = agg_demo_comp.pivot_table(index='Age', columns='Gender', values='ROAS', aggfunc='mean') \
                             if has_demo_comp else None
                    st.plotly_chart(_rich_heatmap(curr_p, prev_p, 'RdYlGn'),
                                    use_container_width=True)
                except Exception:
                    st.dataframe(agg_demo[['Gender','Age','Spend','ROAS','CPA']], use_container_width=True)

        with d_cols_r1[1]:
            st.markdown("**Spend by Gender × Age** — Current Period"
                        + (f" *(hover for vs {comp_label})*" if has_demo_comp else ""))
            if not agg_demo.empty:
                try:
                    curr_sp = agg_demo.pivot_table(index='Age', columns='Gender', values='Spend', aggfunc='sum')
                    prev_sp = agg_demo_comp.pivot_table(index='Age', columns='Gender', values='Spend', aggfunc='sum') \
                              if has_demo_comp else None
                    st.plotly_chart(_rich_heatmap(curr_sp, prev_sp, 'Blues', is_spend=True),
                                    use_container_width=True)
                except Exception:
                    pass

        # ── Row 2: Comparison period heatmaps (only when comparison active) ────
        if has_demo_comp:
            d_cols_r2 = st.columns(2)
            with d_cols_r2[0]:
                st.markdown(f"**ROAS by Gender × Age** — {comp_label}")
                try:
                    prev_roas = agg_demo_comp.pivot_table(index='Age', columns='Gender', values='ROAS', aggfunc='mean')
                    st.plotly_chart(_rich_heatmap(prev_roas, None, 'RdYlGn'),
                                    use_container_width=True)
                except Exception:
                    st.caption("Not enough comparison data for ROAS heatmap.")

            with d_cols_r2[1]:
                st.markdown(f"**Spend by Gender × Age** — {comp_label}")
                try:
                    prev_spend = agg_demo_comp.pivot_table(index='Age', columns='Gender', values='Spend', aggfunc='sum')
                    st.plotly_chart(_rich_heatmap(prev_spend, None, 'Blues', is_spend=True),
                                    use_container_width=True)
                except Exception:
                    st.caption("Not enough comparison data for Spend heatmap.")

        st.markdown('<div class="section-title">Full Demographics Table</div>',
                    unsafe_allow_html=True)
        if not agg_demo.empty:
            st.markdown("**Filter Demographics**")
            da, db, dc = st.columns(3)
            gender_opts = ['All'] + sorted(agg_demo['Gender'].dropna().unique().tolist())
            f_gender = da.selectbox("Gender", gender_opts, key='demo_gender')
            age_opts   = ['All'] + sorted(agg_demo['Age'].dropna().unique().tolist())
            f_age   = db.selectbox("Age group", age_opts, key='demo_age')
            demo_roas_min = dc.number_input("Min ROAS", value=0.0, step=0.5, key='demo_roas')

            demo_view = agg_demo.copy()
            if f_gender != 'All':
                demo_view = demo_view[demo_view['Gender'] == f_gender]
            if f_age != 'All':
                demo_view = demo_view[demo_view['Age'] == f_age]
            demo_view = demo_view[demo_view['ROAS'].fillna(0) >= demo_roas_min]

            st.caption(f"Showing **{len(demo_view)}** segments  |  Click column header to sort")
            cols = ['Gender','Age','Spend','Revenue','ROAS','Purchases','CPA','CTR','CVR']
            cols = [c for c in cols if c in demo_view.columns]
            disp_demo = demo_view[cols].copy()
            disp_demo, has_demo_delta = _agg_with_comp_delta(disp_demo, agg_demo_comp, ['Gender','Age'])
            if has_demo_delta and comp_label:
                cols = cols + ['ROAS Δ%']
            for c in ['Spend','Revenue','CPA']:
                if c in disp_demo: disp_demo[c] = disp_demo[c].round(0)
            for c in ['ROAS','CTR','CVR']:
                if c in disp_demo: disp_demo[c] = disp_demo[c].round(2)
            interactive_table(disp_demo[[c for c in cols if c in disp_demo.columns]],
                              roas_col='ROAS', roas_be=roas_be)

            st.markdown("**AI Insights — Demographics**")
            _demo_comp_labeled = pd.DataFrame()
            if not agg_demo_comp.empty:
                _demo_comp_labeled = agg_demo_comp.copy()
                _demo_comp_labeled['Ad set name'] = (_demo_comp_labeled['Gender'].astype(str)
                                                     + ' ' + _demo_comp_labeled['Age'].astype(str))
            _demo_view_labeled = demo_view.assign(
                **{'Ad set name': demo_view['Gender'].astype(str) + ' ' + demo_view['Age'].astype(str)})
            demo_ins = adset_insights(
                _demo_view_labeled, roas_be, min_spend,
                comp_df=_demo_comp_labeled if not _demo_comp_labeled.empty else None,
                comp_label=comp_label)
            for ins in demo_ins:
                st.markdown(f"- {ins}")
            if not demo_view.empty:
                top = demo_view.loc[demo_view['ROAS'].idxmax()] if not demo_view['ROAS'].isna().all() else None
                bot = demo_view.loc[demo_view['Spend'].idxmax()] if True else None
                if top is not None:
                    st.markdown(f"- Best ROAS segment: **{top['Gender']} {top['Age']}** at "
                                f"**{top['ROAS']:.2f}x** — consider increasing bid modifiers or audience targeting here.")
                if bot is not None and bot['ROAS'] < roas_be:
                    st.markdown(f"- Highest-spend segment **{bot['Gender']} {bot['Age']}** "
                                f"(INR {bot['Spend']:,.0f}) is at only {bot['ROAS']:.2f}x ROAS — "
                                f"review creative messaging for this audience.")

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 5: PLATFORM
    # ═══════════════════════════════════════════════════════════════════════════
    with tabs[4]:
        if df_p.empty:
            st.warning("No platform data for selected filters."); return

        _comp_banner(df_c, df_c_comp, comp_label)

        p1, p2 = st.columns(2)
        plat_grp = agg_plat.groupby('Platform').agg(
            Spend=('Spend','sum'), Revenue=('Revenue','sum'), Purchases=('Purchases','sum')
        ).reset_index()
        plat_grp['ROAS'] = (plat_grp['Revenue'] / plat_grp['Spend'].replace(0, np.nan)).round(2)
        plat_grp = plat_grp[plat_grp['Spend'] > 0].sort_values('Spend', ascending=False)

        plac_grp = agg_plat.groupby('Placement').agg(
            Spend=('Spend','sum'), Revenue=('Revenue','sum'), Purchases=('Purchases','sum')
        ).reset_index()
        plac_grp['ROAS'] = (plac_grp['Revenue'] / plac_grp['Spend'].replace(0, np.nan)).round(2)
        plac_grp = plac_grp[plac_grp['Spend'] > 0].sort_values('Spend', ascending=False)

        # comparison group aggregates
        plat_grp_comp = pd.DataFrame()
        plac_grp_comp = pd.DataFrame()
        if not agg_plat_comp.empty:
            plat_grp_comp = agg_plat_comp.groupby('Platform').agg(
                Spend=('Spend','sum'), Revenue=('Revenue','sum')
            ).reset_index()
            plat_grp_comp['ROAS'] = (plat_grp_comp['Revenue'] / plat_grp_comp['Spend'].replace(0, np.nan)).round(2)
            plac_grp_comp = agg_plat_comp.groupby('Placement').agg(
                Spend=('Spend','sum'), Revenue=('Revenue','sum')
            ).reset_index()
            plac_grp_comp['ROAS'] = (plac_grp_comp['Revenue'] / plac_grp_comp['Spend'].replace(0, np.nan)).round(2)

        # ── Row 1: Spend comparison ──────────────────────────────────────────
        with p1:
            st.markdown("**Spend by Platform**")
            fig_ps = _grouped_spend_bar(
                curr_df=plat_grp,
                comp_df=plat_grp_comp if not plat_grp_comp.empty else None,
                x_col='Platform',
                title='Platform Spend — Current vs Comparison',
                height=300, roas_be=roas_be,
                curr_label='Current', comp_label=comp_label or 'Previous',
            )
            st.plotly_chart(fig_ps, use_container_width=True)

        with p2:
            st.markdown("**Spend by Placement** *(top 8)*")
            top_plac = plac_grp.head(8)
            top_plac_comp = plac_grp_comp[plac_grp_comp['Placement'].isin(top_plac['Placement'])] \
                if not plac_grp_comp.empty else pd.DataFrame()
            fig_plc = _grouped_spend_bar(
                curr_df=top_plac,
                comp_df=top_plac_comp if not top_plac_comp.empty else None,
                x_col='Placement',
                title='Placement Spend — Current vs Comparison',
                height=300, roas_be=roas_be,
                curr_label='Current', comp_label=comp_label or 'Previous',
            )
            fig_plc.update_layout(xaxis=dict(tickangle=-25))
            st.plotly_chart(fig_plc, use_container_width=True)

        # ── Row 2: ROAS comparison ───────────────────────────────────────────
        pr1, pr2 = st.columns(2)

        def _roas_comp_bar(curr_df, comp_df, x_col, title, height, roas_be, comp_lbl, x_angle=0):
            """Grouped bar chart for ROAS current vs comparison."""
            curr_df = curr_df.copy()
            categories = curr_df[x_col].tolist()
            curr_colors = [_roas_color(r, roas_be)[0] for r in curr_df['ROAS']]
            comp_roas = []
            comp_colors_list = []
            for cat in categories:
                if comp_df is not None and len(comp_df):
                    match = comp_df[comp_df[x_col] == cat]
                    rv = float(match.iloc[0]['ROAS']) if not match.empty else 0
                else:
                    rv = 0
                comp_roas.append(rv)
                comp_colors_list.append(_roas_color(rv, roas_be)[1])
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name='Current', x=categories, y=curr_df['ROAS'].tolist(),
                marker_color=curr_colors,
                text=[f"{v:.2f}x" for v in curr_df['ROAS']],
                textposition='outside', textfont=dict(size=10),
                hovertemplate='<b>%{x}</b><br>ROAS: %{y:.2f}x<extra>Current</extra>',
            ))
            if any(v > 0 for v in comp_roas):
                fig.add_trace(go.Bar(
                    name=comp_lbl, x=categories, y=comp_roas,
                    marker_color=comp_colors_list,
                    marker_line_color=curr_colors, marker_line_width=1.5,
                    text=[f"{v:.2f}x" if v else '' for v in comp_roas],
                    textposition='outside', textfont=dict(size=9, color='#666'),
                    hovertemplate='<b>%{x}</b><br>ROAS: %{y:.2f}x<extra>Previous</extra>',
                ))
            fig.add_hline(y=roas_be, line_dash='dash', line_color='red',
                          annotation_text=f"B/E {roas_be}x", annotation_position='bottom right')
            fig.update_layout(
                title=title, height=height, barmode='group',
                bargap=0.25, bargroupgap=0.08,
                plot_bgcolor='#FAFAFA', paper_bgcolor='white',
                font=dict(family='Arial', size=11),
                margin=dict(t=50, b=50, l=10, r=10),
                legend=dict(orientation='h', y=1.1),
                yaxis_title='ROAS',
                xaxis=dict(tickangle=x_angle),
            )
            return fig

        with pr1:
            st.markdown("**ROAS by Platform**")
            fig_pr = _roas_comp_bar(plat_grp, plat_grp_comp if not plat_grp_comp.empty else None,
                                    'Platform', 'Platform ROAS — Current vs Comparison',
                                    280, roas_be, comp_label or 'Previous')
            st.plotly_chart(fig_pr, use_container_width=True)

        with pr2:
            st.markdown("**ROAS by Placement** *(top 8)*")
            fig_pr2 = _roas_comp_bar(top_plac, top_plac_comp if not top_plac_comp.empty else None,
                                     'Placement', 'Placement ROAS — Current vs Comparison',
                                     280, roas_be, comp_label or 'Previous', x_angle=-25)
            st.plotly_chart(fig_pr2, use_container_width=True)

        st.markdown('<div class="section-title">Platform × Placement Detail</div>', unsafe_allow_html=True)
        if not agg_plat.empty:
            st.markdown("**Filter & Sort Platform**")
            pa, pb, pc = st.columns(3)
            plat_opts = ['All'] + sorted(agg_plat['Platform'].dropna().unique().tolist())
            f_plat  = pa.selectbox("Platform", plat_opts, key='plat_f')
            f_plat_roas_min = pb.number_input("Min ROAS", value=0.0, step=0.5, key='plat_rmin')
            f_plat_roas_max = pc.number_input("Max ROAS", value=50.0, step=1.0, key='plat_rmax')

            plat_view = agg_plat.copy()
            if f_plat != 'All':
                plat_view = plat_view[plat_view['Platform'] == f_plat]
            plat_view = plat_view[
                (plat_view['ROAS'].fillna(0) >= f_plat_roas_min) &
                (plat_view['ROAS'].fillna(0) <= f_plat_roas_max)
            ]
            st.caption(f"Showing **{len(plat_view)}** placements  |  Click column header to sort")
            cols_p = ['Platform','Placement','Spend','Revenue','ROAS','Purchases','CPA','CTR','CPM']
            cols_p = [c for c in cols_p if c in plat_view.columns]
            disp_p = plat_view[cols_p].copy()
            disp_p, has_plat_delta = _agg_with_comp_delta(disp_p, agg_plat_comp, ['Platform','Placement'])
            if has_plat_delta and comp_label:
                cols_p = cols_p + ['ROAS Δ%']
            for c in ['Spend','Revenue','CPA']:
                if c in disp_p: disp_p[c] = disp_p[c].round(2)
            for c in ['ROAS','CPM']:
                if c in disp_p: disp_p[c] = disp_p[c].round(2)
            for c in ['CTR']:
                if c in disp_p: disp_p[c] = disp_p[c].round(2)
            interactive_table(disp_p[[c for c in cols_p if c in disp_p.columns]],
                              roas_col='ROAS', roas_be=roas_be)

            st.markdown("**AI Insights — Platform & Placement**")
            _plat_comp_labeled = pd.DataFrame()
            if not agg_plat_comp.empty:
                _plat_comp_labeled = agg_plat_comp.copy()
                _plat_comp_labeled['Ad set name'] = (_plat_comp_labeled['Platform'].astype(str)
                                                     + ' — ' + _plat_comp_labeled['Placement'].astype(str))
            _plat_view_labeled = plat_view.assign(
                **{'Ad set name': plat_view['Platform'].astype(str) + ' — ' + plat_view['Placement'].astype(str)})
            plat_ins = adset_insights(
                _plat_view_labeled, roas_be, min_spend,
                comp_df=_plat_comp_labeled if not _plat_comp_labeled.empty else None,
                comp_label=comp_label)
            for ins in plat_ins:
                st.markdown(f"- {ins}")
            if not plac_grp.empty:
                best_plac = plac_grp.loc[plac_grp['ROAS'].idxmax()]
                worst_plac = plac_grp.loc[plac_grp['ROAS'].idxmin()]
                st.markdown(f"- Best placement: **{best_plac['Placement']}** at {best_plac['ROAS']:.2f}x ROAS on ₹{best_plac['Spend']:,.2f} spend.")
                if worst_plac['ROAS'] < roas_be and worst_plac['Spend'] >= min_spend:
                    st.markdown(f"- Weakest placement: **{worst_plac['Placement']}** at {worst_plac['ROAS']:.2f}x — consider excluding this placement.")

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 6: WHAT-IF SIMULATOR
    # ═══════════════════════════════════════════════════════════════════════════
    with tabs[5]:
        whatif_tab(df_c, agg_fun_t, agg_cat, roas_be, min_spend)


if __name__ == '__main__':
    main()
