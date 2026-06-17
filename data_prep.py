import json
import pandas as pd
import numpy as np

import os as _os, sys as _sys
_BASE = _os.path.dirname(_os.path.abspath(__file__))
def _p(name): return _os.path.join(_BASE, 'data', name)
_HERE        = _BASE
_REPO_EXCEL  = _os.path.join(_HERE, 'Meta Quarterly Performance Report.xlsx')
_LOCAL_EXCEL = r'C:\Users\Lenovo\OneDrive\Meta\Meta Quarterly Performance Report.xlsx'
# On Streamlit Cloud (Linux) always use repo path; on Windows prefer OneDrive
PATH = _REPO_EXCEL if (_sys.platform != 'win32' or _os.path.exists(_REPO_EXCEL)) else _LOCAL_EXCEL

EXCEL_PATH     = _p('NM_Offline_Monthly_Database.xlsx')
DASHBOARD_PATH = _p('NM_Offline_Store_Dashboard.xlsx')
CACHE_PATH     = _p('nm_sku_cache.json')

STORE_NAME_MAP = {'Nalasopara': 'Nalasopara (Capital Mall)'}

STORE_ORDER = [
    'Nalasopara (Capital Mall)', 'Palladium Mumbai', 'Palladium Ahmedabad',
    'Lakeshore Hyderabad', 'DLF Mall Plaza Delhi', 'Lulu Mall Lucknow', 'Abids Hyderabad',
]

STORE_SHORT = {
    'Nalasopara (Capital Mall)': 'Nalasopara',
    'Palladium Mumbai':          'Pal. Mumbai',
    'Palladium Ahmedabad':       'Pal. Ahmedabad',
    'Lakeshore Hyderabad':       'Lakeshore',
    'DLF Mall Plaza Delhi':      'DLF Delhi',
    'Lulu Mall Lucknow':         'Lulu Lucknow',
    'Abids Hyderabad':           'Abids',
}

STORE_COLORS = {
    'Nalasopara (Capital Mall)': '#1F77B4',
    'Palladium Mumbai':          '#FF7F0E',
    'Palladium Ahmedabad':       '#2CA02C',
    'Lakeshore Hyderabad':       '#D62728',
    'DLF Mall Plaza Delhi':      '#9467BD',
    'Lulu Mall Lucknow':         '#8C564B',
    'Abids Hyderabad':           '#E377C2',
}

CITY_MAP = {
    'Nalasopara (Capital Mall)': 'Vasai, Mumbai',
    'Palladium Mumbai':          'Lower Parel, Mumbai',
    'Palladium Ahmedabad':       'Ahmedabad',
    'Lakeshore Hyderabad':       'Hyderabad',
    'DLF Mall Plaza Delhi':      'Delhi',
    'Lulu Mall Lucknow':         'Lucknow',
    'Abids Hyderabad':           'Abids, Hyderabad',
}


def _month_sort_key(m):
    try:
        return pd.Period(str(m).strip(), freq='M')
    except Exception:
        return pd.Period('2099-01', freq='M')


def _period_label(p):
    try:
        return pd.Period(p, freq='M').strftime('%b %Y')
    except Exception:
        return str(p)


# ── Walk-ins & conversion from raw Store Performance sheet ────────────────────
def _load_walkins():
    sp = pd.read_excel(DASHBOARD_PATH, sheet_name='Store Performance', header=1)
    sp.columns = ['Store', 'City', 'Month', 'Walkins', 'Conversions',
                  'Net Sales_sp', 'Units_sp', 'Conv Rate', 'ASP_sp', 'EPT']
    sp['Store'] = sp['Store'].ffill()
    sp = sp.dropna(subset=['Month']).copy()
    sp['Store'] = sp['Store'].map(STORE_NAME_MAP).fillna(sp['Store'])
    for col in ['Walkins', 'Conversions', 'Conv Rate', 'EPT']:
        sp[col] = pd.to_numeric(sp[col], errors='coerce')
    return sp[['Store', 'Month', 'Walkins', 'Conversions', 'Conv Rate', 'EPT']]


# ── Cache monthly aggregates ──────────────────────────────────────────────────
def _load_cache_monthly():
    with open(CACHE_PATH, encoding='utf-8') as f:
        cache = json.load(f)
    rows = []
    for entry in cache['daily_sales']:
        store = STORE_NAME_MAP.get(entry['store'], entry['store'])
        dt    = pd.to_datetime(entry['date'])
        mstr  = dt.strftime('%b %Y')
        for it in entry['items']:
            rows.append({'Store': store, 'Month': mstr,
                         'Month_dt': dt.to_period('M'),
                         'Net': it['qty'] * it['net_price'],
                         'Qty': it['qty']})
    df = pd.DataFrame(rows)
    agg = (df.groupby(['Store', 'Month', 'Month_dt'])
             .agg(Net_Sales=('Net', 'sum'), Units=('Qty', 'sum'))
             .reset_index())
    agg['ASP'] = (agg['Net_Sales'] / agg['Units'].replace(0, np.nan)).round(0)
    return agg


# ── Spends from Dashboard ─────────────────────────────────────────────────────
_GOOGLE_ADS_JSON = _p('google_ads_store_spend.json')

def _load_spends():
    STORE_CODE = {
        'Nalasopara (Capital Mall)': 'CM',
        'Palladium Mumbai':          'MUM',
        'Palladium Ahmedabad':       'AMD',
        'Lakeshore Hyderabad':       'LKS',
        'DLF Mall Plaza Delhi':      'DLF',
    }
    def _sheet(name):
        df = pd.read_excel(DASHBOARD_PATH, sheet_name=name, header=2)
        df.columns = ['Month',
                      'CM_Spend','CM_Imp','CM_Clicks',
                      'MUM_Spend','MUM_Imp','MUM_Clicks',
                      'AMD_Spend','AMD_Imp','AMD_Clicks',
                      'LKS_Spend','LKS_Imp','LKS_Clicks',
                      'DLF_Spend','DLF_Imp','DLF_Clicks']
        df = df[df['Month'].notna() & ~df['Month'].astype(str).str.startswith('*')].iloc[1:].copy()
        return df

    meta = _sheet('Meta Spends')

    # Load live Google Ads spend from Windsor JSON
    try:
        import json as _json
        with open(_GOOGLE_ADS_JSON) as _f:
            _gads = pd.DataFrame(_json.load(_f))
        # pivot to dict: (store, month) -> spend
        _gads_lookup = {(r['Store'], r['MonthLabel']): r['Spend'] for _, r in _gads.iterrows()}
    except Exception:
        _gads_lookup = {}

    excel_months = set(str(mr['Month']).strip() for _, mr in meta.iterrows())

    rows = []
    for store, code in STORE_CODE.items():
        for _, mr in meta.iterrows():
            month = str(mr['Month']).strip()
            m_sp  = pd.to_numeric(mr.get(f'{code}_Spend'), errors='coerce') or 0
            m_imp = pd.to_numeric(mr.get(f'{code}_Imp'),   errors='coerce') or 0
            m_clk = pd.to_numeric(mr.get(f'{code}_Clicks'),errors='coerce') or 0
            g_sp  = _gads_lookup.get((store, month), 0) or 0
            rows.append({
                'Store': store, 'Month': month,
                'Meta Spend': m_sp or None,
                'Meta Impr':  m_imp or None,
                'Meta Clicks': m_clk or None,
                'Google Spend': g_sp or None,
                'Total Spend': (m_sp or 0) + (g_sp or 0) or None,
            })

    # Add all store+month combos from Google Ads that aren't covered by the Excel
    all_stores = set(STORE_CODE.keys()) | {'Lulu Mall Lucknow', 'Abids Hyderabad'}
    for (store, month), g_sp in _gads_lookup.items():
        if store not in all_stores:
            continue
        code = STORE_CODE.get(store)
        if code and month in excel_months:
            continue  # already added above
        rows.append({
            'Store': store, 'Month': month,
            'Meta Spend': None, 'Meta Impr': None, 'Meta Clicks': None,
            'Google Spend': g_sp,
            'Total Spend': g_sp,
        })

    return pd.DataFrame(rows)


# ── Main load ─────────────────────────────────────────────────────────────────
def load_monthly():
    cache_agg = _load_cache_monthly()
    walkins   = _load_walkins()
    spends    = _load_spends()

    # Merge cache monthly with walk-ins and spends
    df = cache_agg.merge(walkins, on=['Store', 'Month'], how='left')
    df = df.merge(spends,   on=['Store', 'Month'], how='left')

    # Fill city
    df['City'] = df['Store'].map(CITY_MAP)

    # Add Excel Dashboard-only months (walk-in data exists but no cache coverage)
    cache_keys = set(zip(cache_agg['Store'], cache_agg['Month']))

    sp_raw = pd.read_excel(DASHBOARD_PATH, sheet_name='Store Performance', header=1)
    sp_raw.columns = ['Store','City','Month','W','C','Net Sales','Units','CR','ASP','EPT_r']
    sp_raw['Store'] = sp_raw['Store'].ffill().map(STORE_NAME_MAP).fillna(sp_raw['Store'].ffill())
    sp_raw = sp_raw.dropna(subset=['Month']).copy()
    for col in ['Net Sales','Units','ASP']:
        sp_raw[col] = pd.to_numeric(sp_raw[col], errors='coerce')

    extra_rows = []
    for _, row in walkins.iterrows():
        if (row['Store'], row['Month']) in cache_keys:
            continue
        sp_m = sp_raw[(sp_raw['Store']==row['Store']) & (sp_raw['Month']==row['Month'])]
        sp2  = spends[(spends['Store']==row['Store']) & (spends['Month']==row['Month'])]
        extra_rows.append({
            'Store':       row['Store'],
            'Month':       row['Month'],
            'Month_dt':    _month_sort_key(row['Month']),
            'Net_Sales':   sp_m['Net Sales'].iloc[0] if not sp_m.empty else np.nan,
            'Units':       sp_m['Units'].iloc[0]     if not sp_m.empty else np.nan,
            'ASP':         sp_m['ASP'].iloc[0]       if not sp_m.empty else np.nan,
            'Walkins':     row['Walkins'],
            'Conversions': row['Conversions'],
            'Conv Rate':   row['Conv Rate'],
            'EPT':         row['EPT'],
            'Meta Spend':  sp2['Meta Spend'].iloc[0]   if not sp2.empty else np.nan,
            'Meta Impr':   sp2['Meta Impr'].iloc[0]    if not sp2.empty else np.nan,
            'Meta Clicks': sp2['Meta Clicks'].iloc[0]  if not sp2.empty else np.nan,
            'Google Spend':sp2['Google Spend'].iloc[0] if not sp2.empty else np.nan,
            'Total Spend': sp2['Total Spend'].iloc[0]  if not sp2.empty else np.nan,
            'City':        CITY_MAP.get(row['Store'], ''),
        })

    if extra_rows:
        df = pd.concat([df, pd.DataFrame(extra_rows)], ignore_index=True)

    df['Sales/Spend'] = (df['Net_Sales'] / df['Total Spend'].replace(0, np.nan)).round(2)
    df['Store_order'] = df['Store'].map({s: i for i, s in enumerate(STORE_ORDER)}).fillna(99)
    df = df.sort_values(['Store_order', 'Month_dt']).reset_index(drop=True)
    return df


def load_sku():
    df = pd.read_excel(EXCEL_PATH, sheet_name='SKU Sales by Store', header=3)
    df.columns = ['Store', 'Month', 'SKU', 'Units', 'Net Sales', 'MOP', 'Discount', 'ASP']
    df['Store'] = df['Store'].ffill().map(STORE_NAME_MAP).fillna(df['Store'].ffill())
    df = df[df['SKU'].notna() & ~df['SKU'].isin(['Store', 'SKU'])].copy()
    # Drop junk rows: SKU starts with punctuation or contains note-like phrases
    df = df[~df['SKU'].astype(str).str.match(r'^[^A-Za-z0-9]')].copy()
    df = df[~df['SKU'].astype(str).str.contains(r'(?i)please|find|dsr|note', regex=True)].copy()
    for col in ['Units', 'Net Sales', 'MOP', 'Discount', 'ASP']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df[df['Units'].notna() & (df['Units'] > 0)].copy()
    df['Month_dt'] = df['Month'].apply(_month_sort_key)
    return df


def load_daily():
    with open(CACHE_PATH, encoding='utf-8') as f:
        cache = json.load(f)
    rows = []
    for entry in cache['daily_sales']:
        store = STORE_NAME_MAP.get(entry['store'], entry['store'])
        date  = pd.to_datetime(entry['date'])
        for it in entry['items']:
            rows.append({
                'Store': store, 'Date': date,
                'Month': date.strftime('%b %Y'),
                'Month_dt': date.to_period('M'),
                'SKU': it['sku'], 'Qty': it['qty'],
                'Net': it['qty'] * it['net_price'],
                'MOP': it.get('mop', it['net_price']),
                'Discount': it.get('discount', 0),
            })
    return pd.DataFrame(rows)


def load_all():
    return load_monthly(), load_sku(), load_daily()


# ── Insight helpers ───────────────────────────────────────────────────────────
def generate_insights(monthly, sku):
    insights = []
    df = monthly.copy()

    # Top store by cumulative sales
    store_totals = df.groupby('Store')['Net_Sales'].sum().sort_values(ascending=False)
    top_store = store_totals.index[0]
    insights.append({
        'type': 'top',
        'title': f"🏆 {STORE_SHORT.get(top_store, top_store)} leads overall",
        'body': f"₹{store_totals.iloc[0]/1e5:.1f}L cumulative net sales — "
                f"{store_totals.iloc[0]/store_totals.sum()*100:.0f}% of network total."
    })

    # Best Sales/Spend ratio store (min 2 months of spend data)
    spend_df = df[df['Total Spend'].notna() & (df['Total Spend'] > 0)]
    if not spend_df.empty:
        roas_by_store = (spend_df.groupby('Store')
                         .apply(lambda x: x['Net_Sales'].sum() / x['Total Spend'].sum())
                         .sort_values(ascending=False))
        if len(roas_by_store):
            best_roas_store = roas_by_store.index[0]
            insights.append({
                'type': 'efficiency',
                'title': f"💰 {STORE_SHORT.get(best_roas_store, best_roas_store)} most spend-efficient",
                'body': f"Generates ₹{roas_by_store.iloc[0]:.1f} per ₹1 of ad spend — "
                        f"best in network."
            })

    # MoM trend for latest month
    months = sorted(df['Month_dt'].unique())
    if len(months) >= 2:
        cur_m, prev_m = months[-1], months[-2]
        cur  = df[df['Month_dt'] == cur_m].groupby('Store')['Net_Sales'].sum()
        prev = df[df['Month_dt'] == prev_m].groupby('Store')['Net_Sales'].sum()
        mom  = ((cur - prev) / prev.replace(0, np.nan) * 100).dropna().sort_values()
        if len(mom):
            worst_store = mom.index[0]
            best_store  = mom.index[-1]
            insights.append({
                'type': 'trend',
                'title': f"📉 {STORE_SHORT.get(worst_store, worst_store)} sharpest MoM drop",
                'body': f"{_period_label(cur_m)}: {mom.iloc[0]:+.0f}% vs {_period_label(prev_m)}. "
                        f"Typical mid-month pattern for partial DSR data."
            })
            if best_store != worst_store:
                insights.append({
                    'type': 'trend',
                    'title': f"📈 {STORE_SHORT.get(best_store, best_store)} best MoM growth",
                    'body': f"{_period_label(cur_m)}: {mom.iloc[-1]:+.0f}% vs {_period_label(prev_m)}."
                })

    # Highest ASP store
    asp_df = df[df['ASP'].notna() & (df['ASP'] > 0)]
    if not asp_df.empty:
        asp_by_store = asp_df.groupby('Store')['ASP'].mean().sort_values(ascending=False)
        high_asp = asp_by_store.index[0]
        insights.append({
            'type': 'product',
            'title': f"🎯 {STORE_SHORT.get(high_asp, high_asp)} highest avg ASP",
            'body': f"₹{asp_by_store.iloc[0]:,.0f} average selling price — "
                    f"customers buying premium SKUs here."
        })

    # Best conversion store
    conv_df = df[df['Conv Rate'].notna() & (df['Conv Rate'] > 0)]
    if not conv_df.empty:
        conv_by_store = conv_df.groupby('Store')['Conv Rate'].mean().sort_values(ascending=False)
        best_conv = conv_by_store.index[0]
        insights.append({
            'type': 'conversion',
            'title': f"🔁 {STORE_SHORT.get(best_conv, best_conv)} best conversion rate",
            'body': f"{conv_by_store.iloc[0]*100:.1f}% avg walk-in to purchase — "
                    f"best floor sales execution."
        })

    # Top SKU network-wide
    if not sku.empty:
        top_sku = sku.groupby('SKU')['Net Sales'].sum().sort_values(ascending=False)
        if len(top_sku):
            insights.append({
                'type': 'product',
                'title': f"🛍️ Top SKU: {top_sku.index[0]}",
                'body': f"₹{top_sku.iloc[0]/1e5:.1f}L net sales across all stores."
            })

    # Store with no spend data (missing ad tracking)
    no_spend = [s for s in df['Store'].unique() if df[df['Store']==s]['Total Spend'].isna().all()]
    if no_spend:
        names = ', '.join(STORE_SHORT.get(s, s) for s in no_spend)
        insights.append({
            'type': 'warning',
            'title': f"⚠️ No ad spend tracked: {names}",
            'body': "These stores have no Meta/Google spend data linked yet. "
                    "Sales/Spend ratio cannot be computed."
        })

    return insights
