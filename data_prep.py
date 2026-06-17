"""
data_prep.py  –  load, clean, merge and aggregate all raw data.
Imported by build_full.py and refresh.py.
"""
import pandas as pd
import numpy as np
from datetime import datetime

import os as _os, sys as _sys
_HERE        = _os.path.dirname(_os.path.abspath(__file__))
_REPO_EXCEL  = _os.path.join(_HERE, 'Meta Quarterly Performance Report.xlsx')
_LOCAL_EXCEL = r'C:\Users\Lenovo\OneDrive\Meta\Meta Quarterly Performance Report.xlsx'
# On Streamlit Cloud (Linux) always use repo path; on Windows prefer OneDrive
PATH = _REPO_EXCEL if (_sys.platform != 'win32' or _os.path.exists(_REPO_EXCEL)) else _LOCAL_EXCEL

MONTH_ORDER = [
    'Oct-2025','Nov-2025','Dec-2025',
    'Jan-2026','Feb-2026','Mar-2026','Apr-2026','May-2026','Jun-2026',
]
MONTH_LABELS = MONTH_ORDER   # same format used for both storage and display
MONTH_STARTS = [
    datetime(2025,10,1), datetime(2025,11,1), datetime(2025,12,1),
    datetime(2026,1,1),  datetime(2026,2,1),  datetime(2026,3,1),
    datetime(2026,4,1),  datetime(2026,5,1),  datetime(2026,6,1),
]
MONTH_ENDS = [
    datetime(2025,10,31), datetime(2025,11,30), datetime(2025,12,31),
    datetime(2026,1,31),  datetime(2026,2,28),  datetime(2026,3,31),
    datetime(2026,4,30),  datetime(2026,5,31),  datetime(2026,6,30),
]

NUM_COLS = ['Amount spent (INR)','Purchases conversion value','Purchases',
            'Adds to cart','Checkouts initiated','Impressions','Link clicks',
            'Reach','Website landing page views','Clicks (all)']

def _num(df):
    for c in NUM_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    return df

HAS_DAILY_DATA = False   # updated by load_all() when Date column is present
DATA_MIN_DATE  = None
DATA_MAX_DATE  = None


def load_all():
    global HAS_DAILY_DATA, DATA_MIN_DATE, DATA_MAX_DATE

    # read all sheets at once so we only open the file once
    _all = pd.read_excel(PATH, sheet_name=None)

    df_c = _all.get('Raw Data - Campaign ', pd.DataFrame())
    # merge any overflow campaign sheet (e.g. "Raw Data - Campaign 2026")
    for _s, _df in _all.items():
        if _s.startswith('Raw Data - Campaign') and _s != 'Raw Data - Campaign ':
            df_c = pd.concat([df_c, _df], ignore_index=True)

    df_d = pd.read_excel(PATH, sheet_name='Raw Data - Demographics')
    df_p = pd.read_excel(PATH, sheet_name='Raw Data - Platform & Placement')
    vl   = pd.read_excel(PATH, sheet_name='Vlookup')

    # remove duplicate column names (keep first occurrence)
    df_c = df_c.loc[:, ~df_c.columns.duplicated()]
    df_d = df_d.loc[:, ~df_d.columns.duplicated()]
    df_p = df_p.loc[:, ~df_p.columns.duplicated()]

    _num(df_c); _num(df_d); _num(df_p)

    # merge vlookup → campaign
    vl_ad = (vl[['Ad name','Category ','Format','Influencer']]
               .dropna(subset=['Ad name'])
               .rename(columns={'Category ':'Category'})
               .drop_duplicates('Ad name'))
    vl_as = (vl[['Ad set name','Funnel']]
               .dropna(subset=['Ad set name'])
               .drop_duplicates('Ad set name'))

    df_c = df_c.merge(vl_ad, on='Ad name', how='left', suffixes=('_x',''))
    df_c = df_c.merge(vl_as, on='Ad set name', how='left', suffixes=('_x',''))
    for col in ['Category','Format','Influencer','Funnel']:
        ox = col+'_x'
        if ox in df_c.columns:
            df_c[col] = df_c[col].fillna(df_c[ox])
            df_c.drop(columns=[ox], inplace=True)

    # ── daily data support ──────────────────────────────────────────────────
    DATE_ALIASES = ['Date', 'Day', 'Reporting starts', 'date_start']

    mo_map = dict(zip(MONTH_ORDER, MONTH_STARTS))
    old_keys = [f"{s.strftime('%Y-%m-%d')} - {e.strftime('%Y-%m-%d')}"
                for s, e in zip(MONTH_STARTS, MONTH_ENDS)]
    mo_map.update(dict(zip(old_keys, MONTH_STARTS)))

    def _parse_one(v):
        """Parse a single cell value to pd.Timestamp safely."""
        try:
            if v is None or (isinstance(v, float) and np.isnan(v)):
                return pd.NaT
            if isinstance(v, pd.Timestamp):
                return v
            if hasattr(v, 'date'):          # datetime.datetime / datetime.date
                return pd.Timestamp(v)
            s = str(v).strip()[:10]
            if not s or s.lower() == 'nat' or s.lower() == 'none':
                return pd.NaT
            return pd.Timestamp(s)
        except Exception:
            return pd.NaT

    def _process_dates(df):
        # 1. remove ALL duplicate column names (keep first occurrence)
        df = df.loc[:, ~df.columns.duplicated()].copy()

        # 2. drop redundant Meta date columns that duplicate 'Date'
        drop_these = [c for c in ['Reporting starts', 'Reporting ends',
                                   'Day', 'date_start', 'Month_Start',
                                   'Month', 'Is_Influencer', 'Frequency']
                      if c in df.columns]
        if drop_these:
            df = df.drop(columns=drop_these)

        # 3. if still no 'Date' col, try known aliases
        if 'Date' not in df.columns:
            for alias in ['Day', 'Reporting starts', 'date_start']:
                if alias in df.columns:
                    df = df.rename(columns={alias: 'Date'})
                    break

        # 4. parse Date column
        if 'Date' in df.columns:
            df['Date'] = df['Date'].apply(_parse_one)
            df['Month_Start'] = df['Date'].dt.to_period('M').dt.to_timestamp()
            df['Month'] = df['Date'].apply(
                lambda d: d.strftime('%b-%Y') if pd.notna(d) else '')
        elif 'Month' in df.columns:
            df['Month_Start'] = df['Month'].map(mo_map)
        else:
            df['Month_Start'] = pd.NaT
            df['Month'] = ''
        return df

    df_c = _process_dates(df_c)
    df_d = _process_dates(df_d)
    df_p = _process_dates(df_p)

    HAS_DAILY_DATA = 'Date' in df_c.columns and df_c['Date'].notna().any()
    if HAS_DAILY_DATA:
        DATA_MIN_DATE = df_c['Date'].min().date()
        DATA_MAX_DATE = df_c['Date'].max().date()
    else:
        DATA_MIN_DATE = MONTH_STARTS[0].date()
        DATA_MAX_DATE = MONTH_ENDS[-1].date()

    # influencer flag
    df_c['Is_Influencer'] = (
        df_c['Influencer'].notna() &
        (df_c['Influencer'].astype(str).str.strip() != '0') &
        (df_c['Influencer'].astype(str).str.strip() != 'nan') &
        (df_c['Influencer'].astype(str).str.strip() != '')
    )

    # frequency on campaign
    df_c['Frequency'] = (df_c['Impressions'] /
                          df_c['Reach'].replace(0, np.nan)).round(2)

    return df_c, df_d, df_p


def _agg(df, group_cols):
    agg_spec = dict(
        Spend       =('Amount spent (INR)', 'sum'),
        Revenue     =('Purchases conversion value', 'sum'),
        Purchases   =('Purchases', 'sum'),
        Impressions =('Impressions', 'sum'),
        Clicks      =('Link clicks', 'sum'),
        ATC         =('Adds to cart', 'sum'),
        IC          =('Checkouts initiated', 'sum'),
        Reach       =('Reach', 'sum'),
    )
    if 'Website landing page views' in df.columns:
        agg_spec['LPV'] = ('Website landing page views', 'sum')
    g = df.groupby(group_cols, dropna=False).agg(**agg_spec).reset_index()
    s = g['Spend'].replace(0, np.nan)
    g['ROAS']      = (g['Revenue'] / s).round(2)
    g['CPM']       = (g['Spend'] / g['Impressions'].replace(0,np.nan) * 1000).round(0)
    g['CTR']       = (g['Clicks'] / g['Impressions'].replace(0,np.nan) * 100).round(2)
    g['ATC_Rate']  = (g['ATC']  / g['Clicks'].replace(0,np.nan) * 100).round(2)
    g['IC_Rate']   = (g['IC']   / g['ATC'].replace(0,np.nan) * 100).round(2)
    g['CVR']       = (g['Purchases'] / g['Clicks'].replace(0,np.nan) * 100).round(2)
    g['CPA']       = (g['Spend'] / g['Purchases'].replace(0,np.nan)).round(0)
    g['AOV']       = (g['Revenue'] / g['Purchases'].replace(0,np.nan)).round(0)
    g['Frequency'] = (g['Impressions'] / g['Reach'].replace(0,np.nan)).round(2)
    return g


def build_aggregates(df_c, df_d, df_p, obj_filter=None, start=None, end=None):
    """Return dict of aggregated DataFrames for all dimensions."""

    def filt(df):
        d = df.copy()
        if obj_filter and obj_filter != 'All':
            d = d[d['Objective'].astype(str) == obj_filter]
        date_col = 'Date' if ('Date' in d.columns and d['Date'].notna().any()) else 'Month_Start'
        if start:
            d = d[d[date_col] >= pd.Timestamp(start)]
        if end:
            d = d[d[date_col] <= pd.Timestamp(end)]
        return d

    c  = filt(df_c)
    dd = filt(df_d)
    dp = filt(df_p)

    out = {}

    # --- account monthly ---
    out['account'] = _agg(c, ['Month','Month_Start']).sort_values('Month_Start')

    # --- funnel monthly ---
    out['funnel'] = _agg(c, ['Funnel','Month','Month_Start']).sort_values(['Funnel','Month_Start'])

    # --- category monthly ---
    out['category'] = _agg(c, ['Category','Month','Month_Start']).sort_values(['Category','Month_Start'])

    # --- format monthly ---
    out['format'] = _agg(c, ['Format','Month','Month_Start']).sort_values(['Format','Month_Start'])

    # --- influencer vs BAU ---
    out['inf_bau'] = _agg(c, ['Is_Influencer']).sort_values('Spend', ascending=False)

    # --- per influencer ---
    inf_rows = c[c['Is_Influencer'] == True]
    out['per_influencer'] = _agg(inf_rows, ['Influencer']).sort_values('Spend', ascending=False)

    # --- adset (top 60 by spend) ---
    adset_all = _agg(c, ['Ad set name','Funnel','Month','Month_Start'])
    adset_tot = _agg(c, ['Ad set name','Funnel']).sort_values('Spend', ascending=False).head(60)
    out['adset_total'] = adset_tot
    out['adset_monthly'] = adset_all

    # --- demographics ---
    out['demo'] = _agg(dd, ['Gender','Age','Month','Month_Start']).sort_values(['Gender','Age','Month_Start'])
    out['demo_total'] = _agg(dd, ['Gender','Age']).sort_values('Spend', ascending=False)

    # --- platform ---
    out['platform'] = _agg(dp, ['Platform','Placement','Month','Month_Start']).sort_values(['Platform','Placement','Month_Start'])
    out['platform_total'] = _agg(dp, ['Platform','Placement']).sort_values('Spend', ascending=False)

    # --- campaign total ---
    out['campaign_total'] = _agg(c, ['Campaign name','Funnel']).sort_values('Spend', ascending=False)

    # --- funnel total (no month) ---
    out['funnel_total'] = _agg(c, ['Funnel']).sort_values('Spend', ascending=False)

    # --- category total ---
    out['category_total'] = _agg(c, ['Category']).sort_values('Spend', ascending=False)

    # --- format total ---
    out['format_total'] = _agg(c, ['Format']).sort_values('Spend', ascending=False)

    return out
