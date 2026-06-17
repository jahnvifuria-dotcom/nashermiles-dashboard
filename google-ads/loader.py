import os
import pandas as pd
import streamlit as st
from pathlib import Path

# ── Data source: Parquet (cloud) or Excel (local) ─────────────────────────────
_HERE = Path(__file__).parent
PARQUET_FOLDER = _HERE / "data"

# Fall back to local Excel if parquet files don't exist (local dev mode)
_USE_PARQUET = (PARQUET_FOLDER / "campaign_performance.parquet").exists()

FOLDER = os.getenv(
    'GOOGLE_ADS_EXCEL_FOLDER',
    r'C:\Users\Lenovo\OneDrive\Google Ads'
)

# ── Parquet file map ──────────────────────────────────────────────────────────
_PARQUET_FILES = {
    'campaign_performance': 'campaign_performance.parquet',
    'brand_search':         'brand_search.parquet',
    'pmax_search':          'pmax_search.parquet',
    'audiences':            'audiences.parquet',
    'landing_pages':        'landing_pages.parquet',
    'shopping':             'shopping.parquet',
    'demographics':         'demographics.parquet',
    'placements':           'placements.parquet',
    'geography':            'geography.parquet',
}

def _load_parquet(key: str) -> pd.DataFrame:
    path = PARQUET_FOLDER / _PARQUET_FILES[key]
    if path.exists():
        return pd.read_parquet(str(path), engine='pyarrow')
    return pd.DataFrame()

def _mtime(filename: str) -> float:
    """Return file modification time — used as cache key so data auto-refreshes after sync."""
    try:
        return os.path.getmtime(os.path.join(FOLDER, filename))
    except OSError:
        return 0.0

# ---------------------------------------------------------------------------
# Campaign classification
# ---------------------------------------------------------------------------

def classify_campaign(name: str, ctype: str) -> str:
    n = str(name).lower()
    t = str(ctype).lower()
    if 'offline' in n:
        return 'Offline'
    if ('yt' in n or 'youtube' in n or 'video view' in n or 'video_view' in n
            or t == 'video' or t.startswith('video')):
        return 'Video / Awareness'
    if 'competitor' in n:
        return 'Competitor Search'
    if 'retargeting' in n or 'wv90' in n or 'atc60' in n:
        return 'Demand Gen / Retargeting'
    if 'demand gen' in t or 'demand_gen' in n or 'tofu' in n:
        return 'Demand Gen / Retargeting'
    if 'performance max' in t or 'pmax' in n or 'performancemax' in n:
        return 'Performance Max'
    if 'generic' in n or 'non-branded' in n or 'non_branded' in n:
        return 'Generic Search'
    if 'brand' in n or 'shark' in n:
        return 'Branded Search'
    return 'Other'


# ---------------------------------------------------------------------------
# Loaders — each reads one sheet, renames to canonical columns
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_campaigns(_mtime: float = None) -> pd.DataFrame:
    # classifier-v2
    if _USE_PARQUET:
        df = _load_parquet('campaign_performance')
        df = df.rename(columns={'Campaign type': 'Campaign_Type', 'Conversion gaol': 'Goals',
                                'Impr.': 'Impressions', 'Currency code': 'Currency',
                                'Conv. value': 'Conv_Value', 'Conv. value / cost': 'ROAS'})
    else:
        path = os.path.join(FOLDER, 'Google Campaign Performance Report.xlsx')
        df = pd.read_excel(path, sheet_name='Google Campaign Performance Rep',
                           skiprows=2, engine='openpyxl')
        df.columns = ['Campaign', 'Campaign_Type', 'Goals', 'Day', 'Clicks', 'Impressions',
                      'Currency', 'Cost', 'Conversions', 'Conv_Value', 'ROAS']
    df = df.dropna(subset=['Campaign'])
    df['Day'] = pd.to_datetime(df['Day'], errors='coerce')
    df = df.dropna(subset=['Day'])
    for c in ['Clicks', 'Impressions', 'Cost', 'Conversions', 'Conv_Value', 'ROAS']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    df['Group'] = df.apply(lambda r: classify_campaign(r['Campaign'], r['Campaign_Type']), axis=1)
    return df


@st.cache_data(show_spinner=False)
def load_search_terms_brand(_mtime: float = None) -> pd.DataFrame:
    if _USE_PARQUET:
        df = _load_parquet('brand_search')
    else:
        path = os.path.join(FOLDER, 'Google ads Search Term Report.xlsx')
        df = pd.read_excel(path, sheet_name='Search keyword (1)', engine='openpyxl')
    rename = {
        'Search keyword': 'Keyword',
        'Search keyword status': 'Status',
        'Search keyword match type': 'Match_Type',
        'Campaign': 'Campaign',
        'Ad group': 'Ad_Group',
        'Day': 'Day',
        'Goals': 'Goals',
        'Clicks': 'Clicks',
        'Impr.': 'Impressions',
        'CTR': 'CTR',
        'Currency code': 'Currency',
        'Avg. CPC': 'CPC',
        'Cost': 'Cost',
        'Conversions': 'Conversions',
        'Cost / conv.': 'CPA',
        'Conv. rate': 'Conv_Rate',
        'Conv. value': 'Conv_Value',
    }
    df = df.rename(columns=rename)
    df['Day'] = pd.to_datetime(df['Day'], errors='coerce')
    for c in ['Clicks', 'Impressions', 'Cost', 'Conversions', 'Conv_Value', 'CPC', 'CTR']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    df['ROAS'] = df.apply(
        lambda r: round(r['Conv_Value'] / r['Cost'], 2) if r['Cost'] > 0 else 0, axis=1)
    df['Keyword_Group'] = 'Branded'
    return df


@st.cache_data(show_spinner=False)
def load_search_terms_pmax(_mtime: float = None) -> pd.DataFrame:
    if _USE_PARQUET:
        df = _load_parquet('pmax_search')
        df = df.rename(columns={
            'campaign_search_term_view_search_term': 'Keyword',
            'Search term': 'Keyword',
            'Campaign': 'Campaign', 'Day': 'Day',
            'Conversions': 'Conversions', 'Clicks': 'Clicks',
            'Conv. value': 'Conv_Value', 'Impr.': 'Impressions', 'Cost': 'Cost'})
        df = df[['Keyword','Campaign','Day','Conversions','Clicks','Conv_Value','Impressions','Cost']
               ].copy() if all(c in df.columns for c in ['Keyword','Campaign','Day']) else df
    else:
        path = os.path.join(FOLDER, 'Google Pmax Search Term Report.xlsx')
        usecols = [0, 3, 4, 6, 9, 11, 12, 14]
        df = pd.read_excel(path, sheet_name='Pmax Search Term Report',
                           skiprows=2, usecols=usecols, engine='openpyxl')
        df.columns = ['Keyword', 'Campaign', 'Day', 'Conversions', 'Clicks', 'Conv_Value', 'Impressions', 'Cost']
    df = df.dropna(subset=['Keyword'])
    df['Day'] = pd.to_datetime(df['Day'], errors='coerce')
    df = df.dropna(subset=['Day'])
    df['Day'] = df['Day'].astype('datetime64[ns]')
    for c in ['Clicks', 'Impressions', 'Cost', 'Conversions', 'Conv_Value']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    # Drop zero-spend rows early to cut memory
    df = df[df['Cost'] > 0]
    # Classify keyword group
    def _kw_group(kw):
        k = str(kw).lower()
        if any(b in k for b in ['nasher', 'nashermiles']):
            return 'Branded'
        if any(c in k for c in ['safari', 'american tourister', 'skybags', 'vip',
                                  'aristocrat', 'samsonite', 'mokobara']):
            return 'Competitor'
        return 'Generic'
    df['Keyword_Group'] = df['Keyword'].apply(_kw_group)
    # Pre-aggregate by Keyword + Keyword_Group + Day to cut row count drastically
    df = (df.groupby(['Keyword', 'Keyword_Group', 'Day'])
            .agg(Cost=('Cost', 'sum'), Clicks=('Clicks', 'sum'),
                 Conv_Value=('Conv_Value', 'sum'), Conversions=('Conversions', 'sum'))
            .reset_index())
    df['ROAS'] = (df['Conv_Value'] / df['Cost']).round(2).where(df['Cost'] > 0, 0)
    return df


@st.cache_data(show_spinner=False)
def load_audiences(_mtime: float = None) -> pd.DataFrame:
    if _USE_PARQUET:
        df = _load_parquet('audiences')
    else:
        path = os.path.join(FOLDER, 'Google Audiences Reports.xlsx')
        df = pd.read_excel(path, sheet_name='Audiences - reporting', engine='openpyxl')
    rename = {
        'Audience segment': 'Audience',
        'Funnel': 'Funnel',
        'Audience segment state': 'Status',
        'Campaign': 'Campaign',
        'Ad group': 'Ad_Group',
        'Day': 'Day',
        'Goal': 'Goals',
        'Clicks': 'Clicks',
        'Impr.': 'Impressions',
        'Currency code': 'Currency',
        'Cost': 'Cost',
        'Conv. value': 'Conv_Value',
        'Conversions': 'Conversions',
    }
    df = df.rename(columns=rename)
    df['Day'] = pd.to_datetime(df['Day'], errors='coerce')
    for c in ['Clicks', 'Impressions', 'Cost', 'Conversions', 'Conv_Value']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    df['ROAS'] = df.apply(
        lambda r: round(r['Conv_Value'] / r['Cost'], 2) if r['Cost'] > 0 else 0, axis=1)
    return df


@st.cache_data(show_spinner=False)
def load_landing_pages(_mtime: float = None) -> pd.DataFrame:
    if _USE_PARQUET:
        df = _load_parquet('landing_pages')
        df = df.rename(columns={
            'expanded_landing_page_view_expanded_final_url': 'URL',
            'Landing page': 'URL', 'Shortened LP': 'Short_URL', 'Type of LP': 'Page_Type',
            'Day': 'Day', 'Clicks': 'Clicks', 'Impr.': 'Impressions',
            'Cost': 'Cost', 'Conv. value': 'Conv_Value', 'Conversions': 'Conversions'})
        if 'Short_URL' not in df.columns: df['Short_URL'] = df.get('URL', '')
        if 'Page_Type' not in df.columns: df['Page_Type'] = ''
    else:
        path = os.path.join(FOLDER, 'Google Landing Page Report.xlsx')
        usecols = [0, 1, 2, 4, 6, 7, 9, 10, 11]
        df = pd.read_excel(path, sheet_name='Landing pages Report (5)',
                           usecols=usecols, engine='openpyxl')
        df.columns = ['URL', 'Short_URL', 'Page_Type', 'Day', 'Clicks', 'Impressions', 'Cost', 'Conv_Value', 'Conversions']
    df['Day'] = pd.to_datetime(df['Day'], errors='coerce')
    df = df.dropna(subset=['Day'])
    df['Day'] = df['Day'].astype('datetime64[ns]')
    for c in ['Clicks', 'Impressions', 'Cost', 'Conversions', 'Conv_Value']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    # Drop zero rows early
    df = df[(df['Cost'] > 0) | (df['Clicks'] > 0)]
    df['Display_URL'] = df['Short_URL'].fillna(df['URL']).apply(
        lambda u: str(u).replace('https://nashermiles.com', ''))
    # Pre-aggregate by page + day
    df = (df.groupby(['Display_URL', 'Page_Type', 'Day'])
            .agg(Cost=('Cost', 'sum'), Clicks=('Clicks', 'sum'),
                 Conv_Value=('Conv_Value', 'sum'), Conversions=('Conversions', 'sum'))
            .reset_index())
    df['ROAS'] = (df['Conv_Value'] / df['Cost']).round(2).where(df['Cost'] > 0, 0)
    df['Conv_Rate'] = (df['Conversions'] / df['Clicks'] * 100).round(2).where(df['Clicks'] > 0, 0)
    return df


@st.cache_data(show_spinner=False)
def load_placements() -> pd.DataFrame:
    if _USE_PARQUET:
        df = _load_parquet('placements')
        df = df.rename(columns={
            'group_placement_view_display_name': 'Placement',
            'Placement (group)': 'Placement', 'Placement type (group)': 'Placement_Type',
            'group_placement_view_placement_type': 'Placement_Type',
            'Day': 'Day', 'video_trueview_views': 'Views', 'TrueView views': 'Views',
            'Clicks': 'Clicks', 'Impr.': 'Impressions',
            'Cost': 'Cost', 'Conv. value': 'Conv_Value', 'Conversions': 'Conversions'})
        if 'Views' not in df.columns: df['Views'] = 0
    else:
        path = os.path.join(FOLDER, 'Google Placements Report.xlsx')
        usecols = [0, 1, 4, 6, 7, 8, 10, 11, 12]
        df = pd.read_excel(path, sheet_name='Placements Report',
                           usecols=usecols, engine='openpyxl')
        df.columns = ['Placement', 'Placement_Type', 'Day', 'Views', 'Clicks', 'Impressions', 'Cost', 'Conv_Value', 'Conversions']
    # Placement column can have stray ints/datetimes from openpyxl — cast to str
    df['Placement'] = df['Placement'].astype(str)
    df = df[~df['Placement'].str.contains('no longer available', case=False, na=False)]
    # Also remove placeholder ' --' placement-type rows
    df = df[~df['Placement_Type'].astype(str).str.strip().isin(['--', ''])]
    df['Day'] = pd.to_datetime(df['Day'], errors='coerce')
    df = df.dropna(subset=['Day'])
    for c in ['Clicks', 'Impressions', 'Cost', 'Conversions', 'Conv_Value', 'Views']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    df = df[(df['Cost'] > 0) | (df['Views'] > 0)]
    # Pre-aggregate by placement + day
    df = (df.groupby(['Placement', 'Placement_Type', 'Day'])
            .agg(Cost=('Cost', 'sum'), Clicks=('Clicks', 'sum'), Views=('Views', 'sum'),
                 Conv_Value=('Conv_Value', 'sum'), Conversions=('Conversions', 'sum'))
            .reset_index())
    df['ROAS'] = (df['Conv_Value'] / df['Cost']).round(2).where(df['Cost'] > 0, 0)
    return df


@st.cache_data(show_spinner=False)
def load_shopping() -> pd.DataFrame:
    if _USE_PARQUET:
        df = _load_parquet('shopping')
    else:
        path = os.path.join(FOLDER, 'Shopping Placment - Pmax ^0  Shopping Campaign.xlsx')
        df = pd.read_excel(path, sheet_name='Shopping products - Shopping Ca', engine='openpyxl')
    rename = {
        'Item ID': 'Item_ID',
        'Product type (1st level)': 'Product_Type',
        'Product Title': 'Product_Title',
        'Collection Name': 'Collection',
        'Campaign': 'Campaign',
        'Conversion Goals': 'Goals',
        'Date': 'Day',
        'Clicks': 'Clicks',
        'Impr.': 'Impressions',
        'Currency code': 'Currency',
        'Cost': 'Cost',
        'Conversions': 'Conversions',
        'Conv. value': 'Conv_Value',
    }
    df = df.rename(columns=rename)
    df['Day'] = pd.to_datetime(df['Day'], errors='coerce')
    for c in ['Clicks', 'Impressions', 'Cost', 'Conversions', 'Conv_Value']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    df['ROAS'] = df.apply(
        lambda r: round(r['Conv_Value'] / r['Cost'], 2) if r['Cost'] > 0 else 0, axis=1)
    # Clean up " --" placeholder rows
    df = df[df['Item_ID'].astype(str).str.strip() != '--']
    df = df.dropna(subset=['Product_Title'])
    # Normalise category
    def _cat(pt):
        p = str(pt).lower()
        if 'backpack' in p:
            return 'Backpacks'
        if 'set' in p or 'luggage set' in p:
            return 'Luggage Sets'
        if 'hardside' in p or 'hard side' in p or 'hard-side' in p:
            return 'Hardside Luggage'
        if 'softside' in p or 'soft side' in p:
            return 'Softside Luggage'
        return 'Other'
    df['Category'] = df['Product_Type'].apply(_cat)
    return df


@st.cache_data(show_spinner=False)
def load_demographics() -> pd.DataFrame:
    if _USE_PARQUET:
        df = _load_parquet('demographics')
        df = df.rename(columns={
            'Age': 'Age', 'age_range_type': 'Age',
            'Gender': 'Gender', 'gender_type': 'Gender',
            'Parental status': 'Parental_Status', 'parental_status_type': 'Parental_Status',
            'Campaign': 'Campaign', 'Day': 'Day',
            'Clicks': 'Clicks', 'Impr.': 'Impressions', 'CTR': 'CTR',
            'Currency code': 'Currency', 'account_currency_code': 'Currency',
            'Avg. CPC': 'CPC', 'average_cpc': 'CPC', 'Cost': 'Cost',
            'Conv. rate': 'Conv_Rate', 'conversions_from_interactions_rate': 'Conv_Rate',
            'Conversions': 'Conversions', 'Cost / conv.': 'CPA', 'cost_per_conversion': 'CPA',
            'Conv. value': 'Conv_Value', 'conversion_value': 'Conv_Value'})
        for col in ['Parental_Status', 'Goals', 'CTR', 'CPC', 'Conv_Rate', 'CPA']:
            if col not in df.columns: df[col] = None
    else:
        path = os.path.join(FOLDER, 'Google Demographic Report.xlsx')
        df = pd.read_excel(path, sheet_name='Demographic Report',
                           skiprows=2, engine='openpyxl')
        df.columns = ['Age', 'Gender', 'Parental_Status', 'Campaign', 'Goals',
                      'Day', 'Clicks', 'Impressions', 'CTR', 'Currency',
                      'CPC', 'Cost', 'Conv_Rate', 'Conversions', 'CPA', 'Conv_Value']
    df = df.dropna(subset=['Age'])
    df['Day'] = pd.to_datetime(df['Day'], errors='coerce')
    for c in ['Clicks', 'Impressions', 'Cost', 'Conversions', 'Conv_Value', 'CPC', 'CTR']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    df['ROAS'] = df.apply(
        lambda r: round(r['Conv_Value'] / r['Cost'], 2) if r['Cost'] > 0 else 0, axis=1)
    return df


@st.cache_data(show_spinner=False)
def load_geography() -> pd.DataFrame:
    if _USE_PARQUET:
        df = _load_parquet('geography')
        df = df.rename(columns={
            'City (Matched)': 'City', 'city': 'City',
            'State (Matched)': 'State', 'region': 'State',
            'Day': 'Day', 'Clicks': 'Clicks', 'Impr.': 'Impressions',
            'Cost': 'Cost', 'Conversions': 'Conversions'})
    else:
        path = os.path.join(FOLDER, 'Google Ads Geography Level Report.xlsx')
        usecols = [0, 1, 2, 5, 6, 10, 12]
        df = pd.read_excel(path, sheet_name='Geography Level Report',
                           skiprows=2, usecols=usecols, engine='openpyxl')
        df.columns = ['City', 'State', 'Day', 'Clicks', 'Impressions', 'Cost', 'Conversions']
    df = df.dropna(subset=['City'])
    df['Day'] = pd.to_datetime(df['Day'], errors='coerce')
    df = df.dropna(subset=['Day'])
    df['Day'] = df['Day'].astype('datetime64[ns]')
    for c in ['Clicks', 'Impressions', 'Cost', 'Conversions']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    df = df[(df['Cost'] > 0) | (df['Clicks'] > 0)]
    # Pre-aggregate by city + state + day
    df = (df.groupby(['City', 'State', 'Day'])
            .agg(Cost=('Cost', 'sum'), Clicks=('Clicks', 'sum'),
                 Conversions=('Conversions', 'sum'))
            .reset_index())
    return df


# ---------------------------------------------------------------------------
# Shared filter helpers
# ---------------------------------------------------------------------------

def filter_dates(df: pd.DataFrame, start, end, col='Day') -> pd.DataFrame:
    mask = (df[col] >= pd.Timestamp(start)) & (df[col] <= pd.Timestamp(end))
    return df[mask]


def filter_goals(df: pd.DataFrame, goals: list, col='Goals') -> pd.DataFrame:
    if not goals or col not in df.columns:
        return df
    pattern = '|'.join(goals)
    return df[df[col].astype(str).str.contains(pattern, case=False, na=False)]
