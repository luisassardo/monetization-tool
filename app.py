"""
Monetization Tool API - Backend for Meta Monetization Data Explorer
A J-Lab tool (monetizacion.j-lab.tools). Data: monetization.wtf / WHAT TO FIX.
Deployable on Render, Railway, or any Python hosting platform.
"""

from flask import Flask, jsonify, request, render_template, make_response
from flask_cors import CORS
import pandas as pd
import os
import json
from datetime import datetime
import re

try:
    import anthropic
except ImportError:  # keep the app runnable without the SDK (falls back to local engine)
    anthropic = None

app = Flask(__name__)
CORS(app)  # Enable CORS for widget embedding

# ==================== CONFIG ====================
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '').strip()
ANTHROPIC_MODEL = os.environ.get('ANTHROPIC_MODEL', 'claude-haiku-4-5')
MAX_TOOL_TURNS = int(os.environ.get('AI_MAX_TOOL_TURNS', '6'))
AI_ENABLED = bool(ANTHROPIC_API_KEY) and anthropic is not None

_anthropic_client = (
    anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if AI_ENABLED else None
)

# Load data
DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'accounts.csv')

PROGRAM_COLS = {
    'Instant Articles': 'facebook_instant_articles_session_count',
    'In-Stream Ads': 'facebook_in_stream_ads_session_count',
    'Ads on Reels': 'facebook_ads_on_reels_session_count',
    'Content Monetization': 'facebook_content_monetization_session_count',
}


def load_data():
    """Load and preprocess the CSV data"""
    df = pd.read_csv(DATA_PATH)
    # Guard against a stray duplicated-header row in the source data
    df = df[df['admin_location'] != 'admin_location']
    # Convert verified to boolean
    df['account_verified'] = df['account_verified'].astype(str).str.lower() == 'true'
    # Convert subscriber count to int
    df['account_subscriber_count'] = pd.to_numeric(df['account_subscriber_count'], errors='coerce').fillna(0).astype(int)
    # Convert session counts to int
    for col in PROGRAM_COLS.values():
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
    # Parse dates
    for col in ['page_created_date', 'first_recorded_monetization', 'last_recorded_monetization', 'last_onboarding']:
        df[col] = pd.to_datetime(df[col], errors='coerce')
    return df


# Global data cache
try:
    DATA = load_data()
except Exception as e:
    print(f"Error loading data: {e}")
    DATA = pd.DataFrame()


# ==================== i18n ====================
I18N = {
    'es': {
        'lang': 'es',
        'title': 'Cuentas monetizadas por Meta en América Latina',
        'subtitle': 'Archivo de monetización · Facebook & Instagram',
        'kicker': 'J-LAB · HERRAMIENTA DE DATOS',
        'stat_total': 'Cuentas',
        'stat_subscribers': 'Suscriptores',
        'stat_verified': 'Verificadas',
        'stat_active': 'Activas (90 días)',
        'chat_title': 'Pregúntale a los datos',
        'chat_sub': 'Asistente con IA · respuestas basadas en la base de datos',
        'chat_placeholder': 'Pregunta sobre los datos… ej: "¿Cuáles son las 10 cuentas mayores en Guatemala?"',
        'chat_send': 'Enviar',
        'chat_hint': '⏎ enviar · ⇧⏎ nueva línea',
        'chat_thinking': 'Analizando…',
        'chat_examples': ['Top 10 cuentas', 'Cuentas verificadas', 'Cuentas por país', 'Programas de monetización', 'Estadísticas generales'],
        'badge_claude': 'IA · respuesta basada en datos',
        'badge_local': 'motor local · sin IA',
        'analysis_title': 'Análisis para investigación',
        'analysis_sub': 'Señales de historia calculadas sobre los datos. Son pistas, no veredictos.',
        'an_bursts_title': 'Ráfagas coordinadas',
        'an_bursts_desc': 'Cuentas creadas el mismo día en el mismo país — posible coordinación.',
        'an_migration_title': 'Migración de programas',
        'an_migration_desc': 'Cómo cambió el uso de programas según el año de creación.',
        'an_verified_title': 'Brecha de verificación',
        'an_verified_desc': 'Cuentas no verificadas que reciben ingresos de Meta, por país.',
        'an_asymmetry_title': 'Asimetría entre países',
        'an_asymmetry_desc': 'Métricas normalizadas por país para comparar de forma justa.',
        'an_outliers_title': 'Crecimiento atípico',
        'an_outliers_desc': 'Páginas jóvenes con audiencias inusualmente grandes.',
        'chart_locations': 'Cuentas por país',
        'chart_monetization': 'Programas de monetización',
        'chart_timeline': 'Creación de cuentas por año',
        'chart_top': 'Top 10 por suscriptores',
        'table_title': 'Explorar cuentas',
        'col_name': 'Cuenta',
        'col_location': 'País',
        'col_subs': 'Suscriptores',
        'col_verified': 'Verif.',
        'col_created': 'Creada',
        'col_lang': 'Idioma',
        'search_ph': 'Buscar por nombre, handle o ID…',
        'filter_all_loc': 'Todos los países',
        'filter_all_lang': 'Todos los idiomas',
        'filter_verified': 'Solo verificadas',
        'prev': 'Anterior',
        'next': 'Siguiente',
        'loading': 'Cargando…',
        'view_account': 'Ver cuenta',
        'back': 'Volver',
        'footer_data': 'Datos: monetization.wtf · WHAT TO FIX (con apoyo de Luminate) · CC BY-ND 4.0',
        'footer_tool': 'Herramienta J-Lab · con atribución a Vector Crítico',
        'no_results': 'Sin resultados',
        'accounts_unit': 'cuentas',
        'subs_unit': 'suscriptores',
    },
    'en': {
        'lang': 'en',
        'title': 'Accounts monetized by Meta in Latin America',
        'subtitle': 'Monetization archive · Facebook & Instagram',
        'kicker': 'J-LAB · DATA TOOL',
        'stat_total': 'Accounts',
        'stat_subscribers': 'Subscribers',
        'stat_verified': 'Verified',
        'stat_active': 'Active (90 days)',
        'chat_title': 'Ask the data',
        'chat_sub': 'AI assistant · answers grounded in the database',
        'chat_placeholder': 'Ask about the data… e.g. "What are the 10 largest accounts in Guatemala?"',
        'chat_send': 'Send',
        'chat_hint': '⏎ send · ⇧⏎ newline',
        'chat_thinking': 'Analyzing…',
        'chat_examples': ['Top 10 accounts', 'Verified accounts', 'Accounts by country', 'Monetization programs', 'Overall stats'],
        'badge_claude': 'AI · grounded in data',
        'badge_local': 'local engine · no AI',
        'analysis_title': 'Analysis for reporting',
        'analysis_sub': 'Story signals computed over the data. These are leads, not verdicts.',
        'an_bursts_title': 'Coordinated bursts',
        'an_bursts_desc': 'Accounts created the same day in the same country — possible coordination.',
        'an_migration_title': 'Program migration',
        'an_migration_desc': 'How program usage shifted by account creation year.',
        'an_verified_title': 'Verification gap',
        'an_verified_desc': 'Unverified accounts pulling Meta revenue, by country.',
        'an_asymmetry_title': 'Country asymmetry',
        'an_asymmetry_desc': 'Per-country normalized metrics for a fair comparison.',
        'an_outliers_title': 'Growth outliers',
        'an_outliers_desc': 'Young pages with unusually large audiences.',
        'chart_locations': 'Accounts by country',
        'chart_monetization': 'Monetization programs',
        'chart_timeline': 'Account creation by year',
        'chart_top': 'Top 10 by subscribers',
        'table_title': 'Explore accounts',
        'col_name': 'Account',
        'col_location': 'Country',
        'col_subs': 'Subscribers',
        'col_verified': 'Verif.',
        'col_created': 'Created',
        'col_lang': 'Language',
        'search_ph': 'Search by name, handle or ID…',
        'filter_all_loc': 'All countries',
        'filter_all_lang': 'All languages',
        'filter_verified': 'Verified only',
        'prev': 'Previous',
        'next': 'Next',
        'loading': 'Loading…',
        'view_account': 'View account',
        'back': 'Back',
        'footer_data': 'Data: monetization.wtf · WHAT TO FIX (supported by Luminate) · CC BY-ND 4.0',
        'footer_tool': 'A J-Lab tool · with attribution to Vector Crítico',
        'no_results': 'No results',
        'accounts_unit': 'accounts',
        'subs_unit': 'subscribers',
    },
}


def resolve_lang():
    """Resolve language: ?lang= -> cookie -> Accept-Language -> 'es'."""
    lang = request.args.get('lang')
    if lang not in ('es', 'en'):
        lang = request.cookies.get('lang')
    if lang not in ('es', 'en'):
        al = request.headers.get('Accept-Language', '')
        lang = 'en' if al[:2].lower() == 'en' else 'es'
    return lang if lang in ('es', 'en') else 'es'


def render_localized(template, **ctx):
    """render_template with lang/t injected and a lang cookie set when ?lang= is used."""
    lang = resolve_lang()
    resp = make_response(render_template(template, lang=lang, t=I18N[lang], **ctx))
    if request.args.get('lang') in ('es', 'en'):
        resp.set_cookie('lang', lang, max_age=60 * 60 * 24 * 365, samesite='Lax')
    return resp


# ==================== PAGE ROUTES ====================

@app.route('/')
def index():
    """Main dashboard page"""
    return render_localized('index.html')


@app.route('/cuenta/<account_id>')
def account_detail(account_id):
    """Individual account detail page"""
    return render_localized('account.html', account_id=account_id)


@app.route('/widget')
def widget():
    """Embeddable widget version"""
    return render_localized('widget.html')


# ==================== DATA API ROUTES ====================

@app.route('/api/stats')
def get_stats():
    """Get overall statistics"""
    if DATA.empty:
        return jsonify({'error': 'No data available'}), 500

    stats = {
        'total_accounts': len(DATA),
        'total_subscribers': int(DATA['account_subscriber_count'].sum()),
        'verified_accounts': int(DATA['account_verified'].sum()),
        'avg_subscribers': int(DATA['account_subscriber_count'].mean()),
        'median_subscribers': int(DATA['account_subscriber_count'].median()),
        'languages': DATA['account_language'].value_counts().to_dict(),
        'locations': DATA['admin_location'].value_counts().to_dict(),
        'by_year': DATA.groupby(DATA['page_created_date'].dt.year).size().to_dict(),
        'monetization_active': int((DATA['last_recorded_monetization'] >= datetime.now() - pd.Timedelta(days=90)).sum()),
    }
    return jsonify(stats)


@app.route('/api/accounts')
def get_accounts():
    """Get paginated list of accounts with filters"""
    if DATA.empty:
        return jsonify({'error': 'No data available'}), 500

    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    per_page = min(per_page, 100)  # Max 100 per page

    # Filters
    search = request.args.get('search', '').lower()
    location = request.args.get('location', '')
    verified = request.args.get('verified', '')
    language = request.args.get('language', '')
    min_subs = request.args.get('min_subs', 0, type=int)

    # Sort
    sort_by = request.args.get('sort', 'account_subscriber_count')
    sort_order = request.args.get('order', 'desc')

    # Apply filters
    filtered = DATA.copy()

    if search:
        mask = (
            filtered['account_name'].str.lower().str.contains(search, na=False) |
            filtered['account_handle'].str.lower().str.contains(search, na=False) |
            filtered['account_id'].astype(str).str.contains(search, na=False)
        )
        filtered = filtered[mask]

    if location:
        filtered = filtered[filtered['admin_location'] == location]

    if verified:
        is_verified = verified.lower() == 'true'
        filtered = filtered[filtered['account_verified'] == is_verified]

    if language:
        filtered = filtered[filtered['account_language'] == language]

    if min_subs > 0:
        filtered = filtered[filtered['account_subscriber_count'] >= min_subs]

    # Sort
    if sort_by in filtered.columns:
        ascending = sort_order.lower() == 'asc'
        filtered = filtered.sort_values(by=sort_by, ascending=ascending, na_position='last')

    # Paginate
    total = len(filtered)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = filtered.iloc[start:end]

    # Format response
    accounts = []
    for _, row in paginated.iterrows():
        accounts.append({
            'account_id': str(row['account_id']),
            'account_name': row['account_name'],
            'account_handle': row['account_handle'] if pd.notna(row['account_handle']) else None,
            'account_verified': bool(row['account_verified']),
            'page_created_date': row['page_created_date'].strftime('%Y-%m-%d') if pd.notna(row['page_created_date']) else None,
            'account_subscriber_count': int(row['account_subscriber_count']),
            'account_language': row['account_language'],
            'admin_location': row['admin_location'],
            'first_recorded_monetization': row['first_recorded_monetization'].strftime('%Y-%m-%d') if pd.notna(row['first_recorded_monetization']) else None,
            'last_recorded_monetization': row['last_recorded_monetization'].strftime('%Y-%m-%d') if pd.notna(row['last_recorded_monetization']) else None,
            'facebook_url': f"https://facebook.com/{row['account_id']}"
        })

    return jsonify({
        'accounts': accounts,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page
    })


@app.route('/api/account/<account_id>')
def get_account(account_id):
    """Get single account details"""
    if DATA.empty:
        return jsonify({'error': 'No data available'}), 500

    account = DATA[DATA['account_id'].astype(str) == str(account_id)]

    if account.empty:
        return jsonify({'error': 'Account not found'}), 404

    row = account.iloc[0]

    return jsonify({
        'account_id': str(row['account_id']),
        'account_name': row['account_name'],
        'account_handle': row['account_handle'] if pd.notna(row['account_handle']) else None,
        'account_verified': bool(row['account_verified']),
        'page_created_date': row['page_created_date'].strftime('%Y-%m-%d') if pd.notna(row['page_created_date']) else None,
        'account_subscriber_count': int(row['account_subscriber_count']),
        'account_language_code': row['account_language_code'],
        'account_language': row['account_language'],
        'admin_location_code': row['admin_location_code'],
        'admin_location': row['admin_location'],
        'last_onboarding': row['last_onboarding'].strftime('%Y-%m-%d') if pd.notna(row['last_onboarding']) else None,
        'first_recorded_monetization': row['first_recorded_monetization'].strftime('%Y-%m-%d') if pd.notna(row['first_recorded_monetization']) else None,
        'last_recorded_monetization': row['last_recorded_monetization'].strftime('%Y-%m-%d') if pd.notna(row['last_recorded_monetization']) else None,
        'facebook_instant_articles_session_count': int(row['facebook_instant_articles_session_count']) if pd.notna(row['facebook_instant_articles_session_count']) else 0,
        'facebook_in_stream_ads_session_count': int(row['facebook_in_stream_ads_session_count']) if pd.notna(row['facebook_in_stream_ads_session_count']) else 0,
        'facebook_ads_on_reels_session_count': int(row['facebook_ads_on_reels_session_count']) if pd.notna(row['facebook_ads_on_reels_session_count']) else 0,
        'facebook_content_monetization_session_count': int(row['facebook_content_monetization_session_count']) if pd.notna(row['facebook_content_monetization_session_count']) else 0,
        'facebook_url': f"https://facebook.com/{row['account_id']}"
    })


@app.route('/api/chart/locations')
def chart_locations():
    """Get location distribution for charts"""
    if DATA.empty:
        return jsonify({'error': 'No data available'}), 500

    location_data = DATA.groupby('admin_location').agg({
        'account_id': 'count',
        'account_subscriber_count': 'sum',
        'account_verified': 'sum'
    }).reset_index()
    location_data.columns = ['location', 'accounts', 'total_subscribers', 'verified']

    return jsonify(location_data.to_dict(orient='records'))


@app.route('/api/chart/timeline')
def chart_timeline():
    """Get account creation timeline for charts"""
    if DATA.empty:
        return jsonify({'error': 'No data available'}), 500

    timeline = DATA.groupby(DATA['page_created_date'].dt.to_period('Y')).agg({
        'account_id': 'count',
        'account_subscriber_count': 'sum'
    }).reset_index()
    timeline['page_created_date'] = timeline['page_created_date'].astype(str)
    timeline.columns = ['year', 'accounts', 'subscribers']

    return jsonify(timeline.to_dict(orient='records'))


@app.route('/api/chart/monetization')
def chart_monetization():
    """Get monetization program distribution"""
    if DATA.empty:
        return jsonify({'error': 'No data available'}), 500

    programs = {name: int(DATA[col].sum()) for name, col in PROGRAM_COLS.items()}
    accounts_per_program = {name: int((DATA[col] > 0).sum()) for name, col in PROGRAM_COLS.items()}

    return jsonify({
        'sessions': programs,
        'accounts': accounts_per_program
    })


@app.route('/api/filters')
def get_filters():
    """Get available filter options"""
    if DATA.empty:
        return jsonify({'error': 'No data available'}), 500

    return jsonify({
        'locations': sorted(DATA['admin_location'].dropna().unique().tolist()),
        'languages': sorted(DATA['account_language'].dropna().unique().tolist())
    })


# ==================== SAFE QUERY TOOLS ====================
# Pure, read-only functions over DATA. Returned dicts feed both the local
# keyword fallback and Claude's tool_result content. They never mutate DATA.

def _filter_location(df, location):
    if not location:
        return df
    loc = str(location).strip().lower()
    return df[(df['admin_location'].astype(str).str.lower() == loc) |
              (df['admin_location_code'].astype(str).str.lower() == loc)]


def _acct(row, fields=('account_id', 'account_name', 'subscribers', 'verified', 'location')):
    out = {}
    if 'account_id' in fields:
        out['account_id'] = str(row['account_id'])
    if 'account_name' in fields:
        out['account_name'] = row['account_name']
    if 'handle' in fields:
        out['account_handle'] = row['account_handle'] if pd.notna(row['account_handle']) else None
    if 'subscribers' in fields:
        out['subscribers'] = int(row['account_subscriber_count'])
    if 'verified' in fields:
        out['verified'] = bool(row['account_verified'])
    if 'location' in fields:
        out['location'] = row['admin_location']
    return out


def tool_top_accounts(n=10, location=None, verified_only=False):
    """Top accounts by subscriber count, optionally filtered by country/verified."""
    df = _filter_location(DATA, location)
    if verified_only:
        df = df[df['account_verified'] == True]
    n = max(1, min(int(n), 50))
    top = df.nlargest(n, 'account_subscriber_count')
    return {
        'count': int(len(top)),
        'filter_location': location,
        'verified_only': bool(verified_only),
        'accounts': [_acct(r, ('account_id', 'account_name', 'handle', 'subscribers', 'verified', 'location')) for _, r in top.iterrows()],
    }


def tool_verified_stats():
    """Counts and share of verified accounts plus the top verified accounts."""
    verified = DATA[DATA['account_verified'] == True]
    n_all = int(len(DATA))
    total = int(len(verified))
    top = verified.nlargest(5, 'account_subscriber_count')
    return {
        'verified': total,
        'total': n_all,
        'pct_verified': round(total / n_all * 100, 1) if n_all else 0.0,
        'top': [_acct(r) for _, r in top.iterrows()],
    }


def tool_by_location(country=None):
    """Per-country aggregate, or detail for a single country."""
    if country:
        df = _filter_location(DATA, country)
        if df.empty:
            return {'country': country, 'found': False}
        top = df.nlargest(5, 'account_subscriber_count')
        return {
            'country': df.iloc[0]['admin_location'],
            'found': True,
            'accounts': int(len(df)),
            'total_subscribers': int(df['account_subscriber_count'].sum()),
            'verified': int(df['account_verified'].sum()),
            'top': [_acct(r) for _, r in top.iterrows()],
        }
    agg = DATA.groupby('admin_location').agg(
        accounts=('account_id', 'count'),
        total_subscribers=('account_subscriber_count', 'sum'),
        verified=('account_verified', 'sum'),
    ).reset_index().sort_values('accounts', ascending=False)
    return {'by_location': [
        {'location': r['admin_location'], 'accounts': int(r['accounts']),
         'total_subscribers': int(r['total_subscribers']), 'verified': int(r['verified'])}
        for _, r in agg.iterrows()
    ]}


def tool_by_year(year=None):
    """Account-creation histogram by year, or detail for a single year."""
    yrs = DATA['page_created_date'].dt.year
    if year:
        year = int(year)
        d = DATA[yrs == year]
        if d.empty:
            return {'year': year, 'found': False}
        top = d.nlargest(5, 'account_subscriber_count')
        return {
            'year': year, 'found': True, 'accounts': int(len(d)),
            'total_subscribers': int(d['account_subscriber_count'].sum()),
            'avg_subscribers': int(d['account_subscriber_count'].mean()),
            'top': [_acct(r, ('account_name', 'subscribers')) for _, r in top.iterrows()],
        }
    hist = DATA.groupby(yrs).size()
    return {'by_year': [{'year': int(y), 'accounts': int(c)} for y, c in hist.items() if pd.notna(y)]}


def tool_by_monetization_program(program=None):
    """Accounts per monetization program + count active in the last 90 days."""
    counts = {name: int((DATA[col] > 0).sum()) for name, col in PROGRAM_COLS.items()}
    active90 = int((DATA['last_recorded_monetization'] >= datetime.now() - pd.Timedelta(days=90)).sum())
    out = {'programs': counts, 'active_last_90_days': active90}
    if program:
        pl = str(program).lower()
        match = next((name for name in PROGRAM_COLS if pl in name.lower() or name.lower() in pl), None)
        if match:
            col = PROGRAM_COLS[match]
            d = DATA[DATA[col] > 0]
            out['program_detail'] = {
                'program': match,
                'accounts': int(len(d)),
                'total_sessions': int(DATA[col].sum()),
            }
    return out


def tool_by_language(language=None):
    """Accounts per language, or detail for a single language."""
    vc = DATA['account_language'].value_counts()
    out = {'by_language': [{'language': str(l), 'accounts': int(c)} for l, c in vc.items()]}
    if language:
        ll = str(language).lower()
        d = DATA[DATA['account_language'].astype(str).str.lower().str.contains(ll, na=False)]
        out['language_detail'] = {'language': language, 'accounts': int(len(d))}
    return out


def tool_summary_stats():
    """Overall summary of the dataset."""
    return {
        'total_accounts': int(len(DATA)),
        'verified_accounts': int(DATA['account_verified'].sum()),
        'pct_verified': round(DATA['account_verified'].mean() * 100, 1) if len(DATA) else 0.0,
        'total_subscribers': int(DATA['account_subscriber_count'].sum()),
        'avg_subscribers': int(DATA['account_subscriber_count'].mean()) if len(DATA) else 0,
        'median_subscribers': int(DATA['account_subscriber_count'].median()) if len(DATA) else 0,
        'top_locations': [{'location': str(l), 'accounts': int(c)} for l, c in DATA['admin_location'].value_counts().head(5).items()],
        'top_languages': [{'language': str(l), 'accounts': int(c)} for l, c in DATA['account_language'].value_counts().head(5).items()],
    }


def tool_search_accounts(query, limit=10):
    """Substring search over account name / handle / id."""
    q = str(query or '').strip().lower()
    limit = max(1, min(int(limit), 25))
    if not q:
        return {'query': query, 'count': 0, 'matches': []}
    mask = (
        DATA['account_name'].astype(str).str.lower().str.contains(q, na=False, regex=False) |
        DATA['account_handle'].astype(str).str.lower().str.contains(q, na=False, regex=False) |
        DATA['account_id'].astype(str).str.contains(q, na=False, regex=False)
    )
    res = DATA[mask].nlargest(limit, 'account_subscriber_count')
    return {
        'query': query,
        'count': int(mask.sum()),
        'matches': [_acct(r, ('account_id', 'account_name', 'handle', 'subscribers', 'verified', 'location')) for _, r in res.iterrows()],
    }


TOOL_FUNCS = {
    'top_accounts': tool_top_accounts,
    'verified_stats': tool_verified_stats,
    'by_location': tool_by_location,
    'by_year': tool_by_year,
    'by_monetization_program': tool_by_monetization_program,
    'by_language': tool_by_language,
    'summary_stats': tool_summary_stats,
    'search_accounts': tool_search_accounts,
}


def run_tool(name, args):
    fn = TOOL_FUNCS.get(name)
    if not fn:
        return {'error': f'unknown tool {name}'}
    try:
        return fn(**(args or {}))
    except TypeError as e:
        return {'error': f'bad args: {e}'}
    except Exception as e:  # never let a tool crash the request
        return {'error': str(e)}


# ==================== LOCAL KEYWORD ENGINE (fallback) ====================

def _md_top(result, lang):
    head = 'Top {n} cuentas por suscriptores' if lang == 'es' else 'Top {n} accounts by subscribers'
    subs = 'suscriptores' if lang == 'es' else 'subscribers'
    out = f"**{head.format(n=result['count'])}:**\n\n"
    for i, a in enumerate(result['accounts'], 1):
        v = ' ✓' if a.get('verified') else ''
        out += f"{i}. **{a['account_name']}**{v} — {a['subscribers']:,} {subs} ({a.get('location','')})\n"
    return out


def _md_verified(result, lang):
    if lang == 'es':
        out = f"**Cuentas verificadas:** {result['verified']} de {result['total']} ({result['pct_verified']}%)\n\n**Top 5 verificadas:**\n"
    else:
        out = f"**Verified accounts:** {result['verified']} of {result['total']} ({result['pct_verified']}%)\n\n**Top 5 verified:**\n"
    for i, a in enumerate(result['top'], 1):
        out += f"{i}. {a['account_name']} — {a['subscribers']:,}\n"
    return out


def _md_location(result, lang):
    if 'by_location' in result:
        head = 'Cuentas por país' if lang == 'es' else 'Accounts by country'
        unit = 'cuentas' if lang == 'es' else 'accounts'
        subs = 'suscriptores' if lang == 'es' else 'subscribers'
        out = f"**{head}:**\n\n"
        for r in result['by_location']:
            out += f"• **{r['location']}:** {r['accounts']} {unit} ({r['total_subscribers']:,} {subs})\n"
        return out
    if not result.get('found'):
        return (f"No se encontraron cuentas para «{result.get('country')}»." if lang == 'es'
                else f"No accounts found for \"{result.get('country')}\".")
    subs = 'suscriptores' if lang == 'es' else 'subscribers'
    if lang == 'es':
        out = f"**{result['country']}:** {result['accounts']} cuentas · {result['total_subscribers']:,} {subs} · {result['verified']} verificadas\n\n**Top 5:**\n"
    else:
        out = f"**{result['country']}:** {result['accounts']} accounts · {result['total_subscribers']:,} {subs} · {result['verified']} verified\n\n**Top 5:**\n"
    for i, a in enumerate(result['top'], 1):
        out += f"{i}. {a['account_name']} — {a['subscribers']:,}\n"
    return out


def _md_year(result, lang):
    if 'by_year' in result:
        head = 'Cuentas por año de creación' if lang == 'es' else 'Accounts by creation year'
        unit = 'cuentas' if lang == 'es' else 'accounts'
        out = f"**{head}:**\n\n"
        for r in result['by_year']:
            out += f"• {r['year']}: {r['accounts']} {unit}\n"
        return out
    if not result.get('found'):
        return (f"No se encontraron cuentas creadas en {result['year']}." if lang == 'es'
                else f"No accounts created in {result['year']}.")
    if lang == 'es':
        out = f"**Cuentas creadas en {result['year']}:** {result['accounts']}\n\n• Suscriptores: {result['total_subscribers']:,}\n• Promedio: {result['avg_subscribers']:,}\n\n**Top 5:**\n"
    else:
        out = f"**Accounts created in {result['year']}:** {result['accounts']}\n\n• Subscribers: {result['total_subscribers']:,}\n• Average: {result['avg_subscribers']:,}\n\n**Top 5:**\n"
    for i, a in enumerate(result['top'], 1):
        out += f"{i}. {a['account_name']} — {a['subscribers']:,}\n"
    return out


def _md_program(result, lang):
    head = 'Cuentas por programa de monetización' if lang == 'es' else 'Accounts by monetization program'
    unit = 'cuentas' if lang == 'es' else 'accounts'
    out = f"**{head}:**\n\n"
    for prog, count in sorted(result['programs'].items(), key=lambda x: x[1], reverse=True):
        out += f"• **{prog}:** {count} {unit}\n"
    if lang == 'es':
        out += f"\n**Activas (últimos 90 días):** {result['active_last_90_days']} cuentas"
    else:
        out += f"\n**Active (last 90 days):** {result['active_last_90_days']} accounts"
    return out


def _md_language(result, lang):
    head = 'Cuentas por idioma' if lang == 'es' else 'Accounts by language'
    unit = 'cuentas' if lang == 'es' else 'accounts'
    out = f"**{head}:**\n\n"
    for r in result['by_language']:
        out += f"• **{r['language']}:** {r['accounts']} {unit}\n"
    return out


def _md_summary(result, lang):
    if lang == 'es':
        out = (f"**Resumen de la base de datos:**\n\n"
               f"• **Total de cuentas:** {result['total_accounts']:,}\n"
               f"• **Verificadas:** {result['verified_accounts']} ({result['pct_verified']}%)\n"
               f"• **Total de suscriptores:** {result['total_subscribers']:,}\n"
               f"• **Promedio:** {result['avg_subscribers']:,}\n"
               f"• **Mediana:** {result['median_subscribers']:,}\n\n**Por país:**\n")
    else:
        out = (f"**Database summary:**\n\n"
               f"• **Total accounts:** {result['total_accounts']:,}\n"
               f"• **Verified:** {result['verified_accounts']} ({result['pct_verified']}%)\n"
               f"• **Total subscribers:** {result['total_subscribers']:,}\n"
               f"• **Average:** {result['avg_subscribers']:,}\n"
               f"• **Median:** {result['median_subscribers']:,}\n\n**By country:**\n")
    for r in result['top_locations']:
        out += f"• {r['location']}: {r['accounts']}\n"
    out += ('\n**Por idioma:**\n' if lang == 'es' else '\n**By language:**\n')
    for r in result['top_languages']:
        out += f"• {r['language']}: {r['accounts']}\n"
    return out


def _md_search(result, lang):
    if not result['matches']:
        return (f"No se encontró ninguna cuenta que coincida con «{result['query']}»." if lang == 'es'
                else f"No account matches \"{result['query']}\".")
    head = f"{result['count']} coincidencias" if lang == 'es' else f"{result['count']} matches"
    subs = 'suscriptores' if lang == 'es' else 'subscribers'
    out = f"**{head}:**\n\n"
    for i, a in enumerate(result['matches'], 1):
        v = ' ✓' if a.get('verified') else ''
        out += f"{i}. **{a['account_name']}**{v} — {a['subscribers']:,} {subs} ({a.get('location','')})\n"
    return out


_MD_RENDERERS = {
    'top_accounts': _md_top,
    'verified_stats': _md_verified,
    'by_location': _md_location,
    'by_year': _md_year,
    'by_monetization_program': _md_program,
    'by_language': _md_language,
    'summary_stats': _md_summary,
    'search_accounts': _md_search,
}


def render_tool_result_md(name, result, lang='es'):
    fn = _MD_RENDERERS.get(name)
    return fn(result, lang) if fn else json.dumps(result, ensure_ascii=False)


def _help_text(lang):
    if lang == 'es':
        return ("**Consultas disponibles:**\n\n"
                "• **Top cuentas:** \"Top 10 cuentas por suscriptores\"\n"
                "• **Verificación:** \"¿Cuántas cuentas están verificadas?\"\n"
                "• **País:** \"Cuentas por país\" / \"Cuentas en Guatemala\"\n"
                "• **Año:** \"Cuentas creadas en 2023\"\n"
                "• **Monetización:** \"¿Qué programas de monetización usan?\"\n"
                "• **Idioma:** \"Cuentas por idioma\"\n"
                "• **Buscar:** \"Busca <nombre o handle>\"\n"
                "• **Resumen:** \"Estadísticas generales\"")
    return ("**Available queries:**\n\n"
            "• **Top accounts:** \"Top 10 accounts by subscribers\"\n"
            "• **Verification:** \"How many accounts are verified?\"\n"
            "• **Country:** \"Accounts by country\" / \"Accounts in Guatemala\"\n"
            "• **Year:** \"Accounts created in 2023\"\n"
            "• **Monetization:** \"What monetization programs do they use?\"\n"
            "• **Language:** \"Accounts by language\"\n"
            "• **Search:** \"Search for <name or handle>\"\n"
            "• **Summary:** \"Overall stats\"")


def process_query(query, lang='es'):
    """Local keyword engine: route the query to a tool function and render Markdown.

    This is the fallback path used when no Anthropic key is set or the AI call fails.
    """
    q = (query or '').lower()

    # Search: "busca X" / "search X" / "is X in the data"
    m = re.search(r'(?:busca(?:r)?|search(?:\s+for)?)\s+(.+)', q)
    if m:
        return render_tool_result_md('search_accounts', tool_search_accounts(m.group(1).strip(), 10), lang)

    # Top accounts
    if any(w in q for w in ['top', 'mejores', 'mayores', 'más suscriptores', 'mas suscriptores', 'largest', 'biggest']):
        nums = re.findall(r'\d+', q)
        n = min(int(nums[0]), 50) if nums else 10
        return render_tool_result_md('top_accounts', tool_top_accounts(n), lang)

    # Verified
    if 'verificad' in q or 'verified' in q:
        return render_tool_result_md('verified_stats', tool_verified_stats(), lang)

    # Location / country
    if any(w in q for w in ['ubicación', 'ubicacion', 'país', 'pais', 'location', 'country', 'guatemala', 'honduras', 'salvador', 'nicaragua', 'costa rica', 'méxico', 'mexico', 'colombia', 'brasil', 'brazil', 'argentina', 'chile', 'perú', 'peru']):
        return render_tool_result_md('by_location', tool_by_location(), lang)

    # Year
    if any(w in q for w in ['año', 'anio', 'year']) or re.search(r'20\d{2}', q):
        ym = re.search(r'20\d{2}', q)
        year = int(ym.group()) if ym else None
        return render_tool_result_md('by_year', tool_by_year(year), lang)

    # Monetization
    if any(w in q for w in ['monetiza', 'programa', 'program', 'ads', 'reels', 'stream']):
        return render_tool_result_md('by_monetization_program', tool_by_monetization_program(), lang)

    # Language
    if any(w in q for w in ['idioma', 'lenguaje', 'language', 'español', 'english']):
        return render_tool_result_md('by_language', tool_by_language(), lang)

    # Summary
    if any(w in q for w in ['estadística', 'estadistica', 'resumen', 'summary', 'total', 'cuánta', 'cuanta', 'stats', 'overview']):
        return render_tool_result_md('summary_stats', tool_summary_stats(), lang)

    return _help_text(lang)


@app.route('/api/query', methods=['POST'])
def natural_language_query():
    """Process natural language queries about the data (local keyword engine)."""
    if DATA.empty:
        return jsonify({'error': 'No data available'}), 500

    data = request.get_json(silent=True)
    query = data.get('query', '') if data else ''

    if not query:
        return jsonify({'error': 'No query provided'}), 400

    response = process_query(query, resolve_lang())
    return jsonify({'response': response, 'query': query})


# ==================== AI CHAT (Claude tool-use) ====================

ANTHROPIC_TOOLS = [
    {
        'name': 'top_accounts',
        'description': 'Get the top accounts by subscriber count. Use for "top/largest/biggest accounts", optionally filtered by country (admin location name or ISO-2 code) and/or verified only.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'n': {'type': 'integer', 'description': 'How many accounts (max 50).'},
                'location': {'type': 'string', 'description': 'Country name (e.g. "Guatemala") or ISO-2 code (e.g. "GT"). Optional.'},
                'verified_only': {'type': 'boolean', 'description': 'Restrict to verified accounts.'},
            },
        },
    },
    {
        'name': 'verified_stats',
        'description': 'Count and share of verified accounts, plus the 5 largest verified accounts.',
        'input_schema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'by_location',
        'description': 'Accounts aggregated per country. Pass a country name/code to get detail for one country instead.',
        'input_schema': {
            'type': 'object',
            'properties': {'country': {'type': 'string', 'description': 'Country name or ISO-2 code. Omit for the full per-country breakdown.'}},
        },
    },
    {
        'name': 'by_year',
        'description': 'Accounts by page creation year. Pass a year for detail (count, subscribers, top 5) for that year.',
        'input_schema': {
            'type': 'object',
            'properties': {'year': {'type': 'integer', 'description': 'A 4-digit year. Omit for the full histogram.'}},
        },
    },
    {
        'name': 'by_monetization_program',
        'description': 'How many accounts use each Meta monetization program (Instant Articles, In-Stream Ads, Ads on Reels, Content Monetization) and how many are active in the last 90 days.',
        'input_schema': {
            'type': 'object',
            'properties': {'program': {'type': 'string', 'description': 'Optional program name to get detail for one program.'}},
        },
    },
    {
        'name': 'by_language',
        'description': 'Accounts grouped by language. Pass a language to get the count for that language.',
        'input_schema': {
            'type': 'object',
            'properties': {'language': {'type': 'string', 'description': 'Optional language name (e.g. "Spanish").'}},
        },
    },
    {
        'name': 'summary_stats',
        'description': 'Overall dataset summary: totals, verified share, subscriber sum/avg/median, top countries and languages.',
        'input_schema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'search_accounts',
        'description': 'Find specific accounts by name, handle, or ID (substring match). Use this to check whether a particular account is in the dataset.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'description': 'Name, handle, or ID to search for.'},
                'limit': {'type': 'integer', 'description': 'Max results (max 25).'},
            },
            'required': ['query'],
        },
    },
]

SYSTEM_PROMPT = (
    "Eres un asistente de datos del Archivo de Monetización de Meta para América Latina, "
    "una herramienta de J-Lab (con datos de monetization.wtf / WHAT TO FIX). El conjunto de "
    "datos lista cuentas de Facebook e Instagram inscritas en los programas de redistribución "
    "de ingresos de Meta.\n\n"
    "Reglas:\n"
    "- Responde ÚNICAMENTE con base en los resultados de las herramientas. Nunca inventes "
    "cuentas, cifras ni países.\n"
    "- Si los datos no contienen la respuesta, dilo con claridad.\n"
    "- Responde en el idioma del usuario (español por defecto).\n"
    "- Sé conciso, cita números exactos y usa Markdown (listas, negritas) cuando ayude.\n"
    "- Recuerda al usuario, cuando sea pertinente, que las señales (ráfagas, crecimiento atípico) "
    "son pistas para investigar, no acusaciones."
)


@app.route('/api/ai/chat', methods=['POST'])
def ai_chat():
    """Real AI chat grounded in the dataset via Claude tool-use.

    Degrades gracefully to the local keyword engine on any failure (HTTP 200).
    """
    if DATA.empty:
        return jsonify({'error': 'No data available'}), 500

    body = request.get_json(silent=True) or {}
    user_msg = (body.get('query') or '').strip()
    if not user_msg:
        return jsonify({'error': 'No query provided'}), 400

    lang = resolve_lang()

    # No key / SDK missing -> local engine.
    if not AI_ENABLED:
        return jsonify({'response': process_query(user_msg, lang), 'engine': 'local', 'query': user_msg})

    try:
        messages = [{'role': 'user', 'content': user_msg}]
        for _ in range(MAX_TOOL_TURNS):
            resp = _anthropic_client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=1500,
                system=SYSTEM_PROMPT,
                tools=ANTHROPIC_TOOLS,
                messages=messages,
            )
            if resp.stop_reason != 'tool_use':
                text = ''.join(b.text for b in resp.content if b.type == 'text')
                return jsonify({'response': text, 'engine': 'claude', 'model': ANTHROPIC_MODEL, 'query': user_msg})
            messages.append({'role': 'assistant', 'content': resp.content})
            tool_results = [
                {
                    'type': 'tool_result',
                    'tool_use_id': b.id,
                    'content': json.dumps(run_tool(b.name, b.input), ensure_ascii=False),
                }
                for b in resp.content if b.type == 'tool_use'
            ]
            messages.append({'role': 'user', 'content': tool_results})
        # Loop cap reached -> degrade rather than error.
        return jsonify({'response': process_query(user_msg, lang), 'engine': 'local-fallback', 'note': 'max_tool_turns', 'query': user_msg})
    except Exception as e:  # rate limits, API errors, anything
        app.logger.warning('AI chat failed: %s', e)
        note = 'rate_limited' if anthropic and isinstance(e, getattr(anthropic, 'RateLimitError', ())) else 'error'
        return jsonify({'response': process_query(user_msg, lang), 'engine': 'local-fallback', 'note': note, 'query': user_msg})


@app.route('/api/ai/status')
def ai_status():
    """Tells the frontend whether the grounded AI path is available."""
    return jsonify({'ai_enabled': AI_ENABLED, 'model': ANTHROPIC_MODEL if AI_ENABLED else None})


# ==================== ANALYSIS ENDPOINTS ====================
# Pure pandas over existing columns. Outputs are leads for reporting, not verdicts.

@app.route('/api/analysis/coordinated-bursts')
def analysis_coordinated_bursts():
    """Accounts created the same day in the same country (coordination signal)."""
    if DATA.empty:
        return jsonify({'error': 'No data available'}), 500
    min_count = max(2, request.args.get('min', 3, type=int))
    df = DATA.dropna(subset=['page_created_date']).copy()
    df['cdate'] = df['page_created_date'].dt.strftime('%Y-%m-%d')
    clusters = []
    for (date, loc), grp in df.groupby(['cdate', 'admin_location']):
        if len(grp) >= min_count:
            clusters.append({
                'date': date,
                'location': loc,
                'account_count': int(len(grp)),
                'total_subscribers': int(grp['account_subscriber_count'].sum()),
                'accounts': [
                    {'account_id': str(r['account_id']), 'account_name': r['account_name'],
                     'subscribers': int(r['account_subscriber_count']), 'verified': bool(r['account_verified'])}
                    for _, r in grp.nlargest(15, 'account_subscriber_count').iterrows()
                ],
            })
    clusters.sort(key=lambda c: c['account_count'], reverse=True)
    return jsonify({'min_count': min_count, 'cluster_count': len(clusters), 'clusters': clusters[:50]})


@app.route('/api/analysis/program-migration')
def analysis_program_migration():
    """Share of accounts per program, by account-creation cohort year."""
    if DATA.empty:
        return jsonify({'error': 'No data available'}), 500
    df = DATA.dropna(subset=['page_created_date']).copy()
    df['year'] = df['page_created_date'].dt.year.astype(int)
    rows = []
    for year, grp in df.groupby('year'):
        rows.append({
            'year': int(year),
            'accounts': int(len(grp)),
            'instant_articles': int((grp['facebook_instant_articles_session_count'] > 0).sum()),
            'in_stream': int((grp['facebook_in_stream_ads_session_count'] > 0).sum()),
            'reels': int((grp['facebook_ads_on_reels_session_count'] > 0).sum()),
            'content_monetization': int((grp['facebook_content_monetization_session_count'] > 0).sum()),
        })
    rows.sort(key=lambda r: r['year'])
    return jsonify({'by_year': rows})


@app.route('/api/analysis/verified-gap')
def analysis_verified_gap():
    """Verified vs unverified monetization per country."""
    if DATA.empty:
        return jsonify({'error': 'No data available'}), 500
    rows = []
    for loc, grp in DATA.groupby('admin_location'):
        v = grp[grp['account_verified'] == True]
        u = grp[grp['account_verified'] == False]
        total = len(grp)
        rows.append({
            'location': loc,
            'verified': int(len(v)),
            'unverified': int(len(u)),
            'verified_subs': int(v['account_subscriber_count'].sum()),
            'unverified_subs': int(u['account_subscriber_count'].sum()),
            'pct_unverified': round(len(u) / total * 100, 1) if total else 0.0,
        })
    rows.sort(key=lambda r: r['unverified'], reverse=True)
    return jsonify({'by_location': rows})


@app.route('/api/analysis/country-asymmetry')
def analysis_country_asymmetry():
    """Per-country normalized metrics for fair comparison."""
    if DATA.empty:
        return jsonify({'error': 'No data available'}), 500
    now = datetime.now()
    rows = []
    for loc, grp in DATA.groupby('admin_location'):
        n = len(grp)
        subs = int(grp['account_subscriber_count'].sum())
        active = int((grp['last_recorded_monetization'] >= now - pd.Timedelta(days=90)).sum())
        rows.append({
            'location': loc,
            'accounts': int(n),
            'total_subscribers': subs,
            'subs_per_account': int(subs / n) if n else 0,
            'verified_rate': round(grp['account_verified'].mean() * 100, 1) if n else 0.0,
            'active_rate': round(active / n * 100, 1) if n else 0.0,
        })
    rows.sort(key=lambda r: r['accounts'], reverse=True)
    return jsonify({'by_location': rows})


@app.route('/api/analysis/growth-outliers')
def analysis_growth_outliers():
    """Young pages with unusually large audiences (subs/day + per-country z-score)."""
    if DATA.empty:
        return jsonify({'error': 'No data available'}), 500
    now = pd.Timestamp(datetime.now())
    df = DATA.dropna(subset=['page_created_date']).copy()
    df = df[df['account_subscriber_count'] > 0]
    if df.empty:
        return jsonify({'outliers': []})
    age_days = (now - df['page_created_date']).dt.days.clip(lower=1)
    df['page_age_days'] = age_days
    df['subs_per_day'] = df['account_subscriber_count'] / age_days
    g = df.groupby('admin_location')['account_subscriber_count']
    df['z_score'] = g.transform(lambda x: (x - x.mean()) / x.std(ddof=0) if x.std(ddof=0) > 0 else 0.0)
    out = df.nlargest(25, 'subs_per_day')
    return jsonify({'outliers': [
        {
            'account_id': str(r['account_id']),
            'account_name': r['account_name'],
            'location': r['admin_location'],
            'subscribers': int(r['account_subscriber_count']),
            'page_age_days': int(r['page_age_days']),
            'subs_per_day': round(float(r['subs_per_day']), 1),
            'z_score': round(float(r['z_score']), 2),
            'page_created_date': r['page_created_date'].strftime('%Y-%m-%d'),
            'verified': bool(r['account_verified']),
        }
        for _, r in out.iterrows()
    ]})


# ==================== RUN ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
