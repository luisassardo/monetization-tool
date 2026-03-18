"""
Monetization Tool API - Backend for Facebook Monetization Data Explorer
Deployable on Render, Railway, or any Python hosting platform
"""

from flask import Flask, jsonify, request, render_template, redirect
from flask_cors import CORS
import pandas as pd
import os
import json
from datetime import datetime
import re

app = Flask(__name__)
CORS(app)  # Enable CORS for widget embedding

# Load data
DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'accounts.csv')

def load_data():
    """Load and preprocess the CSV data"""
    df = pd.read_csv(DATA_PATH)
    # Convert verified to boolean
    df['account_verified'] = df['account_verified'].astype(str).str.lower() == 'true'
    # Convert subscriber count to int
    df['account_subscriber_count'] = pd.to_numeric(df['account_subscriber_count'], errors='coerce').fillna(0).astype(int)
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


# ==================== API ROUTES ====================

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')


@app.route('/cuenta/<account_id>')
def account_detail(account_id):
    """Individual account detail page"""
    return render_template('account.html', account_id=account_id)


@app.route('/widget')
def widget():
    """Embeddable widget version"""
    return render_template('widget.html')


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
    
    programs = {
        'Instant Articles': int(DATA['facebook_instant_articles_session_count'].sum()),
        'In-Stream Ads': int(DATA['facebook_in_stream_ads_session_count'].sum()),
        'Ads on Reels': int(DATA['facebook_ads_on_reels_session_count'].sum()),
        'Content Monetization': int(DATA['facebook_content_monetization_session_count'].sum())
    }
    
    # Count accounts per program (with at least 1 session)
    accounts_per_program = {
        'Instant Articles': int((DATA['facebook_instant_articles_session_count'] > 0).sum()),
        'In-Stream Ads': int((DATA['facebook_in_stream_ads_session_count'] > 0).sum()),
        'Ads on Reels': int((DATA['facebook_ads_on_reels_session_count'] > 0).sum()),
        'Content Monetization': int((DATA['facebook_content_monetization_session_count'] > 0).sum())
    }
    
    return jsonify({
        'sessions': programs,
        'accounts': accounts_per_program
    })


@app.route('/api/query', methods=['POST'])
def natural_language_query():
    """Process natural language queries about the data"""
    if DATA.empty:
        return jsonify({'error': 'No data available'}), 500
    
    data = request.get_json()
    query = data.get('query', '').lower() if data else ''
    
    if not query:
        return jsonify({'error': 'No query provided'}), 400
    
    # Process common queries locally
    response = process_query(query)
    
    return jsonify({'response': response, 'query': query})


def process_query(query):
    """Process natural language query and return response"""
    query = query.lower()
    
    # Top accounts by subscribers
    if any(word in query for word in ['top', 'mejores', 'mayores', 'más suscriptores', 'mas suscriptores']):
        n = 10
        numbers = re.findall(r'\d+', query)
        if numbers:
            n = min(int(numbers[0]), 50)
        
        top = DATA.nlargest(n, 'account_subscriber_count')[['account_name', 'account_subscriber_count', 'account_verified', 'admin_location']]
        result = f"**Top {n} cuentas por suscriptores:**\n\n"
        for i, (_, row) in enumerate(top.iterrows(), 1):
            verified = " ✓" if row['account_verified'] else ""
            result += f"{i}. **{row['account_name']}**{verified} — {row['account_subscriber_count']:,} suscriptores ({row['admin_location']})\n"
        return result
    
    # Verified accounts
    if 'verificad' in query:
        verified = DATA[DATA['account_verified'] == True]
        total = len(verified)
        pct = (total / len(DATA) * 100) if len(DATA) > 0 else 0
        
        result = f"**Cuentas verificadas:** {total} de {len(DATA)} ({pct:.1f}%)\n\n"
        result += "**Top 5 cuentas verificadas:**\n"
        for i, (_, row) in enumerate(verified.nlargest(5, 'account_subscriber_count').iterrows(), 1):
            result += f"{i}. {row['account_name']} — {row['account_subscriber_count']:,} suscriptores\n"
        return result
    
    # By location/country
    if any(word in query for word in ['ubicación', 'ubicacion', 'país', 'pais', 'location', 'country', 'guatemala', 'honduras', 'salvador']):
        loc_stats = DATA.groupby('admin_location').agg({
            'account_id': 'count',
            'account_subscriber_count': 'sum'
        }).reset_index()
        loc_stats.columns = ['Ubicación', 'Cuentas', 'Suscriptores']
        loc_stats = loc_stats.sort_values('Cuentas', ascending=False)
        
        result = "**Cuentas por ubicación:**\n\n"
        for _, row in loc_stats.iterrows():
            result += f"• **{row['Ubicación']}:** {row['Cuentas']} cuentas ({row['Suscriptores']:,} suscriptores)\n"
        return result
    
    # By year
    if any(word in query for word in ['año', 'anio', 'year', '2020', '2021', '2022', '2023', '2024', '2025']):
        year_match = re.search(r'20\d{2}', query)
        if year_match:
            year = int(year_match.group())
            year_data = DATA[DATA['page_created_date'].dt.year == year]
            if len(year_data) == 0:
                return f"No se encontraron cuentas creadas en {year}."
            
            result = f"**Cuentas creadas en {year}:** {len(year_data)}\n\n"
            result += f"• Suscriptores totales: {year_data['account_subscriber_count'].sum():,}\n"
            result += f"• Promedio de suscriptores: {int(year_data['account_subscriber_count'].mean()):,}\n\n"
            result += "**Top 5:**\n"
            for i, (_, row) in enumerate(year_data.nlargest(5, 'account_subscriber_count').iterrows(), 1):
                result += f"{i}. {row['account_name']} — {row['account_subscriber_count']:,}\n"
            return result
        else:
            # Show by year summary
            year_stats = DATA.groupby(DATA['page_created_date'].dt.year).size()
            result = "**Cuentas por año de creación:**\n\n"
            for year, count in sorted(year_stats.items()):
                if pd.notna(year):
                    result += f"• {int(year)}: {count} cuentas\n"
            return result
    
    # Monetization
    if any(word in query for word in ['monetiza', 'programa', 'ads', 'reels', 'stream']):
        programs = {
            'Instant Articles': int((DATA['facebook_instant_articles_session_count'] > 0).sum()),
            'In-Stream Ads': int((DATA['facebook_in_stream_ads_session_count'] > 0).sum()),
            'Ads on Reels': int((DATA['facebook_ads_on_reels_session_count'] > 0).sum()),
            'Content Monetization': int((DATA['facebook_content_monetization_session_count'] > 0).sum())
        }
        
        result = "**Cuentas por programa de monetización:**\n\n"
        for prog, count in sorted(programs.items(), key=lambda x: x[1], reverse=True):
            result += f"• **{prog}:** {count} cuentas\n"
        
        # Active in last 3 months
        recent = (DATA['last_recorded_monetization'] >= datetime.now() - pd.Timedelta(days=90)).sum()
        result += f"\n**Activas (últimos 90 días):** {recent} cuentas"
        return result
    
    # Language
    if any(word in query for word in ['idioma', 'lenguaje', 'language', 'español', 'english']):
        lang_stats = DATA['account_language'].value_counts()
        result = "**Cuentas por idioma:**\n\n"
        for lang, count in lang_stats.items():
            result += f"• **{lang}:** {count} cuentas\n"
        return result
    
    # Statistics / summary
    if any(word in query for word in ['estadísticas', 'estadisticas', 'resumen', 'summary', 'total', 'cuántas', 'cuantas']):
        result = f"""**Resumen de la base de datos:**

• **Total de cuentas:** {len(DATA):,}
• **Cuentas verificadas:** {DATA['account_verified'].sum()} ({DATA['account_verified'].mean()*100:.1f}%)
• **Total de suscriptores:** {DATA['account_subscriber_count'].sum():,}
• **Promedio de suscriptores:** {int(DATA['account_subscriber_count'].mean()):,}
• **Mediana de suscriptores:** {int(DATA['account_subscriber_count'].median()):,}

**Por ubicación:**
{chr(10).join([f"• {loc}: {count}" for loc, count in DATA['admin_location'].value_counts().head(5).items()])}

**Por idioma:**
{chr(10).join([f"• {lang}: {count}" for lang, count in DATA['account_language'].value_counts().head(5).items()])}
"""
        return result
    
    # Default response
    return """**Consultas disponibles:**

Puedes preguntar sobre:
• **Top cuentas:** "Top 10 cuentas por suscriptores"
• **Verificación:** "¿Cuántas cuentas están verificadas?"
• **Ubicación:** "Cuentas por país"
• **Año:** "Cuentas creadas en 2023"
• **Monetización:** "¿Qué programas de monetización usan?"
• **Idioma:** "Cuentas por idioma"
• **Resumen:** "Estadísticas generales"

Intenta con una de estas consultas."""


@app.route('/api/filters')
def get_filters():
    """Get available filter options"""
    if DATA.empty:
        return jsonify({'error': 'No data available'}), 500
    
    return jsonify({
        'locations': sorted(DATA['admin_location'].dropna().unique().tolist()),
        'languages': sorted(DATA['account_language'].dropna().unique().tolist())
    })


# ==================== RUN ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
